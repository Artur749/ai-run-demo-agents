import logging
import os

import click
import uvicorn
from dotenv import load_dotenv

from agent import CodeMieCallerAgent
from app import create_app

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_agent() -> CodeMieCallerAgent:
    cm_base_url = os.environ.get("CM_BASE_URL", "http://localhost:8080")
    cm_assistant_id = os.environ["CM_ASSISTANT_ID"]
    cm_auth_token = os.environ["CM_AUTH_TOKEN"]
    return CodeMieCallerAgent(cm_base_url, cm_assistant_id, cm_auth_token)


@click.command()
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=11000, show_default=True)
def main(host: str, port: int) -> None:
    agent = _build_agent()
    app = create_app(agent, host, port)
    logger.info("Starting codemie-caller-agent on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
