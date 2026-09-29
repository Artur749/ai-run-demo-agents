import asyncio
import contextlib
import sys

import httpx

from a2a.client import A2ACardResolver, create_client
from a2a.helpers import get_stream_response_text, new_text_message
from a2a.types import Role, SendMessageRequest

AGENT_URL = 'http://localhost:10900'


async def check_agent_card(httpx_client: httpx.AsyncClient):
    card = await A2ACardResolver(httpx_client, AGENT_URL).get_agent_card()
    assert card.name, 'agent card missing name'
    assert card.skills, 'agent card missing skills'
    assert card.capabilities is not None, 'agent card missing capabilities'
    assert card.capabilities.streaming, 'agent card must advertise streaming capability'
    return card


async def send_goal(client, goal: str) -> list:
    # new_text_message defaults to role=ROLE_AGENT (it's normally used server-side
    # to build outgoing responses); a client-sent message must be ROLE_USER, since
    # the server's new_task_from_user_message() rejects anything else.
    request = SendMessageRequest(message=new_text_message(goal, role=Role.ROLE_USER))
    chunks = [chunk async for chunk in client.send_message(request)]
    assert chunks, 'expected at least one response chunk'
    return chunks


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as httpx_client:
        card = await check_agent_card(httpx_client)
        client = await create_client(card)
        try:
            chunks = await send_goal(client, 'Set up a home Wi-Fi router.')
            content_chunks = [c for c in chunks if get_stream_response_text(c).strip()]
            assert len(content_chunks) > 1, (
                f'expected genuinely incremental output (>1 content-bearing event), '
                f'got {len(content_chunks)}'
            )
            final_text = get_stream_response_text(content_chunks[-1]).strip()
            assert final_text, 'expected a non-empty final compiled guide'
            print(f'OK ({len(content_chunks)} incremental events): {final_text}')
        finally:
            # A close()-time failure must never mask a real assertion failure raised
            # inside the try block above.
            with contextlib.suppress(Exception):
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
