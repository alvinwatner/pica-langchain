"""
Example demonstrating how to use pica-langchain with LangChain.
"""

import os
import sys

from langchain_openai import ChatOpenAI
from langchain.agents import AgentType
from pica_langchain import PicaClient, create_pica_agent
from pica_langchain.models import PicaClientOptions


def get_env_var(name: str) -> str:
    """Get environment variable or exit if not set."""
    value = os.environ.get(name)

    if not value:
        print(f"ERROR: {name} environment variable must be set")
        sys.exit(1)

    return value


def main():
    try:
        pica_client = PicaClient(
            secret=get_env_var("PICA_SECRET"),
            options=PicaClientOptions(
                serper_api_key=get_env_var("SERPER_API_KEY"),
                # server_url="https://my-self-hosted-server.com",
                # identity_type="user"
                # identity="user-id",

                connectors=[
                    "*"
                ],  # Initialize all available connections for this example
            ),
        )

        pica_client.initialize()
        
        llm = ChatOpenAI(
            temperature=0,
            model="gpt-4.1",
        )
        
        agent = create_pica_agent(
            client=pica_client,
            llm=llm,
            agent_type=AgentType.OPENAI_FUNCTIONS,
        )

        # Example 1: Using a query that might use platform-specific tools
        result1 = agent.invoke(
            {"input": ("What is the population density of New York in 2025?")},
        )

        print(f"\nExample 1 Result (Population density query):\n {result1}")

        # Example 2: Using a query that would benefit from web search
        result2 = agent.invoke(
            {
                "input": (
                    "What are the latest developments in the war between Ukraine and Russia?"
                )
            },
        )

        print(f"\nExample 2 Result (Web search query):\n {result2}")

        # Example 3: Using a query that doesn't need web search
        result3 = agent.invoke(
            {
                "input": (
                    "What is the capital of France? Can you also explain what a capital city is?"
                )
            },
        )

        print(f"\nExample 3 (No web search needed):\n {result3}")

    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
