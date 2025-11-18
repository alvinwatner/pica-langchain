import warnings
import asyncio
from typing import List, Optional, Dict, Any, Union

from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain.tools import BaseTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.llms.base import BaseLLM
from langchain.chat_models.base import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .flutter_formatter import FlutterUIFormatter
from .client import PicaClient
from .tools import (
    GetAvailableActionsTool,
    GetActionKnowledgeTool,
    ExecuteTool,
    PromptToConnectPlatformTool,
    ReinitiateConnectionTool,
    WebSearchTool,
    GoogleCustomSearchTool,
    RedirectToAppTool,
)

from .file_tools import create_file_processing_tools
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
        RedirectToAppTool(client=client)
    ]

    # Add the PromptToConnectPlatformTool if AuthKit is enabled
    if hasattr(client, "_use_authkit") and client._use_authkit:
        tools.append(PromptToConnectPlatformTool(client=client))
        tools.append(ReinitiateConnectionTool(client=client))
        
    return tools


def get_tools_from_client(
    client: PicaClient,
    disable_web_search: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,  # New parameter
) -> List[BaseTool]:
    """
    Get all tools from a Pica client, including Pica tools, MCP tools, web search tools, and file processing tools.

    Args:
        client: The Pica client to use.
        disable_web_search: Whether to disable web search tools.
        uploaded_files: List of uploaded file information for creating file processing tools.

    Returns:
        A list of LangChain tools.
    """
    # Get standard Pica tools
    pica_tools = create_pica_tools(client)

    # Get MCP tools if available
    mcp_tools = client.get_mcp_tools() if hasattr(client, "get_mcp_tools") else []

    # Add web search tools if not disabled
    search_tools = []
    if not disable_web_search:
        if hasattr(client, "serper_api_keys") and client.serper_api_keys:
            search_tools.append(
                WebSearchTool(
                    serper_api_keys=client.serper_api_keys,
                    firecrawl_api_keys=getattr(client, "firecrawl_api_keys", None),
                    client=client,
                )
            )

        if (
            hasattr(client, "google_search_api_keys")
            and client.google_search_api_keys
            and hasattr(client, "google_search_engine_id")
            and client.google_search_engine_id
        ):
            search_tools.append(
                GoogleCustomSearchTool(
                    api_keys=client.google_search_api_keys,
                    cx=client.google_search_engine_id,
                    client=client,
                )
            )

    # Create file processing tools if files are uploaded
    file_tools = []
    if uploaded_files:
        file_tools = create_file_processing_tools(
            client=client,
            uploaded_files=uploaded_files,
        )
        logger.info(f"Created {len(file_tools)} file processing tools")

    # Combine all tools
    all_tools = pica_tools + mcp_tools + search_tools + file_tools

    return all_tools


def generate_file_processing_instructions(uploaded_files: List[Dict[str, Any]]) -> str:
    """
    Generate instructions for the agent on how to use file processing tools.

    Args:
        uploaded_files: List of uploaded file information

    Returns:
        Instructions string for the agent
    """
    file_types = set()
    file_list = []

    for file_info in uploaded_files:
        content_type = file_info.get("type", "").lower()
        filename = file_info.get("name", "unknown")
        file_path = file_info.get("path", "")

        file_list.append(f"- {filename} ({content_type}) at path: {file_path}")

        if "pdf" in content_type:
            file_types.add("PDF")
        elif content_type in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]:
            file_types.add("Excel")
        elif content_type.startswith("image/"):
            file_types.add("Image")

    instructions = f"""

FILE PROCESSING CAPABILITIES:
You have access to LOCAL file processing tools that work DIFFERENTLY from Pica platform tools.
These tools do NOT require platform connections and should be used DIRECTLY when users ask about uploaded files.

UPLOADED FILES:
{chr(10).join(file_list)}

IMPORTANT: File processing tools are LOCAL tools, not Pica platform tools:
- Do NOT use getAvailableActions, getActionKnowledge, or execute for file processing
- Do NOT treat file processing as platform connections
- Use file processing tools DIRECTLY when users ask about files

AVAILABLE FILE PROCESSING TOOLS:
"""

    if "PDF" in file_types:
        instructions += """
- analyze_pdf: Process PDF files directly
  * Operations: extract_text, get_info, search
  * Usage: analyze_pdf(file_path="/path/to/file.pdf", operation="extract_text")
  * No connection required - this is a local tool
"""

    if "Excel" in file_types:
        instructions += """
- analyze_excel: Process Excel files directly  
  * Operations: get_info, extract_data, summary_stats, search
  * Usage: analyze_excel(file_path="/path/to/file.xlsx", operation="get_info")
  * No connection required - this is a local tool
"""

    if "Image" in file_types:
        instructions += """
- analyze_image: Process image files directly
  * Operations: get_info, extract_text, get_base64
  * Usage: analyze_image(file_path="/path/to/image.png", operation="extract_text")
  * No connection required - this is a local tool
"""

    instructions += """
WORKFLOW FOR FILE PROCESSING:
1. When user asks about uploaded files, use file processing tools DIRECTLY
2. Do NOT follow the Pica platform workflow (getAvailableActions -> getActionKnowledge -> execute)
3. File processing tools work independently and immediately
4. Only use Pica platform workflow for actual platform integrations (Gmail, Slack, etc.)

EXAMPLES:
- "Analyze this PDF" → Use analyze_pdf tool directly
- "What's in the Excel file?" → Use analyze_excel tool directly  
- "Extract text from image" → Use analyze_image tool directly
- "Send an email" → Use Pica platform workflow (getAvailableActions for gmail, etc.)
"""

    return instructions


def generate_system_prompt(
    client: PicaClient,
    system_prompt: Optional[str] = None,
    override_default_prompt: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate the system prompt for Pica agents.

    This function handles the logic for combining the default Pica system prompt with any
    custom system prompt, handling asyncio runtime contexts, and adding file processing instructions.

    Args:
        client: The Pica client to use.
        system_prompt: Optional custom system prompt to prepend to the Pica system prompt.
        override_default_prompt: If True, completely replaces the default system prompt with the provided system_prompt.
        uploaded_files: List of uploaded file information for creating file processing instructions.

    Returns:
        The combined system prompt string.
    """
    if system_prompt:
        if override_default_prompt:
            warnings.warn(
                "Overriding the default Pica system prompt. This will remove all Pica-specific instructions "
                "and may disrupt core functionality. Only use this if you know what you're doing.",
                UserWarning,
            )
            try:
                # If we're already in a running event loop
                loop = asyncio.get_running_loop()
                # Create a basic custom prompt with required information
                combined_system_prompt = f"{system_prompt}\n<connections_info>\n{client.connections_info}\n</connections_info>\n<available_platforms_info>\n{client.available_platforms_info}\n</available_platforms_info>\n<mcp_tools_info>\n{client.mcp_tools_info}\n</mcp_tools_info>"

                # Add file processing instructions
                if uploaded_files:
                    file_instructions = generate_file_processing_instructions(
                        uploaded_files
                    )
                    combined_system_prompt += f"\n<file_processing_info>\n{file_instructions}\n</file_processing_info>"
            except RuntimeError:
                # If we're not in a running event loop, we can use asyncio.run
                combined_system_prompt = asyncio.run(
                    client.generate_custom_system_prompt(
                        system_prompt, override_default=True
                    )
                )
                if uploaded_files:
                    file_instructions = generate_file_processing_instructions(
                        uploaded_files
                    )
                    combined_system_prompt += f"\n<file_processing_info>\n{file_instructions}\n</file_processing_info>"
        else:
            try:
                # If we're already in a running event loop
                loop = asyncio.get_running_loop()
                combined_system_prompt = client.system
                if system_prompt:
                    from .prompts import generate_full_system_prompt

                    combined_system_prompt = generate_full_system_prompt(
                        combined_system_prompt, system_prompt
                    )

                # Add file processing instructions
                if uploaded_files:
                    file_instructions = generate_file_processing_instructions(
                        uploaded_files
                    )
                    combined_system_prompt += f"\n<file_processing_info>\n{file_instructions}\n</file_processing_info>"
            except RuntimeError:
                # If we're not in a running event loop, we can use asyncio.run
                combined_system_prompt = asyncio.run(
                    client.generate_system_prompt(system_prompt)
                )
                if uploaded_files:
                    file_instructions = generate_file_processing_instructions(
                        uploaded_files
                    )
                    combined_system_prompt += f"\n<file_processing_info>\n{file_instructions}\n</file_processing_info>"
    else:
        # No custom system prompt provided, use the default
        combined_system_prompt = client.system
        if uploaded_files:
            file_instructions = generate_file_processing_instructions(uploaded_files)
            combined_system_prompt += f"\n<file_processing_info>\n{file_instructions}\n</file_processing_info>"

    return combined_system_prompt


def create_pica_agent(
    client: PicaClient,
    llm: Union[BaseLLM, BaseChatModel],
    agent_type: Any = None,  # Deprecated parameter, kept for backward compatibility
    verbose: bool = False,
    agent_kwargs: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[BaseTool]] = None,
    disable_web_search: Optional[bool] = False,
    override_default_prompt: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    **kwargs,
):
    """
    Create a LangChain agent with Pica tools using modern tool calling API.

    Args:
        client: The Pica client to use.
        llm: The language model to use.
        agent_type: Deprecated - kept for backward compatibility, no longer used.
        verbose: Whether to enable verbose output.
        agent_kwargs: Additional arguments for the agent (deprecated, use **kwargs instead).
        system_prompt: Optional custom system prompt to prepend to the Pica system prompt.
        tools: Optional list of additional tools to include alongside the Pica tools.
        disable_web_search: If True, disables the web search tool.
        override_default_prompt: If True, completely replaces the default system prompt with the provided system_prompt.
                                WARNING: This will remove all Pica-specific instructions and may disrupt core functionality.
        uploaded_files: List of uploaded file information for creating file processing tools.
        **kwargs: Additional arguments for AgentExecutor.

    Returns:
        A LangChain AgentExecutor.
    """
    import asyncio

    # Create default Pica tools
    all_tools = get_tools_from_client(
        client,
        disable_web_search,
        uploaded_files,
    )

    # Combine default tools with any user-provided tools
    if tools:
        all_tools = all_tools + tools

    # Generate system prompt with Pica information
    combined_system_prompt = generate_system_prompt(
        client=client,
        system_prompt=system_prompt,
        override_default_prompt=override_default_prompt,
        uploaded_files=uploaded_files,
    )

    # Create ChatPromptTemplate with required structure for modern agents
    prompt = ChatPromptTemplate.from_messages([
        ("system", combined_system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create the agent using modern tool calling approach
    agent = create_tool_calling_agent(llm, all_tools, prompt)

    # Wrap in AgentExecutor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=verbose,
        **kwargs,
    )

    return agent_executor


def create_flutter_ui_agent(
    client: PicaClient,
    llm: Union[BaseLLM, BaseChatModel],
    flutter_llm: BaseChatModel,
    agent_type: Any = None,  # Deprecated parameter, kept for backward compatibility
    verbose: bool = False,
    agent_kwargs: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    ui_formatter_prompt: Optional[str] = None,
    tools: Optional[List[BaseTool]] = None,
    override_default_prompt: bool = False,
    disable_web_search: bool = False,
    return_intermediate_steps: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    **kwargs,
):
    """
    Create a Flutter UI agent with Pica tools using modern tool calling API.

    Args:
        client: The Pica client to use.
        llm: The language model to use for the agent's reasoning and tool usage.
        flutter_llm: The fine-tuned OpenAI model to use for generating Flutter UI JSON.
        agent_type: Deprecated - kept for backward compatibility, no longer used.
        verbose: Whether to enable verbose output.
        agent_kwargs: Additional arguments for the agent (deprecated, use **kwargs instead).
        system_prompt: Optional custom system prompt to prepend to the Flutter system prompt.
        ui_formatter_prompt: Optional custom prompt template for generating Flutter UI JSON.
                           If provided, it will replace the default prompt template.
                           The template should include placeholders for {agent_output} and {tool_usage_str}.
        override_default_prompt: If True, completely replaces the default system prompt with the provided system_prompt.
                                WARNING: This will remove all Pica-specific instructions and may disrupt core functionality.
        tools: Optional list of additional tools to include alongside the Pica tools.
        disable_web_search: If True, disables the web search tool.
        return_intermediate_steps: Whether to return intermediate steps in the agent's output.
        uploaded_files: List of uploaded file information for creating file processing tools.
        **kwargs: Additional arguments for AgentExecutor.

    Returns:
        A Flutter UI agent.
    """
    # Create default Pica tools
    all_tools = get_tools_from_client(
        client,
        disable_web_search,
        uploaded_files,
    )

    # Combine default tools with any user-provided tools
    if tools:
        all_tools = all_tools + tools

    combined_system_prompt = generate_system_prompt(
        client=client,
        system_prompt=system_prompt,
        override_default_prompt=override_default_prompt,
        uploaded_files=uploaded_files,
    )

    # Create ChatPromptTemplate with required structure for modern agents
    prompt = ChatPromptTemplate.from_messages([
        ("system", combined_system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create the agent using modern tool calling approach
    agent = create_tool_calling_agent(llm, all_tools, prompt)

    # Wrap in AgentExecutor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=verbose,
        return_intermediate_steps=return_intermediate_steps,
        **kwargs,
    )

    # Wrap the agent executor with the Flutter UI formatter
    return FlutterUIAgent(agent_executor, flutter_llm, ui_formatter_prompt)


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
