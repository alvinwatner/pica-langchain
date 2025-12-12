"""
Workflow-specific tools for Pica LangChain.

This module provides tools that wrap the standard ExecuteTool with workflow
context for tracking execution progress in Firestore. This enables real-time
visualization of workflow execution on the Flutter canvas.
"""

import asyncio
import json
from typing import Any, ClassVar, Dict, Optional

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from .client import PicaClient
from .logger import get_logger
from .models import ActionToExecute, ExecuteParams

logger = get_logger()


class WorkflowExecuteTool(BaseTool):
    """Tool for executing workflow steps with execution progress tracking.

    This tool wraps the standard ExecuteTool functionality but adds workflow
    context to track execution progress in Firestore. The progress updates
    enable real-time visualization on the Flutter canvas.

    Unlike ExecuteTool which is used by general agents, this tool is
    specifically designed for workflow execution and includes:
    - workflow_id: The workflow being executed
    - total_steps: Total number of steps in the workflow
    - _execution_count: Internal counter tracking current step (increments each call)
    """

    name: ClassVar[str] = "execute"
    description: ClassVar[str] = "Execute a specific action using the passthrough API"
    client: PicaClient

    # Workflow context
    workflow_id: str
    total_steps: int

    # Internal state for tracking execution progress
    # This is not a Pydantic field, but a class attribute that tracks state
    _execution_count: int = 0

    class Config:
        """Pydantic config to allow arbitrary types."""

        arbitrary_types_allowed = True

    def __init__(self, **data):
        """Initialize the tool with execution count reset."""
        super().__init__(**data)
        # Reset execution count for each new tool instance
        object.__setattr__(self, "_execution_count", 0)

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
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute a workflow step with progress tracking.

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
        # Get current step index and increment for next call
        current_step = self._execution_count
        object.__setattr__(self, "_execution_count", current_step + 1)

        action = (
            f"Executing workflow step {current_step + 1}/{self.total_steps}: "
            f"{action_id} on {platform}"
        )
        logger.info(action)

        # Track workflow execution start - status: running
        asyncio.create_task(
            self.client.action_tracking_service.update_workflow_execution(
                workflow_id=self.workflow_id,
                current_step_index=current_step,
                total_steps=self.total_steps,
                step_status="running",
                overall_status="running",
                status_message=f"Executing {action_id} on {platform}",
                platform=platform,
            )
        )

        # Also update the regular action tracking for backward compatibility
        action_human = f"Executing step {current_step + 1} on {platform}"
        asyncio.create_task(
            self.client.action_tracking_service.update_action(action_human, platform)
        )

        # Prepare execution parameters
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
            is_url_encoded=is_url_encoded,
        )

        logger.debug(f"Workflow execute params: {params}")

        # Execute the action
        response = self.client.execute(params)

        if response.success:
            action = (
                f"Successfully executed workflow step {current_step + 1}: "
                f"{response.action} on {platform}"
            )
            logger.info(action)

            # Determine if this is the last step
            is_last_step = current_step == self.total_steps - 1
            overall_status = "completed" if is_last_step else "running"

            # Track workflow execution success
            asyncio.create_task(
                self.client.action_tracking_service.update_workflow_execution(
                    workflow_id=self.workflow_id,
                    current_step_index=current_step,
                    total_steps=self.total_steps,
                    step_status="success",
                    overall_status=overall_status,
                    status_message=f"Successfully executed {action_id}",
                    platform=platform,
                )
            )

            # Update regular action tracking
            action_human = f"Step {current_step + 1} completed successfully"
            asyncio.create_task(
                self.client.action_tracking_service.update_action(action_human, platform)
            )
        else:
            action = f"Failed to execute workflow step {current_step + 1}: {response.message}"
            logger.warning(action)

            # Track workflow execution failure
            asyncio.create_task(
                self.client.action_tracking_service.update_workflow_execution(
                    workflow_id=self.workflow_id,
                    current_step_index=current_step,
                    total_steps=self.total_steps,
                    step_status="failed",
                    overall_status="failed",
                    status_message=f"Failed: {response.message}",
                    platform=platform,
                )
            )

            # Update regular action tracking
            action_human = f"Step {current_step + 1} failed. Retrying..."
            asyncio.create_task(
                self.client.action_tracking_service.update_action(action_human, platform)
            )

        # Remove knowledge field from response before serializing
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
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Async version of the run method."""
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
        )


class WorkflowExecuteSchema(BaseModel):
    """Schema for WorkflowExecuteTool arguments."""

    platform: str = Field(description="The platform to execute the action on")
    action_id: str = Field(description="The ID of the action to execute")
    action_path: str = Field(description="The path of the action to execute")
    method: str = Field(
        description="The HTTP method to use (GET, POST, PUT, DELETE, etc.)"
    )
    connection_key: str = Field(description="The connection key to use")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Optional data to send with the request"
    )
    path_variables: Optional[Dict[str, Any]] = Field(
        None, description="Optional variables to replace in the path"
    )
    query_params: Optional[Dict[str, Any]] = Field(
        None, description="Optional query parameters to include in the request"
    )
    headers: Optional[Dict[str, Any]] = Field(
        None, description="Optional headers to include in the request"
    )
    is_form_data: bool = Field(
        False, description="Whether to send the data as form data"
    )
    is_url_encoded: bool = Field(
        False, description="Whether to send the data as url encoded"
    )


WorkflowExecuteTool.args_schema = WorkflowExecuteSchema
