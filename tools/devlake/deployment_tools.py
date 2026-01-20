#!/usr/bin/env python3
"""
Deployment Tools for Konflux DevLake MCP Server

Contains tools for deployment analysis and management with improved modularity
and maintainability.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class DeploymentTools(BaseTool):
    """
    Deployment-related tools for Konflux DevLake MCP Server.

    This class provides tools for deployment analysis, filtering, and reporting
    with proper error handling and logging.
    """

    def __init__(self, db_connection):
        """
        Initialize deployment tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.DeploymentTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all deployment tools.

        Returns:
            List of Tool objects for deployment operations
        """
        return [
            Tool(
                name="get_deployments",
                description=(
                    "**Comprehensive Deployment Analytics Tool** - Retrieves deployment data "
                    "from the Konflux DevLake database with advanced filtering capabilities. "
                    "This tool provides comprehensive deployment information including "
                    "deployment_id, display_title, url, result, environment, finished_date, "
                    "and project details. Supports filtering by project (e.g., "
                    "'Konflux_Pilot_Team'), environment (e.g., 'PRODUCTION', 'STAGING', "
                    "'DEVELOPMENT'), time range (days_back, start_date, end_date), and result "
                    "limits. Perfect for deployment frequency analysis, release tracking, "
                    "and operational reporting. Returns deployments sorted by finished_date "
                    "(newest first)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project name to filter by "
                            "(default: 'Konflux_Pilot_Team'). "
                            "Leave empty to get all projects.",
                        },
                        "environment": {
                            "type": "string",
                            "description": "Environment to filter by (default: "
                            "'PRODUCTION', options: 'PRODUCTION', "
                            "'STAGING', 'DEVELOPMENT'). Leave "
                            "empty to get all environments.",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to include in "
                            "results (default: 30, max: 365). "
                            "Leave empty to get all deployments.",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date for filtering (format: "
                            "YYYY-MM-DD or YYYY-MM-DD HH:MM:SS). "
                            "Leave empty for no start date limit.",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date for filtering (format: "
                            "YYYY-MM-DD or YYYY-MM-DD HH:MM:SS). "
                            "Leave empty for no end date limit.",
                        },
                        "date_field": {
                            "type": "string",
                            "description": "Date field to filter on: "
                            "'finished_date', 'created_date', or "
                            "'updated_date' (default: "
                            "'finished_date').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of deployments to "
                            "return (default: 50, max: 200)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_deployment_frequency",
                description=(
                    "**DORA Deployment Frequency Metrics Tool** - Returns pre-aggregated "
                    "deployment frequency data optimized for DORA metrics visualization. "
                    "This tool is token-efficient, returning aggregated counts instead of "
                    "individual deployment records. Provides: (1) Summary statistics "
                    "(total deployments, unique deployment days, date range), (2) Daily "
                    "deployment counts, (3) Weekly deployment days count, (4) Monthly "
                    "deployment days count, (5) DORA performance level classification "
                    "(Elite >= 5 days/week, High >= 1 day/week, Medium >= 1 day/month, "
                    "Low < 1 day/month). Perfect for deployment frequency dashboards."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project name to filter by "
                            "(default: 'Konflux_Pilot_Team'). ",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to analyze " "(default: 180).",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date for filtering (format: "
                            "YYYY-MM-DD). Overrides days_back if set.",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date for filtering (format: "
                            "YYYY-MM-DD). Defaults to today.",
                        },
                    },
                    "required": [],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a deployment tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON encoded string with tool execution result
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Route to appropriate tool method
            if name == "get_deployments":
                result = await self._get_deployments_tool(arguments)
            elif name == "get_deployment_frequency":
                result = await self._get_deployment_frequency_tool(arguments)
            else:
                result = {"success": False, "error": f"Unknown deployment tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Deployment tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_deployments_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get deployment data with comprehensive filtering options using Grafana-like query structure.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with deployment data and filtering information
        """
        try:
            project = arguments.get("project", "")
            environment = arguments.get("environment", "")
            days_back = arguments.get("days_back", 0)
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            date_field = arguments.get("date_field", "finished_date")
            limit = arguments.get("limit", 50)

            # Validate date_field
            valid_date_fields = ["finished_date", "created_date", "updated_date"]
            if date_field not in valid_date_fields:
                return {
                    "success": False,
                    "error": (
                        f"Invalid date_field '{date_field}'. Must be one of: "
                        f"{', '.join(valid_date_fields)}"
                    ),
                }

            # Build the query using the exact structure provided
            base_query = """
            WITH _deployment_commit_rank AS (
                SELECT
                    pm.project_name,
                    IF(cdc._raw_data_table != '',
                       cdc._raw_data_table,
                       cdc.cicd_scope_id) as _raw_data_table,
                    cdc.id,
                    cdc.display_title,
                    cdc.url,
                    cdc.cicd_deployment_id,
                    cdc.cicd_scope_id,
                    result,
                    environment,
                    finished_date,
                    row_number() OVER(
                        PARTITION BY cdc.cicd_deployment_id
                        ORDER BY finished_date DESC
                    ) as _deployment_commit_rank
                FROM lake.cicd_deployment_commits cdc
                LEFT JOIN lake.project_mapping pm
                    ON cdc.cicd_scope_id = pm.row_id
                    AND pm.`table` = 'cicd_scopes'
                WHERE 1=1
            """

            # Build WHERE conditions for the CTE
            where_conditions = []

            # Always exclude github_pages deployments (not production)
            where_conditions.append("cdc.cicd_deployment_id NOT LIKE '%github_pages%'")
            where_conditions.append("cdc.display_title NOT LIKE '%github_pages%'")

            if project:
                where_conditions.append(f"pm.project_name IN ('{project}')")
            else:
                # Default to Konflux_Pilot_Team if no project specified
                where_conditions.append("pm.project_name IN ('Konflux_Pilot_Team')")

            where_conditions.append("environment = 'PRODUCTION'")

            # Date filtering - prioritize explicit date ranges over days_back
            if start_date or end_date:
                # Use explicit date range filtering
                if start_date:
                    # If start_date doesn't have time, assume 00:00:00
                    if len(start_date) == 10:  # YYYY-MM-DD format
                        start_date = f"{start_date} 00:00:00"
                    where_conditions.append(f"finished_date >= '{start_date}'")

                if end_date:
                    # If end_date doesn't have time, assume 23:59:59 to capture full day
                    if len(end_date) == 10:  # YYYY-MM-DD format
                        end_date = f"{end_date} 23:59:59"
                    where_conditions.append(f"finished_date <= '{end_date}'")
            elif days_back > 0:
                # Fall back to days_back filtering
                start_date_calc = datetime.now() - timedelta(days=days_back)
                start_date_str = start_date_calc.strftime("%Y-%m-%d %H:%M:%S")
                where_conditions.append(f"finished_date >= '{start_date_str}'")

            # Add WHERE conditions to the CTE
            if where_conditions:
                base_query += " AND " + " AND ".join(where_conditions)

            # Close the CTE and add the main SELECT
            base_query += """
            )
            SELECT
                project_name,
                cicd_deployment_id as deployment_id,
                CASE WHEN display_title = '' THEN 'N/A' ELSE display_title END as display_title,
                url,
                url as metric_hidden,
                result,
                environment,
                finished_date
            FROM _deployment_commit_rank
            WHERE _deployment_commit_rank = 1
            ORDER BY finished_date DESC
            """

            # Add limit
            base_query += f" LIMIT {limit}"

            self.logger.info(
                f"Getting deployments with filters: project={project}, "
                f"environment={environment}, days_back={days_back}, "
                f"start_date={start_date}, end_date={end_date}, "
                f"date_field={date_field}, limit={limit}"
            )

            result = await self.db_connection.execute_query(base_query, limit)

            if result["success"]:
                return {
                    "success": True,
                    "filters": {
                        "project": project if project else "all",
                        "environment": environment if environment else "all",
                        "days_back": days_back if days_back > 0 else "all",
                        "start_date": start_date if start_date else "all",
                        "end_date": end_date if end_date else "all",
                        "date_field": date_field,
                        "limit": limit,
                    },
                    "query": base_query,
                    "deployments": result["data"],
                }

            return result

        except Exception as e:
            self.logger.error(f"Get deployments failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_deployment_frequency_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get pre-aggregated deployment frequency data for DORA metrics.

        Returns aggregated counts by day/week/month instead of individual records.
        If full records are needed, use the get_deployments tool instead.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            TOON encoded dictionary with aggregated deployment frequency data
        """
        try:
            project = arguments.get("project", "Konflux_Pilot_Team")
            days_back = arguments.get("days_back", 180)
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")

            # Calculate date range
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days_back)
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")

            start_date_str = start_dt.strftime("%Y-%m-%d 00:00:00")
            end_date_str = end_dt.strftime("%Y-%m-%d 23:59:59")

            # Build the query to get daily deployment counts
            query = """
            WITH _deployment_commit_rank AS (
                SELECT
                    pm.project_name,
                    cdc.cicd_deployment_id,
                    DATE(finished_date) as deployment_date,
                    row_number() OVER(
                        PARTITION BY cdc.cicd_deployment_id
                        ORDER BY finished_date DESC
                    ) as _rank
                FROM lake.cicd_deployment_commits cdc
                LEFT JOIN lake.project_mapping pm
                    ON cdc.cicd_scope_id = pm.row_id
                    AND pm.`table` = 'cicd_scopes'
                WHERE cdc.cicd_deployment_id NOT LIKE '%github_pages%'
                    AND cdc.display_title NOT LIKE '%github_pages%'
                    AND environment = 'PRODUCTION'
                    AND result = 'SUCCESS'
            """

            query += f" AND pm.project_name IN ('{project}')"
            query += f" AND finished_date >= '{start_date_str}'"
            query += f" AND finished_date <= '{end_date_str}'"

            query += """
            ),
            _unique_deployments AS (
                SELECT project_name, cicd_deployment_id, deployment_date
                FROM _deployment_commit_rank
                WHERE _rank = 1
            ),
            _daily_counts AS (
                SELECT
                    deployment_date,
                    COUNT(*) as deployment_count
                FROM _unique_deployments
                GROUP BY deployment_date
            )
            SELECT
                deployment_date,
                deployment_count
            FROM _daily_counts
            ORDER BY deployment_date ASC
            """

            self.logger.info(
                f"Getting deployment frequency: project={project}, "
                f"start={start_date_str}, end={end_date_str}"
            )

            result = await self.db_connection.execute_query(query, 1000)

            if not result["success"]:
                return {"success": False, "error": result["error"]}

            # Build daily data dict
            daily_data = {}
            for row in result["data"]:
                date_str = str(row["deployment_date"])
                daily_data[date_str] = int(row["deployment_count"])

            # Calculate weekly aggregation (deployment days per week)
            weekly_data = {}
            for date_str, count in daily_data.items():
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                # Get week start (Monday)
                week_start = date_obj - timedelta(days=date_obj.weekday())
                week_key = week_start.strftime("%Y-%m-%d")
                if week_key not in weekly_data:
                    weekly_data[week_key] = {"deployment_days": 0, "total_deployments": 0}
                weekly_data[week_key]["deployment_days"] += 1
                weekly_data[week_key]["total_deployments"] += count

            # Calculate monthly aggregation (deployment days per month)
            monthly_data = {}
            for date_str, count in daily_data.items():
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                month_key = date_obj.strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {"deployment_days": 0, "total_deployments": 0}
                monthly_data[month_key]["deployment_days"] += 1
                monthly_data[month_key]["total_deployments"] += count

            # Calculate summary statistics
            total_deployments = sum(daily_data.values())
            unique_deployment_days = len(daily_data)
            total_weeks = len(weekly_data) if weekly_data else 1

            # Calculate averages
            avg_deployments_per_week = round(total_deployments / total_weeks, 2)
            avg_deployment_days_per_week = round(unique_deployment_days / total_weeks, 2)

            # Determine DORA level based on deployment days per week (NOTE: Is this important?)
            if avg_deployment_days_per_week >= 5:
                dora_level = "elite"
            elif avg_deployment_days_per_week >= 1:
                dora_level = "high"
            elif avg_deployment_days_per_week >= 0.25:  # ~1 day per month
                dora_level = "medium"
            else:
                dora_level = "low"

            return {
                "success": True,
                "project": project,
                "date_range": {
                    "start": start_dt.strftime("%Y-%m-%d"),
                    "end": end_dt.strftime("%Y-%m-%d"),
                    "days": (end_dt - start_dt).days,
                },
                "summary": {
                    "total_deployments": total_deployments,
                    "unique_deployment_days": unique_deployment_days,
                    "total_weeks": total_weeks,
                    "avg_deployments_per_week": avg_deployments_per_week,
                    "avg_deployment_days_per_week": avg_deployment_days_per_week,
                    "dora_level": dora_level,
                },
                "daily": daily_data,
                "weekly": weekly_data,
                "monthly": monthly_data,
            }

        except Exception as e:
            self.logger.error(f"Get deployment frequency failed: {e}")
            return {"success": False, "error": str(e)}
