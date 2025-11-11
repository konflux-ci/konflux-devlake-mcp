#!/usr/bin/env python3
"""
Server Factory

This module provides a factory pattern for creating and configuring MCP servers
with different transport layers and configurations.
"""

from server.core.mcp_server import KonfluxDevLakeMCPServer
from server.transport.base_transport import BaseTransport
from server.transport.stdio_transport import StdioTransport
from server.transport.http_transport import HttpTransport
from tools.tools_manager import KonfluxDevLakeToolsManager
from utils.config import KonfluxDevLakeConfig
from utils.db import KonfluxDevLakeConnection
from utils.security import KonfluxDevLakeSecurityManager
from utils.logger import get_logger


class ServerFactory:
    """
    Factory for creating and configuring MCP servers.

    This class provides a centralized way to create MCP servers with different
    configurations and transport layers, ensuring proper initialization and
    dependency injection.
    """

    def __init__(self):
        """Initialize the server factory."""
        self.logger = get_logger(f"{__name__}.ServerFactory")

    def create_server(self, config: KonfluxDevLakeConfig) -> KonfluxDevLakeMCPServer:
        """
        Create a fully configured MCP server.

        Args:
            config: Server configuration object

        Returns:
            Configured MCP server instance
        """
        self.logger.info("Creating MCP server with configuration")

        # Create database connection
        db_connection = KonfluxDevLakeConnection(config.get_database_config())

        # Create tools manager
        tools_manager = KonfluxDevLakeToolsManager(db_connection)

        # Create security manager
        security_manager = KonfluxDevLakeSecurityManager(config)

        # Create and return the MCP server
        server = KonfluxDevLakeMCPServer(
            config=config,
            db_connection=db_connection,
            tools_manager=tools_manager,
            security_manager=security_manager,
        )

        self.logger.info("MCP server created successfully")
        return server

    def create_transport(self, transport_type: str, **kwargs) -> BaseTransport:
        """
        Create a transport layer based on the specified type.

        Args:
            transport_type: Type of transport to create ("stdio" or "http")
            **kwargs: Additional arguments for transport configuration

        Returns:
            Configured transport instance

        Raises:
            ValueError: If transport type is not supported
        """
        self.logger.info(f"Creating transport layer: {transport_type}")

        if transport_type == "stdio":
            return StdioTransport()
        elif transport_type == "http":
            host = kwargs.get("host", "0.0.0.0")
            port = kwargs.get("port", 3000)
            return HttpTransport(host=host, port=port)
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    def validate_configuration(self, config: KonfluxDevLakeConfig) -> bool:
        """
        Validate server configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid, False otherwise
        """
        self.logger.info("Validating server configuration")

        if not config.validate():
            self.logger.error("Configuration validation failed")
            return False

        # Additional validation specific to our server
        if not config.database.host:
            self.logger.error("Database host is required")
            return False

        if not config.database.user:
            self.logger.error("Database user is required")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def get_server_info(self, config: KonfluxDevLakeConfig) -> dict:
        """
        Get server information for logging and monitoring.

        Args:
            config: Server configuration

        Returns:
            Dictionary containing server information
        """
        return {
            "server_name": "konflux-devlake-mcp-server",
            "version": "1.0.0",
            "transport": config.server.transport,
            "host": config.server.host,
            "port": config.server.port,
            "database_host": config.database.host,
            "database_port": config.database.port,
            "database_name": config.database.database,
            "log_level": config.logging.level,
        }
