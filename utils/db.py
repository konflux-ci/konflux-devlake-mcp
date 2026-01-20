#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Database Connection Utility.

This module provides robust database connection management with:
- Async connection pooling for concurrent request handling
- Automatic connection health checks and recycling
- Retry logic with exponential backoff for transient failures
- Graceful handling of "MySQL server has gone away" and similar errors
"""

import asyncio
import json
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, Optional

import aiomysql
import pymysql

from utils.logger import get_logger, log_database_operation

# Transient MySQL errors that warrant a retry
TRANSIENT_MYSQL_ERRORS = {
    2006,  # MySQL server has gone away
    2013,  # Lost connection to MySQL server during query
    2014,  # Commands out of sync
    2055,  # Lost connection to MySQL server
    0,  # Empty error (connection in bad state)
}


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime and Decimal objects"""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            # Convert Decimal to string to preserve precision
            # Use str() instead of float() to avoid precision loss
            return str(obj)
        return super().default(obj)


def serialize_datetime_objects(data):
    """Recursively serialize datetime and Decimal objects in data structures"""
    if isinstance(data, dict):
        return {key: serialize_datetime_objects(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_datetime_objects(item) for item in data]
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, Decimal):
        # Convert Decimal to string to preserve precision
        return str(data)
    else:
        return data


class KonfluxDevLakeConnection:
    """Konflux DevLake Connection Manager with async connection pooling.

    This class manages a pool of database connections for efficient handling
    of concurrent requests. Key features:
    - Connection pooling with configurable min/max connections
    - Automatic connection health checks and recycling
    - Retry logic for transient failures
    - Graceful degradation with fallback to single connection
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 0.5  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds
    BACKOFF_MULTIPLIER = 2.0

    # Pool configuration - sized for multi-user concurrent access
    DEFAULT_MIN_CONNECTIONS = 5  # Keep 5 connections ready for immediate use
    DEFAULT_MAX_CONNECTIONS = 50  # Scale up to 20 for concurrent users
    DEFAULT_POOL_RECYCLE = 300  # Recycle connections after 5 minutes

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._pool: Optional[aiomysql.Pool] = None
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeConnection")
        self._last_health_check: float = 0
        self._pool_lock = asyncio.Lock()

    async def connect(self) -> Dict[str, Any]:
        """Initialize the connection pool."""
        return await self._create_pool()

    async def _create_pool(self) -> Dict[str, Any]:
        """Create the connection pool with retry logic."""
        async with self._pool_lock:
            if self._pool is not None and not self._pool.closed:
                return {
                    "success": True,
                    "message": "Connection pool already initialized",
                    "pool_size": self._pool.size,
                    "pool_freesize": self._pool.freesize,
                    "connection_info": {
                        "host": self.config["host"],
                        "port": self.config["port"],
                        "user": self.config["user"],
                        "database": self.config.get("database"),
                        "pool_min_size": self._pool.minsize,
                        "pool_max_size": self._pool.maxsize,
                    },
                }

            last_error = None
            delay = self.INITIAL_RETRY_DELAY

            for attempt in range(self.MAX_RETRIES):
                try:
                    self.logger.info(
                        f"Creating connection pool to {self.config['host']}:{self.config['port']}"
                        + (f" (attempt {attempt + 1}/{self.MAX_RETRIES})" if attempt > 0 else "")
                    )

                    # Pool configuration
                    min_size = self.config.get("pool_min_size", self.DEFAULT_MIN_CONNECTIONS)
                    max_size = self.config.get("pool_max_size", self.DEFAULT_MAX_CONNECTIONS)
                    pool_recycle = self.config.get("pool_recycle", self.DEFAULT_POOL_RECYCLE)

                    self._pool = await aiomysql.create_pool(
                        host=self.config["host"],
                        port=self.config["port"],
                        user=self.config["user"],
                        password=self.config["password"],
                        db=self.config.get("database"),
                        charset="utf8mb4",
                        minsize=min_size,
                        maxsize=max_size,
                        pool_recycle=pool_recycle,
                        autocommit=True,
                        cursorclass=aiomysql.DictCursor,
                        echo=False,
                    )

                    # Test the pool with a simple query
                    async with self._pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT VERSION() as version")
                            result = await cursor.fetchone()

                    self._last_health_check = time.time()
                    self.logger.info(
                        f"Connection pool created successfully "
                        f"(min={min_size}, max={max_size}, recycle={pool_recycle}s)"
                    )
                    log_database_operation("connect", success=True)

                    return {
                        "success": True,
                        "message": "Connection pool created successfully",
                        "version": result["version"] if result else "Unknown",
                        "pool_size": self._pool.size,
                        "pool_freesize": self._pool.freesize,
                        "connection_info": {
                            "host": self.config["host"],
                            "port": self.config["port"],
                            "user": self.config["user"],
                            "database": self.config.get("database"),
                            "pool_min_size": min_size,
                            "pool_max_size": max_size,
                        },
                    }

                except Exception as e:
                    last_error = e
                    self.logger.warning(
                        f"Connection pool creation attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"failed: {e}"
                    )

                    if attempt < self.MAX_RETRIES - 1:
                        self.logger.info(f"Retrying in {delay:.1f} seconds...")
                        await asyncio.sleep(delay)
                        delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)

            self.logger.error(
                f"Connection pool creation failed after {self.MAX_RETRIES} attempts: {last_error}"
            )
            log_database_operation("connect", success=False, error=str(last_error))
            return {"success": False, "error": str(last_error)}

    async def execute_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Execute a SQL query using a connection from the pool."""
        return await self._execute_with_retry(query, limit)

    async def _execute_with_retry(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Execute a query with retry logic for transient failures."""
        last_error = None
        delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self.MAX_RETRIES):
            try:
                # Ensure pool is available
                await self._ensure_pool()

                self.logger.debug(
                    f"Executing query: {query[:100]}..."
                    + (f" (attempt {attempt + 1}/{self.MAX_RETRIES})" if attempt > 0 else "")
                )

                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query)
                        results = await cursor.fetchall()

                # Serialize datetime objects to prevent JSON serialization issues
                serialized_results = serialize_datetime_objects(list(results[:limit]))

                self.logger.info(f"Query executed successfully, returned {len(results)} rows")
                log_database_operation("execute_query", query=query, success=True)

                return {
                    "success": True,
                    "query": query,
                    "row_count": len(results),
                    "data": serialized_results,
                }

            except (aiomysql.Error, pymysql.Error) as e:
                last_error = e
                error_code = e.args[0] if e.args else 0

                # Check if this is a transient error that warrants a retry
                if error_code in TRANSIENT_MYSQL_ERRORS and attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(
                        f"Transient MySQL error (code {error_code}) on attempt "
                        f"{attempt + 1}/{self.MAX_RETRIES}: {e}"
                    )
                    # Recreate the pool on next attempt
                    await self._close_pool()
                    self.logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                    delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)
                    continue

                # Non-transient error or max retries reached
                self.logger.error(f"Query execution failed: {e}")
                log_database_operation("execute_query", query=query, success=False, error=str(e))
                return {"success": False, "error": str(e), "query": query}

            except Exception as e:
                last_error = e
                # Check for connection-related errors in the exception message
                error_str = str(e).lower()
                is_connection_error = any(
                    keyword in error_str
                    for keyword in [
                        "broken pipe",
                        "connection reset",
                        "server has gone away",
                        "pool is closed",
                    ]
                )

                if is_connection_error and attempt < self.MAX_RETRIES - 1:
                    self.logger.warning(
                        f"Connection error on attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                    )
                    # Recreate the pool on next attempt
                    await self._close_pool()
                    self.logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                    delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)
                    continue

                self.logger.error(f"Query execution failed: {e}")
                log_database_operation("execute_query", query=query, success=False, error=str(e))
                return {"success": False, "error": str(e), "query": query}

        # Should not reach here, but handle it anyway
        error_msg = f"Query failed after {self.MAX_RETRIES} attempts: {last_error}"
        self.logger.error(error_msg)
        log_database_operation("execute_query", query=query, success=False, error=error_msg)
        return {"success": False, "error": error_msg, "query": query}

    async def _ensure_pool(self) -> None:
        """Ensure we have a healthy connection pool."""
        if self._pool is None or self._pool.closed:
            self.logger.info("Connection pool not available, creating...")
            result = await self._create_pool()
            if not result.get("success"):
                raise ConnectionError(f"Failed to create connection pool: {result.get('error')}")

    async def _close_pool(self) -> None:
        """Close the connection pool."""
        async with self._pool_lock:
            if self._pool is not None:
                try:
                    self._pool.close()
                    await self._pool.wait_closed()
                except Exception as e:
                    self.logger.warning(f"Error closing pool: {e}")
                finally:
                    self._pool = None

    async def close(self):
        """Close the connection pool."""
        self.logger.info("Closing connection pool...")
        await self._close_pool()
        self.logger.info("Connection pool closed")

    async def test_connection(self) -> bool:
        """Test if the connection pool is healthy."""
        try:
            if self._pool is None or self._pool.closed:
                return False

            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()

            self.logger.debug("Connection pool test successful")
            return True
        except Exception as e:
            self.logger.warning(f"Connection pool test failed: {e}")
            return False

    async def reconnect(self) -> Dict[str, Any]:
        """Force recreation of the connection pool."""
        self.logger.info("Forcing connection pool recreation...")
        await self._close_pool()
        return await self._create_pool()

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection pool information."""
        pool_info = {}
        if self._pool is not None and not self._pool.closed:
            pool_info = {
                "pool_size": self._pool.size,
                "pool_freesize": self._pool.freesize,
                "pool_minsize": self._pool.minsize,
                "pool_maxsize": self._pool.maxsize,
            }

        return {
            "host": self.config["host"],
            "port": self.config["port"],
            "user": self.config["user"],
            "database": self.config.get("database"),
            "connected": self._pool is not None and not self._pool.closed,
            "last_health_check": (
                datetime.fromtimestamp(self._last_health_check).isoformat()
                if self._last_health_check > 0
                else None
            ),
            **pool_info,
        }

    # Legacy property for backward compatibility
    @property
    def connection(self):
        """Legacy property - returns pool status for compatibility."""
        return self._pool
