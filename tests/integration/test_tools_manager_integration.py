"""
Tools Manager integration tests.

These tests verify that the KonfluxDevLakeToolsManager works correctly
with real database operations and proper tool routing.
"""

import pytest
import json
from toon_format import decode as toon_decode

from tools.tools_manager import KonfluxDevLakeToolsManager
from utils.db import KonfluxDevLakeConnection


@pytest.mark.integration
@pytest.mark.asyncio
class TestToolsManagerIntegration:
    """Integration tests for KonfluxDevLakeToolsManager."""

    async def test_list_tools_returns_all_tools(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test that list_tools returns all available tools."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        tools = await tools_manager.list_tools()

        assert len(tools) > 0

        tool_names = [tool.name for tool in tools]

        assert "connect_database" in tool_names
        assert "list_databases" in tool_names
        assert "list_tables" in tool_names
        assert "get_table_schema" in tool_names

        assert "get_incidents" in tool_names

        assert "get_deployments" in tool_names
        assert "get_deployment_frequency" in tool_names
        assert "analyze_pr_retests" in tool_names

    async def test_call_database_tool(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test calling a database tool through the manager."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("list_databases", {})
        result = json.loads(result_json)

        assert result["success"] is True
        assert "data" in result

    async def test_call_incident_tool(
        self, integration_db_connection: KonfluxDevLakeConnection, clean_database
    ):
        """Test calling an incident tool through the manager."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("get_incidents", {})
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "incidents" in result

    async def test_call_deployment_tool(
        self, integration_db_connection: KonfluxDevLakeConnection, clean_database
    ):
        """Test calling a deployment tool through the manager."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("get_deployments", {})
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "deployments" in result

    async def test_call_deployment_frequency_tool(
        self, integration_db_connection: KonfluxDevLakeConnection, clean_database
    ):
        """Test calling the deployment frequency tool through the manager."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("get_deployment_frequency", {})
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "summary" in result
        assert "dora_level" in result["summary"]

    async def test_call_nonexistent_tool(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test calling a non-existent tool returns proper error."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("nonexistent_tool", {})
        result = json.loads(result_json)

        assert result["success"] is False
        assert "error" in result
        assert "Unknown tool" in result["error"]
        assert "available_tools" in result

    async def test_tool_statistics(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test getting tool statistics."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        stats = tools_manager.get_tool_statistics()

        assert "total_tools" in stats
        assert "modules" in stats
        assert "tools_by_module" in stats
        assert "available_tools" in stats

        assert stats["total_tools"] > 0
        assert stats["modules"] == 4

        assert "DatabaseTools" in stats["tools_by_module"]
        assert "IncidentTools" in stats["tools_by_module"]
        assert "DeploymentTools" in stats["tools_by_module"]
        assert "PRRetestTools" in stats["tools_by_module"]

        assert stats["tools_by_module"]["DatabaseTools"] > 0
        assert stats["tools_by_module"]["IncidentTools"] > 0
        assert stats["tools_by_module"]["DeploymentTools"] > 0
        assert stats["tools_by_module"]["PRRetestTools"] > 0

    async def test_validate_tool_exists(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test validating tool existence."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        assert tools_manager.validate_tool_exists("list_databases") is True
        assert tools_manager.validate_tool_exists("get_incidents") is True
        assert tools_manager.validate_tool_exists("get_deployments") is True
        assert tools_manager.validate_tool_exists("get_deployment_frequency") is True
        assert tools_manager.validate_tool_exists("analyze_pr_retests") is True

        assert tools_manager.validate_tool_exists("nonexistent_tool") is False

    async def test_get_tool_module(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test getting the module for a specific tool."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        db_module = tools_manager.get_tool_module("list_databases")
        incident_module = tools_manager.get_tool_module("get_incidents")
        deployment_module = tools_manager.get_tool_module("get_deployments")
        pr_retest_module = tools_manager.get_tool_module("analyze_pr_retests")

        assert db_module.__class__.__name__ == "DatabaseTools"
        assert incident_module.__class__.__name__ == "IncidentTools"
        assert deployment_module.__class__.__name__ == "DeploymentTools"
        assert pr_retest_module.__class__.__name__ == "PRRetestTools"

    async def test_get_tool_module_nonexistent(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test getting module for non-existent tool raises error."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        with pytest.raises(KeyError) as exc_info:
            tools_manager.get_tool_module("nonexistent_tool")

        assert "not found" in str(exc_info.value)

    async def test_tool_routing_with_arguments(
        self, integration_db_connection: KonfluxDevLakeConnection, clean_database
    ):
        """Test that tool arguments are properly routed to the correct tool."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("get_incidents", {"status": "DONE", "limit": 5})
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["filters"]["status"] == "DONE"
        assert result["filters"]["limit"] == 5

    async def test_multiple_sequential_tool_calls(
        self, integration_db_connection: KonfluxDevLakeConnection, clean_database
    ):
        """Test multiple sequential tool calls work correctly."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result1_json = await tools_manager.call_tool("list_databases", {})
        result1 = json.loads(result1_json)
        assert result1["success"] is True

        result2_json = await tools_manager.call_tool("get_incidents", {})
        result2 = toon_decode(result2_json)
        assert result2["success"] is True

        result3_json = await tools_manager.call_tool("get_deployments", {})
        result3 = toon_decode(result3_json)
        assert result3["success"] is True

    async def test_tool_error_handling(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test that tool errors are properly handled and returned."""
        tools_manager = KonfluxDevLakeToolsManager(integration_db_connection)

        result_json = await tools_manager.call_tool("get_table_schema", {"database": "lake"})
        result = json.loads(result_json)

        assert result["success"] is False
        assert "error" in result
