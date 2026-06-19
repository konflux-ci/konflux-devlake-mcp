#!/usr/bin/env python3
"""
Unit Tests for Server Factory Module

Tests the ServerFactory class including transport creation, configuration
validation, server info, and server creation.
"""

import pytest
from unittest.mock import Mock, patch

from server.factory.server_factory import ServerFactory
from server.transport.stdio_transport import StdioTransport
from server.transport.http_transport import HttpTransport


@pytest.mark.unit
class TestServerFactoryTransport:
    """Tests for ServerFactory transport creation."""

    def test_create_transport_stdio(self):
        """Test creating a stdio transport."""
        factory = ServerFactory()
        transport = factory.create_transport("stdio")

        assert isinstance(transport, StdioTransport)

    def test_create_transport_http(self):
        """Test creating an http transport with correct params."""
        factory = ServerFactory()
        mock_config = Mock()
        transport = factory.create_transport(
            "http",
            host="10.0.0.1",
            port=8080,
            timeout_keep_alive=500,
            timeout_graceful_shutdown=90,
            config=mock_config,
        )

        assert isinstance(transport, HttpTransport)
        assert transport.host == "10.0.0.1"
        assert transport.port == 8080
        assert transport.timeout_keep_alive == 500
        assert transport.timeout_graceful_shutdown == 90
        assert transport.config is mock_config

    def test_create_transport_http_defaults(self):
        """Test creating an http transport uses factory defaults."""
        factory = ServerFactory()
        transport = factory.create_transport("http")

        assert isinstance(transport, HttpTransport)
        assert transport.host == "0.0.0.0"
        assert transport.port == 3000
        assert transport.timeout_keep_alive == 300
        assert transport.timeout_graceful_shutdown == 60

    def test_create_transport_invalid(self):
        """Test creating an invalid transport raises ValueError."""
        factory = ServerFactory()

        with pytest.raises(ValueError, match="Unsupported transport type"):
            factory.create_transport("websocket")


@pytest.mark.unit
class TestServerFactoryValidation:
    """Tests for ServerFactory configuration validation."""

    def test_validate_configuration_valid(self, mock_config):
        """Test validation returns True for valid config."""
        factory = ServerFactory()

        result = factory.validate_configuration(mock_config)
        assert result is True

    def test_validate_configuration_invalid(self, mock_config):
        """Test validation returns False when config.validate() fails."""
        factory = ServerFactory()
        mock_config.database.host = ""
        mock_config.database.user = ""

        result = factory.validate_configuration(mock_config)
        assert result is False

    def test_validate_configuration_no_host(self, mock_config):
        """Test validation returns False when database host is missing."""
        factory = ServerFactory()
        mock_config.database.host = ""

        result = factory.validate_configuration(mock_config)
        assert result is False

    def test_validate_configuration_no_user(self, mock_config):
        """Test validation returns False when database user is missing."""
        factory = ServerFactory()
        mock_config.database.user = ""

        result = factory.validate_configuration(mock_config)
        assert result is False


@pytest.mark.unit
class TestServerFactoryInfo:
    """Tests for ServerFactory get_server_info."""

    def test_get_server_info(self, mock_config):
        """Test get_server_info returns correct dictionary."""
        factory = ServerFactory()

        info = factory.get_server_info(mock_config)

        assert info["server_name"] == "konflux-devlake-mcp-server"
        assert info["version"] == "1.0.0"
        assert info["transport"] == mock_config.server.transport
        assert info["host"] == mock_config.server.host
        assert info["port"] == mock_config.server.port
        assert info["database_host"] == mock_config.database.host
        assert info["database_port"] == mock_config.database.port
        assert info["database_name"] == mock_config.database.database
        assert info["log_level"] == mock_config.logging.level


@pytest.mark.unit
class TestServerFactoryCreateServer:
    """Tests for ServerFactory create_server."""

    @patch("server.factory.server_factory.KonfluxDevLakeMCPServer")
    @patch("server.factory.server_factory.KonfluxDevLakeSecurityManager")
    @patch("server.factory.server_factory.KonfluxDevLakeToolsManager")
    @patch("server.factory.server_factory.KonfluxDevLakeConnection")
    def test_create_server(
        self,
        mock_conn_cls,
        mock_tools_cls,
        mock_sec_cls,
        mock_server_cls,
        mock_config,
    ):
        """Test create_server creates server with all dependencies."""
        mock_conn_instance = Mock()
        mock_conn_cls.return_value = mock_conn_instance

        mock_tools_instance = Mock()
        mock_tools_cls.return_value = mock_tools_instance

        mock_sec_instance = Mock()
        mock_sec_cls.return_value = mock_sec_instance

        mock_server_instance = Mock()
        mock_server_cls.return_value = mock_server_instance

        factory = ServerFactory()
        result = factory.create_server(mock_config)

        mock_conn_cls.assert_called_once_with(mock_config.get_database_config())
        mock_tools_cls.assert_called_once_with(mock_conn_instance)
        mock_sec_cls.assert_called_once_with(mock_config)

        mock_server_cls.assert_called_once_with(
            config=mock_config,
            db_connection=mock_conn_instance,
            tools_manager=mock_tools_instance,
            security_manager=mock_sec_instance,
        )

        assert result is mock_server_instance
