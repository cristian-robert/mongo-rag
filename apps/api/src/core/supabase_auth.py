"""Supabase JWT verification.

Verifies Supabase-issued user JWTs against the project's JWKS endpoint, with
an optional fallback to the legacy HS256 shared secret. Issuer (`iss`) and
audience (`aud`) are pinned by configuration — they are never trusted from
the token's own header.

Verification rules:
    * `alg` must come from a strict allow-list (no `none`, no algorithm
      confusion via header tampering).
    * Asymmetric tokens are verified against the JWKS key whose `kid`
      matches the token header. JWKS is fetched once and cached in-process
      for `settings.supabase_jwks_cache_seconds` seconds.
    * `iss`, `aud`, and `exp` are required and validated against settings.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

from src.core.settings import Settings

logger = logging.getLogger(__name__)

# Algorithms accepted for Supabase JWTs. `none` is intentionally absent — it
# would let an attacker forge a token by stripping the signature.
_ASYMMETRIC_ALGS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")
_SYMMETRIC_ALGS = ("HS256",)


@dataclass
class SupabaseClaims:
    """The minimal set of claims we extract from a verified Supabase JWT."""

    sub: str
    email: Optional[str]
    tenant_id: Optional[str]
    raw: dict[str, Any]


class _JWKSCache:
    """In-process JWKS cache with TTL and concurrency protection.

    A single shared lock prevents multiple concurrent requests from
    stampeding the JWKS endpoint after expiry.
    """

    def __init__(self) -> None:
        self._jwks: Optional[dict[str, Any]] = None
        self._fetched_at: float = 0.0
        self._url: Optional[str] = None
        self._lock = asyncio.Lock()

    async def get(self, url: str, ttl_seconds: int) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._jwks is not None
            and self._url == url
            and now - self._fetched_at < ttl_seconds
        ):
            return self._jwks

        async with self._lock:
            now = time.monotonic()
            if (
                self._jwks is not None
                and self._url == url
                and now - self._fetched_at < ttl_seconds
            ):
                return self._jwks

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                jwks = resp.json()
            if not isinstance(jwks, dict) or "keys" not in jwks:
                raise ValueError("Invalid JWKS document: missing 'keys'")
            self._jwks = jwks
            self._url = url
            self._fetched_at = time.monotonic()
            return jwks

    def invalidate(self) -> None:
        self._jwks = None
        self._fetched_at = 0.0
        self._url = None


_jwks_cache = _JWKSCache()


def reset_jwks_cache() -> None:
    """Test hook — reset the module-level JWKS cache."""
    _jwks_cache.invalidate()


def _looks_like_supabase_token(token: str, settings: Settings) -> bool:
    """Cheap pre-check before full verification.

    Decodes the unverified payload to peek at `iss`. If it matches the
    configured Supabase issuer, this is a Supabase token. Used only to route
    between the legacy NextAuth path and the Supabase path; the real
    verification happens in `verify_supabase_jwt`.
    """
    if not settings.supabase_issuer:
        return False
    try:
        unverified = jwt.get_unverified_claims(token)
    except JWTError:
        return False
    iss = unverified.get("iss")
    return isinstance(iss, str) and iss == settings.supabase_issuer


async def verify_supabase_jwt(token: str, settings: Settings) -> SupabaseClaims:
    """Verify a Supabase JWT and extract the claims we care about.

    Args:
        token: The raw JWT string from the Authorization header.
        settings: Application settings (must have Supabase configured).

    Returns:
        SupabaseClaims with `sub`, optional `email`, optional `tenant_id`.

    Raises:
        ValueError: On any verification failure (invalid signature, wrong
            issuer/audience, expired, missing claims, JWKS fetch failure).
            Messages are intentionally generic — never echo crypto detail
            back to the caller.
    """
    if not settings.supabase_issuer:
        raise ValueError("Supabase auth is not configured")

    # Read header WITHOUT trusting it for verification — we only use `alg`
    # and `kid` to pick the verification path/key, and we constrain `alg`
    # against a strict allow-list below.
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise ValueError("Malformed token") from None

    alg = header.get("alg")
    if not isinstance(alg, str):
        raise ValueError("Token header missing alg")

    decode_kwargs: dict[str, Any] = {
        "audience": settings.supabase_jwt_audience,
        "issuer": settings.supabase_issuer,
        "options": {
            "verify_signature": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
            "require_exp": True,
        },
    }

    if alg in _SYMMETRIC_ALGS:
        if not settings.supabase_jwt_secret:
            # Token claims to be HS256 but no shared secret configured →
            # likely an alg-confusion attempt against an asymmetric setup.
            raise ValueError("Symmetric algorithm not enabled for this project")
        key: Any = settings.supabase_jwt_secret
        algorithms = list(_SYMMETRIC_ALGS)
    elif alg in _ASYMMETRIC_ALGS:
        if not settings.supabase_jwks_url:
            raise ValueError("JWKS not available for this project")
        kid = header.get("kid")
        if not kid:
            raise ValueError("Token header missing kid")

        jwks = await _jwks_cache.get(
            settings.supabase_jwks_url, settings.supabase_jwks_cache_seconds
        )
        key = _select_jwk(jwks, kid)
        if key is None:
            # Possible key rotation — invalidate and retry once.
            _jwks_cache.invalidate()
            jwks = await _jwks_cache.get(
                settings.supabase_jwks_url, settings.supabase_jwks_cache_seconds
            )
            key = _select_jwk(jwks, kid)
        if key is None:
            raise ValueError("Unknown signing key")

        # Restrict algorithm verification to the JWK's declared alg if present;
        # otherwise allow the full asymmetric set. Either way, `none` is impossible.
        jwk_alg = key.get("alg") if isinstance(key, dict) else None
        if isinstance(jwk_alg, str) and jwk_alg in _ASYMMETRIC_ALGS:
            algorithms = [jwk_alg]
        else:
            algorithms = list(_ASYMMETRIC_ALGS)
    else:
        raise ValueError("Unsupported token algorithm")

    try:
        payload = jwt.decode(token, key, algorithms=algorithms, **decode_kwargs)
    except JWTError:
        # Do not surface crypto errors. Log at debug for ops.
        logger.debug("Supabase JWT verification failed", exc_info=True)
        raise ValueError("Invalid or expired token") from None

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise ValueError("Token missing sub claim")

    email = payload.get("email") if isinstance(payload.get("email"), str) else None
    tenant_id = _extract_tenant_id(payload)

    return SupabaseClaims(sub=sub, email=email, tenant_id=tenant_id, raw=payload)


def _select_jwk(jwks: dict[str, Any], kid: str) -> Optional[dict[str, Any]]:
    """Find the JWK whose `kid` matches the token header."""
    for entry in jwks.get("keys", []):
        if isinstance(entry, dict) and entry.get("kid") == kid:
            return entry
    return None


def _extract_tenant_id(payload: dict[str, Any]) -> Optional[str]:
    """Pull `tenant_id` from the standard Supabase metadata locations.

    Looks in this order:
        1. top-level `tenant_id`
        2. `app_metadata.tenant_id` (server-controlled — preferred)
        3. `user_metadata.tenant_id` (user-editable — accepted as a fallback
           but should not be the source of truth in production)
    """
    direct = payload.get("tenant_id")
    if isinstance(direct, str) and direct:
        return direct

    for bucket in ("app_metadata", "user_metadata"):
        meta = payload.get(bucket)
        if isinstance(meta, dict):
            tid = meta.get("tenant_id")
            if isinstance(tid, str) and tid:
                return tid

    return None
