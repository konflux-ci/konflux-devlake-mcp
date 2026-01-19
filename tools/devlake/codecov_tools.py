#!/usr/bin/env python3
"""
Codecov Coverage Analysis Tools for Konflux DevLake MCP Server

Contains tools for analyzing code coverage metrics from Codecov including
repository coverage, patch coverage, flag analysis, and trend tracking.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class CodecovTools(BaseTool):
    """
    Codecov Coverage Analysis tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing code coverage metrics,
    including repository coverage, patch coverage, and trend analysis.
    """

    def __init__(self, db_connection):
        """
        Initialize Codecov tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.CodecovTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all Codecov analysis tools.

        Returns:
            List of Tool objects for Codecov operations
        """
        return [
            Tool(
                name="get_codecov_coverage",
                description=(
                    "Comprehensive Codecov Coverage Analysis Tool - Provides complete "
                    "code coverage metrics for a DevLake project including: executive summary "
                    "with aggregated KPIs, per-repository coverage breakdown with all flags, "
                    "daily coverage trends for charting, patch coverage analysis (PR coverage), "
                    "coverage by test type (unit-tests, e2e-tests, etc.), trend analysis "
                    "(coverage change over time), and health status classification. "
                    "Returns a comprehensive object ready for report generation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name (e.g., 'Secureflow - Konflux - Global')"
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": "Number of days back to analyze (default: 30)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
            Tool(
                name="get_codecov_summary",
                description=(
                    "Quick Codecov Summary - Returns a simplified coverage summary with just "
                    "the essential KPIs: repo_count, avg_coverage, min_coverage, max_coverage, "
                    "total_lines, lines_covered, avg_patch_coverage, and health distribution. "
                    "Use this for quick dashboards or when you only need summary metrics."
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
                            "description": "Number of days back to analyze (default: 30)",
                        },
                    },
                    "required": ["project_name"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a Codecov tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            log_tool_call(name, arguments, success=True)

            if name == "get_codecov_coverage":
                result = await self._get_codecov_coverage(arguments)
            elif name == "get_codecov_summary":
                result = await self._get_codecov_summary(arguments)
            else:
                result = {"success": False, "error": f"Unknown Codecov tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Codecov tool call failed: {e}")
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

    def _classify_coverage(self, coverage: float) -> str:
        """
        Classify coverage health status.

        Args:
            coverage: Coverage percentage

        Returns:
            Status string: 'good', 'warning', or 'danger'
        """
        if coverage >= 70:
            return "good"
        elif coverage >= 50:
            return "warning"
        else:
            return "danger"

    def _calculate_trend(self, start_coverage: float, end_coverage: float) -> tuple:
        """
        Calculate coverage trend.

        Args:
            start_coverage: Coverage at start of period
            end_coverage: Coverage at end of period

        Returns:
            Tuple of (trend_direction, change_percentage)
        """
        change = end_coverage - start_coverage
        if change > 1.0:
            return ("improving", round(change, 2))
        elif change < -1.0:
            return ("declining", round(change, 2))
        else:
            return ("stable", round(change, 2))

    def _generate_recommendations(self, repositories: List[Dict]) -> List[Dict]:
        """
        Generate recommendations based on coverage analysis.

        Args:
            repositories: List of repository coverage data

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        for repo in repositories:
            coverage = repo.get("latest_coverage", 0)
            repo_id = repo.get("repo_id", "unknown")

            # Critical: coverage below 50%
            if coverage < 50:
                recommendations.append(
                    {
                        "priority": 1,
                        "type": "critical",
                        "repo": repo_id,
                        "issue": "Coverage critically low",
                        "current": coverage,
                        "target": 50.0,
                        "action": "Add unit tests for core modules",
                    }
                )
            # Warning: coverage below 70%
            elif coverage < 70:
                recommendations.append(
                    {
                        "priority": 2,
                        "type": "improvement",
                        "repo": repo_id,
                        "issue": "Coverage below target",
                        "current": coverage,
                        "target": 70.0,
                        "action": "Expand test coverage for edge cases",
                    }
                )

            # Check for declining trend
            trend = repo.get("trend", "stable")
            trend_change = repo.get("trend_change_pct", 0)
            if trend == "declining" and trend_change < -3:
                recommendations.append(
                    {
                        "priority": 1,
                        "type": "warning",
                        "repo": repo_id,
                        "issue": f"Coverage declining ({trend_change}%)",
                        "action": "Investigate recent PRs that reduced coverage",
                    }
                )

        return sorted(recommendations, key=lambda x: x["priority"])

    async def _get_codecov_coverage(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive Codecov coverage analysis.

        Args:
            arguments: Tool arguments containing project_name and days_back

        Returns:
            Dictionary with coverage analysis
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 30)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            # Step 1: Get repo names for this project
            # First try direct Codecov repo mapping
            repo_ids_query = f"""
                SELECT DISTINCT pm.row_id as repo_id
                FROM lake.project_mapping pm
                WHERE pm.project_name = '{project_name}'
                AND pm.`table` = '_tool_codecov_repos'
            """
            repo_ids_result = await self._execute_with_timeout(repo_ids_query, 500, timeout=30)

            repo_ids = []
            if repo_ids_result.get("success") and repo_ids_result.get("data"):
                repo_ids = [r["repo_id"] for r in repo_ids_result["data"]]

            # If no direct Codecov mapping, get repo names through repos table
            if not repo_ids:
                repos_query = f"""
                    SELECT DISTINCT r.name as repo_id
                    FROM lake.repos r
                    JOIN lake.project_mapping pm ON pm.row_id = r.id
                    WHERE pm.project_name = '{project_name}'
                    AND pm.`table` = 'repos'
                """
                repos_result = await self._execute_with_timeout(repos_query, 500, timeout=30)
                if repos_result.get("success") and repos_result.get("data"):
                    repo_ids = [r["repo_id"] for r in repos_result["data"]]

            if not repo_ids:
                return {
                    "success": True,
                    "message": "No repositories found for project",
                    "project_name": project_name,
                    "analysis_period_days": days_back,
                    "generated_at": datetime.now().isoformat(),
                    "executive_summary": {
                        "repo_count": 0,
                        "avg_coverage": 0.0,
                        "min_coverage": 0.0,
                        "max_coverage": 0.0,
                    },
                    "repositories": [],
                    "coverage_by_flag": [],
                    "daily_trend": [],
                    "patch_coverage": {"avg_patch_coverage": 0.0, "by_repository": []},
                    "health_breakdown": {"good": [], "warning": [], "danger": []},
                    "recommendations": [],
                }

            repo_ids_str = ", ".join([f"'{r}'" for r in repo_ids])

            # Step 2: Build all queries
            # Query 2: Latest Coverage Per Repository (with flags)
            latest_coverage_query = f"""
                SELECT
                    c.repo_id,
                    c.flag_name,
                    c.coverage_percentage,
                    c.lines_total,
                    c.hits as lines_covered,
                    c.partials,
                    c.misses as lines_uncovered,
                    c.commit_timestamp
                FROM lake._tool_codecov_coverages c
                WHERE c.repo_id IN ({repo_ids_str})
                AND c.coverage_percentage > 0
                AND c.commit_timestamp = (
                    SELECT MAX(c2.commit_timestamp)
                    FROM lake._tool_codecov_coverages c2
                    WHERE c2.repo_id = c.repo_id
                    AND c2.flag_name = c.flag_name
                    AND c2.coverage_percentage > 0
                )
                ORDER BY c.repo_id, c.flag_name
            """

            # Query 3: Daily Coverage Trend (using pre-aggregated trends table like dashboard)
            daily_trend_query = f"""
                SELECT
                    t.date,
                    t.repo_id,
                    t.flag_name,
                    ROUND(t.coverage_percentage, 2) as daily_coverage,
                    t.lines_total,
                    t.lines_covered
                FROM lake._tool_codecov_coverage_trends t
                WHERE t.repo_id IN ({repo_ids_str})
                AND t.coverage_percentage > 0
                AND t.date >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                ORDER BY t.date, t.repo_id
            """

            # Query 4: Start Coverage (for trend calculation)
            start_coverage_query = f"""
                SELECT
                    c.repo_id,
                    ROUND(AVG(c.coverage_percentage), 2) as start_coverage
                FROM lake._tool_codecov_coverages c
                WHERE c.repo_id IN ({repo_ids_str})
                AND c.coverage_percentage > 0
                AND c.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND c.commit_timestamp <= DATE_SUB(NOW(), INTERVAL {days_back - 7} DAY)
                GROUP BY c.repo_id
            """

            # Query 5: Patch Coverage by Repository
            # Correct calculation: AVG of MAX(patch) per commit (matching Grafana dashboard)
            # Each commit can have multiple flags, we take MAX per commit then AVG
            patch_coverage_query = f"""
                SELECT
                    repo_id,
                    ROUND(AVG(patch_per_commit), 2) as avg_patch_coverage,
                    COUNT(*) as patch_count
                FROM (
                    SELECT
                        comp.repo_id,
                        comp.commit_sha,
                        MAX(comp.patch) as patch_per_commit
                FROM lake._tool_codecov_comparisons comp
                INNER JOIN lake._tool_codecov_commits cm
                    ON comp.connection_id = cm.connection_id
                    AND comp.repo_id = cm.repo_id
                    AND comp.commit_sha = cm.commit_sha
                WHERE comp.repo_id IN ({repo_ids_str})
                AND comp.patch IS NOT NULL
                AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                    GROUP BY comp.repo_id, comp.commit_sha
                ) sub
                GROUP BY repo_id
            """

            # Query 6: Latest Patch Coverage Per Repository
            # Get MAX(patch) per commit for latest commit per repo (matching dashboard approach)
            latest_patch_query = f"""
                SELECT
                    repo_id,
                    ROUND(latest_patch, 2) as latest_patch
                FROM (
                    SELECT
                    comp.repo_id,
                        MAX(comp.patch) as latest_patch,
                        ROW_NUMBER() OVER (
                        PARTITION BY comp.repo_id
                            ORDER BY MAX(cm.commit_timestamp) DESC
                        ) as rn
                FROM lake._tool_codecov_comparisons comp
                INNER JOIN lake._tool_codecov_commits cm
                    ON comp.connection_id = cm.connection_id
                    AND comp.repo_id = cm.repo_id
                    AND comp.commit_sha = cm.commit_sha
                WHERE comp.repo_id IN ({repo_ids_str})
                AND comp.patch IS NOT NULL
                AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                    GROUP BY comp.repo_id, comp.commit_sha
                ) sub
                WHERE rn = 1
            """

            # Query 7: Daily Patch Trend
            # Correct calculation: AVG of MAX(patch) per commit per day (matching Grafana dashboard)
            daily_patch_query = f"""
                SELECT
                    date,
                    ROUND(AVG(patch_per_commit), 2) as avg_patch,
                    COUNT(*) as patch_count
                FROM (
                SELECT
                    DATE(cm.commit_timestamp) as date,
                        comp.commit_sha,
                        MAX(comp.patch) as patch_per_commit
                FROM lake._tool_codecov_comparisons comp
                INNER JOIN lake._tool_codecov_commits cm
                    ON comp.connection_id = cm.connection_id
                    AND comp.repo_id = cm.repo_id
                    AND comp.commit_sha = cm.commit_sha
                WHERE comp.repo_id IN ({repo_ids_str})
                AND comp.patch IS NOT NULL
                AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                    GROUP BY DATE(cm.commit_timestamp), comp.commit_sha
                ) sub
                GROUP BY date
                ORDER BY date
            """

            # Query 8: Coverage by Flag Aggregated
            flag_coverage_query = f"""
                SELECT
                    c.flag_name,
                    COUNT(DISTINCT c.repo_id) as repo_count,
                    ROUND(AVG(c.coverage_percentage), 2) as avg_coverage,
                    SUM(c.lines_total) as total_lines,
                    SUM(c.hits) as lines_covered
                FROM lake._tool_codecov_coverages c
                WHERE c.repo_id IN ({repo_ids_str})
                AND c.coverage_percentage > 0
                AND c.flag_name IS NOT NULL AND c.flag_name != ''
                AND c.commit_timestamp = (
                    SELECT MAX(c2.commit_timestamp)
                    FROM lake._tool_codecov_coverages c2
                    WHERE c2.repo_id = c.repo_id
                    AND c2.flag_name = c.flag_name
                    AND c2.coverage_percentage > 0
                )
                GROUP BY c.flag_name
                ORDER BY repo_count DESC
            """

            # Step 3: Run all queries in parallel
            results = await asyncio.gather(
                self._execute_with_timeout(latest_coverage_query, 500, timeout=60),
                self._execute_with_timeout(daily_trend_query, 1000, timeout=60),
                self._execute_with_timeout(start_coverage_query, 100, timeout=60),
                self._execute_with_timeout(patch_coverage_query, 100, timeout=60),
                self._execute_with_timeout(latest_patch_query, 100, timeout=60),
                self._execute_with_timeout(daily_patch_query, 100, timeout=60),
                self._execute_with_timeout(flag_coverage_query, 50, timeout=60),
                return_exceptions=True,
            )

            (
                latest_cov_result,
                daily_trend_result,
                start_cov_result,
                patch_cov_result,
                latest_patch_result,
                daily_patch_result,
                flag_cov_result,
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

            # Process latest coverage data
            latest_cov_data = safe_get_data(latest_cov_result)
            start_cov_data = safe_get_data(start_cov_result)
            patch_cov_data = safe_get_data(patch_cov_result)
            latest_patch_data = safe_get_data(latest_patch_result)
            daily_trend_data = safe_get_data(daily_trend_result)
            daily_patch_data = safe_get_data(daily_patch_result)
            flag_cov_data = safe_get_data(flag_cov_result)

            # Build start coverage lookup
            start_cov_lookup = {}
            for row in start_cov_data:
                start_cov_lookup[row["repo_id"]] = float(row.get("start_coverage", 0) or 0)

            # Build patch coverage lookups
            patch_cov_lookup = {}
            for row in patch_cov_data:
                patch_cov_lookup[row["repo_id"]] = {
                    "avg_patch_coverage": float(row.get("avg_patch_coverage", 0) or 0),
                    "patch_count": int(row.get("patch_count", 0) or 0),
                }

            latest_patch_lookup = {}
            for row in latest_patch_data:
                latest_patch_lookup[row["repo_id"]] = float(row.get("latest_patch", 0) or 0)

            # Process repositories with flags
            # Use flag with highest lines_total for line counts (matching dashboard logic)
            repo_data = {}
            for row in latest_cov_data:
                repo_id = row["repo_id"]
                flag_name = row.get("flag_name") or "total"
                coverage = float(row.get("coverage_percentage", 0) or 0)
                lines_total = int(row.get("lines_total", 0) or 0)
                lines_covered = int(row.get("lines_covered", 0) or 0)
                partials = int(row.get("partials", 0) or 0)
                lines_uncovered = int(row.get("lines_uncovered", 0) or 0)
                commit_timestamp = row.get("commit_timestamp")

                if repo_id not in repo_data:
                    # Calculate trend
                    start_cov = start_cov_lookup.get(repo_id, coverage)
                    trend, trend_change = self._calculate_trend(start_cov, coverage)

                    repo_data[repo_id] = {
                        "repo_id": repo_id,
                        "latest_coverage": coverage,
                        "lines_total": lines_total,
                        "lines_covered": lines_covered,
                        "lines_partial": partials,
                        "lines_uncovered": lines_uncovered,
                        "latest_patch_coverage": latest_patch_lookup.get(repo_id, 0),
                        "last_updated": str(commit_timestamp) if commit_timestamp else None,
                        "status": self._classify_coverage(coverage),
                        "trend": trend,
                        "trend_change_pct": trend_change,
                        "flags": [],
                    }

                # Add flag data
                repo_data[repo_id]["flags"].append(
                    {
                        "flag_name": flag_name,
                        "coverage": coverage,
                        "lines_total": lines_total,
                        "lines_covered": lines_covered,
                    }
                )

                # Update repo coverage to max of all flags
                if coverage > repo_data[repo_id]["latest_coverage"]:
                    repo_data[repo_id]["latest_coverage"] = coverage
                    repo_data[repo_id]["status"] = self._classify_coverage(coverage)

                # Update line counts to flag with highest lines_total (dashboard logic)
                if lines_total > repo_data[repo_id]["lines_total"]:
                    repo_data[repo_id]["lines_total"] = lines_total
                    repo_data[repo_id]["lines_covered"] = lines_covered
                    repo_data[repo_id]["lines_partial"] = partials
                    repo_data[repo_id]["lines_uncovered"] = lines_uncovered
                    repo_data[repo_id]["last_updated"] = (
                        str(commit_timestamp) if commit_timestamp else None
                    )

            repositories = list(repo_data.values())

            # Calculate executive summary
            if repositories:
                coverages = [r["latest_coverage"] for r in repositories]
                avg_coverage = round(sum(coverages) / len(coverages), 2)
                min_coverage = round(min(coverages), 2)
                max_coverage = round(max(coverages), 2)
                total_lines = sum(r["lines_total"] for r in repositories)
                lines_covered = sum(r["lines_covered"] for r in repositories)
                lines_partial = sum(r["lines_partial"] for r in repositories)
                lines_uncovered = sum(r["lines_uncovered"] for r in repositories)
                repos_above_80 = len([c for c in coverages if c >= 80])
                repos_50_to_80 = len([c for c in coverages if 50 <= c < 80])
                repos_below_50 = len([c for c in coverages if c < 50])

                # Calculate overall trend
                if start_cov_data and repositories:
                    avg_start = (
                        sum(start_cov_lookup.values()) / len(start_cov_lookup)
                        if start_cov_lookup
                        else avg_coverage
                    )
                    overall_trend, overall_change = self._calculate_trend(avg_start, avg_coverage)
                else:
                    overall_trend, overall_change = "stable", 0.0

                # Calculate average patch coverage
                patch_coverages = [
                    r["latest_patch_coverage"]
                    for r in repositories
                    if r["latest_patch_coverage"] > 0
                ]
                avg_patch_coverage = (
                    round(sum(patch_coverages) / len(patch_coverages), 2)
                    if patch_coverages
                    else 0.0
                )
            else:
                avg_coverage = min_coverage = max_coverage = 0.0
                total_lines = lines_covered = lines_partial = lines_uncovered = 0
                repos_above_80 = repos_50_to_80 = repos_below_50 = 0
                overall_trend, overall_change = "stable", 0.0
                avg_patch_coverage = 0.0

            # Process daily trend (aggregate across repos)
            daily_agg = {}
            for row in daily_trend_data:
                date_str = str(row["date"])
                if date_str not in daily_agg:
                    daily_agg[date_str] = {"coverages": [], "repos": set()}
                daily_agg[date_str]["coverages"].append(float(row.get("daily_coverage", 0) or 0))
                daily_agg[date_str]["repos"].add(row["repo_id"])

            daily_trend = []
            for date_str in sorted(daily_agg.keys()):
                data = daily_agg[date_str]
                daily_trend.append(
                    {
                        "date": date_str,
                        "avg_coverage": round(sum(data["coverages"]) / len(data["coverages"]), 2),
                        "repos_reported": len(data["repos"]),
                    }
                )

            # Process coverage by flag
            coverage_by_flag = []
            for row in flag_cov_data:
                coverage_by_flag.append(
                    {
                        "flag_name": row.get("flag_name", "unknown"),
                        "repo_count": int(row.get("repo_count", 0) or 0),
                        "avg_coverage": float(row.get("avg_coverage", 0) or 0),
                        "total_lines": int(row.get("total_lines", 0) or 0),
                        "lines_covered": int(row.get("lines_covered", 0) or 0),
                    }
                )

            # Process patch coverage
            patch_by_repo = []
            for repo_id, data in patch_cov_lookup.items():
                patch_by_repo.append(
                    {
                        "repo_id": repo_id,
                        "latest_patch_coverage": latest_patch_lookup.get(repo_id, 0),
                        "avg_patch_coverage_30d": data["avg_patch_coverage"],
                        "patch_count_30d": data["patch_count"],
                    }
                )

            # Process daily patch trend
            patch_daily_trend = []
            for row in daily_patch_data:
                patch_daily_trend.append(
                    {
                        "date": str(row["date"]),
                        "avg_patch": float(row.get("avg_patch", 0) or 0),
                        "patch_count": int(row.get("patch_count", 0) or 0),
                    }
                )

            # Build health breakdown
            health_breakdown = {"good": [], "warning": [], "danger": []}
            for repo in repositories:
                status = repo["status"]
                health_breakdown[status].append(repo["repo_id"])

            # Generate recommendations
            recommendations = self._generate_recommendations(repositories)

            return {
                "success": True,
                "project_name": project_name,
                "analysis_period_days": days_back,
                "generated_at": datetime.now().isoformat(),
                "executive_summary": {
                    "repo_count": len(repositories),
                    "avg_coverage": avg_coverage,
                    "min_coverage": min_coverage,
                    "max_coverage": max_coverage,
                    "total_lines": total_lines,
                    "lines_covered": lines_covered,
                    "lines_partial": lines_partial,
                    "lines_uncovered": lines_uncovered,
                    "avg_patch_coverage": avg_patch_coverage,
                    "repos_above_80": repos_above_80,
                    "repos_50_to_80": repos_50_to_80,
                    "repos_below_50": repos_below_50,
                    "overall_trend": overall_trend,
                    "trend_change_pct": overall_change,
                },
                "repositories": repositories,
                "coverage_by_flag": coverage_by_flag,
                "daily_trend": daily_trend,
                "patch_coverage": {
                    "avg_patch_coverage": avg_patch_coverage,
                    "repos_with_patch_data": len(patch_by_repo),
                    "by_repository": patch_by_repo,
                    "daily_trend": patch_daily_trend,
                },
                "health_breakdown": health_breakdown,
                "recommendations": recommendations,
            }

        except Exception as e:
            self.logger.error(f"Get Codecov coverage failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_codecov_summary(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get quick Codecov coverage summary with essential KPIs.

        Uses same logic as get_codecov_coverage for consistency:
        - Gets all flags per repo
        - Uses MAX coverage per repo
        - Uses first flag's line counts per repo

        Args:
            arguments: Tool arguments containing project_name and days_back

        Returns:
            Dictionary with coverage summary KPIs
        """
        try:
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 30)

            if not project_name:
                return {"success": False, "error": "project_name is required"}

            empty_result = {
                "success": True,
                "project_name": project_name,
                "days_back": days_back,
                "repo_count": 0,
                "avg_coverage": 0.0,
                "min_coverage": 0.0,
                "max_coverage": 0.0,
                "total_lines": 0,
                "lines_covered": 0,
                "lines_partial": 0,
                "lines_uncovered": 0,
                "avg_patch_coverage": 0.0,
                "coverage_trend": "stable",
                "trend_change_pct": 0.0,
                "health_distribution": {"good": 0, "warning": 0, "danger": 0},
            }

            # Get repository IDs for project
            repo_query = f"""
                SELECT DISTINCT pm.row_id as repo_id
                FROM lake.project_mapping pm
                WHERE pm.project_name = '{project_name}'
                AND pm.`table` = '_tool_codecov_repos'
            """
            repo_result = await self._execute_with_timeout(repo_query, 500, timeout=30)

            if not repo_result.get("success") or not repo_result.get("data"):
                return empty_result

            repo_ids = [r["repo_id"] for r in repo_result["data"]]
            repo_ids_str = ", ".join([f"'{r}'" for r in repo_ids])

            # Get latest coverage per flag, then select highest lines_total per repo
            # Matches Query 2b from Grafana dashboard specification
            latest_coverage_query = f"""
                SELECT sub2.repo_id, sub2.flag_name, sub2.coverage_percentage,
                       sub2.lines_total, sub2.lines_covered, sub2.partials,
                       sub2.lines_uncovered
                FROM (
                    SELECT sub.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY sub.repo_id
                               ORDER BY sub.lines_total DESC
                           ) as rn2
                    FROM (
                        SELECT
                            c.repo_id,
                            c.flag_name,
                            c.coverage_percentage,
                            c.lines_total,
                            c.hits as lines_covered,
                            c.partials,
                            c.misses as lines_uncovered
                        FROM lake._tool_codecov_coverages c
                        WHERE c.repo_id IN ({repo_ids_str})
                        AND c.coverage_percentage > 0
                        AND c.commit_timestamp = (
                            SELECT MAX(c2.commit_timestamp)
                            FROM lake._tool_codecov_coverages c2
                            WHERE c2.repo_id = c.repo_id
                            AND c2.flag_name = c.flag_name
                            AND c2.coverage_percentage > 0
                        )
                    ) sub
                ) sub2
                WHERE sub2.rn2 = 1
                ORDER BY sub2.repo_id
            """

            # Patch coverage query (matching full tool)
            patch_query = f"""
                SELECT
                    repo_id,
                    ROUND(latest_patch, 2) as latest_patch
                FROM (
                    SELECT
                        comp.repo_id,
                        MAX(comp.patch) as latest_patch,
                        ROW_NUMBER() OVER (
                            PARTITION BY comp.repo_id
                            ORDER BY MAX(cm.commit_timestamp) DESC
                        ) as rn
                    FROM lake._tool_codecov_comparisons comp
                    INNER JOIN lake._tool_codecov_commits cm
                        ON comp.connection_id = cm.connection_id
                        AND comp.repo_id = cm.repo_id
                        AND comp.commit_sha = cm.commit_sha
                    WHERE comp.repo_id IN ({repo_ids_str})
                    AND comp.patch IS NOT NULL
                    AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                    GROUP BY comp.repo_id, comp.commit_sha
                ) sub
                WHERE rn = 1
            """

            # Start coverage for trend
            start_query = f"""
                SELECT
                    c.repo_id,
                    ROUND(AVG(c.coverage_percentage), 2) as start_coverage
                FROM lake._tool_codecov_coverages c
                WHERE c.repo_id IN ({repo_ids_str})
                AND c.coverage_percentage > 0
                AND c.commit_timestamp >= DATE_SUB(NOW(), INTERVAL {days_back} DAY)
                AND c.commit_timestamp <= DATE_SUB(NOW(), INTERVAL {max(days_back - 7, 1)} DAY)
                GROUP BY c.repo_id
            """

            # Execute queries in parallel
            cov_result, patch_result, start_result = await asyncio.gather(
                self._execute_with_timeout(latest_coverage_query, 500, timeout=60),
                self._execute_with_timeout(patch_query, 100, timeout=60),
                self._execute_with_timeout(start_query, 100, timeout=30),
            )

            if not cov_result.get("success") or not cov_result.get("data"):
                return empty_result

            # Build patch lookup
            patch_lookup = {}
            if patch_result.get("success") and patch_result.get("data"):
                for row in patch_result["data"]:
                    patch_lookup[row["repo_id"]] = float(row.get("latest_patch", 0) or 0)

            # Build start coverage lookup
            start_lookup = {}
            if start_result.get("success") and start_result.get("data"):
                for row in start_result["data"]:
                    start_lookup[row["repo_id"]] = float(row.get("start_coverage", 0) or 0)

            # Process repos with same logic as full tool:
            # - Use first flag's line data
            # - Use MAX coverage across flags
            repo_data = {}
            for row in cov_result["data"]:
                repo_id = row["repo_id"]
                coverage = float(row.get("coverage_percentage", 0) or 0)
                lines_total = int(row.get("lines_total", 0) or 0)
                lines_covered = int(row.get("lines_covered", 0) or 0)
                partials = int(row.get("partials", 0) or 0)
                lines_uncovered = int(row.get("lines_uncovered", 0) or 0)

                if repo_id not in repo_data:
                    # First flag for this repo - set initial data
                    repo_data[repo_id] = {
                        "coverage": coverage,
                        "lines_total": lines_total,
                        "lines_covered": lines_covered,
                        "lines_partial": partials,
                        "lines_uncovered": lines_uncovered,
                    }
                else:
                    # Update to MAX coverage (same as full tool)
                    if coverage > repo_data[repo_id]["coverage"]:
                        repo_data[repo_id]["coverage"] = coverage

            if not repo_data:
                return empty_result

            # Calculate summary metrics
            coverages = [r["coverage"] for r in repo_data.values()]
            total_lines = sum(r["lines_total"] for r in repo_data.values())
            lines_covered = sum(r["lines_covered"] for r in repo_data.values())
            lines_partial = sum(r["lines_partial"] for r in repo_data.values())
            lines_uncovered = sum(r["lines_uncovered"] for r in repo_data.values())

            avg_coverage = round(sum(coverages) / len(coverages), 2)

            # Health distribution
            good = len([c for c in coverages if c >= 70])
            warning = len([c for c in coverages if 50 <= c < 70])
            danger = len([c for c in coverages if c < 50])

            # Patch coverage
            patch_values = [patch_lookup.get(rid, 0) for rid in repo_data.keys()]
            patch_values = [v for v in patch_values if v > 0]
            avg_patch = round(sum(patch_values) / len(patch_values), 2) if patch_values else 0.0

            # Trend calculation
            if start_lookup:
                avg_start = sum(start_lookup.values()) / len(start_lookup)
                trend, trend_change = self._calculate_trend(avg_start, avg_coverage)
            else:
                trend, trend_change = "stable", 0.0

            return {
                "success": True,
                "project_name": project_name,
                "days_back": days_back,
                "repo_count": len(repo_data),
                "avg_coverage": avg_coverage,
                "min_coverage": round(min(coverages), 2),
                "max_coverage": round(max(coverages), 2),
                "total_lines": total_lines,
                "lines_covered": lines_covered,
                "lines_partial": lines_partial,
                "lines_uncovered": lines_uncovered,
                "avg_patch_coverage": avg_patch,
                "coverage_trend": trend,
                "trend_change_pct": trend_change,
                "health_distribution": {
                    "good": good,
                    "warning": warning,
                    "danger": danger,
                },
            }

        except Exception as e:
            self.logger.error(f"Get Codecov summary failed: {e}")
            return {"success": False, "error": str(e)}
