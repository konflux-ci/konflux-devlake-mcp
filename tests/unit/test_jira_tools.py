#!/usr/bin/env python3
"""
Unit Tests for Jira Tools

Tests the JiraTools class functionality including:
- Tool registration and listing
- Jira features retrieval
- Status filtering
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

from tools.devlake.jira_tools import JiraTools
from mcp.types import Tool


@pytest.mark.unit
class TestJiraTools:
    """Test suite for JiraTools class."""

    @pytest.fixture
    def jira_tools(self, mock_db_connection):
        """Create JiraTools instance with mock connection."""
        return JiraTools(mock_db_connection)

    @pytest.fixture
    def sample_jira_features(self):
        """Sample Jira features data for testing."""
        return [
            {
                "issue_key": "FEAT-001",
                "summary": "Implement user authentication",
                "type": "Feature",
                "status_name": "In Progress",
                "status_key": "in_progress",
                "priority_name": "High",
                "epic_key": "EPIC-100",
                "assignee_display_name": "John Doe",
                "creator_display_name": "Jane Smith",
                "story_point": 8,
                "created": "2024-01-10T09:00:00",
                "updated": "2024-01-15T14:30:00",
                "resolution_date": None,
                "lead_time_minutes": None,
                "sprint_name": "Sprint 5",
                "components": "backend,security",
                "fix_versions": "v1.2.0",
                "url": "https://jira.example.com/browse/FEAT-001",
            },
            {
                "issue_key": "FEAT-002",
                "summary": "Add dashboard analytics",
                "type": "Feature",
                "status_name": "Done",
                "status_key": "done",
                "priority_name": "Medium",
                "epic_key": "EPIC-101",
                "assignee_display_name": "Alice Brown",
                "creator_display_name": "Bob Wilson",
                "story_point": 5,
                "created": "2024-01-05T10:00:00",
                "updated": "2024-01-12T16:00:00",
                "resolution_date": "2024-01-12T16:00:00",
                "lead_time_minutes": 10080,
                "sprint_name": "Sprint 4",
                "components": "frontend",
                "fix_versions": "v1.1.0",
                "url": "https://jira.example.com/browse/FEAT-002",
            },
        ]

    @pytest.fixture
    def sample_summary_data(self):
        """Sample summary data for testing."""
        return [
            {
                "total_features": 10,
                "done": 3,
                "in_progress": 5,
                "other": 2,
                "avg_story_points": 6.5,
                "total_story_points": 65,
            }
        ]

    def test_get_tools_returns_jira_tools(self, jira_tools):
        """Test that get_tools returns the jira analysis tools."""
        tools = jira_tools.get_tools()

        assert len(tools) == 1
        tool_names = [tool.name for tool in tools]
        assert "get_jira_features" in tool_names
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_get_tool_names(self, jira_tools):
        """Test get_tool_names method."""
        tool_names = jira_tools.get_tool_names()
        assert "get_jira_features" in tool_names

    def test_validate_tool_exists(self, jira_tools):
        """Test tool existence validation."""
        assert jira_tools.validate_tool_exists("get_jira_features") is True
        assert jira_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_jira_features_with_project_name(
        self, jira_tools, mock_db_connection, sample_jira_features, sample_summary_data
    ):
        """Test getting jira features with required project_name."""
        mock_db_connection.execute_query.side_effect = [
            # Board IDs query
            {"success": True, "data": [{"board_id": 1}, {"board_id": 2}]},
            # Features query
            {"success": True, "data": sample_jira_features},
            # Summary query
            {"success": True, "data": sample_summary_data},
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert "summary" in result
        assert "features" in result
        assert len(result["features"]) == 2

    @pytest.mark.asyncio
    async def test_get_jira_features_missing_project_name(self, jira_tools):
        """Test that get_jira_features fails without project_name."""
        result_toon = await jira_tools.call_tool("get_jira_features", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_jira_features_no_boards_found(self, jira_tools, mock_db_connection):
        """Test handling when no Jira boards found for project."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": []},  # No boards found
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Empty Project"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert result["total_features"] == 0
        assert result["features"] == []
        assert "No Jira boards found" in result["message"]

    @pytest.mark.asyncio
    async def test_get_jira_features_with_status_filter(
        self, jira_tools, mock_db_connection, sample_jira_features, sample_summary_data
    ):
        """Test getting jira features with status filter."""
        done_features = [f for f in sample_jira_features if f["status_name"] == "Done"]
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"board_id": 1}]},
            {"success": True, "data": done_features},
            {"success": True, "data": sample_summary_data},
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project", "status": "Done"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True
        for feature in result["features"]:
            assert feature["status"] == "Done"

    @pytest.mark.asyncio
    async def test_get_jira_features_with_limit(
        self, jira_tools, mock_db_connection, sample_jira_features, sample_summary_data
    ):
        """Test getting jira features with custom limit."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"board_id": 1}]},
            {"success": True, "data": sample_jira_features[:1]},
            {"success": True, "data": sample_summary_data},
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project", "limit": 1}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True
        assert len(result["features"]) == 1

    @pytest.mark.asyncio
    async def test_get_jira_features_database_error(self, jira_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.side_effect = Exception("Database error")

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, jira_tools):
        """Test calling an unknown tool."""
        result_toon = await jira_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_toon)

        assert result["success"] is False
        assert "Unknown Jira tool" in result["error"]

    def test_jira_features_tool_input_schema(self, jira_tools):
        """Test that the jira features tool has proper input schema."""
        tools = jira_tools.get_tools()
        features_tool = next(t for t in tools if t.name == "get_jira_features")

        schema = features_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        assert "project_name" in properties
        assert "status" in properties
        assert "limit" in properties

    @pytest.mark.asyncio
    async def test_get_jira_features_data_structure(
        self, jira_tools, mock_db_connection, sample_jira_features, sample_summary_data
    ):
        """Test that returned features have expected structure."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"board_id": 1}]},
            {"success": True, "data": sample_jira_features},
            {"success": True, "data": sample_summary_data},
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project"}
        )
        result = toon_decode(result_toon)

        assert result["success"] is True

        # Check summary structure
        summary = result["summary"]
        assert "total_features" in summary
        assert "done" in summary
        assert "in_progress" in summary
        assert "other" in summary
        assert "avg_story_points" in summary

        # Check feature structure
        for feature in result["features"]:
            assert "issue_key" in feature
            assert "summary" in feature
            assert "status" in feature
            assert "priority" in feature
            assert "assignee" in feature
            assert "story_points" in feature
            assert "created" in feature
            assert "url" in feature

    @pytest.mark.asyncio
    async def test_get_jira_features_lead_time_conversion(
        self, jira_tools, mock_db_connection, sample_jira_features, sample_summary_data
    ):
        """Test that lead time is properly converted to hours."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"board_id": 1}]},
            {"success": True, "data": sample_jira_features},
            {"success": True, "data": sample_summary_data},
        ]

        result_toon = await jira_tools.call_tool(
            "get_jira_features", {"project_name": "Test Project"}
        )
        result = toon_decode(result_toon)

        # FEAT-002 has lead_time_minutes = 10080 (7 days = 168 hours)
        done_feature = next((f for f in result["features"] if f["issue_key"] == "FEAT-002"), None)
        assert done_feature is not None
        assert done_feature["lead_time_hours"] == 168.0

    @pytest.mark.asyncio
    async def test_get_board_ids_for_project(self, jira_tools, mock_db_connection):
        """Test the helper method for getting board IDs."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "data": [{"board_id": 1}, {"board_id": 2}, {"board_id": 3}],
        }

        board_ids = await jira_tools._get_board_ids_for_project("Test Project")

        assert board_ids == "1, 2, 3"

    @pytest.mark.asyncio
    async def test_get_board_ids_empty(self, jira_tools, mock_db_connection):
        """Test the helper method when no boards found."""
        mock_db_connection.execute_query.return_value = {"success": True, "data": []}

        board_ids = await jira_tools._get_board_ids_for_project("Test Project")

        assert board_ids == ""
