"""Stripe webhook router.

POST /api/v1/stripe/webhook — public endpoint; auth comes from Stripe's
HMAC signature, not from JWT/API key. Body is the raw request bytes (must
NOT be parsed before signature verification — Stripe signs the exact bytes).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.postgres import PostgresUnavailableError, get_pool
from src.services.stripe_webhook import (
    WebhookSignatureError,
    construct_event,
    process_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stripe", tags=["billing", "webhooks"])


# Cap the request body size for webhooks at 1 MiB. Stripe events are
# typically <50 KiB; this defends against amplification on the public route.
_MAX_WEBHOOK_BYTES = 1 * 1024 * 1024


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    deps: AgentDependencies = Depends(get_deps),
) -> dict[str, str]:
    """Verify the signature, dedupe by event.id, dispatch to handlers."""
    if deps.settings is None:
        raise HTTPException(status_code=503, detail="settings not loaded")

    secret = deps.settings.stripe_webhook_secret
    if not secret:
        # Fail closed — never accept unverified webhooks.
        logger.error("stripe_webhook_secret_unconfigured")
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook secret not configured",
        )

    if not stripe_signature:
        # Don't reveal whether secret is set — generic 400.
        raise HTTPException(status_code=400, detail="missing signature header")

    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="empty body")
    if len(payload) > _MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    try:
        event = construct_event(
            payload=payload,
            signature=stripe_signature,
            secret=secret,
            tolerance=deps.settings.stripe_webhook_tolerance_seconds,
        )
    except WebhookSignatureError as exc:
        # Log without echoing the payload — payload bytes can contain PII.
        logger.warning(
            "stripe_webhook_bad_signature",
            extra={"reason": str(exc), "len": len(payload)},
        )
        raise HTTPException(status_code=400, detail="invalid signature")

    # Verified. Persist + dispatch.
    try:
        pool = await get_pool(deps.settings)
    except PostgresUnavailableError as exc:
        logger.error("stripe_webhook_pg_unavailable", extra={"reason": str(exc)})
        # 503 → Stripe retries with backoff. Don't 500 here — Stripe treats
        # 5xx the same way but 503 documents intent.
        raise HTTPException(status_code=503, detail="postgres unavailable")

    try:
        processed = await process_event(pool, event, deps.settings)
    except Exception:
        # Bubble up as 500 so Stripe retries. Never log raw payloads.
        logger.exception(
            "stripe_webhook_handler_failed",
            extra={"event_id": event.id, "type": event.type},
        )
        raise HTTPException(status_code=500, detail="handler failure")

    # 200 ack — Stripe stops retrying once it sees 2xx.
    return {"received": "ok", "duplicate": "false" if processed else "true"}
