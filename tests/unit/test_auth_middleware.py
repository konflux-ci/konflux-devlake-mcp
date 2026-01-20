#!/usr/bin/env python3
"""
Unit Tests for Authentication Middleware

Tests for server/middleware/auth_middleware.py
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from server.middleware.auth_middleware import (
    AuthMiddleware,
    create_auth_middleware,
)
from server.middleware.oidc_auth import AuthResult, OIDCConfig


class TestAuthMiddleware:
    """Tests for AuthMiddleware class."""

    @pytest.mark.asyncio
    async def test_non_http_requests_pass_through(self):
        """Test that non-HTTP requests pass through without authentication."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_disabled_oidc_passes_through(self):
        """Test that requests pass through when OIDC is disabled."""
        config = OIDCConfig(enabled=False)

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {"type": "http", "path": "/mcp", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_health_path_skips_auth(self):
        """Test that health paths skip authentication."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            skip_paths=["/health", "/security"],
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {"type": "http", "path": "/health", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        """Test that missing Authorization header returns 401."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {"type": "http", "path": "/mcp", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # App should not be called
        app.assert_not_called()

        # Verify response was sent (401)
        assert send.call_count > 0

    @pytest.mark.asyncio
    async def test_successful_auth_passes_to_app(self):
        """Test that successful authentication passes request to app."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer valid.token.here")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Mock successful authentication
        mock_result = AuthResult(
            authenticated=True,
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            groups=["developers"],
            scopes=["openid"],
            status_code=200,
        )

        with patch.object(
            middleware.authenticator,
            "authenticate_request",
            return_value=mock_result,
        ):
            await middleware(scope, receive, send)

        # App should be called
        app.assert_called_once()

        # Verify user info was added to scope
        call_scope = app.call_args[0][0]
        assert "user" in call_scope
        assert call_scope["user"]["id"] == "user-123"
        assert call_scope["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """Test that invalid token returns 401."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer invalid.token")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Mock failed authentication
        mock_result = AuthResult(
            authenticated=False,
            error="Token has expired",
            status_code=401,
        )

        with patch.object(
            middleware.authenticator,
            "authenticate_request",
            return_value=mock_result,
        ):
            await middleware(scope, receive, send)

        # App should not be called
        app.assert_not_called()

        # Verify response was sent
        assert send.call_count > 0

    @pytest.mark.asyncio
    async def test_insufficient_scopes_returns_403(self):
        """Test that insufficient scopes returns 403."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            required_scopes=["admin"],
        )

        app = AsyncMock()
        middleware = AuthMiddleware(app, config)

        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer valid.token")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Mock authentication with insufficient scopes
        mock_result = AuthResult(
            authenticated=False,
            error="Missing required scopes: {'admin'}",
            status_code=403,
        )

        with patch.object(
            middleware.authenticator,
            "authenticate_request",
            return_value=mock_result,
        ):
            await middleware(scope, receive, send)

        # App should not be called
        app.assert_not_called()


class TestCreateAuthMiddleware:
    """Tests for create_auth_middleware function."""

    def test_returns_original_app_when_no_config(self):
        """Test that original app is returned when no config provided."""
        app = AsyncMock()

        result = create_auth_middleware(app, None)

        assert result is app

    def test_returns_original_app_when_oidc_disabled(self):
        """Test that original app is returned when OIDC is disabled."""
        app = AsyncMock()

        # Create a mock config with disabled OIDC
        config = MagicMock()
        config.oidc = MagicMock()
        config.oidc.enabled = False

        result = create_auth_middleware(app, config)

        assert result is app

    def test_returns_middleware_when_oidc_enabled(self):
        """Test that AuthMiddleware is returned when OIDC is enabled."""
        app = AsyncMock()

        # Create a mock config with enabled OIDC
        config = MagicMock()
        config.oidc = MagicMock()
        config.oidc.enabled = True
        config.oidc.issuer_url = "https://sso.example.com/realms/test"
        config.oidc.client_id = "mcp-server"
        config.oidc.required_scopes = []
        config.oidc.jwks_cache_ttl = 3600
        config.oidc.skip_paths = ["/health"]
        config.oidc.verify_ssl = True

        result = create_auth_middleware(app, config)

        assert isinstance(result, AuthMiddleware)

    def test_returns_original_app_when_config_has_no_oidc_attr(self):
        """Test that original app is returned when config has no oidc attribute."""
        app = AsyncMock()

        # Create a config without oidc attribute
        config = MagicMock(spec=[])

        result = create_auth_middleware(app, config)

        assert result is app
