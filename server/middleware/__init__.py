#!/usr/bin/env python3
"""
Server Middleware Package

This package contains middleware components for the MCP server,
including authentication and authorization.
"""

from server.middleware.oidc_auth import OIDCAuthenticator, OIDCConfig
from server.middleware.auth_middleware import AuthMiddleware, create_auth_middleware

__all__ = ["OIDCAuthenticator", "OIDCConfig", "AuthMiddleware", "create_auth_middleware"]
