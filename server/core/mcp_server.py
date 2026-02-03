#!/usr/bin/env python3
"""
Core MCP Server Implementation

This module contains the main MCP server class that handles protocol communication,
tool management, and security validation.
"""

import asyncio
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import Tool, TextContent

from server.handlers.tool_handler import ToolHandler
from server.transport.base_transport import BaseTransport
from utils.logger import get_logger
from utils.rbac import AuthorizationService


class KonfluxDevLakeMCPServer:
    """
    Core MCP Server for Konflux DevLake operations.

    This class manages the MCP protocol server, tool handling, security validation,
    and provides a clean interface for different transport layers.
    """

    def __init__(self, config, db_connection, tools_manager, security_manager):
        """
        Initialize the MCP server.

        Args:
            config: Server configuration object
            db_connection: Database connection manager
            tools_manager: Tools management system
            security_manager: Security validation system
        """
        self.config = config
        self.db_connection = db_connection
        self.tools_manager = tools_manager
        self.security_manager = security_manager
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeMCPServer")

        # Initialize RBAC - enabled when OIDC is enabled
        rbac_enabled = False
        if hasattr(config, "oidc") and config.oidc.enabled:
            rbac_enabled = True
            self.logger.info("RBAC enabled (OIDC authentication is active)")
        else:
            self.logger.info("RBAC disabled (OIDC authentication is not active)")

        # Initialize core components
        self.server = Server("konflux-devlake-mcp-server")
        self.authorization_service = AuthorizationService() if rbac_enabled else None
        self.tool_handler = ToolHandler(
            tools_manager,
            security_manager,
            authorization_service=self.authorization_service,
            rbac_enabled=rbac_enabled,
        )

        # Setup protocol handlers
        self._setup_protocol_handlers()

    def _setup_protocol_handlers(self):
        """Setup MCP protocol handlers for tool listing and execution."""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Handle tool list request from MCP clients."""
            try:
                self.logger.info("Handling tool list request")
                tools = await self.tools_manager.list_tools()
                self.logger.info(f"Returning {len(tools)} tools")
                return tools
            except Exception as e:
                self.logger.error(f"Failed to handle tool list request: {e}")
                return []

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool execution request from MCP clients."""
            return await self.tool_handler.handle_tool_call(name, arguments)

    async def start(self, transport: BaseTransport):
        """
        Start the MCP server with the specified transport.

        Args:
            transport: Transport layer implementation

        Raises:
            ConnectionError: If database connection cannot be established
        """
        self.logger.info(f"Starting MCP server with {transport.__class__.__name__}")

        # Initialize database connection pool at startup (eager initialization)
        # Server will not start if database is unreachable
        self.logger.info("Initializing database connection pool...")
        result = await self.db_connection.connect()
        if not result.get("success"):
            error_msg = f"Database connection failed: {result.get('error')}"
            self.logger.error(error_msg)
            self.logger.error("Server cannot start without database connection. Exiting.")
            raise ConnectionError(error_msg)

        pool_info = self.db_connection.get_connection_info()
        self.logger.info(
            f"Database pool initialized: "
            f"size={pool_info.get('pool_size', 'N/A')}, "
            f"min={pool_info.get('pool_minsize', 'N/A')}, "
            f"max={pool_info.get('pool_maxsize', 'N/A')}"
        )

        await transport.start(self.server)

    async def shutdown(self):
        """Gracefully shutdown the MCP server and cleanup resources."""
        self.logger.info("Shutting down Konflux DevLake MCP Server")
        try:
            # Cleanup security manager
            self.security_manager.cleanup_expired_tokens()

            # Close database connection
            await self.db_connection.close()

            self.logger.info("Server shutdown complete")
        except (asyncio.CancelledError, KeyboardInterrupt):
            # Ignore cancellation errors during shutdown
            self.logger.debug("Shutdown interrupted")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information for health checks and monitoring."""
        return {
            "server_name": "konflux-devlake-mcp-server",
            "version": "1.0.0",
            "status": "running",
            "security_stats": self.security_manager.get_security_stats(),
        }
