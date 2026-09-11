#!/usr/bin/env python3
"""LDAP/Rover group-based role authorization for MCP tools."""

import asyncio
from typing import Dict, List, Optional, Set

from utils.ldap_service import LDAPService
from utils.logger import get_logger

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "mcp-viewer": {
        "connect_database",
        "list_databases",
        "list_tables",
        "get_table_schema",
        "get_incidents",
        "get_failed_deployment_recovery_time",
        "get_deployments",
        "get_deployment_frequency",
        "analyze_pr_retests",
        "get_pr_cycle_time",
        "get_pr_stats",
        "get_github_actions_health",
        "analyze_e2e_tests",
        "get_codecov_coverage",
        "get_codecov_summary",
        "get_historical_trends",
        "get_lead_time_for_changes",
        "get_jira_features",
    },
    "mcp-admin": {"*"},
}

DEFAULT_ROLE = "mcp-viewer"


class AuthorizationService:
    """Resolve MCP roles using IPA membership in the admin Rover group."""

    def __init__(
        self,
        role_permissions: Optional[Dict[str, Set[str]]] = None,
        ldap_service: Optional[LDAPService] = None,
    ):
        self.logger = get_logger(f"{__name__}.AuthorizationService")
        self.role_permissions = role_permissions or ROLE_PERMISSIONS
        self.default_role = DEFAULT_ROLE
        self.ldap_service = ldap_service or LDAPService()

    async def resolve_user_roles(self, username: Optional[str] = None) -> List[str]:
        """Resolve roles without blocking the async request loop."""
        if username:
            try:
                if await asyncio.to_thread(self.ldap_service.is_admin, username):
                    return ["mcp-admin"]
            except Exception as exc:
                self.logger.warning("LDAP lookup failed for '%s': %s", username, exc)
        return [self.default_role]

    async def get_tool_authorization(
        self, tool_name: str, username: Optional[str] = None
    ) -> Dict[str, bool]:
        """Return tool authorization and resolved administrator status."""
        roles = await self.resolve_user_roles(username)
        return {
            "authorized": any(self._role_allows_tool(role, tool_name) for role in roles),
            "is_admin": "mcp-admin" in roles,
        }

    def _role_allows_tool(self, role: str, tool_name: str) -> bool:
        allowed_tools = self.role_permissions.get(role, set())
        return "*" in allowed_tools or tool_name in allowed_tools

    async def get_allowed_tools(self, username: Optional[str] = None) -> Set[str]:
        """Return tools allowed for the user, or '*' for an administrator."""
        allowed: Set[str] = set()
        for role in await self.resolve_user_roles(username):
            role_tools = self.role_permissions.get(role, set())
            if "*" in role_tools:
                return {"*"}
            allowed.update(role_tools)
        return allowed

    def get_denied_reason(self, tool_name: str) -> str:
        """Return a stable user-facing denial message."""
        return f"Access denied: tool '{tool_name}' requires mcp-admin role"
