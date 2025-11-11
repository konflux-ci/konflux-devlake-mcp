#!/usr/bin/env python3
"""
Core MCP Server Implementation

This module contains the main MCP server class that handles protocol communication,
tool management, and security validation.
"""

from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import Tool, TextContent

from server.handlers.tool_handler import ToolHandler
from server.transport.base_transport import BaseTransport
from utils.logger import get_logger


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

        # Initialize core components
        self.server = Server("konflux-devlake-mcp-server")
        self.tool_handler = ToolHandler(tools_manager, security_manager)
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeMCPServer")

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
        """
        self.logger.info(f"Starting MCP server with {transport.__class__.__name__}")
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
