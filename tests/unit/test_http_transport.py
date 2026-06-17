#!/usr/bin/env python3
"""
Unit Tests for HTTP Transport Module

Tests the HttpTransport class including initialization, transport info,
stop behavior, health endpoints, MCP app routing, and error handling.
"""

import json

import pytest
from unittest.mock import Mock, AsyncMock, patch

from server.transport.http_transport import HttpTransport


@pytest.mark.unit
class TestHttpTransportInit:
    """Tests for HttpTransport initialization."""

    def test_init_defaults(self):
        """Test HttpTransport initializes with correct default values."""
        transport = HttpTransport()
        assert transport.host == "0.0.0.0"
        assert transport.port == 3000
        assert transport.timeout_keep_alive == 600
        assert transport.timeout_graceful_shutdown == 120
        assert transport.config is None
        assert transport._session_manager is None
        assert transport._server is None

    def test_init_custom(self):
        """Test HttpTransport initializes with custom values."""
        mock_config = Mock()
        transport = HttpTransport(
            host="127.0.0.1",
            port=8080,
            timeout_keep_alive=300,
            timeout_graceful_shutdown=60,
            config=mock_config,
        )
        assert transport.host == "127.0.0.1"
        assert transport.port == 8080
        assert transport.timeout_keep_alive == 300
        assert transport.timeout_graceful_shutdown == 60
        assert transport.config is mock_config


@pytest.mark.unit
class TestHttpTransportInfo:
    """Tests for HttpTransport get_transport_info."""

    def test_get_transport_info(self):
        """Test get_transport_info returns correct dictionary."""
        transport = HttpTransport(host="10.0.0.1", port=9090)
        info = transport.get_transport_info()

        assert info["type"] == "http"
        assert info["host"] == "10.0.0.1"
        assert info["port"] == 9090
        assert "description" in info
        assert "capabilities" in info
        assert "remote_access" in info["capabilities"]
        assert "production_deployment" in info["capabilities"]


@pytest.mark.unit
class TestHttpTransportStop:
    """Tests for HttpTransport stop method."""

    @pytest.mark.asyncio
    async def test_stop_with_server(self):
        """Test stop sets should_exit on the server."""
        transport = HttpTransport()
        mock_server = Mock()
        mock_server.should_exit = False
        transport._server = mock_server
        transport._session_manager = None

        await transport.stop()
        assert mock_server.should_exit is True

    @pytest.mark.asyncio
    async def test_stop_without_server(self):
        """Test stop when no server is set does not raise."""
        transport = HttpTransport()
        transport._server = None
        transport._session_manager = None

        await transport.stop()

    @pytest.mark.asyncio
    async def test_stop_with_session_manager(self):
        """Test stop with session_manager set does not raise."""
        transport = HttpTransport()
        mock_server = Mock()
        mock_server.should_exit = False
        transport._server = mock_server
        transport._session_manager = Mock()

        await transport.stop()
        assert mock_server.should_exit is True

    @pytest.mark.asyncio
    async def test_stop_exception(self):
        """Test stop handles exception gracefully."""
        transport = HttpTransport()

        class FailingServer:
            @property
            def should_exit(self):
                return False

            @should_exit.setter
            def should_exit(self, value):
                raise RuntimeError("stop error")

        transport._server = FailingServer()

        # Should not raise -- exception is caught internally
        await transport.stop()


@pytest.mark.unit
class TestHttpTransportHealthEndpoints:
    """Tests for HttpTransport _create_health_endpoints."""

    @pytest.mark.asyncio
    @patch("utils.security.KonfluxDevLakeSecurityManager")
    async def test_create_health_endpoints_health_route(self, mock_sec_cls):
        """Test /health endpoint returns healthy status."""
        mock_sec_instance = Mock()
        mock_sec_instance.get_security_stats.return_value = {"active_api_keys": 0}
        mock_sec_cls.return_value = mock_sec_instance

        transport = HttpTransport()
        app = transport._create_health_endpoints()

        scope = {
            "type": "http",
            "path": "/health",
            "method": "GET",
            "headers": [],
            "query_string": b"",
            "root_path": "",
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        send_responses = []

        async def mock_send(message):
            send_responses.append(message)

        await app(scope, mock_receive, mock_send)

        assert len(send_responses) >= 2
        start_msg = send_responses[0]
        assert start_msg["type"] == "http.response.start"
        assert start_msg["status"] == 200

        body_msg = send_responses[1]
        assert body_msg["type"] == "http.response.body"
        body = json.loads(body_msg["body"])
        assert body["status"] == "healthy"
        assert body["service"] == "konflux-devlake-mcp-server"
        assert body["transport"] == "http"

    @pytest.mark.asyncio
    @patch("utils.security.KonfluxDevLakeSecurityManager")
    async def test_create_health_endpoints_security_stats(self, mock_sec_cls):
        """Test /security/stats endpoint returns security stats."""
        mock_sec_instance = Mock()
        mock_sec_instance.get_security_stats.return_value = {
            "active_api_keys": 2,
            "active_session_tokens": 1,
        }
        mock_sec_cls.return_value = mock_sec_instance

        transport = HttpTransport()
        app = transport._create_health_endpoints()

        scope = {
            "type": "http",
            "path": "/security/stats",
            "method": "GET",
            "headers": [],
            "query_string": b"",
            "root_path": "",
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        send_responses = []

        async def mock_send(message):
            send_responses.append(message)

        await app(scope, mock_receive, mock_send)

        assert len(send_responses) >= 2
        start_msg = send_responses[0]
        assert start_msg["status"] == 200

        body_msg = send_responses[1]
        body = json.loads(body_msg["body"])
        assert body["active_api_keys"] == 2
        assert body["active_session_tokens"] == 1

    @pytest.mark.asyncio
    @patch("utils.security.KonfluxDevLakeSecurityManager")
    async def test_create_health_endpoints_no_config(self, mock_sec_cls):
        """Test health endpoints creation when config is None uses MinimalConfig."""
        mock_sec_instance = Mock()
        mock_sec_instance.get_security_stats.return_value = {}
        mock_sec_cls.return_value = mock_sec_instance

        transport = HttpTransport(config=None)
        transport._create_health_endpoints()

        call_args = mock_sec_cls.call_args[0][0]
        assert hasattr(call_args, "allowed_ips")
        assert hasattr(call_args, "api_keys")
        assert call_args.allowed_ips == []
        assert call_args.api_keys == {}


@pytest.mark.unit
class TestHttpTransportMCPApp:
    """Tests for HttpTransport _create_mcp_app."""

    def _make_transport_with_session_manager(self):
        """Helper to create transport with a mock session manager."""
        transport = HttpTransport()
        transport._session_manager = Mock()
        transport._session_manager.handle_request = AsyncMock()
        return transport

    @pytest.mark.asyncio
    async def test_create_mcp_app_health_route(self):
        """Test MCP app routes /health to health app."""
        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/health",
            "method": "GET",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)

        health_app.assert_called_once_with(scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_create_mcp_app_security_route(self):
        """Test MCP app routes /security paths to health app."""
        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/security/stats",
            "method": "GET",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)
        health_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_mcp_app_mcp_route(self):
        """Test MCP app routes /mcp to session manager."""
        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/mcp",
            "method": "POST",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)

        transport._session_manager.handle_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_mcp_app_mcp_subpath(self):
        """Test MCP app routes /mcp/messages to session manager."""
        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/mcp/messages",
            "method": "POST",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)
        transport._session_manager.handle_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_mcp_app_404(self):
        """Test MCP app returns 404 for unknown paths."""
        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/unknown",
            "method": "GET",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        send_responses = []

        async def mock_send(message):
            send_responses.append(message)

        await mcp_app(scope, mock_receive, mock_send)

        start_msg = send_responses[0]
        assert start_msg["type"] == "http.response.start"
        assert start_msg["status"] == 404

    @pytest.mark.asyncio
    async def test_create_mcp_app_client_disconnect(self):
        """Test MCP app handles ClosedResourceError on /mcp route."""
        from anyio import ClosedResourceError

        transport = self._make_transport_with_session_manager()
        transport._session_manager.handle_request = AsyncMock(
            side_effect=ClosedResourceError()
        )

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/mcp",
            "method": "POST",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_create_mcp_app_outer_closed_resource_error(self):
        """Test MCP app handles ClosedResourceError at the outer level."""
        from anyio import ClosedResourceError

        transport = self._make_transport_with_session_manager()

        health_app = AsyncMock(side_effect=ClosedResourceError())
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/health",
            "method": "GET",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        async def mock_send(message):
            pass

        await mcp_app(scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_create_mcp_app_mcp_internal_error(self):
        """Test MCP app handles generic exception on /mcp route."""
        transport = self._make_transport_with_session_manager()
        transport._session_manager.handle_request = AsyncMock(
            side_effect=RuntimeError("internal error")
        )

        health_app = AsyncMock()
        mcp_app = transport._create_mcp_app(health_app)

        scope = {
            "type": "http",
            "path": "/mcp",
            "method": "POST",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }

        async def mock_receive():
            return {"type": "http.request", "body": b""}

        send_responses = []

        async def mock_send(message):
            send_responses.append(message)

        await mcp_app(scope, mock_receive, mock_send)

        start_msg = send_responses[0]
        assert start_msg["type"] == "http.response.start"
        assert start_msg["status"] == 500


@pytest.mark.unit
class TestHttpTransportWrappedSessionManager:
    """Tests for HttpTransport _create_wrapped_session_manager."""

    def test_create_wrapped_session_manager(self):
        """Test _create_wrapped_session_manager wraps the session manager."""
        transport = HttpTransport()
        mock_server = Mock()

        with patch(
            "mcp.server.streamable_http_manager.StreamableHTTPSessionManager"
        ) as mock_sm_cls:
            mock_sm_instance = Mock()
            mock_sm_instance.handle_request = AsyncMock()
            mock_sm_cls.return_value = mock_sm_instance

            result = transport._create_wrapped_session_manager(mock_server)

            mock_sm_cls.assert_called_once_with(
                app=mock_server, json_response=True, stateless=True
            )
            assert result is mock_sm_instance

    @pytest.mark.asyncio
    async def test_wrapped_handle_request_suppresses_closed_resource_error(self):
        """Test wrapped handle_request catches ClosedResourceError."""
        from anyio import ClosedResourceError

        transport = HttpTransport()
        mock_server = Mock()

        with patch(
            "mcp.server.streamable_http_manager.StreamableHTTPSessionManager"
        ) as mock_sm_cls:
            mock_sm_instance = Mock()
            mock_sm_instance.handle_request = AsyncMock(
                side_effect=ClosedResourceError()
            )
            mock_sm_cls.return_value = mock_sm_instance

            result = transport._create_wrapped_session_manager(mock_server)

            await result.handle_request({}, AsyncMock(), AsyncMock())

    @pytest.mark.asyncio
    async def test_wrapped_handle_request_suppresses_broken_pipe(self):
        """Test wrapped handle_request catches BrokenPipeError."""
        transport = HttpTransport()
        mock_server = Mock()

        with patch(
            "mcp.server.streamable_http_manager.StreamableHTTPSessionManager"
        ) as mock_sm_cls:
            mock_sm_instance = Mock()
            mock_sm_instance.handle_request = AsyncMock(
                side_effect=BrokenPipeError("broken pipe")
            )
            mock_sm_cls.return_value = mock_sm_instance

            result = transport._create_wrapped_session_manager(mock_server)

            await result.handle_request({}, AsyncMock(), AsyncMock())

    @pytest.mark.asyncio
    async def test_wrapped_handle_request_success(self):
        """Test wrapped handle_request passes through on success."""
        transport = HttpTransport()
        mock_server = Mock()

        with patch(
            "mcp.server.streamable_http_manager.StreamableHTTPSessionManager"
        ) as mock_sm_cls:
            original_handle = AsyncMock(return_value=None)
            mock_sm_instance = Mock()
            mock_sm_instance.handle_request = original_handle
            mock_sm_cls.return_value = mock_sm_instance

            result = transport._create_wrapped_session_manager(mock_server)

            scope = {"type": "http"}
            receive = AsyncMock()
            send = AsyncMock()
            await result.handle_request(scope, receive, send)

            original_handle.assert_called_once_with(scope, receive, send)
