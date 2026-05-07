# Konflux DevLake MCP Server - Agent Quick Reference

Python MCP server providing engineering metrics tools for Konflux DevLake databases.

## Data Flow

Request -> `server/handlers/tool_handler.py` (security + RBAC) -> `tools/tools_manager.py` (routing) -> `tools/devlake/<tool>.py` (SQL + logic) -> `utils/db.py` (async MySQL pool, type conversion) -> `toon_encode()` response

## Key Paths

`tools/devlake/` metric tools | `tools/base/base_tool.py` BaseTool ABC | `tools/tools_manager.py` registry
`server/` MCP core | `utils/db.py` async MySQL pool | `utils/security.py` SQL injection detection
`skills/` Claude Code skills (must stay in sync with tools) | `tests/conftest.py` shared fixtures

## Adding a Tool

1. Create `tools/devlake/my_tool.py` extending `BaseTool`
2. `get_tools()` -> `List[mcp.types.Tool]` with JSON `inputSchema`
3. `async call_tool()` -> `toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})`
4. Register in `tools/tools_manager.py` `_tool_modules` list
5. Add tool name to `utils/rbac.py` viewer/admin permissions list
6. Add unit test: `tests/unit/test_my_tool.py` with `@pytest.mark.unit`
7. Update `skills/devlake/` if tool interface or SQL changed (see Skill Update Rule)

## Test Suite

Every tool in `tools/tools_manager.py` `_tool_modules` (12 modules) must have a dedicated `tests/unit/test_<name>.py`. Each test file validates: `get_tools()` returns correct tool names and schemas, `call_tool()` with mocked DB rows returns `toon_decode()`-parseable results with `success: True`, error paths return `success: False`, and filter/limit arguments are respected. Integration tests in `tests/integration/` use real MySQL and `clean_database` fixture.

When investigating a bug or adding a feature, verify `tests/unit/test_<name>.py` exists and covers `call_tool()` execution with expected computed values (scores, averages, classifications) -- not just response structure. If tests are missing or incomplete, add them.
Commands: `make test-unit` (mocked DB) | `make test-integration` (docker compose MySQL) | `make test-e2e` (requires `GEMINI_API_KEY`, seeds from `testdata/mysql/`)

- `asyncio_mode = strict`: async tests need `@pytest.mark.asyncio`
- Strict markers: `unit`, `integration`, `security`, `slow` (undeclared = test failure)
- Unit fixtures: `mock_db_connection` (AsyncMock), `mock_config` in `tests/conftest.py`
- Integration fixtures: `integration_db_connection`, `clean_database` in `tests/integration/conftest.py`

## SQL Rules

- Always qualify: `lake.table_name` — no CTEs, use subqueries
- CAST DECIMAL to CHAR in SELECT results
- NEVER interpolate user input via f-strings in SQL. Validate ALL user-supplied values through `SQLInjectionDetector` (`utils/security.py`) before embedding in queries

## Code Style

- Python 3.11+ with type hints, async for all I/O
- `black --line-length 100`, `flake8`, `yamllint` (run via `pre-commit run --all-files`)
- TOON format for tool responses (not JSON) — use `toon_encode()`/`toon_decode()`
- `log_tool_call()` required in every `call_tool()` implementation
- No emojis in code, comments, docstrings, or project files

## Skill Update Rule

When modifying tools, update the corresponding skills:
- SQL or schema changed? Update `skills/devlake/references/devlake-schema.md` and `sql-patterns.md`
- Tool added/removed or input/output changed? Update `skills/devlake/SKILL.md`
- Skills target the **deployed** version (`skills/VERSION`), not `main`

## Core Dependencies

`mcp>=1.23.0` | `aiomysql` | `toon-format` (from git) | `uvicorn`/`starlette` | `PyJWT`/`httpx`
