"""
Example of running the standard Pica agent and Flutter UI agent in parallel.
"""

import os
import sys
import asyncio
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from pica_langchain.models import PicaClientOptions
from pica_langchain import PicaClient, create_pica_agent, create_flutter_ui_agent


def get_env_var(name: str) -> str:
    """Get environment variable or exit if not set."""
    value = os.environ.get(name)

    if not value:
        print(f"ERROR: {name} environment variable must be set")
        sys.exit(1)

    return value


async def run_agents_in_parallel(user_input: str) -> Dict[str, Any]:
    """
    Run both the standard Pica agent and the Flutter UI agent in parallel.

    Args:
        user_input: The user's input message.

    Returns:
        A dictionary containing both agents' responses.
    """
    # Initialize the Pica client
    options = PicaClientOptions(
        connectors=["*"],  # Initialize all available connections
        # Add any other options you need
    )
    pica_client = PicaClient(
        secret=os.getenv("PICA_SECRET"),
        options=options,
    )

    # Initialize the client asynchronously to set up MCP tools
    await pica_client.async_initialize()

    # Create language models
    llm = ChatOpenAI(
        temperature=0,
        model="gpt-4",
        streaming=True,
    )

    # Create a fine-tuned model for Flutter UI generation
    # Replace "ft:gpt-3.5-turbo-xxxx" with your actual fine-tuned model ID
    flutter_llm = ChatOpenAI(
        temperature=0,
        model="ft:gpt-4.1-2025-04-14:steve:stac:BWImQZFZ",
        streaming=False,  # No streaming for the UI generation
    )

    # Optional custom system prompt
    system_prompt = """
    You are an AI Assistant specialized in generating Stac JSON for Flutter's Server-Driven UI framework. Your task is to transform API responses into properly formatted Stac JSON that creates elegant, intuitive UIs adhering to strict design guidelines.
    """

    # Create both agents
    chat_agent = create_pica_agent(
        client=pica_client,
        llm=llm,
        return_intermediate_steps=True,
    )

    ui_agent = create_flutter_ui_agent(
        client=pica_client,
        llm=flutter_llm,
        flutter_llm=flutter_llm,
        return_intermediate_steps=True,
        ui_formatter_prompt=system_prompt
    )

    # Run both agents in parallel
    chat_task = asyncio.create_task(chat_agent.acall({"input": user_input}))
    ui_task = asyncio.create_task(ui_agent.arun(user_input))

    # Wait for both tasks to complete
    chat_result, ui_result = await asyncio.gather(chat_task, ui_task)

    # Return both results
    return {"chat_response": chat_result, "ui_response": ui_result}


async def main():
    """Main function to demonstrate parallel agent execution."""
    user_input = "What actions are available in Gmail?"

    print(f"User input: {user_input}")
    print("Running agents in parallel...")

    results = await run_agents_in_parallel(user_input)

    print("\n--- Chat Agent Response ---")
    print(results["chat_response"]["output"])

    print("\n--- Flutter UI Agent Response ---")
    print(f"UI JSON: {results['ui_response']['ui_json']}")


if __name__ == "__main__":
    asyncio.run(main())
