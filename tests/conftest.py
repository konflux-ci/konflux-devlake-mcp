#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures

This module provides shared fixtures and configuration for all tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from utils.config import KonfluxDevLakeConfig, DatabaseConfig, ServerConfig, LoggingConfig
from utils.db import KonfluxDevLakeConnection
from utils.security import KonfluxDevLakeSecurityManager
from tools.tools_manager import KonfluxDevLakeToolsManager


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = KonfluxDevLakeConfig()
    config.database = DatabaseConfig(
        host="test-host", port=3306, user="test-user", password="test-password", database="test-db"
    )
    config.server = ServerConfig(transport="stdio", host="localhost", port=3000)
    config.logging = LoggingConfig(level="DEBUG")
    return config


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection for testing."""
    mock_conn = Mock(spec=KonfluxDevLakeConnection)
    mock_conn.connect = AsyncMock(
        return_value={
            "success": True,
            "message": "Database connected successfully",
            "version": "8.0.32",
            "connection_info": {
                "host": "test-host",
                "port": 3306,
                "user": "test-user",
                "database": "test-db",
            },
        }
    )
    mock_conn.execute_query = AsyncMock(
        return_value={"success": True, "query": "SELECT 1", "row_count": 1, "data": [{"result": 1}]}
    )
    mock_conn.close = AsyncMock()
    mock_conn.test_connection = AsyncMock(return_value=True)
    return mock_conn


@pytest.fixture
def mock_security_manager(mock_config):
    """Create a mock security manager for testing."""
    mock_security = Mock(spec=KonfluxDevLakeSecurityManager)
    mock_security.validate_sql_query = Mock(return_value=(True, "Query validation passed"))
    mock_security.validate_database_name = Mock(
        return_value=(True, "Database name validation passed")
    )
    mock_security.validate_table_name = Mock(return_value=(True, "Table name validation passed"))
    mock_security.cleanup_expired_tokens = Mock()
    mock_security.get_security_stats = Mock(
        return_value={
            "active_api_keys": 0,
            "active_session_tokens": 0,
            "rate_limit_entries": 0,
            "allowed_ips": 0,
        }
    )
    return mock_security


@pytest.fixture
def mock_tools_manager(mock_db_connection):
    """Create a mock tools manager for testing."""
    mock_tools = Mock(spec=KonfluxDevLakeToolsManager)
    mock_tools.list_tools = AsyncMock(return_value=[])
    mock_tools.call_tool = AsyncMock(return_value='{"success": true, "result": "test"}')
    mock_tools.validate_tool_exists = Mock(return_value=True)
    mock_tools.get_tool_statistics = Mock(
        return_value={
            "total_tools": 7,
            "modules": 3,
            "tools_by_module": {"DatabaseTools": 4, "IncidentTools": 1, "DeploymentTools": 2},
            "available_tools": [
                "connect_database",
                "list_databases",
                "list_tables",
                "get_table_schema",
                "get_incidents",
                "get_deployments",
                "get_deployment_frequency",
            ],
        }
    )
    return mock_tools


@pytest.fixture
def sample_incident_data():
    """Sample incident data for testing."""
    return [
        {
            "incident_key": "INC-001",
            "title": "API Service Outage",
            "description": "Service experiencing high latency",
            "status": "DONE",
            "created_date": "2024-01-15T10:30:00",
            "resolution_date": "2024-01-15T12:45:00",
            "lead_time_minutes": 135,
            "component": "api-service",
            "url": "https://incident-tracker.com/INC-001",
        },
        {
            "incident_key": "INC-002",
            "title": "Database Connection Issues",
            "description": "Database connection pool exhausted",
            "status": "IN_PROGRESS",
            "created_date": "2024-01-16T09:15:00",
            "resolution_date": None,
            "lead_time_minutes": None,
            "component": "database",
            "url": "https://incident-tracker.com/INC-002",
        },
    ]


@pytest.fixture
def sample_deployment_data():
    """Sample deployment data for testing."""
    return [
        {
            "project_name": "Konflux_Pilot_Team",
            "deployment_id": "deploy-abc123",
            "display_title": "Release v1.2.3",
            "url": "https://ci-cd-system.com/deploy-abc123",
            "result": "SUCCESS",
            "environment": "PRODUCTION",
            "finished_date": "2024-01-15T14:30:00",
        },
        {
            "project_name": "Konflux_Pilot_Team",
            "deployment_id": "deploy-def456",
            "display_title": "Release v1.2.4",
            "url": "https://ci-cd-system.com/deploy-def456",
            "result": "FAILED",
            "environment": "PRODUCTION",
            "finished_date": "2024-01-16T10:15:00",
        },
    ]


@pytest.fixture
def sample_daily_deployment_data():
    """Sample aggregated daily deployment data for testing deployment frequency."""
    return [
        {"deployment_date": "2024-01-15", "deployment_count": 3},
        {"deployment_date": "2024-01-16", "deployment_count": 2},
        {"deployment_date": "2024-01-17", "deployment_count": 5},
        {"deployment_date": "2024-01-22", "deployment_count": 1},
        {"deployment_date": "2024-01-23", "deployment_count": 4},
    ]


@pytest.fixture
def sample_database_schema():
    """Sample database schema data for testing."""
    return [
        {
            "Field": "id",
            "Type": "int(11)",
            "Null": "NO",
            "Key": "PRI",
            "Default": None,
            "Extra": "auto_increment",
        },
        {
            "Field": "incident_key",
            "Type": "varchar(255)",
            "Null": "NO",
            "Key": "UNI",
            "Default": None,
            "Extra": "",
        },
        {"Field": "title", "Type": "text", "Null": "YES", "Key": "", "Default": None, "Extra": ""},
        {
            "Field": "status",
            "Type": "varchar(50)",
            "Null": "YES",
            "Key": "",
            "Default": None,
            "Extra": "",
        },
        {
            "Field": "created_date",
            "Type": "datetime",
            "Null": "YES",
            "Key": "",
            "Default": None,
            "Extra": "",
        },
    ]


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests (no external dependencies)")
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires database)"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "security: marks tests as security-related")
