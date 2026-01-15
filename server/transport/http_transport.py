#!/usr/bin/env python3
"""
HTTP Transport Implementation

This module provides the HTTP transport layer for remote MCP server communication.
"""

import asyncio
import json
from typing import Dict, Any

from mcp.server import Server
from anyio import ClosedResourceError

from server.transport.base_transport import BaseTransport
from server.middleware.auth_middleware import create_auth_middleware
from utils.logger import get_logger


class HttpTransport(BaseTransport):
    """
    HTTP transport implementation for remote MCP server communication.

    This transport handles communication via HTTP/HTTPS, typically used for
    production deployments and remote client connections.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3000,
        timeout_keep_alive: int = 600,
        timeout_graceful_shutdown: int = 120,
        config=None,
    ):
        """
        Initialize the HTTP transport.

        Args:
            host: Host address to bind to
            port: Port number to listen on
            timeout_keep_alive: Keep-alive timeout in seconds (default: 600 for LLM connections)
            timeout_graceful_shutdown: Graceful shutdown timeout in seconds (default: 120)
            config: Optional configuration object for security manager
        """
        self.host = host
        self.port = port
        self.timeout_keep_alive = timeout_keep_alive
        self.timeout_graceful_shutdown = timeout_graceful_shutdown
        self.config = config
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
            f"Starting Konflux DevLake MCP Server (HTTP mode) - {self.host}:{self.port}"
        )

        try:
            import uvicorn

            # Create session manager with improved configuration
            # Wrap the session manager to handle ClosedResourceError gracefully
            self._session_manager = self._create_wrapped_session_manager(server)

            # Create health check endpoints
            app = self._create_health_endpoints()

            # Create ASGI app with MCP request handling and error handling
            mcp_app = self._create_mcp_app(app)

            # Apply authentication middleware if OIDC is configured
            mcp_app = create_auth_middleware(mcp_app, self.config)

            # Start server with improved configuration for LLM connections
            # Increased timeouts to handle long-running LLM requests and database queries
            config = uvicorn.Config(
                app=mcp_app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True,
                timeout_keep_alive=self.timeout_keep_alive,
                timeout_graceful_shutdown=self.timeout_graceful_shutdown,
                limit_concurrency=None,  # No concurrency limit
                limit_max_requests=None,  # No request limit
            )
            self._server = uvicorn.Server(config)

            # Start with improved error handling
            try:
                async with self._session_manager.run():
                    await self._server.serve()
            except (ClosedResourceError, BrokenPipeError, ConnectionResetError) as e:
                # Client disconnection - this is normal, log at debug level
                self.logger.debug(f"Client disconnected during session: {e}")
                # Server should continue running
                pass
            except asyncio.CancelledError:
                # Server is being shut down - this is normal, don't log as error
                self.logger.info("Server shutdown requested")
                raise  # Re-raise to allow proper cleanup
            except Exception as e:
                self.logger.error(f"Session manager error: {e}", exc_info=True)
                # Fallback to direct server start
                await self._server.serve()

        except Exception as e:
            self.logger.error(f"HTTP server startup failed: {e}")
            raise

    def _create_wrapped_session_manager(self, server):
        """Create a wrapped session manager that handles ClosedResourceError gracefully."""
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        import logging

        # Suppress ClosedResourceError logging from MCP library BEFORE creating session manager
        # This must be done early to prevent the library from logging the error
        class MCPErrorFilter(logging.Filter):
            """Filter to suppress ClosedResourceError from MCP library"""

            def filter(self, record):
                message = record.getMessage()
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
                if hasattr(record, "exc_info") and record.exc_info:
                    exc_type = str(record.exc_info[0])
                    if "ClosedResourceError" in exc_type:
                        return False
                return True

        mcp_loggers = [
            "mcp.server.streamable_http",
            "mcp.server.streamable_http_manager",
            "mcp.server",
        ]
        error_filter = MCPErrorFilter()
        for logger_name in mcp_loggers:
            mcp_logger = logging.getLogger(logger_name)
            # Set to CRITICAL to suppress ERROR level ClosedResourceError messages
            mcp_logger.setLevel(logging.CRITICAL)
            # Also add a filter to catch any that slip through
            mcp_logger.addFilter(error_filter)

        # Create the session manager
        session_manager = StreamableHTTPSessionManager(
            app=server, json_response=True, stateless=True
        )

        # Wrap handle_request to catch and suppress ClosedResourceError
        original_handle_request = session_manager.handle_request

        async def wrapped_handle_request(scope, receive, send):
            try:
                await original_handle_request(scope, receive, send)
            except ClosedResourceError:
                # Client disconnected - this is normal, suppress the error
                self.logger.debug("Client disconnected (ClosedResourceError suppressed)")
                return
            except (BrokenPipeError, ConnectionResetError) as e:
                # Connection errors - also normal for client disconnections
                self.logger.debug(f"Client connection error (suppressed): {e}")
                return

        session_manager.handle_request = wrapped_handle_request
        return session_manager

    def _create_health_endpoints(self):
        """Create ASGI app for health check and security endpoints."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from utils.security import KonfluxDevLakeSecurityManager

        # Create a minimal config object if not provided
        if self.config is None:

            class MinimalConfig:
                allowed_ips = []
                api_keys = {}

            config = MinimalConfig()
        else:
            config = self.config

        security_manager = KonfluxDevLakeSecurityManager(config)

        async def health_check(_request):
            """Health check endpoint."""
            return JSONResponse(
                {
                    "status": "healthy",
                    "service": "konflux-devlake-mcp-server",
                    "transport": "http",
                }
            )

        async def security_stats(_request):
            """Security statistics endpoint."""
            stats = security_manager.get_security_stats()
            return JSONResponse(stats)

        app = Starlette(
            routes=[
                Route("/health", health_check, methods=["GET"]),
                Route("/security/stats", security_stats, methods=["GET"]),
            ]
        )

        return app

    def _create_mcp_app(self, app):
        """Create ASGI app that handles MCP requests with improved error handling."""
        from starlette.responses import Response
        from anyio import ClosedResourceError

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
                        except ClosedResourceError:
                            # Client disconnected - this is normal, just log at debug level
                            self.logger.debug(f"Client disconnected during MCP request: {path}")
                            # Don't send response as connection is already closed
                            return
                        except Exception as e:
                            self.logger.error(f"MCP request handling error: {e}", exc_info=True)
                            # Only send error response if connection is still open
                            try:
                                response = Response(
                                    json.dumps(
                                        {"error": "Internal server error", "details": str(e)}
                                    ),
                                    status_code=500,
                                    media_type="application/json",
                                )
                                await response(scope, receive, send)
                            except (ClosedResourceError, BrokenPipeError, ConnectionResetError):
                                # Connection already closed, can't send response
                                self.logger.debug(
                                    "Connection closed before error response could be sent"
                                )
                        return

                    # 404 for other paths
                    response = Response("Not Found", status_code=404)
                    await response(scope, receive, send)
            except (ClosedResourceError, BrokenPipeError, ConnectionResetError) as e:
                # Client disconnected - this is normal, just log at debug level
                self.logger.debug(f"Client disconnected: {e}")
                # Don't send response as connection is already closed
                return
            except Exception as e:
                self.logger.error(f"ASGI app error: {e}", exc_info=True)
                # Only send error response if connection is still open
                try:
                    response = Response(
                        json.dumps({"error": "Internal server error", "details": str(e)}),
                        status_code=500,
                        media_type="application/json",
                    )
                    await response(scope, receive, send)
                except (ClosedResourceError, BrokenPipeError, ConnectionResetError):
                    # Connection already closed, can't send response
                    self.logger.debug("Connection closed before error response could be sent")

        return mcp_app

    async def stop(self) -> None:
        """Stop the HTTP transport."""
        self.logger.info("Stopping HTTP transport")
        try:
            if self._server:
                self._server.should_exit = True
            if self._session_manager:
                # Gracefully close session manager
                try:
                    # The session manager will be closed when the context exits
                    pass
                except (asyncio.CancelledError, ClosedResourceError):
                    # Ignore cancellation errors during shutdown
                    self.logger.debug("Session manager closed during shutdown")
        except (asyncio.CancelledError, KeyboardInterrupt):
            # Ignore cancellation errors during shutdown
            self.logger.debug("Transport stop interrupted")
        except Exception as e:
            self.logger.error(f"Error stopping transport: {e}")

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
