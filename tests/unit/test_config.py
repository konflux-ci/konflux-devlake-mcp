#!/usr/bin/env python3
"""
Unit Tests for Configuration Module

Tests the configuration classes and environment variable handling.
"""

import pytest
import os
from unittest.mock import patch

from utils.config import KonfluxDevLakeConfig, DatabaseConfig, ServerConfig, LoggingConfig


@pytest.mark.unit
class TestDatabaseConfig:
    """Test suite for DatabaseConfig class."""

    def test_database_config_defaults(self):
        """Test DatabaseConfig default values."""
        config = DatabaseConfig()

        assert config.host == "localhost"
        assert config.port == 3306
        assert config.user == "root"
        assert config.password == ""
        assert config.database == ""
        assert config.ssl_enabled is False
        assert config.ssl_ca_path == ""

    def test_database_config_custom_values(self):
        """Test DatabaseConfig with custom values."""
        config = DatabaseConfig(
            host="custom-host",
            port=5432,
            user="custom-user",
            password="custom-password",
            database="custom-db",
        )

        assert config.host == "custom-host"
        assert config.port == 5432
        assert config.user == "custom-user"
        assert config.password == "custom-password"
        assert config.database == "custom-db"


@pytest.mark.unit
class TestServerConfig:
    """Test suite for ServerConfig class."""

    def test_server_config_defaults(self):
        """Test ServerConfig default values."""
        config = ServerConfig()

        assert config.transport == "stdio"
        assert config.host == "0.0.0.0"
        assert config.port == 3000

    def test_server_config_custom_values(self):
        """Test ServerConfig with custom values."""
        config = ServerConfig(transport="http", host="127.0.0.1", port=8080)

        assert config.transport == "http"
        assert config.host == "127.0.0.1"
        assert config.port == 8080


@pytest.mark.unit
class TestLoggingConfig:
    """Test suite for LoggingConfig class."""

    def test_logging_config_defaults(self):
        """Test LoggingConfig default values."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def test_logging_config_custom_values(self):
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(level="DEBUG", format="%(levelname)s: %(message)s")

        assert config.level == "DEBUG"
        assert config.format == "%(levelname)s: %(message)s"


@pytest.mark.unit
class TestKonfluxDevLakeConfig:
    """Test suite for KonfluxDevLakeConfig class."""

    def test_config_initialization(self):
        """Test KonfluxDevLakeConfig initialization."""
        config = KonfluxDevLakeConfig()

        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_config_defaults(self):
        """Test KonfluxDevLakeConfig default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.host == "localhost"
            assert config.database.port == 3306
            assert config.database.user == "root"
            assert config.database.password == ""
            assert config.database.database == ""

            assert config.server.transport == "stdio"
            assert config.server.host == "0.0.0.0"
            assert config.server.port == 3000

            assert config.logging.level == "INFO"

    def test_config_environment_variables(self):
        """Test KonfluxDevLakeConfig loading from environment variables."""
        env_vars = {
            "DB_HOST": "env-host",
            "DB_PORT": "5432",
            "DB_USER": "env-user",
            "DB_PASSWORD": "env-password",
            "DB_DATABASE": "env-database",
            "TRANSPORT": "http",
            "SERVER_HOST": "127.0.0.1",
            "SERVER_PORT": "8080",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.host == "env-host"
            assert config.database.port == 5432
            assert config.database.user == "env-user"
            assert config.database.password == "env-password"
            assert config.database.database == "env-database"

            assert config.server.transport == "http"
            assert config.server.host == "127.0.0.1"
            assert config.server.port == 8080

            assert config.logging.level == "DEBUG"

    def test_config_partial_environment_variables(self):
        """Test KonfluxDevLakeConfig with partial environment variables."""
        env_vars = {"DB_HOST": "partial-host", "SERVER_PORT": "9000"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.host == "partial-host"
            assert config.server.port == 9000
            assert config.database.port == 3306
            assert config.database.user == "root"
            assert config.server.transport == "stdio"
            assert config.server.host == "0.0.0.0"

    def test_get_database_config(self):
        """Test get_database_config method."""
        config = KonfluxDevLakeConfig()
        config.database.host = "test-host"
        config.database.port = 5432
        config.database.user = "test-user"
        config.database.password = "test-password"
        config.database.database = "test-db"

        db_config = config.get_database_config()

        expected = {
            "host": "test-host",
            "port": 5432,
            "user": "test-user",
            "password": "test-password",
            "database": "test-db",
            "connect_timeout": 60,
            "read_timeout": 600,
            "write_timeout": 120,
            "pool_min_size": 5,
            "pool_max_size": 50,
            "pool_recycle": 300,
            "ssl_enabled": False,
            "ssl_ca_path": "",
        }

        assert db_config == expected

    def test_get_server_config(self):
        """Test get_server_config method."""
        config = KonfluxDevLakeConfig()
        config.server.transport = "http"
        config.server.host = "test-host"
        config.server.port = 8080

        server_config = config.get_server_config()

        expected = {"transport": "http", "host": "test-host", "port": 8080}

        assert server_config == expected

    def test_validate_valid_config(self):
        """Test validate method with valid configuration."""
        config = KonfluxDevLakeConfig()
        config.database.host = "valid-host"
        config.database.user = "valid-user"
        config.database.port = 3306
        config.server.port = 3000

        assert config.validate() is True

    def test_validate_missing_host(self):
        """Test validate method with missing database host."""
        config = KonfluxDevLakeConfig()
        config.database.host = ""
        config.database.user = "valid-user"

        assert config.validate() is False

    def test_validate_missing_user(self):
        """Test validate method with missing database user."""
        config = KonfluxDevLakeConfig()
        config.database.host = "valid-host"
        config.database.user = ""

        assert config.validate() is False

    def test_validate_invalid_database_port(self):
        """Test validate method with invalid database port."""
        config = KonfluxDevLakeConfig()
        config.database.host = "valid-host"
        config.database.user = "valid-user"
        config.database.port = 0

        assert config.validate() is False

        config.database.port = 70000
        assert config.validate() is False

    def test_validate_invalid_server_port(self):
        """Test validate method with invalid server port."""
        config = KonfluxDevLakeConfig()
        config.database.host = "valid-host"
        config.database.user = "valid-user"
        config.server.port = -1

        assert config.validate() is False

        config.server.port = 70000
        assert config.validate() is False

    def test_string_representation(self):
        """Test string representation of configuration."""
        config = KonfluxDevLakeConfig()
        config.database.host = "test-host"
        config.database.port = 3306
        config.database.user = "test-user"
        config.database.database = "test-db"
        config.server.transport = "http"
        config.server.host = "0.0.0.0"
        config.server.port = 3000
        config.logging.level = "INFO"

        str_repr = str(config)

        assert "Konflux DevLake MCP Server Configuration" in str_repr
        assert "test-host" in str_repr
        assert "3306" in str_repr
        assert "test-user" in str_repr
        assert "test-db" in str_repr
        assert "http" in str_repr
        assert "0.0.0.0" in str_repr
        assert "3000" in str_repr
        assert "INFO" in str_repr

    def test_environment_variable_type_conversion(self):
        """Test that environment variables are properly converted to correct types."""
        env_vars = {"DB_PORT": "5432", "SERVER_PORT": "8080"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert isinstance(config.database.port, int)
            assert isinstance(config.server.port, int)
            assert config.database.port == 5432
            assert config.server.port == 8080

    def test_environment_variable_invalid_port(self):
        """Test handling of invalid port values in environment variables."""
        env_vars = {"DB_PORT": "invalid_port"}

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError):
                KonfluxDevLakeConfig()

    def test_config_immutability_after_env_load(self):
        """Test that configuration values can be modified after environment loading."""
        env_vars = {"DB_HOST": "env-host"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.host == "env-host"

            config.database.host = "modified-host"
            assert config.database.host == "modified-host"

    def test_ssl_defaults(self):
        """Test that SSL defaults to disabled with no CA path."""
        with patch.dict(os.environ, {}, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.ssl_enabled is False
            assert config.database.ssl_ca_path == ""

    def test_ssl_enabled_from_env(self):
        """Test that DB_SSL=true enables SSL."""
        env_vars = {"DB_SSL": "true"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.ssl_enabled is True

    def test_ssl_enabled_case_insensitive(self):
        """Test that DB_SSL parsing is case-insensitive."""
        for value in ("True", "TRUE", "true"):
            with patch.dict(os.environ, {"DB_SSL": value}, clear=True):
                config = KonfluxDevLakeConfig()
                assert config.database.ssl_enabled is True

    def test_ssl_disabled_explicit(self):
        """Test that DB_SSL=false keeps SSL disabled."""
        env_vars = {"DB_SSL": "false"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.ssl_enabled is False

    def test_ssl_ca_path_from_env(self):
        """Test that DB_SSL_CA sets the CA certificate path."""
        env_vars = {"DB_SSL_CA": "/app/certs/rds-combined-ca-bundle.pem"}

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()

            assert config.database.ssl_ca_path == "/app/certs/rds-combined-ca-bundle.pem"

    def test_ssl_config_in_get_database_config(self):
        """Test that SSL fields are included in get_database_config() output."""
        env_vars = {
            "DB_SSL": "true",
            "DB_SSL_CA": "/path/to/ca.pem",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = KonfluxDevLakeConfig()
            db_config = config.get_database_config()

            assert db_config["ssl_enabled"] is True
            assert db_config["ssl_ca_path"] == "/path/to/ca.pem"
