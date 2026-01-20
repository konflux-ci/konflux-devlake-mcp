#!/usr/bin/env python3
"""
Lead Time for Changes Tools for Konflux DevLake MCP Server

DORA metric: Lead Time for Changes - measures how long it takes for code to go
from first commit to production deployment. Aligned with Grafana dashboard
"DORA Details - Lead Time for Changes".
"""

import asyncio
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class LeadTimeTools(BaseTool):
    """
    Lead Time for Changes tools for Konflux DevLake MCP Server.

    Provides DORA Lead Time for Changes metric based on deployed PRs,
    with breakdown into coding, pickup, review, and deploy times.
    """

    def __init__(self, db_connection):
        """
        Initialize Lead Time tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.LeadTimeTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all Lead Time tools.

        Returns:
            List of Tool objects
        """
        return [
            Tool(
                name="get_lead_time_for_changes",
                description=(
                    "DORA Metric: Lead Time for Changes. Measures time from first commit "
                    "to production deployment for merged PRs. Returns average cycle time "
                    "with breakdown into coding, pickup, review, and deploy times. "
                    "Includes detailed PR list with deployment info."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "DevLake project name (required)",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back (default: 30)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum PR details to return (default: 50)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a Lead Time tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_lead_time_for_changes":
                result = await self._get_lead_time_for_changes(arguments)
            else:
                result = {"success": False, "error": f"Unknown tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Lead Time tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_lead_time_for_changes(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get Lead Time for Changes DORA metric.

        Aligned with Grafana dashboard: DORA Details - Lead Time for Changes

        Args:
            arguments: Tool arguments

        Returns:
            Dictionary with lead time metrics and PR details
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 30)
            limit = arguments.get("limit", 50)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Query 1: Average PR Cycle Time (Panel 1)
            cycle_time_query = f"""
                SELECT
                    ROUND(AVG(COALESCE(prm.pr_cycle_time / 60, 0)), 2) AS avg_cycle_time_hours,
                    COUNT(DISTINCT pr.id) AS pr_count
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND prm.pr_deployed_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 2: Average Coding Time (Panel 1.1)
            coding_time_query = f"""
                SELECT
                    ROUND(AVG(COALESCE(prm.pr_coding_time / 60, 0)), 2) AS avg_coding_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND prm.pr_deployed_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 3: Average Pickup Time (Panel 1.2)
            pickup_time_query = f"""
                SELECT
                    ROUND(AVG(COALESCE(prm.pr_pickup_time / 60, 0)), 2) AS avg_pickup_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND prm.pr_deployed_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 4: Average Review Time (Panel 1.3)
            review_time_query = f"""
                SELECT
                    ROUND(AVG(COALESCE(prm.pr_review_time / 60, 0)), 2) AS avg_review_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND prm.pr_deployed_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 5: Average Deploy Time (Panel 1.4)
            deploy_time_query = f"""
                SELECT
                    ROUND(AVG(COALESCE(prm.pr_deploy_time / 60, 0)), 2) AS avg_deploy_time_hours
                FROM lake.pull_requests pr
                LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                WHERE pm.project_name = '{project_name}'
                    AND prm.pr_deployed_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 6: PR Details (Panel 2)
            details_query = f"""
                SELECT DISTINCT
                    pr.title AS pr_title,
                    pr.url AS pr_url,
                    prm.first_commit_sha,
                    prc.commit_authored_date AS first_commit_date,
                    cdc.cicd_deployment_id AS deployment_id,
                    cdc.finished_date AS deployment_date,
                    ROUND(prm.pr_coding_time / 60, 2) AS coding_time_hours,
                    ROUND(prm.pr_pickup_time / 60, 2) AS pickup_time_hours,
                    ROUND(prm.pr_review_time / 60, 2) AS review_time_hours,
                    ROUND(prm.pr_deploy_time / 60, 2) AS deploy_time_hours,
                    ROUND(prm.pr_cycle_time / 60, 2) AS lead_time_hours
                FROM lake.pull_requests pr
                JOIN lake.project_pr_metrics prm ON prm.id = pr.id
                JOIN lake.project_mapping pm ON pr.base_repo_id = pm.row_id
                    AND pm.`table` = 'repos'
                JOIN lake.cicd_deployment_commits cdc ON prm.deployment_commit_id = cdc.id
                LEFT JOIN lake.pull_request_commits prc ON prc.commit_sha = prm.first_commit_sha
                WHERE pm.project_name = '{project_name}'
                    AND pr.merged_date IS NOT NULL
                    AND prm.pr_cycle_time IS NOT NULL
                    AND cdc.finished_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ORDER BY cdc.finished_date DESC
            """

            # Execute all queries in parallel
            results = await asyncio.gather(
                self.db_connection.execute_query(cycle_time_query, 1),
                self.db_connection.execute_query(coding_time_query, 1),
                self.db_connection.execute_query(pickup_time_query, 1),
                self.db_connection.execute_query(review_time_query, 1),
                self.db_connection.execute_query(deploy_time_query, 1),
                self.db_connection.execute_query(details_query, limit),
            )

            (
                cycle_result,
                coding_result,
                pickup_result,
                review_result,
                deploy_result,
                details_result,
            ) = results

            # Extract metrics
            avg_cycle_time = None
            pr_count = 0
            if cycle_result["success"] and cycle_result["data"]:
                avg_cycle_time = self._safe_float(
                    cycle_result["data"][0].get("avg_cycle_time_hours")
                )
                pr_count = int(cycle_result["data"][0].get("pr_count", 0))

            avg_coding_time = None
            if coding_result["success"] and coding_result["data"]:
                avg_coding_time = self._safe_float(
                    coding_result["data"][0].get("avg_coding_time_hours")
                )

            avg_pickup_time = None
            if pickup_result["success"] and pickup_result["data"]:
                avg_pickup_time = self._safe_float(
                    pickup_result["data"][0].get("avg_pickup_time_hours")
                )

            avg_review_time = None
            if review_result["success"] and review_result["data"]:
                avg_review_time = self._safe_float(
                    review_result["data"][0].get("avg_review_time_hours")
                )

            avg_deploy_time = None
            if deploy_result["success"] and deploy_result["data"]:
                avg_deploy_time = self._safe_float(
                    deploy_result["data"][0].get("avg_deploy_time_hours")
                )

            # Extract PR details
            pr_details = []
            if details_result["success"] and details_result["data"]:
                for row in details_result["data"]:
                    pr_details.append(
                        {
                            "pr_title": row.get("pr_title"),
                            "pr_url": row.get("pr_url"),
                            "first_commit_sha": row.get("first_commit_sha"),
                            "first_commit_date": (
                                str(row["first_commit_date"])
                                if row.get("first_commit_date")
                                else None
                            ),
                            "deployment_id": row.get("deployment_id"),
                            "deployment_date": (
                                str(row["deployment_date"]) if row.get("deployment_date") else None
                            ),
                            "coding_time_hours": self._safe_float(row.get("coding_time_hours")),
                            "pickup_time_hours": self._safe_float(row.get("pickup_time_hours")),
                            "review_time_hours": self._safe_float(row.get("review_time_hours")),
                            "deploy_time_hours": self._safe_float(row.get("deploy_time_hours")),
                            "lead_time_hours": self._safe_float(row.get("lead_time_hours")),
                        }
                    )

            return {
                "success": True,
                "project_name": project_name,
                "days_back": days_back,
                "deployed_prs_count": pr_count,
                "avg_lead_time_hours": avg_cycle_time,
                "breakdown": {
                    "avg_coding_time_hours": avg_coding_time,
                    "avg_pickup_time_hours": avg_pickup_time,
                    "avg_review_time_hours": avg_review_time,
                    "avg_deploy_time_hours": avg_deploy_time,
                },
                "pr_details": pr_details,
            }

        except Exception as e:
            self.logger.error(f"Get lead time for changes failed: {e}")
            return {"success": False, "error": str(e)}

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None
