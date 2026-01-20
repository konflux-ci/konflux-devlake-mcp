#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Configuration Utility
"""

import os


class DatabaseConfig:
    """Database configuration"""

    def __init__(
        self,
        host="localhost",
        port=3306,
        user="root",
        password="",
        database="",
        connect_timeout=60,
        read_timeout=600,
        write_timeout=120,
        pool_min_size=5,
        pool_max_size=50,
        pool_recycle=300,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        # Connection pool settings for multi-user concurrent access
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        self.pool_recycle = pool_recycle


class ServerConfig:
    """Server configuration"""

    def __init__(
        self,
        transport="stdio",
        host="0.0.0.0",
        port=3000,
        timeout_keep_alive=3600,
        timeout_graceful_shutdown=300,
    ):
        self.transport = transport
        self.host = host
        self.port = port
        # Keep-alive timeout for SSE/long-lived connections (1 hour default)
        self.timeout_keep_alive = timeout_keep_alive
        self.timeout_graceful_shutdown = timeout_graceful_shutdown


class LoggingConfig:
    """Logging configuration"""

    def __init__(self, level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"):
        self.level = level
        self.format = format


class OIDCConfig:
    """OIDC authentication configuration for Red Hat SSO / Keycloak"""

    def __init__(
        self,
        enabled=False,
        issuer_url="",
        client_id="",
        required_scopes=None,
        jwks_cache_ttl=3600,
        skip_paths=None,
        verify_ssl=True,
        offline_token_enabled=False,
        token_exchange_client_id="",
        access_token_cache_buffer=60,
    ):
        self.enabled = enabled
        self.issuer_url = issuer_url
        self.client_id = client_id
        self.required_scopes = required_scopes or []
        self.jwks_cache_ttl = jwks_cache_ttl
        self.skip_paths = skip_paths or ["/health", "/security"]
        self.verify_ssl = verify_ssl
        # Offline token support: accept refresh tokens and exchange for access tokens
        self.offline_token_enabled = offline_token_enabled
        self.token_exchange_client_id = token_exchange_client_id
        self.access_token_cache_buffer = access_token_cache_buffer


class KonfluxDevLakeConfig:
    """Konflux DevLake MCP Server Configuration"""

    def __init__(self):
        self.database = DatabaseConfig()
        self.server = ServerConfig()
        self.logging = LoggingConfig()
        self.oidc = OIDCConfig()
        self._load_from_env()

    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Database configuration
        self.database.host = os.getenv("DB_HOST", self.database.host)
        self.database.port = int(os.getenv("DB_PORT", str(self.database.port)))
        self.database.user = os.getenv("DB_USER", self.database.user)
        self.database.password = os.getenv("DB_PASSWORD", self.database.password)
        self.database.database = os.getenv("DB_DATABASE", self.database.database)
        self.database.connect_timeout = int(
            os.getenv("DB_CONNECT_TIMEOUT", str(self.database.connect_timeout))
        )
        self.database.read_timeout = int(
            os.getenv("DB_READ_TIMEOUT", str(self.database.read_timeout))
        )
        self.database.write_timeout = int(
            os.getenv("DB_WRITE_TIMEOUT", str(self.database.write_timeout))
        )
        # Connection pool configuration for multi-user support
        self.database.pool_min_size = int(
            os.getenv("DB_POOL_MIN_SIZE", str(self.database.pool_min_size))
        )
        self.database.pool_max_size = int(
            os.getenv("DB_POOL_MAX_SIZE", str(self.database.pool_max_size))
        )
        self.database.pool_recycle = int(
            os.getenv("DB_POOL_RECYCLE", str(self.database.pool_recycle))
        )

        # Server configuration
        self.server.transport = os.getenv("TRANSPORT", self.server.transport)
        self.server.host = os.getenv("SERVER_HOST", self.server.host)
        self.server.port = int(os.getenv("SERVER_PORT", str(self.server.port)))
        self.server.timeout_keep_alive = int(
            os.getenv("SERVER_TIMEOUT_KEEP_ALIVE", str(self.server.timeout_keep_alive))
        )
        self.server.timeout_graceful_shutdown = int(
            os.getenv(
                "SERVER_TIMEOUT_GRACEFUL_SHUTDOWN", str(self.server.timeout_graceful_shutdown)
            )
        )

        # Logging configuration
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)

        # OIDC configuration for Red Hat SSO / Keycloak
        self.oidc.enabled = os.getenv("OIDC_ENABLED", "false").lower() == "true"
        self.oidc.issuer_url = os.getenv("OIDC_ISSUER_URL", self.oidc.issuer_url)
        self.oidc.client_id = os.getenv("OIDC_CLIENT_ID", self.oidc.client_id)
        required_scopes = os.getenv("OIDC_REQUIRED_SCOPES", "")
        if required_scopes:
            self.oidc.required_scopes = [s.strip() for s in required_scopes.split(",")]
        self.oidc.jwks_cache_ttl = int(
            os.getenv("OIDC_JWKS_CACHE_TTL", str(self.oidc.jwks_cache_ttl))
        )
        skip_paths = os.getenv("OIDC_SKIP_PATHS", "")
        if skip_paths:
            self.oidc.skip_paths = [s.strip() for s in skip_paths.split(",")]
        self.oidc.verify_ssl = os.getenv("OIDC_VERIFY_SSL", "true").lower() == "true"
        # Offline token support
        self.oidc.offline_token_enabled = (
            os.getenv("OIDC_OFFLINE_TOKEN_ENABLED", "false").lower() == "true"
        )
        self.oidc.token_exchange_client_id = os.getenv(
            "OIDC_TOKEN_EXCHANGE_CLIENT_ID", self.oidc.token_exchange_client_id
        )
        self.oidc.access_token_cache_buffer = int(
            os.getenv("OIDC_ACCESS_TOKEN_CACHE_BUFFER", str(self.oidc.access_token_cache_buffer))
        )

    def get_database_config(self) -> dict:
        """Get database configuration as dictionary"""
        return {
            "host": self.database.host,
            "port": self.database.port,
            "user": self.database.user,
            "password": self.database.password,
            "database": self.database.database,
            "connect_timeout": self.database.connect_timeout,
            "read_timeout": self.database.read_timeout,
            "write_timeout": self.database.write_timeout,
            "pool_min_size": self.database.pool_min_size,
            "pool_max_size": self.database.pool_max_size,
            "pool_recycle": self.database.pool_recycle,
        }

    def get_server_config(self) -> dict:
        """Get server configuration as dictionary"""
        return {
            "transport": self.server.transport,
            "host": self.server.host,
            "port": self.server.port,
        }

    def get_oidc_config(self) -> dict:
        """Get OIDC configuration as dictionary"""
        return {
            "enabled": self.oidc.enabled,
            "issuer_url": self.oidc.issuer_url,
            "client_id": self.oidc.client_id,
            "required_scopes": self.oidc.required_scopes,
            "jwks_cache_ttl": self.oidc.jwks_cache_ttl,
            "skip_paths": self.oidc.skip_paths,
            "verify_ssl": self.oidc.verify_ssl,
            "offline_token_enabled": self.oidc.offline_token_enabled,
            "token_exchange_client_id": self.oidc.token_exchange_client_id,
            "access_token_cache_buffer": self.oidc.access_token_cache_buffer,
        }

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.database.host:
            return False
        if not self.database.user:
            return False
        if self.database.port <= 0 or self.database.port > 65535:
            return False
        if self.server.port <= 0 or self.server.port > 65535:
            return False
        return True

    def __str__(self) -> str:
        """String representation of configuration"""
        return f"""
Konflux DevLake MCP Server Configuration:
  Database:
    Host: {self.database.host}
    Port: {self.database.port}
    User: {self.database.user}
    Database: {self.database.database}
  Server:
    Transport: {self.server.transport}
    Host: {self.server.host}
    Port: {self.server.port}
  Logging:
    Level: {self.logging.level}
  OIDC:
    Enabled: {self.oidc.enabled}
    Issuer URL: {self.oidc.issuer_url}
    Client ID: {self.oidc.client_id}
    Offline Token Enabled: {self.oidc.offline_token_enabled}
        """
