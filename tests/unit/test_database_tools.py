#!/usr/bin/env python3
"""
Unit Tests for Database Tools

Tests the DatabaseTools class functionality including:
- Tool registration and listing
- Database connectivity testing
- Schema inspection
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

from tools.database_tools import DatabaseTools
from mcp.types import Tool


@pytest.mark.unit
class TestDatabaseTools:
    """Test suite for DatabaseTools class."""

    @pytest.fixture
    def database_tools(self, mock_db_connection):
        """Create DatabaseTools instance with mock connection."""
        return DatabaseTools(mock_db_connection)

    def test_get_tools_returns_correct_tools(self, database_tools):
        """Test that get_tools returns the expected tool definitions."""
        tools = database_tools.get_tools()

        assert len(tools) == 5
        assert all(isinstance(tool, Tool) for tool in tools)

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "connect_database",
            "list_databases",
            "list_tables",
            "get_table_schema",
            "execute_query",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    def test_get_tool_names(self, database_tools):
        """Test get_tool_names method."""
        tool_names = database_tools.get_tool_names()

        assert "connect_database" in tool_names
        assert "list_databases" in tool_names
        assert "list_tables" in tool_names
        assert "get_table_schema" in tool_names
        assert "execute_query" in tool_names

    def test_validate_tool_exists(self, database_tools):
        """Test tool existence validation."""
        assert database_tools.validate_tool_exists("connect_database") is True
        assert database_tools.validate_tool_exists("list_databases") is True
        assert database_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_connect_database_tool_success(self, database_tools, mock_db_connection):
        """Test successful database connection."""
        result_toon = await database_tools.call_tool("connect_database", {})
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert "Database connected successfully" in result["message"]
        assert "version" in result
        assert "connection_info" in result

        mock_db_connection.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_database_tool_failure(self, database_tools, mock_db_connection):
        """Test database connection failure."""
        mock_db_connection.connect.return_value = {"success": False, "error": "Connection failed"}

        result_toon = await database_tools.call_tool("connect_database", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_list_databases_tool(self, database_tools, mock_db_connection):
        """Test list databases functionality."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SHOW DATABASES",
            "row_count": 3,
            "data": [
                {"Database": "information_schema"},
                {"Database": "lake"},
                {"Database": "test_db"},
            ],
        }

        result_toon = await database_tools.call_tool("list_databases", {})
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert result["row_count"] == 3
        assert len(result["data"]) == 3

        mock_db_connection.execute_query.assert_called_once_with("SHOW DATABASES")

    @pytest.mark.asyncio
    async def test_list_tables_tool_success(self, database_tools, mock_db_connection):
        """Test successful table listing."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SHOW TABLES FROM `lake`",
            "row_count": 4,
            "data": [
                {"Tables_in_lake": "incidents"},
                {"Tables_in_lake": "cicd_deployments"},
                {"Tables_in_lake": "cicd_deployment_commits"},
                {"Tables_in_lake": "project_mapping"},
            ],
        }

        result_toon = await database_tools.call_tool("list_tables", {"database": "lake"})
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert result["row_count"] == 4

        mock_db_connection.execute_query.assert_called_once_with("SHOW TABLES FROM `lake`")

    @pytest.mark.asyncio
    async def test_list_tables_tool_missing_database(self, database_tools):
        """Test list tables with missing database parameter."""
        result_toon = await database_tools.call_tool("list_tables", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Database name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_table_schema_tool_success(
        self, database_tools, mock_db_connection, sample_database_schema
    ):
        """Test successful table schema retrieval."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "DESCRIBE `lake`.`incidents`",
            "row_count": 5,
            "data": sample_database_schema,
        }

        result_toon = await database_tools.call_tool(
            "get_table_schema", {"database": "lake", "table": "incidents"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert result["row_count"] == 5
        assert len(result["data"]) == 5

        field_names = [field["Field"] for field in result["data"]]
        assert "id" in field_names
        assert "incident_key" in field_names
        assert "title" in field_names

        mock_db_connection.execute_query.assert_called_once_with("DESCRIBE `lake`.`incidents`")

    @pytest.mark.asyncio
    async def test_get_table_schema_tool_missing_parameters(self, database_tools):
        """Test table schema with missing parameters."""
        result_toon = await database_tools.call_tool("get_table_schema", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Database and table names are required" in result["error"]

        result_toon = await database_tools.call_tool("get_table_schema", {"database": "lake"})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Database and table names are required" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, database_tools):
        """Test calling an unknown tool."""
        result_toon = await database_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Unknown database tool: unknown_tool" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_call_exception_handling(self, database_tools, mock_db_connection):
        """Test exception handling in tool calls."""
        mock_db_connection.execute_query.side_effect = Exception("Database error")

        result_toon = await database_tools.call_tool("list_databases", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Database error" in result["error"]

    def test_tool_input_schemas_are_valid(self, database_tools):
        """Test that all tools have valid input schemas."""
        tools = database_tools.get_tools()

        for tool in tools:
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema
            assert "required" in tool.inputSchema

            for required_param in tool.inputSchema["required"]:
                assert required_param in tool.inputSchema["properties"]
