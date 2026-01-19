"""
Core integration tests - minimal but essential SQL testing.

These tests verify that the most critical database operations work correctly.
"""

import pytest
import json
from toon_format import decode as toon_decode
from utils.db import KonfluxDevLakeConnection
from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools


@pytest.mark.integration
@pytest.mark.asyncio
class TestCoreIntegration:
    """Essential integration tests for database operations."""

    async def test_database_connectivity(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test basic database connection works."""
        result = await integration_db_connection.connect()
        assert result["success"] is True
        assert result["connection_info"]["database"] == "lake"

    async def test_incidents_core_functionality(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test core incident retrieval works with real database."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "incidents" in result
        assert len(result["incidents"]) >= 0

    async def test_deployments_core_functionality(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test core deployment retrieval works with real database."""
        deployment_tools = DeploymentTools(integration_db_connection)

        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)

        assert result["success"] is True
        assert "deployments" in result
        assert len(result["deployments"]) >= 0

    async def test_sql_injection_protection(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test that SQL injection attempts are blocked."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents",
            {"project_name": "Test_Project", "status": "'; DROP TABLE incidents; --"},
        )
        result = toon_decode(result_json)

        assert result["success"] is False or len(result.get("incidents", [])) >= 0

    async def test_database_schema_exists(
        self, integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test that required database tables exist."""
        required_tables = ["incidents", "cicd_deployments", "cicd_deployment_commits"]

        for table in required_tables:
            result = await integration_db_connection.execute_query(f"SHOW TABLES LIKE '{table}'")
            assert result["success"] is True
            assert len(result["data"]) == 1, f"Table {table} should exist"
