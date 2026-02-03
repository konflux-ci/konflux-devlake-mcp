#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) for Konflux DevLake MCP Server

This module provides LDAP/Rover group-based authorization for MCP tools.

Role Assignment:
- LDAP lookup - if user is in Rover group "devlakemcpadmin" -> mcp-admin
- Otherwise -> mcp-viewer (all tools EXCEPT execute_query)
"""

from typing import Any, Dict, List, Optional, Set

from utils.logger import get_logger
from utils.ldap_service import LDAPService

# Role definitions - maps role names to allowed tools
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    # Viewer role - read-only access to analytics and reports
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
    # Admin role - full access to all tools
    "mcp-admin": {"*"},
}

DEFAULT_ROLE = "mcp-viewer"


class AuthorizationService:
    """Authorization service for enforcing RBAC based on LDAP Rover group membership."""

    def __init__(
        self,
        role_permissions: Optional[Dict[str, Set[str]]] = None,
        ldap_service: Optional[LDAPService] = None,
    ):
        self.logger = get_logger(f"{__name__}.AuthorizationService")
        self.role_permissions = role_permissions or ROLE_PERMISSIONS
        self.default_role = DEFAULT_ROLE

        self.ldap_service = ldap_service or LDAPService()

        self.logger.info(
            f"Authorization service initialized with {len(self.role_permissions)} roles, "
            f"default_role={self.default_role}"
        )

    def resolve_user_roles(self, username: Optional[str] = None) -> List[str]:
        """Resolve effective roles for a user via LDAP lookup."""
        if username:
            try:
                if self.ldap_service.is_admin(username):
                    self.logger.info(
                        f"Admin role assigned via LDAP Rover group "
                        f"'{self.ldap_service.admin_group}': {username}"
                    )
                    return ["mcp-admin"]
            except Exception as e:
                self.logger.warning(f"LDAP lookup failed for '{username}': {e}")

        if self.default_role:
            self.logger.debug(f"Default role '{self.default_role}' assigned to {username}")
            return [self.default_role]

        return []

    def is_authorized(self, tool_name: str, username: Optional[str] = None) -> bool:
        """Check if a user is authorized to call a specific tool."""
        effective_roles = self.resolve_user_roles(username)

        if not effective_roles:
            self.logger.warning(f"Access denied: no roles resolved for tool '{tool_name}'")
            return False

        for role in effective_roles:
            if self._role_allows_tool(role, tool_name):
                self.logger.debug(f"Access granted: role '{role}' allows tool '{tool_name}'")
                return True

        self.logger.warning(
            f"Access denied: roles {effective_roles} not authorized for tool '{tool_name}'"
        )
        return False

    def _role_allows_tool(self, role: str, tool_name: str) -> bool:
        """Check if a specific role allows access to a tool."""
        allowed_tools = self.role_permissions.get(role, set())
        if "*" in allowed_tools:
            return True

        return tool_name in allowed_tools

    def get_allowed_tools(self, username: Optional[str] = None) -> Set[str]:
        """Get all tools a user is allowed to call based on their roles."""
        effective_roles = self.resolve_user_roles(username)
        allowed = set()
        for role in effective_roles:
            role_tools = self.role_permissions.get(role, set())
            if "*" in role_tools:
                return {"*"}
            allowed.update(role_tools)

        return allowed

    def get_denied_reason(self, tool_name: str, username: Optional[str] = None) -> str:
        """Get a readable reason why access was denied."""
        return f"Access denied: tool '{tool_name}' requires mcp-admin role"

    def get_role_info(self) -> Dict[str, Any]:
        """Get information about configured roles for debugging/monitoring."""
        role_info = {}
        for role, tools in self.role_permissions.items():
            if "*" in tools:
                role_info[role] = {"access": "full", "tools": ["*"]}
            else:
                role_info[role] = {"access": "limited", "tools": sorted(list(tools))}

        return {
            "roles": role_info,
            "default_role": self.default_role,
            "total_roles": len(self.role_permissions),
            "ldap": self.ldap_service.get_cache_stats() if self.ldap_service else None,
        }
