#!/usr/bin/env python3
"""
Unit Tests for Database Connection Pool

Tests the KonfluxDevLakeConnection class functionality including:
- Connection pool creation and management
- Retry logic for transient errors
- Query execution with pool
- Connection info retrieval
"""

import ssl as ssl_module

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from utils.db import (
    KonfluxDevLakeConnection,
    serialize_datetime_objects,
    DateTimeEncoder,
    TRANSIENT_MYSQL_ERRORS,
)
from datetime import datetime, date
from decimal import Decimal


@pytest.mark.unit
class TestDateTimeEncoder:
    """Test suite for DateTimeEncoder class."""

    def test_encode_datetime(self):
        """Test encoding datetime objects."""
        encoder = DateTimeEncoder()
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = encoder.default(dt)
        assert result == "2024-01-15T10:30:00"

    def test_encode_date(self):
        """Test encoding date objects."""
        encoder = DateTimeEncoder()
        d = date(2024, 1, 15)
        result = encoder.default(d)
        assert result == "2024-01-15"

    def test_encode_decimal(self):
        """Test encoding Decimal objects."""
        encoder = DateTimeEncoder()
        dec = Decimal("123.456")
        result = encoder.default(dec)
        assert result == "123.456"

    def test_encode_other_raises(self):
        """Test encoding other types raises TypeError."""
        encoder = DateTimeEncoder()
        with pytest.raises(TypeError):
            encoder.default({"key": "value"})


@pytest.mark.unit
class TestSerializeDatetimeObjects:
    """Test suite for serialize_datetime_objects function."""

    def test_serialize_dict_with_datetime(self):
        """Test serializing dict with datetime values."""
        data = {"created": datetime(2024, 1, 15, 10, 30, 0), "name": "test"}
        result = serialize_datetime_objects(data)
        assert result["created"] == "2024-01-15T10:30:00"
        assert result["name"] == "test"

    def test_serialize_list_with_datetime(self):
        """Test serializing list with datetime values."""
        data = [datetime(2024, 1, 15, 10, 30), "test"]
        result = serialize_datetime_objects(data)
        assert result[0] == "2024-01-15T10:30:00"
        assert result[1] == "test"

    def test_serialize_decimal(self):
        """Test serializing Decimal values."""
        data = {"amount": Decimal("99.99")}
        result = serialize_datetime_objects(data)
        assert result["amount"] == "99.99"

    def test_serialize_nested(self):
        """Test serializing nested structures."""
        data = {"items": [{"date": datetime(2024, 1, 15, 12, 0), "value": Decimal("10.5")}]}
        result = serialize_datetime_objects(data)
        assert result["items"][0]["date"] == "2024-01-15T12:00:00"
        assert result["items"][0]["value"] == "10.5"


@pytest.mark.unit
class TestTransientErrors:
    """Test suite for transient error detection."""

    def test_transient_errors_defined(self):
        """Test that transient MySQL errors are defined."""
        assert 2006 in TRANSIENT_MYSQL_ERRORS  # MySQL server has gone away
        assert 2013 in TRANSIENT_MYSQL_ERRORS  # Lost connection during query
        assert 2014 in TRANSIENT_MYSQL_ERRORS  # Commands out of sync
        assert 2055 in TRANSIENT_MYSQL_ERRORS  # Lost connection
        assert 0 in TRANSIENT_MYSQL_ERRORS  # Empty error


@pytest.mark.unit
class TestKonfluxDevLakeConnection:
    """Test suite for KonfluxDevLakeConnection class."""

    @pytest.fixture
    def db_config(self):
        """Create test database configuration."""
        return {
            "host": "localhost",
            "port": 3306,
            "user": "test_user",
            "password": "test_password",
            "database": "test_db",
            "pool_min_size": 2,
            "pool_max_size": 10,
            "pool_recycle": 300,
        }

    @pytest.fixture
    def connection(self, db_config):
        """Create KonfluxDevLakeConnection instance."""
        return KonfluxDevLakeConnection(db_config)

    def test_init(self, connection, db_config):
        """Test connection initialization."""
        assert connection.config == db_config
        assert connection._pool is None
        assert connection._last_health_check == 0

    def test_default_pool_config(self):
        """Test default pool configuration values."""
        assert KonfluxDevLakeConnection.DEFAULT_MIN_CONNECTIONS == 5
        assert KonfluxDevLakeConnection.DEFAULT_MAX_CONNECTIONS == 50
        assert KonfluxDevLakeConnection.DEFAULT_POOL_RECYCLE == 300

    def test_retry_config(self):
        """Test retry configuration values."""
        assert KonfluxDevLakeConnection.MAX_RETRIES == 3
        assert KonfluxDevLakeConnection.INITIAL_RETRY_DELAY == 0.5
        assert KonfluxDevLakeConnection.MAX_RETRY_DELAY == 10.0
        assert KonfluxDevLakeConnection.BACKOFF_MULTIPLIER == 2.0

    def test_get_connection_info_no_pool(self, connection):
        """Test get_connection_info when pool is not initialized."""
        info = connection.get_connection_info()
        assert info["host"] == "localhost"
        assert info["port"] == 3306
        assert info["user"] == "test_user"
        assert info["database"] == "test_db"
        assert info["connected"] is False
        assert info["last_health_check"] is None

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, connection):
        """Test that connect() creates a connection pool."""
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 2
        mock_pool.freesize = 2
        mock_pool.minsize = 2
        mock_pool.maxsize = 10

        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"version": "8.0.32"})

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool
            result = await connection.connect()

        assert result["success"] is True
        assert "connection_info" in result

    @pytest.mark.asyncio
    async def test_connect_pool_already_initialized(self, connection):
        """Test connect() when pool is already initialized."""
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 5
        mock_pool.freesize = 5
        mock_pool.minsize = 2
        mock_pool.maxsize = 10
        connection._pool = mock_pool

        result = await connection.connect()

        assert result["success"] is True
        assert result["message"] == "Connection pool already initialized"
        assert "connection_info" in result

    @pytest.mark.asyncio
    async def test_connect_failure_retries(self, connection):
        """Test that connect() retries on failure."""
        with patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Connection refused")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await connection.connect()

        assert result["success"] is False
        assert "Connection refused" in result["error"]
        assert mock_create.call_count == 3  # MAX_RETRIES

    @pytest.mark.asyncio
    async def test_close_pool(self, connection):
        """Test closing the connection pool."""
        mock_pool = MagicMock()
        mock_pool.close = MagicMock()
        mock_pool.wait_closed = AsyncMock()
        connection._pool = mock_pool

        await connection.close()

        mock_pool.close.assert_called_once()
        assert connection._pool is None

    @pytest.mark.asyncio
    async def test_test_connection_no_pool(self, connection):
        """Test test_connection when no pool exists."""
        result = await connection.test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_with_pool(self, connection):
        """Test test_connection with active pool."""
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"result": 1})
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        connection._pool = mock_pool

        result = await connection.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_reconnect(self, connection):
        """Test forcing reconnection."""
        # Set up existing pool
        mock_old_pool = MagicMock()
        mock_old_pool.close = MagicMock()
        connection._pool = mock_old_pool

        # Set up new pool
        mock_new_pool = MagicMock()
        mock_new_pool.closed = False
        mock_new_pool.size = 5
        mock_new_pool.freesize = 5
        mock_new_pool.minsize = 2
        mock_new_pool.maxsize = 10

        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"version": "8.0.32"})
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_new_pool.acquire = MagicMock(return_value=mock_conn)

        with patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_new_pool
            result = await connection.reconnect()

        assert result["success"] is True
        mock_old_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_success(self, connection):
        """Test executing a query successfully."""
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[{"id": 1, "name": "test"}])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 5
        mock_pool.freesize = 5
        mock_pool.minsize = 2
        mock_pool.maxsize = 10
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        connection._pool = mock_pool

        result = await connection.execute_query("SELECT * FROM test")

        assert result["success"] is True
        assert result["row_count"] == 1
        assert result["data"] == [{"id": 1, "name": "test"}]

    @pytest.mark.asyncio
    async def test_execute_query_with_limit(self, connection):
        """Test executing a query with result limit."""
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[{"id": i} for i in range(100)])
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 5
        mock_pool.freesize = 5
        mock_pool.minsize = 2
        mock_pool.maxsize = 10
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        connection._pool = mock_pool

        result = await connection.execute_query("SELECT * FROM test", limit=10)

        assert result["success"] is True
        assert len(result["data"]) == 10

    @pytest.mark.asyncio
    async def test_execute_query_failure(self, connection):
        """Test query execution failure."""
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 5
        mock_pool.freesize = 5
        mock_pool.minsize = 2
        mock_pool.maxsize = 10

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(side_effect=Exception("Query failed"))
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool.acquire = MagicMock(return_value=mock_conn)
        connection._pool = mock_pool

        result = await connection.execute_query("SELECT * FROM test")

        assert result["success"] is False
        assert "Query failed" in result["error"]

    def test_connection_property_legacy(self, connection):
        """Test legacy connection property."""
        mock_pool = MagicMock()
        connection._pool = mock_pool
        assert connection.connection is mock_pool

    @pytest.mark.asyncio
    async def test_connect_ssl_disabled_passes_none(self, db_config):
        """Test that ssl_enabled=False passes ssl=None to create_pool."""
        db_config["ssl_enabled"] = False
        connection = KonfluxDevLakeConnection(db_config)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 2
        mock_pool.freesize = 2
        mock_pool.minsize = 2
        mock_pool.maxsize = 10

        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"version": "8.0.32"})
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool
            result = await connection.connect()

        assert result["success"] is True
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["ssl"] is None

    @pytest.mark.asyncio
    async def test_connect_ssl_enabled_passes_context(self, db_config):
        """Test that ssl_enabled=True passes an ssl.SSLContext to create_pool."""
        db_config["ssl_enabled"] = True
        connection = KonfluxDevLakeConnection(db_config)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 2
        mock_pool.freesize = 2
        mock_pool.minsize = 2
        mock_pool.maxsize = 10

        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"version": "8.0.32"})
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool
            result = await connection.connect()

        assert result["success"] is True
        call_kwargs = mock_create.call_args[1]
        assert isinstance(call_kwargs["ssl"], ssl_module.SSLContext)

    @pytest.mark.asyncio
    async def test_connect_ssl_with_ca_path(self, db_config):
        """Test that ssl_enabled=True with ssl_ca_path loads the CA file."""
        db_config["ssl_enabled"] = True
        db_config["ssl_ca_path"] = "/app/certs/rds-combined-ca-bundle.pem"
        connection = KonfluxDevLakeConnection(db_config)

        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool.size = 2
        mock_pool.freesize = 2
        mock_pool.minsize = 2
        mock_pool.maxsize = 10

        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"version": "8.0.32"})
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with (
            patch("utils.db.aiomysql.create_pool", new_callable=AsyncMock) as mock_create,
            patch("utils.db.ssl_module.create_default_context") as mock_ssl_ctx,
        ):
            mock_ctx_instance = MagicMock(spec=ssl_module.SSLContext)
            mock_ssl_ctx.return_value = mock_ctx_instance
            mock_create.return_value = mock_pool
            result = await connection.connect()

        assert result["success"] is True
        mock_ssl_ctx.assert_called_once()
        mock_ctx_instance.load_verify_locations.assert_called_once_with(
            "/app/certs/rds-combined-ca-bundle.pem"
        )
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["ssl"] is mock_ctx_instance
