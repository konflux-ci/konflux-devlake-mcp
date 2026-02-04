#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Logging Utility
"""

import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

# Global logger instance
_logger_instance: Optional[logging.Logger] = None

# Context variable to track current client ID for tool call logging
client_id_var: ContextVar[Optional[str]] = ContextVar("client_id", default=None)


def set_client_id(client_id: str) -> None:
    """Set the current client ID for logging context."""
    client_id_var.set(client_id)


def get_client_id() -> Optional[str]:
    """Get the current client ID from logging context."""
    return client_id_var.get()


def clear_client_id() -> None:
    """Clear the current client ID from logging context."""
    client_id_var.set(None)


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance with proper configuration"""
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = _setup_logging()

    if name:
        return logging.getLogger(name)
    else:
        return _logger_instance


class ClosedResourceErrorFilter(logging.Filter):
    """Filter to suppress ClosedResourceError from MCP library (normal client disconnections)"""

    def filter(self, record):
        # Suppress ClosedResourceError messages from MCP library
        message = record.getMessage()

        # Check if this is from MCP server streamable_http
        if "mcp.server" in record.name or "streamable_http" in record.name:
            # Suppress ClosedResourceError and related connection errors
            if any(
                keyword in message
                for keyword in [
                    "ClosedResourceError",
                    "closed resource",
                    "Error in message router",
                    "receive_nowait",
                    "anyio.ClosedResourceError",
                ]
            ):
                return False

        # Also check the exception type if available
        if hasattr(record, "exc_info") and record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type and "ClosedResourceError" in str(exc_type):
                return False

        return True


def _setup_logging() -> logging.Logger:
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    logs_dir = Path(os.getenv("LOG_DIR", "logs"))
    logs_dir.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Create filter for MCP library errors
    closed_resource_filter = ClosedResourceErrorFilter()

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addFilter(closed_resource_filter)

    # Also filter MCP library loggers specifically
    mcp_loggers = ["mcp.server", "mcp.server.streamable_http", "mcp.server.streamable_http_manager"]
    for logger_name in mcp_loggers:
        mcp_logger = logging.getLogger(logger_name)
        mcp_logger.addFilter(closed_resource_filter)
        mcp_logger.setLevel(logging.WARNING)  # Only show warnings and above from MCP library

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with filter - use stderr for stdio transport compatibility
    # When using stdio transport, stdout must only contain JSONRPC messages
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(closed_resource_filter)
    root_logger.addHandler(console_handler)

    # File handler for general logs with filter
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "konflux_devlake_mcp_server.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(closed_resource_filter)
    root_logger.addHandler(file_handler)

    # Error file handler with filter (but still log other errors)
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "konflux_devlake_mcp_server_error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(closed_resource_filter)
    root_logger.addHandler(error_handler)

    # Create main logger
    logger = logging.getLogger("konflux_devlake_mcp_server")
    logger.info("Logging system initialized")

    return logger


def log_system_info():
    """Log system information for debugging"""
    logger = get_logger(__name__)

    logger.info("=== System Information ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Logs directory: {Path(os.getenv('LOG_DIR', 'logs')).absolute()}")

    # Log environment variables (without sensitive data)
    env_vars = [
        "DB_HOST",
        "DB_PORT",
        "DB_USER",
        "DB_DATABASE",
        "TRANSPORT",
        "SERVER_HOST",
        "SERVER_PORT",
        "LOG_LEVEL",
    ]

    logger.info("=== Environment Variables ===")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask password-like variables
            if "PASSWORD" in var.upper():
                logger.info(f"{var}: {'*' * len(value)}")
            else:
                logger.info(f"{var}: {value}")

    logger.info("=== End System Information ===")


def setup_module_logging(module_name: str, log_level: str = "INFO"):
    """Setup logging for a specific module"""
    logger = logging.getLogger(module_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    return logger


def log_function_call(func_name: str, args: dict = None, kwargs: dict = None):
    """Decorator to log function calls"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(f"{func.__module__}.{func.__name__}")
            logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{func_name} failed with error: {e}")
                raise

        return wrapper

    return decorator


def log_database_operation(
    operation: str, query: str = None, success: bool = True, error: str = None
):
    """Log database operations"""
    logger = get_logger("database_operations")

    if success:
        logger.info(f"Database operation '{operation}' completed successfully")
        if query:
            logger.debug(f"Query: {query}")
    else:
        logger.error(f"Database operation '{operation}' failed: {error}")
        if query:
            logger.debug(f"Failed query: {query}")


def log_tool_call(tool_name: str, arguments: dict = None, success: bool = True, error: str = None):
    """Log tool calls with client ID for traceability."""
    logger = get_logger("tool_calls")

    # Get client ID from context for traceability
    client_id = get_client_id()
    client_info = f" by client={client_id}" if client_id else ""

    if success:
        logger.info(f"Tool '{tool_name}' called{client_info}")
        if arguments:
            logger.debug(f"Arguments: {arguments}")
    else:
        logger.error(f"Tool '{tool_name}' failed{client_info}: {error}")
        if arguments:
            logger.debug(f"Failed arguments: {arguments}")


def shutdown_logging():
    """Shutdown logging system"""
    try:
        logger = get_logger(__name__)
        logger.info("Shutting down logging system")

        # Flush all handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            try:
                handler.flush()
                handler.close()
            except (ValueError, OSError):
                # Ignore errors when closing handlers (file may already be closed)
                pass

        logger.info("Logging system shutdown complete")
    except (ValueError, OSError):
        # Ignore errors during shutdown (handlers may already be closed)
        pass


class LoggerMixin:
    """Mixin class to add logging capabilities to other classes"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def log_info(self, message: str):
        """Log info message"""
        self.logger.info(message)

    def log_error(self, message: str, exc_info: bool = False):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)

    def log_debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)

    def log_warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
