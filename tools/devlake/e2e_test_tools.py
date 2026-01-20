#!/usr/bin/env python3
"""
E2E Test Analysis Tools for Konflux DevLake MCP Server

Contains tools for analyzing end-to-end and integration test results from Prow/Tekton
CI systems using the test registry data (ci_test_jobs, ci_test_cases, ci_test_suites).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class E2ETestTools(BaseTool):
    """
    E2E Test Analysis tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing end-to-end and integration test results
    from Prow/Tekton CI systems, identifying flaky tests, and providing actionable insights.
    Uses test registry tables: ci_test_jobs, ci_test_cases, ci_test_suites.
    """

    def __init__(self, db_connection):
        """
        Initialize E2E test tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.E2ETestTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all E2E test analysis tools.

        Returns:
            List of Tool objects for E2E test operations
        """
        return [
            Tool(
                name="analyze_e2e_tests",
                description=(
                    "**Comprehensive E2E Test Analysis Tool** - Analyzes end-to-end and "
                    "integration test results for a DevLake project/repository. Automatically "
                    "resolves project_name to team repositories via project_mapping. "
                    "Uses Prow/Tekton test registry data (ci_test_jobs, ci_test_cases). "
                    "Provides: executive summary with pass/fail rates, test-by-test breakdown, "
                    "flaky test detection (20-80% failure rate), failure trends, duration metrics, "
                    "and per-repository breakdown. Essential for understanding E2E test health."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name "
                                "(e.g., 'Secureflow - Konflux - Integration Team'). "
                                "Resolves to team repositories via project_mapping."
                            ),
                        },
                        "repo_name": {
                            "type": "string",
                            "description": (
                                "Optional: Filter by repository name (partial match). "
                                "e.g., 'integration-service', 'build-service'. "
                                "Applied after project_name resolution."
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to analyze (default: 30)",
                        },
                        "include_all_tests": {
                            "type": "boolean",
                            "description": (
                                "Include ALL tests, not just E2E/integration tests. "
                                "Default: false (only E2E tests)"
                            ),
                        },
                    },
                    "required": ["project_name"],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute an E2E test tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "analyze_e2e_tests":
                result = await self._analyze_e2e_tests(arguments)
            else:
                result = {"success": False, "error": f"Unknown E2E test tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"E2E test tool call failed: {e}")
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

    async def _get_repos_for_project(self, project_name: str) -> List[str]:
        """
        Get repository names for a DevLake project from project_mapping.

        Returns short repo names (e.g., 'integration-service') that match
        the repository column in ci_test_jobs.

        Args:
            project_name: DevLake project name

        Returns:
            List of repository names belonging to the project
        """
        # Get repo names from project_mapping via _tool_github_repos
        # Note: COLLATE needed due to MySQL collation mismatch between tables
        query = f"""
            SELECT DISTINCT
                SUBSTRING_INDEX(r.name, '/', -1) as repo_name,
                r.name as full_name
            FROM lake.project_mapping pm
            INNER JOIN lake._tool_github_repos r
                ON SUBSTRING_INDEX(pm.row_id, ':', -1) COLLATE utf8mb4_general_ci
                   = CAST(r.github_id AS CHAR) COLLATE utf8mb4_general_ci
            WHERE pm.project_name = '{project_name}'
            AND pm.row_id LIKE 'github:GithubRepo:%'
        """
        result = await self._execute_with_timeout(query, 500, timeout=30)

        if result.get("success") and result.get("data"):
            # Return short repo names (matching ci_test_jobs.repository format)
            return [row["repo_name"] for row in result["data"] if row.get("repo_name")]
        return []

    def _classify_test_health(self, failure_rate: float) -> str:
        """
        Classify test health status based on failure rate.

        Args:
            failure_rate: Failure rate percentage (0-100)

        Returns:
            Status string: 'healthy', 'warning', 'flaky', 'broken'
        """
        if failure_rate < 5:
            return "healthy"
        elif failure_rate < 20:
            return "warning"
        elif failure_rate < 80:
            return "flaky"
        else:
            return "broken"

    async def _analyze_e2e_tests(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze E2E and integration test results from Prow/Tekton test registry.

        Uses ci_test_jobs, ci_test_cases, and ci_test_suites tables.
        Properly filters by team repositories via project_mapping.

        Args:
            arguments: Tool arguments

        Returns:
            Dictionary with comprehensive E2E test analysis
        """
        try:
            project_name = arguments.get("project_name", "")
            repo_name = arguments.get("repo_name", "")
            days_back = arguments.get("days_back", 30)
            include_all_tests = arguments.get("include_all_tests", False)

            if not project_name and not repo_name:
                return {"success": False, "error": "Either project_name or repo_name is required"}

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Step 1: Resolve project_name to team repository names
            target_repos = []
            if project_name:
                target_repos = await self._get_repos_for_project(project_name)
                self.logger.info(f"Resolved {len(target_repos)} repos for project '{project_name}'")

            if project_name and not target_repos:
                self.logger.warning(f"No repositories found for project: {project_name}")
                return {
                    "success": False,
                    "error": f"No repositories found for project: {project_name}",
                    "hint": "Check that the project_name exists in project_mapping",
                }

            # Step 2: Build repository filter
            # Filter by team repos AND optional repo_name pattern
            repo_filter = ""
            if target_repos:
                # Escape single quotes and build IN clause
                escaped_repos = [r.replace("'", "''") for r in target_repos]
                repo_names_sql = "', '".join(escaped_repos)
                repo_filter = f" AND j.repository IN ('{repo_names_sql}')"

                # If repo_name is also specified, further filter
                if repo_name:
                    repo_filter += f" AND j.repository LIKE '%{repo_name}%'"
            elif repo_name:
                # No project_name, just filter by repo_name pattern
                repo_filter = f" AND j.repository LIKE '%{repo_name}%'"

            # Build test filter for E2E tests only
            test_filter = ""
            if not include_all_tests:
                test_filter = """
                    AND (
                        LOWER(j.job_name) LIKE '%e2e%'
                        OR LOWER(j.job_name) LIKE '%integration%'
                        OR LOWER(j.job_name) LIKE '%test%'
                    )
                """

            # Query 1: Job-level summary (Prow/Tekton jobs)
            job_summary_query = f"""
                SELECT
                    COUNT(DISTINCT j.job_id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END) as passed,
                    COUNT(DISTINCT CASE WHEN j.result = 'FAILURE' THEN j.job_id END) as failed,
                    COUNT(DISTINCT CASE WHEN j.result = 'ABORTED' THEN j.job_id END) as aborted,
                    ROUND(COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT j.job_id), 0), 1) as pass_rate,
                    COUNT(DISTINCT j.job_name) as unique_job_types,
                    COUNT(DISTINCT j.repository) as unique_repos
                FROM lake.ci_test_jobs j
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND j.result IN ('SUCCESS', 'FAILURE', 'ABORTED')
                {repo_filter}
                {test_filter}
            """

            # Query 2: Test case summary
            test_case_summary_query = f"""
                SELECT
                    COUNT(DISTINCT CONCAT(tc.job_id, tc.test_case_id)) as total_test_runs,
                    COUNT(DISTINCT CASE WHEN tc.status = 'passed' THEN
                        CONCAT(tc.job_id, tc.test_case_id) END) as passed,
                    COUNT(DISTINCT CASE WHEN tc.status = 'failed' THEN
                        CONCAT(tc.job_id, tc.test_case_id) END) as failed,
                    COUNT(DISTINCT CASE WHEN tc.status = 'skipped' THEN
                        CONCAT(tc.job_id, tc.test_case_id) END) as skipped,
                    ROUND(COUNT(DISTINCT CASE WHEN tc.status = 'passed' THEN
                        CONCAT(tc.job_id, tc.test_case_id) END) * 100.0 /
                        NULLIF(COUNT(DISTINCT CASE WHEN tc.status IN ('passed', 'failed') THEN
                        CONCAT(tc.job_id, tc.test_case_id) END), 0), 1) as pass_rate,
                    COUNT(DISTINCT tc.name) as unique_tests
                FROM lake.ci_test_cases tc
                INNER JOIN lake.ci_test_jobs j
                    ON tc.connection_id = j.connection_id AND tc.job_id = j.job_id
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                {repo_filter}
                {test_filter}
            """

            # Query 3: Job breakdown by name and result
            job_breakdown_query = f"""
                SELECT
                    j.job_name,
                    j.repository,
                    j.job_type,
                    COUNT(DISTINCT j.job_id) as total_runs,
                    COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END) as passed,
                    COUNT(DISTINCT CASE WHEN j.result = 'FAILURE' THEN j.job_id END) as failed,
                    ROUND(COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT j.job_id), 0), 1) as pass_rate,
                    ROUND(AVG(j.duration_sec), 1) as avg_duration_sec,
                    MAX(j.started_at) as last_run
                FROM lake.ci_test_jobs j
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND j.result IN ('SUCCESS', 'FAILURE', 'ABORTED')
                {repo_filter}
                {test_filter}
                GROUP BY j.job_name, j.repository, j.job_type
                ORDER BY total_runs DESC
                LIMIT 50
            """

            # Query 4: Top failing test cases
            failing_tests_query = f"""
                SELECT
                    j.job_name,
                    j.repository,
                    SUBSTRING(tc.name, 1, 200) as test_name,
                    tc.classname,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN tc.status = 'passed' THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END) as failed,
                    ROUND(SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END)
                        * 100.0 / COUNT(*), 1) as failure_rate,
                    ROUND(AVG(tc.duration), 2) as avg_duration
                FROM lake.ci_test_cases tc
                INNER JOIN lake.ci_test_jobs j
                    ON tc.connection_id = j.connection_id AND tc.job_id = j.job_id
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND tc.status IN ('passed', 'failed')
                {repo_filter}
                {test_filter}
                GROUP BY j.job_name, j.repository, tc.name, tc.classname
                HAVING failed > 0
                ORDER BY failed DESC
                LIMIT 30
            """

            # Query 5: Flaky tests (20-80% failure rate, min 5 runs)
            flaky_tests_query = f"""
                SELECT
                    j.job_name,
                    j.repository,
                    SUBSTRING(tc.name, 1, 200) as test_name,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN tc.status = 'passed' THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END) as failed,
                    ROUND(SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END)
                        * 100.0 / COUNT(*), 1) as failure_rate
                FROM lake.ci_test_cases tc
                INNER JOIN lake.ci_test_jobs j
                    ON tc.connection_id = j.connection_id AND tc.job_id = j.job_id
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND tc.status IN ('passed', 'failed')
                {repo_filter}
                {test_filter}
                GROUP BY j.job_name, j.repository, tc.name
                HAVING COUNT(*) >= 5
                   AND SUM(CASE WHEN tc.status = 'failed' THEN 1 ELSE 0 END)
                       * 100.0 / COUNT(*) BETWEEN 20 AND 80
                ORDER BY failure_rate DESC
                LIMIT 30
            """

            # Query 6: Repository breakdown
            repo_breakdown_query = f"""
                SELECT
                    j.repository,
                    j.organization,
                    COUNT(DISTINCT j.job_id) as total_jobs,
                    COUNT(DISTINCT j.job_name) as unique_job_types,
                    COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END) as passed,
                    COUNT(DISTINCT CASE WHEN j.result = 'FAILURE' THEN j.job_id END) as failed,
                    ROUND(COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT j.job_id), 0), 1) as pass_rate
                FROM lake.ci_test_jobs j
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND j.result IN ('SUCCESS', 'FAILURE', 'ABORTED')
                {repo_filter}
                {test_filter}
                GROUP BY j.repository, j.organization
                ORDER BY total_jobs DESC
                LIMIT 50
            """

            # Query 7: Daily trend
            daily_trend_query = f"""
                SELECT
                    DATE(j.started_at) as date,
                    COUNT(DISTINCT j.job_id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END) as passed,
                    COUNT(DISTINCT CASE WHEN j.result = 'FAILURE' THEN j.job_id END) as failed,
                    ROUND(COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT j.job_id), 0), 1) as pass_rate
                FROM lake.ci_test_jobs j
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND j.result IN ('SUCCESS', 'FAILURE', 'ABORTED')
                {repo_filter}
                {test_filter}
                GROUP BY DATE(j.started_at)
                ORDER BY date DESC
                LIMIT 30
            """

            # Query 8: Weekly trend
            weekly_trend_query = f"""
                SELECT
                    YEARWEEK(j.started_at, 1) as week,
                    MIN(DATE(j.started_at)) as week_start,
                    COUNT(DISTINCT j.job_id) as total_jobs,
                    COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END) as passed,
                    COUNT(DISTINCT CASE WHEN j.result = 'FAILURE' THEN j.job_id END) as failed,
                    ROUND(COUNT(DISTINCT CASE WHEN j.result = 'SUCCESS' THEN j.job_id END)
                        * 100.0 / NULLIF(COUNT(DISTINCT j.job_id), 0), 1) as pass_rate
                FROM lake.ci_test_jobs j
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND j.result IN ('SUCCESS', 'FAILURE', 'ABORTED')
                {repo_filter}
                {test_filter}
                GROUP BY YEARWEEK(j.started_at, 1)
                ORDER BY week DESC
                LIMIT 12
            """

            # Query 9: Test suite summary
            suite_summary_query = f"""
                SELECT
                    j.job_name,
                    j.repository,
                    ts.name as suite_name,
                    COUNT(*) as total_runs,
                    SUM(ts.num_tests) as total_tests,
                    SUM(ts.num_failed) as total_failed,
                    SUM(ts.num_skipped) as total_skipped,
                    ROUND(AVG(ts.duration), 1) as avg_duration
                FROM lake.ci_test_suites ts
                INNER JOIN lake.ci_test_jobs j
                    ON ts.connection_id = j.connection_id AND ts.job_id = j.job_id
                WHERE j.started_at >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                {repo_filter}
                {test_filter}
                GROUP BY j.job_name, j.repository, ts.name
                ORDER BY total_runs DESC
                LIMIT 30
            """

            # Execute all queries in parallel
            results = await asyncio.gather(
                self._execute_with_timeout(job_summary_query, 1, timeout=60),
                self._execute_with_timeout(test_case_summary_query, 1, timeout=60),
                self._execute_with_timeout(job_breakdown_query, 50, timeout=60),
                self._execute_with_timeout(failing_tests_query, 30, timeout=60),
                self._execute_with_timeout(flaky_tests_query, 30, timeout=60),
                self._execute_with_timeout(repo_breakdown_query, 50, timeout=60),
                self._execute_with_timeout(daily_trend_query, 30, timeout=60),
                self._execute_with_timeout(weekly_trend_query, 12, timeout=60),
                self._execute_with_timeout(suite_summary_query, 30, timeout=60),
                return_exceptions=True,
            )

            (
                job_summary_result,
                test_case_summary_result,
                job_breakdown_result,
                failing_tests_result,
                flaky_tests_result,
                repo_breakdown_result,
                daily_trend_result,
                weekly_trend_result,
                suite_summary_result,
            ) = results

            # Helper function to safely extract data
            def safe_get_data(result, default=None):
                if default is None:
                    default = []
                if isinstance(result, Exception):
                    self.logger.error(f"Query failed: {result}")
                    return default
                if not result.get("success"):
                    return default
                return result.get("data", default)

            # Process summaries
            job_summary = {}
            if not isinstance(job_summary_result, Exception) and job_summary_result.get("success"):
                job_summary = job_summary_result["data"][0] if job_summary_result["data"] else {}

            test_case_summary = {}
            if not isinstance(test_case_summary_result, Exception) and test_case_summary_result.get(
                "success"
            ):
                test_case_summary = (
                    test_case_summary_result["data"][0] if test_case_summary_result["data"] else {}
                )

            # Process job breakdown with health classification
            job_breakdown = []
            for j in safe_get_data(job_breakdown_result):
                failed = int(float(j.get("failed", 0) or 0))
                total = int(float(j.get("total_runs", 0) or 0))
                failure_rate = (failed / total * 100) if total > 0 else 0
                job_breakdown.append(
                    {
                        "job_name": j.get("job_name"),
                        "repository": j.get("repository"),
                        "job_type": j.get("job_type"),
                        "total_runs": total,
                        "passed": int(float(j.get("passed", 0) or 0)),
                        "failed": failed,
                        "pass_rate": float(j.get("pass_rate", 0) or 0),
                        "avg_duration_sec": float(j.get("avg_duration_sec", 0) or 0),
                        "last_run": str(j.get("last_run")) if j.get("last_run") else None,
                        "health_status": self._classify_test_health(failure_rate),
                    }
                )

            failing_tests = safe_get_data(failing_tests_result)
            flaky_tests = safe_get_data(flaky_tests_result)
            repo_breakdown = safe_get_data(repo_breakdown_result)
            daily_trend = safe_get_data(daily_trend_result)
            weekly_trend = safe_get_data(weekly_trend_result)
            suite_summary = safe_get_data(suite_summary_result)

            # Calculate health distribution
            health_distribution = {"healthy": 0, "warning": 0, "flaky": 0, "broken": 0}
            for j in job_breakdown:
                status = j.get("health_status", "healthy")
                health_distribution[status] = health_distribution.get(status, 0) + 1

            # Convert numeric types
            def convert_numeric(value, default=0):
                if value is None:
                    return default
                return float(value) if "." in str(value) else int(float(value))

            # Determine CI system from job types
            ci_systems = set()
            for j in job_breakdown:
                job_type = j.get("job_type", "")
                if job_type:
                    ci_systems.add(job_type)
            ci_system = ", ".join(ci_systems) if ci_systems else "Prow/Tekton"

            # Get unique repos actually found in data
            repos_analyzed = list(
                set(j.get("repository", "") for j in job_breakdown if j.get("repository"))
            )

            return {
                "success": True,
                "generated_at": datetime.now().isoformat(),
                "project_name": project_name,
                "repo_filter": repo_name if repo_name else "all",
                "resolved_repos": target_repos,  # Show which repos were resolved from project
                "analysis_period": {
                    "days_back": days_back,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                },
                "test_filter": "all_tests" if include_all_tests else "e2e_integration_only",
                "ci_system": ci_system,
                "repositories_analyzed": repos_analyzed,
                "executive_summary": {
                    "total_job_runs": convert_numeric(job_summary.get("total_jobs", 0)),
                    "unique_job_types": convert_numeric(job_summary.get("unique_job_types", 0)),
                    "job_passed": convert_numeric(job_summary.get("passed", 0)),
                    "job_failed": convert_numeric(job_summary.get("failed", 0)),
                    "job_aborted": convert_numeric(job_summary.get("aborted", 0)),
                    "job_pass_rate": convert_numeric(job_summary.get("pass_rate", 0.0), 0.0),
                    "total_test_runs": convert_numeric(test_case_summary.get("total_test_runs", 0)),
                    "unique_tests": convert_numeric(test_case_summary.get("unique_tests", 0)),
                    "test_passed": convert_numeric(test_case_summary.get("passed", 0)),
                    "test_failed": convert_numeric(test_case_summary.get("failed", 0)),
                    "test_skipped": convert_numeric(test_case_summary.get("skipped", 0)),
                    "test_pass_rate": convert_numeric(test_case_summary.get("pass_rate", 0.0), 0.0),
                    "flaky_test_count": len(flaky_tests),
                },
                "health_distribution": health_distribution,
                "job_breakdown": job_breakdown,
                "top_failing_tests": failing_tests,
                "flaky_tests": flaky_tests,
                "test_suites": suite_summary,
                "repo_breakdown": repo_breakdown,
                "daily_trend": daily_trend,
                "weekly_trend": weekly_trend,
            }

        except Exception as e:
            self.logger.error(f"Analyze E2E tests failed: {e}")
            return {"success": False, "error": str(e)}
