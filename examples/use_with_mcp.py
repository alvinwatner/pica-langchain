"""
Example demonstrating how to use pica-langchain with MCP.
"""

import os
import sys
import asyncio

from langchain_openai import ChatOpenAI
from langchain.agents import AgentType
from pica_langchain import PicaClient, create_pica_agent
from pica_langchain.models import PicaClientOptions

# Configure MCP servers
mcp_options = {
    # "youtube": {
    #     "url": "https://mcp.zapier.com/api/mcp/s/MzgwOTJhMzItMTIxMC00N2I2LWI0OTctNzM2Zjc3NWI2ZWRkOjllYzVkZDhiLWI3MjQtNDJjZi04NmZkLTU3YTlmZmYwMmY3ZA==/sse",
    #     "transport": "sse",
    # }
    "notion": {
        "url": "https://notion-mcp-server.klavis.ai/sse?instance_id=c3d99a79-351c-445b-a0de-1c7018866dfc",
        "transport": "sse",
    }    
    # "KlavisReportGen": {
    #     "url": "https://klavis-reportgen-mcp-server.klavis.ai/sse?instance_id=04080015-04d4-48dd-b8d0-6c6a6ca17b80",
    #     "transport": "sse",
    # },
    # "steve-tasks": {
    #     "command": "/bin/bash",
    #     "args": ["/Users/alvin/Projects/steve-mcp/run_steve_mcp.sh"],
    #     "transport": "stdio",
    # },
    # "math": {
    #     "command": "python",
    #     "args": ["./examples/mcp_server/math_server.py"],
    #     "transport": "stdio",
    # },
    # "weather": {
    #     "url": "http://0.0.0.0:8000/sse",
    #     "transport": "sse",
    # }
}


def get_env_var(name: str) -> str:
    """Get environment variable or exit if not set."""
    value = os.environ.get(name)

    if not value:
        print(f"ERROR: {name} environment variable must be set")
        sys.exit(1)

    return value


async def main():
    pica_client = await PicaClient.create(
        secret=get_env_var("PICA_SECRET"),
        options=PicaClientOptions(
            mcp_options=mcp_options,
        ),
    )

    llm = ChatOpenAI(
        temperature=0,
        model="gpt-4.1",
    )

    # Create an agent with Pica tools
    agent = create_pica_agent(
        client=pica_client,
        llm=llm,
        agent_type=AgentType.OPENAI_FUNCTIONS,
    )

    import signal

    def handle_sigterm(*args):
        print("\nReceived shutdown signal. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    result = await agent.ainvoke(
        {
            "input": ("Can you query the databases in my notion?")
            # "input": ("Can you check what tasks I have?")
            # "input": (
            #     "First, calculate 25 * 17, then check weather in New York, finally list all connectors Pica supported"
            # )
        }
    )

    print(f"\nWorkflow Result:\n {result}")


if __name__ == "__main__":
    asyncio.run(main())
