#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Main Entry Point

MCP server providing natural language access to Konflux DevLake databases.
Supports incident analysis, deployment tracking, and database operations.

Features:
- HTTP/STDIO transport protocols
- Incident analysis with filtering and deduplication
- Deployment tracking and analytics
- Database connectivity and querying
- SQL injection protection
- Comprehensive logging

Usage:
    python konflux-devlake-mcp.py --transport http --host 0.0.0.0 --port 3000 \\
                                  --db-host localhost --db-user root --db-password password \\
                                  --db-database lake
"""

import sys
import os
import asyncio
import logging
import argparse

from server.factory.server_factory import ServerFactory
from utils.config import KonfluxDevLakeConfig
from utils.logger import get_logger, log_system_info, shutdown_logging

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser with all server configuration options.

    Returns:
        Configured ArgumentParser with transport, server, database, and logging options
    """
    parser = argparse.ArgumentParser(
        description="Konflux DevLake MCP Server - Database Querying Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  HTTP Mode (Production):
    python konflux-devlake-mcp.py --transport http --host 0.0.0.0 --port 3000 \
      --db-host localhost --db-user root --db-password password --db-database lake
  STDIO Mode (Development):
    python konflux-devlake-mcp.py --transport stdio --db-host localhost \
      --db-user root --db-password password
  Debug Mode:
    python konflux-devlake-mcp.py --transport http --log-level DEBUG \
      --db-host localhost --db-user root --db-password password
        """,
    )

    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default="http",
        help="Transport protocol: 'stdio' for local development (direct communication), "
        "'http' for production server (network accessible)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="HTTP server host address (default: 0.0.0.0 for all network interfaces). "
        "Use '127.0.0.1' for localhost only, '0.0.0.0' for all interfaces",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="HTTP server port number (default: 3000). Must be available and not in use. "
        "Common alternatives: 8080, 8000, 5000",
    )

    # Database Connection Configuration
    parser.add_argument(
        "--db-host",
        type=str,
        default="localhost",
        help="Database server hostname or IP address (default: localhost). "
        "For remote databases, use the actual server address",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=3306,
        help="Database server port number (default: 3306 for MySQL). "
        "Use 5432 for PostgreSQL, 1433 for SQL Server",
    )
    parser.add_argument(
        "--db-user",
        type=str,
        default="root",
        help="Database username for authentication (default: root). "
        "Must have appropriate permissions to access DevLake tables",
    )
    parser.add_argument(
        "--db-password",
        type=str,
        default="",
        help="Database password for authentication (default: empty). "
        "For security, consider using environment variables or config files",
    )
    parser.add_argument(
        "--db-database",
        type=str,
        default="",
        help="Default database name to connect to (default: empty). "
        "Usually 'lake' for DevLake installations. Leave empty for auto-detection",
    )

    # Logging Configuration
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity level (default: INFO). "
        "DEBUG: Detailed debug info, INFO: General operations, "
        "WARNING: Only warnings and errors, ERROR: Only errors",
    )

    return parser


def create_config(args: argparse.Namespace) -> KonfluxDevLakeConfig:
    """
    Create server configuration from command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        KonfluxDevLakeConfig object with all server settings
    """
    config = KonfluxDevLakeConfig()

    config.database.host = args.db_host
    config.database.port = args.db_port
    config.database.user = args.db_user
    config.database.password = args.db_password
    config.database.database = args.db_database

    config.server.transport = args.transport
    config.server.host = args.host
    config.server.port = args.port

    config.logging.level = args.log_level
    logging.getLogger().setLevel(getattr(logging, config.logging.level))

    return config


def validate_config(config: KonfluxDevLakeConfig) -> bool:
    """
    Validate server configuration for required settings.
    """
    logger = get_logger(__name__)

    if not config.database.host:
        logger.error("Database host is required - specify with --db-host")
        return False
    if not config.database.user:
        logger.error("Database user is required - specify with --db-user")
        return False

    logger.info("Configuration validation passed")
    return True


async def run_server(config: KonfluxDevLakeConfig) -> int:
    """
    Start and run the MCP server with the given configuration.

    Creates server factory, initializes transport layer, and starts the server.
    Handles graceful shutdown on interruption.
    """
    logger = get_logger(__name__)
    server_factory = ServerFactory()
    server = None
    transport = None

    try:
        logger.info("Starting Konflux DevLake MCP Server")
        log_system_info()

        server = server_factory.create_server(config)
        transport_kwargs = (
            {"host": config.server.host, "port": config.server.port}
            if config.server.transport == "http"
            else {}
        )
        transport = server_factory.create_transport(config.server.transport, **transport_kwargs)

        logger.info(f"Server created with {config.server.transport} transport")
        await server.start(transport)
        return 0

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        return 0
    except Exception as e:
        logger.error(f"Server runtime error: {e}")
        return 1
    finally:
        logger.info("Shutting down server")
        try:
            if server:
                await server.shutdown()
            if transport:
                await transport.stop()
            shutdown_logging()
            logger.info("Server shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


async def main():
    """Main application entry point."""
    parser = create_parser()
    args = parser.parse_args()

    config = create_config(args)
    if not validate_config(config):
        return 1

    return await run_server(config)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
