"""
Flutter UI formatter for converting agent responses to Flutter UI JSON.
"""

import json
from typing import Any, Dict, List, Optional, Union
from langchain.schema import AgentAction, AgentFinish
from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.chat_models.base import BaseChatModel
from .logger import get_logger

logger = get_logger()

class FlutterUIFormatter:
    """
    Formatter for converting agent responses to Flutter UI JSON.
    
    This class takes the output from a LangChain agent and uses a fine-tuned
    OpenAI model to convert it into a Flutter server-driven UI JSON format.
    """
    
    def __init__(self, flutter_llm: BaseChatModel):
        """
        Initialize the Flutter UI formatter.
        
        Args:
            flutter_llm: The fine-tuned OpenAI model to use for generating Flutter UI JSON.
        """
        self.flutter_llm = flutter_llm
        
    def format_to_ui(
        self,
        agent_output: str,
        intermediate_steps: Optional[List[Union[AgentAction, AgentFinish]]] = None,
        run_manager: Optional[CallbackManagerForChainRun] = None
    ) -> Dict[str, Any]:
        """
        Format the agent output to Flutter UI JSON.
        
        Args:
            agent_output: The text output from the agent.
            intermediate_steps: Optional list of intermediate steps from the agent.
            run_manager: Optional callback manager for the chain run.
            
        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        logger.info("Converting agent output to Flutter UI JSON")
        
        # Extract tool usage information from intermediate steps if available
        tool_usage = []
        if intermediate_steps:
            for step in intermediate_steps:
                if isinstance(step, tuple) and len(step) >= 2:
                    action, observation = step
                    if hasattr(action, 'tool') and hasattr(action, 'tool_input'):
                        tool_usage.append({
                            "tool": action.tool,
                            "input": action.tool_input,
                            "output": str(observation)
                        })
        
        # Create a prompt for the fine-tuned model
        prompt = self._create_ui_generation_prompt(agent_output, tool_usage)
        
        # Generate Flutter UI JSON using the fine-tuned model
        try:
            response = self.flutter_llm.predict(prompt)
            ui_json = self._extract_json(response)
            logger.info("Successfully generated Flutter UI JSON")
            return ui_json
        except Exception as e:
            logger.error(f"Error generating Flutter UI JSON: {e}", exc_info=True)
            # Fallback to a simple UI representation
            return self._create_fallback_ui(agent_output, str(e))
    
    def _create_ui_generation_prompt(self, agent_output: str, tool_usage: List[Dict[str, Any]]) -> str:
        """
        Create a prompt for the fine-tuned model to generate Flutter UI JSON.
        
        Args:
            agent_output: The text output from the agent.
            tool_usage: Information about tool usage from intermediate steps.
            
        Returns:
            A prompt string for the fine-tuned model.
        """
        tool_usage_str = json.dumps(tool_usage, indent=2) if tool_usage else "No tools were used"
        
        return f"""
        Convert the following agent response to a Flutter server-driven UI JSON:
        
        AGENT OUTPUT:
        {agent_output}
        
        TOOL USAGE:
        {tool_usage_str}
        
        Generate a Flutter server-driven UI JSON that represents this information in a user-friendly way.
        The JSON should be valid and directly usable by a Flutter application.
        """
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """
        Extract JSON from the model response.
        
        Args:
            response: The response from the fine-tuned model.
            
        Returns:
            A dictionary containing the Flutter UI JSON.
        """
        # Try to extract JSON from the response
        try:
            # First, try to parse the entire response as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            try:
                # Look for JSON between triple backticks
                import re
                json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # Look for JSON between curly braces
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # If we can't extract JSON, return a fallback
                return self._create_fallback_ui(response, "Could not extract valid JSON from model response")
            except Exception as e:
                return self._create_fallback_ui(response, f"Error extracting JSON: {e}")
    
    def _create_fallback_ui(self, content: str, error: str) -> Dict[str, Any]:
        """
        Create a fallback UI when JSON generation fails.
        
        Args:
            content: The content to display.
            error: The error message.
            
        Returns:
            A dictionary containing a simple Flutter UI JSON.
        """
        logger.warning(f"Using fallback UI due to error: {error}")
        
        return {
            "type": "fallback",
            "error": error,
            "content": content,
            "ui": {
                "type": "Column",
                "children": [
                    {
                        "type": "Text",
                        "data": "Error generating UI",
                        "style": {
                            "fontWeight": "bold",
                            "color": "red"
                        }
                    },
                    {
                        "type": "Text",
                        "data": content
                    }
                ]
            }
        }
