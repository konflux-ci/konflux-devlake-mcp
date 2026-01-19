#!/usr/bin/env python3
"""
PR Retest Analysis Tools for Konflux DevLake MCP Server

Contains tools for analyzing pull requests that required manual retest commands
(comments containing "/retest") with comprehensive statistics and insights.
"""

from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class PRRetestTools(BaseTool):
    """
    PR Retest Analysis tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing pull requests that required
    manual retest commands, identifying patterns, and providing actionable insights.
    """

    def __init__(self, db_connection):
        """
        Initialize PR retest tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.PRRetestTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all PR retest analysis tools.

        Returns:
            List of Tool objects for PR retest operations
        """
        return [
            Tool(
                name="analyze_pr_retests",
                description=(
                    "**Comprehensive PR Retest Analysis Tool** - Analyzes all pull requests "
                    "in a repository within a DevLake project that required manual retest "
                    "commands (comments containing '/retest'). Provides detailed statistics "
                    "including: total count of manual retest comments (excluding bot comments), "
                    "number of PRs affected, average retests per PR, top PRs with most retests "
                    "(including repo name, PR title, URL, number of retests, PR duration, "
                    "changes, and status), per-repository breakdown, weekly trend data, "
                    "analysis of root causes and failure patterns, breakdown by PR category, "
                    "and timeline visualization data. Focuses on technical patterns and "
                    "systemic issues without financial impacts or personal attribution."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": (
                                "Repository name to analyze (e.g., 'integration-service', "
                                "'build-service', 'release-service', 'infra-deployments'). "
                                "Can be partial match from PR URL."
                            ),
                        },
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name (e.g., 'Secureflow - Konflux - Global', "
                                "'Konflux_Pilot_Team'). Leave empty to search all projects."
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": (
                                "Number of days back to analyze (default: 90 for 3 months). "
                                "Leave empty to analyze all available data."
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
                        "top_n": {
                            "type": "integer",
                            "description": (
                                "Number of top PRs to return in detailed analysis "
                                "(default: 15, max: 50)"
                            ),
                        },
                        "exclude_bots": {
                            "type": "boolean",
                            "description": (
                                "Exclude bot comments from analysis (default: true). "
                                "Bot detection is based on account_id patterns and "
                                "comment characteristics."
                            ),
                        },
                    },
                    "required": [],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a PR retest tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Route to appropriate tool method
            if name == "analyze_pr_retests":
                result = await self._analyze_pr_retests_tool(arguments)
            else:
                result = {"success": False, "error": f"Unknown PR retest tool: {name}"}

            # Use TOON format for token-efficient serialization (30-60% reduction vs JSON)
            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"PR retest tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            # Use TOON format for error responses as well
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _get_repos_for_project(self, project_name: str) -> List[str]:
        """
        Get unique repository names for a project.
        Uses DISTINCT on repo name to avoid duplicate ID issues.

        Args:
            project_name: DevLake project name

        Returns:
            List of unique repository names
        """
        query = f"""
            SELECT DISTINCT r.name
            FROM lake.repos r
            INNER JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
            WHERE pm.project_name = '{project_name}'
        """
        result = await self.db_connection.execute_query(query, 500)

        if result["success"] and result["data"]:
            return [row["name"] for row in result["data"]]
        return []

    async def _analyze_pr_retests_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze PR retests with comprehensive statistics and insights.
        Uses smart repo name resolution to avoid duplicate repo ID issues.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with comprehensive retest analysis
        """
        try:
            repo_name = arguments.get("repo_name", "")
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 90)
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            top_n = min(arguments.get("top_n", 15), 50)  # Cap at 50
            exclude_bots = arguments.get("exclude_bots", True)

            # Build date filter (uses prc.created_date - comment date, not PR creation date)
            date_filter = ""
            if start_date or end_date:
                if start_date:
                    if len(start_date) == 10:
                        start_date = f"{start_date} 00:00:00"
                    date_filter += f" AND prc.created_date >= '{start_date}'"

                if end_date:
                    if len(end_date) == 10:
                        end_date = f"{end_date} 23:59:59"
                    date_filter += f" AND prc.created_date <= '{end_date}'"
            elif days_back > 0:
                date_filter = f" AND prc.created_date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)"

            # SMART REPO RESOLUTION: Convert project_name to repo names
            # This avoids issues with duplicate repo IDs in project_mapping
            target_repos = []

            if project_name:
                # Get repo names for this project
                target_repos = await self._get_repos_for_project(project_name)
                self.logger.info(f"Project '{project_name}' has repos: {target_repos}")

            if repo_name:
                # Add/filter by specific repo name
                if target_repos:
                    # Filter existing repos by repo_name pattern
                    target_repos = [r for r in target_repos if repo_name.lower() in r.lower()]
                else:
                    # No project filter, use repo_name as pattern
                    target_repos = None  # Will use LIKE pattern

            # Build repo filter SQL (by NAME, not by project_mapping JOIN)
            repo_filter = ""
            if target_repos:
                repo_names_sql = ", ".join([f"'{r}'" for r in target_repos])
                repo_filter = f" AND r.name IN ({repo_names_sql})"
            elif repo_name:
                repo_filter = f" AND r.name LIKE '%{repo_name}%'"

            # Build bot exclusion filter
            # 1. Exclude known bot account
            # 2. Filter by comment length (real /retest commands are short, < 20 chars)
            #    This excludes bot messages like "say **/retest** to rerun failed tests"
            bot_filter = ""
            if exclude_bots:
                bot_filter = """
                    AND prc.account_id != 'github:GithubAccount:1:0'
                    AND LENGTH(TRIM(prc.body)) < 20
                """

            # Step 1: Get total count and affected PRs in one query
            total_query = f"""
                SELECT
                    COUNT(DISTINCT prc.id) as total_retests,
                    COUNT(DISTINCT pr.id) as affected_prs
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
            """

            total_result = await self.db_connection.execute_query(total_query, 1)
            if total_result["success"] and total_result["data"]:
                total_retests = int(float(total_result["data"][0]["total_retests"] or 0))
                affected_prs = int(float(total_result["data"][0]["affected_prs"] or 0))
            else:
                total_retests = 0
                affected_prs = 0

            # Calculate average retests per PR
            avg_retests = round(total_retests / affected_prs, 2) if affected_prs > 0 else 0

            # Step 2: Get top PRs with most retests
            top_prs_query = f"""
                SELECT
                    pr.id as pr_id,
                    pr.title,
                    pr.url,
                    pr.status,
                    pr.created_date,
                    pr.merged_date,
                    pr.closed_date,
                    pr.additions,
                    pr.deletions,
                    r.name as repo_name,
                    COUNT(DISTINCT prc.id) as retest_count,
                    DATEDIFF(
                        COALESCE(pr.merged_date, pr.closed_date, NOW()),
                        pr.created_date
                    ) as pr_duration_days
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY pr.id, pr.title, pr.url, pr.status, pr.created_date,
                         pr.merged_date, pr.closed_date, pr.additions, pr.deletions, r.name
                ORDER BY retest_count DESC
                LIMIT {top_n}
            """

            top_prs_result = await self.db_connection.execute_query(top_prs_query, top_n)
            top_prs = top_prs_result["data"] if top_prs_result["success"] else []

            # Step 3: Get timeline data for visualization
            timeline_query = f"""
                SELECT
                    DATE(prc.created_date) as date,
                    COUNT(DISTINCT prc.id) as retest_count
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY DATE(prc.created_date)
                ORDER BY date ASC
            """

            timeline_result = await self.db_connection.execute_query(timeline_query, 1000)
            timeline_data = timeline_result["data"] if timeline_result["success"] else []

            # Step 4: Get breakdown by PR category (based on title keywords)
            category_query = f"""
                SELECT
                    CASE
                        WHEN LOWER(pr.title) LIKE '%bug%' OR
                             LOWER(pr.title) LIKE '%fix%' THEN 'Bug Fixes'
                        WHEN LOWER(pr.title) LIKE '%feat%' OR
                             LOWER(pr.title) LIKE '%feature%' THEN 'Features'
                        WHEN LOWER(pr.title) LIKE '%dep%' OR
                             LOWER(pr.title) LIKE '%dependenc%' THEN 'Dependencies'
                        WHEN LOWER(pr.title) LIKE '%refactor%' THEN 'Refactoring'
                        WHEN LOWER(pr.title) LIKE '%test%' THEN 'Tests'
                        WHEN LOWER(pr.title) LIKE '%doc%' THEN 'Documentation'
                        WHEN LOWER(pr.title) LIKE '%chore%' THEN 'Chores'
                        ELSE 'Other'
                    END as category,
                    COUNT(DISTINCT pr.id) as pr_count,
                    COUNT(DISTINCT prc.id) as total_retests
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY category
                ORDER BY total_retests DESC
            """

            category_result = await self.db_connection.execute_query(category_query, 20)
            category_breakdown = category_result["data"] if category_result["success"] else []

            # Step 5: Analyze root causes and patterns by PR status
            pattern_query = f"""
                SELECT
                    pr.status,
                    COUNT(DISTINCT pr.id) as pr_count,
                    COUNT(DISTINCT prc.id) as total_retests,
                    ROUND(COUNT(DISTINCT prc.id) * 1.0 / COUNT(DISTINCT pr.id), 2) as avg_retests,
                    ROUND(AVG(pr.additions + pr.deletions), 0) as avg_changes,
                    ROUND(AVG(DATEDIFF(
                        COALESCE(pr.merged_date, pr.closed_date, NOW()),
                        pr.created_date
                    )), 1) as avg_duration_days
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY pr.status
                ORDER BY avg_retests DESC
            """

            pattern_result = await self.db_connection.execute_query(pattern_query, 10)
            pattern_analysis = pattern_result["data"] if pattern_result["success"] else []

            # Step 6: Get per-repository breakdown
            repo_breakdown_query = f"""
                SELECT
                    r.name as repo_name,
                    COUNT(DISTINCT prc.id) as total_retests,
                    COUNT(DISTINCT pr.id) as affected_prs,
                    ROUND(COUNT(DISTINCT prc.id) * 1.0 / COUNT(DISTINCT pr.id), 2)
                        as avg_retests_per_pr
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY r.name
                ORDER BY total_retests DESC
            """

            repo_breakdown_result = await self.db_connection.execute_query(
                repo_breakdown_query, 100
            )
            repo_breakdown = (
                repo_breakdown_result["data"] if repo_breakdown_result["success"] else []
            )

            # Step 7: Get weekly trend
            weekly_trend_query = f"""
                SELECT
                    YEARWEEK(prc.created_date, 1) as week,
                    MIN(DATE(prc.created_date)) as week_start,
                    COUNT(DISTINCT prc.id) as retest_count,
                    COUNT(DISTINCT pr.id) as affected_prs
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY YEARWEEK(prc.created_date, 1)
                ORDER BY week DESC
                LIMIT 12
            """

            weekly_trend_result = await self.db_connection.execute_query(weekly_trend_query, 12)
            weekly_trend = weekly_trend_result["data"] if weekly_trend_result["success"] else []

            # Format top PRs for better readability
            formatted_top_prs = []
            for pr in top_prs:
                additions = int(float(pr.get("additions", 0) or 0))
                deletions = int(float(pr.get("deletions", 0) or 0))
                formatted_pr = {
                    "repo_name": pr.get("repo_name", "N/A"),
                    "pr_title": pr.get("title", "N/A"),
                    "pr_url": pr.get("url", "N/A"),
                    "retest_count": int(float(pr.get("retest_count", 0) or 0)),
                    "pr_duration_days": int(float(pr.get("pr_duration_days", 0) or 0)),
                    "changes": {
                        "additions": additions,
                        "deletions": deletions,
                        "total": additions + deletions,
                    },
                    "status": pr.get("status", "UNKNOWN"),
                    "created_date": str(pr.get("created_date")) if pr.get("created_date") else None,
                    "merged_date": str(pr.get("merged_date")) if pr.get("merged_date") else None,
                    "closed_date": str(pr.get("closed_date")) if pr.get("closed_date") else None,
                }
                formatted_top_prs.append(formatted_pr)

            return {
                "success": True,
                "analysis_period": {
                    "start_date": start_date if start_date else "auto",
                    "end_date": end_date if end_date else "now",
                    "days_back": days_back if days_back > 0 else "all",
                },
                "filters": {
                    "repo_name": repo_name if repo_name else "all_repositories",
                    "project_name": project_name if project_name else "all_projects",
                    "resolved_repos": target_repos if target_repos else "all",
                    "exclude_bots": exclude_bots,
                },
                "executive_summary": {
                    "total_manual_retest_comments": total_retests,
                    "number_of_affected_prs": affected_prs,
                    "average_retests_per_pr": avg_retests,
                    "time_period_analyzed": (
                        f"{days_back} days" if days_back > 0 else "all available data"
                    ),
                },
                "repo_breakdown": repo_breakdown,
                "weekly_trend": weekly_trend,
                "top_prs_by_retests": formatted_top_prs,
                "category_breakdown": category_breakdown,
                "timeline_data": timeline_data,
                "pattern_analysis": {
                    "by_status": pattern_analysis,
                    "insights": self._analyze_patterns(pattern_analysis, category_breakdown),
                },
            }

        except Exception as e:
            self.logger.error(f"Analyze PR retests failed: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_patterns(
        self, pattern_analysis: List[Dict], category_breakdown: List[Dict]
    ) -> List[str]:
        """
        Analyze patterns and generate insights.

        Args:
            pattern_analysis: Pattern analysis data
            category_breakdown: Category breakdown data

        Returns:
            List of insight strings
        """
        insights = []

        if pattern_analysis:
            max_status = max(pattern_analysis, key=lambda x: float(x.get("avg_retests", 0) or 0))
            avg_retests_val = float(max_status.get("avg_retests", 0) or 0)
            insights.append(
                f"PRs with status '{max_status.get('status')}' have the highest "
                f"average retest count ({avg_retests_val:.2f} retests per PR)"
            )

        if category_breakdown:
            max_category = max(
                category_breakdown, key=lambda x: float(x.get("total_retests", 0) or 0)
            )
            total_retests_val = float(max_category.get("total_retests", 0) or 0)
            pr_count_val = int(max_category.get("pr_count", 0) or 0)
            insights.append(
                f"'{max_category.get('category')}' category has the most retests "
                f"({int(total_retests_val)} total retests across {pr_count_val} PRs)"
            )

        return insights
