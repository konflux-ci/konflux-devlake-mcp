#!/usr/bin/env python3
"""
Historical Trends Tools for Konflux DevLake MCP Server

Provides week-over-week and month-over-month trend analysis for key engineering metrics.
Aligned with DevLake data model and Grafana dashboards.
"""

import asyncio
from typing import Any, Dict, List, Optional

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class HistoricalTrendsTools(BaseTool):
    """
    Historical trends analysis tools for Konflux DevLake MCP Server.

    Provides week-over-week comparisons and trend analysis for:
    - PR Cycle Time
    - Merge Rate
    - Retests per PR
    - CI Success Rate
    - Code Coverage
    - MTTR (Mean Time to Restore)
    """

    # Thresholds for change detection
    THRESHOLDS = {
        "cycle_time": {"improved": -5, "regressed": 10},  # Lower is better
        "merge_rate": {"improved": 5, "regressed": -10},  # Higher is better
        "retests_per_pr": {"improved": -10, "regressed": 15},  # Lower is better
        "ci_success_rate": {"improved": 3, "regressed": -5},  # Higher is better
        "coverage": {"improved": 2, "regressed": -3},  # Higher is better
        "mttr": {"improved": -10, "regressed": 20},  # Lower is better
    }

    def __init__(self, db_connection):
        """
        Initialize historical trends tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.HistoricalTrendsTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all historical trends tools.

        Returns:
            List of Tool objects
        """
        return [
            Tool(
                name="get_historical_trends",
                description=(
                    "Get historical trends and week-over-week comparisons for key engineering "
                    "metrics including: cycle_time, merge_rate, retests, ci_success, coverage, "
                    "and mttr. Returns current vs previous week values, change percentages, "
                    "4-week trends, and anomaly detection."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "DevLake project name (required)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "Specific metric to analyze: all, cycle_time, "
                            "merge_rate, retests, ci_success, coverage, mttr (default: all)",
                            "enum": [
                                "all",
                                "cycle_time",
                                "merge_rate",
                                "retests",
                                "ci_success",
                                "coverage",
                                "mttr",
                            ],
                        },
                        "period": {
                            "type": "string",
                            "description": "Analysis period in days: 7, 14, 30, 90, 180 "
                            "(default: 30)",
                            "enum": ["7", "14", "30", "90", "180"],
                        },
                    },
                    "required": ["project_name"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a historical trends tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_historical_trends":
                result = await self._get_historical_trends(arguments)
            else:
                result = {"success": False, "error": f"Unknown tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Historical trends tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_historical_trends(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get historical trends and week-over-week comparisons.

        Args:
            arguments: Tool arguments

        Returns:
            Dictionary with trend data for all metrics
        """
        try:
            project_name = arguments.get("project_name", "")
            metric = arguments.get("metric", "all")
            period = int(arguments.get("period", "30"))

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Collect metrics based on selection
            metrics_to_fetch = (
                ["cycle_time", "merge_rate", "retests", "ci_success", "coverage", "mttr"]
                if metric == "all"
                else [metric]
            )

            # Fetch all requested metrics in parallel
            tasks = []
            task_names = []

            for m in metrics_to_fetch:
                if m == "cycle_time":
                    tasks.append(self._get_cycle_time_trend(project_name, period))
                    task_names.append("cycle_time")
                elif m == "merge_rate":
                    tasks.append(self._get_merge_rate_trend(project_name, period))
                    task_names.append("merge_rate")
                elif m == "retests":
                    tasks.append(self._get_retests_trend(project_name, period))
                    task_names.append("retests_per_pr")
                elif m == "ci_success":
                    tasks.append(self._get_ci_success_trend(project_name, period))
                    task_names.append("ci_success_rate")
                elif m == "coverage":
                    tasks.append(self._get_coverage_trend(project_name, period))
                    task_names.append("coverage")
                elif m == "mttr":
                    tasks.append(self._get_mttr_trend(project_name, period))
                    task_names.append("mttr")

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Build metrics dictionary
            metrics = {}
            anomalies = []
            significant_changes = 0

            for name, result in zip(task_names, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error fetching {name}: {result}")
                    metrics[name] = {"error": str(result)}
                else:
                    metrics[name] = result
                    # Check for significant changes
                    if result.get("change_percent") is not None:
                        change = abs(result["change_percent"])
                        if change >= 10:
                            significant_changes += 1
                    # Check for anomalies
                    if result.get("is_anomaly"):
                        anomalies.append(
                            {
                                "metric": name,
                                "current_value": result.get("current_week", {}).get("value"),
                                "expected_range": result.get("expected_range"),
                                "severity": "warning" if change < 20 else "critical",
                                "message": result.get("anomaly_message", ""),
                            }
                        )

            # Determine overall health
            overall_health = self._determine_overall_health(metrics)

            # Get weekly breakdown
            weekly_breakdown = await self._get_weekly_breakdown(project_name, period)

            return {
                "success": True,
                "project_name": project_name,
                "period_days": period,
                "summary": {
                    "total_weeks_analyzed": min(period // 7, 12),
                    "overall_health": overall_health,
                    "significant_changes": significant_changes,
                },
                "metrics": metrics,
                "anomalies": anomalies,
                "weekly_breakdown": weekly_breakdown,
            }

        except Exception as e:
            self.logger.error(f"Get historical trends failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_cycle_time_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get PR cycle time weekly trend."""
        query = f"""
            SELECT
                YEARWEEK(pr.merged_date, 1) AS week,
                MIN(pr.merged_date) AS week_start,
                ROUND(AVG(prm.pr_cycle_time) / 60, 2) AS avg_cycle_time_hours,
                COUNT(*) AS pr_count
            FROM lake.pull_requests pr
            JOIN lake.project_pr_metrics prm ON pr.id = prm.id
            JOIN lake.repos r ON pr.base_repo_id = r.id
            JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
                AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                AND pr.merged_date IS NOT NULL
                AND prm.pr_cycle_time IS NOT NULL
            GROUP BY YEARWEEK(pr.merged_date, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "avg_cycle_time_hours", "hours", "cycle_time")

    async def _get_merge_rate_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get PR merge rate weekly trend."""
        query = f"""
            SELECT
                YEARWEEK(pr.created_date, 1) AS week,
                MIN(pr.created_date) AS week_start,
                ROUND(
                    COUNT(CASE WHEN pr.status = 'MERGED' THEN 1 END) * 100.0 / COUNT(*), 2
                ) AS merge_rate,
                COUNT(*) AS total_prs
            FROM lake.pull_requests pr
            JOIN lake.repos r ON pr.base_repo_id = r.id
            JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
                AND pr.created_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY YEARWEEK(pr.created_date, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "merge_rate", "percent", "merge_rate")

    async def _get_retests_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get retests per PR weekly trend."""
        query = f"""
            SELECT
                YEARWEEK(prc.created_date, 1) AS week,
                MIN(prc.created_date) AS week_start,
                COUNT(DISTINCT prc.id) AS retest_count,
                COUNT(DISTINCT prc.pull_request_id) AS prs_affected,
                ROUND(
                    COUNT(DISTINCT prc.id) * 1.0 /
                    NULLIF(COUNT(DISTINCT prc.pull_request_id), 0), 2
                ) AS retests_per_pr
            FROM lake.pull_request_comments prc
            JOIN lake.repos r ON prc.repo_id = r.id
            JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
                AND prc.body LIKE '%/retest%'
                AND prc.created_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY YEARWEEK(prc.created_date, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "retests_per_pr", "count", "retests_per_pr")

    async def _get_ci_success_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get CI success rate weekly trend."""
        query = f"""
            SELECT
                YEARWEEK(gr.run_started_at, 1) AS week,
                MIN(gr.run_started_at) AS week_start,
                ROUND(
                    COUNT(CASE WHEN gr.conclusion = 'success' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) AS success_rate,
                COUNT(*) AS total_runs
            FROM lake._tool_github_runs gr
            JOIN lake._tool_github_repos repo ON gr.repo_id = repo.repo_id
            JOIN lake.project_mapping pm
                ON CONCAT('github:GithubRepo:1:', repo.github_id) = pm.row_id
                AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
                AND gr.run_started_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                AND gr.conclusion IN ('success', 'failure')
            GROUP BY YEARWEEK(gr.run_started_at, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "success_rate", "percent", "ci_success_rate")

    async def _get_coverage_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get code coverage weekly trend."""
        # First get repo names for the project
        repo_names = await self._get_repo_names(project_name)
        if not repo_names:
            return {
                "current_week": {"value": None, "unit": "percent", "sample_size": 0},
                "previous_week": {"value": None, "unit": "percent", "sample_size": 0},
                "change_percent": None,
                "change_direction": "no_data",
                "trend_4_weeks": [],
            }

        repo_names_str = ", ".join([f"'{r}'" for r in repo_names])

        query = f"""
            SELECT
                YEARWEEK(cm.commit_timestamp, 1) AS week,
                MIN(cm.commit_timestamp) AS week_start,
                ROUND(AVG(c.totals_coverage), 2) AS avg_coverage,
                COUNT(*) AS sample_count
            FROM lake._tool_codecov_coverages c
            JOIN lake._tool_codecov_commits cm
                ON c.connection_id = cm.connection_id
                AND c.repo_id = cm.repo_id
                AND c.commit_sha = cm.commit_sha
            WHERE c.repo_id IN ({repo_names_str})
                AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                AND c.totals_coverage IS NOT NULL
            GROUP BY YEARWEEK(cm.commit_timestamp, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "avg_coverage", "percent", "coverage")

    async def _get_mttr_trend(self, project_name: str, days: int) -> Dict[str, Any]:
        """Get MTTR (Mean Time to Restore) weekly trend."""
        query = f"""
            SELECT
                YEARWEEK(i.resolution_date, 1) AS week,
                MIN(i.resolution_date) AS week_start,
                ROUND(AVG(i.lead_time_minutes) / 60, 2) AS avg_mttr_hours,
                COUNT(*) AS incident_count
            FROM lake.incidents i
            JOIN lake.project_mapping pm ON i.scope_id = pm.row_id
                AND pm.`table` = i.`table`
            WHERE pm.project_name = '{project_name}'
                AND i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                AND i.resolution_date IS NOT NULL
                AND i.lead_time_minutes IS NOT NULL
            GROUP BY YEARWEEK(i.resolution_date, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        return self._process_trend_data(result, "avg_mttr_hours", "hours", "mttr")

    async def _get_repo_names(self, project_name: str) -> List[str]:
        """Get repository names for a project."""
        query = f"""
            SELECT DISTINCT r.name AS repo_name
            FROM lake.repos r
            JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
        """
        result = await self.db_connection.execute_query(query, 100)
        if result["success"] and result["data"]:
            return [row["repo_name"] for row in result["data"]]
        return []

    async def _get_weekly_breakdown(self, project_name: str, days: int) -> List[Dict[str, Any]]:
        """Get weekly breakdown summary."""
        query = f"""
            SELECT
                YEARWEEK(pr.merged_date, 1) AS week,
                MIN(DATE(pr.merged_date)) AS week_start,
                MAX(DATE(pr.merged_date)) AS week_end,
                ROUND(AVG(prm.pr_cycle_time) / 60, 2) AS cycle_time_avg,
                COUNT(*) AS prs_merged
            FROM lake.pull_requests pr
            JOIN lake.project_pr_metrics prm ON pr.id = prm.id
            JOIN lake.repos r ON pr.base_repo_id = r.id
            JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
                AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                AND pr.merged_date IS NOT NULL
            GROUP BY YEARWEEK(pr.merged_date, 1)
            ORDER BY week DESC
            LIMIT 8
        """
        result = await self.db_connection.execute_query(query, 8)
        if result["success"] and result["data"]:
            breakdown = []
            for row in result["data"]:
                breakdown.append(
                    {
                        "week_start": str(row.get("week_start", "")),
                        "week_end": str(row.get("week_end", "")),
                        "cycle_time_avg": (
                            float(row["cycle_time_avg"]) if row.get("cycle_time_avg") else None
                        ),
                        "prs_merged": int(row.get("prs_merged", 0)),
                    }
                )
            return breakdown
        return []

    def _process_trend_data(
        self,
        result: Dict[str, Any],
        value_field: str,
        unit: str,
        metric_name: str,
    ) -> Dict[str, Any]:
        """
        Process query result into trend data structure.

        Args:
            result: Query result
            value_field: Field name containing the metric value
            unit: Unit of measurement
            metric_name: Name of the metric for threshold lookup

        Returns:
            Processed trend data
        """
        if not result["success"] or not result["data"]:
            return {
                "current_week": {"value": None, "unit": unit, "sample_size": 0},
                "previous_week": {"value": None, "unit": unit, "sample_size": 0},
                "change_percent": None,
                "change_direction": "no_data",
                "trend_4_weeks": [],
            }

        data = result["data"]

        # Current week (most recent)
        current = data[0] if len(data) > 0 else {}
        current_value = self._safe_float(current.get(value_field))
        current_sample = self._get_sample_size(current)

        # Previous week
        previous = data[1] if len(data) > 1 else {}
        previous_value = self._safe_float(previous.get(value_field))
        previous_sample = self._get_sample_size(previous)

        # Calculate change
        change_percent = None
        change_direction = "stable"
        if current_value is not None and previous_value is not None and previous_value != 0:
            change_percent = round(((current_value - previous_value) / previous_value) * 100, 2)
            change_direction = self._get_change_direction(change_percent, metric_name)

        # Get 4-week trend
        trend_4_weeks = []
        for i, row in enumerate(data[:4]):
            val = self._safe_float(row.get(value_field))
            if val is not None:
                trend_4_weeks.append(val)

        # Calculate expected range for anomaly detection (mean +/- 2 std dev)
        is_anomaly = False
        anomaly_message = ""
        expected_range = None
        if len(trend_4_weeks) >= 3:
            avg = sum(trend_4_weeks) / len(trend_4_weeks)
            variance = sum((x - avg) ** 2 for x in trend_4_weeks) / len(trend_4_weeks)
            std_dev = variance**0.5
            expected_range = [round(avg - 2 * std_dev, 2), round(avg + 2 * std_dev, 2)]
            if current_value is not None:
                if current_value < expected_range[0] or current_value > expected_range[1]:
                    is_anomaly = True
                    anomaly_message = (
                        f"Value {current_value} is outside expected range "
                        f"{expected_range[0]} - {expected_range[1]}"
                    )

        return {
            "current_week": {
                "value": current_value,
                "unit": unit,
                "sample_size": current_sample,
            },
            "previous_week": {
                "value": previous_value,
                "unit": unit,
                "sample_size": previous_sample,
            },
            "change_percent": change_percent,
            "change_direction": change_direction,
            "trend_4_weeks": trend_4_weeks,
            "is_anomaly": is_anomaly,
            "expected_range": expected_range,
            "anomaly_message": anomaly_message,
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None

    def _get_sample_size(self, row: Dict[str, Any]) -> int:
        """Get sample size from row data."""
        for key in ["pr_count", "total_prs", "total_runs", "sample_count", "incident_count"]:
            if key in row:
                return int(row[key])
        return 0

    def _get_change_direction(self, change_percent: float, metric_name: str) -> str:
        """
        Determine change direction based on metric thresholds.

        Args:
            change_percent: Percentage change
            metric_name: Name of the metric

        Returns:
            "improved", "regressed", or "stable"
        """
        thresholds = self.THRESHOLDS.get(metric_name, {"improved": -5, "regressed": 10})

        if change_percent <= thresholds["improved"]:
            return "improved"
        elif change_percent >= thresholds["regressed"]:
            return "regressed"
        return "stable"

    def _determine_overall_health(self, metrics: Dict[str, Any]) -> str:
        """
        Determine overall health based on all metrics.

        Args:
            metrics: Dictionary of metric results

        Returns:
            "improving", "stable", or "declining"
        """
        improving = 0
        declining = 0

        for metric_data in metrics.values():
            if isinstance(metric_data, dict):
                direction = metric_data.get("change_direction", "stable")
                if direction == "improved":
                    improving += 1
                elif direction == "regressed":
                    declining += 1

        if improving > declining and improving >= 2:
            return "improving"
        elif declining > improving and declining >= 2:
            return "declining"
        return "stable"
