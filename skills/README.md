# Leading Metrics Skills

Cursor Agent Skills that let a program manager query the n8n leading-metrics dashboard
equivalents directly from Cursor — no dashboard required.

Each skill translates the SQL and aggregation logic from the
[n8n-pulumi-poc](https://github.com/redhat-appstudio/n8n-pulumi-poc) leading-metrics
workflows into plain SQL queries that run against the DevLake MCP server.

---

## Available Skills

| Skill | File | Metrics covered |
|-------|------|----------------|
| `lm-pr-metrics` | [`lm-pr-metrics/SKILL.md`](./lm-pr-metrics/SKILL.md) | 11 PR Cycle Time metrics — totals, median cycle time, stages, flow, productivity, size distribution, z-score, trend |
| `lm-ftpr-metrics` | [`lm-ftpr-metrics/SKILL.md`](./lm-ftpr-metrics/SKILL.md) | First Time Pass Rate — overall FTPR %, weekly trend, pass/fail breakdown |
| `lm-coverage-metrics` | [`lm-coverage-metrics/SKILL.md`](./lm-coverage-metrics/SKILL.md) | Code Coverage — overall %, patch coverage, by-team breakdown, line counts, daily trend |

All three skills work at **product level** (e.g. all Konflux teams) or **team level**
(e.g. just Konflux Build), by reading blueprint IDs from the `n8n-pulumi-poc` JSON config
files at query time.

---

## Prerequisites

1. **Cursor IDE** with an LLM that can call MCP tools (Claude, GPT-4o, etc.)
2. **`konflux-devlake-mcp` MCP server** configured in your Cursor MCP settings
   (see the [root README](../README.md) for server setup)
3. **`n8n-pulumi-poc` repo cloned locally** — the skills read product/team JSON files
   from it to resolve blueprint IDs:
   ```bash
   git clone https://github.com/redhat-appstudio/n8n-pulumi-poc.git
   ```
   The skills expect to find it at a path you tell the agent (e.g. `~/Projects/n8n-pulumi-poc`).

---

## Installing a Skill in Cursor

1. Open Cursor Settings → **Features** → **Agent Skills** (or `.cursor/skills/`)
2. Copy the desired `SKILL.md` file into your Cursor skills directory:
   ```bash
   mkdir -p ~/.cursor/skills/lm-pr-metrics
   cp skills/lm-pr-metrics/SKILL.md ~/.cursor/skills/lm-pr-metrics/SKILL.md

   mkdir -p ~/.cursor/skills/lm-ftpr-metrics
   cp skills/lm-ftpr-metrics/SKILL.md ~/.cursor/skills/lm-ftpr-metrics/SKILL.md

   mkdir -p ~/.cursor/skills/lm-coverage-metrics
   cp skills/lm-coverage-metrics/SKILL.md ~/.cursor/skills/lm-coverage-metrics/SKILL.md
   ```
3. Restart Cursor (or reload the window) so the skills are picked up.

---

## MCP Server Configuration

Add the following to your Cursor MCP config (`~/.cursor/mcp.json` or workspace
`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "konflux-devlake-mcp-prd": {
      "url": "http://<your-mcp-server-host>:3000/mcp",
      "headers": {
        "Authorization": "Bearer <your-offline-token>"
      }
    }
  }
}
```

The skills call `mcp_konflux-devlake-mcp-prd_execute_query` — the server name in your
config must match `konflux-devlake-mcp-prd` for that tool name to resolve correctly.

---

## Example Prompts

Once the skills are installed and the MCP server is connected, try these in Cursor Chat:

**PR Cycle Time — product level:**
```
Using the lm-pr-metrics skill, show me PR cycle time metrics for the Konflux product
for April 2026. The n8n-pulumi-poc repo is at ~/Projects/n8n-pulumi-poc.
```

**PR Cycle Time — team level:**
```
Using the lm-pr-metrics skill, show me PR cycle time metrics for the konflux-build team
for Q1 2026 (2026-01-01 to 2026-03-31).
```

**FTPR:**
```
Using the lm-ftpr-metrics skill, what is the first time pass rate for Konflux
for the last 30 days (2026-04-19 to 2026-05-19)?
```

**Code Coverage:**
```
Using the lm-coverage-metrics skill, give me the code coverage report for Konflux
for April 2026. Show me the team breakdown and trend.
```

---

## How the Skills Work

Each skill follows the same pattern:

1. **Resolve scope** — reads `n8n-pulumi-poc/containers/dashboard/products/<id>.json`
   (or `teams/<id>.json`) to extract the blueprint IDs for the requested product/team
2. **Substitute IDs** — inserts those IDs into the `WHERE bp.id IN (...)` clause of
   each SQL template
3. **Execute queries** — calls `mcp_konflux-devlake-mcp-prd_execute_query` one or more
   times (FTPR requires two queries with an agent-side join)
4. **Format report** — assembles results into a markdown report with an interpretation guide

### SQL Constraints

All queries comply with the `execute_query` tool's requirements:
- Must start with `SELECT`
- No CTEs (`WITH` clauses) — uses nested subqueries instead
- No SQL comments (`--` or `/* */`)
- No semicolons
- Under 10,000 characters per query

### Scope Resolution

| JSON file | Dashboard type key | Used by |
|-----------|--------------------|---------|
| `products/<id>.json` → `blueprintids` (array) | `prcycletime` | lm-pr-metrics |
| `products/<id>.json` → `blueprintids` (array) | `ftpr` | lm-ftpr-metrics |
| `products/<id>.json` → `blueprintids` (array) | `codecoverage` | lm-coverage-metrics |
| `teams/<id>.json` → `blueprintid` (string) | same keys above | all three skills |

---

## Adding Support for a New Product or Team

No changes to the skill files are needed. As long as the product or team has a JSON file
in `n8n-pulumi-poc/containers/dashboard/products/` or `teams/` with the relevant
`dashboards` entry, the skill will pick up its blueprint IDs automatically.

To verify a product is configured, check:
```bash
cat n8n-pulumi-poc/containers/dashboard/products/<product-id>.json | python3 -m json.tool
```

Look for a `dashboards` array entry with the `type` matching the skill you want to use.
