# Research Agent with A2A Protocol

This sample demonstrates a research agent built with [LangGraph](https://langchain-ai.github.io/langgraph/) and exposed through the A2A protocol. It showcases comprehensive research capabilities with support for both synchronous and streaming operations.

## How It Works

This agent uses LangGraph with OpenAI to provide comprehensive research services, conducting thorough analysis of topics, gathering relevant information, and presenting findings in a clear and structured manner. The agent is capable of handling complex queries and providing detailed, well-researched responses across various domains. The A2A protocol enables standardized interaction with the agent, allowing clients to send requests and receive real-time updates.

## Prerequisites

- Python 3.13 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an LLM and API Key

## Setup & Running

1. Navigate to the research agent directory:

   ```bash
   cd ai-run-demo-agents/python/agents/research-agent
   ```

2. Create an environment file from the shared example, then fill in real values:

   ```bash
   cp ../../.env.example .env
   ```

   Edit `.env` and replace the placeholder values with your actual credentials.

3.1. Run the agent:

   ```bash
   # Basic run on default port 10700
   uv run .

   # On custom host/port
   uv run . --host 0.0.0.0 --port 8080
   ```

3.2. With Docker

   ```bash
   # Build docker image
   docker buildx build --build-context ai-run-agents=/path/to/ai-run-demo-agents/python/ -t research-agent:latest .

   # Run docker container
   docker run -it -p 10700:10700 -v ./.env:/app/agents/research-agent/.env research-agent:latest
   ```

4. Testing

The test client provides a way to verify the ResearchAgent's A2A protocol implementation,
including both synchronous and streaming interactions.

### Prerequisites

- The agent server must be running (see Setup & Running section above)
- Python 3.13+ installed
- Required dependencies installed (see Setup section)

### Running Tests

   ```bash
   # From the research-agent directory
   uv run test_client.py
   ```

## Features

- Comprehensive research capabilities
- Support for both synchronous and streaming operations
- Real-time updates during long-running research tasks
- Configurable server settings via environment variables
- Optional ngrok tunneling for external access
- Detailed logging and error handling

## Environment Variables

- `HOST`: Server host address (default: localhost)
- `PORT`: Server port number (default: 10700)
- `LOG_LEVEL`: Logging level (default: INFO)
- `ENABLE_NGROK`: Whether to enable ngrok tunneling (default: false)

## Limitations

- Only supports text-based input/output (no multi-modal support)
- Memory is session-based and not persisted between server restarts
- Research capabilities are limited to the model's knowledge cutoff date
