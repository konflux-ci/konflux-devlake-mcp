#!/usr/bin/env python3
"""
Unit Tests for MCP Server Core Module

Tests the KonfluxDevLakeMCPServer class including initialization,
server info, start, and shutdown behaviors.
"""

import asyncio

import pytest
from unittest.mock import Mock, AsyncMock, patch

from server.core.mcp_server import KonfluxDevLakeMCPServer


@pytest.mark.unit
class TestMCPServerInit:
    """Tests for KonfluxDevLakeMCPServer initialization."""

    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    def test_init_without_oidc(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test initialization when OIDC is not enabled."""
        mock_config.oidc.enabled = False

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        assert server.config is mock_config
        assert server.db_connection is mock_db_connection
        assert server.tools_manager is mock_tools_manager
        assert server.security_manager is mock_security_manager
        assert server.authorization_service is None

        mock_tool_handler_cls.assert_called_once_with(
            mock_tools_manager,
            mock_security_manager,
            authorization_service=None,
            rbac_enabled=False,
        )

    @patch("server.core.mcp_server.AuthorizationService")
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    def test_init_with_oidc(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_auth_service_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test initialization when OIDC is enabled."""
        mock_config.oidc.enabled = True
        mock_auth_instance = Mock()
        mock_auth_service_cls.return_value = mock_auth_instance

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        assert server.authorization_service is mock_auth_instance
        mock_auth_service_cls.assert_called_once()

        mock_tool_handler_cls.assert_called_once_with(
            mock_tools_manager,
            mock_security_manager,
            authorization_service=mock_auth_instance,
            rbac_enabled=True,
        )


@pytest.mark.unit
class TestMCPServerInfo:
    """Tests for KonfluxDevLakeMCPServer get_server_info."""

    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    def test_get_server_info(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test get_server_info returns correct dictionary."""
        mock_config.oidc.enabled = False

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        info = server.get_server_info()

        assert info["server_name"] == "konflux-devlake-mcp-server"
        assert info["version"] == "1.0.0"
        assert info["status"] == "running"
        assert "security_stats" in info
        mock_security_manager.get_security_stats.assert_called()


@pytest.mark.unit
class TestMCPServerStart:
    """Tests for KonfluxDevLakeMCPServer start method."""

    @pytest.mark.asyncio
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    async def test_start_success(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test successful server start with database connection."""
        mock_config.oidc.enabled = False
        mock_db_connection.connect = AsyncMock(return_value={"success": True})
        mock_db_connection.get_connection_info = Mock(
            return_value={"pool_size": 5, "pool_minsize": 1, "pool_maxsize": 10}
        )

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        mock_transport = Mock()
        mock_transport.start = AsyncMock()

        await server.start(mock_transport)

        mock_db_connection.connect.assert_awaited_once()
        mock_db_connection.get_connection_info.assert_called_once()
        mock_transport.start.assert_awaited_once_with(server.server)

    @pytest.mark.asyncio
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    async def test_start_db_failure(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test server start raises ConnectionError on DB failure."""
        mock_config.oidc.enabled = False
        mock_db_connection.connect = AsyncMock(
            return_value={"success": False, "error": "Connection refused"}
        )

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        mock_transport = Mock()
        mock_transport.start = AsyncMock()

        with pytest.raises(ConnectionError, match="Connection refused"):
            await server.start(mock_transport)

        mock_transport.start.assert_not_awaited()


@pytest.mark.unit
class TestMCPServerShutdown:
    """Tests for KonfluxDevLakeMCPServer shutdown method."""

    @pytest.mark.asyncio
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    async def test_shutdown_success(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test successful server shutdown."""
        mock_config.oidc.enabled = False

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        await server.shutdown()

        mock_security_manager.cleanup_expired_tokens.assert_called_once()
        mock_db_connection.close.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    async def test_shutdown_exception(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test shutdown handles exceptions gracefully."""
        mock_config.oidc.enabled = False
        mock_security_manager.cleanup_expired_tokens = Mock(
            side_effect=RuntimeError("cleanup error")
        )

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        await server.shutdown()

    @pytest.mark.asyncio
    @patch("server.core.mcp_server.ToolHandler")
    @patch("server.core.mcp_server.Server")
    async def test_shutdown_cancelled(
        self,
        mock_server_cls,
        mock_tool_handler_cls,
        mock_config,
        mock_db_connection,
        mock_tools_manager,
        mock_security_manager,
    ):
        """Test shutdown handles asyncio.CancelledError gracefully."""
        mock_config.oidc.enabled = False
        mock_security_manager.cleanup_expired_tokens = Mock(
            side_effect=asyncio.CancelledError()
        )

        server = KonfluxDevLakeMCPServer(
            config=mock_config,
            db_connection=mock_db_connection,
            tools_manager=mock_tools_manager,
            security_manager=mock_security_manager,
        )

        await server.shutdown()
