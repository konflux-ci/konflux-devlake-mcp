#!/usr/bin/env python3
"""
Unit Tests for Incident Tools

Tests the IncidentTools class functionality including:
- Tool registration and listing
- Incident data retrieval with filtering
- DORA metrics (MTTR, Failed Deployment Recovery Time)
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

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
        """Test that get_tools returns the incident analysis tools."""
        tools = incident_tools.get_tools()

        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert "get_incidents" in tool_names
        assert "get_failed_deployment_recovery_time" in tool_names
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_get_tool_names(self, incident_tools):
        """Test get_tool_names method."""
        tool_names = incident_tools.get_tool_names()
        assert "get_incidents" in tool_names
        assert "get_failed_deployment_recovery_time" in tool_names

    def test_validate_tool_exists(self, incident_tools):
        """Test tool existence validation."""
        assert incident_tools.validate_tool_exists("get_incidents") is True
        assert incident_tools.validate_tool_exists("get_failed_deployment_recovery_time") is True
        assert incident_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_incidents_with_project_name(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with required project_name."""
        # Mock the three queries that get_incidents makes
        mock_db_connection.execute_query.side_effect = [
            # Median MTTR query
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 2.5}]},
            # Count query
            {"success": True, "data": [{"incident_count": 2}]},
            # Details query
            {"success": True, "data": sample_incident_data},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert result["days_back"] == 30
        assert result["median_time_to_restore_service_hours"] == 2.5
        assert result["incident_count"] == 2
        assert "incidents" in result

    @pytest.mark.asyncio
    async def test_get_incidents_missing_project_name(self, incident_tools):
        """Test that get_incidents fails without project_name."""
        result_json = await incident_tools.call_tool("get_incidents", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_incidents_with_status_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with status filter."""
        filtered_data = [
            incident for incident in sample_incident_data if incident["status"] == "DONE"
        ]
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 2.0}]},
            {"success": True, "data": [{"incident_count": 1}]},
            {"success": True, "data": filtered_data},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project", "status": "DONE"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_incidents_with_component_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with component filter."""
        filtered_data = [
            incident for incident in sample_incident_data if incident["component"] == "api-service"
        ]
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 1.5}]},
            {"success": True, "data": [{"incident_count": 1}]},
            {"success": True, "data": filtered_data},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project", "component": "api-service"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_incidents_with_days_back_filter(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with days_back filter."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 3.0}]},
            {"success": True, "data": [{"incident_count": 5}]},
            {"success": True, "data": sample_incident_data},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project", "days_back": 60}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["days_back"] == 60

    @pytest.mark.asyncio
    async def test_get_incidents_with_limit(
        self, incident_tools, mock_db_connection, sample_incident_data
    ):
        """Test getting incidents with custom limit."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 2.0}]},
            {"success": True, "data": [{"incident_count": 10}]},
            {"success": True, "data": sample_incident_data[:1]},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project", "limit": 50}
        )
        result = toon_decode(result_json)

        assert result["success"] is True

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

        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": 1.0}]},
            {"success": True, "data": [{"incident_count": 1}]},
            {"success": True, "data": filtered_data},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents",
            {
                "project_name": "Test Project",
                "status": "DONE",
                "component": "api-service",
                "days_back": 90,
                "limit": 25,
            },
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert result["days_back"] == 90

    @pytest.mark.asyncio
    async def test_get_incidents_database_error(self, incident_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.side_effect = Exception("Database connection failed")

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Database connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_incidents_null_median_mttr(self, incident_tools, mock_db_connection):
        """Test handling when median MTTR is null (no resolved incidents)."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"median_time_to_resolve_in_hours": None}]},
            {"success": True, "data": [{"incident_count": 0}]},
            {"success": True, "data": []},
        ]

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["median_time_to_restore_service_hours"] is None
        assert result["incident_count"] == 0
        assert result["incidents"] == []

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, incident_tools):
        """Test calling an unknown tool."""
        result_json = await incident_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Unknown incident tool: unknown_tool" in result["error"]

    def test_incident_tool_input_schema(self, incident_tools):
        """Test that the incident tool has proper input schema."""
        tools = incident_tools.get_tools()
        get_incidents_tool = next(t for t in tools if t.name == "get_incidents")

        schema = get_incidents_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        expected_properties = [
            "project_name",
            "status",
            "component",
            "days_back",
            "limit",
        ]

        for prop in expected_properties:
            assert prop in properties
            assert "description" in properties[prop]

    def test_failed_deployment_recovery_time_input_schema(self, incident_tools):
        """Test that the FDRT tool has proper input schema."""
        tools = incident_tools.get_tools()
        fdrt_tool = next(t for t in tools if t.name == "get_failed_deployment_recovery_time")

        schema = fdrt_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        assert "project_name" in properties
        assert "days_back" in properties

    @pytest.mark.asyncio
    async def test_get_failed_deployment_recovery_time(self, incident_tools, mock_db_connection):
        """Test the DORA Failed Deployment Recovery Time metric."""
        mock_db_connection.execute_query.side_effect = [
            # Median recovery time query
            {"success": True, "data": [{"median_recovery_time_minutes": 120}]},
            # Count query
            {"success": True, "data": [{"total_incidents": 1}]},
            # Details query
            {
                "success": True,
                "data": [
                    {
                        "deployment_id": "deploy-1",
                        "deployment_finished_date": "2024-01-15T10:00:00",
                        "incident_caused_by_deployment": "deploy-1",
                        "incident_title": "Service outage",
                        "incident_url": "https://example.com/inc-1",
                        "incident_resolution_date": "2024-01-15T12:00:00",
                        "failed_deployment_recovery_time": 2,
                    }
                ],
            },
        ]

        result_json = await incident_tools.call_tool(
            "get_failed_deployment_recovery_time", {"project_name": "Test Project", "days_back": 90}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert result["days_back"] == 90
        assert "median_recovery_time_hours" in result
        assert "incidents_caused_by_deployments" in result
        assert "incident_details" in result

    @pytest.mark.asyncio
    async def test_get_failed_deployment_recovery_time_missing_project(self, incident_tools):
        """Test FDRT fails without project_name."""
        result_json = await incident_tools.call_tool("get_failed_deployment_recovery_time", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

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
