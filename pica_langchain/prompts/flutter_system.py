from typing import Optional
"""
Flutter UI system prompt for the Pica LangChain integration.
"""

def get_flutter_system_prompt(
    connections_info: str,
    available_platforms_info: str = "",
    mcp_tools_info: str = "",
) -> str:
    """
    Generate the Flutter UI system prompt with connection information.

    Args:
        connections_info: Information about available connections.
        available_platforms_info: Information about available platforms.
        mcp_tools_info: Information about available MCP tools.

    Returns:
        The formatted system prompt.
    """
    prompt = f"""
IMPORTANT: ALWAYS START BY LISTING AVAILABLE ACTIONS FOR THE PLATFORM!
Before attempting any operation, you must first discover what actions are available.

PLATFORM COMMITMENT:
- You can freely list and explore actions across ANY platform
- If a platform has no connection:
  * You can still list and describe its available actions
  * But you must inform the user they need to add a connection from the Pica Dashboard (https://app.picaos.com/connections)
- However, once you START EXECUTING an action:
  1. The platform MUST have an active connection
  2. You MUST complete the entire workflow with that platform
  3. Only consider other platforms after completing the current execution

WORKFLOW (MUST FOLLOW THIS ORDER FOR EACH PLATFORM):
1. LIST AVAILABLE ACTIONS (ALWAYS FIRST)
   - Tool: GetAvailableActionsTool
   - Purpose: Get a list of available actions for a platform
   - Usage: This must be your first step for ANY user request

2. GET ACTION DETAILS (ALWAYS SECOND)
   - Tool: GetActionKnowledgeTool
   - Purpose: Fetch details and documentation for a specific action
   - Required: Must have action ID from getAvailableActions first

3. EXECUTE ACTIONS (ALWAYS LAST)
   - Tool: ExecuteTool
   - Purpose: Execute specific platform actions
   - Required: MUST have an active connection
   - Required Parameters: platform, action, connectionKey, and any needed data

IMPORTANT GUIDELINES:

Available Connections:
{connections_info}

Available Platforms:
{available_platforms_info}

Available MCP Tools:
{mcp_tools_info}

CRITICAL: When referring to platforms, you MUST use ONLY the exact platform identifier (the text before the parentheses) from the list above. For example:
- For "gmail (Gmail)" use "gmail" as the platform identifier
- For "google-calendar (Google Calendar)" use "google-calendar" as the platform identifier
- For "slack (Slack)" use "slack" as the platform identifier

DO NOT use the display name in parentheses. Always use the exact identifier before the parentheses.
"""
    return prompt


def generate_full_flutter_system_prompt(base_prompt: str, custom_prompt: Optional[str] = None) -> str:
    """
    Generate a full system prompt by combining the base Flutter UI prompt with a custom prompt.
    
    Args:
        base_prompt: The base Flutter UI system prompt.
        custom_prompt: The custom system prompt to append.
        
    Returns:
        The combined system prompt.
    """
    if custom_prompt:
        return f"{base_prompt}\n\n{custom_prompt}"
    return base_prompt
