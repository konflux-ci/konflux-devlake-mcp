#!/usr/bin/env python3
"""
Unit Tests for Lead Time Tools

Tests the LeadTimeTools class functionality including:
- Tool registration and listing
- DORA Lead Time for Changes metric
- PR cycle time breakdown
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

from tools.devlake.lead_time_tools import LeadTimeTools
from mcp.types import Tool


@pytest.mark.unit
class TestLeadTimeTools:
    """Test suite for LeadTimeTools class."""

    @pytest.fixture
    def lead_time_tools(self, mock_db_connection):
        """Create LeadTimeTools instance with mock connection."""
        return LeadTimeTools(mock_db_connection)

    @pytest.fixture
    def sample_pr_details(self):
        """Sample PR details data for testing."""
        return [
            {
                "pr_title": "Add user authentication",
                "pr_url": "https://github.com/org/repo/pull/1",
                "first_commit_sha": "abc123",
                "first_commit_date": "2024-01-10T09:00:00",
                "deployment_id": "deploy-001",
                "deployment_date": "2024-01-12T15:00:00",
                "coding_time_hours": 24.5,
                "pickup_time_hours": 2.0,
                "review_time_hours": 8.5,
                "deploy_time_hours": 1.0,
                "lead_time_hours": 36.0,
            },
            {
                "pr_title": "Fix performance issue",
                "pr_url": "https://github.com/org/repo/pull/2",
                "first_commit_sha": "def456",
                "first_commit_date": "2024-01-11T10:00:00",
                "deployment_id": "deploy-002",
                "deployment_date": "2024-01-13T11:00:00",
                "coding_time_hours": 12.0,
                "pickup_time_hours": 1.5,
                "review_time_hours": 4.0,
                "deploy_time_hours": 0.5,
                "lead_time_hours": 18.0,
            },
        ]

    def test_get_tools_returns_lead_time_tools(self, lead_time_tools):
        """Test that get_tools returns the lead time analysis tools."""
        tools = lead_time_tools.get_tools()

        assert len(tools) == 1
        tool_names = [tool.name for tool in tools]
        assert "get_lead_time_for_changes" in tool_names
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_get_tool_names(self, lead_time_tools):
        """Test get_tool_names method."""
        tool_names = lead_time_tools.get_tool_names()
        assert "get_lead_time_for_changes" in tool_names

    def test_validate_tool_exists(self, lead_time_tools):
        """Test tool existence validation."""
        assert lead_time_tools.validate_tool_exists("get_lead_time_for_changes") is True
        assert lead_time_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_lead_time_with_project_name(
        self, lead_time_tools, mock_db_connection, sample_pr_details
    ):
        """Test getting lead time for changes with required project_name."""
        mock_db_connection.execute_query.side_effect = [
            # Cycle time query
            {"success": True, "data": [{"avg_cycle_time_hours": 27.0, "pr_count": 10}]},
            # Coding time query
            {"success": True, "data": [{"avg_coding_time_hours": 18.0}]},
            # Pickup time query
            {"success": True, "data": [{"avg_pickup_time_hours": 1.75}]},
            # Review time query
            {"success": True, "data": [{"avg_review_time_hours": 6.25}]},
            # Deploy time query
            {"success": True, "data": [{"avg_deploy_time_hours": 0.75}]},
            # PR details query
            {"success": True, "data": sample_pr_details},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert result["days_back"] == 30
        assert result["deployed_prs_count"] == 10
        assert result["avg_lead_time_hours"] == 27.0
        assert "breakdown" in result
        assert "pr_details" in result

    @pytest.mark.asyncio
    async def test_get_lead_time_missing_project_name(self, lead_time_tools):
        """Test that get_lead_time_for_changes fails without project_name."""
        result_json = await lead_time_tools.call_tool("get_lead_time_for_changes", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_lead_time_with_days_back(
        self, lead_time_tools, mock_db_connection, sample_pr_details
    ):
        """Test getting lead time with custom days_back."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"avg_cycle_time_hours": 30.0, "pr_count": 20}]},
            {"success": True, "data": [{"avg_coding_time_hours": 20.0}]},
            {"success": True, "data": [{"avg_pickup_time_hours": 2.0}]},
            {"success": True, "data": [{"avg_review_time_hours": 7.0}]},
            {"success": True, "data": [{"avg_deploy_time_hours": 1.0}]},
            {"success": True, "data": sample_pr_details},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project", "days_back": 90}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["days_back"] == 90

    @pytest.mark.asyncio
    async def test_get_lead_time_with_limit(
        self, lead_time_tools, mock_db_connection, sample_pr_details
    ):
        """Test getting lead time with custom limit."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"avg_cycle_time_hours": 27.0, "pr_count": 10}]},
            {"success": True, "data": [{"avg_coding_time_hours": 18.0}]},
            {"success": True, "data": [{"avg_pickup_time_hours": 1.75}]},
            {"success": True, "data": [{"avg_review_time_hours": 6.25}]},
            {"success": True, "data": [{"avg_deploy_time_hours": 0.75}]},
            {"success": True, "data": sample_pr_details[:1]},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project", "limit": 1}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert len(result["pr_details"]) == 1

    @pytest.mark.asyncio
    async def test_get_lead_time_no_data(self, lead_time_tools, mock_db_connection):
        """Test handling when no PR data found."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"avg_cycle_time_hours": None, "pr_count": 0}]},
            {"success": True, "data": [{"avg_coding_time_hours": None}]},
            {"success": True, "data": [{"avg_pickup_time_hours": None}]},
            {"success": True, "data": [{"avg_review_time_hours": None}]},
            {"success": True, "data": [{"avg_deploy_time_hours": None}]},
            {"success": True, "data": []},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Empty Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["deployed_prs_count"] == 0
        assert result["avg_lead_time_hours"] is None
        assert result["pr_details"] == []

    @pytest.mark.asyncio
    async def test_get_lead_time_database_error(self, lead_time_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.side_effect = Exception("Database error")

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, lead_time_tools):
        """Test calling an unknown tool."""
        result_json = await lead_time_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_lead_time_tool_input_schema(self, lead_time_tools):
        """Test that the lead time tool has proper input schema."""
        tools = lead_time_tools.get_tools()
        lead_time_tool = next(t for t in tools if t.name == "get_lead_time_for_changes")

        schema = lead_time_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        assert "project_name" in properties
        assert "days_back" in properties
        assert "limit" in properties

    @pytest.mark.asyncio
    async def test_get_lead_time_breakdown_structure(
        self, lead_time_tools, mock_db_connection, sample_pr_details
    ):
        """Test that breakdown has expected structure."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"avg_cycle_time_hours": 27.0, "pr_count": 10}]},
            {"success": True, "data": [{"avg_coding_time_hours": 18.0}]},
            {"success": True, "data": [{"avg_pickup_time_hours": 1.75}]},
            {"success": True, "data": [{"avg_review_time_hours": 6.25}]},
            {"success": True, "data": [{"avg_deploy_time_hours": 0.75}]},
            {"success": True, "data": sample_pr_details},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        breakdown = result["breakdown"]
        assert "avg_coding_time_hours" in breakdown
        assert "avg_pickup_time_hours" in breakdown
        assert "avg_review_time_hours" in breakdown
        assert "avg_deploy_time_hours" in breakdown

        assert breakdown["avg_coding_time_hours"] == 18.0
        assert breakdown["avg_pickup_time_hours"] == 1.75
        assert breakdown["avg_review_time_hours"] == 6.25
        assert breakdown["avg_deploy_time_hours"] == 0.75

    @pytest.mark.asyncio
    async def test_get_lead_time_pr_details_structure(
        self, lead_time_tools, mock_db_connection, sample_pr_details
    ):
        """Test that PR details have expected structure."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"avg_cycle_time_hours": 27.0, "pr_count": 10}]},
            {"success": True, "data": [{"avg_coding_time_hours": 18.0}]},
            {"success": True, "data": [{"avg_pickup_time_hours": 1.75}]},
            {"success": True, "data": [{"avg_review_time_hours": 6.25}]},
            {"success": True, "data": [{"avg_deploy_time_hours": 0.75}]},
            {"success": True, "data": sample_pr_details},
        ]

        result_json = await lead_time_tools.call_tool(
            "get_lead_time_for_changes", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        for pr in result["pr_details"]:
            assert "pr_title" in pr
            assert "pr_url" in pr
            assert "deployment_id" in pr
            assert "deployment_date" in pr
            assert "coding_time_hours" in pr
            assert "pickup_time_hours" in pr
            assert "review_time_hours" in pr
            assert "deploy_time_hours" in pr
            assert "lead_time_hours" in pr

    def test_safe_float_helper(self, lead_time_tools):
        """Test the _safe_float helper method."""
        assert lead_time_tools._safe_float(10.5) == 10.5
        assert lead_time_tools._safe_float("10.5") == 10.5
        assert lead_time_tools._safe_float(None) is None
        assert lead_time_tools._safe_float("invalid") is None
