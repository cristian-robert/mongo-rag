"""Chat endpoints: REST (JSON + SSE) and WebSocket."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.tenant import get_tenant_id, resolve_token
from src.models.api import ChatRequest, ChatResponse, WSMessage
from src.services.chat import ChatService, ConversationNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    deps: AgentDependencies = Depends(get_deps),
):
    """Handle a chat message.

    If Accept header includes text/event-stream, streams tokens via SSE.
    Otherwise returns the full response as JSON.
    """
    accept = request.headers.get("accept", "")
    service = ChatService(deps)

    # SSE streaming path
    if "text/event-stream" in accept:

        async def event_generator():
            async for event in service.handle_message_stream(
                message=body.message,
                tenant_id=tenant_id,
                conversation_id=body.conversation_id,
                search_type=body.search_type,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming JSON path
    try:
        result = await service.handle_message(
            message=body.message,
            tenant_id=tenant_id,
            conversation_id=body.conversation_id,
            search_type=body.search_type,
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        conversation_id=result["conversation_id"],
    )


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
):
    """WebSocket endpoint for real-time chat.

    Authenticate via query parameter: /api/v1/chat/ws?token=<jwt_or_api_key>
    """
    if not token or not token.strip():
        await websocket.close(code=4001, reason="token query parameter required")
        return

    # Resolve tenant from token before accepting connection
    deps: AgentDependencies = websocket.app.state.deps
    try:
        tenant_id = await resolve_token(token.strip(), deps)
    except HTTPException:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    service = ChatService(deps)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                msg = WSMessage(**data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            except (ValueError, TypeError) as e:
                logger.warning("WebSocket invalid message: %s", str(e))
                await websocket.send_json({"type": "error", "message": "Invalid message format"})
                continue

            if msg.type == "cancel":
                await websocket.send_json({"type": "cancelled"})
                continue

            if msg.type == "message" and msg.content:
                try:
                    async for event in service.handle_message_stream(
                        message=msg.content,
                        tenant_id=tenant_id,
                        conversation_id=msg.conversation_id,
                    ):
                        await websocket.send_json(event)
                except Exception as e:
                    logger.exception("WebSocket chat error: %s", str(e))
                    await websocket.send_json(
                        {"type": "error", "message": "An internal error occurred"}
                    )
            else:
                await websocket.send_json(
                    {"type": "error", "message": "Expected type 'message' with content"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: tenant=%s", tenant_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", str(e))
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
