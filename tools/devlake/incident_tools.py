#!/usr/bin/env python3
"""
Incident Tools for Konflux DevLake MCP Server

Contains tools for incident analysis and DORA metrics including Time to Restore Service
(MTTR) and Failed Deployment Recovery Time. Queries aligned with Konflux DevLake
Grafana dashboards.
"""

import asyncio
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class IncidentTools(BaseTool):
    """
    Incident-related tools for Konflux DevLake MCP Server.

    This class provides tools for incident analysis, DORA metrics (Time to Restore
    Service, Failed Deployment Recovery Time), and reporting with proper error
    handling and logging.
    """

    def __init__(self, db_connection):
        """
        Initialize incident tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.IncidentTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all incident tools.

        Returns:
            List of Tool objects for incident operations
        """
        return [
            Tool(
                name="get_incidents",
                description=(
                    "Retrieves incidents from the Konflux DevLake database with filtering. "
                    "Supports filtering by project, status, component, and date ranges. "
                    "Returns incident data including title, status, created_date, "
                    "resolution_date, lead_time_minutes, and URL."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Project name to filter incidents (required)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status (e.g., 'DONE', 'IN_PROGRESS', 'OPEN')",
                        },
                        "component": {
                            "type": "string",
                            "description": "Filter by component name",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back (default: 30)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 100)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
            Tool(
                name="get_failed_deployment_recovery_time",
                description=(
                    "DORA Metric: Failed Deployment Recovery Time (MTTR). "
                    "Calculates the median time to recover from incidents caused by deployments. "
                    "Returns: median recovery time in hours, incident count, and detailed "
                    "incident-deployment relationships. Aligned with Grafana dashboard queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Project name to filter (required)",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back (default: 180)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute an incident tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_incidents":
                result = await self._get_incidents_tool(arguments)
            elif name == "get_failed_deployment_recovery_time":
                result = await self._get_failed_deployment_recovery_time(arguments)
            else:
                result = {"success": False, "error": f"Unknown incident tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Incident tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_incidents_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get incidents with Time to Restore Service metrics.

        Aligned with Grafana dashboard: DORA Details - Time to Restore Service
        Returns median MTTR, incident count, and incident details.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with incident data and MTTR metrics
        """
        try:
            project_name = arguments.get("project_name", "")
            status = arguments.get("status", "")
            component = arguments.get("component", "")
            days_back = arguments.get("days_back", 30)
            limit = arguments.get("limit", 100)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Query 1: Median Time to Restore Service (Panel 1)
            median_query = f"""
                WITH _incidents AS (
                    SELECT
                        DISTINCT i.id,
                        CAST(i.lead_time_minutes AS SIGNED) AS lead_time_minutes
                    FROM lake.incidents i
                    JOIN lake.project_mapping pm ON i.scope_id = pm.row_id
                        AND pm.`table` = i.`table`
                    WHERE pm.project_name = '{project_name}'
                        AND i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ),
                _median_mttr_ranks AS (
                    SELECT
                        id,
                        lead_time_minutes,
                        PERCENT_RANK() OVER (ORDER BY lead_time_minutes) AS ranks
                    FROM _incidents
                    WHERE lead_time_minutes IS NOT NULL
                ),
                _median_mttr AS (
                    SELECT MAX(lead_time_minutes) AS median_time_to_resolve
                    FROM _median_mttr_ranks
                    WHERE ranks <= 0.5
                )
                SELECT median_time_to_resolve / 60 AS median_time_to_resolve_in_hours
                FROM _median_mttr
            """

            # Query 2: Incident Count (Panel 2)
            count_query = f"""
                SELECT COUNT(DISTINCT i.id) AS incident_count
                FROM lake.incidents i
                JOIN lake.project_mapping pm ON i.scope_id = pm.row_id
                    AND pm.`table` = i.`table`
                WHERE pm.project_name = '{project_name}'
                    AND i.created_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Query 3: Incident Details (Panel 3)
            # Build additional WHERE conditions
            extra_conditions = ""
            if status:
                extra_conditions += f" AND i.status = '{status}'"
            if component:
                extra_conditions += f" AND i.component = '{component}'"

            details_query = f"""
                SELECT DISTINCT
                    i.id AS incident_id,
                    i.title,
                    i.url,
                    i.resolution_date,
                    CAST(i.lead_time_minutes / 60 AS SIGNED) AS time_to_restore_service
                FROM lake.incidents i
                JOIN lake.project_mapping pm ON i.scope_id = pm.row_id
                    AND pm.`table` = i.`table`
                WHERE pm.project_name = '{project_name}'
                    AND i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                    {extra_conditions}
                ORDER BY i.resolution_date DESC
            """

            # Execute queries in parallel
            median_result, count_result, details_result = await asyncio.gather(
                self.db_connection.execute_query(median_query, 1),
                self.db_connection.execute_query(count_query, 1),
                self.db_connection.execute_query(details_query, limit),
            )

            # Extract median MTTR
            median_time_to_restore_hours = None
            if median_result["success"] and median_result["data"]:
                median_hours = median_result["data"][0].get("median_time_to_resolve_in_hours")
                if median_hours is not None:
                    median_time_to_restore_hours = round(float(median_hours), 2)

            # Extract incident count
            incident_count = 0
            if count_result["success"] and count_result["data"]:
                incident_count = int(count_result["data"][0].get("incident_count", 0))

            # Extract incident details
            incidents = []
            if details_result["success"]:
                incidents = details_result["data"]

            return {
                "success": True,
                "project_name": project_name,
                "days_back": days_back,
                "median_time_to_restore_service_hours": median_time_to_restore_hours,
                "incident_count": incident_count,
                "incidents": incidents,
            }

        except Exception as e:
            self.logger.error(f"Get incidents failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_failed_deployment_recovery_time(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        DORA Metric: Failed Deployment Recovery Time.

        Calculates median time to recover from incidents caused by deployments.
        Query aligned with Grafana dashboard: DORADetails-FailedDeploymentRecoveryTime.json

        Args:
            arguments: Tool arguments

        Returns:
            Dictionary with recovery time metrics and incident details
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 180)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Query 1: Median Recovery Time (aligned with Grafana dashboard)
            median_query = f"""
                WITH _deployments AS (
                    SELECT
                        cdc.cicd_deployment_id AS deployment_id,
                        MAX(cdc.finished_date) AS deployment_finished_date
                    FROM lake.cicd_deployment_commits cdc
                    JOIN lake.project_mapping pm ON cdc.cicd_scope_id = pm.row_id
                        AND pm.`table` = 'cicd_scopes'
                    WHERE pm.project_name = '{project_name}'
                        AND cdc.result = 'SUCCESS'
                        AND cdc.environment = 'PRODUCTION'
                    GROUP BY cdc.cicd_deployment_id
                    HAVING MAX(cdc.finished_date) >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ),
                _incidents_for_deployments AS (
                    SELECT
                        i.id AS incident_id,
                        i.created_date AS incident_create_date,
                        i.resolution_date AS incident_resolution_date,
                        fd.deployment_id AS caused_by_deployment,
                        fd.deployment_finished_date
                    FROM lake.incidents i
                    LEFT JOIN lake.project_incident_deployment_relationships pim ON i.id = pim.id
                    JOIN _deployments fd ON pim.deployment_id = fd.deployment_id
                    WHERE i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ),
                _recovery_time_ranks AS (
                    SELECT
                        incident_id,
                        incident_resolution_date,
                        deployment_finished_date,
                        TIMESTAMPDIFF(MINUTE, deployment_finished_date, incident_resolution_date)
                            AS recovery_time_minutes,
                        PERCENT_RANK() OVER (
                            ORDER BY TIMESTAMPDIFF(
                                MINUTE, deployment_finished_date, incident_resolution_date
                            )
                        ) AS ranks
                    FROM _incidents_for_deployments
                    WHERE incident_resolution_date IS NOT NULL
                )
                SELECT
                    MAX(recovery_time_minutes) AS median_recovery_time_minutes
                FROM _recovery_time_ranks
                WHERE ranks <= 0.5
            """

            # Query 2: Incident count caused by deployments
            count_query = f"""
                WITH _deployments AS (
                    SELECT
                        cdc.cicd_deployment_id AS deployment_id,
                        MAX(cdc.finished_date) AS deployment_finished_date
                    FROM lake.cicd_deployment_commits cdc
                    JOIN lake.project_mapping pm ON cdc.cicd_scope_id = pm.row_id
                        AND pm.`table` = 'cicd_scopes'
                    WHERE pm.project_name = '{project_name}'
                        AND cdc.result = 'SUCCESS'
                        AND cdc.environment = 'PRODUCTION'
                    GROUP BY cdc.cicd_deployment_id
                    HAVING MAX(cdc.finished_date) >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ),
                _incidents_for_deployments AS (
                    SELECT
                        i.id AS incident_id
                    FROM lake.incidents i
                    LEFT JOIN lake.project_incident_deployment_relationships pim ON i.id = pim.id
                    JOIN _deployments fd ON pim.deployment_id = fd.deployment_id
                    WHERE i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                )
                SELECT COUNT(DISTINCT incident_id) AS total_incidents
                FROM _incidents_for_deployments
            """

            # Query 3: Deployment and incident details (matches Grafana Panel 3)
            details_query = f"""
                WITH _deployments AS (
                    SELECT
                        cdc.cicd_deployment_id AS deployment_id,
                        MAX(cdc.finished_date) AS deployment_finished_date
                    FROM lake.cicd_deployment_commits cdc
                    JOIN lake.project_mapping pm ON cdc.cicd_scope_id = pm.row_id
                        AND pm.`table` = 'cicd_scopes'
                    WHERE pm.project_name = '{project_name}'
                        AND cdc.result = 'SUCCESS'
                        AND cdc.environment = 'PRODUCTION'
                    GROUP BY cdc.cicd_deployment_id
                    HAVING MAX(cdc.finished_date) >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                )
                SELECT
                    fd.deployment_id,
                    fd.deployment_finished_date,
                    i.id AS incident_caused_by_deployment,
                    i.title AS incident_title,
                    i.url AS incident_url,
                    i.resolution_date AS incident_resolution_date,
                    TIMESTAMPDIFF(HOUR, fd.deployment_finished_date, i.resolution_date)
                        AS failed_deployment_recovery_time
                FROM lake.incidents i
                LEFT JOIN lake.project_incident_deployment_relationships pim ON i.id = pim.id
                JOIN _deployments fd ON pim.deployment_id = fd.deployment_id
                WHERE i.resolution_date IS NOT NULL
                    AND i.resolution_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ORDER BY fd.deployment_finished_date DESC
            """

            # Execute queries in parallel
            median_result, count_result, details_result = await asyncio.gather(
                self.db_connection.execute_query(median_query, 1),
                self.db_connection.execute_query(count_query, 1),
                self.db_connection.execute_query(details_query, 100),
            )

            # Extract median recovery time
            median_recovery_time_minutes = None
            median_recovery_time_hours = None
            if median_result["success"] and median_result["data"]:
                median_minutes = median_result["data"][0].get("median_recovery_time_minutes")
                if median_minutes is not None:
                    median_recovery_time_minutes = int(median_minutes)
                    median_recovery_time_hours = round(median_minutes / 60, 2)

            # Extract incident count
            total_incidents = 0
            if count_result["success"] and count_result["data"]:
                total_incidents = int(count_result["data"][0].get("total_incidents", 0))

            # Extract incident details
            incident_details = []
            if details_result["success"]:
                incident_details = details_result["data"]

            return {
                "success": True,
                "project_name": project_name,
                "days_back": days_back,
                "median_recovery_time_minutes": median_recovery_time_minutes,
                "median_recovery_time_hours": median_recovery_time_hours,
                "incidents_caused_by_deployments": total_incidents,
                "incident_details": incident_details,
            }

        except Exception as e:
            self.logger.error(f"Get failed deployment recovery time failed: {e}")
            return {"success": False, "error": str(e)}
