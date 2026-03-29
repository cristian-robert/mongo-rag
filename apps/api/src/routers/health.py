"""Health check endpoint."""

import logging

from fastapi import APIRouter
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.core.dependencies import AgentDependencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Check API and MongoDB health.

    Returns 200 with status if healthy, 503 if MongoDB is unreachable.
    """
    deps = AgentDependencies()
    try:
        await deps.initialize()
        await deps.cleanup()
        return {"status": "ok", "mongodb": "connected"}
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "error", "mongodb": "disconnected", "detail": str(e)},
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})
