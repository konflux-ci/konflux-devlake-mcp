#!/usr/bin/env python3
"""
Tools Manager for Konflux DevLake MCP Server

Manages all tools using a modular approach with clear separation of concerns
and improved maintainability.
"""

import json
from typing import Any, Dict, List

from mcp.types import Tool

from tools.base.base_tool import BaseTool
from tools.database_tools import DatabaseTools
from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools
from tools.devlake.pr_retest_tools import PRRetestTools
from tools.devlake.pr_cycle_time_tools import PRCycleTimeTools
from tools.devlake.github_actions_tools import GitHubActionsTools
from tools.devlake.pr_stats_tools import PRStatsTools
from tools.devlake.codecov_tools import CodecovTools
from tools.devlake.e2e_test_tools import E2ETestTools
from tools.devlake.historical_trends_tools import HistoricalTrendsTools
from tools.devlake.jira_tools import JiraTools
from tools.devlake.lead_time_tools import LeadTimeTools
from utils.logger import get_logger, log_tool_call


class KonfluxDevLakeToolsManager:
    """
    Tools manager for Konflux DevLake MCP Server.

    This class coordinates all tool modules using a modular approach with
    clear separation of concerns and improved error handling.
    """

    def __init__(self, db_connection):
        """
        Initialize the tools manager.

        Args:
            db_connection: Database connection manager
        """
        self.db_connection = db_connection
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeToolsManager")

        # Initialize tool modules using the base tool interface
        self._tool_modules: List[BaseTool] = [
            DatabaseTools(db_connection),
            IncidentTools(db_connection),
            DeploymentTools(db_connection),
            PRRetestTools(db_connection),
            PRCycleTimeTools(db_connection),
            GitHubActionsTools(db_connection),
            PRStatsTools(db_connection),
            CodecovTools(db_connection),
            E2ETestTools(db_connection),
            HistoricalTrendsTools(db_connection),
            JiraTools(db_connection),
            LeadTimeTools(db_connection),
        ]

        # Create tool name to module mapping for efficient routing
        self._tool_mapping = self._create_tool_mapping()

    def _create_tool_mapping(self) -> Dict[str, BaseTool]:
        """
        Create a mapping of tool names to their respective modules.

        Returns:
            Dictionary mapping tool names to tool modules
        """
        tool_mapping = {}

        for module in self._tool_modules:
            for tool in module.get_tools():
                tool_mapping[tool.name] = module

        self.logger.info(f"Created tool mapping with {len(tool_mapping)} tools")
        return tool_mapping

    async def list_tools(self) -> List[Tool]:
        """
        List all available tools from all modules.

        Returns:
            List of all available Tool objects
        """
        tools = []

        for module in self._tool_modules:
            tools.extend(module.get_tools())

        self.logger.info(f"Returning {len(tools)} tools from {len(self._tool_modules)} modules")
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Call a tool by name, delegating to the appropriate module.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            JSON string with tool execution result
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Find the appropriate module for this tool
            if name not in self._tool_mapping:
                error_result = {
                    "success": False,
                    "error": f"Unknown tool: {name}",
                    "available_tools": list(self._tool_mapping.keys()),
                }
                return json.dumps(error_result, indent=2)

            # Execute the tool using the appropriate module
            module = self._tool_mapping[name]
            result = await module.call_tool(name, arguments)

            return result

        except Exception as e:
            self.logger.error(f"Tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return json.dumps(error_result, indent=2)

    def get_tool_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about available tools.

        Returns:
            Dictionary with tool statistics
        """
        total_tools = len(self._tool_mapping)
        tools_by_module = {}

        for module in self._tool_modules:
            module_name = module.__class__.__name__
            tools_by_module[module_name] = len(module.get_tools())

        return {
            "total_tools": total_tools,
            "modules": len(self._tool_modules),
            "tools_by_module": tools_by_module,
            "available_tools": list(self._tool_mapping.keys()),
        }

    def validate_tool_exists(self, name: str) -> bool:
        """
        Check if a tool exists.

        Args:
            name: Tool name to check

        Returns:
            True if tool exists, False otherwise
        """
        return name in self._tool_mapping

    def get_tool_module(self, name: str) -> BaseTool:
        """
        Get the module that provides a specific tool.

        Args:
            name: Tool name

        Returns:
            Tool module that provides the specified tool

        Raises:
            KeyError: If tool doesn't exist
        """
        if name not in self._tool_mapping:
            raise KeyError(f"Tool '{name}' not found")

        return self._tool_mapping[name]
