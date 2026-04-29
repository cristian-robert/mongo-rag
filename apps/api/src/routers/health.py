"""Health and readiness endpoints."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.core.dependencies import AgentDependencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Liveness probe — does the process accept traffic?

    Pings MongoDB so a wedged connection pool surfaces here. Returns 503
    when the database is unreachable.
    """
    deps = AgentDependencies()
    try:
        await deps.initialize()
        await deps.cleanup()
        return {"status": "ok", "mongodb": "connected"}
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error("health_check_mongodb_failed", extra={"error": str(e)})
        return JSONResponse(
            status_code=503,
            content={"status": "error", "mongodb": "disconnected", "detail": str(e)},
        )
    except Exception as e:
        logger.error("health_check_failed", extra={"error": str(e)})
        return JSONResponse(status_code=503, content={"status": "error", "detail": "unhealthy"})


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness probe — is every downstream dependency reachable?

    Checks MongoDB ping AND verifies the embedding client is configured.
    Returns 503 with a per-component breakdown when anything fails.
    """
    components: dict[str, str] = {}
    deps = AgentDependencies()

    try:
        await deps.initialize()
        components["mongodb"] = "ok"
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error("ready_mongodb_failed", extra={"error": str(e)})
        components["mongodb"] = "unreachable"

    if deps.openai_client is not None and deps.settings is not None:
        components["embedding"] = "configured"
    else:
        components["embedding"] = "unconfigured"

    await deps.cleanup()

    all_ok = all(v in ("ok", "configured") for v in components.values())
    if all_ok:
        return {"status": "ready", "components": components}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "components": components},
    )
