#!/usr/bin/env python3
import importlib
import argparse
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

main_module = importlib.import_module("konflux-devlake-mcp")
create_parser = main_module.create_parser
create_config = main_module.create_config
validate_config = main_module.validate_config
run_server = main_module.run_server
main = main_module.main


@pytest.mark.unit
class TestCreateParser:
    def test_defaults(self):
        parser = create_parser()
        args = parser.parse_args([])
        assert args.transport == "http"
        assert args.host == "0.0.0.0"
        assert args.port == 3000
        assert args.db_host == "localhost"
        assert args.db_port == 3306
        assert args.db_user == "root"
        assert args.db_password == ""
        assert args.db_database == ""
        assert args.log_level == "INFO"

    def test_all_args(self):
        parser = create_parser()
        args = parser.parse_args(
            [
                "--transport",
                "stdio",
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
                "--db-host",
                "dbhost",
                "--db-port",
                "5432",
                "--db-user",
                "admin",
                "--db-password",
                "secret",
                "--db-database",
                "lake",
                "--log-level",
                "DEBUG",
            ]
        )
        assert args.transport == "stdio"
        assert args.host == "127.0.0.1"
        assert args.port == 8080
        assert args.db_host == "dbhost"
        assert args.db_port == 5432
        assert args.db_user == "admin"
        assert args.db_password == "secret"
        assert args.db_database == "lake"
        assert args.log_level == "DEBUG"


@pytest.mark.unit
class TestCreateConfig:
    def test_from_args(self):
        args = argparse.Namespace(
            transport="http",
            host="0.0.0.0",
            port=3000,
            db_host="myhost",
            db_port=3306,
            db_user="myuser",
            db_password="mypass",
            db_database="mydb",
            log_level="DEBUG",
        )
        config = create_config(args)
        assert config.database.host == "myhost"
        assert config.database.user == "myuser"
        assert config.database.password == "mypass"
        assert config.database.database == "mydb"
        assert config.server.transport == "http"
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 3000
        assert config.logging.level == "DEBUG"


@pytest.mark.unit
class TestValidateConfig:
    def test_valid(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="h", port=3306, user="u", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")
        assert validate_config(config) is True

    def test_no_host(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="", port=3306, user="u", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")
        assert validate_config(config) is False

    def test_no_user(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="h", port=3306, user="", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")
        assert validate_config(config) is False


@pytest.mark.unit
class TestRunServer:
    @pytest.mark.asyncio
    async def test_run_server_success(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="h", port=3306, user="u", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")

        mock_factory = MagicMock()
        mock_server = MagicMock()
        mock_server.start = AsyncMock()
        mock_server.shutdown = AsyncMock()
        mock_factory.create_server.return_value = mock_server
        mock_transport = MagicMock()
        mock_transport.stop = AsyncMock()
        mock_factory.create_transport.return_value = mock_transport

        with patch.object(main_module, "ServerFactory", return_value=mock_factory):
            result = await run_server(config)
        assert result == 0
        mock_server.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_server_keyboard_interrupt(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="h", port=3306, user="u", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")

        mock_factory = MagicMock()
        mock_server = MagicMock()
        mock_server.start = AsyncMock(side_effect=KeyboardInterrupt())
        mock_server.shutdown = AsyncMock()
        mock_factory.create_server.return_value = mock_server
        mock_transport = MagicMock()
        mock_transport.stop = AsyncMock()
        mock_factory.create_transport.return_value = mock_transport

        with patch.object(main_module, "ServerFactory", return_value=mock_factory):
            result = await run_server(config)
        assert result == 0

    @pytest.mark.asyncio
    async def test_run_server_exception(self):
        from utils.config import (
            KonfluxDevLakeConfig,
            DatabaseConfig,
            ServerConfig,
            LoggingConfig,
        )

        config = KonfluxDevLakeConfig()
        config.database = DatabaseConfig(
            host="h", port=3306, user="u", password="p", database="d"
        )
        config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
        config.logging = LoggingConfig(level="INFO")

        mock_factory = MagicMock()
        mock_server = MagicMock()
        mock_server.start = AsyncMock(side_effect=RuntimeError("boom"))
        mock_server.shutdown = AsyncMock()
        mock_factory.create_server.return_value = mock_server
        mock_transport = MagicMock()
        mock_transport.stop = AsyncMock()
        mock_factory.create_transport.return_value = mock_transport

        with patch.object(main_module, "ServerFactory", return_value=mock_factory):
            result = await run_server(config)
        assert result == 1


@pytest.mark.unit
class TestMain:
    @pytest.mark.asyncio
    async def test_main_success(self):
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = argparse.Namespace(
            transport="stdio",
            host="localhost",
            port=3000,
            db_host="h",
            db_port=3306,
            db_user="u",
            db_password="p",
            db_database="d",
            log_level="INFO",
        )
        mock_run = AsyncMock(return_value=0)
        with (
            patch.object(main_module, "create_parser", return_value=mock_parser),
            patch.object(main_module, "run_server", mock_run),
        ):
            result = await main()
        assert result == 0
        mock_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_invalid_config(self):
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = argparse.Namespace(
            transport="stdio",
            host="localhost",
            port=3000,
            db_host="",
            db_port=3306,
            db_user="",
            db_password="",
            db_database="",
            log_level="INFO",
        )
        with patch.object(main_module, "create_parser", return_value=mock_parser):
            result = await main()
        assert result == 1
