#!/usr/bin/env python3
"""Unit tests for LDAP-backed MCP RBAC."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.handlers.tool_handler import ToolHandler
from utils.request_context import reset_user_context, set_user_context
from utils.rbac import AuthorizationService, ROLE_PERMISSIONS
from utils.security import KonfluxDevLakeSecurityManager


class FakeLDAPService:
    admin_group = "devlakemcpadmin"

    def __init__(self, admins=None):
        self.admins = {value.lower() for value in (admins or set())}

    def is_admin(self, username):
        return username.lower() in self.admins

    def get_cache_stats(self):
        return {"admin_group": self.admin_group, "cache_size": 0, "cache_ttl": 300}


async def is_authorized(service, tool_name, username):
    """Call the same entry point the tool handler uses."""
    return (await service.get_tool_authorization(tool_name, username))["authorized"]


@pytest.mark.unit
class TestAuthorizationService:
    @pytest.mark.asyncio
    async def test_non_admin_gets_viewer_permissions(self):
        service = AuthorizationService(ldap_service=FakeLDAPService())
        assert await is_authorized(service, "get_incidents", "alice") is True
        assert await is_authorized(service, "execute_query", "alice") is False

    @pytest.mark.asyncio
    async def test_admin_gets_all_permissions(self):
        service = AuthorizationService(ldap_service=FakeLDAPService({"alice"}))
        assert await is_authorized(service, "execute_query", "alice") is True
        assert await is_authorized(service, "future_tool", "alice") is True

    @pytest.mark.asyncio
    async def test_missing_username_gets_no_admin_access(self):
        service = AuthorizationService(ldap_service=FakeLDAPService({"alice"}))
        assert await is_authorized(service, "execute_query", None) is False

    def test_policy_contains_viewer_and_admin_roles(self):
        assert ROLE_PERMISSIONS["mcp-admin"] == {"*"}
        assert "execute_query" not in ROLE_PERMISSIONS["mcp-viewer"]


@pytest.mark.unit
class TestToolHandlerRBAC:
    @pytest.fixture
    def dependencies(self):
        tools = MagicMock()
        tools.call_tool = AsyncMock(return_value='{"success": true}')
        security = MagicMock()
        security.validate_database_name.return_value = (True, "")
        security.validate_table_name.return_value = (True, "")
        return tools, security

    @pytest.mark.asyncio
    async def test_viewer_cannot_execute_query(self, dependencies):
        tools, security = dependencies
        service = AuthorizationService(ldap_service=FakeLDAPService())
        handler = ToolHandler(tools, security, service, rbac_enabled=True)
        token = set_user_context({"username": "alice"})
        try:
            result = await handler.handle_tool_call("execute_query", {"query": "SELECT 1"})
        finally:
            reset_user_context(token)

        assert "Access denied" in result[0].text
        tools.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_can_execute_query(self, dependencies):
        tools, security = dependencies
        security.validate_sql_query.return_value = (True, "")
        service = AuthorizationService(ldap_service=FakeLDAPService({"alice"}))
        handler = ToolHandler(tools, security, service, rbac_enabled=True)
        token = set_user_context({"username": "alice"})
        try:
            result = await handler.handle_tool_call("execute_query", {"query": "SELECT 1"})
        finally:
            reset_user_context(token)

        assert "true" in result[0].text
        tools.call_tool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_context_is_denied(self, dependencies):
        tools, security = dependencies
        service = AuthorizationService(ldap_service=FakeLDAPService())
        handler = ToolHandler(tools, security, service, rbac_enabled=True)
        token = set_user_context(None)
        try:
            result = await handler.handle_tool_call("get_incidents", {})
        finally:
            reset_user_context(token)

        assert "authentication required" in result[0].text
        tools.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_viewer_role_reaches_table_security_policy(self):
        """Test that viewer RBAC context blocks admin-only tables in SQL validation."""
        tools = MagicMock()
        tools.call_tool = AsyncMock(return_value='{"success": true}')
        config = MagicMock()
        config.allowed_ips = []
        config.api_keys = {}
        security = KonfluxDevLakeSecurityManager(config)
        service = AuthorizationService(ldap_service=FakeLDAPService())
        handler = ToolHandler(tools, security, service, rbac_enabled=True)
        token = set_user_context({"username": "alice"})
        try:
            result = await handler.handle_tool_call(
                "get_table_schema",
                {"database": "lake", "table": "_devlake_pipelines"},
            )
        finally:
            reset_user_context(token)

        assert "Access to table '_devlake_pipelines' is denied" in result[0].text
        tools.call_tool.assert_not_awaited()
