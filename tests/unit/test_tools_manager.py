#!/usr/bin/env python3
"""
Unit Tests for Tools Manager

Tests the KonfluxDevLakeToolsManager class functionality including:
- Tool registration and management
- Tool routing and execution
- Error handling and statistics
"""

import pytest
from toon_format import decode as toon_decode

from tools.tools_manager import KonfluxDevLakeToolsManager
from tools.database_tools import DatabaseTools
from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools
from mcp.types import Tool


@pytest.mark.unit
class TestKonfluxDevLakeToolsManager:
    """Test suite for KonfluxDevLakeToolsManager class."""

    @pytest.fixture
    def tools_manager(self, mock_db_connection):
        """Create KonfluxDevLakeToolsManager instance with mock connection."""
        return KonfluxDevLakeToolsManager(mock_db_connection)

    def test_initialization(self, tools_manager, mock_db_connection):
        """Test tools manager initialization."""
        assert tools_manager.db_connection == mock_db_connection
        assert len(tools_manager._tool_modules) == 12

        module_types = [type(module).__name__ for module in tools_manager._tool_modules]
        assert "DatabaseTools" in module_types
        assert "IncidentTools" in module_types
        assert "DeploymentTools" in module_types
        assert "PRRetestTools" in module_types
        assert "PRCycleTimeTools" in module_types
        assert "GitHubActionsTools" in module_types
        assert "PRStatsTools" in module_types
        assert "CodecovTools" in module_types
        assert "E2ETestTools" in module_types
        assert "HistoricalTrendsTools" in module_types
        assert "JiraTools" in module_types
        assert "LeadTimeTools" in module_types

    def test_tool_mapping_creation(self, tools_manager):
        """Test that tool mapping is created correctly."""
        tool_mapping = tools_manager._tool_mapping

        expected_tools = [
            "connect_database",
            "list_databases",
            "list_tables",
            "get_table_schema",
            "get_incidents",
            "get_deployments",
            "analyze_pr_retests",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_mapping
            assert hasattr(tool_mapping[tool_name], "call_tool")

    @pytest.mark.asyncio
    async def test_list_tools(self, tools_manager):
        """Test listing all available tools."""
        tools = await tools_manager.list_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 7

        for tool in tools:
            assert isinstance(tool, Tool)
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

    @pytest.mark.asyncio
    async def test_call_tool_success(self, tools_manager, mock_db_connection):
        """Test successful tool execution."""
        mock_db_connection.connect.return_value = {
            "success": True,
            "message": "Database connected successfully",
        }

        result = await tools_manager.call_tool("connect_database", {})
        result_data = toon_decode(result)

        assert result_data["success"] is True
        assert "Database connected successfully" in result_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, tools_manager):
        """Test calling an unknown tool."""
        result = await tools_manager.call_tool("unknown_tool", {})
        result_data = toon_decode(result)

        assert result_data["success"] is False
        assert "Unknown tool: unknown_tool" in result_data["error"]
        assert "available_tools" in result_data

    @pytest.mark.asyncio
    async def test_call_tool_with_arguments(self, tools_manager, mock_db_connection):
        """Test calling a tool with arguments."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SHOW TABLES FROM `test_db`",
            "row_count": 2,
            "data": [{"Tables_in_test_db": "table1"}, {"Tables_in_test_db": "table2"}],
        }

        result = await tools_manager.call_tool("list_tables", {"database": "test_db"})
        result_data = toon_decode(result)

        assert result_data["success"] is True
        assert result_data["row_count"] == 2
        mock_db_connection.execute_query.assert_called_once_with("SHOW TABLES FROM `test_db`")

    @pytest.mark.asyncio
    async def test_call_tool_exception_handling(self, tools_manager, mock_db_connection):
        """Test exception handling in tool calls."""
        mock_db_connection.connect.side_effect = Exception("Connection failed")

        result = await tools_manager.call_tool("connect_database", {})
        result_data = toon_decode(result)

        assert result_data["success"] is False
        assert "Connection failed" in result_data["error"]

    def test_get_tool_statistics(self, tools_manager):
        """Test tool statistics retrieval."""
        stats = tools_manager.get_tool_statistics()

        assert "total_tools" in stats
        assert "modules" in stats
        assert "tools_by_module" in stats
        assert "available_tools" in stats

        assert stats["modules"] == 12
        assert stats["total_tools"] >= 17

        tools_by_module = stats["tools_by_module"]
        assert "DatabaseTools" in tools_by_module
        assert "IncidentTools" in tools_by_module
        assert "DeploymentTools" in tools_by_module
        assert "PRRetestTools" in tools_by_module
        assert "LeadTimeTools" in tools_by_module

        available_tools = stats["available_tools"]
        assert "connect_database" in available_tools
        assert "get_incidents" in available_tools
        assert "get_deployments" in available_tools

    def test_validate_tool_exists(self, tools_manager):
        """Test tool existence validation."""
        assert tools_manager.validate_tool_exists("connect_database") is True
        assert tools_manager.validate_tool_exists("list_databases") is True
        assert tools_manager.validate_tool_exists("get_incidents") is True
        assert tools_manager.validate_tool_exists("get_deployments") is True
        assert tools_manager.validate_tool_exists("nonexistent_tool") is False

    def test_get_tool_module(self, tools_manager):
        """Test getting the module for a specific tool."""
        db_module = tools_manager.get_tool_module("connect_database")
        assert isinstance(db_module, DatabaseTools)

        list_db_module = tools_manager.get_tool_module("list_databases")
        assert isinstance(list_db_module, DatabaseTools)

        incident_module = tools_manager.get_tool_module("get_incidents")
        assert isinstance(incident_module, IncidentTools)

        deployment_module = tools_manager.get_tool_module("get_deployments")
        assert isinstance(deployment_module, DeploymentTools)

    def test_get_tool_module_nonexistent(self, tools_manager):
        """Test getting module for non-existent tool."""
        with pytest.raises(KeyError) as exc_info:
            tools_manager.get_tool_module("nonexistent_tool")

        assert "Tool 'nonexistent_tool' not found" in str(exc_info.value)

    def test_tool_module_isolation(self, tools_manager):
        """Test that tool modules are properly isolated."""
        db_module1 = tools_manager.get_tool_module("connect_database")
        db_module2 = tools_manager.get_tool_module("list_databases")
        incident_module = tools_manager.get_tool_module("get_incidents")

        assert db_module1 is db_module2

        assert db_module1 is not incident_module

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, tools_manager, mock_db_connection):
        """Test handling of concurrent tool calls."""
        import asyncio

        mock_db_connection.connect.return_value = {"success": True, "message": "Connected"}
        mock_db_connection.execute_query.return_value = {"success": True, "data": []}

        tasks = [
            tools_manager.call_tool("connect_database", {}),
            tools_manager.call_tool("list_databases", {}),
            tools_manager.call_tool("get_incidents", {"project_name": "Test Project"}),
            tools_manager.call_tool("get_deployments", {}),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 4
        for result in results:
            result_data = toon_decode(result)
            assert result_data["success"] is True

    def test_tool_mapping_completeness(self, tools_manager):
        """Test that all tools from modules are in the mapping."""
        all_module_tools = []
        for module in tools_manager._tool_modules:
            module_tools = module.get_tools()
            all_module_tools.extend([tool.name for tool in module_tools])

        mapping_tools = list(tools_manager._tool_mapping.keys())

        assert len(all_module_tools) == len(mapping_tools)
        for tool_name in all_module_tools:
            assert tool_name in mapping_tools

    def test_tool_manager_logging(self, tools_manager):
        """Test that tools manager has proper logging setup."""
        assert hasattr(tools_manager, "logger")
        assert tools_manager.logger.name.endswith("KonfluxDevLakeToolsManager")

    @pytest.mark.asyncio
    async def test_tool_call_parameter_forwarding(self, tools_manager, mock_db_connection):
        """Test that tool parameters are properly forwarded."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "DESCRIBE `test_db`.`test_table`",
            "data": [],
        }

        await tools_manager.call_tool(
            "get_table_schema", {"database": "test_db", "table": "test_table"}
        )

        mock_db_connection.execute_query.assert_called_once_with("DESCRIBE `test_db`.`test_table`")

    def test_tool_manager_memory_efficiency(self, tools_manager):
        """Test that tool manager doesn't create duplicate tool instances."""
        module1 = tools_manager.get_tool_module("connect_database")
        module2 = tools_manager.get_tool_module("list_databases")
        module3 = tools_manager.get_tool_module("list_tables")

        assert module1 is module2 is module3

        assert len(tools_manager._tool_modules) == 12
