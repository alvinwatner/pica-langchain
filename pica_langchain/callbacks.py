"""
Custom callback handlers for Pica LangChain integration.
"""

from typing import Dict, Any, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction
import json

from .logger import get_logger

logger = get_logger()

class AutoGenerateStacUIHandler(BaseCallbackHandler):
    """
    Callback handler that automatically invokes the GenerateStacUITool 
    after a successful ExecuteTool response.
    """
    
    def __init__(self, tools):
        """Initialize with the available tools."""
        super().__init__()
        self.tools = tools
        self.execute_tool = None
        self.stac_ui_tool = None
        
        # Find the ExecuteTool and GenerateStacUITool
        for tool in tools:
            if tool.name == "execute":
                self.execute_tool = tool
            elif tool.name == "generate_stac_ui":
                self.stac_ui_tool = tool
        
        if not self.execute_tool:
            logger.warning("ExecuteTool not found in tools list. Auto-generation of Stac UI will not work.")
        if not self.stac_ui_tool:
            logger.warning("GenerateStacUITool not found in tools list. Auto-generation of Stac UI will not work.")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """
        Called when a tool execution ends.
        If the tool was ExecuteTool and it was successful, automatically invoke GenerateStacUITool.
        """
        if not (self.execute_tool and self.stac_ui_tool):
            return
            
        # Get the tool name from kwargs
        tool_name = kwargs.get("name", None)
        
        # Check if the tool is ExecuteTool
        if tool_name == "execute":
            try:
                logger.info(f"ExecuteTool completed. Checking if successful...")
                
                # Parse the output
                if isinstance(output, str):
                    try:
                        output_data = json.loads(output)
                        if output_data.get("success", False):
                            logger.info("ExecuteTool was successful. Automatically generating Stac UI...")
                            
                            # Call the GenerateStacUITool with the ExecuteTool response
                            stac_ui_response = self.stac_ui_tool._run(
                                execute_response=output,
                                stream=False
                            )
                            
                            # Parse the Stac UI response
                            stac_ui_data = json.loads(stac_ui_response)
                            
                            # Add the Stac UI to the original response
                            if stac_ui_data.get("success", False):
                                logger.info("Successfully generated Stac UI automatically")
                                
                                # Append the Stac UI to the original output
                                output_data["stac_ui"] = stac_ui_data.get("ui")
                                
                                # Log the updated output
                                logger.debug(f"Updated output with Stac UI: {json.dumps(output_data)}")
                            else:
                                logger.warning(f"Failed to generate Stac UI: {stac_ui_data.get('message', 'Unknown error')}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing ExecuteTool output as JSON: {e}")
                    except Exception as e:
                        logger.error(f"Error auto-generating Stac UI: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error in on_tool_end for ExecuteTool: {e}", exc_info=True)
