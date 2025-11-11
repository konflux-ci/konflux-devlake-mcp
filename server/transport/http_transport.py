#!/usr/bin/env python3
"""
HTTP Transport Implementation

This module provides the HTTP transport layer for remote MCP server communication.
"""

import json
from datetime import datetime
from typing import Dict, Any

from mcp.server import Server

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from server.transport.base_transport import BaseTransport
from utils.logger import get_logger


class HttpTransport(BaseTransport):
    """
    HTTP transport implementation for remote MCP server communication.

    This transport handles communication via HTTP/HTTPS, typically used for
    production deployments and remote client connections.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 3000):
        """
        Initialize the HTTP transport.

        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        self.host = host
        self.port = port
        self.logger = get_logger(f"{__name__}.HttpTransport")
        self._session_manager = None
        self._server = None

    async def start(self, server: Server) -> None:
        """
        Start the HTTP transport with the given MCP server.

        Args:
            server: MCP server instance to handle requests
        """
        self.logger.info(
            f"Starting Konflux DevLake MCP Server (HTTP mode) - " f"{self.host}:{self.port}"
        )

        try:
            import uvicorn

            # Create session manager with improved configuration
            self._session_manager = StreamableHTTPSessionManager(
                app=server,
                json_response=True,
                stateless=True,  # Changed to True to avoid session issues
            )

            # Create health check endpoints
            app = self._create_health_endpoints()

            # Create ASGI app with MCP request handling and error handling
            mcp_app = self._create_mcp_app(app)

            # Start server with improved configuration
            config = uvicorn.Config(
                app=mcp_app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True,
                timeout_keep_alive=30,  # Keep-alive timeout
                timeout_graceful_shutdown=30,  # Graceful shutdown timeout
            )
            self._server = uvicorn.Server(config)

            # Start with improved error handling
            try:
                async with self._session_manager.run():
                    await self._server.serve()
            except Exception as e:
                self.logger.error(f"Session manager error: {e}")
                # Fallback to direct server start
                await self._server.serve()

        except Exception as e:
            self.logger.error(f"HTTP server startup failed: {e}")
            raise

    def _create_health_endpoints(self):
        """Create health check and monitoring endpoints."""
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def health_check(request: Request) -> JSONResponse:
            return JSONResponse(
                {
                    "status": "healthy",
                    "service": "konflux-devlake-mcp-server",
                    "timestamp": datetime.now().isoformat(),
                    "transport": self.get_transport_info(),
                }
            )

        async def security_stats(request: Request) -> JSONResponse:
            return JSONResponse(
                {"timestamp": datetime.now().isoformat(), "transport": self.get_transport_info()}
            )

        return Starlette(
            routes=[
                Route("/health", health_check, methods=["GET"]),
                Route("/security/stats", security_stats, methods=["GET"]),
            ]
        )

    def _create_mcp_app(self, app):
        """Create ASGI app that handles MCP requests with improved error handling."""
        from starlette.responses import Response

        async def mcp_app(scope, receive, send):
            try:
                if scope["type"] == "http":
                    path = scope.get("path", "")

                    if path.startswith("/health") or path.startswith("/security"):
                        await app(scope, receive, send)
                        return

                    if path == "/mcp" or path.startswith("/mcp/"):
                        try:
                            self.logger.debug(f"Handling MCP request: {path}")
                            await self._session_manager.handle_request(scope, receive, send)
                        except Exception as e:
                            self.logger.error(f"MCP request handling error: {e}")
                            # Return error response instead of crashing
                            response = Response(
                                json.dumps({"error": "Internal server error", "details": str(e)}),
                                status_code=500,
                                media_type="application/json",
                            )
                            await response(scope, receive, send)
                        return

                    # 404 for other paths
                    response = Response("Not Found", status_code=404)
                    await response(scope, receive, send)
            except Exception as e:
                self.logger.error(f"ASGI app error: {e}")
                # Return error response
                response = Response(
                    json.dumps({"error": "Internal server error", "details": str(e)}),
                    status_code=500,
                    media_type="application/json",
                )
                await response(scope, receive, send)

        return mcp_app

    async def stop(self) -> None:
        """Stop the HTTP transport."""
        self.logger.info("Stopping HTTP transport")
        if self._server:
            self._server.should_exit = True

    def get_transport_info(self) -> Dict[str, Any]:
        """
        Get HTTP transport information.

        Returns:
            Dictionary containing HTTP transport information
        """
        return {
            "type": "http",
            "host": self.host,
            "port": self.port,
            "description": "HTTP/HTTPS transport for remote communication",
            "capabilities": ["remote_access", "production_deployment"],
        }
