"""Authentication endpoints: signup, login, password reset."""

import asyncio
import logging

import resend
from fastapi import APIRouter, Depends, HTTPException

from src.core.authz import Principal, get_principal
from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.rate_limit_dep import enforce_auth_ip_rate_limit
from src.core.settings import Settings
from src.core.tenant import get_tenant_id
from src.models.api import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    WSTicketResponse,
)
from src.services.auth import AuthService
from src.services.ws_ticket import WSTicketService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_auth_service(deps: AgentDependencies = Depends(get_deps)) -> AuthService:
    """Create AuthService with injected collections."""
    return AuthService(
        users_collection=deps.users_collection,
        tenants_collection=deps.tenants_collection,
        reset_tokens_collection=deps.reset_tokens_collection,
    )


async def _send_reset_email(email: str, token: str, settings: Settings) -> None:
    """Send password reset email via Resend."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured — reset email not sent to %s", email)
        return
    reset_url = f"{settings.app_url}/reset-password?token={token}"
    try:
        resend.api_key = settings.resend_api_key
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": settings.reset_email_from,
                "to": [email],
                "subject": "Reset your MongoRAG password",
                "html": (
                    f"<p>You requested a password reset.</p>"
                    f'<p><a href="{reset_url}">Click here to reset your password</a></p>'
                    f"<p>This link expires in 1 hour.</p>"
                    f"<p>If you did not request this, ignore this email.</p>"
                ),
            },
        )
    except Exception:
        logger.exception("Failed to send reset email to %s", email)


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=201,
    dependencies=[Depends(enforce_auth_ip_rate_limit)],
)
async def signup(
    body: SignupRequest,
    service: AuthService = Depends(_get_auth_service),
):
    """Register a new user and create their tenant."""
    try:
        result = await service.signup(
            email=body.email,
            password=body.password,
            organization_name=body.organization_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return SignupResponse(**result)


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(enforce_auth_ip_rate_limit)],
)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(_get_auth_service),
):
    """Validate credentials and return user data for Auth.js."""
    try:
        result = await service.login(email=body.email, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return LoginResponse(**result)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(enforce_auth_ip_rate_limit)],
)
async def forgot_password(
    body: ForgotPasswordRequest,
    service: AuthService = Depends(_get_auth_service),
    deps: AgentDependencies = Depends(get_deps),
):
    """Send a password reset email.

    Always returns 200 regardless of whether the email exists
    (prevents email enumeration).
    """
    raw_token = await service.create_password_reset_token(email=body.email)

    if raw_token:
        settings = deps.settings
        await _send_reset_email(body.email, raw_token, settings)

    return MessageResponse(
        message="If that email is registered, check your email for a reset link."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(enforce_auth_ip_rate_limit)],
)
async def reset_password(
    body: ResetPasswordRequest,
    service: AuthService = Depends(_get_auth_service),
):
    """Reset password using a valid reset token."""
    try:
        await service.reset_password(token=body.token, new_password=body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MessageResponse(message="Password has been reset successfully.")


@router.get("/me", response_model=MeResponse)
async def get_me(
    principal: Principal = Depends(get_principal),
    deps: AgentDependencies = Depends(get_deps),
):
    """Return the current user — used by the dashboard for role-gated UI."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(principal.user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=401, detail="Unknown user")

    user = await deps.users_collection.find_one(
        {"_id": oid, "tenant_id": principal.tenant_id}
    )
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")

    # Always trust the DB role over the JWT role to defeat stale tokens.
    return MeResponse(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        email=user["email"],
        name=user.get("name", ""),
        role=user.get("role", "viewer"),
    )


@router.post("/ws-ticket", response_model=WSTicketResponse)
async def create_ws_ticket(
    tenant_id: str = Depends(get_tenant_id),
    deps: AgentDependencies = Depends(get_deps),
):
    """Exchange a JWT or API key for a short-lived WebSocket ticket.

    The ticket is single-use and expires in 30 seconds. Use it to
    connect to the WebSocket endpoint: /api/v1/chat/ws?ticket=<ticket>

    This avoids exposing long-lived credentials in the WebSocket URL.
    """
    service = WSTicketService(deps.ws_tickets_collection)
    ticket = await service.create_ticket(tenant_id)
    return WSTicketResponse(ticket=ticket)
