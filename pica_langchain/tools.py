from typing import Dict, Any, Optional, ClassVar
from langchain.tools import BaseTool
from langchain_community.tools import DuckDuckGoSearchResults
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from .serper_utils import create_serper_wrapper
import os
import json
from pydantic import BaseModel, Field

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
        
        return json.dumps(response_dict, default=str)
    
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
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """

        # We'll call _run which already handles removing the knowledge field
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
            is_url_encoded=is_url_encoded
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

GetAvailableActionsTool.args_schema = GetAvailableActionsSchema
GetActionKnowledgeTool.args_schema = GetActionKnowledgeSchema
ExecuteTool.args_schema = ExecuteSchema

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

PromptToConnectPlatformTool.args_schema = PromptToConnectPlatformSchema


class WebSearchTool(BaseTool):
    """Tool that provides web search with fallback mechanisms."""
    
    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = "Search the web for information about events, people, places, or concepts. Use this when you need to find information that might not be in your training data."
    
    ddg_search: Any = Field(default=None, exclude=True)
    serper: Any = Field(default=None, exclude=True)
    
    def __init__(self, serper_api_key: Optional[str] = None, **kwargs):
        """Initialize the fallback web search tool.
        
        Args:
            serper_api_key: Optional Google Serper API key. If provided, Google Serper will be used as a fallback.
        """
        # Initialize with default values for the fields
        kwargs["ddg_search"] = DuckDuckGoSearchResults(output_format="json")
        
        # Set up Google Serper if API key is provided using our utility function
        kwargs["serper"] = create_serper_wrapper(serper_api_key)
        
        super().__init__(**kwargs)
    
    def _run(
        self, 
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to search the web.
        
        Args:
            query: The search query.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the search results.
        """
        logger.info(f"Searching the web for: {query}")
        
        # Try Google Serper first if available (preferred search engine)
        if self.serper:
            try:
                logger.info("Attempting Google Serper search")
                results = self.serper.run(query)
                logger.info("Google Serper search successful")
                return results
            except Exception as e:
                logger.warning(f"Google Serper search failed: {str(e)}")
                serper_error = str(e)
                
                # Fall back to DuckDuckGo
                try:
                    logger.info("Falling back to DuckDuckGo search")
                    results = self.ddg_search.run(query)
                    logger.info("DuckDuckGo search successful")
                    return results
                except Exception as ddg_e:
                    logger.warning(f"DuckDuckGo search failed: {str(ddg_e)}")
                    
                    # Both searches failed
                    error_msg = f"Web search failed. Google Serper error: {serper_error}. DuckDuckGo error: {str(ddg_e)}"
                    return json.dumps({"error": error_msg})
        
        # If no Google Serper available, try DuckDuckGo only
        try:
            logger.info("Attempting DuckDuckGo search")
            results = self.ddg_search.run(query)
            logger.info("DuckDuckGo search successful")
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {str(e)}")
            error_msg = f"Web search failed. DuckDuckGo error: {str(e)}"
            
            return json.dumps({"error": error_msg})
    
    async def _arun(
        self, 
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(query=query)


class WebSearchSchema(BaseModel):
    query: str = Field(description="The search query to look up information on the web")

WebSearchTool.args_schema = WebSearchSchema
