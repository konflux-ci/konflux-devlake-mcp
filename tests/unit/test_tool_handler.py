#!/usr/bin/env python3
import json
import pytest
from unittest.mock import Mock, AsyncMock

from server.handlers.tool_handler import ToolHandler


@pytest.mark.unit
class TestHandleToolCall:
    @pytest.fixture
    def handler(self):
        tools_mgr = Mock()
        tools_mgr.call_tool = AsyncMock(return_value='{"success": true}')
        sec_mgr = Mock()
        return ToolHandler(tools_mgr, sec_mgr)

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


@pytest.mark.unit
class TestValidateToolRequest:
    @pytest.fixture
    def handler(self):
        sec_mgr = Mock()
        sec_mgr.validate_sql_query.return_value = (True, "")
        sec_mgr.validate_database_name.return_value = (True, "")
        sec_mgr.validate_table_name.return_value = (True, "")
        return ToolHandler(Mock(), sec_mgr)

    @pytest.mark.asyncio
    async def test_normal_tool_passes(self, handler):
        result = await handler._validate_tool_request("get_pr_stats", {"project": "x"})
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_execute_query_valid(self, handler):
        result = await handler._validate_tool_request("execute_query", {"query": "SELECT 1"})
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
        result = await handler._validate_tool_request("list_tables", {"database": "../../etc"})
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
        return ToolHandler(Mock(), Mock())

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
        return ToolHandler(Mock(), Mock())

    def test_basic_error(self, handler):
        result = handler._create_error_response("Something failed")
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert parsed["error"] == "Something failed"
        assert "tool_name" not in parsed

    def test_error_with_tool_info(self, handler):
        result = handler._create_error_response("Failed", tool_name="my_tool", arguments={"x": 1})
        parsed = json.loads(result[0].text)
        assert parsed["tool_name"] == "my_tool"
        assert parsed["arguments"] == {"x": 1}
