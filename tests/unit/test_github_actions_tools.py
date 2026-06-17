#!/usr/bin/env python3
"""
Unit Tests for GitHub Actions Tools
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from mcp.types import Tool
from toon_format import decode as toon_decode

from tools.devlake.github_actions_tools import GitHubActionsTools


@pytest.mark.unit
class TestGitHubActionsTools:
    @pytest.fixture
    def actions_tools(self, mock_db_connection):
        return GitHubActionsTools(mock_db_connection)

    def _make_success_side_effect(self):
        return [
            {"success": True, "data": [{"github_id": "123"}, {"github_id": "456"}]},
            {
                "success": True,
                "data": [
                    {
                        "total_jobs": "100",
                        "success_count": "85",
                        "failure_count": "15",
                        "success_rate": "85.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "total_jobs": "50",
                        "success": "40",
                        "failures": "10",
                        "success_rate": "80.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "workflow_name": "CI",
                        "total_runs": "20",
                        "failures": "3",
                        "failure_rate": "15.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "job_name": "build",
                        "total_jobs": "30",
                        "failures": "5",
                        "failure_rate": "16.7",
                        "status": "WARNING",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "test-repo",
                        "job_name": "e2e-test",
                        "total_jobs": "20",
                        "passes": "12",
                        "failures": "8",
                        "failure_rate": "40.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "date": "2024-01-15",
                        "total_jobs": "15",
                        "failures": "2",
                        "failure_rate": "13.3",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "day_of_week": "Monday",
                        "day_number": "2",
                        "total_jobs": "25",
                        "failures": "4",
                        "failure_rate": "16.0",
                    }
                ],
            },
        ]

    def test_get_tools(self, actions_tools):
        tools = actions_tools.get_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "get_github_actions_health"
        assert tools[0].inputSchema["required"] == ["project_name"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, actions_tools):
        result_toon = await actions_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Unknown GitHub Actions tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, actions_tools):
        with patch.object(
            actions_tools, "_get_github_actions_health", side_effect=Exception("boom")
        ):
            result_toon = await actions_tools.call_tool("get_github_actions_health", {})
            result = toon_decode(result_toon)
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_get_github_actions_health_missing_project(self, actions_tools):
        result_toon = await actions_tools.call_tool("get_github_actions_health", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "project_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_github_actions_health_no_repos(
        self, actions_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = [{"success": True, "data": []}]
        result_toon = await actions_tools.call_tool(
            "get_github_actions_health", {"project_name": "Test"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["executive_summary"]["total_jobs"] == 0
        assert result["repo_breakdown"] == []

    @pytest.mark.asyncio
    async def test_get_github_actions_health_success(
        self, actions_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_success_side_effect()
        result_toon = await actions_tools.call_tool(
            "get_github_actions_health", {"project_name": "Test"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["executive_summary"]["total_jobs"] == 100
        assert result["executive_summary"]["success_rate"] == 85.0
        assert result["executive_summary"]["flaky_job_count"] == 1
        assert len(result["repo_breakdown"]) == 1

    @pytest.mark.asyncio
    async def test_get_github_actions_health_with_days_back(
        self, actions_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = self._make_success_side_effect()
        result_toon = await actions_tools.call_tool(
            "get_github_actions_health", {"project_name": "Test", "days_back": 60}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["analysis_period"]["days_back"] == 60

    @pytest.mark.asyncio
    async def test_get_github_actions_health_db_error(
        self, actions_tools, mock_db_connection
    ):
        mock_db_connection.execute_query = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        result_toon = await actions_tools.call_tool(
            "get_github_actions_health", {"project_name": "Test"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "DB connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_github_actions_health_partial_failure(
        self, actions_tools, mock_db_connection
    ):
        mock_db_connection.execute_query.side_effect = [
            {"success": True, "data": [{"github_id": "123"}]},
            {
                "success": True,
                "data": [
                    {
                        "total_jobs": "50",
                        "success_count": "40",
                        "failure_count": "10",
                        "success_rate": "80.0",
                    }
                ],
            },
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
            {"success": True, "data": []},
        ]
        result_toon = await actions_tools.call_tool(
            "get_github_actions_health", {"project_name": "Test"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["executive_summary"]["total_jobs"] == 50
        assert result["executive_summary"]["flaky_job_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, actions_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(
            return_value={"success": True, "data": []}
        )
        result = await actions_tools._execute_with_timeout("SELECT 1", 1)
        assert result == {"success": True, "data": []}

    @pytest.mark.asyncio
    async def test_execute_with_timeout_timeout(self, actions_tools):
        with patch(
            "tools.devlake.github_actions_tools.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await actions_tools._execute_with_timeout("SELECT 1", 1, timeout=1)
        assert result["success"] is False
        assert "Query timeout" in result["error"]
