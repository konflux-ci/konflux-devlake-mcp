#!/usr/bin/env python3
"""E2E tests for deployment operations using LLM-driven tool calls."""
import pytest
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


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_list_deployments_with_projects(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "List deployments using the MCP tools provided. "
                "In your final answer explicitly name, for each deployment, the project "
                "and the deployment title."
            ),
        ),
    ]
    expected_values = [
        "API Service Production Deployment v1.2.3",
        "Database Service Production Deployment v2.1.0",
        "Konflux_Pilot_Team",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_values
    )
    text = answer.lower()
    for val in expected_values:
        assert val.lower() in text


@pytest.mark.parametrize("model", models)
@pytest.mark.flaky(max_runs=3)
async def test_llm_failed_deployments_with_failure_time(model, mcp_client):
    tools = await get_converted_tools(mcp_client)
    messages = [
        Message(role="system", content=DIRECTIVE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=(
                "List failed deployments. Use only the get_deployments tool "
                "(do not run custom SQL). In the tool call, do NOT set days_back, "
                "start_date, end_date, or environment (let the tool defaults apply). "
                "From the returned deployments, select those with result = FAILURE "
                "and in your final answer explicitly include, for each: deployment id, "
                "project name, environment, and the finished_date formatted as "
                "YYYY-MM-DD HH:MM:SS."
            ),
        ),
    ]
    expected_failure_details = [
        "deploy-db-prod-002",
        "failure",
        "2024-01-16 08:00:00",
        "production",
        "Konflux_Pilot_Team",
    ]
    answer = await outcome_based_test(
        model, messages, tools, mcp_client, expected_keywords=expected_failure_details
    )
    text = answer.lower()
    for item in expected_failure_details:
        assert item.lower() in text
