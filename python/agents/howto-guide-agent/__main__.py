import logging

import click
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette

from a2a.helpers import (
    new_task_from_user_message,
    new_text_artifact_update_event,
    new_text_status_update_event,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from a2a.utils.errors import UnsupportedOperationError

from agent import HowToGuideAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HowToGuideExecutor(AgentExecutor):
    def __init__(self):
        self.agent = HowToGuideAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        result = self.agent.invoke(context.get_user_input())
        if result.status == 'error':
            await event_queue.enqueue_event(new_text_status_update_event(
                task.id, task.context_id, TaskState.TASK_STATE_FAILED, result.summary,
            ))
            return

        for i, step in enumerate(result.steps, start=1):
            await event_queue.enqueue_event(new_text_artifact_update_event(
                task.id, task.context_id, name=f'step-{i}', text=f'{i}. {step}',
                artifact_id=f'step-{i}', append=False, last_chunk=True,
            ))

        numbered = '\n'.join(f'{i}. {s}' for i, s in enumerate(result.steps, start=1))
        await event_queue.enqueue_event(new_text_artifact_update_event(
            task.id, task.context_id, name='guide', text=f'{result.summary}\n\n{numbered}',
            artifact_id='guide', append=False, last_chunk=True,
        ))
        await event_queue.enqueue_event(new_text_status_update_event(
            task.id, task.context_id, TaskState.TASK_STATE_COMPLETED, 'Guide complete.',
        ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Raising the SDK's own A2AError subclass lets the JSON-RPC dispatcher map this
        # to its documented "unsupported operation" error code instead of a generic
        # Internal Server Error.
        raise UnsupportedOperationError(message='Cancellation is not supported by this agent.')


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10900)
def main(host, port):
    base_url = f'http://{host}:{port}'
    skill = AgentSkill(
        id='generate_howto_guide',
        name='How-To Guide Generator',
        description='Decomposes a goal into an ordered, concrete step-by-step guide, streamed incrementally.',
        tags=['planning', 'guide generation'],
        examples=['Set up a home Wi-Fi router.'],
    )
    agent_card = AgentCard(
        name='How-To Guide Agent',
        description='Turns a free-text goal into an ordered how-to guide, streaming one event per step.',
        supported_interfaces=[
            AgentInterface(url=f'{base_url}/', protocol_binding='JSONRPC'),
        ],
        version='1.0.0',
        default_input_modes=HowToGuideAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=HowToGuideAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=HowToGuideExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url='/'),
    ]
    app = Starlette(routes=routes)
    logger.info(f'Starting howto-guide-agent on {host}:{port}')
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()
