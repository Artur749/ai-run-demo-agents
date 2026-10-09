import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class TraceStep:
    step: int
    label: str
    direction: str
    protocol: str
    payload: dict[str, Any]
    endpoint: str | None = None
    latency_ms: int | None = None


@dataclass
class CallResult:
    ok: bool
    response: str
    trace: list[TraceStep]
    error: str | None = None


class CodeMieCallerAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, cm_base_url: str, cm_assistant_id: str, cm_auth_token: str) -> None:
        self._endpoint = f"{cm_base_url.rstrip('/')}/v1/a2a/assistants/{cm_assistant_id}"
        self._auth_token = cm_auth_token

    async def call(self, message: str) -> CallResult:
        rpc_id = uuid.uuid4().hex
        message_id = uuid.uuid4().hex
        request_payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": message_id,
                    "role": "ROLE_USER",
                    "parts": [{"text": message}],
                }
            },
        }
        trace: list[TraceStep] = [
            TraceStep(
                step=1,
                label="UI → codemie-caller-agent",
                direction="outbound",
                protocol="HTTP POST /demo/chat",
                payload={"message": message},
            ),
            TraceStep(
                step=2,
                label="codemie-caller-agent → CodeMie (A2A SendMessage)",
                direction="outbound",
                protocol="A2A JSON-RPC 1.0",
                endpoint=self._endpoint,
                payload=request_payload,
            ),
        ]

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self._endpoint,
                    json=request_payload,
                    headers={
                        "A2A-Version": "1.0",
                        "Authorization": f"Bearer {self._auth_token}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                response_json: dict[str, Any] = resp.json()
        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            error_str = str(exc)
            trace.append(TraceStep(
                step=3,
                label="CodeMie → codemie-caller-agent",
                direction="inbound",
                protocol="A2A JSON-RPC 1.0",
                payload={"error": error_str},
                latency_ms=latency_ms,
            ))
            trace.append(TraceStep(
                step=4,
                label="codemie-caller-agent → UI",
                direction="inbound",
                protocol="HTTP response",
                payload={"ok": False, "error": error_str},
            ))
            return CallResult(ok=False, response="", trace=trace, error=error_str)

        latency_ms = int((time.monotonic() - t0) * 1000)
        trace.append(TraceStep(
            step=3,
            label="CodeMie → codemie-caller-agent",
            direction="inbound",
            protocol="A2A JSON-RPC 1.0",
            payload=response_json,
            latency_ms=latency_ms,
        ))

        if "error" in response_json:
            err = response_json["error"]
            error_msg = f"A2A error {err.get('code')}: {err.get('message', 'unknown')}"
            trace.append(TraceStep(
                step=4,
                label="codemie-caller-agent → UI",
                direction="inbound",
                protocol="HTTP response",
                payload={"ok": False, "error": error_msg},
            ))
            return CallResult(ok=False, response="", trace=trace, error=error_msg)

        response_text = _extract_text(response_json)
        failed_state = _failed_task_state(response_json)
        if failed_state:
            error_msg = f"CodeMie task {failed_state}: {response_text}"
            trace.append(TraceStep(
                step=4,
                label="codemie-caller-agent → UI",
                direction="inbound",
                protocol="HTTP response",
                payload={"ok": False, "error": error_msg},
            ))
            return CallResult(ok=False, response="", trace=trace, error=error_msg)

        trace.append(TraceStep(
            step=4,
            label="codemie-caller-agent → UI",
            direction="inbound",
            protocol="HTTP response",
            payload={"ok": True, "response": response_text},
        ))
        return CallResult(ok=True, response=response_text, trace=trace)


_FAILED_TASK_STATES = ("TASK_STATE_FAILED", "TASK_STATE_REJECTED", "TASK_STATE_CANCELED")


def _first_text(message: dict[str, Any]) -> str | None:
    parts = message.get("parts", [])
    return parts[0].get("text", "") if parts else None


def _failed_task_state(response_json: dict[str, Any]) -> str | None:
    state = response_json.get("result", {}).get("task", {}).get("status", {}).get("state")
    return state if state in _FAILED_TASK_STATES else None


def _extract_text(response_json: dict[str, Any]) -> str:
    """The answer text: a completed task keeps it in an artifact, a failed or input-required one in status.message."""
    result = response_json.get("result", {})
    task = result.get("task", {})
    artifacts = task.get("artifacts", [])
    if artifacts:
        text = _first_text(artifacts[0])
        if text is not None:
            return text
    for message in (task.get("status", {}).get("message", {}), result.get("message", {})):
        text = _first_text(message)
        if text is not None:
            return text
    return str(result)
