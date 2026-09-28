import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, create_client
from a2a.helpers import get_stream_response_text, new_text_message
from a2a.types import SendMessageRequest

AGENT_URL = 'http://localhost:10800'


async def check_agent_card(httpx_client: httpx.AsyncClient):
    card = await A2ACardResolver(httpx_client, AGENT_URL).get_agent_card()
    assert card.name, 'agent card missing name'
    assert card.skills, 'agent card missing skills'
    assert card.capabilities is not None, 'agent card missing capabilities'
    return card


async def send_text(client, text: str) -> str:
    request = SendMessageRequest(message=new_text_message(text))
    chunks = [chunk async for chunk in client.send_message(request)]
    assert chunks, 'expected at least one response chunk'
    return ''.join(get_stream_response_text(chunk) for chunk in chunks).strip()


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as httpx_client:
        card = await check_agent_card(httpx_client)
        client = await create_client(card)
        try:
            result = await send_text(
                client,
                'Customer says the checkout page keeps freezing on mobile, very frustrating.',
            )
            assert result, 'expected a non-empty result for real input'
            print(f'OK (real input): {result}')

            empty = await send_text(client, '   ')
            assert empty, 'agent did not handle empty input gracefully'
            assert 'error' in empty.lower(), (
                f'expected a graceful error-status result for empty input, got: {empty!r}'
            )
            print(f'OK (empty input handled): {empty}')
        finally:
            await client.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f'CHECK FAILED: {exc}')
        sys.exit(1)
    except Exception as exc:
        print(f'CHECK FAILED: {exc}')
        sys.exit(1)
