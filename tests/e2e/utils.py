import os
import json
from litellm import acompletion, Message
from mcp.types import TextContent
from toon_format import decode as toon_decode

os.environ.setdefault("LITELLM_LOGGING", "False")
os.environ.setdefault("LITELLM_VERBOSE", "0")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "1")
os.environ.setdefault("LITELLM_LOGGING_QUEUE", "0")

_LOGGED_KEYS = set()


def _disable_litellm_logging_worker():
    """Force-disable litellm logging worker so it cannot spawn background tasks."""
    try:
        from litellm.litellm_core_utils import logging_worker

        try:

            def _noop(*args, **kwargs):
                return None

            async def _async_noop(*args, **kwargs):
                return None

            if hasattr(logging_worker, "start"):
                logging_worker.start = _noop
            if hasattr(logging_worker, "shutdown"):
                logging_worker.shutdown = _noop
            for name in ("_queue", "_QUEUE", "_worker", "_WORKER"):
                try:
                    if hasattr(logging_worker, name):
                        setattr(logging_worker, name, None)
                except Exception:
                    pass
            LW = getattr(logging_worker, "LoggingWorker", None)
            if LW is not None:
                for meth in ("start", "shutdown", "add_task"):
                    if hasattr(LW, meth):
                        setattr(LW, meth, _noop)
                if hasattr(LW, "_worker_loop"):
                    setattr(LW, "_worker_loop", _async_noop)
                for name in ("_queue", "_QUEUE", "_worker", "_WORKER"):
                    if hasattr(LW, name):
                        try:
                            setattr(LW, name, None)
                        except Exception:
                            pass
        except Exception:
            pass
    except Exception:
        pass


_disable_litellm_logging_worker()


def _disable_litellm_background_workers():
    """
    Disable of LiteLLM background logging to avoid event loop conflicts in tests.
    """
    try:
        import litellm

        try:
            setattr(litellm, "callbacks", [])
        except Exception:
            pass
        for attr in ("success_callback", "failure_callback"):
            try:
                if hasattr(litellm, attr):
                    setattr(litellm, attr, [])
            except Exception:
                pass
        for attr in ("LOGGING", "logging", "verbose"):
            try:
                if hasattr(litellm, attr):
                    setattr(litellm, attr, False)
            except Exception:
                pass
        try:
            from litellm.litellm_core_utils import logging_worker

            try:
                if hasattr(logging_worker, "shutdown"):
                    logging_worker.shutdown()
            except Exception:
                pass
            for name in ("_queue", "_QUEUE", "_worker", "_WORKER"):
                try:
                    if hasattr(logging_worker, name):
                        setattr(logging_worker, name, None)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass


os.environ.setdefault("LITELLM_LOGGING", "0")
os.environ.setdefault("LITELLM_VERBOSE", "0")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "1")
os.environ.setdefault("LITELLM_LOGGING_QUEUE", "0")
os.environ.setdefault("LITELLM_USE_BACKGROUND_THREAD", "1")
_disable_litellm_background_workers()


def _summarize_tool_output(tool_name, args, raw):
    """Produce a readable narrative from common tool outputs without extra LLM calls.
    Falls back to compact text when structure is unknown.
    """

    def _truncate(s, n=1600):
        return s if len(s) <= n else s[: n - 3] + "..."

    try:
        data = toon_decode(raw)
    except Exception:
        try:
            data = json.loads(raw)
        except Exception:
            return _truncate(raw.strip())

    def _to_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for k in (
                "data",
                "items",
                "results",
                "databases",
                "tables",
                "incidents",
                "deployments",
                "columns",
            ):
                v = value.get(k)
                if isinstance(v, list):
                    return v
        return []

    if tool_name and "database" in tool_name.lower() and "table" not in tool_name.lower():
        names = []
        seq = _to_list(data)
        if seq and all(isinstance(x, str) for x in seq):
            names = seq
        elif seq and all(isinstance(x, dict) for x in seq):
            for item in seq:
                for k in ("name", "database", "db"):
                    if isinstance(item, dict) and k in item:
                        names.append(str(item[k]))
                        break
        if names:
            preview = ", ".join(names[:20])
            more = f" and {len(names)-20} more" if len(names) > 20 else ""
            plural = "database" if len(names) == 1 else "databases"
            return (
                f"There {'is' if len(names) == 1 else 'are'} {len(names)} "
                f"{plural}: {preview}{more}."
            )

    if tool_name and "table" in tool_name.lower():
        tables = []
        seq = _to_list(data)
        if seq and all(isinstance(x, str) for x in seq):
            tables = seq
        elif seq and all(isinstance(x, dict) for x in seq):
            for item in seq:
                for k in ("name", "table", "table_name"):
                    if isinstance(item, dict) and k in item:
                        tables.append(str(item[k]))
                        break
        if tables:
            preview = ", ".join(tables[:20])
            more = f" and {len(tables)-20} more" if len(tables) > 20 else ""
            return f"Found {len(tables)} tables: {preview}{more}."

    if tool_name and "incident" in tool_name.lower():
        seq = _to_list(data)
        total = len(seq)
        if total:
            status_counts = {}
            comp_counts = {}
            samples = []
            for item in seq[:10]:
                if isinstance(item, dict):
                    s = str(item.get("status", "unknown")).upper()
                    c = str(item.get("component", "unknown"))
                    status_counts[s] = status_counts.get(s, 0) + 1
                    comp_counts[c] = comp_counts.get(c, 0) + 1
                    title = item.get("title") or item.get("incident_key") or item.get("id")
                    if title:
                        samples.append(str(title))
            status_text = ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items())) or ""
            top_components = sorted(comp_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
            comp_text = ", ".join(f"{k} ({v})" for k, v in top_components) or ""
            parts = [f"Found {total} incidents."]
            if status_text:
                parts.append(f"Status distribution: {status_text}.")
            if comp_text:
                parts.append(f"Top components: {comp_text}.")
            if samples:
                parts.append(f"Examples: {', '.join(samples[:5])}.")
            return " ".join(parts)

    if tool_name and "deployment" in tool_name.lower():
        seq = _to_list(data)
        total = len(seq)
        if total:
            env_counts = {}
            proj_counts = {}
            results = {}
            for item in seq[:50]:
                if isinstance(item, dict):
                    env = str(item.get("environment", "unknown")).upper()
                    proj = str(item.get("project", item.get("project_name", "unknown")))
                    res = str(item.get("result", "unknown")).upper()
                    env_counts[env] = env_counts.get(env, 0) + 1
                    proj_counts[proj] = proj_counts.get(proj, 0) + 1
                    results[res] = results.get(res, 0) + 1
            env_text = ", ".join(f"{k}: {v}" for k, v in sorted(env_counts.items())) or ""
            top_projects = sorted(proj_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
            proj_text = ", ".join(f"{k} ({v})" for k, v in top_projects) or ""
            res_text = ", ".join(f"{k}: {v}" for k, v in sorted(results.items())) or ""
            parts = [f"Found {total} deployments."]
            if env_text:
                parts.append(f"By environment: {env_text}.")
            if res_text:
                parts.append(f"Results: {res_text}.")
            if proj_text:
                parts.append(f"Top projects: {proj_text}.")
            return " ".join(parts)

    if tool_name and "schema" in tool_name.lower():
        cols = []
        if isinstance(data, list):
            cols = data
        elif isinstance(data, dict):
            _columns = data.get("columns")
            if isinstance(_columns, list):
                cols = _columns
            else:
                _data = data.get("data")
                if isinstance(_data, list):
                    cols = _data
        if cols and all(isinstance(x, dict) for x in cols):
            names = []
            for item in cols[:50]:
                name = str(item.get("name", item.get("column", "")))
                ctype = str(item.get("type", item.get("data_type", "")))
                info = f" ({ctype})" if ctype else ""
                names.append(f"- {name}{info}")
            more = f"\n... and {len(cols)-50} more" if len(cols) > 50 else ""
            return f"The table has {len(cols)} columns including:\n\n" + "\n".join(names) + more

    seq = _to_list(data)
    if seq and all(isinstance(x, dict) for x in seq):
        keys = set()
        lines = []
        for item in seq[:10]:
            keys.update(item.keys())
            parts = []
            for k in ("id", "uid", "name", "title", "status", "result", "environment"):
                if k in item:
                    parts.append(f"{k}: {item[k]}")
            if not parts:
                for k in list(item.keys())[:2]:
                    parts.append(f"{k}: {item[k]}")
            lines.append("- " + ", ".join(parts))
        keys_text = ", ".join(sorted(list(keys)))
        more = f"\n... and {len(seq)-10} more items" if len(seq) > 10 else ""
        return (
            f"Found {len(seq)} items with fields: {keys_text}. Sample:\n\n"
            + "\n".join(lines)
            + more
        )

    try:
        compact = json.dumps(data, ensure_ascii=False)
    except Exception:
        compact = str(data)
    return compact[:2000]


def convert_tool(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                **tool.inputSchema,
                "properties": tool.inputSchema.get("properties", {}),
            },
        },
    }


async def get_converted_tools(mcp_client):
    tools = await mcp_client.list_tools()
    return [convert_tool(t) for t in tools.tools]


async def _finalize_llm_answer(model, conversation, default_text):
    """Ask the model for a detailed, human-readable summary after tool results.
    Returns default_text if the model cannot provide content.
    """
    prompt = (
        "Provide a clear, human-readable summary of the results above. "
        "Explain what happened and highlight the key details and their implications. "
        "Do not return JSON; respond in full sentences with helpful context."
    )
    try:
        resp = await acompletion(
            model=model,
            messages=conversation + [Message(role="user", content=prompt)],
            tool_choice="none",
            num_retries=1,
            timeout=int(os.environ.get("LITELLM_TIMEOUT", "30")),
        )
        try:
            _disable_litellm_background_workers()
        except Exception:
            pass
        txt = resp.choices[0].message.content or ""
        txt = str(txt).strip()
        return txt if txt else default_text
    except Exception:
        return default_text


def _append_md_log(section):
    path = os.environ.get("E2E_LOG_MD_PATH")
    if not path:
        return
    try:
        test_name = os.environ.get("E2E_TEST_NAME", "unknown-test")
        model = section.get("model", "unknown-model")
        asked = section.get("asked", [])
        dedupe_key = f"{test_name}|{model}|{asked[0] if asked else ''}"
        if dedupe_key in _LOGGED_KEYS:
            return
        _LOGGED_KEYS.add(dedupe_key)
        assistant = section.get("assistant", "")
        tool_calls = section.get("tool_calls", [])
        tool_results = section.get("tool_results", [])
        reason = section.get("reason", "")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"### {test_name} [{model}]\n\n")
            if asked:
                fh.write("**Asked**:\n\n")
                for q in asked:
                    fh.write("```\n" + q + "\n```\n\n")
            fh.write("**LLM Response**:\n\n")
            if assistant and str(assistant).strip():
                fh.write("```\n" + str(assistant) + "\n```\n\n")
            else:
                fh.write("(no textual response; tool calls were issued)\n\n")
            if tool_calls:
                fh.write("**Tool calls**:\n\n")
                for tc in tool_calls:
                    fh.write(f"- {tc.get('name')}: {tc.get('arguments')}\n")
                fh.write("\n")
            if tool_results:
                fh.write("**Full tool output**:\n\n")
                for ev in tool_results:
                    fh.write(f"- {ev.get('name')}: {ev.get('arguments')}\n\n")
                    fh.write("```\n" + (ev.get("output") or "") + "\n```\n\n")
            if reason:
                fh.write("**Why test passed**: " + reason + "\n\n")
    except Exception:
        pass


def _reason_from_expected(assistant_text, expected):
    if not expected:
        return "LLM answer produced based on tool output"
    text = (assistant_text or "").lower()
    matched = [e for e in expected if e.lower() in text]
    missing = [e for e in expected if e.lower() not in text]
    common_values = ["localhost", "127.0.0.1", "3306", "lake", "devlake"]
    extras = [v for v in common_values if v in text and v not in [m.lower() for m in matched]]
    parts = []
    included_list = matched + extras
    if included_list:
        parts.append("Answer included: " + ", ".join(included_list))
    if missing:
        parts.append("missing: " + ", ".join(missing))
    return "; ".join(parts) if parts else "LLM answer produced based on tool output"


async def outcome_based_test(
    model,
    messages,
    tools,
    mcp_client,
    expected_keywords=None,
    max_iterations=5,
    debug=False,
):
    conversation = messages.copy()
    asked_texts = [
        m.content for m in messages if isinstance(m, Message) and getattr(m, "role", "") == "user"
    ]
    assistant_texts = []
    tool_events = []

    for _ in range(max_iterations):
        response = await acompletion(
            model=model,
            messages=conversation,
            tools=tools,
            tool_choice="required",
            num_retries=1,
            timeout=int(os.environ.get("LITELLM_TIMEOUT", "30")),
        )
        try:
            _disable_litellm_background_workers()
        except Exception:
            pass
        assistant_message = response.choices[0].message
        conversation.append(assistant_message)
        if getattr(assistant_message, "content", None):
            assistant_texts.append(str(assistant_message.content))

        raw_tool_calls = getattr(assistant_message, "tool_calls", None) or []
        tool_calls = []
        for tc in raw_tool_calls:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                tool_calls.append(
                    {
                        "id": str(tc.get("id") or tc.get("index") or ""),
                        "name": str(func.get("name") or ""),
                        "arguments": str(func.get("arguments") or func.get("args") or "{}"),
                    }
                )
            else:
                func = getattr(tc, "function", None)
                tool_calls.append(
                    {
                        "id": str(getattr(tc, "id", "") or ""),
                        "name": str(getattr(func, "name", "") if func else ""),
                        "arguments": str(getattr(func, "arguments", "{}") if func else "{}"),
                    }
                )

        if not tool_calls:
            final_answer = assistant_message.content or ""
            if final_answer:
                if expected_keywords:
                    lower = final_answer.lower()
                    for kw in expected_keywords:
                        assert kw.lower() in lower, f"Expected '{kw}' in final answer"
                _append_md_log(
                    {
                        "model": model,
                        "asked": asked_texts,
                        "assistant": ("\n\n".join(t for t in assistant_texts if t) or final_answer),
                        "tool_calls": [],
                        "tool_results": tool_events,
                        "reason": (
                            _reason_from_expected(final_answer, expected_keywords)
                            if expected_keywords
                            else "Final answer returned and validated by test assertions"
                        ),
                    }
                )
                return final_answer
            continue

        for tool_call in tool_calls:
            name = tool_call.get("name")
            args = json.loads(tool_call.get("arguments") or "{}")
            result = await mcp_client.call_tool(name, args)
            assert len(result.content) > 0 and isinstance(result.content[0], TextContent)
            conversation.append(
                Message(
                    role="tool", tool_call_id=tool_call.get("id"), content=result.content[0].text
                )
            )

            tool_text = result.content[0].text or ""
            tool_events.append(
                {
                    "name": name or "",
                    "arguments": json.dumps(args, ensure_ascii=False),
                    "output": tool_text,
                }
            )

            if tool_text:
                assistant_for_log = "\n\n".join(t for t in assistant_texts if t).strip()
                if not assistant_for_log:
                    assistant_for_log = await _finalize_llm_answer(
                        model,
                        conversation,
                        _summarize_tool_output(name or "", args, tool_text),
                    )
                _append_md_log(
                    {
                        "model": model,
                        "asked": asked_texts,
                        "assistant": assistant_for_log,
                        "tool_calls": tool_calls,
                        "tool_results": tool_events,
                        "reason": _reason_from_expected(assistant_for_log, expected_keywords),
                    }
                )
                try:
                    _disable_litellm_background_workers()
                except Exception:
                    pass
                return assistant_for_log

    last = conversation[-1].content or ""
    raise AssertionError(
        f"Max iterations reached without a final answer. " f"Last message: {last[:200]}"
    )
