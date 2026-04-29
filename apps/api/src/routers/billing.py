"""Billing endpoints: pricing catalog and Stripe Checkout session creation.

Webhook handling is intentionally out of scope here — see issue #43.
"""

import ipaddress
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException

from src.core.authz import Principal, require_role
from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.models.billing import (
    DISPLAY_PRICES_CENTS,
    MODEL_CATALOG,
    NON_CHECKOUT_PLANS,
    PLAN_LIMITS,
    CheckoutRequest,
    CheckoutResponse,
    LimitsInfo,
    ModelInfo,
    ModelTier,
    ModelTierInfo,
    PlanInfo,
    PlansResponse,
)
from src.models.tenant import PlanTier
from src.models.user import UserRole
from src.services.billing import BillingError, BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _get_billing_service(deps: AgentDependencies = Depends(get_deps)) -> BillingService:
    """Construct a BillingService with the configured Stripe key."""
    if deps.settings is None:
        raise HTTPException(status_code=503, detail="Application settings not loaded")
    try:
        return BillingService(
            settings=deps.settings,
            subscriptions_collection=deps.subscriptions_collection,
            tenants_collection=deps.tenants_collection,
            users_collection=deps.users_collection,
        )
    except BillingError as exc:
        # Stripe not configured — surface as 503 so callers can degrade.
        raise HTTPException(status_code=503, detail=str(exc))


def _is_private_host(host: str) -> bool:
    """Return True for hostnames that resolve to private/loopback ranges.

    We block IP-literal hosts in private, loopback, link-local, and
    multicast ranges to prevent SSRF-style abuse via the redirect URL.
    """
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _validate_redirect_url(url: str, field: str) -> None:
    """Reject obviously dangerous URLs before forwarding to Stripe.

    We do not allowlist hosts here (success/cancel URLs are tenant-specific
    and cannot be enumerated up-front). We do enforce:
      - scheme is http or https
      - a host is present
      - no embedded credentials (user@host)
      - http is only allowed for localhost (dev)
      - IP-literal hosts in private ranges are rejected to harden against
        SSRF probes injected into the redirect chain
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} is not a valid URL")
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail=f"{field} must use http or https",
        )
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail=f"{field} is missing a host")
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail=f"{field} must not include user credentials",
        )
    host = parsed.hostname.lower()
    if parsed.scheme == "http":
        if host != "localhost" and not host.startswith("127."):
            raise HTTPException(
                status_code=400,
                detail=f"{field} must use https outside of localhost",
            )
    elif _is_private_host(host):
        raise HTTPException(
            status_code=400,
            detail=f"{field} must not point to a private network address",
        )


@router.get("/plans", response_model=PlansResponse)
async def list_plans() -> PlansResponse:
    """Return the public pricing catalog.

    Used by the public pricing page and the dashboard upgrade modal. Returns
    plans (with quotas), model tiers (with prices and model lists). No auth
    required — pricing is public information.
    """
    plans = [
        PlanInfo(
            plan=plan,
            limits=LimitsInfo(**PLAN_LIMITS[plan]),
        )
        for plan in PlanTier
        if plan in PLAN_LIMITS
    ]

    model_tiers: list[ModelTierInfo] = []
    for tier, models in MODEL_CATALOG.items():
        pro_price = DISPLAY_PRICES_CENTS.get((PlanTier.PRO, tier))
        ent_price = DISPLAY_PRICES_CENTS.get((PlanTier.ENTERPRISE, tier))
        model_tiers.append(
            ModelTierInfo(
                tier=tier,
                pro_price_cents=pro_price,
                enterprise_price_cents=ent_price,
                models=[
                    ModelInfo(id=mid, name=name, provider=provider)
                    for (mid, name, provider) in models
                ],
            )
        )

    return PlansResponse(plans=plans, model_tiers=model_tiers)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    principal: Principal = Depends(require_role(UserRole.OWNER)),
    service: BillingService = Depends(_get_billing_service),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for an upgrade.

    Owner-only — billing is a tenant-financial concern.
    """
    tenant_id = principal.tenant_id
    if body.plan in NON_CHECKOUT_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{body.plan.value}' cannot be purchased via Checkout",
        )

    # Validate model tier exists.
    if body.model_tier not in {tier for tier in ModelTier}:
        raise HTTPException(status_code=400, detail="Unknown model tier")

    _validate_redirect_url(body.success_url, "success_url")
    _validate_redirect_url(body.cancel_url, "cancel_url")

    try:
        url, session_id = await service.create_checkout_session(
            tenant_id=tenant_id,
            plan=body.plan,
            model_tier=body.model_tier,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except BillingError as exc:
        msg = str(exc)
        # Missing price config is a server config error, not a client error.
        if "No Stripe price configured" in msg:
            logger.error("stripe_price_unconfigured", extra={"detail": msg})
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    return CheckoutResponse(checkout_url=url, session_id=session_id)
