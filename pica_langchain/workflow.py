"""
Workflow execution agent for Pica.

This module provides a specialized LangChain agent for executing pre-defined workflows.
Unlike create_pica_agent which handles discovery and general chat, this agent focuses
on executing workflow steps sequentially with intelligent data mapping between steps.
"""

import json
from typing import Any, Dict, List, Optional, Union

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models import BaseChatModel, BaseLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from .client import PicaClient
from .file_tools import create_file_processing_tools
from .logger import get_logger
from .tools import ExecuteTool, GoogleCustomSearchTool, WebSearchTool

logger = get_logger()


def get_workflow_tools(
    client: PicaClient,
    disable_web_search: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
) -> List[BaseTool]:
    """
    Get tools needed for workflow execution.

    This is a filtered subset of tools - only those needed for execution.
    Excludes discovery tools (GetAvailableActions, GetActionKnowledge).

    Args:
        client: PicaClient for executing actions
        disable_web_search: If True, exclude web search tools
        uploaded_files: List of uploaded files for file processing tools

    Returns:
        List of LangChain tools for workflow execution
    """
    # Core execution tool
    tools: List[BaseTool] = [ExecuteTool(client=client)]

    # Web search tools (same pattern as get_tools_from_client in utils.py)
    if not disable_web_search:
        if hasattr(client, "serper_api_keys") and client.serper_api_keys:
            tools.append(
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
            tools.append(
                GoogleCustomSearchTool(
                    api_keys=client.google_search_api_keys,
                    cx=client.google_search_engine_id,
                    client=client,
                )
            )

    # File processing tools
    if uploaded_files:
        file_tools = create_file_processing_tools(
            client=client,
            uploaded_files=uploaded_files,
        )
        tools.extend(file_tools)
        logger.info(f"Added {len(file_tools)} file processing tools")

    # MCP tools
    if hasattr(client, "get_mcp_tools"):
        mcp_tools = client.get_mcp_tools()
        tools.extend(mcp_tools)
        if mcp_tools:
            logger.info(f"Added {len(mcp_tools)} MCP tools")

    return tools


def _escape_braces(text: str) -> str:
    """Escape curly braces for use in LangChain prompt templates."""
    return text.replace("{", "{{").replace("}", "}}")


def _format_payload_fields(fields: Optional[List[Dict[str, Any]]]) -> str:
    """
    Format webhook payload field definitions for the prompt.

    Args:
        fields: List of payload field definitions with name, type, description, required

    Returns:
        Formatted string describing the expected fields
    """
    if not fields:
        return "No specific fields defined"

    lines = []
    for field in fields:
        required = "(required)" if field.get("required", True) else "(optional)"
        field_type = field.get("type", "string")
        lines.append(
            f"- **{field['name']}** ({field_type}) {required}: {field.get('description', 'No description')}"
        )
    return "\n".join(lines)


def generate_workflow_system_prompt(
    workflow: Dict[str, Any],
    client: PicaClient,
    webhook_context: Optional[str] = None,
    webhook_payload_fields: Optional[List[Dict[str, Any]]] = None,
    initial_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate system prompt for workflow execution agent.

    Args:
        workflow: Workflow definition with steps
        client: PicaClient for connection info
        webhook_context: Context explaining what the webhook payload represents
        webhook_payload_fields: Expected payload field definitions
        initial_data: Actual payload data from webhook trigger

    Returns:
        System prompt string
    """
    # Get connection info for the prompt
    connections = client.get_user_connections()
    connections_info = (
        "\n".join(
            [
                f"- {conn.get('platform', 'unknown')}: key={conn.get('key', 'N/A')}"
                for conn in connections
            ]
        )
        if connections
        else "No connections available"
    )

    # Format workflow steps for the prompt
    # We need to escape curly braces in dynamic content to prevent LangChain
    # from interpreting them as template variables
    steps_info = []
    for i, step in enumerate(workflow.get("steps", []), 1):
        # Escape all dynamic content that might contain curly braces
        name = _escape_braces(step.get("name", f"Step {i}"))
        user_instruction = _escape_braces(
            step.get("user_instruction", "No instruction provided")
        )
        platform = _escape_braces(step.get("platform", "unknown"))
        action_id = _escape_braces(step.get("action_id", "unknown"))
        connection_key = _escape_braces(step.get("connection_key", "N/A"))
        action_path = _escape_braces(step.get("action_path", "/"))
        action_method = _escape_braces(step.get("action_method", "GET"))
        action_knowledge = _escape_braces(
            step.get("action_knowledge", "No documentation available")
        )

        step_info = f"""
### Step {i}: {name}
- **User Instruction**: {user_instruction}
- **Platform**: {platform}
- **Action ID**: {action_id}
- **Connection Key**: {connection_key}
- **Action Path**: {action_path}
- **Method**: {action_method}

**Action Knowledge (API Documentation)**:
```
{action_knowledge}
```
"""
        steps_info.append(step_info)

    steps_formatted = "\n".join(steps_info)

    workflow_name = _escape_braces(workflow.get("name", "Unnamed Workflow"))
    workflow_description = _escape_braces(workflow.get("description", ""))
    connections_info = _escape_braces(connections_info)

    # Build webhook trigger section if this is a webhook-triggered execution
    webhook_section = ""
    if initial_data and webhook_context:
        # Escape the JSON to prevent template interpretation
        escaped_initial_data = _escape_braces(json.dumps(initial_data, indent=2))
        escaped_context = _escape_braces(webhook_context)
        escaped_payload_fields = _escape_braces(_format_payload_fields(webhook_payload_fields))

        webhook_section = f"""
## Webhook Trigger Context

**What triggered this workflow:**
{escaped_context}

**Expected payload fields:**
{escaped_payload_fields}

**Actual data received:**
```json
{escaped_initial_data}
```

**Instructions:**
Use the data above to execute the workflow steps. Map the payload fields to the appropriate
action parameters based on the field descriptions and the user instructions in each step.
For example:
- If a step says "send email to the customer", use the email from the payload
- If a step says "include their name in the subject", use the name field
- If a step says "create calendar event for follow-up", use relevant contact info

"""

    # Use the actual values directly with single braces
    return f"""You are a Workflow Execution Agent. Your job is to execute a sequence of pre-defined workflow steps.

## Workflow: {workflow_name}
{workflow_description}
{webhook_section}
## Your Task
Execute each step in the workflow SEQUENTIALLY. For each step:
1. Read the **user_instruction** to understand what the user wants to achieve
2. Use the **action_knowledge** (API documentation) to understand required parameters
3. Build the proper request parameters based on:
   - Static values from the step definition
   - Data from previous step results (if applicable)
4. Execute the action using the appropriate tool
5. Store the result - it may be needed for subsequent steps

## Critical Rules
- Execute steps IN ORDER (Step 1, then Step 2, etc.)
- STOP IMMEDIATELY if any step fails - do not continue to next steps
- Intelligently map data from previous step results to current step inputs
- Use the action_knowledge to determine what fields go in body vs query_params vs path_variables
- For web search actions (platform: web-search), use the WebSearchTool directly with the query

## ExecuteTool Parameters
When using ExecuteTool for platform actions (NOT web-search), provide:
- **platform**: The platform identifier (e.g., "gmail", "google-calendar")
- **action_id**: The action ID (e.g., "gmail::send-email")
- **action_path**: API path from the step definition
- **method**: HTTP method (GET, POST, PUT, DELETE, PATCH)
- **connection_key**: The connection key for authentication
- **data**: Request body as JSON object (based on action_knowledge)
- **path_variables**: URL path variable values if the path contains {{{{variable}}}}
- **query_params**: Query string parameters

## WebSearchTool
For web search steps (platform: web-search), use the WebSearchTool with:
- **query**: The search query string

## Available Connections
{connections_info}

## Workflow Steps
{steps_formatted}

## Output Format
After executing each step, provide a brief summary:
- What was executed
- Whether it succeeded or failed
- Key data from the result (that might be used in next steps)

At the end, provide a final summary of the entire workflow execution.
"""


def create_workflow_agent(
    client: PicaClient,
    llm: Union[BaseLLM, BaseChatModel],
    workflow: Dict[str, Any],
    disable_web_search: bool = False,
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    verbose: bool = False,
    webhook_context: Optional[str] = None,
    webhook_payload_fields: Optional[List[Dict[str, Any]]] = None,
    initial_data: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> AgentExecutor:
    """
    Create a LangChain agent specialized for workflow execution.

    Unlike create_pica_agent which handles discovery and general chat,
    this agent focuses on executing pre-defined workflow steps with
    intelligent data mapping between steps.

    The agent will:
    - Execute steps sequentially in order
    - Stop immediately if any step fails
    - Map data from previous step results to current step inputs
    - Use ExecuteTool for platform actions and WebSearchTool for web searches

    Args:
        client: PicaClient for executing actions
        llm: Language model for reasoning and data mapping
        workflow: Workflow definition containing steps to execute.
                  Expected format:
                  {
                      "name": str,
                      "description": str (optional),
                      "steps": [
                          {
                              "name": str,
                              "user_instruction": str,
                              "platform": str,
                              "action_id": str,
                              "action_knowledge": str,
                              "action_path": str,
                              "action_method": str,
                              "connection_key": str,
                          },
                          ...
                      ]
                  }
        disable_web_search: If True, disable web search tools
        uploaded_files: List of uploaded files for file processing
        verbose: Enable verbose logging
        webhook_context: Context explaining what the webhook payload represents
        webhook_payload_fields: Expected payload field definitions
        initial_data: Actual payload data from webhook trigger
        **kwargs: Additional arguments for AgentExecutor

    Returns:
        AgentExecutor ready to execute the workflow
    """
    workflow_name = workflow.get("name", "Unnamed")
    steps_count = len(workflow.get("steps", []))
    logger.info(f"Creating workflow agent for: {workflow_name} ({steps_count} steps)")

    # Get filtered tools for workflow execution
    tools = get_workflow_tools(
        client=client,
        disable_web_search=disable_web_search,
        uploaded_files=uploaded_files,
    )

    logger.info(f"Workflow agent tools: {[t.name for t in tools]}")

    # Generate workflow-specific system prompt with optional webhook data
    system_prompt = generate_workflow_system_prompt(
        workflow,
        client,
        webhook_context=webhook_context,
        webhook_payload_fields=webhook_payload_fields,
        initial_data=initial_data,
    )

    logger.info(f'final system prompt is = {system_prompt}')

    # Create prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Create agent using tool calling
    agent = create_tool_calling_agent(llm, tools, prompt)

    # Wrap in AgentExecutor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        **kwargs,
    )

    return agent_executor
