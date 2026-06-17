#!/usr/bin/env python3
"""
Unit Tests for PR Retest Tools
"""

import pytest
from unittest.mock import AsyncMock, patch

from toon_format import decode as toon_decode

from tools.devlake.pr_retest_tools import PRRetestTools
from mcp.types import Tool


@pytest.mark.unit
class TestPRRetestTools:
    @pytest.fixture
    def retest_tools(self, mock_db_connection):
        return PRRetestTools(mock_db_connection)

    def _make_default_side_effect(self):
        return [
            {"success": True, "data": [{"total_retests": "25", "affected_prs": "10"}]},
            {
                "success": True,
                "data": [
                    {
                        "pr_id": "1",
                        "title": "Fix bug",
                        "url": "https://github.com/org/repo/pull/1",
                        "status": "MERGED",
                        "created_date": "2024-01-01",
                        "merged_date": "2024-01-05",
                        "closed_date": None,
                        "additions": "10",
                        "deletions": "5",
                        "repo_name": "test-repo",
                        "retest_count": "5",
                        "pr_duration_days": "4",
                    }
                ],
            },
            {"success": True, "data": [{"date": "2024-01-01", "retest_count": "3"}]},
            {
                "success": True,
                "data": [
                    {"category": "Bug Fixes", "pr_count": "5", "total_retests": "15"}
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "status": "MERGED",
                        "pr_count": "8",
                        "total_retests": "20",
                        "avg_retests": "2.5",
                        "avg_changes": "100",
                        "avg_duration_days": "5.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "total_retests": "25",
                        "affected_prs": "10",
                        "avg_retests_per_pr": "2.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202401",
                        "week_start": "2024-01-01",
                        "retest_count": "10",
                        "affected_prs": "5",
                    }
                ],
            },
        ]

    def test_get_tools(self, retest_tools):
        tools = retest_tools.get_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "analyze_pr_retests"
        assert tools[0].inputSchema["required"] == []

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, retest_tools):
        result_toon = await retest_tools.call_tool("unknown", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Unknown PR retest tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, retest_tools):
        with patch.object(
            retest_tools, "_analyze_pr_retests_tool", side_effect=Exception("boom")
        ):
            result_toon = await retest_tools.call_tool("analyze_pr_retests", {})
            result = toon_decode(result_toon)
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_defaults(self, retest_tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_default_side_effect()
        result_toon = await retest_tools.call_tool("analyze_pr_retests", {})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["executive_summary"]["total_manual_retest_comments"] == 25
        assert result["executive_summary"]["number_of_affected_prs"] == 10
        assert result["executive_summary"]["average_retests_per_pr"] == 2.5
        assert len(result["top_prs_by_retests"]) == 1
        pr = result["top_prs_by_retests"][0]
        assert pr["repo_name"] == "test-repo"
        assert pr["retest_count"] == 5
        assert pr["changes"]["total"] == 15

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_with_project(
        self, retest_tools, mock_db_connection
    ):
        side_effect = [
            {"success": True, "data": [{"name": "test-repo"}]}
        ] + self._make_default_side_effect()
        mock_db_connection.execute_query.side_effect = side_effect
        result_toon = await retest_tools.call_tool(
            "analyze_pr_retests", {"project_name": "TestProject"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["filters"]["project_name"] == "TestProject"
        assert result["filters"]["resolved_repos"] == ["test-repo"]

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_with_repo_name(
        self, retest_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_default_side_effect()
        result_toon = await retest_tools.call_tool(
            "analyze_pr_retests", {"repo_name": "integration-service"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["filters"]["repo_name"] == "integration-service"

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_with_dates(
        self, retest_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_default_side_effect()
        result_toon = await retest_tools.call_tool(
            "analyze_pr_retests", {"start_date": "2024-01-01", "end_date": "2024-03-31"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert "2024-01-01" in result["analysis_period"]["start_date"]
        assert "2024-03-31" in result["analysis_period"]["end_date"]

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_with_days_back(
        self, retest_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_default_side_effect()
        result_toon = await retest_tools.call_tool(
            "analyze_pr_retests", {"days_back": 60}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["analysis_period"]["days_back"] == 60

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_exclude_bots_false(
        self, retest_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_default_side_effect()
        result_toon = await retest_tools.call_tool(
            "analyze_pr_retests", {"exclude_bots": False}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["filters"]["exclude_bots"] is False

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_db_error(self, retest_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        result_toon = await retest_tools.call_tool("analyze_pr_retests", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "DB connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_pr_retests_empty_results(
        self, retest_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"total_retests": "0", "affected_prs": "0"}]},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]
        result_toon = await retest_tools.call_tool("analyze_pr_retests", {})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["executive_summary"]["total_manual_retest_comments"] == 0
        assert len(result["top_prs_by_retests"]) == 0

    def test_analyze_patterns(self, retest_tools):
        pattern_analysis = [
            {"status": "MERGED", "avg_retests": "3.5"},
            {"status": "CLOSED", "avg_retests": "1.0"},
        ]
        category_breakdown = [
            {"category": "Bug Fixes", "total_retests": "20", "pr_count": "5"},
            {"category": "Features", "total_retests": "10", "pr_count": "3"},
        ]
        insights = retest_tools._analyze_patterns(pattern_analysis, category_breakdown)
        assert len(insights) == 2
        assert "MERGED" in insights[0]
        assert "Bug Fixes" in insights[1]

    def test_analyze_patterns_empty(self, retest_tools):
        assert retest_tools._analyze_patterns([], []) == []

    @pytest.mark.asyncio
    async def test_get_repos_for_project(self, retest_tools, mock_db_connection):
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "data": [{"name": "repo1"}, {"name": "repo2"}],
        }
        repos = await retest_tools._get_repos_for_project("TestProject")
        assert repos == ["repo1", "repo2"]

    @pytest.mark.asyncio
    async def test_get_repos_for_project_empty(self, retest_tools, mock_db_connection):
        mock_db_connection.execute_query.return_value = {"success": True, "data": []}
        repos = await retest_tools._get_repos_for_project("TestProject")
        assert repos == []
