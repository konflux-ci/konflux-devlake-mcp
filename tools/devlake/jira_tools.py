#!/usr/bin/env python3
"""
Jira Tools for Konflux DevLake MCP Server

Provides tools for querying Jira data including Features, Epics, Stories, and Bugs
from the DevLake database. Filters by DevLake project using project_mapping.
"""

import asyncio
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class JiraTools(BaseTool):
    """
    Jira-related tools for Konflux DevLake MCP Server.

    Provides tools for querying Jira issues (Features, Epics, Stories, Bugs)
    filtered by DevLake project.
    """

    def __init__(self, db_connection):
        """
        Initialize Jira tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.JiraTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all Jira tools.

        Returns:
            List of Tool objects
        """
        return [
            Tool(
                name="get_jira_features",
                description=(
                    "Retrieves all Jira Features for a DevLake project. Returns feature details "
                    "including key, summary, status, priority, epic, assignee, story points, "
                    "and dates. Supports filtering by status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "DevLake project name (required)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status (e.g., 'Done', 'In Progress')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 100)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a Jira tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_jira_features":
                result = await self._get_jira_features(arguments)
            else:
                result = {"success": False, "error": f"Unknown Jira tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Jira tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_jira_features(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get Jira Features for a DevLake project.

        Args:
            arguments: Tool arguments

        Returns:
            Dictionary with Jira features data
        """
        try:
            project_name = arguments.get("project_name", "")
            status = arguments.get("status", "")
            limit = arguments.get("limit", 100)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # First, get board IDs for the project
            board_ids = await self._get_board_ids_for_project(project_name)
            if not board_ids:
                return {
                    "success": True,
                    "project_name": project_name,
                    "message": "No Jira boards found for this project",
                    "total_features": 0,
                    "features": [],
                }

            # Build WHERE conditions
            status_filter = ""
            if status:
                status_filter = f"AND i.status_name = '{status}'"

            # Query for Features
            features_query = f"""
                SELECT DISTINCT
                    i.issue_key,
                    i.summary,
                    i.type,
                    i.status_name,
                    i.status_key,
                    i.priority_name,
                    i.epic_key,
                    i.assignee_display_name,
                    i.creator_display_name,
                    i.story_point,
                    i.created,
                    i.updated,
                    i.resolution_date,
                    i.lead_time_minutes,
                    i.sprint_name,
                    i.components,
                    i.fix_versions,
                    i.self AS url
                FROM lake._tool_jira_issues i
                INNER JOIN lake._tool_jira_board_issues bi
                    ON i.connection_id = bi.connection_id
                    AND i.issue_id = bi.issue_id
                WHERE bi.board_id IN ({board_ids})
                    AND i.type = 'Feature'
                    {status_filter}
                ORDER BY i.created DESC
            """

            # Query for summary stats
            summary_query = f"""
                SELECT
                    COUNT(DISTINCT i.issue_id) AS total_features,
                    COUNT(DISTINCT CASE WHEN i.status_name = 'Done' THEN i.issue_id END) AS done,
                    COUNT(DISTINCT CASE WHEN i.status_name = 'In Progress' THEN i.issue_id END)
                        AS in_progress,
                    COUNT(DISTINCT CASE WHEN i.status_name NOT IN ('Done', 'In Progress')
                        THEN i.issue_id END) AS other,
                    ROUND(AVG(i.story_point), 1) AS avg_story_points,
                    SUM(i.story_point) AS total_story_points
                FROM lake._tool_jira_issues i
                INNER JOIN lake._tool_jira_board_issues bi
                    ON i.connection_id = bi.connection_id
                    AND i.issue_id = bi.issue_id
                WHERE bi.board_id IN ({board_ids})
                    AND i.type = 'Feature'
            """

            # Execute queries in parallel
            features_result, summary_result = await asyncio.gather(
                self.db_connection.execute_query(features_query, limit),
                self.db_connection.execute_query(summary_query, 1),
            )

            # Process features
            features = []
            if features_result["success"] and features_result["data"]:
                for row in features_result["data"]:
                    features.append(
                        {
                            "issue_key": row.get("issue_key"),
                            "summary": row.get("summary"),
                            "status": row.get("status_name"),
                            "priority": row.get("priority_name"),
                            "epic_key": row.get("epic_key"),
                            "assignee": row.get("assignee_display_name"),
                            "creator": row.get("creator_display_name"),
                            "story_points": (
                                float(row["story_point"]) if row.get("story_point") else None
                            ),
                            "created": str(row.get("created", "")) if row.get("created") else None,
                            "updated": str(row.get("updated", "")) if row.get("updated") else None,
                            "resolution_date": (
                                str(row.get("resolution_date", ""))
                                if row.get("resolution_date")
                                else None
                            ),
                            "lead_time_hours": (
                                round(int(row["lead_time_minutes"]) / 60, 1)
                                if row.get("lead_time_minutes")
                                else None
                            ),
                            "sprint": row.get("sprint_name"),
                            "components": row.get("components"),
                            "fix_versions": row.get("fix_versions"),
                            "url": row.get("url"),
                        }
                    )

            # Process summary
            summary = {
                "total_features": 0,
                "done": 0,
                "in_progress": 0,
                "other": 0,
                "avg_story_points": None,
                "total_story_points": None,
            }
            if summary_result["success"] and summary_result["data"]:
                s = summary_result["data"][0]
                summary = {
                    "total_features": int(s.get("total_features", 0)),
                    "done": int(s.get("done", 0)),
                    "in_progress": int(s.get("in_progress", 0)),
                    "other": int(s.get("other", 0)),
                    "avg_story_points": (
                        float(s["avg_story_points"]) if s.get("avg_story_points") else None
                    ),
                    "total_story_points": (
                        float(s["total_story_points"]) if s.get("total_story_points") else None
                    ),
                }

            return {
                "success": True,
                "project_name": project_name,
                "summary": summary,
                "features": features,
            }

        except Exception as e:
            self.logger.error(f"Get Jira features failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_board_ids_for_project(self, project_name: str) -> str:
        """
        Get Jira board IDs for a DevLake project.

        Args:
            project_name: DevLake project name

        Returns:
            Comma-separated string of board IDs, or empty string if none found
        """
        query = f"""
            SELECT DISTINCT
                CAST(SUBSTRING_INDEX(pm.row_id, ':', -1) AS UNSIGNED) AS board_id
            FROM lake.project_mapping pm
            WHERE pm.project_name = '{project_name}'
                AND pm.`table` = 'boards'
                AND pm.row_id LIKE 'jira:JiraBoard:%'
        """
        result = await self.db_connection.execute_query(query, 100)
        if result["success"] and result["data"]:
            board_ids = [str(row["board_id"]) for row in result["data"]]
            return ", ".join(board_ids)
        return ""
