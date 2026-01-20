#!/usr/bin/env python3
"""
Unit Tests for Historical Trends Tools

Tests the HistoricalTrendsTools class functionality including:
- Tool registration and listing
- Week-over-week trend analysis
- Anomaly detection
- Parameter validation
"""

import pytest
from toon_format import decode as toon_decode

from tools.devlake.historical_trends_tools import HistoricalTrendsTools
from mcp.types import Tool


@pytest.mark.unit
class TestHistoricalTrendsTools:
    """Test suite for HistoricalTrendsTools class."""

    @pytest.fixture
    def trends_tools(self, mock_db_connection):
        """Create HistoricalTrendsTools instance with mock connection."""
        return HistoricalTrendsTools(mock_db_connection)

    @pytest.fixture
    def sample_cycle_time_data(self):
        """Sample cycle time weekly data for testing."""
        return [
            {
                "week": 202403,
                "week_start": "2024-01-15",
                "avg_cycle_time_hours": 24.5,
                "pr_count": 15,
            },
            {
                "week": 202402,
                "week_start": "2024-01-08",
                "avg_cycle_time_hours": 28.0,
                "pr_count": 12,
            },
            {
                "week": 202401,
                "week_start": "2024-01-01",
                "avg_cycle_time_hours": 26.0,
                "pr_count": 10,
            },
            {
                "week": 202352,
                "week_start": "2023-12-25",
                "avg_cycle_time_hours": 25.5,
                "pr_count": 8,
            },
        ]

    @pytest.fixture
    def sample_merge_rate_data(self):
        """Sample merge rate weekly data for testing."""
        return [
            {
                "week": 202403,
                "week_start": "2024-01-15",
                "merge_rate": 85.5,
                "total_prs": 20,
            },
            {
                "week": 202402,
                "week_start": "2024-01-08",
                "merge_rate": 80.0,
                "total_prs": 18,
            },
        ]

    @pytest.fixture
    def sample_weekly_breakdown(self):
        """Sample weekly breakdown data for testing."""
        return [
            {
                "week": 202403,
                "week_start": "2024-01-15",
                "week_end": "2024-01-21",
                "cycle_time_avg": 24.5,
                "prs_merged": 15,
            },
            {
                "week": 202402,
                "week_start": "2024-01-08",
                "week_end": "2024-01-14",
                "cycle_time_avg": 28.0,
                "prs_merged": 12,
            },
        ]

    def test_get_tools_returns_trends_tools(self, trends_tools):
        """Test that get_tools returns the trends analysis tools."""
        tools = trends_tools.get_tools()

        assert len(tools) == 1
        tool_names = [tool.name for tool in tools]
        assert "get_historical_trends" in tool_names
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_get_tool_names(self, trends_tools):
        """Test get_tool_names method."""
        tool_names = trends_tools.get_tool_names()
        assert "get_historical_trends" in tool_names

    def test_validate_tool_exists(self, trends_tools):
        """Test tool existence validation."""
        assert trends_tools.validate_tool_exists("get_historical_trends") is True
        assert trends_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_historical_trends_all_metrics(
        self, trends_tools, mock_db_connection, sample_cycle_time_data, sample_weekly_breakdown
    ):
        """Test getting all historical trends."""
        # Mock all the metric queries + weekly breakdown
        mock_db_connection.execute_query.side_effect = [
            # Cycle time query
            {"success": True, "data": sample_cycle_time_data},
            # Merge rate query
            {"success": True, "data": [{"week": 202403, "merge_rate": 85.0, "total_prs": 20}]},
            # Retests query
            {
                "success": True,
                "data": [
                    {
                        "week": 202403,
                        "retest_count": 10,
                        "prs_affected": 8,
                        "retests_per_pr": 1.25,
                    }
                ],
            },
            # CI success query
            {"success": True, "data": [{"week": 202403, "success_rate": 92.0, "total_runs": 100}]},
            # Coverage query - first get repo names
            {"success": True, "data": [{"repo_name": "repo1"}]},
            # Coverage weekly data
            {"success": True, "data": [{"week": 202403, "avg_coverage": 78.5, "sample_count": 50}]},
            # MTTR query
            {
                "success": True,
                "data": [{"week": 202403, "avg_mttr_hours": 4.5, "incident_count": 3}],
            },
            # Weekly breakdown query
            {"success": True, "data": sample_weekly_breakdown},
        ]

        result_json = await trends_tools.call_tool(
            "get_historical_trends", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert "summary" in result
        assert "metrics" in result
        assert "anomalies" in result
        assert "weekly_breakdown" in result

    @pytest.mark.asyncio
    async def test_get_historical_trends_missing_project_name(self, trends_tools):
        """Test that get_historical_trends fails without project_name."""
        result_json = await trends_tools.call_tool("get_historical_trends", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_historical_trends_single_metric(
        self, trends_tools, mock_db_connection, sample_cycle_time_data, sample_weekly_breakdown
    ):
        """Test getting a single metric trend."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": sample_cycle_time_data},
            {"success": True, "data": sample_weekly_breakdown},
        ]

        result_json = await trends_tools.call_tool(
            "get_historical_trends", {"project_name": "Test Project", "metric": "cycle_time"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "cycle_time" in result["metrics"]

    @pytest.mark.asyncio
    async def test_get_historical_trends_with_period(
        self, trends_tools, mock_db_connection, sample_cycle_time_data, sample_weekly_breakdown
    ):
        """Test getting trends with custom period."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": sample_cycle_time_data},
            {"success": True, "data": sample_weekly_breakdown},
        ]

        result_json = await trends_tools.call_tool(
            "get_historical_trends",
            {"project_name": "Test Project", "metric": "cycle_time", "period": "90"},
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert result["period_days"] == 90

    @pytest.mark.asyncio
    async def test_get_historical_trends_no_data(self, trends_tools, mock_db_connection):
        """Test handling when no trend data found."""
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]

        result_json = await trends_tools.call_tool(
            "get_historical_trends", {"project_name": "Empty Project", "metric": "cycle_time"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        cycle_time = result["metrics"]["cycle_time"]
        assert cycle_time["current_week"]["value"] is None
        assert cycle_time["change_direction"] == "no_data"

    @pytest.mark.asyncio
    async def test_get_historical_trends_database_error(self, trends_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.side_effect = Exception("Database error")

        result_json = await trends_tools.call_tool(
            "get_historical_trends", {"project_name": "Test Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, trends_tools):
        """Test calling an unknown tool."""
        result_json = await trends_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_json)

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_historical_trends_tool_input_schema(self, trends_tools):
        """Test that the historical trends tool has proper input schema."""
        tools = trends_tools.get_tools()
        trends_tool = next(t for t in tools if t.name == "get_historical_trends")

        schema = trends_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == ["project_name"]

        properties = schema["properties"]
        assert "project_name" in properties
        assert "metric" in properties
        assert "period" in properties

        # Check enum values
        assert "enum" in properties["metric"]
        assert "all" in properties["metric"]["enum"]
        assert "cycle_time" in properties["metric"]["enum"]

    def test_process_trend_data_with_data(self, trends_tools):
        """Test _process_trend_data with valid data."""
        result = {
            "success": True,
            "data": [
                {"week": 202403, "avg_value": 24.5, "pr_count": 15},
                {"week": 202402, "avg_value": 28.0, "pr_count": 12},
                {"week": 202401, "avg_value": 26.0, "pr_count": 10},
                {"week": 202352, "avg_value": 25.5, "pr_count": 8},
            ],
        }

        processed = trends_tools._process_trend_data(result, "avg_value", "hours", "cycle_time")

        assert processed["current_week"]["value"] == 24.5
        assert processed["previous_week"]["value"] == 28.0
        assert processed["change_percent"] is not None
        assert len(processed["trend_4_weeks"]) == 4

    def test_process_trend_data_empty(self, trends_tools):
        """Test _process_trend_data with empty data."""
        result = {"success": True, "data": []}

        processed = trends_tools._process_trend_data(result, "avg_value", "hours", "cycle_time")

        assert processed["current_week"]["value"] is None
        assert processed["change_direction"] == "no_data"
        assert processed["trend_4_weeks"] == []

    def test_get_change_direction_improved(self, trends_tools):
        """Test change direction calculation for improvement."""
        # For cycle_time, negative change is improvement
        direction = trends_tools._get_change_direction(-10, "cycle_time")
        assert direction == "improved"

    def test_get_change_direction_regressed(self, trends_tools):
        """Test change direction calculation for regression."""
        # For cycle_time, large positive change is regression
        direction = trends_tools._get_change_direction(15, "cycle_time")
        assert direction == "regressed"

    def test_get_change_direction_stable(self, trends_tools):
        """Test change direction calculation for stable."""
        # Small change is stable
        direction = trends_tools._get_change_direction(2, "cycle_time")
        assert direction == "stable"

    def test_determine_overall_health_improving(self, trends_tools):
        """Test overall health determination when improving."""
        metrics = {
            "cycle_time": {"change_direction": "improved"},
            "merge_rate": {"change_direction": "improved"},
            "ci_success": {"change_direction": "stable"},
        }
        health = trends_tools._determine_overall_health(metrics)
        assert health == "improving"

    def test_determine_overall_health_declining(self, trends_tools):
        """Test overall health determination when declining."""
        metrics = {
            "cycle_time": {"change_direction": "regressed"},
            "merge_rate": {"change_direction": "regressed"},
            "ci_success": {"change_direction": "stable"},
        }
        health = trends_tools._determine_overall_health(metrics)
        assert health == "declining"

    def test_determine_overall_health_stable(self, trends_tools):
        """Test overall health determination when stable."""
        metrics = {
            "cycle_time": {"change_direction": "improved"},
            "merge_rate": {"change_direction": "regressed"},
            "ci_success": {"change_direction": "stable"},
        }
        health = trends_tools._determine_overall_health(metrics)
        assert health == "stable"

    def test_safe_float_helper(self, trends_tools):
        """Test the _safe_float helper method."""
        assert trends_tools._safe_float(10.5) == 10.5
        assert trends_tools._safe_float("10.5") == 10.5
        assert trends_tools._safe_float(None) is None
        assert trends_tools._safe_float("invalid") is None

    def test_get_sample_size(self, trends_tools):
        """Test the _get_sample_size helper method."""
        assert trends_tools._get_sample_size({"pr_count": 10}) == 10
        assert trends_tools._get_sample_size({"total_prs": 15}) == 15
        assert trends_tools._get_sample_size({"total_runs": 100}) == 100
        assert trends_tools._get_sample_size({"incident_count": 5}) == 5
        assert trends_tools._get_sample_size({}) == 0

    def test_thresholds_defined(self, trends_tools):
        """Test that thresholds are properly defined for all metrics."""
        expected_metrics = [
            "cycle_time",
            "merge_rate",
            "retests_per_pr",
            "ci_success_rate",
            "coverage",
            "mttr",
        ]

        for metric in expected_metrics:
            assert metric in trends_tools.THRESHOLDS
            assert "improved" in trends_tools.THRESHOLDS[metric]
            assert "regressed" in trends_tools.THRESHOLDS[metric]

    @pytest.mark.asyncio
    async def test_get_repo_names(self, trends_tools, mock_db_connection):
        """Test the _get_repo_names helper method."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "data": [{"repo_name": "repo1"}, {"repo_name": "repo2"}],
        }

        repo_names = await trends_tools._get_repo_names("Test Project")

        assert repo_names == ["repo1", "repo2"]

    @pytest.mark.asyncio
    async def test_get_repo_names_empty(self, trends_tools, mock_db_connection):
        """Test the _get_repo_names helper when no repos found."""
        mock_db_connection.execute_query.return_value = {"success": True, "data": []}

        repo_names = await trends_tools._get_repo_names("Empty Project")

        assert repo_names == []
