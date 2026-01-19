#!/usr/bin/env python3
"""
GitHub Actions Health Analysis Tools for Konflux DevLake MCP Server

Contains tools for analyzing GitHub Actions CI health metrics including
job success rates, flaky jobs, workflow failures, and trend analysis.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class GitHubActionsTools(BaseTool):
    """
    GitHub Actions Health Analysis tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing GitHub Actions CI health metrics,
    identifying flaky jobs, workflow failures, and providing trend analysis.
    """

    def __init__(self, db_connection):
        """
        Initialize GitHub Actions tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.GitHubActionsTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all GitHub Actions analysis tools.

        Returns:
            List of Tool objects for GitHub Actions operations
        """
        return [
            Tool(
                name="get_github_actions_health",
                description=(
                    "**GitHub Actions CI Health Analysis Tool** - Provides comprehensive "
                    "GitHub Actions job and workflow metrics for a DevLake project. Returns "
                    "repository breakdown, top failing jobs, flaky jobs (20-80% failure rate), "
                    "workflow failures, daily failure trends, and day-of-week analysis. "
                    "Essential for identifying CI reliability issues and bottlenecks."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name (e.g., 'Secureflow - Konflux - Build Team')"
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to analyze (default: 30)",
                        },
                    },
                    "required": ["project_name"],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a GitHub Actions tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_github_actions_health":
                result = await self._get_github_actions_health(arguments)
            else:
                result = {"success": False, "error": f"Unknown GitHub Actions tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"GitHub Actions tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _execute_with_timeout(
        self, query: str, limit: int, timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Execute query with timeout.

        Args:
            query: SQL query to execute
            limit: Maximum number of rows to return
            timeout: Timeout in seconds (default: 60)

        Returns:
            Query result dictionary
        """
        try:
            return await asyncio.wait_for(
                self.db_connection.execute_query(query, limit), timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Query timed out after {timeout}s")
            return {"success": False, "data": [], "error": "Query timeout"}

    async def _get_github_actions_health(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive GitHub Actions CI health metrics.

        Uses optimized queries with repo ID pre-fetch and parallel execution.

        Args:
            arguments: Tool arguments containing project_name and days_back

        Returns:
            Dictionary with GitHub Actions health analysis
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 30)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Step 1: Get repo github_ids for this project (fast query to avoid CONCAT in JOINs)
            repo_ids_query = f"""
                SELECT DISTINCT SUBSTRING_INDEX(pm.row_id, ':', -1) as github_id
                FROM lake.project_mapping pm
                WHERE pm.project_name = '{project_name}'
                AND pm.row_id LIKE 'github:GithubRepo:1:%'
            """
            repo_ids_result = await self._execute_with_timeout(repo_ids_query, 500, timeout=30)

            if not repo_ids_result.get("success") or not repo_ids_result.get("data"):
                return {
                    "success": True,
                    "message": "No repositories found for project",
                    "project_name": project_name,
                    "executive_summary": {
                        "total_jobs": 0,
                        "success_count": 0,
                        "failure_count": 0,
                        "success_rate": 0.0,
                        "flaky_job_count": 0,
                    },
                    "repo_breakdown": [],
                    "workflow_failures": [],
                    "top_failing_jobs": [],
                    "flaky_jobs": [],
                    "daily_trend": [],
                    "day_of_week_analysis": [],
                }

            repo_ids = [str(r["github_id"]) for r in repo_ids_result["data"]]
            repo_ids_str = ",".join(repo_ids)

            # Step 2: Build optimized queries using IN clause instead of JOIN + CONCAT
            # Query 1: Executive Summary
            summary_query = f"""
                SELECT
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'success' THEN gj.id END)
                        as success_count,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failure_count,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'success' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as success_rate
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
            """

            # Query 2: Repository Breakdown
            repo_query = f"""
                SELECT
                    r.name as repo_name,
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'success' THEN gj.id END)
                        as success,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'success' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as success_rate
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                INNER JOIN lake._tool_github_repos r ON gr.repo_id = r.github_id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
                GROUP BY r.name
                ORDER BY total_jobs DESC
            """

            # Query 3: Workflow Failures
            workflow_query = f"""
                SELECT
                    r.name as repo_name,
                    gr.name as workflow_name,
                    COUNT(DISTINCT gr.id) as total_runs,
                    COUNT(DISTINCT CASE WHEN gr.conclusion = 'failure' THEN gr.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gr.conclusion = 'failure' THEN gr.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gr.id), 0), 1) as failure_rate
                FROM lake._tool_github_runs gr
                INNER JOIN lake._tool_github_repos r ON gr.repo_id = r.github_id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gr.created_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gr.conclusion IN ('success', 'failure')
                GROUP BY r.name, gr.name
                HAVING failures > 0
                ORDER BY failures DESC
                LIMIT 20
            """

            # Query 4: Top Failing Jobs
            failing_jobs_query = f"""
                SELECT
                    r.name as repo_name,
                    gj.name as job_name,
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as failure_rate,
                    CASE
                        WHEN COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                            * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0) > 80 THEN 'BROKEN'
                        WHEN COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                            * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0) BETWEEN 20 AND 80
                            THEN 'FLAKY'
                        WHEN COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                            * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0) BETWEEN 10 AND 20
                            THEN 'WARNING'
                        ELSE 'STABLE'
                    END as status
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                INNER JOIN lake._tool_github_repos r ON gr.repo_id = r.github_id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
                GROUP BY r.name, gj.name
                HAVING failures > 0
                ORDER BY failures DESC
                LIMIT 20
            """

            # Query 5: Flaky Jobs (20-80% failure rate, minimum 5 runs)
            flaky_jobs_query = f"""
                SELECT
                    r.name as repo_name,
                    gj.name as job_name,
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'success' THEN gj.id END)
                        as passes,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as failure_rate
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                INNER JOIN lake._tool_github_repos r ON gr.repo_id = r.github_id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
                GROUP BY r.name, gj.name
                HAVING COUNT(DISTINCT gj.id) >= 5
                   AND COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                       * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0) BETWEEN 20 AND 80
                ORDER BY failures DESC
                LIMIT 30
            """

            # Query 6: Daily Trend
            daily_trend_query = f"""
                SELECT
                    DATE(gj.started_at) as date,
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as failure_rate
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
                GROUP BY DATE(gj.started_at)
                ORDER BY date DESC
                LIMIT 30
            """

            # Query 7: Day of Week Analysis
            day_of_week_query = f"""
                SELECT
                    DAYNAME(gj.started_at) as day_of_week,
                    DAYOFWEEK(gj.started_at) as day_number,
                    COUNT(DISTINCT gj.id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        as failures,
                    ROUND(COUNT(DISTINCT CASE WHEN gj.conclusion = 'failure' THEN gj.id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT gj.id), 0), 1) as failure_rate
                FROM lake._tool_github_jobs gj
                INNER JOIN lake._tool_github_runs gr ON gj.run_id = gr.id
                WHERE gr.repo_id IN ({repo_ids_str})
                AND gj.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND gj.conclusion IN ('success', 'failure')
                GROUP BY DAYNAME(gj.started_at), DAYOFWEEK(gj.started_at)
                ORDER BY day_number
            """

            # Step 3: Run all queries in parallel with timeouts
            results = await asyncio.gather(
                self._execute_with_timeout(summary_query, 1, timeout=60),
                self._execute_with_timeout(repo_query, 100, timeout=60),
                self._execute_with_timeout(workflow_query, 20, timeout=60),
                self._execute_with_timeout(failing_jobs_query, 20, timeout=60),
                self._execute_with_timeout(flaky_jobs_query, 30, timeout=60),
                self._execute_with_timeout(daily_trend_query, 30, timeout=60),
                self._execute_with_timeout(day_of_week_query, 7, timeout=60),
                return_exceptions=True,
            )

            # Unpack results
            (
                summary_result,
                repo_result,
                workflow_result,
                failing_jobs_result,
                flaky_jobs_result,
                daily_trend_result,
                day_of_week_result,
            ) = results

            # Handle any exceptions from parallel execution
            def safe_get_data(result, default=None):
                if default is None:
                    default = []
                if isinstance(result, Exception):
                    self.logger.error(f"Query failed with exception: {result}")
                    return default
                if not result.get("success"):
                    return default
                return result.get("data", default)

            summary_data = {}
            if not isinstance(summary_result, Exception) and summary_result.get("success"):
                summary_data = summary_result["data"][0] if summary_result["data"] else {}

            repo_breakdown = safe_get_data(repo_result)
            workflow_failures = safe_get_data(workflow_result)
            top_failing_jobs = safe_get_data(failing_jobs_result)
            flaky_jobs = safe_get_data(flaky_jobs_result)
            daily_trend = safe_get_data(daily_trend_result)
            day_of_week_analysis = safe_get_data(day_of_week_result)

            # Convert MySQL Decimal types to Python floats/ints
            def convert_numeric(value, default=0):
                if value is None:
                    return default
                return float(value) if "." in str(value) else int(float(value))

            return {
                "success": True,
                "generated_at": datetime.now().isoformat(),
                "project_name": project_name,
                "analysis_period": {
                    "days_back": days_back,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                },
                "executive_summary": {
                    "total_jobs": convert_numeric(summary_data.get("total_jobs", 0)),
                    "success_count": convert_numeric(summary_data.get("success_count", 0)),
                    "failure_count": convert_numeric(summary_data.get("failure_count", 0)),
                    "success_rate": convert_numeric(summary_data.get("success_rate", 0.0), 0.0),
                    "flaky_job_count": len(flaky_jobs),
                },
                "repo_breakdown": repo_breakdown,
                "workflow_failures": workflow_failures,
                "top_failing_jobs": top_failing_jobs,
                "flaky_jobs": flaky_jobs,
                "daily_trend": daily_trend,
                "day_of_week_analysis": day_of_week_analysis,
            }

        except Exception as e:
            self.logger.error(f"Get GitHub Actions health failed: {e}")
            return {"success": False, "error": str(e)}
