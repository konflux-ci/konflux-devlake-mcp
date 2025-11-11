#!/usr/bin/env python3
"""
Incident Tools for Konflux DevLake MCP Server

Contains tools for incident analysis and management with improved modularity
and maintainability.
"""

import json
from typing import Any, Dict, List

from mcp.types import Tool

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call
from utils.db import DateTimeEncoder


class IncidentTools(BaseTool):
    """
    Incident-related tools for Konflux DevLake MCP Server.

    This class provides tools for incident analysis, filtering, and reporting
    with proper error handling and logging.
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
                    "🚨 **Comprehensive Incident Analysis Tool** - Retrieves unique "
                    "incidents from the Konflux DevLake database with advanced "
                    "filtering capabilities. This tool automatically deduplicates "
                    "incidents by incident_key to show only the most recent "
                    "version of each incident. Supports filtering by status "
                    "(e.g., 'DONE', 'IN_PROGRESS', 'OPEN'), component name, and "
                    "flexible date ranges. Provides comprehensive incident data "
                    "including incident_key, title, description, status, "
                    "created_date, resolution_date, lead_time_minutes, "
                    "component, and URL. Perfect for incident analysis, "
                    "reporting, and understanding operational issues. "
                    "Returns incidents sorted by creation date (newest first)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter incidents by status (e.g., "
                            "'DONE', 'IN_PROGRESS', 'OPEN'). "
                            "Leave empty to get all statuses.",
                        },
                        "component": {
                            "type": "string",
                            "description": "Filter incidents by component name. "
                            "Leave empty to get all components.",
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to include in "
                            "results (default: 30, max: 365). "
                            "Leave empty to get all incidents.",
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
                            "'created_date', 'resolution_date', "
                            "or 'updated_date' (default: "
                            "'created_date').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of incidents to "
                            "return (default: 100, max: 500)",
                        },
                    },
                    "required": [],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute an incident tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            JSON string with tool execution result
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Route to appropriate tool method
            if name == "get_incidents":
                result = await self._get_incidents_tool(arguments)
            else:
                result = {"success": False, "error": f"Unknown incident tool: {name}"}

            return json.dumps(result, indent=2, cls=DateTimeEncoder)

        except Exception as e:
            self.logger.error(f"Incident tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return json.dumps(error_result, indent=2, cls=DateTimeEncoder)

    async def _get_incidents_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get unique incidents with comprehensive filtering options.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with incident data and filtering information
        """
        try:
            status = arguments.get("status", "")
            component = arguments.get("component", "")
            days_back = arguments.get("days_back", 0)
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            date_field = arguments.get("date_field", "created_date")
            limit = arguments.get("limit", 100)

            # Validate date_field
            valid_date_fields = ["created_date", "resolution_date", "updated_date"]
            if date_field not in valid_date_fields:
                return {
                    "success": False,
                    "error": (
                        f"Invalid date_field '{date_field}'. Must be one of: "
                        f"{', '.join(valid_date_fields)}"
                    ),
                }

            base_query = (
                "SELECT t1.* FROM lake.incidents t1 "
                "INNER JOIN ("
                "  SELECT incident_key, MAX(id) AS max_id "
                "  FROM lake.incidents GROUP BY incident_key"
                ") t2 "
                "ON t1.incident_key = t2.incident_key AND t1.id = t2.max_id "
            )

            # Build WHERE clause with filters
            where_conditions = []

            if status:
                where_conditions.append(f"t1.status = '{status}'")

            if component:
                where_conditions.append(f"t1.component = '{component}'")

            # Date filtering - prioritize explicit date ranges over days_back
            if start_date or end_date:
                # Use explicit date range filtering
                if start_date:
                    # If start_date doesn't have time, assume 00:00:00
                    if len(start_date) == 10:  # YYYY-MM-DD format
                        start_date = f"{start_date} 00:00:00"
                    where_conditions.append(f"t1.{date_field} >= '{start_date}'")

                if end_date:
                    # If end_date doesn't have time, assume 23:59:59 to capture full day
                    if len(end_date) == 10:  # YYYY-MM-DD format
                        end_date = f"{end_date} 23:59:59"
                    where_conditions.append(f"t1.{date_field} <= '{end_date}'")
            elif days_back > 0:
                # Fall back to days_back filtering
                from datetime import datetime, timedelta

                start_date_calc = datetime.now() - timedelta(days=days_back)
                start_date_str = start_date_calc.strftime("%Y-%m-%d %H:%M:%S")
                where_conditions.append(f"t1.{date_field} >= '{start_date_str}'")

            # Add WHERE clause if we have conditions
            if where_conditions:
                base_query += "WHERE " + " AND ".join(where_conditions) + " "

            # Add ordering and limit
            base_query += f"ORDER BY t1.{date_field} DESC "
            base_query += f"LIMIT {limit}"

            log_message = (
                f"Getting incidents with filters: status={status}, "
                f"component={component}, days_back={days_back}, "
                f"start_date={start_date}, end_date={end_date}, "
                f"date_field={date_field}, limit={limit}"
            )
            self.logger.info(log_message)

            result = await self.db_connection.execute_query(base_query, limit)

            if result["success"]:
                return {
                    "success": True,
                    "filters": {
                        "status": status if status else "all",
                        "component": component if component else "all",
                        "days_back": days_back if days_back > 0 else "all",
                        "start_date": start_date if start_date else "all",
                        "end_date": end_date if end_date else "all",
                        "date_field": date_field,
                        "limit": limit,
                    },
                    "query": base_query,
                    "incidents": result["data"],
                }

            return result

        except Exception as e:
            self.logger.error(f"Get incidents failed: {e}")
            return {"success": False, "error": str(e)}
