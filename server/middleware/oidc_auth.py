#!/usr/bin/env python3
"""
OIDC Authentication Module for Red Hat SSO / Keycloak

This module provides JWT token validation against Red Hat SSO (Keycloak)
using the OIDC protocol. It fetches and caches JWKS (JSON Web Key Set)
for token signature verification.
"""

import asyncio
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
import jwt
from jwt import PyJWK
from jwt.exceptions import PyJWKError

from utils.logger import get_logger


@dataclass
class OIDCConfig:
    """
    OIDC Configuration for Red Hat SSO / Keycloak.

    Attributes:
        enabled: Whether OIDC authentication is enabled
        issuer_url: The OIDC issuer URL (e.g., https://sso.example.com/realms/myrealm)
        client_id: The OIDC client ID (audience)
        required_scopes: List of required scopes for access
        jwks_cache_ttl: Time-to-live for JWKS cache in seconds (default: 3600)
        skip_paths: List of paths to skip authentication (e.g., /health)
        verify_ssl: Whether to verify SSL certificates (default: True)
        allowed_algorithms: List of allowed JWT algorithms (default: RS256)
    """

    enabled: bool = False
    issuer_url: str = ""
    client_id: str = ""
    required_scopes: List[str] = field(default_factory=list)
    jwks_cache_ttl: int = 3600
    skip_paths: List[str] = field(default_factory=lambda: ["/health", "/security"])
    verify_ssl: bool = True
    allowed_algorithms: List[str] = field(default_factory=lambda: ["RS256"])


@dataclass
class AuthResult:
    """
    Result of authentication attempt.

    Attributes:
        authenticated: Whether authentication was successful
        user_id: The user ID from the token (sub claim)
        username: The username from the token (preferred_username claim)
        email: The user's email from the token
        groups: List of groups the user belongs to
        scopes: List of scopes granted to the token
        error: Error message if authentication failed
        status_code: HTTP status code for the response
    """

    authenticated: bool = False
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    status_code: int = 401


class OIDCAuthenticator:
    """
    OIDC Authenticator for validating JWT tokens from Red Hat SSO / Keycloak.

    This class handles:
    - Fetching and caching JWKS from the OIDC provider
    - Validating JWT token signatures
    - Verifying token claims (issuer, audience, expiration)
    - Extracting user information from tokens
    """

    def __init__(self, config: OIDCConfig):
        """
        Initialize the OIDC authenticator.

        Args:
            config: OIDC configuration
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.OIDCAuthenticator")
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: float = 0
        self._oidc_config_cache: Optional[Dict[str, Any]] = None
        self._oidc_config_cache_time: float = 0
        self._lock = asyncio.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Get or create a reusable HTTP client.

        Returns:
            httpx.AsyncClient instance
        """
        if self._http_client is None or self._http_client.is_closed:
            # Create SSL context that can handle Red Hat SSO certificates
            ssl_context = None
            if not self.config.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            self._http_client = httpx.AsyncClient(
                verify=ssl_context if ssl_context else self.config.verify_ssl,
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._http_client

    async def _fetch_oidc_configuration(self) -> Dict[str, Any]:
        """
        Fetch OIDC configuration from the well-known endpoint.

        Returns:
            OIDC configuration dictionary
        """
        current_time = time.time()

        # Return cached config if still valid
        if (
            self._oidc_config_cache is not None
            and current_time - self._oidc_config_cache_time < self.config.jwks_cache_ttl
        ):
            return self._oidc_config_cache

        well_known_url = f"{self.config.issuer_url.rstrip('/')}/.well-known/openid-configuration"

        try:
            client = await self._get_http_client()
            self.logger.debug(f"Fetching OIDC configuration from {well_known_url}")
            response = await client.get(well_known_url)
            response.raise_for_status()
            self._oidc_config_cache = response.json()
            self._oidc_config_cache_time = current_time
            self.logger.debug("Successfully fetched OIDC configuration")
            return self._oidc_config_cache
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch OIDC configuration from {well_known_url}: {e}")
            raise RuntimeError(f"Failed to fetch OIDC configuration: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching OIDC configuration: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch OIDC configuration: {e}")

    async def _fetch_jwks(self) -> Dict[str, Any]:
        """
        Fetch JWKS from the OIDC provider using httpx.

        Returns:
            JWKS dictionary containing keys
        """
        current_time = time.time()

        async with self._lock:
            # Return cached JWKS if still valid
            if (
                self._jwks_cache is not None
                and current_time - self._jwks_cache_time < self.config.jwks_cache_ttl
            ):
                return self._jwks_cache

            # Fetch OIDC configuration to get JWKS URI
            oidc_config = await self._fetch_oidc_configuration()
            jwks_uri = oidc_config.get("jwks_uri")

            if not jwks_uri:
                raise RuntimeError("JWKS URI not found in OIDC configuration")

            # Fetch JWKS using our HTTP client (respects SSL settings)
            try:
                client = await self._get_http_client()
                self.logger.debug(f"Fetching JWKS from {jwks_uri}")
                response = await client.get(jwks_uri)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = current_time
                self.logger.info(
                    f"Successfully fetched JWKS with {len(self._jwks_cache.get('keys', []))} keys"
                )
                return self._jwks_cache
            except httpx.HTTPError as e:
                self.logger.error(f"Failed to fetch JWKS from {jwks_uri}: {e}")
                raise RuntimeError(f"Failed to fetch JWKS: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error fetching JWKS: {e}", exc_info=True)
                raise RuntimeError(f"Failed to fetch JWKS: {e}")

    def _get_signing_key_from_jwt(self, token: str, jwks: Dict[str, Any]) -> Any:
        """
        Get the signing key for a JWT token from the JWKS.

        Args:
            token: The JWT token
            jwks: The JWKS dictionary

        Returns:
            The signing key for the token
        """
        # Decode the token header to get the key ID (kid)
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as e:
            raise PyJWKError(f"Failed to decode token header: {e}")

        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")

        self.logger.debug(f"Looking for key with kid={kid}, alg={alg}")

        # Find the matching key in JWKS
        keys = jwks.get("keys", [])
        for key_data in keys:
            if key_data.get("kid") == kid:
                try:
                    jwk = PyJWK.from_dict(key_data)
                    self.logger.debug(f"Found matching key for kid={kid}")
                    return jwk.key
                except Exception as e:
                    self.logger.error(f"Failed to create key from JWK: {e}")
                    raise PyJWKError(f"Failed to create key from JWK: {e}")

        # If no kid match, try to find a key with matching algorithm
        for key_data in keys:
            key_alg = key_data.get("alg")
            key_type = key_data.get("kty")
            if key_alg == alg or (key_type == "RSA" and alg.startswith("RS")):
                try:
                    jwk = PyJWK.from_dict(key_data)
                    self.logger.debug(f"Using key with matching algorithm: {alg}")
                    return jwk.key
                except Exception:
                    continue

        raise PyJWKError(f"No matching key found for kid={kid}")

    def _extract_token_from_header(self, auth_header: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract Bearer token from Authorization header.

        Args:
            auth_header: The Authorization header value

        Returns:
            Tuple of (token, error_message)
        """
        if not auth_header:
            return None, "Authorization header is required"

        parts = auth_header.split()

        if len(parts) != 2:
            return None, "Invalid Authorization header format"

        scheme, token = parts

        if scheme.lower() != "bearer":
            return None, "Authorization scheme must be Bearer"

        return token, None

    async def validate_token(self, token: str) -> AuthResult:
        """
        Validate a JWT token against Red Hat SSO.

        Args:
            token: The JWT token to validate

        Returns:
            AuthResult with validation result
        """
        try:
            # Fetch JWKS
            jwks = await self._fetch_jwks()

            # Get signing key from token header
            try:
                signing_key = self._get_signing_key_from_jwt(token, jwks)
            except PyJWKError as e:
                self.logger.warning(f"Failed to get signing key: {e}")
                return AuthResult(
                    authenticated=False,
                    error="Invalid token signature",
                    status_code=401,
                )

            # Decode and verify token
            try:
                payload = jwt.decode(
                    token,
                    signing_key,
                    algorithms=self.config.allowed_algorithms,
                    audience=self.config.client_id,
                    issuer=self.config.issuer_url,
                    options={
                        "verify_exp": True,
                        "verify_iat": True,
                        "verify_aud": True,
                        "verify_iss": True,
                    },
                )
            except jwt.ExpiredSignatureError:
                self.logger.warning("Token has expired")
                return AuthResult(
                    authenticated=False,
                    error="Token has expired",
                    status_code=401,
                )
            except jwt.InvalidAudienceError:
                self.logger.warning("Invalid token audience")
                return AuthResult(
                    authenticated=False,
                    error="Invalid token audience",
                    status_code=401,
                )
            except jwt.InvalidIssuerError:
                self.logger.warning("Invalid token issuer")
                return AuthResult(
                    authenticated=False,
                    error="Invalid token issuer",
                    status_code=401,
                )
            except jwt.InvalidTokenError as e:
                self.logger.warning(f"Invalid token: {e}")
                return AuthResult(
                    authenticated=False,
                    error=f"Invalid token: {str(e)}",
                    status_code=401,
                )

            # Extract user information
            user_id = payload.get("sub")
            username = payload.get("preferred_username") or payload.get("username")
            email = payload.get("email")

            # Extract groups (Keycloak specific)
            groups = payload.get("groups", [])
            if not groups:
                # Try realm_access.roles for Keycloak
                realm_access = payload.get("realm_access", {})
                groups = realm_access.get("roles", [])

            # Extract scopes
            scope_claim = payload.get("scope", "")
            scopes = scope_claim.split() if isinstance(scope_claim, str) else []

            # Verify required scopes
            if self.config.required_scopes:
                missing_scopes = set(self.config.required_scopes) - set(scopes)
                if missing_scopes:
                    self.logger.warning(f"Missing required scopes: {missing_scopes}")
                    return AuthResult(
                        authenticated=False,
                        error=f"Missing required scopes: {missing_scopes}",
                        status_code=403,
                    )

            self.logger.info(f"Successfully authenticated user: {username} ({user_id})")

            return AuthResult(
                authenticated=True,
                user_id=user_id,
                username=username,
                email=email,
                groups=groups,
                scopes=scopes,
                status_code=200,
            )

        except RuntimeError as e:
            self.logger.error(f"OIDC configuration error: {e}")
            return AuthResult(
                authenticated=False,
                error="Authentication service unavailable",
                status_code=503,
            )
        except Exception as e:
            self.logger.error(f"Unexpected authentication error: {e}", exc_info=True)
            return AuthResult(
                authenticated=False,
                error="Internal authentication error",
                status_code=500,
            )

    async def authenticate_request(self, auth_header: str) -> AuthResult:
        """
        Authenticate an incoming request using the Authorization header.

        Args:
            auth_header: The Authorization header value

        Returns:
            AuthResult with authentication result
        """
        # Extract token from header
        token, error = self._extract_token_from_header(auth_header)
        if error:
            return AuthResult(
                authenticated=False,
                error=error,
                status_code=401,
            )

        # Validate token
        return await self.validate_token(token)

    def should_skip_auth(self, path: str) -> bool:
        """
        Check if authentication should be skipped for the given path.

        Args:
            path: The request path

        Returns:
            True if authentication should be skipped
        """
        for skip_path in self.config.skip_paths:
            if path.startswith(skip_path):
                return True
        return False

    def is_enabled(self) -> bool:
        """
        Check if OIDC authentication is enabled.

        Returns:
            True if OIDC is enabled and properly configured
        """
        return self.config.enabled and bool(self.config.issuer_url) and bool(self.config.client_id)

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the OIDC provider.

        Returns:
            Health check result dictionary
        """
        if not self.is_enabled():
            return {
                "status": "disabled",
                "message": "OIDC authentication is not enabled",
            }

        try:
            await self._fetch_oidc_configuration()
            return {
                "status": "healthy",
                "issuer": self.config.issuer_url,
                "client_id": self.config.client_id,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
