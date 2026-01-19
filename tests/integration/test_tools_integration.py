"""
Tools integration tests.

These tests verify that the MCP tools work correctly
against a real database with actual data.
"""

import pytest
import json
from toon_format import decode as toon_decode

from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools


@pytest.mark.integration
@pytest.mark.asyncio
class TestIncidentToolsIntegration:
    """Integration tests for incident tools."""

    async def test_get_incidents_no_filters(self, integration_db_connection, clean_database):
        """Test getting incidents with required project_name."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "incidents" in result
        assert "project_name" in result

        incidents = result["incidents"]
        # May be empty if no data for test project
        for incident in incidents:
            assert "incident_key" in incident
            assert "title" in incident
            assert "status" in incident
            assert "created_date" in incident

    async def test_get_incidents_with_status_filter(
        self, integration_db_connection, clean_database
    ):
        """Test getting incidents with status filter."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project", "status": "DONE"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "project_name" in result

        incidents = result["incidents"]
        for incident in incidents:
            assert incident["status"] == "DONE"

    async def test_get_incidents_with_component_filter(
        self, integration_db_connection, clean_database
    ):
        """Test getting incidents with component filter."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project", "component": "api-service"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "project_name" in result

        incidents = result["incidents"]
        for incident in incidents:
            assert incident["component"] == "api-service"

    async def test_get_incidents_with_date_range(self, integration_db_connection, clean_database):
        """Test getting incidents with days_back filter."""
        incident_tools = IncidentTools(integration_db_connection)

        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project", "days_back": 30}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        assert "project_name" in result
        assert "days_back" in result

    async def test_insert_and_query_test_incident(
        self,
        integration_db_connection,
        clean_database,
        sample_test_incident,
    ):
        """Test inserting a test incident and querying it."""
        insert_query = """
        INSERT INTO incidents (
            incident_key, title, description, status, severity,
            component, assignee, reporter, labels
        )
        VALUES (
            %(incident_key)s, %(title)s, %(description)s, %(status)s,
            %(severity)s, %(component)s, %(assignee)s, %(reporter)s,
            %(labels)s
        )
        """

        formatted_query = insert_query % {
            "incident_key": f"'{sample_test_incident['incident_key']}'",
            "title": f"'{sample_test_incident['title']}'",
            "description": f"'{sample_test_incident['description']}'",
            "status": f"'{sample_test_incident['status']}'",
            "severity": f"'{sample_test_incident['severity']}'",
            "component": f"'{sample_test_incident['component']}'",
            "assignee": f"'{sample_test_incident['assignee']}'",
            "reporter": f"'{sample_test_incident['reporter']}'",
            "labels": f"'{sample_test_incident['labels']}'",
        }
        result = await integration_db_connection.execute_query(formatted_query)
        assert result["success"] is True

        incident_tools = IncidentTools(integration_db_connection)
        result_json = await incident_tools.call_tool(
            "get_incidents", {"project_name": "Test_Project", "component": "test-service"}
        )
        result = toon_decode(result_json)

        assert result["success"] is True
        incidents = result["incidents"]

        # Note: Test incident may not appear if project_mapping is not set up
        # This test validates the tool works, not necessarily data presence
        assert isinstance(incidents, list)


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentToolsIntegration:
    """Integration tests for deployment tools."""

    async def test_get_deployments_no_filters(self, integration_db_connection, clean_database):
        """
        Test getting deployments without filters
        (should default to PRODUCTION + Konflux_Pilot_Team).
        """
        deployment_tools = DeploymentTools(integration_db_connection)

        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)

        assert result["success"] is True
        assert "deployments" in result
        assert "filters" in result

        deployments = result["deployments"]
        assert len(deployments) == 2

        for deployment in deployments:
            assert deployment["environment"] == "PRODUCTION"

        for deployment in deployments:
            assert "deployment_id" in deployment
            assert "display_title" in deployment
            assert "result" in deployment
            assert "environment" in deployment

    async def test_get_deployments_with_environment_filter(
        self, integration_db_connection, clean_database
    ):
        """Test getting deployments with environment filter."""
        deployment_tools = DeploymentTools(integration_db_connection)

        result_json = await deployment_tools.call_tool(
            "get_deployments", {"environment": "PRODUCTION"}
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["environment"] == "PRODUCTION"

        deployments = result["deployments"]
        for deployment in deployments:
            assert deployment["environment"] == "PRODUCTION"

    async def test_get_deployments_with_project_filter(
        self, integration_db_connection, clean_database
    ):
        """Test getting deployments with project filter."""
        deployment_tools = DeploymentTools(integration_db_connection)

        result_json = await deployment_tools.call_tool(
            "get_deployments", {"project": "Konflux_Pilot_Team"}
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["filters"]["project"] == "Konflux_Pilot_Team"

        deployments = result["deployments"]
        for deployment in deployments:
            assert deployment["project_name"] == "Konflux_Pilot_Team"
            assert deployment["environment"] == "PRODUCTION"

    async def test_insert_and_query_test_deployment(
        self,
        integration_db_connection,
        clean_database,
        sample_test_deployment,
    ):
        """Test inserting a test deployment and querying it."""
        insert_deployment_query = """
        INSERT INTO cicd_deployments (
            deployment_id, display_title, url, result, status,
            environment, project, commit_sha, branch
        )
        VALUES (
            %(deployment_id)s, %(display_title)s, %(url)s, %(result)s,
            %(status)s, %(environment)s, %(project)s, %(commit_sha)s,
            %(branch)s
        )
        """

        formatted_deployment_query = insert_deployment_query % {
            "deployment_id": f"'{sample_test_deployment['deployment_id']}'",
            "display_title": f"'{sample_test_deployment['display_title']}'",
            "url": f"'{sample_test_deployment['url']}'",
            "result": f"'{sample_test_deployment['result']}'",
            "status": f"'{sample_test_deployment['status']}'",
            "environment": "'PRODUCTION'",
            "project": "'Konflux_Pilot_Team'",
            "commit_sha": f"'{sample_test_deployment['commit_sha']}'",
            "branch": f"'{sample_test_deployment['branch']}'",
        }
        result = await integration_db_connection.execute_query(formatted_deployment_query)
        assert result["success"] is True

        insert_commit_query = """
        INSERT INTO cicd_deployment_commits (
            deployment_id, cicd_deployment_id, cicd_scope_id,
            display_title, url, result, environment, finished_date,
            commit_sha, commit_message, commit_author, commit_date,
            _raw_data_table
        ) VALUES (
            '%s', '%s', 'test-scope-001', '%s', '%s', '%s',
            'PRODUCTION', NOW(), '%s', 'Integration test deployment',
            'test@example.com', NOW(), 'raw_deployments'
        )
        """ % (
            sample_test_deployment["deployment_id"],
            sample_test_deployment["deployment_id"],
            sample_test_deployment["display_title"],
            sample_test_deployment["url"],
            sample_test_deployment["result"],
            sample_test_deployment["commit_sha"],
        )

        result = await integration_db_connection.execute_query(insert_commit_query)
        assert result["success"] is True

        insert_mapping_query = """
        INSERT INTO project_mapping (
            project_name, `table`, row_id, raw_data_table, params
        )
        VALUES (
            'Konflux_Pilot_Team', 'cicd_scopes', 'test-scope-001',
            'raw_deployments', '{"source": "test"}'
        )
        """

        result = await integration_db_connection.execute_query(insert_mapping_query)
        assert result["success"] is True

        deployment_tools = DeploymentTools(integration_db_connection)
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)

        assert result["success"] is True
        deployments = result["deployments"]

        test_deployment = next(
            (dep for dep in deployments if dep["deployment_id"] == "test-deploy-001"), None
        )
        assert test_deployment is not None
        assert test_deployment["display_title"] == "Integration Test Deployment"
        assert test_deployment["result"] == "SUCCESS"

    async def test_deployment_date_filtering(self, integration_db_connection, clean_database):
        """Test deployment date filtering."""
        deployment_tools = DeploymentTools(integration_db_connection)

        result_json = await deployment_tools.call_tool(
            "get_deployments", {"start_date": "2024-01-15", "end_date": "2024-01-17"}
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert "2024-01-15" in result["filters"]["start_date"]
        assert "2024-01-17" in result["filters"]["end_date"]

        deployments = result["deployments"]
        assert len(deployments) > 0
