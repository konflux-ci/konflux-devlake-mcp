"""E2E tests for incident operations using LLM-driven tool calls."""

import pytest
from litellm import Message

from ..e2e.utils import get_converted_tools, outcome_based_test
from ..e2e.conftest import models


pytestmark = pytest.mark.anyio


PROMPT = (
    "You are a DevLake assistant. Use tools immediately, assume reasonable date ranges, "
    "and summarize results."
)


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_january_range(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(
            role="user",
            content=(
                "Show incidents between 2024-01-01 and 2024-01-31. "
                "In your final answer, explicitly list each incident's title and status."
            ),
        ),
    ]
    expected_values = [
        "2024",
        "API Service High Response Time",
        "Database Connection Pool Exhaustion",
        "Frontend Build Pipeline Failure",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_values
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_incidents_by_component(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(
            role="user",
            content=(
                "Show incidents for component 'database-service' between 2024-01-01 "
                "and 2024-01-31. In your final answer, explicitly include for each "
                "incident: the title, incident key/id, severity, and status."
            ),
        ),
    ]
    expected_values = [
        "database-service",
        "Database Connection Pool Exhaustion",
        "INC-2024-002",
        "CRITICAL",
        "IN_PROGRESS",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_values
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_open_incidents_january(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(
            role="user",
            content=(
                "List OPEN incidents between 2024-01-01 and 2024-01-31. "
                "Explicitly include the titles."
            ),
        ),
    ]
    expected_values = [
        "open",
        "Frontend Build Pipeline Failure",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_values
    )
    assert len(answer) > 10


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_done_incidents_january(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=PROMPT),
        Message(
            role="user",
            content=(
                "Show DONE incidents between 2024-01-01 and 2024-01-31. "
                "In your final answer explicitly include the incident titles and status."
            ),
        ),
    ]
    expected_values = [
        "API Service High Response Time",
        "DONE",
        "2024",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_values
    )
    assert len(answer) > 10
