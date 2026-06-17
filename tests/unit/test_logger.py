#!/usr/bin/env python3
import logging
import os
import pytest
from unittest.mock import patch

from utils.logger import (
    set_client_id,
    get_client_id,
    clear_client_id,
    get_logger,
    log_system_info,
    setup_module_logging,
    log_function_call,
    log_database_operation,
    log_tool_call,
    shutdown_logging,
    LoggerMixin,
    ClosedResourceErrorFilter,
)


@pytest.mark.unit
class TestClientIdContext:
    def test_set_and_get(self):
        set_client_id("abc123")
        assert get_client_id() == "abc123"
        clear_client_id()

    def test_clear(self):
        set_client_id("abc123")
        clear_client_id()
        assert get_client_id() is None

    def test_default_none(self):
        clear_client_id()
        assert get_client_id() is None


@pytest.mark.unit
class TestGetLogger:
    def test_with_name(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_without_name(self):
        logger = get_logger()
        assert isinstance(logger, logging.Logger)


@pytest.mark.unit
class TestClosedResourceErrorFilter:
    @pytest.fixture
    def filter_instance(self):
        return ClosedResourceErrorFilter()

    def test_passes_normal_message(self, filter_instance):
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Normal error message",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_suppresses_closed_resource_from_mcp(self, filter_instance):
        record = logging.LogRecord(
            name="mcp.server.streamable_http",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="ClosedResourceError in handler",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_suppresses_error_in_message_router(self, filter_instance):
        record = logging.LogRecord(
            name="mcp.server",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error in message router",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_passes_non_mcp_closed_resource(self, filter_instance):
        record = logging.LogRecord(
            name="other.module",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="ClosedResourceError happened",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_suppresses_exc_info_closed_resource(self, filter_instance):
        from anyio import ClosedResourceError

        try:
            raise ClosedResourceError()
        except ClosedResourceError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Some error",
            args=(),
            exc_info=exc_info,
        )
        assert filter_instance.filter(record) is False


@pytest.mark.unit
class TestLogSystemInfo:
    @patch.dict(os.environ, {"DB_HOST": "localhost", "DB_PORT": "3306"}, clear=False)
    def test_log_system_info(self):
        log_system_info()

    @patch.dict(
        os.environ,
        {"DB_HOST": "localhost", "DB_PASSWORD": "secret123"},
        clear=False,
    )
    def test_log_system_info_masks_password(self):
        log_system_info()


@pytest.mark.unit
class TestSetupModuleLogging:
    def test_returns_logger(self):
        logger = setup_module_logging("test.module", "DEBUG")
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.DEBUG

    def test_default_level(self):
        logger = setup_module_logging("test.module2")
        assert logger.level == logging.INFO


@pytest.mark.unit
class TestLogFunctionCall:
    def test_decorator_success(self):
        @log_function_call("my_func")
        def my_func(x):
            return x * 2

        result = my_func(5)
        assert result == 10

    def test_decorator_exception(self):
        @log_function_call("failing_func")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()


@pytest.mark.unit
class TestLogDatabaseOperation:
    def test_success(self):
        log_database_operation("SELECT", query="SELECT 1", success=True)

    def test_failure(self):
        log_database_operation(
            "INSERT", query="INSERT INTO t", success=False, error="Duplicate key"
        )


@pytest.mark.unit
class TestLogToolCall:
    def test_success_no_client(self):
        clear_client_id()
        log_tool_call("test_tool", arguments={"key": "val"}, success=True)

    def test_success_with_client(self):
        set_client_id("client123")
        log_tool_call("test_tool", arguments={"key": "val"}, success=True)
        clear_client_id()

    def test_failure(self):
        log_tool_call(
            "test_tool",
            arguments={"key": "val"},
            success=False,
            error="Tool failed",
        )


@pytest.mark.unit
class TestShutdownLogging:
    def test_shutdown(self):
        shutdown_logging()


@pytest.mark.unit
class TestLoggerMixin:
    def test_mixin(self):
        class MyClass(LoggerMixin):
            pass

        obj = MyClass()
        assert obj.logger is not None
        obj.log_info("test info")
        obj.log_error("test error")
        obj.log_debug("test debug")
        obj.log_warning("test warning")

    def test_mixin_with_exc_info(self):
        class MyClass(LoggerMixin):
            pass

        obj = MyClass()
        obj.log_error("error with exc", exc_info=True)
