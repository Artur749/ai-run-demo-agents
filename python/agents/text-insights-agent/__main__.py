import logging

import click
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from agent import TextInsightsAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextInsightsExecutor(AgentExecutor):
    def __init__(self):
        self.agent = TextInsightsAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = self.agent.invoke(context.get_user_input())
        summary = (
            f'Status: {result.status}\n'
            f'Sentiment: {result.sentiment}\n'
            f"Key points: {'; '.join(result.key_points)}\n"
            f'Suggested next step: {result.suggested_next_step}'
        )
        await event_queue.enqueue_event(new_text_message(summary))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError('Cancellation is not supported.')


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10800)
def main(host, port):
    base_url = f'http://{host}:{port}'
    skill = AgentSkill(
        id='analyze_text_insights',
        name='Text Insights Tool',
        description='Summarizes sentiment, key points, and a suggested next step for a block of free text.',
        tags=['text analysis', 'sentiment'],
        examples=['Customer says the checkout page keeps freezing on mobile.'],
    )
    agent_card = AgentCard(
        name='Text Insights Agent',
        description='Turns free text (e.g. feedback or a support ticket) into a structured insight summary.',
        supported_interfaces=[
            AgentInterface(url=f'{base_url}/', protocol_binding='JSONRPC'),
        ],
        version='1.0.0',
        default_input_modes=TextInsightsAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=TextInsightsAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=TextInsightsExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url='/'),
    ]
    app = Starlette(routes=routes)
    logger.info(f'Starting text-insights-agent on {host}:{port}')
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()
