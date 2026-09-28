import sys
import traceback
from typing import Any
from uuid import uuid4

from common.client import A2AClient
from common.client.card_resolver import A2ACardResolver
from common.types import (
    SendTaskResponse,
    SendTaskStreamingResponse,
    GetTaskResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    Message,
    TextPart,
)

AGENT_URL = 'http://localhost:10700'


def create_send_task_payload(text: str) -> Message:
    """Helper function to create the payload for sending a task."""
    return Message(
        role='user',
        parts=[TextPart(text=text)],
    )

def print_json_response(response: Any, description: str) -> None:
    """Helper function to print the JSON representation of a response."""
    print(f'--- {description} ---')
    if hasattr(response, 'result'):
        print(f'{response.result.model_dump_json(exclude_none=True)}\n')
    else:
        print(f'{response.model_dump(mode="json", exclude_none=True)}\n')


def extract_text(task: Task) -> str:
    """Joins every TextPart.text found across artifacts and the status message."""
    chunks: list[str] = []
    for artifact in task.artifacts or []:
        for part in artifact.parts:
            if isinstance(part, TextPart):
                chunks.append(part.text)
    if task.status.message:
        for part in task.status.message.parts:
            if isinstance(part, TextPart):
                chunks.append(part.text)
    return ''.join(chunks).strip()


async def run_single_turn_test(client: A2AClient) -> None:
    """Runs a single-turn non-streaming test."""

    send_payload = create_send_task_payload(
        text="What is the most important thing to do to fix the planet?"
    )

    # Create task parameters as a dictionary
    task_params = {
        "id": uuid4().hex,
        "message": send_payload.model_dump(),
    }

    print('--- Single Turn Request ---')
    # Send Message
    send_response: SendTaskResponse = await client.send_task(task_params)
    print_json_response(send_response, 'Single Turn Request Response')

    assert isinstance(send_response.result, Task), (
        f'expected a Task result, got {type(send_response.result)}'
    )

    task_id: str = send_response.result.id
    print('---Query Task---')
    # query the task
    get_params = {"id": task_id}
    get_response: GetTaskResponse = await client.get_task(get_params)
    print_json_response(get_response, 'Query Task Response')

    task = get_response.result
    assert isinstance(task, Task), f'expected a Task result, got {type(task)}'
    assert task.status.state in (TaskState.COMPLETED, TaskState.INPUT_REQUIRED), (
        f'unexpected task state: {task.status.state}'
    )
    text = extract_text(task)
    assert text, 'expected a non-empty response text'

async def run_streaming_test(client: A2AClient) -> None:
    """Runs a streaming test."""

    send_payload = create_send_task_payload(
        text="What is the most important thing to do to fix the planet?"
    )

    # Create task parameters as a dictionary
    task_params = {
        "id": uuid4().hex,
        "message": send_payload.model_dump(),
    }

    print('--- Streaming Request ---')
    chunks: list[SendTaskStreamingResponse] = []
    stream_response = client.send_task_streaming(task_params)
    async for chunk in stream_response:
        print_json_response(chunk, 'Streaming Chunk')
        chunks.append(chunk)

    assert chunks, 'expected at least one streaming chunk'

    final_chunk = chunks[-1]
    result = final_chunk.result
    text = ''
    if isinstance(result, TaskArtifactUpdateEvent):
        text = ''.join(
            part.text
            for part in result.artifact.parts
            if isinstance(part, TextPart)
        ).strip()
    elif isinstance(result, TaskStatusUpdateEvent) and result.status.message:
        text = ''.join(
            part.text
            for part in result.status.message.parts
            if isinstance(part, TextPart)
        ).strip()
    assert text, 'expected non-empty text content in the final streaming chunk'


async def main() -> None:
    """Main function to run the tests."""
    print(f'Connecting to agent at {AGENT_URL}...')
    try:
        agent_card_resolver = A2ACardResolver(AGENT_URL)
        agent_card = agent_card_resolver.get_agent_card()
        client = A2AClient(agent_card)

        print(f'Connected to agent at {client.url}')

        await run_single_turn_test(client)
        await run_streaming_test(client)

    except Exception as e:
        traceback.print_exc()
        print(f'An error occurred: {e}')
        print('Ensure the agent server is running.')
        raise


if __name__ == '__main__':
    import asyncio

    try:
        asyncio.run(main())
    except (AssertionError, Exception) as exc:
        print(f'CHECK FAILED: {exc}')
        sys.exit(1)