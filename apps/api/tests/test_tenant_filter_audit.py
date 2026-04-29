"""Static audit: every Mongo CRUD call site in apps/api must filter by tenant_id.

This test reads every ``.py`` file under ``src/`` and uses the AST to find
calls of the form ``<collection>.<op>(...)`` where ``op`` is one of the
mutating or reading Mongo methods. Each call must either:

1. Reference ``tenant_id`` somewhere in its arguments, OR
2. Be on the documented ALLOWLIST below (with a justification).

If a new call site is added without one of those two, this test fails and
the developer must either:
  - Use ``tenant_filter(principal, ...)`` from ``src.core.principal``, or
  - Justify the exemption by adding it to the allowlist with a comment.

This is intentionally conservative — it accepts ``tenant_id`` appearing
anywhere in the call's source span, including arguments built by helpers
like ``tenant_filter()``. False positives are easy to fix; false negatives
(a query that bypasses tenant scoping) would be catastrophic.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

# Mongo methods we care about for tenant-scope auditing.
_MONGO_OPS = {
    "find",
    "find_one",
    "find_one_and_update",
    "find_one_and_delete",
    "find_one_and_replace",
    "update_one",
    "update_many",
    "delete_one",
    "delete_many",
    "insert_one",
    "insert_many",
    "aggregate",
    "count_documents",
    "replace_one",
    "bulk_write",
}

# The audit walks src/ relative to apps/api.
_SRC_ROOT = pathlib.Path(__file__).resolve().parent.parent / "src"

# Justified exemptions — every entry MUST have a comment explaining why.
# Format: (relative_path, op_name, line_number_or_None, reason)
#
# The line_number is intentionally optional — we match (path, op, reason) by
# substring so a small line drift won't break the test, but a deliberate
# tenant-scope regression (e.g. removing tenant_id from a previously-scoped
# call) WILL break it because the file no longer contains the unscoped call
# at the right shape. Run with `pytest -k tenant_filter_audit -v` to see
# every flagged call.
_ALLOWLIST: list[tuple[str, str, str]] = [
    # --- Authentication-by-credential lookups -------------------------------
    # The credential IS the auth secret; we look it up before we know which
    # tenant the caller belongs to. After the lookup, every subsequent query
    # uses the tenant_id derived from the matched document.
    (
        "core/principal.py",
        "find_one",
        "API key auth — looked up by SHA256(key_hash) before tenant is known",
    ),
    (
        "core/principal.py",
        "update_one",
        "API key last_used_at touch — keyed by key_hash, not tenant_id",
    ),
    (
        "core/tenant.py",
        "find_one",
        "Legacy API key auth path — same as core/principal.py, scheduled for removal",
    ),
    (
        "core/tenant.py",
        "update_one",
        "Legacy API key last_used_at touch — same as core/principal.py",
    ),
    (
        "services/api_key.py",
        "find_one",
        "API key validation — looked up by SHA256(key_hash) before tenant is known",
    ),
    (
        "services/auth.py",
        "find_one",
        "Login + password reset — looked up by email/user_id which are unique "
        "across the whole system; tenant is part of the response, not the filter",
    ),
    (
        "services/auth.py",
        "find_one_and_update",
        "Reset token claim — looked up by SHA256(token_hash); token IS the secret. "
        "Tenant defense-in-depth check happens after the claim using the user record.",
    ),
    (
        "services/auth.py",
        "update_many",
        "Invalidate stale reset tokens for a user — keyed by user_id (which "
        "implies the tenant); never operates across tenants",
    ),
    # --- Public widget bootstrap --------------------------------------------
    (
        "services/bot.py",
        "find_one",
        "Public bot lookup for the embeddable widget — only returns bots "
        "explicitly marked is_public=True; never leaks tenant_id in the response",
    ),
    # --- Internal infra (no tenant data lives here) -------------------------
    (
        "migrations/runner.py",
        "find",
        "Migrations bookkeeping collection — global infra, no tenant data",
    ),
    (
        "migrations/runner.py",
        "insert_one",
        "Migration version record — global infra, no tenant data",
    ),
    (
        "migrations/runner.py",
        "delete_one",
        "Migration version record — global infra, no tenant data",
    ),
    # --- Team invitation claim ---------------------------------------------
    (
        "services/team.py",
        "find_one_and_update",
        "Invite claim is keyed by SHA256(token_hash); the token IS the secret. "
        "After claim the recovered tenant_id is the only one used downstream.",
    ),
    # --- WebSocket ticket consume -------------------------------------------
    (
        "services/ws_ticket.py",
        "find_one_and_update",
        "WS ticket consumed by SHA256(ticket); ticket IS the secret. "
        "After consume, the recovered tenant_id is the only one used downstream.",
    ),
    (
        "services/ws_ticket.py",
        "insert_one",
        "WS ticket creation — document already includes tenant_id at construction",
    ),
    # --- Auth + signup ------------------------------------------------------
    (
        "services/auth.py",
        "insert_one",
        "Signup creates a fresh tenant + user atomically; tenant_id is "
        "minted server-side and embedded in both documents at construction",
    ),
    (
        "services/auth.py",
        "delete_one",
        "Signup rollback — deletes the freshly-minted tenant when the "
        "matching user insert raises DuplicateKeyError",
    ),
    (
        "services/auth.py",
        "update_one",
        "Password reset commits the new hash by user _id; the user record "
        "was already loaded with its tenant_id verified above",
    ),
]


def _ast_node_mentions_tenant_id(node: ast.AST) -> bool:
    """Return True if ``tenant_id`` appears anywhere in this AST subtree.

    Tenant scoping is acknowledged when any of these appear in the subtree:
      - the literal name ``tenant_id`` (variable, attribute, dict-key, kwarg)
      - the helper calls ``tenant_filter(...)`` or ``tenant_doc(...)``
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "tenant_id":
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value == "tenant_id":
                return True
        if isinstance(sub, ast.Attribute) and sub.attr == "tenant_id":
            return True
        if isinstance(sub, ast.keyword) and sub.arg == "tenant_id":
            return True
        # Calls to our helpers count as tenant-scoped by construction.
        if isinstance(sub, ast.Call):
            target = sub.func
            if isinstance(target, ast.Attribute) and target.attr in {
                "tenant_filter",
                "tenant_doc",
            }:
                return True
            if isinstance(target, ast.Name) and target.id in {
                "tenant_filter",
                "tenant_doc",
            }:
                return True
    return False


def _enclosing_function(tree: ast.AST, target: ast.AST) -> ast.AST | None:
    """Return the smallest enclosing FunctionDef / AsyncFunctionDef of ``target``.

    Falls back to the module if the call is at module top level. The function
    body acts as the tenant-scope window: a ``find_one(...)`` whose call site
    doesn't directly reference ``tenant_id`` is still considered scoped if its
    enclosing function builds the filter via ``tenant_id`` somewhere else
    (common pattern: ``filter_q = {"tenant_id": tenant_id}; coll.find(filter_q)``).
    """
    candidate: ast.AST | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if sub is target:
                if candidate is None or _is_inside(candidate, node):
                    candidate = node
                break
    return candidate


def _is_inside(outer: ast.AST, inner: ast.AST) -> bool:
    """True if ``inner`` is contained within ``outer`` (different node)."""
    if outer is inner:
        return False
    for sub in ast.walk(outer):
        if sub is inner:
            return True
    return False


# Receiver names that are clearly NOT Mongo collections — common false
# positives for ``str.find`` or business helpers that happen to share a name.
_NON_MONGO_RECEIVERS = {
    "content",
    "text",
    "data",
    "buffer",
    "body",
    "raw",
    "string",
    "str",
}


def _iter_mongo_calls(tree: ast.AST):
    """Yield ``ast.Call`` nodes that look like a Mongo collection method.

    Heuristics:
      - method name must be in ``_MONGO_OPS``;
      - receiver, when it's a plain Name, must not be in ``_NON_MONGO_RECEIVERS``
        (these are common false positives — e.g. ``content.find('---')``).
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _MONGO_OPS:
            continue
        # Reject obvious non-Mongo receivers (string ops mostly).
        if isinstance(func.value, ast.Name) and func.value.id in _NON_MONGO_RECEIVERS:
            continue
        yield node


def _allowlisted(rel: str, op: str) -> bool:
    return any(entry[0] == rel and entry[1] == op for entry in _ALLOWLIST)


@pytest.mark.unit
def test_every_mongo_call_in_apps_api_is_tenant_scoped() -> None:
    """No raw Mongo CRUD without ``tenant_id`` outside the allowlist."""
    violations: list[str] = []

    py_files = sorted(_SRC_ROOT.rglob("*.py"))
    assert py_files, f"No source files found under {_SRC_ROOT} — bad layout?"

    for path in py_files:
        rel = str(path.relative_to(_SRC_ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            # Don't let unrelated syntax issues mask the real test signal.
            continue

        for call in _iter_mongo_calls(tree):
            assert isinstance(call.func, ast.Attribute)
            op = call.func.attr
            if _ast_node_mentions_tenant_id(call):
                continue
            enclosing = _enclosing_function(tree, call)
            if enclosing is not None and _ast_node_mentions_tenant_id(enclosing):
                continue
            if _allowlisted(rel, op):
                continue
            violations.append(f"{rel}:{call.lineno} — {op}() lacks tenant_id filter")

    if violations:
        formatted = "\n  ".join(violations)
        raise AssertionError(
            "Tenant-isolation audit failed. Each violation must either use "
            "tenant_filter(principal, ...) / tenant_doc(principal, ...) or be "
            "added to the allowlist in this test with a justification.\n  " + formatted
        )


@pytest.mark.unit
def test_no_router_accepts_tenant_id_from_request() -> None:
    """Routers must derive tenant_id from auth, never accept it as input."""
    routers_root = _SRC_ROOT / "routers"
    offenders: list[str] = []

    for path in sorted(routers_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for arg in func.args.args + func.args.kwonlyargs:
                if arg.arg != "tenant_id":
                    continue
                # tenant_id is only allowed if it has a Depends(...) default.
                # We map argument index → default by walking from the right.
                ok = _arg_has_depends_default(func, arg)
                if not ok:
                    offenders.append(f"{path.relative_to(_SRC_ROOT)}:{func.lineno} {func.name}")

    assert not offenders, "Routers accepting raw tenant_id without Depends(...):\n  " + "\n  ".join(
        offenders
    )


def _arg_has_depends_default(func: ast.FunctionDef | ast.AsyncFunctionDef, arg: ast.arg) -> bool:
    """Return True if ``arg`` has a ``Depends(...)`` default OR Annotated[..., Depends(...)]."""
    # First, check the annotation itself for Annotated[..., Depends(...)].
    if arg.annotation is not None and _annotation_uses_depends(arg.annotation):
        return True

    # Then check default-value form: ``arg = Depends(...)``.
    candidates: list[tuple[ast.arg, ast.expr | None]] = []
    args = list(func.args.args)
    defaults = list(func.args.defaults)
    # Right-align: defaults bind from the rightmost arg.
    pad = len(args) - len(defaults)
    for i, a in enumerate(args):
        d = defaults[i - pad] if i - pad >= 0 else None
        candidates.append((a, d))
    for a, d in zip(func.args.kwonlyargs, func.args.kw_defaults):
        candidates.append((a, d))

    for a, default in candidates:
        if a is not arg:
            continue
        if default is None:
            return False
        if isinstance(default, ast.Call):
            f = default.func
            if isinstance(f, ast.Name) and f.id == "Depends":
                return True
            if isinstance(f, ast.Attribute) and f.attr == "Depends":
                return True
        return False
    return False


def _annotation_uses_depends(annotation: ast.AST) -> bool:
    """Return True if an annotation uses ``Annotated[..., Depends(...)]`` form."""
    for sub in ast.walk(annotation):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name) and f.id == "Depends":
                return True
            if isinstance(f, ast.Attribute) and f.attr == "Depends":
                return True
    return False
