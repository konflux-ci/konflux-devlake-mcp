#!/usr/bin/env python3
"""
Unit Tests for Role-Based Access Control (RBAC)

Tests for utils/rbac.py and RBAC integration in tool_handler.py
"""

import pytest
from unittest.mock import MagicMock

from utils.rbac import (
    AuthorizationService,
    ROLE_PERMISSIONS,
)
from server.handlers.tool_handler import (
    ToolHandler,
    set_user_context,
    get_user_context,
)


class MockLDAPService:
    """Mock LDAP service for testing."""

    def __init__(self, admin_users=None):
        self.admin_users = admin_users or set()
        self.admin_group = "devlakemcpadmin"

    @property
    def enabled(self):
        return True

    def is_admin(self, username):
        return username.lower() in self.admin_users

    def get_user_groups(self, username):
        if username.lower() in self.admin_users:
            return {self.admin_group}
        return set()

    def get_cache_stats(self):
        return {
            "server": "mock",
            "admin_group": self.admin_group,
            "cache_size": 0,
            "cache_ttl": 300,
        }


class TestAuthorizationService:
    """Tests for AuthorizationService class."""

    def test_initialization_with_defaults(self):
        """Test authorization service initializes with default roles and viewer as default."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        assert auth_service.role_permissions == ROLE_PERMISSIONS
        assert auth_service.default_role == "mcp-viewer"

    def test_initialization_with_custom_roles(self):
        """Test authorization service with custom role definitions."""
        custom_roles = {
            "custom-viewer": {"list_databases"},
            "custom-admin": {"*"},
        }
        mock_ldap = MockLDAPService()

        auth_service = AuthorizationService(role_permissions=custom_roles, ldap_service=mock_ldap)

        assert auth_service.role_permissions == custom_roles

    def test_viewer_can_access_allowed_tools(self):
        """Test that mcp-viewer role can access read-only tools."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Viewer should be able to access these tools
        allowed_tools = [
            "list_databases",
            "list_tables",
            "get_table_schema",
            "get_incidents",
            "get_deployments",
            "get_pr_stats",
            "get_historical_trends",
        ]

        for tool in allowed_tools:
            assert auth_service.is_authorized(tool) is True

    def test_viewer_cannot_access_execute_query(self):
        """Test that mcp-viewer role cannot access execute_query."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Viewer should NOT be able to execute raw queries
        assert auth_service.is_authorized("execute_query") is False

    def test_admin_can_access_all_tools(self):
        """Test that mcp-admin role can access all tools including execute_query."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Admin should be able to access everything
        all_tools = [
            "list_databases",
            "execute_query",
            "get_incidents",
            "some_future_tool",  # Wildcard should allow any tool
        ]

        for tool in all_tools:
            # Use LDAP-based admin assignment
            assert auth_service.is_authorized(tool, username="admin") is True

    def test_user_gets_default_role(self):
        """Test that users get default viewer role."""
        mock_ldap = MockLDAPService()
        # Default behavior: users get mcp-viewer role
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Should be able to access viewer tools
        assert auth_service.is_authorized("list_databases") is True
        # But not admin tools
        assert auth_service.is_authorized("execute_query") is False

    def test_ldap_admin_grants_full_access(self):
        """Test that LDAP admin group grants full access including execute_query."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Admin via LDAP should grant full access
        assert auth_service.is_authorized("execute_query", username="admin") is True
        # Non-admin via LDAP should not have execute_query
        assert auth_service.is_authorized("execute_query", username="user") is False

    def test_get_allowed_tools_for_viewer(self):
        """Test getting allowed tools for viewer role."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        allowed = auth_service.get_allowed_tools()

        assert "list_databases" in allowed
        assert "get_incidents" in allowed
        assert "execute_query" not in allowed
        assert "*" not in allowed

    def test_get_allowed_tools_for_admin(self):
        """Test getting allowed tools for admin role returns wildcard."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Use LDAP-based admin assignment
        allowed = auth_service.get_allowed_tools(username="admin")

        assert allowed == {"*"}

    def test_get_denied_reason(self):
        """Test denied reason for admin-only tool."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        reason = auth_service.get_denied_reason("execute_query")

        assert "execute_query" in reason
        assert "mcp-admin" in reason

    def test_get_role_info(self):
        """Test getting role configuration info."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        info = auth_service.get_role_info()

        assert "roles" in info
        assert "mcp-viewer" in info["roles"]
        assert "mcp-admin" in info["roles"]
        assert info["roles"]["mcp-admin"]["access"] == "full"
        assert info["roles"]["mcp-viewer"]["access"] == "limited"
        assert "ldap" in info

    def test_default_role_assignment(self):
        """Test default role for users without explicit assignment."""
        mock_ldap = MockLDAPService()
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # User should get default role permissions (mcp-viewer)
        assert auth_service.is_authorized("get_incidents") is True
        assert auth_service.is_authorized("execute_query") is False


class TestLDAPBasedRoles:
    """Tests for LDAP-based role assignment."""

    def test_ldap_admin_user_gets_admin_role(self):
        """Test that LDAP admin user gets admin access."""
        mock_ldap = MockLDAPService(admin_users={"admin", "team-lead"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Admin user should get full access
        assert auth_service.is_authorized("execute_query", username="admin") is True
        assert auth_service.is_authorized("list_databases", username="admin") is True

    def test_non_ldap_admin_gets_viewer_role(self):
        """Test that non-admin user gets viewer role."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Non-admin user should get viewer access only
        assert auth_service.is_authorized("list_databases", username="user") is True
        assert auth_service.is_authorized("execute_query", username="user") is False

    def test_username_matching_case_insensitive(self):
        """Test that username matching is case-insensitive."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        # Should match regardless of case
        assert auth_service.is_authorized("execute_query", username="ADMIN") is True
        assert auth_service.is_authorized("execute_query", username="Admin") is True

    def test_resolve_user_roles_with_ldap_admin(self):
        """Test resolving roles when user is LDAP admin."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        roles = auth_service.resolve_user_roles(username="admin")
        assert "mcp-admin" in roles

    def test_resolve_user_roles_without_ldap_match(self):
        """Test resolving roles when user is not LDAP admin."""
        mock_ldap = MockLDAPService(admin_users={"admin"})
        auth_service = AuthorizationService(ldap_service=mock_ldap)

        roles = auth_service.resolve_user_roles(username="user")
        assert "mcp-viewer" in roles
        assert "mcp-admin" not in roles


class TestUserContext:
    """Tests for user context management."""

    def test_set_and_get_user_context(self):
        """Test setting and getting user context."""
        user_info = {
            "id": "user-123",
            "username": "testuser",
            "groups": ["mcp-viewer"],
        }

        set_user_context(user_info)
        retrieved = get_user_context()

        assert retrieved == user_info

    def test_clear_user_context(self):
        """Test clearing user context."""
        set_user_context({"id": "test"})
        set_user_context(None)

        assert get_user_context() is None

    def test_default_context_is_none(self):
        """Test that default context is None."""
        # Clear any existing context
        set_user_context(None)

        assert get_user_context() is None


class TestToolHandlerRBAC:
    """Tests for RBAC integration in ToolHandler."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_tools_manager = MagicMock()
        self.mock_security_manager = MagicMock()
        # Clear user context before each test
        set_user_context(None)

    def test_tool_handler_with_rbac_enabled(self):
        """Test tool handler initializes with RBAC enabled."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=True,
        )

        assert handler.rbac_enabled is True
        assert handler.authorization_service is not None

    def test_tool_handler_with_rbac_disabled(self):
        """Test tool handler initializes with RBAC disabled."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=False,
        )

        assert handler.rbac_enabled is False
        assert handler.authorization_service is None

    @pytest.mark.asyncio
    async def test_authorized_user_can_call_tool(self):
        """Test that authorized user can call tool successfully."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=True,
        )

        # Set user context with viewer role
        set_user_context(
            {
                "id": "user-123",
                "username": "viewer-user",
                "groups": ["mcp-viewer"],
            }
        )

        # Mock tool execution
        self.mock_tools_manager.call_tool.return_value = '{"success": true}'

        # Call a tool that viewer can access
        result = await handler.handle_tool_call("get_incidents", {})

        # Should succeed
        assert len(result) == 1
        self.mock_tools_manager.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_unauthorized_user_denied(self):
        """Test that unauthorized user is denied access."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=True,
        )

        # Set user context with viewer role
        set_user_context(
            {
                "id": "user-123",
                "username": "viewer-user",
                "groups": ["mcp-viewer"],
            }
        )

        # Try to call execute_query (admin only)
        result = await handler.handle_tool_call("execute_query", {"query": "SELECT 1"})

        # Should be denied
        assert len(result) == 1
        response_text = result[0].text
        assert "Access denied" in response_text
        # Tool should not be called
        self.mock_tools_manager.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_user_context_denied(self):
        """Test that missing user context results in denied access."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=True,
        )

        # No user context set
        set_user_context(None)

        # Try to call any tool
        result = await handler.handle_tool_call("list_databases", {})

        # Should be denied
        assert len(result) == 1
        response_text = result[0].text
        assert "authentication required" in response_text
        self.mock_tools_manager.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_rbac_disabled_allows_all(self):
        """Test that with RBAC disabled, all tools are accessible."""
        handler = ToolHandler(
            self.mock_tools_manager,
            self.mock_security_manager,
            rbac_enabled=False,
        )

        # No user context
        set_user_context(None)

        # Mock tool execution
        self.mock_tools_manager.call_tool.return_value = '{"success": true}'
        self.mock_security_manager.validate_sql_query.return_value = (True, "OK")

        # Call execute_query - should work without auth
        await handler.handle_tool_call("execute_query", {"query": "SELECT 1"})

        # Should succeed (no RBAC check) - tool was called
        self.mock_tools_manager.call_tool.assert_called_once()
