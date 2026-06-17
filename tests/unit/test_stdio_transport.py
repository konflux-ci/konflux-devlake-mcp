#!/usr/bin/env python3
"""
Unit Tests for STDIO Transport Module

Tests the StdioTransport class including initialization, transport info,
stop behavior, and start method.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from contextlib import asynccontextmanager

from server.transport.stdio_transport import StdioTransport


@pytest.mark.unit
class TestStdioTransportInit:
    """Tests for StdioTransport initialization."""

    def test_init(self):
        """Test StdioTransport initializes correctly."""
        transport = StdioTransport()
        assert transport._server is None
        assert hasattr(transport, "logger")


@pytest.mark.unit
class TestStdioTransportInfo:
    """Tests for StdioTransport get_transport_info."""

    def test_get_transport_info(self):
        """Test get_transport_info returns correct dictionary."""
        transport = StdioTransport()
        info = transport.get_transport_info()

        assert info["type"] == "stdio"
        assert "description" in info
        assert "capabilities" in info
        assert "local_development" in info["capabilities"]
        assert "testing" in info["capabilities"]


@pytest.mark.unit
class TestStdioTransportStop:
    """Tests for StdioTransport stop method."""

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stop is a no-op and does not raise."""
        transport = StdioTransport()
        await transport.stop()


@pytest.mark.unit
class TestStdioTransportStart:
    """Tests for StdioTransport start method."""

    @pytest.mark.asyncio
    @patch("mcp.server.stdio.stdio_server")
    async def test_start(self, mock_stdio_server):
        """Test start uses stdio_server context manager and runs the server."""
        transport = StdioTransport()

        mock_read_stream = Mock()
        mock_write_stream = Mock()

        @asynccontextmanager
        async def fake_stdio_server():
            yield (mock_read_stream, mock_write_stream)

        mock_stdio_server.side_effect = fake_stdio_server

        mock_server = Mock()
        mock_server.run = AsyncMock()

        await transport.start(mock_server)

        mock_server.run.assert_awaited_once()
        call_args = mock_server.run.call_args
        assert call_args[0][0] is mock_read_stream
        assert call_args[0][1] is mock_write_stream
        init_options = call_args[0][2]
        assert init_options.server_name == "konflux-devlake-mcp-server"
        assert init_options.server_version == "1.0.0"

    @pytest.mark.asyncio
    @patch("mcp.server.stdio.stdio_server")
    async def test_start_exception(self, mock_stdio_server):
        """Test start raises exception on failure."""
        transport = StdioTransport()

        @asynccontextmanager
        async def failing_stdio_server():
            raise RuntimeError("stdio failure")
            yield

        mock_stdio_server.side_effect = failing_stdio_server

        mock_server = Mock()
        mock_server.run = AsyncMock()

        with pytest.raises(RuntimeError, match="stdio failure"):
            await transport.start(mock_server)
