import requests
import asyncio
from typing import Dict, Any, Optional, ClassVar, List
from langchain.tools import BaseTool
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_sync_playwright_browser

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from .serper_utils import SerperWrapper
from .firecrawl_utils import FirecrawlWrapper
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
        query: Optional[str] = None,
        limit: int = 20,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to get available actions.

        Args:
            platform: The platform to get actions for.
            query: Optional search query to filter actions using vector search.
            limit: Maximum number of results when using search (default: 20).
            run_manager: Callback manager for the tool run.

        Returns:
            JSON string with the available actions.
        """
        logger.info(f"Getting available actions for platform: {platform}")
        if query:
            logger.debug(f"Using search query: {query}")
        response = self.client.get_available_actions(platform, query=query, limit=limit)
        logger.debug(f"Got response with {len(response.actions or [])} actions")

        return json.dumps(response.model_dump(), default=str)
    
    async def _arun(
        self,
        platform: str,
        query: Optional[str] = None,
        limit: int = 20,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(platform=platform, query=query, limit=limit)


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
        action = f"Getting knowledge for action ID: {action_id} on platform: {platform}"        
        logger.info(action)
        action_human = f"Getting knowledge for the associated action ID on {platform} platform"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform))

        response = self.client.get_action_knowledge(platform, action_id)
        
        if response.success:
            action = f"Successfully retrieved knowledge with action: {response.action.title if response.action else 'unknown'}"
            logger.debug(action)
            asyncio.create_task(self.client.action_tracking_service.update_action(action, platform))
            
            # Get platform-specific rules
            platform_rules = get_platform_rules(platform)
            
            # If we have platform-specific rules, add them to the response
            if platform_rules:                
                # Create a new dictionary from the response model
                response_dict = response.model_dump()
                # Add platform rules to the response
                response_dict["platform_rules"] = platform_rules
                action = f"Added platform-specific rules for {platform}"
                logger.debug(action)
                return json.dumps(response_dict, default=str)
        else:
            action = f"Failed to get knowledge for action ID: {action_id}: {response.message}"            
            logger.warning(action)
            action_human = f"Failed to get knowledge for the associated action ID on {platform} platform"
            asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform))        
        
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
        action = f"Executing action ID: {action_id} on platform: {platform} with method: {method}"
        logger.info(action)

        # Track action start
        action_human = f"Executing action ID on {platform} platform with {method} method"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform))
        
        action = f"Preparing execution parameters for {platform} action"
        logger.debug(action)
        asyncio.create_task(self.client.action_tracking_service.update_action(action, platform))

        action_to_execute = ActionToExecute(_id=action_id, path=action_path)

        params = ExecuteParams(
            platform=platform,
            action=action_to_execute,
            method=method,
            connection_key=connection_key,
            data=data,
            path_variables=path_variables,
            query_params=query_params,
            headers=headers,
            is_form_data=is_form_data,
            is_url_encoded=is_url_encoded
        )

        action = f"Sending {method} request to {platform} API"
        logger.debug(action)
        asyncio.create_task(self.client.action_tracking_service.update_action(action, platform))
                        
        response = self.client.execute(params)

        if response.success:
            action = f"Successfully executed action: {response.action} on platform: {platform}"
            logger.info(action)
            action_human = f"Successfully executed action on {platform} platform"
            asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform))
        else:
            action = f"Failed to execute action: {response.message}"
            logger.warning(action)
            action_human = "Failed to execute action on {} platform.".format(platform)
            action_human += "\nHold on this is normal, we are trying with different parameters"
            asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform))
        
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
    query: Optional[str] = Field(None, description="Optional search query to filter actions using vector search. Pass a descriptive intent phrase WITHOUT the platform name. For example, if the platform is 'gmail' and the user's query is 'fetch my 5 latest emails from Gmail', then the query should be 'fetch my 5 latest emails'.")
    limit: int = Field(20, description="Maximum number of results to return when using search (default: 20)")

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
        action = f"Prompting user to connect to platform: {platform_name}"
        logger.info(action)
        action_human = f"Please connect to {platform_name} platform"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform_name))
        
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


class RedirectToAppTool(BaseTool):
    """Tool for redirecting the user to a specific app within the platform."""
    
    name: ClassVar[str] = "redirect_to_app"
    description: ClassVar[str] = "Redirect the user to a specific app within the platform with a message and optional metadata"
    client: PicaClient
    
    def _run(
        self, 
        app: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to redirect to a specific app.
        
        Args:
            app: The app to redirect to (e.g., 'vibe_studio').
            message: The message to display to the user before redirecting.
            metadata: Optional metadata to include with the redirect (e.g., query parameters).
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the redirect information.
        """
        action = f"Redirecting user to app: {app} with message: {message}"
        logger.info(action)
        action_human = f"Redirecting to {app}"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, app))
        
        response = {
            "success": True,
            "app": app,
            "message": message
        }
        
        if metadata:
            response["metadata"] = metadata
        
        return json.dumps(response, default=str)
    
    async def _arun(
        self, 
        app: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(app=app, message=message, metadata=metadata)


class RedirectToAppSchema(BaseModel):
    app: str = Field(description="The app to redirect to (e.g., 'vibe_studio', 'email', 'tasks'). Use the exact app identifier.")
    message: str = Field(description="The message to display to the user before redirecting. This should explain why the redirection is happening.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata to include with the redirect, such as query parameters or context information.")


RedirectToAppTool.args_schema = RedirectToAppSchema


class ReinitiateConnectionTool(BaseTool):
    """Tool for reinitiating a connection to a platform by deleting the existing connection and prompting for reconnection."""
    
    name: ClassVar[str] = "reinitiate_connection"
    description: ClassVar[str] = "Reinitiate a connection to a platform by deleting the existing connection and prompting the user to reconnect. Use this when a connection is having issues and needs to be reset."    
    client: PicaClient
    
    def _delete_connection(self, connection_id: str) -> dict:
        """
        Delete a connection using the Pica API.
        
        Args:
            connection_id: The connection ID to delete.
            
        Returns:
            API response as dictionary.
        """
        url = f"{self.client.base_url}/v1/vault/connections/{connection_id}"
        
        headers = {
            "Content-Type": "application/json",
            "x-pica-secret": self.client.secret
        }
        
        try:
            logger.info(f"Deleting connection: {connection_id}")
            
            response = requests.delete(url, headers=headers, timeout=35)
            response.raise_for_status()
            
            logger.info(f"Successfully deleted connection: {connection_id}")
            return {
                "success": True, 
                "message": "Connection deleted successfully",
                "status_code": response.status_code
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Connection {connection_id} not found (404)")
                return {
                    "success": False, 
                    "error": "Connection not found or already deleted",
                    "status_code": 404
                }
            elif e.response.status_code == 403:
                logger.error(f"Forbidden access to connection {connection_id} (403)")
                return {
                    "success": False, 
                    "error": "Access denied. Check your permissions or API secret.",
                    "status_code": 403
                }
            else:
                logger.error(f"HTTP error deleting connection {connection_id}: {str(e)}")
                return {
                    "success": False, 
                    "error": f"HTTP error: {e.response.status_code} - {str(e)}",
                    "status_code": e.response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout deleting connection {connection_id}")
            return {
                "success": False, 
                "error": "Request timeout. Please try again.",
                "status_code": None
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error deleting connection {connection_id}: {str(e)}")
            return {
                "success": False, 
                "error": f"Request failed: {str(e)}",
                "status_code": None
            }
            
        except Exception as e:
            logger.error(f"Unexpected error deleting connection {connection_id}: {str(e)}")
            return {
                "success": False, 
                "error": f"Unexpected error: {str(e)}",
                "status_code": None
            }
    
    def _run(
        self, 
        platform_name: str,
        connection_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to reinitiate connection to a platform.
        
        Args:
            platform_name: The platform to reinitiate connection for.
            connection_id: The connection ID to delete (format: conn::xxx::yyy).
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the result.
        """
        logger.info(f"Reinitiating connection for platform: {platform_name}, connection ID: {connection_id}")
        
        # Validate connection ID format
        if not connection_id.startswith("conn::"):
            error_response = {
                "success": False,
                "platform": platform_name,
                "connection_id": connection_id,
                "error": "Invalid connection ID format. Expected format: conn::xxx::yyy",
                "action": "check_connection_id"
            }
            return json.dumps(error_response, default=str)
        
        # Delete the existing connection
        deletion_result = self._delete_connection(connection_id)
        
        if not deletion_result.get("success"):
            error_response = {
                "success": False,
                "platform": platform_name,
                "connection_id": connection_id,
                "error": deletion_result.get("error"),
                "status_code": deletion_result.get("status_code"),
                "action": "deletion_failed"
            }
            return json.dumps(error_response, default=str)
        
        # Return success response prompting for reconnection (similar to PromptToConnectPlatformTool)
        success_response = {
            "success": True,
            "platform": platform_name,
            "connection_id": connection_id,
            "action": "reconnect_required",
            "message": f"Successfully removed existing connection for {platform_name}. Please reconnect to continue using this platform."
        }
        
        logger.info(f"Successfully reinitiated connection process for {platform_name}")
        action_human = f"Please reconnect to {platform_name} platform"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, platform_name))                
        return json.dumps(success_response, default=str)
    
    async def _arun(
        self, 
        platform_name: str,
        connection_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(platform_name=platform_name, connection_id=connection_id)


class ReinitiateConnectionSchema(BaseModel):
    platform_name: str = Field(
        description="The platform name to reinitiate connection for. Use the exact platform identifier (e.g., 'gmail', 'google-drive', 'github')."
    )
    connection_id: str = Field(
        description="The connection ID to delete, in format conn::xxx::yyy. Extract this from the system prompt's connection list for the specified platform."
    )


ReinitiateConnectionTool.args_schema = ReinitiateConnectionSchema

class WebSearchTool(BaseTool):
    """Tool that provides web search with multiple fallback mechanisms."""
    
    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = "Search the web for information about events, people, places, or concepts. Use this when you need to find information that might not be in your training data."
    client: PicaClient
    
    ddg_search: Any = Field(default=None, exclude=True)
    serper: Any = Field(default=None, exclude=True)
    firecrawl: Any = Field(default=None, exclude=True)
    
    def __init__(self, serper_api_keys: Optional[List[str]] = None, firecrawl_api_keys: Optional[List[str]] = None, **kwargs):
        """Initialize the fallback web search tool.
        
        Args:
            serper_api_keys: Optional list of Google Serper API keys. Will be tried in order.
            firecrawl_api_keys: Optional list of Firecrawl API keys. Will be tried in order if Google Serper fails.
        """
        # Initialize with default values for the fields
        kwargs["ddg_search"] = DuckDuckGoSearchResults(output_format="json")
        
        # Set up Google Serper if API keys are provided
        if serper_api_keys:
            if isinstance(serper_api_keys, str):
                serper_api_keys = [serper_api_keys]
            try:
                kwargs["serper"] = SerperWrapper(serper_api_keys) if serper_api_keys else None
            except Exception as e:
                logger.warning(f"Failed to initialize SerperWrapper: {str(e)}")
                kwargs["serper"] = None
        else:
            kwargs["serper"] = None
        
        # Set up Firecrawl if API keys are provided
        if firecrawl_api_keys:
            try:
                kwargs["firecrawl"] = FirecrawlWrapper(firecrawl_api_keys) if firecrawl_api_keys else None
            except Exception as e:
                logger.warning(f"Failed to initialize FirecrawlWrapper: {str(e)}")
                kwargs["firecrawl"] = None
        else:
            kwargs["firecrawl"] = None
        
        super().__init__(**kwargs)
    
    def _run(
        self, 
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to search the web with multiple fallbacks.
        
        Fallback order:
        1. Google Serper (with multiple API keys)
        2. Firecrawl (with multiple API keys)
        3. DuckDuckGo
        
        Args:
            query: The search query.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the search results.
        """
        action =f'Searching the web using query : "{query}"'
        logger.info(action)
        asyncio.create_task(self.client.action_tracking_service.update_action(action, "web"))                
        errors = {}
        
        # Try Google Serper first if available (preferred search engine)
        if self.serper:
            try:
                action = f"Attempting search using Google Serper tool"
                logger.info(action)
                asyncio.create_task(self.client.action_tracking_service.update_action(action, "Google Serper"))
                results = self.serper.run(query)
                logger.info("Google Serper search successful")
                return results
            except Exception as e:
                action = f"All Google Serper API keys failed: {str(e)}"
                logger.warning(action)
                action_human = "Failed to search using Google Serper"
                asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "Google Serper"))
                errors["serper"] = str(e)
        
        # If Google Serper failed, try Firecrawl
        if self.firecrawl:
            try:
                action = f"Second attempt, searching using Firecrawl tool"
                logger.info(action)
                asyncio.create_task(self.client.action_tracking_service.update_action(action, "Firecrawl"))
                results = self.firecrawl.run(query)
                logger.info("Firecrawl search successful")
                return results
            except Exception as e:
                action = f"All Firecrawl API keys failed: {str(e)}"
                logger.warning(action)
                action_human = "Failed to search using Firecrawl"
                asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "Firecrawl"))
                errors["firecrawl"] = str(e)
        
        # If both Google Serper and Firecrawl failed, try DuckDuckGo
        try:
            action = f"Third attempt, searching using DuckDuckGo tool"
            logger.info(action)
            asyncio.create_task(self.client.action_tracking_service.update_action(action, "DuckDuckGo"))
            results = self.ddg_search.run(query)
            logger.info("DuckDuckGo search successful")
            return results
        except Exception as e:
            action = f"DuckDuckGo search failed: {str(e)}"
            logger.warning(action)
            action_human = "Failed to search using DuckDuckGo"
            asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "DuckDuckGo"))
            errors["duckduckgo"] = str(e)
            
            # All search engines failed
            error_details = ", ".join([f"{k}: {v}" for k, v in errors.items()])
            error_msg = f"Web search failed. Errors: {error_details}"
            
            return json.dumps({"error": error_msg})
    
    async def _arun(
        self, 
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        """
        return self._run(query=query)


class WebSearchSchema(BaseModel):
    query: str = Field(description="The search query to look up information on the web")

WebSearchTool.args_schema = WebSearchSchema




class GoogleCustomSearchTool(BaseTool):
    """Tool that uses Google Custom Search API as a last resort when other search methods fail."""
    
    name: str = "google_custom_search"
    description: str = "Search the web using Google Custom Search API when other search methods fail. This is a last resort search tool that provides comprehensive results."
    client: PicaClient
    
    api_keys: List[str] = Field(default=None, exclude=True)
    cx: str = Field(default=None, exclude=True)
    base_url: str = Field(default="https://www.googleapis.com/customsearch/v1", exclude=True)
    timeout: int = Field(default=30, exclude=True)
    max_results: int = Field(default=10, exclude=True)
    
    def __init__(
        self, 
        api_keys: Optional[List[str]] = None,
        cx: str = "405e625c354154a3b",
        base_url: str = "https://www.googleapis.com/customsearch/v1",
        timeout: int = 30,
        max_results: int = 10,
        **kwargs
    ):
        """Initialize the Google Custom Search tool.
        
        Args:
            api_keys: List of Google Custom Search API keys. Will be tried in order.
            cx: The custom search engine ID.
            base_url: Base URL for the Google Custom Search API.
            timeout: Timeout in seconds for API requests.
            max_results: Maximum number of search results to return.
        """
        # Ensure api_keys is a list
        if isinstance(api_keys, str):
            api_keys = [api_keys]
        
        kwargs["api_keys"] = api_keys
        kwargs["cx"] = cx
        kwargs["base_url"] = base_url
        kwargs["timeout"] = timeout
        kwargs["max_results"] = max_results
        
        super().__init__(**kwargs)
    
    def _make_search_request(self, query: str, api_key: str) -> dict:
        """Make a search request to Google Custom Search API.
        
        Args:
            query: The search query.
            api_key: The API key to use.
            
        Returns:
            JSON response from the API.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        params = {
            "key": api_key,
            "cx": self.cx,
            "q": query,
            "num": self.max_results
        }
        
        logger.info(f"Making Google Custom Search request for query: {query}")
        response = requests.get(
            self.base_url,
            params=params,
            timeout=self.timeout
        )
        
        # Check for HTTP errors
        response.raise_for_status()
        
        # Check for API errors
        data = response.json()
        if "error" in data:
            error_message = data["error"].get("message", "Unknown API error")
            raise requests.RequestException(f"Google Custom Search API error: {error_message}")
        
        return data
    
    def _format_search_results(self, api_response: dict) -> str:
        """Format the Google Custom Search API response for LLM consumption.
        
        Args:
            api_response: Raw response from Google Custom Search API.
            
        Returns:
            JSON string with formatted search results.
        """
        try:
            # Extract search information
            search_info = api_response.get("searchInformation", {})
            total_results = search_info.get("totalResults", "0")
            search_time = search_info.get("formattedSearchTime", "0")
            
            # Extract and format search results
            items = api_response.get("items", [])
            results = []
            
            for item in items:
                result = {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "displayLink": item.get("displayLink", ""),
                    "formattedUrl": item.get("formattedUrl", "")
                }
                
                # Add additional metadata if available
                pagemap = item.get("pagemap", {})
                if pagemap:
                    # Extract useful metadata
                    metatags = pagemap.get("metatags", [])
                    if metatags and isinstance(metatags, list) and len(metatags) > 0:
                        meta = metatags[0]
                        result["metadata"] = {
                            "og_title": meta.get("og:title", ""),
                            "og_description": meta.get("og:description", ""),
                            "og_image": meta.get("og:image", "")
                        }
                
                results.append(result)
            
            # Format the final response
            formatted_response = {
                "results": results,
                "search_metadata": {
                    "total_results": total_results,
                    "search_time": search_time,
                    "results_count": len(results)
                },
                "source": "google_custom_search",
                "query": api_response.get("queries", {}).get("request", [{}])[0].get("searchTerms", "")
            }
            
            logger.info(f"Successfully formatted {len(results)} search results")
            return json.dumps(formatted_response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Error formatting search results: {str(e)}")
            # Return a basic format if detailed formatting fails
            items = api_response.get("items", [])
            basic_results = []
            
            for item in items:
                basic_results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
            
            return json.dumps({
                "results": basic_results,
                "source": "google_custom_search",
                "error": f"Formatting error: {str(e)}"
            })
    
    def _run(
        self, 
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Run the tool to search using Google Custom Search API.
        
        Args:
            query: The search query.
            run_manager: Callback manager for the tool run.
            
        Returns:
            JSON string with the search results.
        """
        action = f"Starting Google Custom Search for query: {query}"
        logger.info(action)
        asyncio.create_task(self.client.action_tracking_service.update_action(action, "Google Search API"))
        
        if not self.api_keys:
            error_msg = "No Google Custom Search API keys configured"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # Try each API key in order
        for i, api_key in enumerate(self.api_keys):
            try:
                logger.info(f"Trying API key {i + 1}/{len(self.api_keys)}")
                
                # Make the search request
                api_response = self._make_search_request(query, api_key)
                
                # Format and return the results
                formatted_results = self._format_search_results(api_response)
                                
                action = f"Google Custom Search successful with API key {i + 1}"
                logger.info(action)
                action_human = f"Google Search successful! Processing the data..."
                asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "Google Search API"))
                return formatted_results
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout with API key {i + 1}")
                if i == len(self.api_keys) - 1:  # Last key
                    return json.dumps({"error": "All API keys timed out"})
                continue
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.warning(f"API key {i + 1} quota exceeded or invalid: {str(e)}")
                    if i == len(self.api_keys) - 1:  # Last key
                        return json.dumps({"error": "All API keys exhausted or invalid"})
                    continue
                else:
                    logger.warning(f"HTTP error with API key {i + 1}: {str(e)}")
                    if i == len(self.api_keys) - 1:  # Last key
                        return json.dumps({"error": f"HTTP error: {str(e)}"})
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed with API key {i + 1}: {str(e)}")
                if i == len(self.api_keys) - 1:  # Last key
                    return json.dumps({"error": f"Request failed: {str(e)}"})
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error with API key {i + 1}: {str(e)}")
                if i == len(self.api_keys) - 1:  # Last key
                    return json.dumps({"error": f"Unexpected error: {str(e)}"})
                continue
        
        # This should never be reached, but just in case
        return json.dumps({"error": "All search attempts failed"})
    
    async def _arun(
        self, 
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """
        Async version of the run method.
        
        Note: This implementation uses the synchronous requests library.
        For a production async implementation, consider using aiohttp.
        """
        return self._run(query=query)


class GoogleCustomSearchSchema(BaseModel):
    query: str = Field(description="The search query to look up information using Google Custom Search API")


GoogleCustomSearchTool.args_schema = GoogleCustomSearchSchema