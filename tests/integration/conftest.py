"""
Integration test configuration and fixtures.

This module provides fixtures and utilities for integration tests that
interact with a real MySQL database.
"""

import asyncio
import os
import pytest
import pytest_asyncio
import time

import pymysql
from utils.db import KonfluxDevLakeConnection
from utils.config import KonfluxDevLakeConfig


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def integration_db_config():
    """Database configuration for integration tests."""
    config = KonfluxDevLakeConfig()
    config.database.host = os.getenv("TEST_DB_HOST", "localhost")
    config.database.port = int(os.getenv("TEST_DB_PORT", "3306"))
    config.database.user = os.getenv("TEST_DB_USER", "devlake")
    config.database.password = os.getenv("TEST_DB_PASSWORD", "devlake_password")
    config.database.database = os.getenv("TEST_DB_NAME", "lake")
    config.logging.level = "DEBUG"
    return config


@pytest.fixture(scope="session")
def wait_for_database(integration_db_config):
    """Wait for the database to be ready before running tests."""
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            connection = pymysql.connect(
                host=integration_db_config.database.host,
                port=integration_db_config.database.port,
                user=integration_db_config.database.user,
                password=integration_db_config.database.password,
                database=integration_db_config.database.database,
                charset="utf8mb4",
            )
            connection.close()
            print(f"✅ Database is ready after {attempt + 1} attempts")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⏳ Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                pytest.fail(f"❌ Database failed to become ready after {max_retries} attempts: {e}")


@pytest_asyncio.fixture(scope="function")
async def integration_db_connection(integration_db_config, wait_for_database):
    """Create a database connection for integration tests."""
    db_connection = KonfluxDevLakeConnection(
        {
            "host": integration_db_config.database.host,
            "port": integration_db_config.database.port,
            "user": integration_db_config.database.user,
            "password": integration_db_config.database.password,
            "database": integration_db_config.database.database,
        }
    )

    result = await db_connection.connect()
    if not result["success"]:
        pytest.fail(f"Failed to connect to integration database: {result.get('error')}")

    yield db_connection

    await db_connection.close()


@pytest_asyncio.fixture(scope="function")
async def clean_database(integration_db_connection):
    """Clean database state before each test."""
    cleanup_queries = [
        "DELETE FROM cicd_deployment_commits WHERE deployment_id LIKE 'test-%'",
        "DELETE FROM cicd_deployments WHERE deployment_id LIKE 'test-%'",
        "DELETE FROM incidents WHERE incident_key LIKE 'TEST-%'",
        "DELETE FROM project_mapping WHERE project_name LIKE 'Test_%'",
    ]

    for query in cleanup_queries:
        await integration_db_connection.execute_query(query)

    yield

    for query in cleanup_queries:
        await integration_db_connection.execute_query(query)


@pytest.fixture
def sample_test_incident():
    """Sample incident data for testing."""
    return {
        "incident_key": "TEST-INT-001",
        "title": "Integration Test Incident",
        "description": "This is a test incident for integration testing",
        "status": "OPEN",
        "severity": "MEDIUM",
        "component": "test-service",
        "assignee": "test@example.com",
        "reporter": "integration-test@example.com",
        "labels": '{"test": true, "environment": "integration"}',
    }


@pytest.fixture
def sample_test_deployment():
    """Sample deployment data for testing."""
    return {
        "deployment_id": "test-deploy-001",
        "display_title": "Integration Test Deployment",
        "url": "https://test.example.com/deployments/test-deploy-001",
        "result": "SUCCESS",
        "status": "COMPLETED",
        "environment": "TESTING",
        "project": "Test_Integration_Project",
        "commit_sha": "test123abc456",
        "branch": "test/integration",
    }


def pytest_configure(config):
    """Configure pytest markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring database"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark integration tests."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
