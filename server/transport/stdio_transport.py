#!/usr/bin/env python3
"""
STDIO Transport Implementation

This module provides the STDIO transport layer for local MCP server communication.
"""

from typing import Dict, Any

from mcp.server import Server
from mcp.server.models import InitializationOptions

from server.transport.base_transport import BaseTransport
from utils.logger import get_logger


class StdioTransport(BaseTransport):
    """
    STDIO transport implementation for local MCP server communication.

    This transport handles communication via standard input/output streams,
    typically used for local development and testing.
    """

    def __init__(self):
        """Initialize the STDIO transport."""
        self.logger = get_logger(f"{__name__}.StdioTransport")
        self._server = None

    async def start(self, server: Server) -> None:
        """
        Start the STDIO transport with the given MCP server.

        Args:
            server: MCP server instance to handle requests
        """
        self.logger.info("Starting Konflux DevLake MCP Server (stdio mode)")

        try:
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                init_options = InitializationOptions(
                    server_name="konflux-devlake-mcp-server",
                    server_version="1.0.0",
                    capabilities={"tools": {}},
                )

                await server.run(read_stream, write_stream, init_options)

        except Exception as e:
            self.logger.error(f"STDIO server startup failed: {e}")
            raise

    async def stop(self) -> None:
        """Stop the STDIO transport."""
        self.logger.info("Stopping STDIO transport")
        # STDIO transport doesn't require explicit cleanup

    def get_transport_info(self) -> Dict[str, Any]:
        """
        Get STDIO transport information.

        Returns:
            Dictionary containing STDIO transport information
        """
        return {
            "type": "stdio",
            "description": "Standard input/output transport for local communication",
            "capabilities": ["local_development", "testing"],
        }
