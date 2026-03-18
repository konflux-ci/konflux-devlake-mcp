# Konflux DevLake MCP Server - Development Guidelines

## Project Overview

Python MCP server providing engineering metrics tools for Konflux DevLake databases.
Also ships Claude Code skills (`.claude-plugin/`) for interactive querying, report generation, and automated report repo scaffolding.

## Key Commands

```bash
make install               # Install dependencies
make test-unit             # Unit tests
make test-integration      # Integration tests (requires DB)
make test-e2e              # End-to-end tests (requires DB + LLM key)
make test-all              # All tests
pre-commit run --all-files # Lint (black, flake8, yamllint)
```

## Architecture

- `server/` — MCP server core (transport, handlers, factory, middleware)
- `tools/` — Tool modules (BaseTool interface, auto-registered via ToolsManager)
- `tools/devlake/` — DevLake-specific tools (PR cycle time, retests, deployments, etc.)
- `utils/` — Config, DB connection, security, logging, RBAC
- `.claude-plugin/` — Claude Code plugin manifest
- `skills/` — Claude Code skills (devlake, report, scaffold-report-repo)
- `docs/.prompts/` — Standalone prompt templates for report generation

## Adding New Tools

1. Create `tools/devlake/my_tool.py` extending `BaseTool`
2. Register in `tools/tools_manager.py`
3. Add tests in `tests/unit/test_my_tool.py`

## Skill Update Rule

**When modifying MCP tools, you MUST also update the corresponding skills:**

- Changed a tool's SQL query or schema? Update `skills/devlake/references/devlake-schema.md` and `skills/devlake/references/sql-patterns.md`
- Added/removed a tool? Update `skills/devlake/SKILL.md` tool references
- Changed tool input/output schema? Update relevant skill SKILL.md and prompt files
- Changed report prompt patterns? Update `skills/report/` and `docs/.prompts/`

This rule prevents schema drift between the MCP server and the skills that consume it.

## Deployed Version Awareness

The MCP server is deployed on OpenShift. The deployed version may lag behind `main`.
Skills and prompt templates must work with the **currently deployed version**, not bleeding-edge source.

- `skills/devlake/references/devlake-schema.md` documents the schema as seen in **production**
- SQL patterns are validated against the prod database
- When a new tool is added but not yet deployed, mark it in the skill as `(requires MCP >= vX.Y.Z)`
- The deployed version is tracked in `skills/VERSION` — update this after each deployment

## Code Style

- Python 3.11+ with type hints
- black + flake8 for formatting/linting
- Async methods for I/O operations
- TOON format for tool responses (token-efficient)
- All SQL queries must use `lake.table_name` format, no CTEs, CAST DECIMAL to CHAR
