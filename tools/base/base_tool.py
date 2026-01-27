#!/usr/bin/env python3
"""
Base Tool Interface

This module defines the base tool interface that all tool implementations
must implement for consistency and maintainability.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from mcp.types import Tool


class BaseTool(ABC):
    """
    Base tool interface for MCP server tools.

    This abstract class defines the interface that all tool implementations
    must implement, providing a consistent way to handle tool execution
    and management.
    """

    def __init__(self, db_connection):
        """
        Initialize the base tool.

        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection

    @abstractmethod
    def get_tools(self) -> List[Tool]:
        """
        Get all tools provided by this implementation.

        Returns:
            List of Tool objects
        """
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON string with tool execution result
        """
        pass

    def get_tool_names(self) -> List[str]:
        """
        Get list of tool names provided by this implementation.

        Returns:
            List of tool names
        """
        return [tool.name for tool in self.get_tools()]

    def validate_tool_exists(self, name: str) -> bool:
        """
        Check if a tool exists in this implementation.

        Args:
            name: Tool name to check

        Returns:
            True if tool exists, False otherwise
        """
        return name in self.get_tool_names()
