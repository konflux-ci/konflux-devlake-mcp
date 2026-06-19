#!/usr/bin/env python3
"""
Unit Tests for PR Cycle Time Tools
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from mcp.types import Tool
from toon_format import decode as toon_decode

from tools.devlake.pr_cycle_time_tools import PRCycleTimeTools


@pytest.mark.unit
class TestPRCycleTimeTools:
    @pytest.fixture
    def tools(self, mock_db_connection):
        return PRCycleTimeTools(mock_db_connection)

    def _make_five_query_side_effect(self):
        return [
            {
                "success": True,
                "data": [
                    {
                        "merged_pr_count": "10",
                        "avg_cycle_time_hours": "24.5",
                        "avg_coding_time_hours": "12.0",
                        "avg_pickup_time_hours": "6.0",
                        "avg_review_time_hours": "6.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "5",
                        "avg_cycle_time_hours": "20.0",
                        "avg_coding_time_hours": "10.0",
                        "avg_pickup_time_hours": "5.0",
                        "avg_review_time_hours": "5.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "8",
                        "avg_cycle_time_hours": "22.0",
                        "avg_coding_time_hours": "11.0",
                        "avg_pickup_time_hours": "5.5",
                        "avg_review_time_hours": "5.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "repo_url": "https://github.com/org/test-repo",
                        "merged_pr_count": "3",
                        "avg_cycle_time_hours": "18.0",
                        "avg_coding_time_hours": "9.0",
                        "avg_pickup_time_hours": "4.5",
                        "avg_review_time_hours": "4.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "size_category": "XS (1-50 lines)",
                        "pr_count": "5",
                        "avg_cycle_time_hours": "10.0",
                        "avg_pickup_time_hours": "3.0",
                        "avg_review_time_hours": "3.0",
                    }
                ],
            },
        ]

    def test_get_tools(self, tools):
        tool_list = tools.get_tools()
        assert len(tool_list) == 1
        assert isinstance(tool_list[0], Tool)
        assert tool_list[0].name == "get_pr_cycle_time"
        assert tool_list[0].inputSchema["required"] == ["project_name"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, tools):
        result_toon = await tools.call_tool("unknown", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, tools):
        with patch.object(tools, "_get_pr_cycle_time", side_effect=Exception("boom")):
            result_toon = await tools.call_tool("get_pr_cycle_time", {})
            result = toon_decode(result_toon)
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_missing_project(self, tools):
        result_toon = await tools.call_tool("get_pr_cycle_time", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_with_defaults(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_five_query_side_effect()
        result_toon = await tools.call_tool("get_pr_cycle_time", {"project_name": "Test Project"})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["project_name"] == "Test Project"
        assert result["repo_filter"] == "all"
        pr_ct = result["pr_cycle_time"]
        assert pr_ct["merged_pr_count"] == 10
        assert pr_ct["avg_cycle_time_hours"] == 24.5
        assert "weekly_trends" in result
        assert "three_month_trend" in result
        assert "repository_breakdown" in result
        assert "size_analysis" in result
        assert mock_db_connection.execute_query.call_count == 5

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_with_dates(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_five_query_side_effect()
        result_toon = await tools.call_tool(
            "get_pr_cycle_time",
            {
                "project_name": "Test Project",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )
        result = toon_decode(result_toon)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_with_days_back(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_five_query_side_effect()
        result_toon = await tools.call_tool(
            "get_pr_cycle_time", {"project_name": "Test Project", "days_back": 60}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_with_repo_filter(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_five_query_side_effect()
        result_toon = await tools.call_tool(
            "get_pr_cycle_time",
            {"project_name": "Test Project", "repo_name": "integration-service"},
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["repo_filter"] == "integration-service"

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_no_repo_breakdown(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {
                "success": True,
                "data": [
                    {
                        "merged_pr_count": "10",
                        "avg_cycle_time_hours": "24.5",
                        "avg_coding_time_hours": "12.0",
                        "avg_pickup_time_hours": "6.0",
                        "avg_review_time_hours": "6.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "5",
                        "avg_cycle_time_hours": "20.0",
                        "avg_coding_time_hours": "10.0",
                        "avg_pickup_time_hours": "5.0",
                        "avg_review_time_hours": "5.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "8",
                        "avg_cycle_time_hours": "22.0",
                        "avg_coding_time_hours": "11.0",
                        "avg_pickup_time_hours": "5.5",
                        "avg_review_time_hours": "5.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "size_category": "XS (1-50 lines)",
                        "pr_count": "5",
                        "avg_cycle_time_hours": "10.0",
                        "avg_pickup_time_hours": "3.0",
                        "avg_review_time_hours": "3.0",
                    }
                ],
            },
        ]
        result_toon = await tools.call_tool(
            "get_pr_cycle_time",
            {"project_name": "Test Project", "include_repo_breakdown": False},
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert "repository_breakdown" not in result
        assert "size_analysis" in result

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_no_size_analysis(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {
                "success": True,
                "data": [
                    {
                        "merged_pr_count": "10",
                        "avg_cycle_time_hours": "24.5",
                        "avg_coding_time_hours": "12.0",
                        "avg_pickup_time_hours": "6.0",
                        "avg_review_time_hours": "6.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "5",
                        "avg_cycle_time_hours": "20.0",
                        "avg_coding_time_hours": "10.0",
                        "avg_pickup_time_hours": "5.0",
                        "avg_review_time_hours": "5.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "8",
                        "avg_cycle_time_hours": "22.0",
                        "avg_coding_time_hours": "11.0",
                        "avg_pickup_time_hours": "5.5",
                        "avg_review_time_hours": "5.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "repo_url": "https://github.com/org/test-repo",
                        "merged_pr_count": "3",
                        "avg_cycle_time_hours": "18.0",
                        "avg_coding_time_hours": "9.0",
                        "avg_pickup_time_hours": "4.5",
                        "avg_review_time_hours": "4.5",
                    }
                ],
            },
        ]
        result_toon = await tools.call_tool(
            "get_pr_cycle_time",
            {"project_name": "Test Project", "include_size_analysis": False},
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert "repository_breakdown" in result
        assert "size_analysis" not in result

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_db_error(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {"success": False, "error": "DB error"},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]
        result_toon = await tools.call_tool("get_pr_cycle_time", {"project_name": "Test Project"})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Failed to retrieve" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_no_data(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]
        result_toon = await tools.call_tool("get_pr_cycle_time", {"project_name": "Test Project"})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "No merged PRs" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_cycle_time_partial_failure(self, tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {
                "success": True,
                "data": [
                    {
                        "merged_pr_count": "10",
                        "avg_cycle_time_hours": "24.5",
                        "avg_coding_time_hours": "12.0",
                        "avg_pickup_time_hours": "6.0",
                        "avg_review_time_hours": "6.5",
                    }
                ],
            },
            Exception("weekly failed"),
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "merged_pr_count": "8",
                        "avg_cycle_time_hours": "22.0",
                        "avg_coding_time_hours": "11.0",
                        "avg_pickup_time_hours": "5.5",
                        "avg_review_time_hours": "5.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "repo_url": "https://github.com/org/test-repo",
                        "merged_pr_count": "3",
                        "avg_cycle_time_hours": "18.0",
                        "avg_coding_time_hours": "9.0",
                        "avg_pickup_time_hours": "4.5",
                        "avg_review_time_hours": "4.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "size_category": "XS (1-50 lines)",
                        "pr_count": "5",
                        "avg_cycle_time_hours": "10.0",
                        "avg_pickup_time_hours": "3.0",
                        "avg_review_time_hours": "3.0",
                    }
                ],
            },
        ]
        result_toon = await tools.call_tool("get_pr_cycle_time", {"project_name": "Test Project"})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert "weekly_trends" not in result
        assert "three_month_trend" in result

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(return_value={"success": True, "data": []})
        result = await tools._execute_with_timeout("SELECT 1", 1)
        assert result == {"success": True, "data": []}

    @pytest.mark.asyncio
    async def test_execute_with_timeout_timeout(self, tools):
        with patch(
            "tools.devlake.pr_cycle_time_tools.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await tools._execute_with_timeout("SELECT 1", 1, timeout=1)
        assert result["success"] is False
        assert result["data"] == []
        assert "Query timeout" in result["error"]
