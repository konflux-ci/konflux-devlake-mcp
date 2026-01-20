#!/usr/bin/env python3
"""
PR Statistics Tools for Konflux DevLake MCP Server

Contains tools for analyzing pull request statistics including
open PRs, repository breakdown, PR type analysis, and stale PR identification.
"""

import asyncio
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class PRStatsTools(BaseTool):
    """
    PR Statistics tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing pull request statistics,
    including open PRs, repository breakdown, and stale PR identification.
    """

    def __init__(self, db_connection):
        """
        Initialize PR stats tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.PRStatsTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all PR statistics tools.

        Returns:
            List of Tool objects for PR statistics operations
        """
        return [
            Tool(
                name="get_pr_stats",
                description=(
                    "**PR Statistics Tool** - Provides comprehensive pull request statistics "
                    "for a DevLake project. Returns open PRs, repository breakdown, PR type "
                    "analysis (engineering vs bot/dependency), and stale PR identification. "
                    "Optimized with parallel queries and repo ID pre-fetching."
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
        Execute a PR stats tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_pr_stats":
                result = await self._get_pr_stats(arguments)
            else:
                result = {"success": False, "error": f"Unknown PR stats tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"PR stats tool call failed: {e}")
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

    def _categorize_pr(self, title: str) -> str:
        """
        Categorize PR based on title.

        Args:
            title: PR title

        Returns:
            Category string: 'dependency_bot', 'wip_exclude', or 'engineering'
        """
        title_lower = title.lower() if title else ""

        # Check for dependency/bot PRs
        dep_patterns = [
            "chore(deps)",
            "fix(deps)",
            "update docker",
            "update digest",
            "dependencies",
            "renovate",
            "dependabot",
            "bump ",
        ]
        for pattern in dep_patterns:
            if pattern in title_lower:
                return "dependency_bot"

        # Check for WIP/DNM PRs
        wip_patterns = ["dnm", "do not merge", "wip", "draft", "[wip]", "[dnm]"]
        for pattern in wip_patterns:
            if pattern in title_lower:
                return "wip_exclude"

        return "engineering"

    async def _get_pr_stats(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive PR statistics for a project.

        Args:
            arguments: Tool arguments containing project_name and days_back

        Returns:
            Dictionary with PR statistics
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 30)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Step 1: Get repo IDs for this project
            repo_ids_query = f"""
                SELECT DISTINCT r.id, r.name, r.url
                FROM lake.repos r
                INNER JOIN lake.project_mapping pm ON r.id = pm.row_id
                WHERE pm.project_name = '{project_name}'
                AND pm.`table` = 'repos'
            """
            repo_ids_result = await self._execute_with_timeout(repo_ids_query, 500, timeout=30)

            if not repo_ids_result.get("success") or not repo_ids_result.get("data"):
                return {
                    "success": True,
                    "message": "No repositories found for project",
                    "project_name": project_name,
                    "analysis_period_days": days_back,
                    "summary": {
                        "total_prs": 0,
                        "merged_prs": 0,
                        "open_prs": 0,
                        "closed_prs": 0,
                        "merge_rate": 0.0,
                        "stale_prs_7d": 0,
                        "stale_prs_14d": 0,
                    },
                    "open_prs": [],
                    "repo_breakdown": [],
                    "pr_type_breakdown": {},
                    "stale_prs": [],
                }

            repo_ids = [f"'{r['id']}'" for r in repo_ids_result["data"]]
            repo_ids_str = ",".join(repo_ids)

            # Step 2: Build queries
            # Query 2: Open PRs (using DISTINCT to avoid duplicates)
            open_prs_query = f"""
                SELECT DISTINCT
                    r.name as repo_name,
                    pr.id as pr_id,
                    pr.title,
                    pr.url,
                    pr.created_date,
                    TIMESTAMPDIFF(DAY, pr.created_date, NOW()) as days_open,
                    pr.additions,
                    pr.deletions,
                    (COALESCE(pr.additions, 0) + COALESCE(pr.deletions, 0)) as total_changes
                FROM lake.pull_requests pr
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE r.id IN ({repo_ids_str})
                AND pr.status = 'OPEN'
                ORDER BY days_open DESC
            """

            # Query 3: PR Summary per Repository (using COUNT DISTINCT to avoid duplicates)
            repo_summary_query = f"""
                SELECT
                    r.name as repo_name,
                    COUNT(DISTINCT pr.id) as total_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'MERGED' THEN pr.id END) as merged_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN' THEN pr.id END) as open_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'CLOSED' THEN pr.id END) as closed_prs
                FROM lake.pull_requests pr
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE r.id IN ({repo_ids_str})
                AND pr.created_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                GROUP BY r.name
                ORDER BY total_prs DESC
            """

            # Query 4: PR Type Breakdown (Bot vs Engineering) - using COUNT DISTINCT
            pr_type_query = f"""
                SELECT
                    CASE
                        WHEN LOWER(pr.title) LIKE '%chore(deps)%'
                             OR LOWER(pr.title) LIKE '%fix(deps)%'
                             OR LOWER(pr.title) LIKE '%update%docker%'
                             OR LOWER(pr.title) LIKE '%update%digest%'
                             OR LOWER(pr.title) LIKE '%dependencies%'
                             OR LOWER(pr.title) LIKE '%renovate%'
                             OR LOWER(pr.title) LIKE '%dependabot%'
                             OR LOWER(pr.title) LIKE '%bump %'
                             THEN 'dependency_bot'
                        WHEN LOWER(pr.title) LIKE '%dnm%'
                             OR LOWER(pr.title) LIKE '%do not merge%'
                             OR LOWER(pr.title) LIKE '%wip%'
                             OR LOWER(pr.title) LIKE '%draft%'
                             THEN 'wip_exclude'
                        ELSE 'engineering'
                    END as pr_type,
                    COUNT(DISTINCT pr.id) as total_count,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN' THEN pr.id END) as open_count,
                    COUNT(DISTINCT CASE WHEN pr.status = 'MERGED' THEN pr.id END) as merged_count,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN'
                         AND TIMESTAMPDIFF(DAY, pr.created_date, NOW()) > 14
                         THEN pr.id END) as stale_14d
                FROM lake.pull_requests pr
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE r.id IN ({repo_ids_str})
                AND pr.created_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                GROUP BY pr_type
            """

            # Query 5: Stale PRs (>7 days) - using DISTINCT to avoid duplicates
            stale_prs_query = f"""
                SELECT DISTINCT
                    r.name as repo_name,
                    pr.id as pr_id,
                    pr.title,
                    pr.url,
                    TIMESTAMPDIFF(DAY, pr.created_date, NOW()) as days_open,
                    (COALESCE(pr.additions, 0) + COALESCE(pr.deletions, 0)) as total_changes
                FROM lake.pull_requests pr
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE r.id IN ({repo_ids_str})
                AND pr.status = 'OPEN'
                AND TIMESTAMPDIFF(DAY, pr.created_date, NOW()) > 7
                ORDER BY days_open DESC
                LIMIT 50
            """

            # Query 6: Overall summary - using COUNT DISTINCT to avoid duplicates
            summary_query = f"""
                SELECT
                    COUNT(DISTINCT pr.id) as total_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'MERGED' THEN pr.id END) as merged_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN' THEN pr.id END) as open_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'CLOSED' THEN pr.id END) as closed_prs,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN'
                         AND TIMESTAMPDIFF(DAY, pr.created_date, NOW()) > 7
                         THEN pr.id END) as stale_prs_7d,
                    COUNT(DISTINCT CASE WHEN pr.status = 'OPEN'
                         AND TIMESTAMPDIFF(DAY, pr.created_date, NOW()) > 14
                         THEN pr.id END) as stale_prs_14d
                FROM lake.pull_requests pr
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE r.id IN ({repo_ids_str})
                AND pr.created_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
            """

            # Step 3: Run all queries in parallel
            results = await asyncio.gather(
                self._execute_with_timeout(open_prs_query, 200, timeout=60),
                self._execute_with_timeout(repo_summary_query, 100, timeout=60),
                self._execute_with_timeout(pr_type_query, 10, timeout=60),
                self._execute_with_timeout(stale_prs_query, 50, timeout=60),
                self._execute_with_timeout(summary_query, 1, timeout=60),
                return_exceptions=True,
            )

            (
                open_prs_result,
                repo_summary_result,
                pr_type_result,
                stale_prs_result,
                summary_result,
            ) = results

            # Helper function to safely extract data
            def safe_get_data(result, default=None):
                if default is None:
                    default = []
                if isinstance(result, Exception):
                    self.logger.error(f"Query failed with exception: {result}")
                    return default
                if not result.get("success"):
                    return default
                return result.get("data", default)

            # Process results
            open_prs_data = safe_get_data(open_prs_result)
            repo_breakdown_data = safe_get_data(repo_summary_result)
            pr_type_data = safe_get_data(pr_type_result)
            stale_prs_data = safe_get_data(stale_prs_result)

            # Process summary
            summary_data = {}
            if not isinstance(summary_result, Exception) and summary_result.get("success"):
                summary_data = summary_result["data"][0] if summary_result["data"] else {}

            # Convert numeric values
            def to_int(val):
                if val is None:
                    return 0
                return int(float(val))

            total_prs = to_int(summary_data.get("total_prs", 0))
            merged_prs = to_int(summary_data.get("merged_prs", 0))
            open_prs_count = to_int(summary_data.get("open_prs", 0))
            closed_prs = to_int(summary_data.get("closed_prs", 0))
            stale_7d = to_int(summary_data.get("stale_prs_7d", 0))
            stale_14d = to_int(summary_data.get("stale_prs_14d", 0))

            merge_rate = round((merged_prs / total_prs * 100), 1) if total_prs > 0 else 0.0

            # Format open PRs with category
            formatted_open_prs = []
            for pr in open_prs_data:
                days_open = to_int(pr.get("days_open", 0))
                formatted_open_prs.append(
                    {
                        "repo_name": pr.get("repo_name", ""),
                        "title": pr.get("title", ""),
                        "url": pr.get("url", ""),
                        "days_open": days_open,
                        "additions": to_int(pr.get("additions", 0)),
                        "deletions": to_int(pr.get("deletions", 0)),
                        "total_changes": to_int(pr.get("total_changes", 0)),
                        "category": self._categorize_pr(pr.get("title", "")),
                        "is_stale": days_open > 7,
                    }
                )

            # Format repo breakdown with merge rate
            formatted_repo_breakdown = []
            for repo in repo_breakdown_data:
                repo_total = to_int(repo.get("total_prs", 0))
                repo_merged = to_int(repo.get("merged_prs", 0))
                repo_merge_rate = (
                    round((repo_merged / repo_total * 100), 1) if repo_total > 0 else 0.0
                )
                formatted_repo_breakdown.append(
                    {
                        "repo_name": repo.get("repo_name", ""),
                        "total_prs": repo_total,
                        "merged_prs": repo_merged,
                        "open_prs": to_int(repo.get("open_prs", 0)),
                        "closed_prs": to_int(repo.get("closed_prs", 0)),
                        "merge_rate": repo_merge_rate,
                    }
                )

            # Format PR type breakdown
            pr_type_breakdown = {}
            for pr_type in pr_type_data:
                type_name = pr_type.get("pr_type", "unknown")
                type_total = to_int(pr_type.get("total_count", 0))
                type_merged = to_int(pr_type.get("merged_count", 0))
                type_merge_rate = (
                    round((type_merged / type_total * 100), 1) if type_total > 0 else 0.0
                )
                pr_type_breakdown[type_name] = {
                    "total": type_total,
                    "open": to_int(pr_type.get("open_count", 0)),
                    "merged": type_merged,
                    "stale_14d": to_int(pr_type.get("stale_14d", 0)),
                    "merge_rate": type_merge_rate,
                }

            # Format stale PRs with category
            formatted_stale_prs = []
            for pr in stale_prs_data:
                formatted_stale_prs.append(
                    {
                        "repo_name": pr.get("repo_name", ""),
                        "title": pr.get("title", ""),
                        "url": pr.get("url", ""),
                        "days_open": to_int(pr.get("days_open", 0)),
                        "category": self._categorize_pr(pr.get("title", "")),
                        "total_changes": to_int(pr.get("total_changes", 0)),
                    }
                )

            return {
                "success": True,
                "project_name": project_name,
                "analysis_period_days": days_back,
                "summary": {
                    "total_prs": total_prs,
                    "merged_prs": merged_prs,
                    "open_prs": open_prs_count,
                    "closed_prs": closed_prs,
                    "merge_rate": merge_rate,
                    "stale_prs_7d": stale_7d,
                    "stale_prs_14d": stale_14d,
                },
                "open_prs": formatted_open_prs,
                "repo_breakdown": formatted_repo_breakdown,
                "pr_type_breakdown": pr_type_breakdown,
                "stale_prs": formatted_stale_prs,
            }

        except Exception as e:
            self.logger.error(f"Get PR stats failed: {e}")
            return {"success": False, "error": str(e)}
