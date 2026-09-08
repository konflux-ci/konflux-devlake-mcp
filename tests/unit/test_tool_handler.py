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
        sec_mgr.validate_database_name.return_value = (True, "")
        sec_mgr.validate_table_name.return_value = (True, "")
        return ToolHandler(Mock(), sec_mgr)

    @pytest.mark.asyncio
    async def test_normal_tool_passes(self, handler):
        result = await handler._validate_tool_request("get_pr_stats", {"project": "x"})
        assert result["valid"] is True

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
class TestValidateToolRequestInputValidation:
    """Test centralized input validation for all tools."""

    @pytest.fixture
    def handler(self):
        from utils.security import KonfluxDevLakeSecurityManager

        sec_mgr = KonfluxDevLakeSecurityManager(Mock())
        return ToolHandler(Mock(), sec_mgr)

    @pytest.mark.asyncio
    async def test_rejects_sql_injection_in_project_name(self, handler):
        result = await handler._validate_tool_request(
            "get_deployments",
            {"project": "x') UNION SELECT user FROM mysql.user -- "},
        )
        assert result["valid"] is False
        assert "disallowed" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_sql_injection_in_project_name_arg(self, handler):
        result = await handler._validate_tool_request(
            "get_incidents",
            {"project_name": "x'; DROP TABLE incidents; --"},
        )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_rejects_sql_injection_in_repo_name(self, handler):
        result = await handler._validate_tool_request(
            "analyze_pr_retests",
            {"repo_name": "repo; DROP TABLE incidents --"},
        )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_rejects_invalid_date(self, handler):
        result = await handler._validate_tool_request(
            "get_deployments",
            {"start_date": "not-a-date"},
        )
        assert result["valid"] is False
        assert "start_date" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_negative_days_back(self, handler):
        result = await handler._validate_tool_request(
            "get_deployments",
            {"days_back": -1},
        )
        assert result["valid"] is False
        assert "days_back" in result["error"]

    @pytest.mark.asyncio
    async def test_allows_legitimate_project_names(self, handler):
        legitimate_names = [
            "Konflux_Pilot_Team",
            "Secureflow - Konflux - Global",
            "Secureflow - Konflux - Build Team",
        ]
        for name in legitimate_names:
            result = await handler._validate_tool_request("get_deployments", {"project": name})
            assert result["valid"] is True, f"Rejected legitimate project name: {name}"

    @pytest.mark.asyncio
    async def test_allows_valid_dates(self, handler):
        result = await handler._validate_tool_request(
            "get_deployments",
            {"start_date": "2024-01-15", "end_date": "2024-01-31"},
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_skips_empty_optional_args(self, handler):
        result = await handler._validate_tool_request(
            "get_deployments",
            {"project": "", "start_date": "", "days_back": None},
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_rejects_denied_table_in_get_table_schema(self, handler):
        result = await handler._validate_tool_request(
            "get_table_schema",
            {"database": "lake", "table": "_devlake_api_keys"},
        )
        assert result["valid"] is False
        assert "_devlake_api_keys" in result["error"]
        assert result["security_check"] == "failed"

    @pytest.mark.asyncio
    async def test_rejects_connection_table_in_get_table_schema(self, handler):
        result = await handler._validate_tool_request(
            "get_table_schema",
            {"database": "lake", "table": "_tool_github_connections"},
        )
        assert result["valid"] is False
        assert "_tool_github_connections" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_raw_table_in_get_table_schema(self, handler):
        result = await handler._validate_tool_request(
            "get_table_schema",
            {"database": "lake", "table": "_raw_github_api_issues"},
        )
        assert result["valid"] is False
        assert "_raw_github_api_issues" in result["error"]

    @pytest.mark.asyncio
    async def test_allows_normal_table_in_get_table_schema(self, handler):
        result = await handler._validate_tool_request(
            "get_table_schema",
            {"database": "lake", "table": "incidents"},
        )
        assert result["valid"] is True


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
