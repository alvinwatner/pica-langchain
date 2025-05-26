"""
Pica integration for LangChain.

This package provides tools and utilities for using Pica with LangChain.
It also includes Flutter UI generation capabilities.
"""

from .client import PicaClient
from .tools import GetAvailableActionsTool, GetActionKnowledgeTool, ExecuteTool, PromptToConnectPlatformTool
from .utils import create_pica_tools, create_pica_agent, get_tools_from_client, create_flutter_ui_agent, FlutterUIAgent
from .models import (
    Connection,
    ConnectionDefinition,
    AvailableAction,
    ExecuteParams,
    ActionsResponse,
    ActionKnowledgeResponse,
    ExecuteResponse
)

__all__ = [
    "PicaClient",
    "GetAvailableActionsTool",
    "GetActionKnowledgeTool",
    "ExecuteTool",
    "PromptToConnectPlatformTool",
    "create_pica_tools",
    "create_pica_agent",
    "create_flutter_ui_agent",
    "get_tools_from_client",
    "Connection",
    "ConnectionDefinition",
    "AvailableAction",
    "ExecuteParams",
    "ActionsResponse",
    "ActionKnowledgeResponse",
    "ExecuteResponse"
]