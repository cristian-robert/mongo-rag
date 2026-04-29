"""Tests for the Principal abstraction and tenant_filter helper."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.core.principal import Principal, tenant_doc, tenant_filter
from tests.conftest import MOCK_TENANT_B_ID, MOCK_TENANT_ID


@pytest.mark.unit
def test_tenant_filter_pins_tenant_id_to_principal() -> None:
    """tenant_filter ALWAYS sets tenant_id from the principal, never the caller."""
    principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="jwt", user_id="u")

    filt = tenant_filter(principal, status="ready")

    assert filt == {"tenant_id": MOCK_TENANT_ID, "status": "ready"}


@pytest.mark.unit
def test_tenant_filter_overrides_forged_tenant_id_in_extras() -> None:
    """A forged tenant_id passed in extras is silently overridden by the principal."""
    principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="jwt")

    filt = tenant_filter(principal, tenant_id=MOCK_TENANT_B_ID, status="ready")

    assert filt["tenant_id"] == MOCK_TENANT_ID
    assert MOCK_TENANT_B_ID not in filt.values()


@pytest.mark.unit
def test_tenant_filter_rejects_empty_principal_tenant() -> None:
    """tenant_filter raises 401 if the principal somehow has no tenant_id."""
    principal = Principal(tenant_id="", auth_method="jwt")

    with pytest.raises(HTTPException) as exc:
        tenant_filter(principal)

    assert exc.value.status_code == 401


@pytest.mark.unit
def test_tenant_doc_pins_tenant_id_to_principal() -> None:
    """tenant_doc locks tenant_id on inserts even if caller provides one."""
    principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="api_key")

    doc = tenant_doc(principal, tenant_id=MOCK_TENANT_B_ID, name="Acme")

    assert doc["tenant_id"] == MOCK_TENANT_ID
    assert doc["name"] == "Acme"


@pytest.mark.unit
def test_principal_require_jwt_blocks_api_keys() -> None:
    """API-key principals cannot reach JWT-only endpoints."""
    principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="api_key")

    with pytest.raises(HTTPException) as exc:
        principal.require_jwt()

    assert exc.value.status_code == 403


@pytest.mark.unit
def test_principal_require_jwt_allows_jwt() -> None:
    principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="jwt")

    assert principal.require_jwt() is principal


@pytest.mark.unit
def test_principal_require_permission_blocks_missing_api_scope() -> None:
    """API keys lacking a scope are rejected; JWT principals are exempt (RBAC owns that)."""
    api_principal = Principal(
        tenant_id=MOCK_TENANT_ID,
        auth_method="api_key",
        permissions=("chat",),
    )

    with pytest.raises(HTTPException) as exc:
        api_principal.require_permission("search")
    assert exc.value.status_code == 403

    api_principal.require_permission("chat")  # OK

    jwt_principal = Principal(tenant_id=MOCK_TENANT_ID, auth_method="jwt")
    jwt_principal.require_permission("anything-goes")


@pytest.mark.unit
async def test_get_principal_jwt_path_uses_token_tenant() -> None:
    from jose import jwt

    from src.core.principal import get_principal

    request = MagicMock()
    request.state = MagicMock()
    deps = MagicMock()

    token = jwt.encode(
        {"sub": "user-1", "tenant_id": MOCK_TENANT_ID, "role": "owner"},
        "test-secret-for-unit-tests-minimum-32chars",
        algorithm="HS256",
    )

    principal = await get_principal(request, authorization=f"Bearer {token}", deps=deps)

    assert principal.tenant_id == MOCK_TENANT_ID
    assert principal.auth_method == "jwt"
    assert principal.user_id == "user-1"
    assert principal.role == "owner"


@pytest.mark.unit
async def test_get_principal_api_key_path_uses_keyhash_lookup() -> None:
    """API-key principals carry the tenant_id from the database, not the token."""
    from src.core.principal import get_principal

    request = MagicMock()
    request.state = MagicMock()

    deps = MagicMock()
    deps.api_keys_collection = MagicMock()
    deps.api_keys_collection.find_one = AsyncMock(
        return_value={
            "_id": "key-doc-1",
            "tenant_id": MOCK_TENANT_ID,
            "permissions": ["chat", "search"],
            "is_revoked": False,
        }
    )
    deps.api_keys_collection.update_one = AsyncMock()

    principal = await get_principal(
        request,
        authorization="Bearer mrag_does_not_matter_what_value",
        deps=deps,
    )

    assert principal.tenant_id == MOCK_TENANT_ID
    assert principal.auth_method == "api_key"
    assert "chat" in principal.permissions


@pytest.mark.unit
async def test_get_principal_rejects_missing_authorization() -> None:
    from src.core.principal import get_principal

    request = MagicMock()
    deps = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await get_principal(request, authorization=None, deps=deps)
    assert exc.value.status_code == 401


@pytest.mark.unit
async def test_get_principal_rejects_jwt_without_tenant_claim() -> None:
    from jose import jwt

    from src.core.principal import get_principal

    request = MagicMock()
    request.state = MagicMock()
    deps = MagicMock()

    token = jwt.encode(
        {"sub": "user-1"},  # No tenant_id claim
        "test-secret-for-unit-tests-minimum-32chars",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc:
        await get_principal(request, authorization=f"Bearer {token}", deps=deps)
    assert exc.value.status_code == 401


@pytest.mark.unit
async def test_get_principal_rejects_revoked_api_key() -> None:
    from src.core.principal import get_principal

    request = MagicMock()
    request.state = MagicMock()
    deps = MagicMock()
    deps.api_keys_collection = MagicMock()
    deps.api_keys_collection.find_one = AsyncMock(
        return_value={"tenant_id": MOCK_TENANT_ID, "is_revoked": True}
    )

    with pytest.raises(HTTPException) as exc:
        await get_principal(request, authorization="Bearer mrag_revoked", deps=deps)
    assert exc.value.status_code == 401
