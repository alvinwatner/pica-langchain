from typing import Dict, Any, Optional, ClassVar
from langchain.tools import BaseTool
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
import json
import sys
from pydantic import BaseModel, Field
from openai import OpenAI

from .client import PicaClient
from .models import ExecuteParams, ActionToExecute
from .logger import get_logger
from .platform_rules import get_platform_rules

logger = get_logger()

class GetAvailableActionsTool(BaseTool):
    """Tool for getting available actions for a platform."""
    
    name: ClassVar[str] = "get_available_actions"
    description: ClassVar[str] = "Get available actions for a platform"
    client: PicaClient
    
    def _run(
        self, 
        platform: str, 
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to get available actions.
        
        Args:
            platform: The platform to get actions for.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the available actions.
        """
        logger.info(f"Getting available actions for platform: {platform}")
        response = self.client.get_available_actions(platform)
        logger.debug(f"Got response with {len(response.actions or [])} actions")

        return json.dumps(response.model_dump(), default=str)
    
    async def _arun(
        self, 
        platform: str, 
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(platform=platform)


class GetActionKnowledgeTool(BaseTool):
    """Tool for getting knowledge about a specific action."""
    
    name: ClassVar[str] = "get_action_knowledge"
    description: ClassVar[str] = "Get full action details including knowledge documentation for a specific action"
    client: PicaClient
    
    def _run(
        self, 
        platform: str,
        action_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to get action knowledge.
        
        Args:
            platform: The platform the action belongs to.
            action_id: The ID of the action.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the action knowledge.
        """
        logger.info(f"Getting knowledge for action ID: {action_id} on platform: {platform}")
        response = self.client.get_action_knowledge(platform, action_id)
        
        if response.success:
            logger.debug(f"Successfully retrieved knowledge for action: {response.action.title if response.action else 'unknown'}")
            
            # Get platform-specific rules
            platform_rules = get_platform_rules(platform)
            
            # If we have platform-specific rules, add them to the response
            if platform_rules:                
                # Create a new dictionary from the response model
                response_dict = response.model_dump()
                # Add platform rules to the response
                response_dict["platform_rules"] = platform_rules
                logger.debug(f"Adding platform-specific rules for {platform} with rules {platform_rules}")
                return json.dumps(response_dict, default=str)
        else:
            logger.warning(f"Failed to get knowledge for action ID: {action_id}: {response.message}")
        
        return json.dumps(response.model_dump(), default=str)
    
    async def _arun(
        self, 
        platform: str,
        action_id: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(platform=platform, action_id=action_id)


class ExecuteTool(BaseTool):
    """Tool for executing a specific action using the passthrough API."""
    
    name: ClassVar[str] = "execute"
    description: ClassVar[str] = "Execute a specific action using the passthrough API"
    client: PicaClient
    
    def _run(
        self, 
        platform: str,
        action_id: str,
        action_path: str,
        method: str,
        connection_key: str,
        data: Optional[Dict[str, Any]] = None,
        path_variables: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        is_form_data: bool = False,
        is_url_encoded: bool = False,
        auto_generate_stac_ui: bool = True,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to execute an action.
        
        Args:
            platform: The platform to execute the action on.
            action_id: The ID of the action to execute.
            action_path: The path of the action to execute.
            method: The HTTP method to use.
            connection_key: The connection key to use.
            data: Optional data to send with the request.
            path_variables: Optional variables to replace in the path.
            query_params: Optional query parameters to include in the request.
            headers: Optional headers to include in the request.
            is_form_data: Whether to send the data as form data.
            is_url_encoded: Whether to send the data as url encoded.
            auto_generate_stac_ui: Whether to automatically generate Stac UI for the response.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the execution results.
        """
        logger.info(f"Executing action ID: {action_id} on platform: {platform} with method: {method}")
        
        action = ActionToExecute(_id=action_id, path=action_path)

        params = ExecuteParams(
            platform=platform,
            action=action,
            method=method,
            connection_key=connection_key,
            data=data,
            path_variables=path_variables,
            query_params=query_params,
            headers=headers,
            is_form_data=is_form_data,
            is_url_encoded=is_url_encoded
        )
        
        response = self.client.execute(params)

        if response.success:
            logger.info(f"Successfully executed action: {response.action} on platform: {platform}")
        else:
            logger.warning(f"Failed to execute action: {response.message}")
        
        # Remove knowledge field from response before serializing to JSON
        response_dict = response.model_dump()
        if "knowledge" in response_dict:
            del response_dict["knowledge"]
        
        response_json = json.dumps(response_dict, default=str)
        
        # Automatically generate Stac UI if enabled and the execution was successful
        if auto_generate_stac_ui and response.success:
            try:
                # Find the GenerateStacUITool in the same module
                for attr_name in dir(sys.modules[__name__]):
                    attr = getattr(sys.modules[__name__], attr_name)
                    if isinstance(attr, type) and attr.__name__ == "GenerateStacUITool":
                        GenerateStacUIToolClass = attr
                        break
                else:
                    logger.warning("Could not find GenerateStacUITool class for auto-generation")
                    return response_json
                
                # Create an instance of GenerateStacUITool
                stac_ui_tool = GenerateStacUIToolClass(client=self.client)
                
                # Initialize OpenAI client if not already initialized
                if not hasattr(stac_ui_tool, "openai_client") or stac_ui_tool.openai_client is None:
                    api_key = os.environ.get("OPENAI_API_KEY")
                    if api_key:
                        stac_ui_tool.openai_client = OpenAI(api_key=api_key)
                    else:
                        logger.warning("OPENAI_API_KEY not found in environment variables. Auto-generation of Stac UI will not work.")
                        return response_json
                
                # Generate Stac UI
                logger.info("Automatically generating Stac UI...")
                stac_ui_response = stac_ui_tool._run(
                    execute_response=response_json,
                    stream=False
                )
                
                # Parse the Stac UI response
                stac_ui_data = json.loads(stac_ui_response)
                
                # Add the Stac UI to the original response if successful
                if stac_ui_data.get("success", False):
                    logger.info("Successfully generated Stac UI automatically")
                    
                    # Parse the original response again
                    response_data = json.loads(response_json)
                    
                    # Add the Stac UI to the response
                    response_data["stac_ui"] = stac_ui_data.get("ui")
                    
                    # Return the updated response
                    return json.dumps(response_data, default=str)
                else:
                    logger.warning(f"Failed to generate Stac UI: {stac_ui_data.get('message', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Error auto-generating Stac UI: {e}", exc_info=True)
        
        return response_json
    
    async def _arun(
        self, 
        platform: str,
        action_id: str,
        action_path: str,
        method: str,
        connection_key: str,
        data: Optional[Dict[str, Any]] = None,
        path_variables: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        is_form_data: bool = False,
        is_url_encoded: bool = False,
        auto_generate_stac_ui: bool = True,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(
            platform=platform,
            action_id=action_id,
            action_path=action_path,
            method=method,
            connection_key=connection_key,
            data=data,
            path_variables=path_variables,
            query_params=query_params,
            headers=headers,
            is_form_data=is_form_data,
            is_url_encoded=is_url_encoded,
            auto_generate_stac_ui=auto_generate_stac_ui
        )


class GenerateStacUITool(BaseTool):
    """Tool for generating a Flutter Server Driven UI (Stac) based on the API response from ExecuteTool."""
    
    name: ClassVar[str] = "generate_stac_ui"
    description: ClassVar[str] = "Generate a Flutter Server Driven UI (Stac) based on the API response from ExecuteTool"
    client: PicaClient
    openai_client: Optional[OpenAI] = None
    model_name: str = "ft:gpt-4o-mini-2024-07-18:steve:steve-ai-gui-1-x:BJKVqBV0" 
    max_tokens: int = 2048
    temperature: float = 0.2
    
    def __init__(self, **kwargs):
        """Initialize the tool with OpenAI client."""
        super().__init__(**kwargs)
        # Initialize OpenAI client if API key is available
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        else:
            logger.warning("OPENAI_API_KEY not found in environment variables. GenerateStacUITool will not work.")
    
    def _run(
        self, 
        execute_response: str,
        temperature: Optional[float] = None,
        stream: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to generate a Flutter Server Driven UI.
        
        Args:
            execute_response: The JSON response from ExecuteTool.
            temperature: Optional temperature for the LLM call.
            stream: Whether to stream the response.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the Flutter Server Driven UI in Stac format.
        """
        if not self.openai_client:
            error_msg = "OpenAI client not initialized. Make sure OPENAI_API_KEY is set in environment variables."
            logger.error(error_msg)
            return json.dumps({"success": False, "message": error_msg})
        
        logger.info("Generating Flutter Server Driven UI based on API response")
        
        try:
            # Parse the execute_response if it's a string
            if isinstance(execute_response, str):
                execute_data = json.loads(execute_response)
            else:
                execute_data = execute_response
            
            # Check if the execution was successful
            if not execute_data.get("success", False):
                error_msg = f"Cannot generate UI for failed execution: {execute_data.get('message', 'Unknown error')}"
                logger.error(error_msg)
                return json.dumps({"success": False, "message": error_msg})
            
            # Extract the response data
            response_data = execute_data.get("data", {})
            
            # Create a simple message with just the API response data
            messages = [
                {"role": "user", "content": f"Can you visualize this API response with Stac JSON format \n{json.dumps(response_data, indent=2)}"}
            ]
            
            # Make the OpenAI API call
            kwargs = {
                "model": "ft:gpt-4o-mini-2024-07-18:steve:steve-ai-gui-1-x:BJKVqBV0",
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
                "stream": stream
            }
            
            if stream:
                # Return a streaming response
                return self.openai_client.chat.completions.create(**kwargs)
            else:
                # Return a complete response
                response = self.openai_client.chat.completions.create(**kwargs)
                ui_content = response.choices[0].message.content

                logger.info("Generated Flutter Server Driven UI: ", ui_content)
                
                # Try to parse the response as JSON
                try:
                    # Check if the response is already valid JSON
                    ui_json = json.loads(ui_content)
                    logger.info("Successfully generated Flutter Server Driven UI")
                    return json.dumps({"success": True, "ui": ui_json})
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', ui_content)
                    if json_match:
                        try:
                            ui_json = json.loads(json_match.group(1))
                            logger.info("Successfully extracted JSON from markdown code block")
                            return json.dumps({"success": True, "ui": ui_json})
                        except json.JSONDecodeError:
                            error_msg = "Failed to parse JSON from markdown code block"
                            logger.error(error_msg)
                            return json.dumps({"success": False, "message": error_msg, "raw_content": ui_content})
                    else:
                        error_msg = "Response does not contain valid JSON or markdown code block"
                        logger.error(error_msg)
                        return json.dumps({"success": False, "message": error_msg, "raw_content": ui_content})
        
        except Exception as e:
            logger.error(f"Error generating Flutter Server Driven UI: {e}", exc_info=True)
            return json.dumps({"success": False, "message": str(e)})
    
    async def _arun(
        self, 
        execute_response: str,
        temperature: Optional[float] = None,
        stream: bool = False,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(
            execute_response=execute_response,
            temperature=temperature,
            stream=stream,
            run_manager=run_manager
        )


class GetAvailableActionsSchema(BaseModel):
    platform: str = Field(description="The platform to get available actions for")

class GetActionKnowledgeSchema(BaseModel):
    platform: str = Field(description="The platform the action belongs to")
    action_id: str = Field(description="The ID of the action to get knowledge for")

class ExecuteSchema(BaseModel):
    platform: str = Field(description="The platform to execute the action on")
    action_id: str = Field(description="The ID of the action to execute")
    action_path: str = Field(description="The path of the action to execute")
    method: str = Field(description="The HTTP method to use (GET, POST, PUT, DELETE, etc.)")
    connection_key: str = Field(description="The connection key to use")
    data: Optional[Dict[str, Any]] = Field(None, description="Optional data to send with the request")
    path_variables: Optional[Dict[str, Any]] = Field(None, description="Optional variables to replace in the path")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Optional query parameters to include in the request")
    headers: Optional[Dict[str, Any]] = Field(None, description="Optional headers to include in the request")
    is_form_data: bool = Field(False, description="Whether to send the data as form data")
    is_url_encoded: bool = Field(False, description="Whether to send the data as url encoded")
    auto_generate_stac_ui: bool = Field(True, description="Whether to automatically generate Stac UI for the response")

class GenerateStacUISchema(BaseModel):
    """Schema for the GenerateStacUITool."""
    execute_response: str = Field(description="The JSON response from ExecuteTool")
    temperature: Optional[float] = Field(None, description="Optional temperature for the LLM call")
    stream: bool = Field(False, description="Whether to stream the response")

class PromptToConnectPlatformTool(BaseTool):
    """Tool for prompting the user to connect to a platform they don't currently have access to."""
    
    name: ClassVar[str] = "prompt_to_connect_platform"
    description: ClassVar[str] = "Prompt the user to connect to a platform that they do not currently have access to"
    client: PicaClient
    
    def _run(
        self, 
        platform_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to prompt connection to a platform.
        
        Args:
            platform_name: The platform to connect to.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the platform name.
        """
        logger.info(f"Prompting user to connect to platform: {platform_name}")
        
        response = {
            "success": True,
            "platform": platform_name
        }
        
        return json.dumps(response, default=str)
    
    async def _arun(
        self, 
        platform_name: str, 
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(platform_name=platform_name)


class PromptToConnectPlatformSchema(BaseModel):
    platform_name: str = Field(description="The platform name that the user needs to connect to. Always use the exact platform identifier (text before parentheses), e.g., 'gmail' for 'gmail (Gmail)'.")

GetAvailableActionsTool.args_schema = GetAvailableActionsSchema
GetActionKnowledgeTool.args_schema = GetActionKnowledgeSchema
ExecuteTool.args_schema = ExecuteSchema
PromptToConnectPlatformTool.args_schema = PromptToConnectPlatformSchema
GenerateStacUITool.args_schema = GenerateStacUISchema
