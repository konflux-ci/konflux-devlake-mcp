#!/usr/bin/env python3
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch

from server.handlers.tool_handler import (
    ToolHandler,
    set_user_context,
    get_user_context,
)


@pytest.mark.unit
class TestUserContext:
    def test_set_and_get(self):
        set_user_context({"username": "alice"})
        assert get_user_context() == {"username": "alice"}
        set_user_context(None)

    def test_default_none(self):
        set_user_context(None)
        assert get_user_context() is None


@pytest.mark.unit
class TestToolHandlerInit:
    def test_init_rbac_disabled(self):
        handler = ToolHandler(Mock(), Mock(), rbac_enabled=False)
        assert handler.rbac_enabled is False
        assert handler.authorization_service is None

    def test_init_rbac_enabled_with_auth_service(self):
        auth_svc = Mock()
        handler = ToolHandler(
            Mock(), Mock(), authorization_service=auth_svc, rbac_enabled=True
        )
        assert handler.rbac_enabled is True
        assert handler.authorization_service is auth_svc

    @patch("server.handlers.tool_handler.AuthorizationService")
    def test_init_rbac_enabled_creates_auth_service(self, mock_auth_cls):
        mock_auth_cls.return_value = Mock()
        handler = ToolHandler(Mock(), Mock(), rbac_enabled=True)
        assert handler.authorization_service is not None
        mock_auth_cls.assert_called_once()


@pytest.mark.unit
class TestHandleToolCall:
    @pytest.fixture
    def handler(self):
        tools_mgr = Mock()
        tools_mgr.call_tool = AsyncMock(return_value='{"success": true}')
        sec_mgr = Mock()
        return ToolHandler(tools_mgr, sec_mgr, rbac_enabled=False)

    @pytest.mark.asyncio
    async def test_success(self, handler):
        result = await handler.handle_tool_call("some_tool", {"key": "val"})
        assert len(result) == 1
        assert result[0].type == "text"
        assert "true" in result[0].text

    @pytest.mark.asyncio
    async def test_exception(self, handler):
        handler.tools_manager.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
        result = await handler.handle_tool_call("some_tool", {})
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert "boom" in parsed["error"]

    @pytest.mark.asyncio
    async def test_rbac_denied(self):
        auth_svc = Mock()
        auth_svc.is_authorized.return_value = False
        auth_svc.get_denied_reason.return_value = "Not authorized"
        handler = ToolHandler(
            Mock(), Mock(), authorization_service=auth_svc, rbac_enabled=True
        )
        set_user_context({"username": "bob"})
        result = await handler.handle_tool_call("admin_tool", {})
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert "Not authorized" in parsed["error"]
        set_user_context(None)

    @pytest.mark.asyncio
    async def test_rbac_no_user_context(self):
        auth_svc = Mock()
        handler = ToolHandler(
            Mock(), Mock(), authorization_service=auth_svc, rbac_enabled=True
        )
        set_user_context(None)
        result = await handler.handle_tool_call("admin_tool", {})
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert "authentication required" in parsed["error"]

    @pytest.mark.asyncio
    async def test_rbac_authorized(self):
        auth_svc = Mock()
        auth_svc.is_authorized.return_value = True
        tools_mgr = Mock()
        tools_mgr.call_tool = AsyncMock(return_value='{"success": true}')
        sec_mgr = Mock()
        handler = ToolHandler(
            tools_mgr, sec_mgr, authorization_service=auth_svc, rbac_enabled=True
        )
        set_user_context({"username": "alice"})
        result = await handler.handle_tool_call("some_tool", {})
        assert "true" in result[0].text
        set_user_context(None)


@pytest.mark.unit
class TestValidateToolRequest:
    @pytest.fixture
    def handler(self):
        sec_mgr = Mock()
        sec_mgr.validate_sql_query.return_value = (True, "")
        sec_mgr.validate_database_name.return_value = (True, "")
        sec_mgr.validate_table_name.return_value = (True, "")
        return ToolHandler(Mock(), sec_mgr, rbac_enabled=False)

    @pytest.mark.asyncio
    async def test_normal_tool_passes(self, handler):
        result = await handler._validate_tool_request("get_pr_stats", {"project": "x"})
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_execute_query_valid(self, handler):
        result = await handler._validate_tool_request(
            "execute_query", {"query": "SELECT 1"}
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_execute_query_sql_invalid(self, handler):
        handler.security_manager.validate_sql_query.return_value = (
            False,
            "dangerous query",
        )
        result = await handler._validate_tool_request(
            "execute_query", {"query": "DROP TABLE users"}
        )
        assert result["valid"] is False
        assert "SQL query validation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_query_injection(self, handler):
        handler.sql_injection_detector.detect_sql_injection = Mock(
            return_value=(True, ["UNION SELECT"])
        )
        result = await handler._validate_tool_request(
            "execute_query", {"query": "1 UNION SELECT * FROM users"}
        )
        assert result["valid"] is False
        assert "SQL injection" in result["error"]

    @pytest.mark.asyncio
    async def test_list_tables_invalid_db(self, handler):
        handler.security_manager.validate_database_name.return_value = (
            False,
            "bad db name",
        )
        result = await handler._validate_tool_request(
            "list_tables", {"database": "../../etc"}
        )
        assert result["valid"] is False
        assert "Database name" in result["error"]

    @pytest.mark.asyncio
    async def test_get_table_schema_invalid_table(self, handler):
        handler.security_manager.validate_table_name.return_value = (
            False,
            "bad table",
        )
        result = await handler._validate_tool_request(
            "get_table_schema", {"database": "lake", "table": "bad;table"}
        )
        assert result["valid"] is False
        assert "Table name" in result["error"]


@pytest.mark.unit
class TestMaskSensitiveData:
    @pytest.fixture
    def handler(self):
        return ToolHandler(Mock(), Mock(), rbac_enabled=False)

    def test_json_with_data(self, handler):
        result = handler._mask_sensitive_data(json.dumps({"data": [{"name": "test"}]}))
        parsed = json.loads(result)
        assert "data" in parsed

    def test_non_json(self, handler):
        result = handler._mask_sensitive_data("plain text result")
        assert result == "plain text result"

    def test_json_without_data_key(self, handler):
        result = handler._mask_sensitive_data(json.dumps({"other": "val"}))
        assert result == json.dumps({"other": "val"})


@pytest.mark.unit
class TestCreateErrorResponse:
    @pytest.fixture
    def handler(self):
        return ToolHandler(Mock(), Mock(), rbac_enabled=False)

    def test_basic_error(self, handler):
        result = handler._create_error_response("Something failed")
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert parsed["error"] == "Something failed"
        assert "tool_name" not in parsed

    def test_error_with_tool_info(self, handler):
        result = handler._create_error_response(
            "Failed", tool_name="my_tool", arguments={"x": 1}
        )
        parsed = json.loads(result[0].text)
        assert parsed["tool_name"] == "my_tool"
        assert parsed["arguments"] == {"x": 1}
