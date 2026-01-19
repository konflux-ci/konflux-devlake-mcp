#!/usr/bin/env python3
"""
PR Cycle Time Analysis Tools for Konflux DevLake MCP Server

Aligned with Konflux DevLake Engineering Throughput and Cycle Time dashboard:
https://github.com/konflux-ci/konflux-devlake-dashboards

Cycle Time Breakdown:
- Total Cycle Time: 1st commit to PR merged
- Coding Time: 1st commit to PR submitted
- Pickup Time: PR submitted to 1st review
- Review Time: 1st review to merged
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class PRCycleTimeTools(BaseTool):
    """
    PR Cycle Time Analysis tools aligned with Konflux DevLake dashboard.
    """

    def __init__(self, db_connection):
        """
        Initialize PR cycle time tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.PRCycleTimeTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all PR cycle time analysis tools.

        Returns:
            List of Tool objects for PR cycle time operations
        """
        return [
            Tool(
                name="get_pr_cycle_time",
                description=(
                    "**PR Cycle Time Analysis Tool** - Analyzes pull request cycle time "
                    "metrics for a DevLake project within a specified time interval. "
                    "Returns comprehensive cycle time breakdown including: "
                    "- Total Cycle Time (1st commit to PR merged), "
                    "- Coding Time (1st commit to PR submitted), "
                    "- Pickup Time (PR submitted to 1st review), "
                    "- Review Time (1st review to merged). "
                    "Also provides weekly trends, repository breakdown, PR size impact "
                    "analysis. Always includes 3-month trend data. "
                    "Can filter by specific repository. "
                    "Aligned with Konflux DevLake Engineering Throughput dashboard."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name (e.g., 'Secureflow - Konflux - Global', "
                                "'Konflux_Pilot_Team'). Required for filtering PRs."
                            ),
                        },
                        "repo_name": {
                            "type": "string",
                            "description": (
                                "Filter by specific repository name (partial match). "
                                "e.g., 'integration-service', 'build-service'"
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": (
                                "Number of days back to analyze (default: 30). "
                                "Leave empty to use start_date/end_date instead."
                            ),
                        },
                        "start_date": {
                            "type": "string",
                            "description": (
                                "Start date for analysis (format: YYYY-MM-DD or "
                                "YYYY-MM-DD HH:MM:SS). Leave empty for no start date limit."
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": (
                                "End date for analysis (format: YYYY-MM-DD or "
                                "YYYY-MM-DD HH:MM:SS). Leave empty for no end date limit."
                            ),
                        },
                        "include_repo_breakdown": {
                            "type": "boolean",
                            "description": (
                                "Include breakdown by repository (default: true). "
                                "Shows top repositories by PR count with cycle times."
                            ),
                        },
                        "include_size_analysis": {
                            "type": "boolean",
                            "description": (
                                "Include PR size impact analysis (default: true). "
                                "Shows how PR size affects cycle time."
                            ),
                        },
                        "top_repos": {
                            "type": "integer",
                            "description": (
                                "Number of top repositories to include in breakdown "
                                "(default: 20, max: 50)"
                            ),
                        },
                    },
                    "required": ["project_name"],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a PR cycle time tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_pr_cycle_time":
                result = await self._get_pr_cycle_time(arguments)
            else:
                result = {"success": False, "error": f"Unknown tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"PR cycle time tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {"success": False, "error": str(e)}
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

    async def _get_pr_cycle_time(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get PR cycle time metrics aligned with Grafana dashboard.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with cycle time data
        """
        try:
            project_name = arguments.get("project_name", "")
            repo_name = arguments.get("repo_name", "")
            days_back = arguments.get("days_back")
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            include_repo_breakdown = arguments.get("include_repo_breakdown", True)
            include_size_analysis = arguments.get("include_size_analysis", True)
            top_repos = min(arguments.get("top_repos", 20), 50)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Build date filter based on merged_date (matching Grafana)
            date_filter = ""
            if start_date or end_date:
                if start_date:
                    if len(start_date) == 10:
                        start_date = f"{start_date} 00:00:00"
                    date_filter += f" AND pr.merged_date >= '{start_date}'"
                if end_date:
                    if len(end_date) == 10:
                        end_date = f"{end_date} 23:59:59"
                    date_filter += f" AND pr.merged_date <= '{end_date}'"
            elif days_back is not None and days_back > 0:
                date_filter = f" AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)"
            else:
                days_back = 30
                date_filter = f" AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)"

            # Build repo filter
            repo_filter = ""
            if repo_name:
                repo_filter = f" AND r.name LIKE '%{repo_name}%'"

            # Query 1: Overall Cycle Time (matching Grafana dashboard)
            overall_query = f"""
                SELECT
                    COUNT(DISTINCT pr.id) as merged_pr_count,
                    ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 2) as avg_cycle_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_coding_time, 0) / 60), 2) as avg_coding_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 2) as avg_pickup_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 2) as avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.repos r ON pr.base_repo_id = r.id
                JOIN lake.project_mapping pm ON r.id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    {date_filter}
                    {repo_filter}
            """

            # Query 2: Weekly Trends for analysis period
            weekly_query = f"""
                SELECT
                    YEARWEEK(pr.merged_date, 1) as week,
                    MIN(DATE(pr.merged_date)) as week_start,
                    COUNT(DISTINCT pr.id) as merged_pr_count,
                    ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 2) as avg_cycle_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_coding_time, 0) / 60), 2) as avg_coding_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 2) as avg_pickup_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 2) as avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.repos r ON pr.base_repo_id = r.id
                JOIN lake.project_mapping pm ON r.id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    {date_filter}
                    {repo_filter}
                GROUP BY YEARWEEK(pr.merged_date, 1)
                ORDER BY week DESC
            """

            # Query 3: 3-Month Trend (ALWAYS included)
            three_month_trend_query = f"""
                SELECT
                    YEARWEEK(pr.merged_date, 1) as week,
                    MIN(DATE(pr.merged_date)) as week_start,
                    COUNT(DISTINCT pr.id) as merged_pr_count,
                    ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 2) as avg_cycle_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_coding_time, 0) / 60), 2) as avg_coding_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 2) as avg_pickup_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 2) as avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.repos r ON pr.base_repo_id = r.id
                JOIN lake.project_mapping pm ON r.id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                    {repo_filter}
                GROUP BY YEARWEEK(pr.merged_date, 1)
                ORDER BY week DESC
            """

            # Query 4: Repository Breakdown
            repo_query = f"""
                SELECT
                    r.name as repo_name,
                    SUBSTRING_INDEX(pr.url, '/pull/', 1) as repo_url,
                    COUNT(DISTINCT pr.id) as merged_pr_count,
                    ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 2) as avg_cycle_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_coding_time, 0) / 60), 2) as avg_coding_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 2) as avg_pickup_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 2) as avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.repos r ON pr.base_repo_id = r.id
                JOIN lake.project_mapping pm ON r.id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    {date_filter}
                    {repo_filter}
                GROUP BY r.name, repo_url
                ORDER BY merged_pr_count DESC
                LIMIT {top_repos}
            """

            # Query 5: PR Size Analysis
            size_query = f"""
                SELECT
                    CASE
                        WHEN (pr.additions + pr.deletions) <= 50
                            THEN 'XS (1-50 lines)'
                        WHEN (pr.additions + pr.deletions) <= 200
                            THEN 'S (51-200 lines)'
                        WHEN (pr.additions + pr.deletions) <= 500
                            THEN 'M (201-500 lines)'
                        WHEN (pr.additions + pr.deletions) <= 1000
                            THEN 'L (501-1000 lines)'
                        ELSE 'XL (>1000 lines)'
                    END as size_category,
                    COUNT(DISTINCT pr.id) as pr_count,
                    ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 2) as avg_cycle_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 2) as avg_pickup_time_hours,
                    ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 2) as avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.repos r ON pr.base_repo_id = r.id
                JOIN lake.project_mapping pm ON r.id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    {date_filter}
                    {repo_filter}
                GROUP BY size_category
                ORDER BY
                    CASE size_category
                        WHEN 'XS (1-50 lines)' THEN 1
                        WHEN 'S (51-200 lines)' THEN 2
                        WHEN 'M (201-500 lines)' THEN 3
                        WHEN 'L (501-1000 lines)' THEN 4
                        ELSE 5
                    END
            """

            # Execute queries in parallel
            queries = [
                self._execute_with_timeout(overall_query, 1, timeout=60),
                self._execute_with_timeout(weekly_query, 52, timeout=60),
                self._execute_with_timeout(three_month_trend_query, 13, timeout=60),
            ]

            if include_repo_breakdown:
                queries.append(self._execute_with_timeout(repo_query, top_repos, timeout=60))
            if include_size_analysis:
                queries.append(self._execute_with_timeout(size_query, 10, timeout=60))

            results = await asyncio.gather(*queries, return_exceptions=True)

            # Process overall metrics
            overall_result = results[0]
            if isinstance(overall_result, Exception) or not overall_result.get("success"):
                error_msg = (
                    str(overall_result)
                    if isinstance(overall_result, Exception)
                    else (overall_result.get("error", "No data"))
                )
                return {
                    "success": False,
                    "error": "Failed to retrieve cycle time metrics",
                    "query_error": error_msg,
                }

            if not overall_result["data"]:
                return {
                    "success": False,
                    "error": "No merged PRs found for the specified filters",
                }

            metrics = overall_result["data"][0]

            result = {
                "success": True,
                "generated_at": datetime.now().isoformat(),
                "project_name": project_name,
                "repo_filter": repo_name if repo_name else "all",
                "pr_cycle_time": {
                    "merged_pr_count": int(float(metrics.get("merged_pr_count") or 0)),
                    "avg_cycle_time_hours": float(metrics.get("avg_cycle_time_hours") or 0),
                    "avg_coding_time_hours": float(metrics.get("avg_coding_time_hours") or 0),
                    "avg_pickup_time_hours": float(metrics.get("avg_pickup_time_hours") or 0),
                    "avg_review_time_hours": float(metrics.get("avg_review_time_hours") or 0),
                },
            }

            # Process weekly trends for analysis period
            weekly_result = results[1]
            if not isinstance(weekly_result, Exception) and weekly_result.get("success"):
                result["weekly_trends"] = [
                    {
                        "week": row.get("week"),
                        "week_start": str(row.get("week_start")) if row.get("week_start") else None,
                        "merged_pr_count": int(float(row.get("merged_pr_count") or 0)),
                        "avg_cycle_time_hours": float(row.get("avg_cycle_time_hours") or 0),
                        "avg_coding_time_hours": float(row.get("avg_coding_time_hours") or 0),
                        "avg_pickup_time_hours": float(row.get("avg_pickup_time_hours") or 0),
                        "avg_review_time_hours": float(row.get("avg_review_time_hours") or 0),
                    }
                    for row in weekly_result["data"]
                ]

            # Process 3-month trend (ALWAYS included)
            three_month_result = results[2]
            if not isinstance(three_month_result, Exception) and three_month_result.get("success"):
                result["three_month_trend"] = [
                    {
                        "week": row.get("week"),
                        "week_start": str(row.get("week_start")) if row.get("week_start") else None,
                        "merged_pr_count": int(float(row.get("merged_pr_count") or 0)),
                        "avg_cycle_time_hours": float(row.get("avg_cycle_time_hours") or 0),
                        "avg_coding_time_hours": float(row.get("avg_coding_time_hours") or 0),
                        "avg_pickup_time_hours": float(row.get("avg_pickup_time_hours") or 0),
                        "avg_review_time_hours": float(row.get("avg_review_time_hours") or 0),
                    }
                    for row in three_month_result["data"]
                ]

            # Process repository breakdown
            result_idx = 3
            if include_repo_breakdown:
                repo_result = results[result_idx]
                if not isinstance(repo_result, Exception) and repo_result.get("success"):
                    result["repository_breakdown"] = [
                        {
                            "repo_name": row.get("repo_name"),
                            "repo_url": row.get("repo_url"),
                            "merged_pr_count": int(float(row.get("merged_pr_count") or 0)),
                            "avg_cycle_time_hours": float(row.get("avg_cycle_time_hours") or 0),
                            "avg_coding_time_hours": float(row.get("avg_coding_time_hours") or 0),
                            "avg_pickup_time_hours": float(row.get("avg_pickup_time_hours") or 0),
                            "avg_review_time_hours": float(row.get("avg_review_time_hours") or 0),
                        }
                        for row in repo_result["data"]
                    ]
                result_idx += 1

            # Process size analysis
            if include_size_analysis and result_idx < len(results):
                size_result = results[result_idx]
                if not isinstance(size_result, Exception) and size_result.get("success"):
                    result["size_analysis"] = [
                        {
                            "size_category": row.get("size_category"),
                            "pr_count": int(float(row.get("pr_count") or 0)),
                            "avg_cycle_time_hours": float(row.get("avg_cycle_time_hours") or 0),
                            "avg_pickup_time_hours": float(row.get("avg_pickup_time_hours") or 0),
                            "avg_review_time_hours": float(row.get("avg_review_time_hours") or 0),
                        }
                        for row in size_result["data"]
                    ]

            return result

        except Exception as e:
            self.logger.error(f"Get PR cycle time failed: {e}")
            return {"success": False, "error": str(e)}
