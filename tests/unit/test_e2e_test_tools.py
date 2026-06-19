#!/usr/bin/env python3
"""
Unit Tests for E2E Test Tools
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from mcp.types import Tool
from toon_format import decode as toon_decode

from tools.devlake.e2e_test_tools import E2ETestTools


@pytest.mark.unit
class TestE2ETestTools:
    @pytest.fixture
    def e2e_tools(self, mock_db_connection):
        return E2ETestTools(mock_db_connection)

    def _make_success_side_effect(self):
        return [
            {
                "success": True,
                "data": [
                    {
                        "repo_name": "integration-service",
                        "full_name": "org/integration-service",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "total_jobs": "100",
                        "passed": "85",
                        "failed": "10",
                        "aborted": "5",
                        "pass_rate": "85.0",
                        "unique_job_types": "5",
                        "unique_repos": "1",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "total_test_runs": "500",
                        "passed": "450",
                        "failed": "30",
                        "skipped": "20",
                        "pass_rate": "93.8",
                        "unique_tests": "50",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "job_name": "e2e-tests",
                        "repository": "integration-service",
                        "job_type": "presubmit",
                        "total_runs": "50",
                        "passed": "45",
                        "failed": "5",
                        "pass_rate": "90.0",
                        "avg_duration_sec": "120.5",
                        "last_run": "2024-01-15 10:00:00",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "job_name": "e2e-tests",
                        "repository": "integration-service",
                        "test_name": "TestLogin",
                        "classname": "auth",
                        "total_runs": "10",
                        "passed": "7",
                        "failed": "3",
                        "failure_rate": "30.0",
                        "avg_duration": "5.5",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "job_name": "e2e-tests",
                        "repository": "integration-service",
                        "test_name": "TestFlaky",
                        "total_runs": "20",
                        "passed": "12",
                        "failed": "8",
                        "failure_rate": "40.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "repository": "integration-service",
                        "organization": "org",
                        "total_jobs": "100",
                        "unique_job_types": "5",
                        "passed": "85",
                        "failed": "10",
                        "pass_rate": "85.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "date": "2024-01-15",
                        "total_jobs": "10",
                        "passed": "8",
                        "failed": "2",
                        "pass_rate": "80.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "week": "202403",
                        "week_start": "2024-01-15",
                        "total_jobs": "50",
                        "passed": "42",
                        "failed": "8",
                        "pass_rate": "84.0",
                    }
                ],
            },
            {
                "success": True,
                "data": [
                    {
                        "job_name": "e2e-tests",
                        "repository": "integration-service",
                        "suite_name": "AuthSuite",
                        "total_runs": "10",
                        "total_tests": "100",
                        "total_failed": "5",
                        "total_skipped": "2",
                        "avg_duration": "30.5",
                    }
                ],
            },
        ]

    def test_get_tools(self, e2e_tools):
        tools = e2e_tools.get_tools()
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "analyze_e2e_tests"
        assert tools[0].inputSchema["required"] == ["project_name"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, e2e_tools):
        result_toon = await e2e_tools.call_tool("unknown_tool", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Unknown E2E test tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_exception(self, e2e_tools):
        with patch.object(e2e_tools, "_analyze_e2e_tests", side_effect=Exception("boom")):
            result_toon = await e2e_tools.call_tool("analyze_e2e_tests", {})
            result = toon_decode(result_toon)
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_classify_test_health(self, e2e_tools):
        assert e2e_tools._classify_test_health(0) == "healthy"
        assert e2e_tools._classify_test_health(4.9) == "healthy"
        assert e2e_tools._classify_test_health(5) == "warning"
        assert e2e_tools._classify_test_health(19.9) == "warning"
        assert e2e_tools._classify_test_health(20) == "flaky"
        assert e2e_tools._classify_test_health(79.9) == "flaky"
        assert e2e_tools._classify_test_health(80) == "broken"
        assert e2e_tools._classify_test_health(100) == "broken"

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_missing_args(self, e2e_tools):
        result_toon = await e2e_tools.call_tool("analyze_e2e_tests", {})
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "Either project_name or repo_name is required" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_no_repos(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=[{"success": True, "data": []}])
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests", {"project_name": "TestProject"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "No repositories found" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_success(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=self._make_success_side_effect())
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests", {"project_name": "TestProject"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["resolved_repos"] == ["integration-service"]
        assert result["executive_summary"]["total_job_runs"] == 100
        assert result["executive_summary"]["job_pass_rate"] == 85.0
        assert len(result["job_breakdown"]) == 1
        assert result["job_breakdown"][0]["health_status"] == "warning"

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_with_repo_filter(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=self._make_success_side_effect())
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests",
            {"project_name": "TestProject", "repo_name": "integration"},
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["repo_filter"] == "integration"

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_include_all_tests(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=self._make_success_side_effect())
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests",
            {"project_name": "TestProject", "include_all_tests": True},
        )
        result = toon_decode(result_toon)
        assert result["success"] is True
        assert result["test_filter"] == "all_tests"

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_repo_name_only(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(
            side_effect=self._make_success_side_effect()[1:]
        )
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests", {"repo_name": "integration-service"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_analyze_e2e_tests_db_error(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(side_effect=Exception("DB error"))
        result_toon = await e2e_tools.call_tool(
            "analyze_e2e_tests", {"project_name": "TestProject"}
        )
        result = toon_decode(result_toon)
        assert result["success"] is False
        assert "DB error" in result["error"]

    @pytest.mark.asyncio
    async def test_get_repos_for_project(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {"repo_name": "repo1", "full_name": "org/repo1"},
                    {"repo_name": "repo2", "full_name": "org/repo2"},
                ],
            }
        )
        repos = await e2e_tools._get_repos_for_project("TestProject")
        assert repos == ["repo1", "repo2"]

    @pytest.mark.asyncio
    async def test_get_repos_for_project_empty(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(return_value={"success": True, "data": []})
        repos = await e2e_tools._get_repos_for_project("TestProject")
        assert repos == []

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, e2e_tools, mock_db_connection):
        mock_db_connection.execute_query = AsyncMock(return_value={"success": True, "data": []})
        result = await e2e_tools._execute_with_timeout("SELECT 1", 1)
        assert result == {"success": True, "data": []}

    @pytest.mark.asyncio
    async def test_execute_with_timeout_timeout(self, e2e_tools):
        with patch(
            "tools.devlake.e2e_test_tools.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await e2e_tools._execute_with_timeout("SELECT 1", 1)
        assert result["success"] is False
        assert result["error"] == "Query timeout"
