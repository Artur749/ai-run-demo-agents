import logging
import os
from typing import Literal

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {'azure', 'openai'}


def _create_chat_model():
    """Standalone factory — no dependency on common/. Duplicated from
    text-insights-agent/agent.py rather than imported: agents 3 and 4 share no
    code per spec."""
    name = os.getenv('CHAT_MODEL', 'gpt-4o')
    provider = os.getenv('CHAT_MODEL_PROVIDER', 'openai').strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f'Unsupported CHAT_MODEL_PROVIDER={provider!r}; '
            f'expected one of {sorted(_SUPPORTED_PROVIDERS)}.'
        )
    if provider == 'azure':
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        version = os.getenv('AZURE_OPENAI_API_VERSION')
        if not api_key or not endpoint or not version:
            raise ValueError(
                'AZURE_OPENAI_API_KEY/AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_VERSION '
                'required for azure provider.'
            )
        return AzureChatOpenAI(
            azure_endpoint=endpoint, azure_deployment=name, openai_api_version=version
        )
    return ChatOpenAI(model=name)


class GuideResponse(BaseModel):
    status: Literal['completed', 'error'] = 'completed'
    steps: list[str] = Field(
        default_factory=list,
        description="3-8 ordered, concrete steps when status is 'completed'; empty when 'error'.",
    )
    summary: str

    @model_validator(mode='after')
    def _enforce_steps_range(self) -> 'GuideResponse':
        # Only the success path promises 3-8 steps; the error path (empty/unusable
        # goal, or an LLM-call failure) legitimately has none to report.
        if self.status == 'completed' and not (3 <= len(self.steps) <= 8):
            raise ValueError(
                f'steps must contain 3-8 items when status is completed, got {len(self.steps)}'
            )
        return self


SYSTEM_INSTRUCTION = (
    "Decompose the user's goal into 3-8 ordered, concrete steps, then write a one-sentence "
    "summary of the resulting guide. status='error' only for an empty/unusable goal."
)


class HowToGuideAgent:
    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self.model = _create_chat_model().with_structured_output(GuideResponse)

    def invoke(self, goal: str) -> GuideResponse:
        if not goal or not goal.strip():
            return GuideResponse(
                status='error', steps=[], summary='Provide a non-empty goal to plan.'
            )
        try:
            return self.model.invoke([('system', SYSTEM_INSTRUCTION), ('user', goal)])
        except Exception:
            # Log the real cause server-side only — never relay raw exception text
            # (endpoint URLs, auth error fragments, etc.) to an external caller.
            logger.exception('Failed to generate how-to guide with the LLM')
            return GuideResponse(
                status='error',
                steps=[],
                summary='Unable to generate a guide right now; please try again later.',
            )
