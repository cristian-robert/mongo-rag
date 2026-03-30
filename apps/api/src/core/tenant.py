"""Tenant extraction dependency for FastAPI."""

from typing import Optional

from fastapi import Header, HTTPException


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Extract and validate tenant_id from X-Tenant-ID header.

    This is a stub for Phase 3 auth. The real implementation will
    derive tenant_id from the authenticated session or API key.

    Args:
        x_tenant_id: Tenant ID from request header.

    Returns:
        Validated tenant_id string.

    Raises:
        HTTPException: 400 if header is missing or empty.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id.strip()
