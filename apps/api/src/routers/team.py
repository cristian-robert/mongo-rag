"""Team management endpoints: members + invitations.

Authorization is enforced via ``require_role``:
* listing members / invitations: any authenticated user (member+)
* creating / revoking invitations: admin+
* changing roles / removing members: admin+ (with owner-only rules in service)

Accept-invite endpoints are public so far as they accept either:
* a signed-in dashboard user that matches the invite email, OR
* a new user signing up + accepting in one step.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.authz import Principal, get_principal, require_role
from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.settings import load_settings
from src.models.api import (
    AcceptInvitationRequest,
    AcceptInvitationSignupRequest,
    CreateInvitationRequest,
    CreateInvitationResponse,
    InvitationListResponse,
    InvitationPreviewResponse,
    InvitationResponse,
    LoginResponse,
    MemberListResponse,
    MemberResponse,
    MessageResponse,
    UpdateMemberRoleRequest,
)
from src.models.user import UserRole
from src.services.team import TeamError, TeamService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/team", tags=["team"])


def _service(deps: AgentDependencies = Depends(get_deps)) -> TeamService:
    settings = load_settings()
    return TeamService(
        users_collection=deps.users_collection,
        tenants_collection=deps.tenants_collection,
        invitations_collection=deps.invitations_collection,
        invitation_ttl_hours=settings.invitation_ttl_hours,
    )


def _accept_url(token: str) -> str:
    settings = load_settings()
    base = settings.app_url.rstrip("/")
    return f"{base}/invite/{token}"


# --- Members -----------------------------------------------------------


@router.get("/members", response_model=MemberListResponse)
async def list_members(
    principal: Principal = Depends(get_principal),
    service: TeamService = Depends(_service),
):
    """Any authenticated user can see who else is on the team."""
    members = await service.list_members(principal.tenant_id)
    return MemberListResponse(members=[MemberResponse(**m) for m in members])


@router.patch("/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    user_id: str,
    body: UpdateMemberRoleRequest,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: TeamService = Depends(_service),
):
    try:
        updated = await service.update_member_role(
            tenant_id=principal.tenant_id,
            target_user_id=user_id,
            new_role=UserRole(body.role),
            actor_user_id=principal.user_id,
            actor_role=UserRole(principal.role),
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")
    return MemberResponse(**updated)


@router.delete("/members/{user_id}", response_model=MessageResponse)
async def remove_member(
    user_id: str,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: TeamService = Depends(_service),
):
    try:
        removed = await service.remove_member(
            tenant_id=principal.tenant_id,
            target_user_id=user_id,
            actor_user_id=principal.user_id,
            actor_role=UserRole(principal.role),
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return MessageResponse(message="Member removed")


# --- Invitations -------------------------------------------------------


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: TeamService = Depends(_service),
):
    invites = await service.list_invitations(principal.tenant_id)
    return InvitationListResponse(
        invitations=[InvitationResponse(**i) for i in invites]
    )


@router.post(
    "/invitations",
    response_model=CreateInvitationResponse,
    status_code=201,
)
async def create_invitation(
    body: CreateInvitationRequest,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: TeamService = Depends(_service),
):
    try:
        record, raw_token = await service.create_invitation(
            tenant_id=principal.tenant_id,
            email=body.email,
            role=UserRole(body.role),
            invited_by_user_id=principal.user_id,
            actor_role=UserRole(principal.role),
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return CreateInvitationResponse(
        invitation=InvitationResponse(**record),
        accept_url=_accept_url(raw_token),
    )


@router.delete("/invitations/{invitation_id}", response_model=MessageResponse)
async def revoke_invitation(
    invitation_id: str,
    principal: Principal = Depends(require_role(UserRole.ADMIN)),
    service: TeamService = Depends(_service),
):
    revoked = await service.revoke_invitation(
        tenant_id=principal.tenant_id,
        invitation_id=invitation_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return MessageResponse(message="Invitation revoked")


# --- Accept (public) ---------------------------------------------------


@router.get(
    "/invitations/{token}/preview",
    response_model=InvitationPreviewResponse,
)
async def preview_invitation(
    token: str,
    service: TeamService = Depends(_service),
):
    """Public: look up an invitation for the accept page.

    Returns 404 for unknown / expired / revoked tokens to avoid enumeration.
    """
    preview = await service.preview_invitation(token)
    if not preview:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return InvitationPreviewResponse(**preview)


@router.post("/invitations/{token}/accept", response_model=LoginResponse)
async def accept_invitation(
    token: str,
    body: AcceptInvitationRequest,
    principal: Principal = Depends(get_principal),
    service: TeamService = Depends(_service),
):
    """Authenticated path: an existing user accepts their invite.

    The path token MUST equal the body token — defends against CSRF that
    swaps the path while reusing a stale body.
    """
    if token != body.token:
        raise HTTPException(status_code=400, detail="Token mismatch")

    user = await service._users.find_one(  # noqa: SLF001 — internal helper
        {"_id": _safe_oid(principal.user_id)}
    )
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")

    try:
        result = await service.accept_invitation_existing_user(
            raw_token=body.token,
            acting_user_id=principal.user_id,
            acting_email=user["email"],
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return LoginResponse(
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        email=user["email"],
        name=user.get("name", ""),
        role=result["role"],
    )


@router.post(
    "/invitations/{token}/accept-signup",
    response_model=LoginResponse,
    status_code=201,
)
async def accept_invitation_signup(
    token: str,
    body: AcceptInvitationSignupRequest,
    request: Request,
    deps: AgentDependencies = Depends(get_deps),
    service: TeamService = Depends(_service),
):
    """Public: a brand-new user signs up + accepts the invite atomically.

    Rate-limited per source IP to deter token enumeration / brute force.
    """
    if token != body.token:
        raise HTTPException(status_code=400, detail="Token mismatch")

    await _enforce_invite_rate_limit(request, deps)

    try:
        result = await service.accept_invitation_new_user(
            raw_token=body.token,
            password=body.password,
            name=body.name,
        )
    except TeamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return LoginResponse(
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        email=result["email"],
        name=body.name or "",
        role=result["role"],
    )


# --- helpers -----------------------------------------------------------


def _safe_oid(value: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc


async def _enforce_invite_rate_limit(
    request: Request,
    deps: AgentDependencies,
) -> None:
    """Cap accept-signup attempts per source IP."""
    from src.services.rate_limit import get_default_limiter

    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    key = f"invite-accept:{client_ip}"
    limiter = get_default_limiter()
    result = await limiter.check(key, limit=10, window_seconds=60)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many invitation attempts; try again later",
            headers={"Retry-After": str(result.reset_in)},
        )
