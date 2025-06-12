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
                openai_api_key=get_env_var("OPENAI_API_KEY"),
                connectors=["*"],
            ),
        )

        llm = ChatOpenAI(
            temperature=0,
            model="gpt-4o",
        )

        agent = create_pica_agent(
            client=pica_client,
            llm=llm,
            agent_type=AgentType.OPENAI_FUNCTIONS,
            uploaded_files=[
                {
                    "path": "examples/image_people_analysis.png",
                    "type": "image/png",
                    "name": "image_people_analysis.png",
                }
            ],
            disable_web_search=True,
        )

        # Example 1: Using a query that might use platform-specific tools
        result1 = agent.invoke(
            {"input": ("Who are the people in this image? Describe for me his appearance.")},
        )

        print(f"\nExample 1 Result (Image people analysis query):\n {result1}")

    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
