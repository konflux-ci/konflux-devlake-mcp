#!/usr/bin/env python3
"""
Unit Tests for Incident Tools

Tests the IncidentTools class functionality including:
- Tool registration and listing
- Incident data retrieval with filtering
- Parameter validation
- Date range handling
"""

import pytest
import json

from tools.devlake.incident_tools import IncidentTools
from mcp.types import Tool


@pytest.mark.unit
class TestIncidentTools:
    """Test suite for IncidentTools class."""

    @pytest.fixture
    def incident_tools(self, mock_db_connection):
        """Create IncidentTools instance with mock connection."""
        return IncidentTools(mock_db_connection)

    def test_get_tools_returns_incident_tools(self, incident_tools):
        """Test that get_tools returns the incident analysis tool."""
        tools = incident_tools.get_tools()

        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "get_incidents"
        assert "Comprehensive Incident Analysis Tool" in tools[0].description

    def test_get_tool_names(self, incident_tools):
        """Test get_tool_names method."""
        tool_names = incident_tools.get_tool_names()
        assert "get_incidents" in tool_names

    def test_validate_tool_exists(self, incident_tools):
        """Test tool existence validation."""
        assert incident_tools.validate_tool_exists("get_incidents") is True
        assert incident_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_incidents_no_filters(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents without any filters."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ...",
            "row_count": 2,
            "data": sample_incident_data,
        }

        result_json = await incident_tools.call_tool("get_incidents", {})
        result = json.loads(result_json)

        assert result["success"] is True
        assert "filters" in result
        assert "incidents" in result
        assert len(result["incidents"]) == 2

        filters = result["filters"]
        assert filters["status"] == "all"
        assert filters["component"] == "all"
        assert filters["date_field"] == "created_date"
        assert filters["limit"] == 100

    @pytest.mark.asyncio
    async def test_get_incidents_with_status_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with status filter."""
        filtered_data = [
            incident for incident in sample_incident_data if incident["status"] == "DONE"
        ]
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... " "WHERE t1.status = 'DONE'",
            "row_count": 1,
            "data": filtered_data,
        }

        result_json = await incident_tools.call_tool("get_incidents", {"status": "DONE"})
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["status"] == "DONE"
        assert len(result["incidents"]) == 1
        assert result["incidents"][0]["status"] == "DONE"

    @pytest.mark.asyncio
    async def test_get_incidents_with_component_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with component filter."""
        filtered_data = [
            incident for incident in sample_incident_data if incident["component"] == "api-service"
        ]
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... " "WHERE t1.component = 'api-service'",
            "row_count": 1,
            "data": filtered_data,
        }

        result_json = await incident_tools.call_tool("get_incidents", {"component": "api-service"})
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["component"] == "api-service"
        assert len(result["incidents"]) == 1
        assert result["incidents"][0]["component"] == "api-service"

    @pytest.mark.asyncio
    async def test_get_incidents_with_days_back_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with days_back filter."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... "
            "WHERE t1.created_date >= '2024-01-01 00:00:00'",
            "row_count": 2,
            "data": sample_incident_data,
        }

        result_json = await incident_tools.call_tool("get_incidents", {"days_back": 30})
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["days_back"] == 30
        assert len(result["incidents"]) == 2

    @pytest.mark.asyncio
    async def test_get_incidents_with_date_range(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with explicit date range."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... "
            "WHERE t1.created_date >= '2024-01-15 00:00:00' "
            "AND t1.created_date <= '2024-01-16 23:59:59'",
            "row_count": 2,
            "data": sample_incident_data,
        }

        result_json = await incident_tools.call_tool(
            "get_incidents", {"start_date": "2024-01-15", "end_date": "2024-01-16"}
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert "2024-01-15" in result["filters"]["start_date"]
        assert "2024-01-16" in result["filters"]["end_date"]

    @pytest.mark.asyncio
    async def test_get_incidents_with_datetime_range(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with full datetime range."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... "
            "WHERE t1.created_date >= '2024-01-15 10:00:00' "
            "AND t1.created_date <= '2024-01-16 12:00:00'",
            "row_count": 2,
            "data": sample_incident_data,
        }

        result_json = await incident_tools.call_tool(
            "get_incidents",
            {"start_date": "2024-01-15 10:00:00", "end_date": "2024-01-16 12:00:00"},
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["start_date"] == "2024-01-15 10:00:00"
        assert result["filters"]["end_date"] == "2024-01-16 12:00:00"

    @pytest.mark.asyncio
    async def test_get_incidents_with_different_date_fields(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with different date field options."""
        for date_field in ["created_date", "resolution_date", "updated_date"]:
            mock_db_connection.execute_query.return_value = {
                "success": True,
                "query": f"SELECT t1.* FROM lake.incidents t1 ... "
                f"ORDER BY t1.{date_field} DESC",
                "row_count": 2,
                "data": sample_incident_data,
            }

            result_json = await incident_tools.call_tool(
                "get_incidents", {"date_field": date_field}
            )
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["filters"]["date_field"] == date_field

    @pytest.mark.asyncio
    async def test_get_incidents_invalid_date_field(self, incident_tools):
        """Test getting incidents with invalid date field."""
        result_json = await incident_tools.call_tool(
            "get_incidents", {"date_field": "invalid_field"}
        )
        result = json.loads(result_json)

        assert result["success"] is False
        assert "Invalid date_field 'invalid_field'" in result["error"]

    @pytest.mark.asyncio
    async def test_get_incidents_with_limit(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with custom limit."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... LIMIT 50",
            "row_count": 2,
            "data": sample_incident_data,
        }

        result_json = await incident_tools.call_tool("get_incidents", {"limit": 50})
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_get_incidents_combined_filters(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with multiple filters combined."""
        filtered_data = [
            incident
            for incident in sample_incident_data
            if incident["status"] == "DONE" and incident["component"] == "api-service"
        ]

        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "SELECT t1.* FROM lake.incidents t1 ... "
            "WHERE t1.status = 'DONE' "
            "AND t1.component = 'api-service'",
            "row_count": 1,
            "data": filtered_data,
        }

        result_json = await incident_tools.call_tool(
            "get_incidents", {"status": "DONE", "component": "api-service", "limit": 25}
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["status"] == "DONE"
        assert result["filters"]["component"] == "api-service"
        assert result["filters"]["limit"] == 25

    @pytest.mark.asyncio
    async def test_get_incidents_database_error(self, incident_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.return_value = {
            "success": False,
            "error": "Database connection failed",
        }

        result_json = await incident_tools.call_tool("get_incidents", {})
        result = json.loads(result_json)

        assert result["success"] is False
        assert "Database connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_incidents_exception_handling(self, incident_tools, mock_db_connection):
        """Test exception handling in incident tools."""
        mock_db_connection.execute_query.side_effect = Exception("Unexpected error")

        result_json = await incident_tools.call_tool("get_incidents", {})
        result = json.loads(result_json)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, incident_tools):
        """Test calling an unknown tool."""
        result_json = await incident_tools.call_tool("unknown_tool", {})
        result = json.loads(result_json)

        assert result["success"] is False
        assert "Unknown incident tool: unknown_tool" in result["error"]

    def test_incident_tool_input_schema(self, incident_tools):
        """Test that the incident tool has proper input schema."""
        tools = incident_tools.get_tools()
        get_incidents_tool = tools[0]

        schema = get_incidents_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == []

        properties = schema["properties"]
        expected_properties = [
            "status",
            "component",
            "days_back",
            "start_date",
            "end_date",
            "date_field",
            "limit",
        ]

        for prop in expected_properties:
            assert prop in properties
            assert "description" in properties[prop]

    def test_incident_data_structure_validation(self, sample_incident_data):
        """Test that sample incident data has expected structure."""
        for incident in sample_incident_data:
            required_fields = [
                "incident_key",
                "title",
                "description",
                "status",
                "created_date",
                "component",
                "url",
            ]

            for field in required_fields:
                assert field in incident

            assert isinstance(incident["incident_key"], str)
            assert isinstance(incident["title"], str)
            assert isinstance(incident["status"], str)
            assert isinstance(incident["component"], str)
            assert isinstance(incident["url"], str)
