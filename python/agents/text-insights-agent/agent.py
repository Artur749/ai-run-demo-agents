import os
import re
from typing import Literal

from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

POSITIVE = {"great", "good", "excellent", "love", "happy", "satisfied", "thanks", "resolved"}
NEGATIVE = {"bad", "terrible", "hate", "angry", "frustrated", "broken", "disappointed", "issue"}


def _create_chat_model():
    """Standalone factory — no dependency on common/."""
    name = os.getenv('CHAT_MODEL', 'gpt-4o')
    provider = os.getenv('CHAT_MODEL_PROVIDER', 'openai')
    if provider == 'azure':
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        version = os.getenv('AZURE_OPENAI_API_VERSION')
        if not endpoint or not version:
            raise ValueError(
                'AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_VERSION required for azure provider.'
            )
        return AzureChatOpenAI(
            azure_endpoint=endpoint, azure_deployment=name, openai_api_version=version
        )
    return ChatOpenAI(model=name)


@tool
def analyze_text_stats(text: str) -> dict:
    """Word count, reading time (min), keyword-based sentiment for a text block."""
    words = text.split()
    if not words:
        return {'word_count': 0, 'reading_time_minutes': 0.0, 'sentiment_signal': 'neutral'}
    lowered = {re.sub(r'[^a-z]', '', w.lower()) for w in words}
    pos, neg = len(lowered & POSITIVE), len(lowered & NEGATIVE)
    signal = 'positive' if pos > neg else 'negative' if neg > pos else 'neutral'
    return {
        'word_count': len(words),
        'reading_time_minutes': round(len(words) / 200, 2),
        'sentiment_signal': signal,
    }


class InsightsResponse(BaseModel):
    status: Literal['completed', 'error'] = 'completed'
    sentiment: str
    key_points: list[str]
    suggested_next_step: str


SYSTEM_INSTRUCTION = (
    "Use 'analyze_text_stats' for objective stats, then produce a short structured summary: "
    "sentiment, 2-4 key_points, suggested_next_step. status='error' only for empty/unusable input."
)


class TextInsightsAgent:
    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self.graph = create_react_agent(
            _create_chat_model(),
            tools=[analyze_text_stats],
            prompt=SYSTEM_INSTRUCTION,
            response_format=InsightsResponse,
        )

    def invoke(self, text: str) -> InsightsResponse:
        if not text or not text.strip():
            return InsightsResponse(
                status='error',
                sentiment='unknown',
                key_points=[],
                suggested_next_step='Provide non-empty text to analyze.',
            )
        try:
            result = self.graph.invoke({'messages': [('user', text)]})
            return result['structured_response']
        except Exception as exc:
            return InsightsResponse(
                status='error',
                sentiment='unknown',
                key_points=[],
                suggested_next_step=f'Unable to analyze text: {exc}',
            )
