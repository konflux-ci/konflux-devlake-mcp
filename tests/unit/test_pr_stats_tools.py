#!/usr/bin/env python3
"""
Unit Tests for PR Stats Tools
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from mcp.types import Tool
from toon_format import decode as toon_decode

from tools.devlake.pr_stats_tools import PRStatsTools


@pytest.mark.unit
class TestPRStatsTools:
    @pytest.fixture
    def stats_tools(self, mock_db_connection):
        return PRStatsTools(mock_db_connection)

    def _make_success_side_effect(self):
        return [
            {
                "success": True,
                "data": [
                    {
                        "id": "github:GithubRepo:1:123",
                        "name": "test-repo",
                        "url": "https://github.com/org/test-repo",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "pr_id": "pr1",
                        "title": "Add feature",
                        "url": "https://github.com/org/test-repo/pull/1",
                        "created_date": "2024-01-01",
                        "days_open": "5",
                        "additions": "10",
                        "deletions": "5",
                        "total_changes": "15",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "total_prs": "20",
                        "merged_prs": "15",
                        "open_prs": "3",
                        "closed_prs": "2",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "pr_type": "engineering",
                        "total_count": "15",
                        "open_count": "2",
                        "merged_count": "12",
                        "stale_14d": "1",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "pr_id": "pr2",
                        "title": "Old PR",
                        "url": "https://github.com/org/test-repo/pull/2",
                        "days_open": "15",
                        "total_changes": "30",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "total_prs": "20",
                        "merged_prs": "15",
                        "open_prs": "3",
                        "closed_prs": "2",
                        "stale_prs_7d": "2",
                        "stale_prs_14d": "1",
                    }
                ],
            },
        ]

    def test_get_tools(self, stats_tools):
        tool_list = stats_tools.get_tools()
        assert len(tool_list) == 1
        assert isinstance(tool_list[0], Tool)
        assert tool_list[0].name == "get_pr_stats"
        assert tool_list[0].inputSchema["required"] == ["project_name"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, stats_tools):
        result_toon = await stats_tools.call_tool("unknown", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Unknown PR stats tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, stats_tools):
        with patch.object(stats_tools, "_get_pr_stats", side_effect=Exception("boom")):
            result_toon = await stats_tools.call_tool("get_pr_stats", {})
            result = toon_decode(result_toon)
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_categorize_pr(self, stats_tools):
        assert stats_tools._categorize_pr("chore(deps): update foo") == "dependency_bot"
        assert stats_tools._categorize_pr("fix(deps): upgrade bar") == "dependency_bot"
        assert stats_tools._categorize_pr("Update Docker image") == "dependency_bot"
        assert stats_tools._categorize_pr("Bump version to 1.0") == "dependency_bot"
        assert stats_tools._categorize_pr("dependabot: update lodash") == "dependency_bot"
        assert stats_tools._categorize_pr("renovate: pin deps") == "dependency_bot"
        assert stats_tools._categorize_pr("update digest to abc") == "dependency_bot"
        assert stats_tools._categorize_pr("dependencies cleanup") == "dependency_bot"
        assert stats_tools._categorize_pr("DNM: experimental") == "wip_exclude"
        assert stats_tools._categorize_pr("WIP: work in progress") == "wip_exclude"
        assert stats_tools._categorize_pr("[WIP] draft feature") == "wip_exclude"
        assert stats_tools._categorize_pr("do not merge this") == "wip_exclude"
        assert stats_tools._categorize_pr("draft: new feature") == "wip_exclude"
        assert stats_tools._categorize_pr("[DNM] test") == "wip_exclude"
        assert stats_tools._categorize_pr("Add new feature") == "engineering"
        assert stats_tools._categorize_pr("Fix login bug") == "engineering"
        assert stats_tools._categorize_pr(None) == "engineering"
        assert stats_tools._categorize_pr("") == "engineering"

    @pytest.mark.asyncio
    async def test_get_pr_stats_missing_project(self, stats_tools):
        result_toon = await stats_tools.call_tool("get_pr_stats", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_stats_no_repos(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [{"success": True, "data": []}]
        result_toon = await stats_tools.call_tool("get_pr_stats", {"project_name": "Test"})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["summary"]["total_prs"] == 0
        assert result["open_prs"] == []

    @pytest.mark.asyncio
    async def test_get_pr_stats_success(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_success_side_effect()
        result_toon = await stats_tools.call_tool("get_pr_stats", {"project_name": "Test"})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["summary"]["total_prs"] == 20
        assert result["summary"]["merged_prs"] == 15
        assert len(result["open_prs"]) == 1
        assert result["open_prs"][0]["category"] == "engineering"
        assert "engineering" in result["pr_type_breakdown"]
        assert len(result["stale_prs"]) == 1

    @pytest.mark.asyncio
    async def test_get_pr_stats_with_days_back(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = self._make_success_side_effect()
        result_toon = await stats_tools.call_tool(
            "get_pr_stats", {"project_name": "Test", "days_back": 60}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["analysis_period_days"] == 60

    @pytest.mark.asyncio
    async def test_get_pr_stats_db_error(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=Exception("DB error"))
        result_toon = await stats_tools.call_tool("get_pr_stats", {"project_name": "Test"})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "DB error" in result["error"]

    @pytest.mark.asyncio
    async def test_get_pr_stats_partial_failure(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query.side_effect = [
            {
                "success": True,
                "data": [
                    {
                        "id": "github:GithubRepo:1:123",
                        "name": "test-repo",
                        "url": "https://...",
                    }
                ],
            },
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {
                "success": True,
                "data": [
                    {
                        "total_prs": "10",
                        "merged_prs": "8",
                        "open_prs": "1",
                        "closed_prs": "1",
                        "stale_prs_7d": "0",
                        "stale_prs_14d": "0",
                    }
                ],
            },
        ]
        result_toon = await stats_tools.call_tool("get_pr_stats", {"project_name": "Test"})
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["summary"]["total_prs"] == 10

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, stats_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(return_value={"success": True, "data": []})
        result = await stats_tools._execute_with_timeout("SELECT 1", 1)
        assert result == {"success": True, "data": []}

    @pytest.mark.asyncio
    async def test_execute_with_timeout_timeout(self, stats_tools):
        with patch(
            "tools.devlake.pr_stats_tools.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await stats_tools._execute_with_timeout("SELECT 1", 1, timeout=1)
        assert result["success"] is False
        assert "Query timeout" in result["error"]
