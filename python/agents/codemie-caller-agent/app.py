import logging
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.utils.errors import UnsupportedOperationError

from agent import CodeMieCallerAgent

logger = logging.getLogger(__name__)

_CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class CodeMieCallerExecutor(AgentExecutor):
    def __init__(self, agent: CodeMieCallerAgent) -> None:
        self._agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self._agent.call(context.get_user_input())
        text = result.response if result.ok else (result.error or "Unknown error")
        await event_queue.enqueue_event(new_text_message(text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError(message="Cancellation is not supported.")


async def demo_chat(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"},
                            status_code=400, headers=_CORS_HEADERS)
    message: str = body.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return JSONResponse({"ok": False, "error": "message field is required and must be non-empty"},
                            status_code=400, headers=_CORS_HEADERS)

    agent: CodeMieCallerAgent = request.app.state.agent
    logger.info("demo/chat: calling CodeMie via codemie-caller-agent")
    result = await agent.call(message.strip())

    trace_list = [
        {
            "step": s.step,
            "label": s.label,
            "direction": s.direction,
            "protocol": s.protocol,
            "payload": s.payload,
            **({"endpoint": s.endpoint} if s.endpoint is not None else {}),
            **({"latency_ms": s.latency_ms} if s.latency_ms is not None else {}),
        }
        for s in result.trace
    ]
    payload: dict[str, Any] = {"ok": result.ok, "response": result.response, "trace": trace_list}
    if not result.ok:
        payload["error"] = result.error
    return JSONResponse(payload, headers=_CORS_HEADERS)


async def demo_chat_preflight(request: Request) -> JSONResponse:
    return JSONResponse({}, headers=_CORS_HEADERS)


def create_app(
    agent: CodeMieCallerAgent,
    host: str = "localhost",
    port: int = 11000,
) -> Starlette:
    base_url = f"http://{host}:{port}"
    skill = AgentSkill(
        id="forward_to_codemie",
        name="Forward to CodeMie",
        description=(
            "Forwards the user message to a configured CodeMie assistant via A2A v1.0 "
            "and returns the response with a full wire trace."
        ),
        tags=["proxy", "codemie", "demo"],
        examples=[
            'Customer says: "The app keeps crashing after the last update."',
            "Set up a home Wi-Fi router.",
        ],
    )
    agent_card = AgentCard(
        name="CodeMie Caller Agent",
        description=(
            "Demo agent that calls a CodeMie assistant via A2A v1.0 "
            "and exposes the full wire trace for demonstration purposes."
        ),
        supported_interfaces=[
            AgentInterface(url=f"{base_url}/", protocol_binding="JSONRPC"),
        ],
        version="1.0.0",
        default_input_modes=CodeMieCallerAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=CodeMieCallerAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=CodeMieCallerExecutor(agent),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        Route("/demo/chat", demo_chat, methods=["POST"]),
        Route("/demo/chat", demo_chat_preflight, methods=["OPTIONS"]),
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ]
    app = Starlette(routes=routes)
    app.state.agent = agent
    return app
