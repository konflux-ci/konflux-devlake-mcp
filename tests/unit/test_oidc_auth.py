#!/usr/bin/env python3
"""
Unit Tests for OIDC Authentication Module

Tests for server/middleware/oidc_auth.py
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from server.middleware.oidc_auth import (
    AuthResult,
    OIDCAuthenticator,
    OIDCConfig,
)


class TestOIDCConfig:
    """Tests for OIDCConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OIDCConfig()

        assert config.enabled is False
        assert config.issuer_url == ""
        assert config.client_id == ""
        assert config.required_scopes == []
        assert config.jwks_cache_ttl == 3600
        assert config.skip_paths == ["/health", "/security"]
        assert config.verify_ssl is True
        assert config.allowed_algorithms == ["RS256"]

    def test_custom_values(self):
        """Test custom configuration values."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            required_scopes=["openid", "profile"],
            jwks_cache_ttl=1800,
            skip_paths=["/health", "/metrics"],
            verify_ssl=False,
        )

        assert config.enabled is True
        assert config.issuer_url == "https://sso.example.com/realms/test"
        assert config.client_id == "mcp-server"
        assert config.required_scopes == ["openid", "profile"]
        assert config.jwks_cache_ttl == 1800
        assert config.skip_paths == ["/health", "/metrics"]
        assert config.verify_ssl is False

    def test_offline_token_defaults(self):
        """Test offline token default values."""
        config = OIDCConfig()

        assert config.offline_token_enabled is False
        assert config.token_exchange_client_id == ""
        assert config.access_token_cache_buffer == 60

    def test_offline_token_custom_values(self):
        """Test offline token custom values."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
            token_exchange_client_id="cloud-services",
            access_token_cache_buffer=30,
        )

        assert config.offline_token_enabled is True
        assert config.token_exchange_client_id == "cloud-services"
        assert config.access_token_cache_buffer == 30


class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_default_values(self):
        """Test default AuthResult values."""
        result = AuthResult()

        assert result.authenticated is False
        assert result.user_id is None
        assert result.username is None
        assert result.email is None
        assert result.groups == []
        assert result.scopes == []
        assert result.error is None
        assert result.status_code == 401

    def test_successful_auth(self):
        """Test successful authentication result."""
        result = AuthResult(
            authenticated=True,
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            groups=["developers", "admins"],
            scopes=["openid", "profile"],
            status_code=200,
        )

        assert result.authenticated is True
        assert result.user_id == "user-123"
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.groups == ["developers", "admins"]
        assert result.scopes == ["openid", "profile"]
        assert result.status_code == 200

    def test_failed_auth(self):
        """Test failed authentication result."""
        result = AuthResult(
            authenticated=False,
            error="Token has expired",
            status_code=401,
        )

        assert result.authenticated is False
        assert result.error == "Token has expired"
        assert result.status_code == 401


class TestOIDCAuthenticator:
    """Tests for OIDCAuthenticator class."""

    def test_is_enabled_when_disabled(self):
        """Test is_enabled returns False when OIDC is disabled."""
        config = OIDCConfig(enabled=False)
        auth = OIDCAuthenticator(config)

        assert auth.is_enabled() is False

    def test_is_enabled_when_enabled_but_missing_config(self):
        """Test is_enabled returns False when enabled but missing config."""
        config = OIDCConfig(enabled=True, issuer_url="", client_id="")
        auth = OIDCAuthenticator(config)

        assert auth.is_enabled() is False

    def test_is_enabled_when_properly_configured(self):
        """Test is_enabled returns True when properly configured."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        assert auth.is_enabled() is True

    def test_should_skip_auth_for_health_path(self):
        """Test should_skip_auth returns True for health paths."""
        config = OIDCConfig(skip_paths=["/health", "/security"])
        auth = OIDCAuthenticator(config)

        assert auth.should_skip_auth("/health") is True
        assert auth.should_skip_auth("/health/live") is True
        assert auth.should_skip_auth("/security") is True
        assert auth.should_skip_auth("/security/stats") is True

    def test_should_skip_auth_for_mcp_path(self):
        """Test should_skip_auth returns False for MCP paths."""
        config = OIDCConfig(skip_paths=["/health", "/security"])
        auth = OIDCAuthenticator(config)

        assert auth.should_skip_auth("/mcp") is False
        assert auth.should_skip_auth("/mcp/messages") is False

    def test_extract_token_from_header_valid(self):
        """Test extracting valid Bearer token from header."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        token, error = auth._extract_token_from_header("Bearer eyJhbGc...")

        assert token == "eyJhbGc..."
        assert error is None

    def test_extract_token_from_header_missing(self):
        """Test extracting token from missing header."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        token, error = auth._extract_token_from_header("")

        assert token is None
        assert error == "Authorization header is required"

    def test_extract_token_from_header_wrong_scheme(self):
        """Test extracting token with wrong scheme."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        token, error = auth._extract_token_from_header("Basic dXNlcjpwYXNz")

        assert token is None
        assert error == "Authorization scheme must be Bearer"

    def test_extract_token_from_header_malformed(self):
        """Test extracting token from malformed header."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        token, error = auth._extract_token_from_header("Bearer")

        assert token is None
        assert error == "Invalid Authorization header format"

    @pytest.mark.asyncio
    async def test_authenticate_request_missing_header(self):
        """Test authentication with missing Authorization header."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        result = await auth.authenticate_request("")

        assert result.authenticated is False
        assert result.error == "Authorization header is required"
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_health_check_when_disabled(self):
        """Test health check when OIDC is disabled."""
        config = OIDCConfig(enabled=False)
        auth = OIDCAuthenticator(config)

        result = await auth.health_check()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_health_check_when_enabled(self):
        """Test health check when OIDC is enabled and healthy."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock the OIDC configuration fetch
        mock_config = {
            "issuer": "https://sso.example.com/realms/test",
            "jwks_uri": "https://sso.example.com/realms/test/protocol/openid-connect/certs",
        }

        with patch.object(auth, "_fetch_oidc_configuration", return_value=mock_config):
            result = await auth.health_check()

        assert result["status"] == "healthy"
        assert result["issuer"] == "https://sso.example.com/realms/test"
        assert result["client_id"] == "mcp-server"

    @pytest.mark.asyncio
    async def test_health_check_when_unhealthy(self):
        """Test health check when OIDC provider is unreachable."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock the OIDC configuration fetch to raise an exception
        with patch.object(
            auth,
            "_fetch_oidc_configuration",
            side_effect=RuntimeError("Connection refused"),
        ):
            result = await auth.health_check()

        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]


class TestOIDCAuthenticatorTokenValidation:
    """Tests for token validation in OIDCAuthenticator."""

    @pytest.mark.asyncio
    async def test_validate_token_expired(self):
        """Test validation of expired token."""
        import jwt

        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", side_effect=jwt.ExpiredSignatureError("Token expired")):
                    result = await auth.validate_token("expired.token.here")

        assert result.authenticated is False
        assert result.error == "Token has expired"
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_token_invalid_audience(self):
        """Test validation of token with invalid audience."""
        import jwt

        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", side_effect=jwt.InvalidAudienceError("Invalid audience")):
                    result = await auth.validate_token("invalid.audience.token")

        assert result.authenticated is False
        assert result.error == "Invalid token audience"
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_token_invalid_issuer(self):
        """Test validation of token with invalid issuer."""
        import jwt

        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", side_effect=jwt.InvalidIssuerError("Invalid issuer")):
                    result = await auth.validate_token("invalid.issuer.token")

        assert result.authenticated is False
        assert result.error == "Invalid token issuer"
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_token_success(self):
        """Test successful token validation."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        # Mock decoded token payload
        mock_payload = {
            "sub": "user-123",
            "preferred_username": "testuser",
            "email": "test@example.com",
            "groups": ["developers"],
            "scope": "openid profile email",
        }

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", return_value=mock_payload):
                    result = await auth.validate_token("valid.token.here")

        assert result.authenticated is True
        assert result.user_id == "user-123"
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.groups == ["developers"]
        assert "openid" in result.scopes
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_token_missing_required_scopes(self):
        """Test token validation with missing required scopes."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            required_scopes=["admin", "write"],
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        # Mock decoded token payload with insufficient scopes
        mock_payload = {
            "sub": "user-123",
            "preferred_username": "testuser",
            "scope": "openid profile",  # Missing 'admin' and 'write'
        }

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", return_value=mock_payload):
                    result = await auth.validate_token("valid.token.here")

        assert result.authenticated is False
        assert "Missing required scopes" in result.error
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_validate_token_keycloak_realm_roles(self):
        """Test token validation with Keycloak realm_access roles."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
        )
        auth = OIDCAuthenticator(config)

        # Mock JWKS response
        mock_jwks = {"keys": [{"kid": "test-key-id", "kty": "RSA"}]}

        # Mock decoded token payload with Keycloak realm_access
        mock_payload = {
            "sub": "user-123",
            "preferred_username": "testuser",
            "realm_access": {
                "roles": ["user", "admin"],
            },
            "scope": "openid",
        }

        with patch.object(auth, "_fetch_jwks", return_value=mock_jwks):
            with patch.object(auth, "_get_signing_key_from_jwt", return_value="test-key"):
                with patch("jwt.decode", return_value=mock_payload):
                    result = await auth.validate_token("valid.token.here")

        assert result.authenticated is True
        assert result.groups == ["user", "admin"]


class TestOfflineTokenSupport:
    """Tests for offline token (refresh token) support."""

    def test_hash_token(self):
        """Test token hashing for cache keys."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        hash1 = auth._hash_token("token1")
        hash2 = auth._hash_token("token1")
        hash3 = auth._hash_token("token2")

        # Same token should produce same hash
        assert hash1 == hash2
        # Different tokens should produce different hashes
        assert hash1 != hash3
        # Hash should be a hex string
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_is_access_token_with_bearer_type(self):
        """Test access token detection with Bearer type."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        # Access tokens have typ="Bearer" or "JWT"
        with patch("jwt.get_unverified_header", return_value={"alg": "RS256", "typ": "Bearer"}):
            result = auth._is_access_token("eyJhbGc.eyJzdWI.signature")

        assert result is True

    def test_is_access_token_with_jwt_type(self):
        """Test access token detection with JWT type."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        with patch("jwt.get_unverified_header", return_value={"alg": "RS256", "typ": "JWT"}):
            result = auth._is_access_token("eyJhbGc.eyJzdWI.signature")

        assert result is True

    def test_is_access_token_with_refresh_type(self):
        """Test refresh token detection with Refresh type."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        # Refresh tokens have typ="Refresh"
        with patch("jwt.get_unverified_header", return_value={"alg": "RS256", "typ": "Refresh"}):
            result = auth._is_access_token("eyJhbGc.eyJzdWI.signature")

        assert result is False

    def test_is_access_token_with_opaque_token(self):
        """Test detection with an opaque token (no dots)."""
        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        # Opaque tokens don't have JWT structure
        result = auth._is_access_token("offline-token-opaque-string-no-dots")

        assert result is False

    def test_is_access_token_with_malformed_jwt(self):
        """Test detection with malformed JWT."""
        import jwt

        config = OIDCConfig()
        auth = OIDCAuthenticator(config)

        # Has three parts but not decodable
        with patch("jwt.get_unverified_header", side_effect=jwt.exceptions.DecodeError("Bad")):
            result = auth._is_access_token("not.a.jwt")

        assert result is False

    @pytest.mark.asyncio
    async def test_exchange_offline_token_success(self):
        """Test successful offline token exchange."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
        )
        auth = OIDCAuthenticator(config)

        # Mock OIDC configuration
        mock_oidc_config = {
            "issuer": "https://sso.example.com/realms/test",
            "token_endpoint": "https://sso.example.com/realms/test/protocol/openid-connect/token",
        }

        # Mock successful token exchange response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(auth, "_fetch_oidc_configuration", return_value=mock_oidc_config):
            with patch.object(auth, "_get_http_client", return_value=mock_client):
                access_token, expires_in = await auth._exchange_offline_token("offline-token")

        assert access_token == "new-access-token"
        assert expires_in == 600

    @pytest.mark.asyncio
    async def test_exchange_offline_token_with_custom_client_id(self):
        """Test offline token exchange with custom token_exchange_client_id."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
            token_exchange_client_id="cloud-services",
        )
        auth = OIDCAuthenticator(config)

        mock_oidc_config = {
            "token_endpoint": "https://sso.example.com/realms/test/protocol/openid-connect/token",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(auth, "_fetch_oidc_configuration", return_value=mock_oidc_config):
            with patch.object(auth, "_get_http_client", return_value=mock_client):
                await auth._exchange_offline_token("offline-token")

        # Verify the correct client_id was used
        call_args = mock_client.post.call_args
        assert call_args[1]["data"]["client_id"] == "cloud-services"

    @pytest.mark.asyncio
    async def test_get_access_token_from_offline_caching(self):
        """Test that access tokens are cached correctly."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
            access_token_cache_buffer=60,
        )
        auth = OIDCAuthenticator(config)

        # First call should exchange the token
        with patch.object(
            auth, "_exchange_offline_token", return_value=("access-token-1", 600)
        ) as mock_exchange:
            token1 = await auth._get_access_token_from_offline("offline-token")

            assert token1 == "access-token-1"
            assert mock_exchange.call_count == 1

            # Second call with same offline token should use cache
            token2 = await auth._get_access_token_from_offline("offline-token")

            assert token2 == "access-token-1"
            assert mock_exchange.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_authenticate_request_with_offline_token(self):
        """Test authenticate_request with offline token when enabled."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
        )
        auth = OIDCAuthenticator(config)

        with patch.object(auth, "_is_access_token", return_value=False):
            with patch.object(auth, "_get_access_token_from_offline", return_value="access-token"):
                with patch.object(
                    auth,
                    "validate_token",
                    return_value=AuthResult(
                        authenticated=True,
                        user_id="user-123",
                        username="testuser",
                        status_code=200,
                    ),
                ) as mock_validate:
                    result = await auth.authenticate_request("Bearer offline-token")

        assert result.authenticated is True
        assert result.user_id == "user-123"
        mock_validate.assert_called_once_with("access-token")

    @pytest.mark.asyncio
    async def test_authenticate_request_offline_token_disabled(self):
        """Test that non-JWT tokens are rejected when offline_token_enabled is False."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=False,  # Disabled
        )
        auth = OIDCAuthenticator(config)

        with patch.object(auth, "_is_access_token", return_value=False):
            result = await auth.authenticate_request("Bearer offline-token")

        assert result.authenticated is False
        assert "Invalid token format" in result.error
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticate_request_offline_token_exchange_failure(self):
        """Test handling of offline token exchange failure."""
        config = OIDCConfig(
            enabled=True,
            issuer_url="https://sso.example.com/realms/test",
            client_id="mcp-server",
            offline_token_enabled=True,
        )
        auth = OIDCAuthenticator(config)

        with patch.object(auth, "_is_access_token", return_value=False):
            with patch.object(
                auth,
                "_get_access_token_from_offline",
                side_effect=RuntimeError("Token exchange failed: 401"),
            ):
                result = await auth.authenticate_request("Bearer bad-offline-token")

        assert result.authenticated is False
        assert "Token exchange failed" in result.error
        assert result.status_code == 401
