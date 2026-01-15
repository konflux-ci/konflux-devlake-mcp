#!/usr/bin/env python3
"""
Authentication Middleware for MCP Server

This module provides ASGI middleware for authenticating requests
using OIDC tokens from Red Hat SSO / Keycloak.
"""

from typing import Any, Callable, Dict, Optional

from starlette.responses import JSONResponse

from server.middleware.oidc_auth import OIDCAuthenticator, OIDCConfig
from utils.logger import get_logger


class AuthMiddleware:
    """
    ASGI Authentication Middleware.

    This middleware intercepts incoming requests and validates
    OIDC tokens before passing requests to the main application.
    """

    def __init__(
        self,
        app: Callable,
        oidc_config: OIDCConfig,
    ):
        """
        Initialize the authentication middleware.

        Args:
            app: The ASGI application to wrap
            oidc_config: OIDC configuration
        """
        self.app = app
        self.oidc_config = oidc_config
        self.authenticator = OIDCAuthenticator(oidc_config)
        self.logger = get_logger(f"{__name__}.AuthMiddleware")

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """
        Process incoming ASGI requests.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip authentication if OIDC is not enabled
        if not self.authenticator.is_enabled():
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip authentication for configured paths
        if self.authenticator.should_skip_auth(path):
            self.logger.debug(f"Skipping auth for path: {path}")
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        # Authenticate the request
        result = await self.authenticator.authenticate_request(auth_header)

        if not result.authenticated:
            self.logger.warning(
                f"Authentication failed for {path}: {result.error}",
                extra={
                    "path": path,
                    "error": result.error,
                    "status_code": result.status_code,
                },
            )

            # Send error response
            response = JSONResponse(
                content={
                    "error": "authentication_failed",
                    "message": result.error,
                },
                status_code=result.status_code,
                headers={
                    "WWW-Authenticate": 'Bearer realm="konflux-devlake-mcp"',
                },
            )
            await response(scope, receive, send)
            return

        # Add user info to scope for downstream handlers
        scope["user"] = {
            "id": result.user_id,
            "username": result.username,
            "email": result.email,
            "groups": result.groups,
            "scopes": result.scopes,
        }

        self.logger.debug(
            f"Authenticated request from user: {result.username}",
            extra={
                "path": path,
                "user_id": result.user_id,
                "username": result.username,
            },
        )

        # Pass request to the application
        await self.app(scope, receive, send)


def create_auth_middleware(
    app: Callable,
    config: Optional[Any] = None,
) -> Callable:
    """
    Create authentication middleware from configuration.

    Args:
        app: The ASGI application to wrap
        config: Configuration object with OIDC settings

    Returns:
        ASGI middleware callable
    """
    logger = get_logger(__name__)

    # Extract OIDC config from main config object
    if config is not None and hasattr(config, "oidc"):
        oidc_config = OIDCConfig(
            enabled=config.oidc.enabled,
            issuer_url=config.oidc.issuer_url,
            client_id=config.oidc.client_id,
            required_scopes=config.oidc.required_scopes,
            jwks_cache_ttl=config.oidc.jwks_cache_ttl,
            skip_paths=config.oidc.skip_paths,
            verify_ssl=config.oidc.verify_ssl,
        )

        if oidc_config.enabled:
            logger.info(f"OIDC authentication enabled with issuer: {oidc_config.issuer_url}")
            return AuthMiddleware(app, oidc_config)
        else:
            logger.info("OIDC authentication is disabled")
    else:
        logger.info("No OIDC configuration provided, authentication disabled")

    # Return the original app if OIDC is not enabled
    return app
