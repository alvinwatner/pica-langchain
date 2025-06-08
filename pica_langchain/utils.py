import warnings
import asyncio
from typing import List, Optional, Dict, Any, Union

from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain.tools import BaseTool
from langchain.agents import AgentType, initialize_agent
from langchain.llms.base import BaseLLM
from langchain.chat_models.base import BaseChatModel

from .flutter_formatter import FlutterUIFormatter
from .client import PicaClient
from .prompts import generate_full_flutter_system_prompt
from .tools import (
    GetAvailableActionsTool,
    GetActionKnowledgeTool,
    ExecuteTool,
    PromptToConnectPlatformTool,
    WebSearchTool,
)

from .logger import get_logger


warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

logger = get_logger()


def create_pica_tools(client: PicaClient) -> List[BaseTool]:
    """
    Create a list of Pica tools for use with LangChain.

    Args:
        client: The Pica client to use.

    Returns:
        A list of LangChain tools.
    """
    tools: List[BaseTool] = [
        GetAvailableActionsTool(client=client),
        GetActionKnowledgeTool(client=client),
        ExecuteTool(client=client),
    ]

    # Add the PromptToConnectPlatformTool if AuthKit is enabled
    if hasattr(client, "_use_authkit") and client._use_authkit:
        tools.append(PromptToConnectPlatformTool(client=client))

    return tools


def get_tools_from_client(
    client: PicaClient, disable_web_search: bool = False
) -> List[BaseTool]:
    """
    Get all tools from a Pica client, including both Pica tools, MCP tools, and web search tools.

    Args:
        client: The Pica client to use.

    Returns:
        A list of LangChain tools.
    """
    # Get standard Pica tools
    pica_tools = create_pica_tools(client)

    # Get MCP tools if available
    mcp_tools = client.get_mcp_tools() if hasattr(client, "get_mcp_tools") else []

    # Add web search tool if not disabled
    search_tool = (
        WebSearchTool(
            serper_api_keys=client.serper_api_keys,
            firecrawl_api_keys=client.firecrawl_api_keys,
        )
        if not disable_web_search
        else None
    )

    all_tools = pica_tools + mcp_tools

    if search_tool:
        all_tools.append(search_tool)

    return all_tools


def create_pica_agent(
    client: PicaClient,
    llm: Union[BaseLLM, BaseChatModel],
    agent_type: AgentType = AgentType.OPENAI_FUNCTIONS,
    verbose: bool = False,
    agent_kwargs: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[BaseTool]] = None,
    disable_web_search: Optional[bool] = False,
    override_default_prompt: bool = False,
    **kwargs,
):
    """
    Create a LangChain agent with Pica tools.

    Args:
        client: The Pica client to use.
        llm: The language model to use.
        agent_type: The type of agent to create.
        verbose: Whether to enable verbose output.
        agent_kwargs: Additional arguments for the agent.
        system_prompt: Optional custom system prompt to prepend to the Pica system prompt.
        tools: Optional list of additional tools to include alongside the Pica tools.
        disable_web_search: If True, disables the web search tool.
        override_default_prompt: If True, completely replaces the default system prompt with the provided system_prompt.
                                WARNING: This will remove all Pica-specific instructions and may disrupt core functionality.
        **kwargs: Additional arguments for initialize_agent.

    Returns:
        A LangChain agent.
    """
    import asyncio

    # Create default Pica tools
    all_tools = get_tools_from_client(client, disable_web_search)

    # Combine default tools with any user-provided tools
    if tools:
        all_tools = all_tools + tools

    # Generate system prompt with Pica information
    if system_prompt:
        if override_default_prompt:
            # Log a warning about overriding the default prompt
            warnings.warn(
                "Overriding the default Pica system prompt. This will remove all Pica-specific instructions "
                "and may disrupt core functionality. Only use this if you know what you're doing.",
                UserWarning,
            )
            # Use the user's system prompt directly, but still include the necessary connection info
            try:
                loop = asyncio.get_running_loop()
                combined_system_prompt = f"{system_prompt}\n\<connections_info>\n{client.connections_info}\n\</connections_info>\n<available_platforms_info>\n{client.available_platforms_info}\n</available_platforms_info>\n<mcp_tools_info>\n{client.mcp_tools_info}\n\</mcp_tools_info>"

            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                combined_system_prompt = asyncio.run(
                    client.generate_custom_system_prompt(
                        system_prompt, override_default=True
                    )
                )
        else:
            # Standard behavior: append user prompt to default prompt
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, use the client.system property directly
                # and append the user system prompt
                combined_system_prompt = client.system
                if system_prompt:
                    from .prompts import generate_full_system_prompt

                    combined_system_prompt = generate_full_system_prompt(
                        combined_system_prompt, system_prompt
                    )
            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                combined_system_prompt = asyncio.run(
                    client.generate_system_prompt(system_prompt)
                )
    else:
        # If no custom prompt, use the default system prompt
        combined_system_prompt = client.system

    default_agent_kwargs = {"system_message": combined_system_prompt}

    # Merge default agent kwargs with user-provided ones
    if agent_kwargs:
        default_agent_kwargs.update(agent_kwargs)

    # Create and return the agent
    return initialize_agent(
        all_tools,
        llm,
        agent=agent_type,
        verbose=verbose,
        agent_kwargs=default_agent_kwargs,
        **kwargs,
    )


def create_flutter_ui_agent(
    client: PicaClient,
    llm: Union[BaseLLM, BaseChatModel],
    flutter_llm: BaseChatModel,
    agent_type: AgentType = AgentType.OPENAI_FUNCTIONS,
    verbose: bool = False,
    agent_kwargs: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    ui_formatter_prompt: Optional[str] = None,
    tools: Optional[List[BaseTool]] = None,
    override_default_prompt: bool = False,
    disable_web_search: bool = False,
    return_intermediate_steps: bool = False,
    **kwargs,
):
    """
    Create a Flutter UI agent with Pica tools.

    Args:
        client: The Pica client to use.
        llm: The language model to use for the agent's reasoning and tool usage.
        flutter_llm: The fine-tuned OpenAI model to use for generating Flutter UI JSON.
        agent_type: The type of agent to create.
        verbose: Whether to enable verbose output.
        agent_kwargs: Additional arguments for the agent.
        system_prompt: Optional custom system prompt to prepend to the Flutter system prompt.
        ui_formatter_prompt: Optional custom prompt template for generating Flutter UI JSON.
                           If provided, it will replace the default prompt template.
                           The template should include placeholders for {agent_output} and {tool_usage_str}.
        override_default_prompt: If True, completely replaces the default system prompt with the provided system_prompt.
                                WARNING: This will remove all Pica-specific instructions and may disrupt core functionality.
        tools: Optional list of additional tools to include alongside the Pica tools.
        disable_web_search: If True, disables the web search tool.
        return_intermediate_steps: Whether to return intermediate steps in the agent's output.
        **kwargs: Additional arguments for initialize_agent.

    Returns:
        A Flutter UI agent.
    """
    # Create default Pica tools
    all_tools = get_tools_from_client(client, disable_web_search)

    # Combine default tools with any user-provided tools
    if tools:
        all_tools = all_tools + tools

    # Append the custom system prompt if provided
    if system_prompt:
        if override_default_prompt:
            # Log a warning about overriding the default prompt
            warnings.warn(
                "Overriding the default Pica system prompt. This will remove all Pica-specific instructions "
                "and may disrupt core functionality. Only use this if you know what you're doing.",
                UserWarning,
            )
            # Use the user's system prompt directly, but still include the necessary connection info
            try:
                loop = asyncio.get_running_loop()
                combined_system_prompt = f"{system_prompt}\n\<connections_info>\n{client.connections_info}\n\</connections_info>\n<available_platforms_info>\n{client.available_platforms_info}\n</available_platforms_info>\n<mcp_tools_info>\n{client.mcp_tools_info}\n\</mcp_tools_info>"

            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                combined_system_prompt = asyncio.run(
                    client.generate_custom_system_prompt(
                        system_prompt, override_default=True
                    )
                )
        else:
            # Standard behavior: append user prompt to default prompt
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, use the client.system property directly
                # and append the user system prompt
                combined_system_prompt = client.system
                if system_prompt:
                    from .prompts import generate_full_system_prompt

                    combined_system_prompt = generate_full_system_prompt(
                        combined_system_prompt, system_prompt
                    )
            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                combined_system_prompt = asyncio.run(
                    client.generate_system_prompt(system_prompt)
                )

    else:
        # If no custom prompt, use the default system prompt
        combined_system_prompt = client.system

    default_agent_kwargs = {
        "system_message": combined_system_prompt,
        "return_intermediate_steps": return_intermediate_steps,
    }

    # Merge default agent kwargs with user-provided ones
    if agent_kwargs:
        default_agent_kwargs.update(agent_kwargs)

    # Create the base agent
    agent = initialize_agent(
        all_tools,
        llm,
        agent=agent_type,
        verbose=verbose,
        agent_kwargs=default_agent_kwargs,
        **kwargs,
    )

    # Wrap the agent with the Flutter UI formatter
    return FlutterUIAgent(agent, flutter_llm, ui_formatter_prompt)


class FlutterUIAgent:
    """
    Agent wrapper that generates Flutter UI JSON from agent responses.
    """

    def __init__(
        self,
        agent,
        flutter_llm: BaseChatModel,
        ui_formatter_prompt: Optional[str] = None,
    ):
        """
        Initialize the Flutter UI Agent.

        Args:
            agent: The LangChain agent to wrap.
            flutter_llm: The fine-tuned OpenAI model to use for generating Flutter UI JSON.
            ui_formatter_prompt: Optional custom prompt template for generating Flutter UI JSON.
                               If provided, it will replace the default prompt template.
                               The template should include placeholders for {agent_output} and {tool_usage_str}.
        """
        self.agent = agent
        self.formatter = FlutterUIFormatter(flutter_llm, ui_formatter_prompt)

    def __call__(self, inputs, **kwargs):
        """
        Run the agent and format the output as Flutter UI JSON.

        Args:
            inputs: The inputs to pass to the agent.
            **kwargs: Additional arguments to pass to the agent.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        # Run the original agent
        result = self.agent(inputs, **kwargs)

        # Extract the output
        output = result.get("output", "")

        # Format the output to Flutter UI JSON
        ui_json = self.formatter.format_to_ui(output)

        # Return both the original result and the UI JSON
        result["ui_json"] = ui_json
        return result

    async def acall(self, inputs, **kwargs):
        """
        Asynchronously run the agent and format the output as Flutter UI JSON.

        Args:
            inputs: The inputs to pass to the agent.
            **kwargs: Additional arguments to pass to the agent.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        # Run the original agent
        result = await self.agent.acall(inputs, **kwargs)
        logger.info(f"UI Agent output: {result}")

        # Extract the output
        output = result.get("output", "")

        # Extract user input using the helper method
        user_input = self.formatter._extract_user_input(inputs)

        # Format the output to Flutter UI JSON with both user input and agent output
        ui_json = self.formatter.format_to_ui(user_input, output)

        # Return both the original result and the UI JSON
        result["ui_json"] = ui_json
        return result

    def run(self, input_text: str, **kwargs):
        """
        Run the agent with a simple string input.

        Args:
            input_text: The input text from the user.
            **kwargs: Additional arguments to pass to the agent.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        return self({"input": input_text}, **kwargs)

    async def arun(self, input_text: str, **kwargs):
        """
        Asynchronously run the agent with a simple string input.

        Args:
            input_text: The input text from the user.
            **kwargs: Additional arguments to pass to the agent.

        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        return await self.acall({"input": input_text}, **kwargs)
