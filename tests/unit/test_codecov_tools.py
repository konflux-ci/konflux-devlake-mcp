#!/usr/bin/env python3
"""
Unit Tests for Codecov Tools

Tests the CodecovTools class functionality including:
- Tool registration and listing
- Coverage data retrieval
- Summary metrics calculation
- Trend analysis
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

from tools.devlake.codecov_tools import CodecovTools
from mcp.types import Tool


@pytest.mark.unit
class TestCodecovTools:
    """Test suite for CodecovTools class."""

    @pytest.fixture
    def codecov_tools(self, mock_db_connection):
        """Create CodecovTools instance with mock connection."""
        return CodecovTools(mock_db_connection)

    @pytest.fixture
    def sample_coverage_data(self):
        """Sample coverage data for testing."""
        return [
            {
                "repo_id": "repo1",
                "flag_name": "unit-tests",
                "coverage_percentage": 85.5,
                "lines_total": 1000,
                "lines_covered": 855,
                "partials": 50,
                "lines_uncovered": 95,
                "commit_timestamp": "2024-01-15T10:00:00",
            },
            {
                "repo_id": "repo2",
                "flag_name": "unit-tests",
                "coverage_percentage": 72.3,
                "lines_total": 800,
                "lines_covered": 578,
                "partials": 30,
                "lines_uncovered": 192,
                "commit_timestamp": "2024-01-14T10:00:00",
            },
        ]

    def test_get_tools_returns_codecov_tools(self, codecov_tools):
        """Test that get_tools returns the codecov analysis tools."""
        tools = codecov_tools.get_tools()

        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert "get_codecov_coverage" in tool_names
        assert "get_codecov_summary" in tool_names
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_get_tool_names(self, codecov_tools):
        """Test get_tool_names method."""
        tool_names = codecov_tools.get_tool_names()
        assert "get_codecov_coverage" in tool_names
        assert "get_codecov_summary" in tool_names

    def test_validate_tool_exists(self, codecov_tools):
        """Test tool existence validation."""
        assert codecov_tools.validate_tool_exists("get_codecov_coverage") is True
        assert codecov_tools.validate_tool_exists("get_codecov_summary") is True
        assert codecov_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_codecov_summary_with_project_name(self, codecov_tools, mock_db_connection):
        """Test getting codecov summary with required project_name."""
        mock_db_connection.execute_query.side_effect = [
            # Repo IDs query
            {"success": True, "data": [{"repo_id": "repo1"}, {"repo_id": "repo2"}]},
            # Latest coverage query
            {
                "success": True,
                "data": [
                    {
                        "repo_id": "repo1",
                        "flag_name": "unit-tests",
                        "coverage_percentage": 85.5,
                        "lines_total": 1000,
                        "lines_covered": 855,
                        "partials": 50,
                        "lines_uncovered": 95,
                    },
                    {
                        "repo_id": "repo2",
                        "flag_name": "unit-tests",
                        "coverage_percentage": 72.3,
                        "lines_total": 800,
                        "lines_covered": 578,
                        "partials": 30,
                        "lines_uncovered": 192,
                    },
                ],
            },
            # Patch coverage query
            {"success": True, "data": [{"repo_id": "repo1", "latest_patch": 90.0}]},
            # Start coverage query
            {"success": True, "data": [{"repo_id": "repo1", "start_coverage": 80.0}]},
        ]

        result_json = await codecov_tools.call_tool(
            "get_codecov_summary", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert "repo_count" in result
        assert "avg_coverage" in result
        assert "total_lines" in result
        assert "health_distribution" in result

    @pytest.mark.asyncio
    async def test_get_codecov_summary_missing_project_name(self, codecov_tools):
        """Test that get_codecov_summary fails without project_name."""
        result_json = await codecov_tools.call_tool("get_codecov_summary", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_codecov_coverage_with_project_name(self, codecov_tools, mock_db_connection):
        """Test getting full codecov coverage analysis."""
        mock_db_connection.execute_query.side_effect = [
            # Repo IDs query
            {"success": True, "data": [{"repo_id": "repo1"}]},
            # Latest coverage query
            {
                "success": True,
                "data": [
                    {
                        "repo_id": "repo1",
                        "flag_name": "unit-tests",
                        "coverage_percentage": 85.5,
                        "lines_total": 1000,
                        "lines_covered": 855,
                        "partials": 50,
                        "lines_uncovered": 95,
                        "commit_timestamp": "2024-01-15T10:00:00",
                    }
                ],
            },
            # Daily trend query
            {
                "success": True,
                "data": [
                    {
                        "date": "2024-01-15",
                        "repo_id": "repo1",
                        "flag_name": "unit-tests",
                        "daily_coverage": 85.5,
                        "lines_total": 1000,
                        "lines_covered": 855,
                    }
                ],
            },
            # Start coverage query
            {"success": True, "data": [{"repo_id": "repo1", "start_coverage": 80.0}]},
            # Patch coverage query
            {
                "success": True,
                "data": [{"repo_id": "repo1", "avg_patch_coverage": 92.0, "patch_count": 5}],
            },
            # Latest patch query
            {"success": True, "data": [{"repo_id": "repo1", "latest_patch": 95.0}]},
            # Daily patch query
            {
                "success": True,
                "data": [{"date": "2024-01-15", "avg_patch": 92.0, "patch_count": 2}],
            },
            # Flag coverage query
            {
                "success": True,
                "data": [
                    {
                        "flag_name": "unit-tests",
                        "repo_count": 1,
                        "avg_coverage": 85.5,
                        "total_lines": 1000,
                        "lines_covered": 855,
                    }
                ],
            },
        ]

        result_json = await codecov_tools.call_tool(
            "get_codecov_coverage", {"project_name": "Test Project", "days_back": 30}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert "executive_summary" in result
        assert "repositories" in result
        assert "coverage_by_flag" in result
        assert "daily_trend" in result
        assert "patch_coverage" in result
        assert "health_breakdown" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_get_codecov_coverage_no_repos(self, codecov_tools, mock_db_connection):
        """Test handling when no repositories found."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": []},  # No repos found
            {"success": True, "data": []},  # Fallback also empty
        ]

        result_json = await codecov_tools.call_tool(
            "get_codecov_coverage", {"project_name": "Empty Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["executive_summary"]["repo_count"] == 0

    @pytest.mark.asyncio
    async def test_get_codecov_summary_with_days_back(self, codecov_tools, mock_db_connection):
        """Test codecov summary with custom days_back."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"repo_id": "repo1"}]},
            {
                "success": True,
                "data": [
                    {
                        "repo_id": "repo1",
                        "flag_name": "unit-tests",
                        "coverage_percentage": 85.5,
                        "lines_total": 1000,
                        "lines_covered": 855,
                        "partials": 50,
                        "lines_uncovered": 95,
                    }
                ],
            },
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]

        result_json = await codecov_tools.call_tool(
            "get_codecov_summary", {"project_name": "Test Project", "days_back": 90}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["days_back"] == 90

    @pytest.mark.asyncio
    async def test_get_codecov_summary_database_error(self, codecov_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.side_effect = Exception("Database error")

        result_json = await codecov_tools.call_tool(
            "get_codecov_summary", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, codecov_tools):
        """Test calling an unknown tool."""
        result_json = await codecov_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Unknown Codecov tool" in result["error"]

    def test_codecov_coverage_tool_input_schema(self, codecov_tools):
        """Test that the codecov coverage tool has proper input schema."""
        tools = codecov_tools.get_tools()
        coverage_tool = next(t for t in tools if t.name == "get_codecov_coverage")

        schema = coverage_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        assert "project_name" in properties
        assert "days_back" in properties

    def test_codecov_summary_tool_input_schema(self, codecov_tools):
        """Test that the codecov summary tool has proper input schema."""
        tools = codecov_tools.get_tools()
        summary_tool = next(t for t in tools if t.name == "get_codecov_summary")

        schema = summary_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

    def test_classify_coverage(self, codecov_tools):
        """Test coverage classification helper."""
        assert codecov_tools._classify_coverage(80) == "good"
        assert codecov_tools._classify_coverage(70) == "good"
        assert codecov_tools._classify_coverage(60) == "warning"
        assert codecov_tools._classify_coverage(50) == "warning"
        assert codecov_tools._classify_coverage(40) == "danger"

    def test_calculate_trend(self, codecov_tools):
        """Test trend calculation helper."""
        direction, change = codecov_tools._calculate_trend(80, 85)
        assert direction == "improving"
        assert change == 5.0

        direction, change = codecov_tools._calculate_trend(85, 80)
        assert direction == "declining"
        assert change == -5.0

        direction, change = codecov_tools._calculate_trend(80, 80.5)
        assert direction == "stable"

    def test_generate_recommendations(self, codecov_tools):
        """Test recommendation generation."""
        repos = [
            {"repo_id": "repo1", "latest_coverage": 45, "trend": "stable"},
            {
                "repo_id": "repo2",
                "latest_coverage": 65,
                "trend": "declining",
                "trend_change_pct": -5,
            },
        ]
        recommendations = codecov_tools._generate_recommendations(repos)

        assert len(recommendations) >= 1
        # Should have critical recommendation for repo1 (below 50%)
        critical = [r for r in recommendations if r["type"] == "critical"]
        assert len(critical) >= 1
