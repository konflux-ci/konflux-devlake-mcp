"""E2E tests for database operations using LLM-driven tool calls."""

import pytest
import json
from litellm import Message

from ..e2e.utils import get_converted_tools, outcome_based_test
from ..e2e.conftest import models

pytestmark = pytest.mark.anyio


DIRECTIVE_SYSTEM_PROMPT = (
    "You are a helpful database assistant. "
    "When asked, call tools immediately, make reasonable assumptions, "
    "and always summarize after tool calls. "
    "Always include the specific requested details in your final answer."
)


def _find_tool_by_keywords(tools, *keywords):
    names = [t.name for t in tools.tools]
    for name in names:
        lower = name.lower()
        if all(k.lower() in lower for k in keywords):
            return name
    return None


def _content_to_dict(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_db_connect(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "Connect to the DevLake database, then in your final answer explicitly state: "
                "the host, port number, user and database name."
            ),
        ),
    ]
    answer = await outcome_based_test(
        model,
        messages,
        tools,
        mcp_client,
        expected_keywords=["host", "port", "user", "database"],
    )
    text = answer.lower()
    assert ("localhost" in text) or ("127.0.0.1" in text)
    assert "3306" in text
    assert "devlake" in text
    assert "lake" in text


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_list_databases(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "List all databases on the server and explicitly name each one in your answer."
            ),
        ),
    ]
    required_dbs = ["information_schema", "performance_schema", "lake"]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=required_dbs
    )
    text = answer.lower()
    for db in required_dbs:
        assert db in text


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_list_tables(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "List all table names in the 'lake' database and explicitly name "
                "each one in your answer."
            ),
        ),
    ]
    required_tables = [
        "incidents",
        "cicd_deployments",
        "cicd_deployment_commits",
        "project_mapping",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=required_tables
    )
    text = answer.lower()
    for tbl in required_tables:
        assert tbl in text


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_get_table_schema(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "Describe the columns of table 'incidents' in database 'lake'. In your answer, "
                "explicitly list column names."
            ),
        ),
    ]
    expected_columns = [
        "id",
        "incident_key",
        "title",
        "description",
        "status",
        "severity",
        "component",
        "created_date",
        "updated_date",
        "resolution_date",
        "lead_time_minutes",
        "url",
        "assignee",
        "reporter",
        "labels",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_columns
    )
    text = answer.lower()
    for col in expected_columns:
        assert col in text


# Direct tool smoke tests (non-LLM)
@pytest.mark.flaky(max_runs=2)
async def test_server_connect_direct(mcp_client):
    tools = await mcp_client.list_tools()
    connect_name = _find_tool_by_keywords(tools, "connect", "database") or "connect_database"
    assert connect_name is not None, f"Connect tool not found in: {[t.name for t in tools.tools]}"

    result = await mcp_client.call_tool(connect_name, {})
    assert result.content and result.content[0].text
    payload = _content_to_dict(result.content[0].text)
    assert (isinstance(payload, dict) and payload.get("success") is True) or (
        "connected" in result.content[0].text.lower()
    ), f"Unexpected connect response: {result.content[0].text[:200]}"


@pytest.mark.flaky(max_runs=2)
async def test_server_list_databases_direct(mcp_client):
    tools = await mcp_client.list_tools()
    list_name = _find_tool_by_keywords(tools, "list", "database") or "list_databases"
    assert (
        list_name is not None
    ), f"List databases tool not found in: {[t.name for t in tools.tools]}"

    result = await mcp_client.call_tool(list_name, {})
    assert result.content and result.content[0].text
    text = result.content[0].text.lower()
    assert (
        "lake" in text or "database" in text
    ), f"Unexpected list databases response: {result.content[0].text[:200]}"
