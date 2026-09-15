# Leading Metrics (LM) SQL Skills Design

**Date:** 2026-05-19  
**Status:** Draft  
**Scope:** devlake_tools — cross-project (n8n-pulumi-poc + konflux-devlake-mcp)

---

## Overview

The n8n metrics dashboard computes 18 metric panels across three groups — PR Cycle Time,
First Time Pass Rate (FTPR), and Code Coverage — by running per-repo SQL queries and
aggregating the results in JavaScript code nodes. This spec designs a set of **Cursor agent
skills** that replicate the same metrics using pure SQL, supporting any product or team
already configured in the `n8n-pulumi-poc` dashboard, so a program manager (PM) can use
Cursor with the `user-konflux-devlake-mcp-prd` MCP server to generate trend reports without
needing access to the dashboard.

**Scope is driven by the `n8n-pulumi-poc` product/team JSON files** — the agent reads them
to determine which blueprint IDs to filter on, rather than hard-coding values into the
skills. This means the skills work for any of the 20+ products configured in that repo
(Konflux, Konveyor, OpenShift Pipelines, AppSRE, etc.) with no changes to the skill files
themselves.

### Goals

1. Extract the full SQL + computation logic from all 18 n8n metric nodes into SKILL.md files.
2. Support **product-level aggregation** for any product defined in `n8n-pulumi-poc`
   (e.g. Konflux = all ~17 team blueprints combined).
3. Support **team-level** queries (single team JSON file = single blueprint ID).
4. Enable a PM to say "show me FTPR for Konflux for the last 30 days" in Cursor and get a
   structured markdown report with the same numbers the n8n dashboard would show.

### Non-goals

- MCP Python tool implementations (deferred).
- Exact chart/visualization format parity (reports use markdown tables and trend commentary).
- Real-time streaming data (queries run against the DevLake MySQL snapshot).

---

## Delivery

Three SKILL.md files, one per metric group, stored in the `konflux-devlake-mcp` repo:

```
konflux-devlake-mcp/skills/
  lm-pr-metrics/SKILL.md          # 11 PR Cycle Time metrics
  lm-ftpr-metrics/SKILL.md        # 3 FTPR metrics
  lm-coverage-metrics/SKILL.md    # 4 Code Coverage metrics
```

---

## Program Manager Setup & Usage Guide

This section is written for program managers and team leads who want to run Konflux metrics
in Cursor without developer assistance.

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **Cursor IDE** | Any recent version. [cursor.com](https://cursor.com) |
| **MCP server access** | The `user-konflux-devlake-mcp-prd` MCP server must be configured in your Cursor settings (see below). Contact the DevOps/tooling team if you do not have credentials. |
| **`konflux-devlake-mcp` repo** | Clone this repo locally. The skills live inside it. |
| **`n8n-pulumi-poc` repo** | Clone this repo alongside the above. The product and team JSON files inside it are the source of truth for scope (blueprint IDs). |

### Step 1 — Clone both repos

```bash
# Skills live here
git clone https://github.com/redhat-konflux/konflux-devlake-mcp.git
cd konflux-devlake-mcp

# Product/team scope config lives here — clone into the same parent directory
cd ..
git clone https://github.com/redhat-konflux/n8n-pulumi-poc.git
```

The agent expects to find:
- `n8n-pulumi-poc/containers/dashboard/products/<product-id>.json` — for product-level queries
- `n8n-pulumi-poc/containers/dashboard/teams/<team-id>.json` — for team-level queries

### Step 2 — Install the skills into Cursor

Cursor discovers agent skills from `~/.cursor/skills/`. Copy (or symlink) each skill
directory there:

```bash
# Create the skills directory if it does not exist
mkdir -p ~/.cursor/skills

# Copy all three leading-metrics skills
cp -r skills/lm-pr-metrics     ~/.cursor/skills/
cp -r skills/lm-ftpr-metrics   ~/.cursor/skills/
cp -r skills/lm-coverage-metrics ~/.cursor/skills/
```

To update skills when the repo changes, re-run the `cp` commands or use symlinks:

```bash
ln -sf "$(pwd)/skills/lm-pr-metrics"      ~/.cursor/skills/lm-pr-metrics
ln -sf "$(pwd)/skills/lm-ftpr-metrics"    ~/.cursor/skills/lm-ftpr-metrics
ln -sf "$(pwd)/skills/lm-coverage-metrics" ~/.cursor/skills/lm-coverage-metrics
```

### Step 3 — Configure the MCP server in Cursor

Open **Cursor → Settings → MCP** (or edit `~/.cursor/mcp.json`) and add the
`user-konflux-devlake-mcp-prd` server. Your tooling team should provide the connection
block; it looks like:

```json
{
  "mcpServers": {
    "user-konflux-devlake-mcp-prd": {
      "url": "https://<mcp-server-host>/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

Restart Cursor after saving. You can verify connectivity by asking:

> "Use the DevLake MCP to list available databases."

### Step 4 — Open a Cursor chat and ask for metrics

Start a new Cursor chat (Agent mode). The skills are automatically available. Use natural
language — the agent will invoke the right skill and run the SQL queries on your behalf.

#### Example prompts

**PR Cycle Time — last 30 days (Konflux product level)**

> "Show me PR cycle time metrics for Konflux for the last 30 days. Include total PRs,
> median cycle time, and the weekly trend."

**FTPR — specific date range**

> "What is the First Time Pass Rate for Konflux from 2026-04-01 to 2026-04-30?
> Show the weekly trend and the pass/fail breakdown."

**Code Coverage — current state**

> "Give me the current code coverage summary for all Konflux teams. Include average
> overall coverage, patch coverage, and which teams are below 60%."

**Combined report**

> "Generate a Konflux leading metrics report for the last 4 weeks. Include PR cycle time
> key metrics, FTPR trend, and coverage by team. Format it as a markdown table I can
> paste into a Confluence page."

**Team-level (single team)**

> "Show PR cycle time metrics for the Konflux Build team for the last 30 days."

**Another product entirely**

> "Show me FTPR for the OpenShift Pipelines product for the last 4 weeks."

### What the agent does under the hood

1. Reads the appropriate SKILL.md (e.g. `lm-ftpr-metrics`).
2. Reads `n8n-pulumi-poc/containers/dashboard/products/<product-id>.json` (or `teams/<team-id>.json`) to extract the `blueprintids` (or `blueprintid`) for the requested dashboard type.
3. Substitutes those IDs and your `from_date` / `to_date` into the SQL templates.
4. Calls `mcp_konflux-devlake-mcp-prd_execute_query` one or more times.
5. Aggregates and formats the results as a markdown report.

You do not need to write any SQL, know DevLake table names, or look up blueprint IDs.

### Keeping skills and scope up to date

**Skills** (in `konflux-devlake-mcp`): update when SQL logic changes.

```bash
cd konflux-devlake-mcp && git pull
```

**Scope config** (in `n8n-pulumi-poc`): update when teams or products are added/removed.

```bash
cd n8n-pulumi-poc && git pull
```

If you used symlinks in Step 2, a `git pull` of `konflux-devlake-mcp` is all that's needed for skill updates — no file copying required.

---

## Product-Level Aggregation

### How n8n does it

When "All Repos" is selected on a product view in the dashboard:

1. The frontend collects every `owner/name` pair from every team JSON in the product.
2. It sends them as arrays to the n8n webhook: `?owner[]=konflux-ci&name[]=build-service&...`
3. The n8n `Split Out` node emits one execution item per repo.
4. Each SQL node runs once per repo, filtered by `r.name = '<owner>/<repo>'` AND
   `bp.id = <blueprintid>`.
5. The code node collects all results from all repos via `$("Get PRs").all()` and computes
   aggregate metrics across the full set.

### How SQL skills do it

Replace the per-repo loop with a single SQL join using blueprint IDs sourced from the
`n8n-pulumi-poc` JSON config files:

```sql
-- Product-level: agent reads blueprintids from products/<product-id>.json
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN ({blueprintids})  -- substituted from JSON at query time
```

For **team-level** queries, the agent reads `blueprintid` (singular) from the team JSON:

```sql
-- Team-level: agent reads blueprintid from teams/<team-id>.json
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id = {blueprintid}  -- single ID from team JSON
```

### Scope resolution — JSON file structure

**Product JSON** (`containers/dashboard/products/<product-id>.json`):

```json
{
  "id": "konflux",
  "name": "Konflux",
  "teams": ["collective", "devprod", "konflux-build", ...],
  "dashboards": [
    {
      "id": "prcycletime",
      "type": "prcycletime",
      "blueprintids": ["2", "4", "5", "6", "7", "8", "9", "10",
                       "13", "17", "20", "87", "89", "90", "96", "101", "104"]
    }
  ]
}
```

The agent extracts `blueprintids` from the dashboard entry whose `type` matches the
requested metric group:
- PR Cycle Time → `type: "prcycletime"`
- FTPR → `type: "ftpr"`
- Code Coverage → `type: "codecoverage"`

**Team JSON** (`containers/dashboard/teams/<team-id>.json`):

```json
{
  "id": "konflux-build",
  "name": "Konflux Build Team",
  "dashboards": [
    { "type": "prcycletime", "blueprintid": "5" },
    { "type": "ftpr",        "blueprintid": "5" },
    { "type": "codecoverage","blueprintid": "2" }
  ]
}
```

The agent extracts the single `blueprintid` from the matching dashboard entry.

### Supported products (as of May 2026)

Any product or team with a JSON file under `containers/dashboard/products/` or
`containers/dashboard/teams/` in `n8n-pulumi-poc` is supported — including Konflux,
Konveyor, OpenShift Pipelines, Developer Sandbox, AppSRE, LightSpeed, and 15+ others.
No changes to the skill files are needed to use a different product.

---

## Shared SQL Patterns

These snippets are reused across all skills. The skill files reference them as named patterns.

### Bot Filter (PR author)

Excludes AI/bot-authored PRs matching the same rules as the n8n `isAutogenerated()` function.
Also excludes draft PRs.

```sql
-- Bot/autogenerated author filter (applies to pr.author_name)
AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
AND pr.is_draft = 0
```

Note: The conditional-AI tier (github-actions[bot] + content pattern) is collapsed into the
broader `github-actions` exclusion. This is conservative (excludes all github-actions[bot]
authors) and matches the n8n legacy fallback behavior.

### Bot Filter (reviewer)

Applies to `pull_request_comments.author_name` for review-based metrics.

```sql
AND prc_author NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
```

### Date Range Filter

n8n receives `from`/`to` as Unix timestamps. SQL equivalents:

```sql
-- Closed/merged PRs in range:
AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'

-- Opened PRs in range:
AND pr.created_date >= '{from_date}'
AND pr.created_date <= '{to_date}'
```

Use ISO 8601 format: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`.

### Median Calculation (MySQL 8.0+, subquery form — no CTEs)

MySQL has no `MEDIAN()` function. Use `ROW_NUMBER()` in a nested derived table subquery.
**Do not use CTEs** — `execute_query` rejects any SQL not starting with `SELECT` (the security
layer blocks `WITH`).

```sql
-- Subquery (derived table) form — wraps the base query and the window functions:
SELECT ROUND(AVG(val), 2) AS median_val
FROM (
    SELECT val,
           ROW_NUMBER() OVER (ORDER BY val) AS rn,
           COUNT(*) OVER ()                 AS cnt
    FROM (
        /* ... your base SELECT producing the `val` column ... */
    ) base_vals
    WHERE val >= 0
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));
```

For counts that need to be returned alongside the median, run two separate queries (one
`COUNT(*)`, one median subquery) and let the agent combine the results.

### First Commit SHA per PR

Used for FTPR. Finds the earliest commit by authored date.

```sql
LEFT JOIN (
    SELECT prc.pull_request_id,
           prc.commit_sha,
           ROW_NUMBER() OVER (
               PARTITION BY prc.pull_request_id
               ORDER BY prc.commit_authored_date ASC
           ) AS rn
    FROM lake.pull_request_commits prc
) fc ON pr.id = fc.pull_request_id AND fc.rn = 1
```

---

## Metric Group 1: PR Cycle Time (11 metrics)

**Source nodes:** `node-metric_pr_key_metrics.js`, `node-metric_pr_cycle_time_over_time.js`,
`node-metric_pr_stages.js`, `node-metric_pr_flow.js`, `node-metric_pr_activity.js`,
`node-metric_pr_productivity.js`, `node-metric_pr_sandbox_key_metrics.js`,
`node-metric_pr_size.js`, `node-metric_pr_cross_repo.js`, `node-metric_pr_zscore.js`,
`node-metric_pr_zscore_lookback.js`

**Data sources:** `lake.pull_requests`, `lake.pull_request_commits`,
`lake.pull_request_comments`, `lake.repos`, `lake.project_mapping`,
`lake._devlake_blueprints`

### 1.1 PR Key Metrics

**Metrics:** Total Closed PRs, Median Cycle Time (hours), Opened PRs, Median Interaction Time

**Cycle time definition:** `created_date → COALESCE(merged_date, closed_date)` in hours.
This is the n8n definition (not DevLake's `project_pr_metrics` coding/pickup/review split).

**Interaction time definition:** Median of medians — for each PR, the median time (hours)
between consecutive review comments; then the median of those per-PR medians.

```sql
-- Query A1: Total Closed PRs (separate query — CTEs are blocked by execute_query)
SELECT COUNT(*) AS total_closed_prs
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND (pr.merged_date IS NOT NULL OR pr.closed_date IS NOT NULL)
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
  AND pr.created_date IS NOT NULL;

-- Query A2: Median Cycle Time (subquery form — no CTEs)
SELECT ROUND(AVG(cycle_hours), 2) AS median_cycle_time_hours
FROM (
    SELECT cycle_hours,
           ROW_NUMBER() OVER (ORDER BY cycle_hours) AS rn,
           COUNT(*) OVER ()                         AS cnt
    FROM (
        SELECT TIMESTAMPDIFF(MINUTE, pr.created_date,
                   COALESCE(pr.merged_date, pr.closed_date)) / 60.0 AS cycle_hours
        FROM lake.pull_requests pr
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND pr.status IN ('MERGED', 'CLOSED')
          AND (pr.merged_date IS NOT NULL OR pr.closed_date IS NOT NULL)
          AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
          AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
          AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
          AND pr.is_draft = 0
          AND pr.created_date IS NOT NULL
    ) base_prs WHERE cycle_hours >= 0
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));

-- Query B: Opened PRs (created in the selected range)
SELECT COUNT(*) AS opened_prs
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.created_date >= '{from_date}'
  AND pr.created_date <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0;

-- Query C: Median Interaction Time (subquery form — no CTEs)
SELECT ROUND(AVG(avg_interval_hours), 2) AS median_interaction_time_hours
FROM (
    SELECT avg_interval_hours,
           ROW_NUMBER() OVER (ORDER BY avg_interval_hours) AS rn,
           COUNT(*) OVER ()                                AS cnt
    FROM (
        SELECT pull_request_id,
               AVG(interval_hours) AS avg_interval_hours
        FROM (
            SELECT pull_request_id,
                   TIMESTAMPDIFF(MINUTE, prev_date, created_date) / 60.0 AS interval_hours
            FROM (
                SELECT prc.pull_request_id,
                       prc.created_date,
                       LAG(prc.created_date) OVER (
                           PARTITION BY prc.pull_request_id
                           ORDER BY prc.created_date ASC
                       ) AS prev_date
                FROM lake.pull_request_comments prc
                JOIN (
                    SELECT pr.id AS pr_id
                    FROM lake.pull_requests pr
                    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
                    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
                    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
                      AND pr.status IN ('MERGED', 'CLOSED')
                      AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
                      AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
                      AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
                      AND pr.is_draft = 0
                ) pr_scope ON prc.pull_request_id = pr_scope.pr_id
                WHERE prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
            ) review_events
            WHERE prev_date IS NOT NULL AND TIMESTAMPDIFF(MINUTE, prev_date, created_date) >= 0
        ) intervals
        GROUP BY pull_request_id
        HAVING COUNT(*) >= 1
    ) pr_avg_interval
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));
```

**Approximation note:** n8n computes the true median-of-medians. Query C uses
AVG-of-intervals per PR then median of those averages. Direction and magnitude are correct;
exact values may differ by a small amount.

---

### 1.2 PR Cycle Time Over Time

**Metric:** Daily median cycle time with 7-day rolling average.

```sql
-- Daily median cycle time (subquery form — no CTEs)
SELECT close_day,
       ROUND(AVG(cycle_hours), 2) AS daily_median_cycle_hours,
       COUNT(*)                   AS pr_count
FROM (
    SELECT close_day, cycle_hours,
           ROW_NUMBER() OVER (PARTITION BY close_day ORDER BY cycle_hours) AS rn,
           COUNT(*) OVER (PARTITION BY close_day)                          AS cnt
    FROM (
        SELECT DATE(COALESCE(pr.merged_date, pr.closed_date)) AS close_day,
               TIMESTAMPDIFF(MINUTE, pr.created_date,
                   COALESCE(pr.merged_date, pr.closed_date)) / 60.0 AS cycle_hours
        FROM lake.pull_requests pr
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND pr.status IN ('MERGED', 'CLOSED')
          AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
          AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
          AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
          AND pr.is_draft = 0
          AND TIMESTAMPDIFF(MINUTE, pr.created_date,
              COALESCE(pr.merged_date, pr.closed_date)) >= 0
    ) base_prs
) daily_ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
GROUP BY close_day
ORDER BY close_day;
```

**Post-processing:** The agent computes the 7-day rolling average from the returned rows
(sum of last 7 `daily_median_cycle_hours` / 7).

---

### 1.3 PR Stages (Cycle Time Breakdown)

**Metrics:** Median First Review time, Median First Approval time, Median Integration time.

- **First Review:** PR `created_date` → first non-bot review comment date
- **First Approval:** PR `created_date` → first APPROVED review or Prow LGTM comment
- **Integration:** First approval → `merged_date`

```sql
-- First Review time (created → first non-bot review) — subquery form
SELECT ROUND(AVG(hours), 2) AS median_first_review_hours
FROM (
    SELECT hours,
           ROW_NUMBER() OVER (ORDER BY hours) AS rn,
           COUNT(*) OVER ()                   AS cnt
    FROM (
        SELECT TIMESTAMPDIFF(MINUTE, p.created_date, fr.first_review_date) / 60.0 AS hours
        FROM (
            SELECT pr.id, pr.created_date
            FROM lake.pull_requests pr
            JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
            JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
            WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
              AND pr.status IN ('MERGED', 'CLOSED')
              AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
              AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
              AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
              AND pr.is_draft = 0
        ) p
        JOIN (
            SELECT prc.pull_request_id, MIN(prc.created_date) AS first_review_date
            FROM lake.pull_request_comments prc
            WHERE prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
            GROUP BY prc.pull_request_id
        ) fr ON p.id = fr.pull_request_id
        WHERE fr.first_review_date > p.created_date
    ) pickup_times WHERE hours >= 0
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));

-- First Approval time (created → first APPROVED or /lgtm) — subquery form
SELECT ROUND(AVG(hours), 2) AS median_first_approval_hours
FROM (
    SELECT hours,
           ROW_NUMBER() OVER (ORDER BY hours) AS rn,
           COUNT(*) OVER ()                   AS cnt
    FROM (
        SELECT TIMESTAMPDIFF(MINUTE, p.created_date, fa.first_approval_date) / 60.0 AS hours
        FROM (
            SELECT pr.id, pr.created_date
            FROM lake.pull_requests pr
            JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
            JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
            WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
              AND pr.status IN ('MERGED', 'CLOSED')
              AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
              AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
              AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
              AND pr.is_draft = 0
        ) p
        JOIN (
            SELECT prc.pull_request_id, MIN(prc.created_date) AS first_approval_date
            FROM lake.pull_request_comments prc
            WHERE prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
              AND (prc.type = 'REVIEW' AND prc.body LIKE '%APPROVED%'
                   OR prc.body REGEXP '^/lgtm')
            GROUP BY prc.pull_request_id
        ) fa ON p.id = fa.pull_request_id
        WHERE fa.first_approval_date > p.created_date
    ) approval_times WHERE hours >= 0
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));
```

**Integration time** = `median_cycle_time` (Query A in 1.1) minus `median_first_approval_hours`.
Or computed separately by joining merged PRs to their first approval and taking
`merged_date - first_approval_date`.

---

### 1.4 PR Flow (Sankey)

**Metrics:** Count of PRs transitioning through states: Opened → Reviewed → Approved →
Merged | Abandoned. Expressed as percentages of total opened PRs.

```sql
-- PR Flow — subquery form (no CTEs)
SELECT
    COUNT(*)                                                         AS total_opened,
    SUM(CASE WHEN r.pull_request_id IS NOT NULL THEN 1 ELSE 0 END)  AS reviewed,
    SUM(CASE WHEN a.pull_request_id IS NOT NULL THEN 1 ELSE 0 END)  AS approved,
    SUM(CASE WHEN p.status = 'MERGED' THEN 1 ELSE 0 END)            AS merged,
    SUM(CASE WHEN p.status = 'CLOSED' AND p.merged_date IS NULL THEN 1 ELSE 0 END) AS abandoned
FROM (
    SELECT pr.id, pr.status, pr.merged_date
    FROM lake.pull_requests pr
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
      AND pr.status IN ('MERGED', 'CLOSED')
      AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
      AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
      AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
      AND pr.is_draft = 0
) p
LEFT JOIN (
    SELECT DISTINCT prc.pull_request_id
    FROM lake.pull_request_comments prc
    WHERE prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
) r ON p.id = r.pull_request_id
LEFT JOIN (
    SELECT DISTINCT prc.pull_request_id
    FROM lake.pull_request_comments prc
    WHERE prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
      AND (prc.type = 'REVIEW' AND prc.body LIKE '%APPROVED%'
           OR prc.body REGEXP '^/lgtm')
) a ON p.id = a.pull_request_id;
```

---

### 1.5 PR Activity (Investment Focus)

**Metric:** Top 5 repositories by closed PR count in the selected period.

```sql
SELECT r.name AS repository,
       COUNT(DISTINCT pr.id) AS closed_prs
FROM lake.pull_requests pr
JOIN lake.repos r ON r.id = pr.base_repo_id
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
GROUP BY r.name
ORDER BY closed_prs DESC
LIMIT 5;
```

---

### 1.6 PR Productivity

**Metric:** Merged % vs Closed-without-merge %. Shows whether PRs are being accepted or
abandoned.

```sql
SELECT
    SUM(CASE WHEN pr.status = 'MERGED' OR pr.merged_date IS NOT NULL THEN 1 ELSE 0 END) AS merged_count,
    SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END)    AS closed_without_merge,
    COUNT(*)                                                                              AS total,
    ROUND(SUM(CASE WHEN pr.status = 'MERGED' OR pr.merged_date IS NOT NULL THEN 1 ELSE 0 END)
          * 100.0 / COUNT(*), 1)                                                         AS merged_pct,
    ROUND(SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END)
          * 100.0 / COUNT(*), 1)                                                         AS abandoned_pct
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0;
```

---

### 1.7 PR Sandbox Key Metrics (Median Reviewers per PR)

**Metric:** Median number of distinct reviewers per PR in the selected period.

```sql
-- Median reviewers per PR — subquery form (no CTEs)
SELECT ROUND(AVG(reviewer_count), 2) AS median_reviewers_per_pr
FROM (
    SELECT reviewer_count,
           ROW_NUMBER() OVER (ORDER BY reviewer_count) AS rn,
           COUNT(*) OVER ()                            AS cnt
    FROM (
        SELECT prc.pull_request_id,
               COUNT(DISTINCT prc.author_name) AS reviewer_count
        FROM lake.pull_request_comments prc
        JOIN lake.pull_requests pr ON pr.id = prc.pull_request_id
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND pr.created_date >= '{from_date}'
          AND pr.created_date <= '{to_date}'
          AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
          AND pr.is_draft = 0
          AND prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
        GROUP BY prc.pull_request_id
    ) reviewer_counts
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2));
```

---

### 1.8 PR Size Distribution

**Metric:** Additions vs deletions per PR (scatter data). For reports: distribution by size
bucket.

```sql
SELECT
    CASE
        WHEN (pr.additions + pr.deletions) <= 50   THEN 'XS (1-50 lines)'
        WHEN (pr.additions + pr.deletions) <= 200  THEN 'S (51-200 lines)'
        WHEN (pr.additions + pr.deletions) <= 500  THEN 'M (201-500 lines)'
        WHEN (pr.additions + pr.deletions) <= 1000 THEN 'L (501-1000 lines)'
        ELSE 'XL (>1000 lines)'
    END AS size_bucket,
    COUNT(*)           AS pr_count,
    ROUND(AVG(pr.additions + pr.deletions), 0) AS avg_lines_changed
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
GROUP BY size_bucket
ORDER BY FIELD(size_bucket,
    'XS (1-50 lines)', 'S (51-200 lines)', 'M (201-500 lines)',
    'L (501-1000 lines)', 'XL (>1000 lines)');
```

---

### 1.9 Cross-Repo Comparison

**Metric:** Per-repository table with Median Cycle Time, Opened, Closed, First Review (hrs),
First Approval (hrs), Integration (hrs), Abandonment %, Reviewers/PR.

```sql
-- Per-repo cycle time and PR counts
SELECT
    r.name                                                             AS repository,
    COUNT(DISTINCT pr.id)                                             AS closed_prs,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, pr.created_date,
        COALESCE(pr.merged_date, pr.closed_date)) / 60.0), 2)        AS avg_cycle_hours,
    ROUND(SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END)
          * 100.0 / COUNT(*), 1)                                      AS abandonment_pct
FROM lake.pull_requests pr
JOIN lake.repos r ON r.id = pr.base_repo_id
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
GROUP BY r.name
ORDER BY avg_cycle_hours DESC
LIMIT 30;
```

**Note:** True per-repo median requires a more complex nested query. This returns AVG as
an approximation. For exact median per repo, add ROW_NUMBER PARTITION BY r.name.

---

### 1.10 PR Z-Score

**Metric:** Classify PRs as Fast (z < -1), Average (-1 ≤ z ≤ 1), or Slow (z > 1) based on
log-normal z-score of cycle time against a 90-day baseline.

**Two-step process:**

```sql
-- Step 1 (Lookback baseline): Get mu_log and sigma_log from 90-day window — subquery form
SELECT
    AVG(log_val)                                                    AS mu_log,
    SQRT(AVG(log_val * log_val) - AVG(log_val) * AVG(log_val))     AS sigma_log,
    COUNT(*)                                                        AS baseline_pr_count
FROM (
    SELECT LOG(cycle_hours + 1) AS log_val
    FROM (
        SELECT TIMESTAMPDIFF(MINUTE, pr.created_date,
                   COALESCE(pr.merged_date, pr.closed_date)) / 60.0 AS cycle_hours
        FROM lake.pull_requests pr
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND pr.status IN ('MERGED', 'CLOSED')
          AND COALESCE(pr.merged_date, pr.closed_date) >= DATE_SUB('{to_date}', INTERVAL 90 DAY)
          AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
          AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
          AND pr.is_draft = 0
          AND TIMESTAMPDIFF(MINUTE, pr.created_date,
              COALESCE(pr.merged_date, pr.closed_date)) > 0
    ) baseline_prs
) log_vals;

-- Step 2 (Classification): Classify PRs in the selected period
-- Use mu_log and sigma_log from Step 1, substituted as parameters below
SELECT
    CASE
        WHEN (LOG(cycle_hours + 1) - {mu_log}) / NULLIF({sigma_log}, 0) < -1 THEN 'Fast'
        WHEN (LOG(cycle_hours + 1) - {mu_log}) / NULLIF({sigma_log}, 0) > 1  THEN 'Slow'
        ELSE 'Average'
    END AS category,
    COUNT(*) AS pr_count,
    ROUND(AVG(cycle_hours / 24), 1) AS median_days
FROM (
    SELECT TIMESTAMPDIFF(MINUTE, pr.created_date,
               COALESCE(pr.merged_date, pr.closed_date)) / 60.0 AS cycle_hours
    FROM lake.pull_requests pr
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
      AND pr.status IN ('MERGED', 'CLOSED')
      AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
      AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
      AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
      AND pr.is_draft = 0
      AND TIMESTAMPDIFF(MINUTE, pr.created_date,
          COALESCE(pr.merged_date, pr.closed_date)) > 0
) prs
GROUP BY category;
```

---

## Metric Group 2: FTPR — First Time Pass Rate (3 metrics)

**Source nodes:** `node-metric_ftpr_key_metrics.js`, `node-metric_ftpr_over_time.js`,
`node-metric_ftpr_pass_fail.js`

**Data sources:** `lake.pull_requests`, `lake.pull_request_commits`,
`lake.cicd_pipelines`, `lake.cicd_pipeline_commits`, `lake.ci_test_jobs`,
`lake.repos`, `lake.project_mapping`, `lake._devlake_blueprints`

### FTPR Definition

FTPR = (Merged PRs where ALL CI pipelines on the **first commit** passed) / (Total merged
PRs with CI data) × 100

Pipeline deduplication: if the same pipeline name ran multiple times on a commit, keep only
the **latest** result. Non-CI events (empty result field) are excluded.

### 2.1 FTPR Key Metrics

**Implementation strategy:** The 6-CTE chain from the design notes is too deeply nested to
be readable in a single subquery under the 10KB limit. Split into **two `execute_query`
calls** and let the agent join the results in-memory.

**Query 2.1-A: PRs with first-commit SHA** (returns `pr_id`, `merged_date`, `first_commit_sha`)

```sql
SELECT pr.id AS pr_id,
       pr.merged_date,
       fc.commit_sha AS first_commit_sha
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
LEFT JOIN (
    SELECT prc.pull_request_id, prc.commit_sha,
           ROW_NUMBER() OVER (PARTITION BY prc.pull_request_id
                              ORDER BY prc.commit_authored_date ASC) AS rn
    FROM lake.pull_request_commits prc
) fc ON pr.id = fc.pull_request_id AND fc.rn = 1
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status = 'MERGED'
  AND pr.merged_date >= '{from_date}'
  AND pr.merged_date <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0;
```

**Query 2.1-B: Deduped pipeline pass/fail per commit** (returns `commit_sha`, `all_passed`)

```sql
SELECT commit_sha,
       MIN(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) AS all_passed
FROM (
    SELECT commit_sha, pipeline_name, result,
           ROW_NUMBER() OVER (
               PARTITION BY commit_sha, pipeline_name
               ORDER BY finished_at DESC
           ) AS rn
    FROM (
        SELECT cpc.commit_sha, cp.name AS pipeline_name, cp.result,
               cp.finished_date AS finished_at
        FROM lake.cicd_pipeline_commits cpc
        JOIN lake.cicd_pipelines cp ON cpc.pipeline_id = cp.id
        JOIN lake.repos r ON cpc.repo_id = r.id
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND cp.status = 'DONE' AND cp.result != ''
        UNION ALL
        SELECT ctj.commit_sha, ctj.job_name AS pipeline_name, ctj.result,
               ctj.finished_at
        FROM lake.ci_test_jobs ctj
        JOIN lake.repos r ON r.name = CONCAT(ctj.organization, '/', ctj.repository)
        JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
        JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
        WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
          AND ctj.job_type IN ('prow', 'tekton')
          AND ctj.trigger_type = 'pull_request'
          AND ctj.result != ''
    ) all_pipelines
) latest_pipelines
WHERE rn = 1
GROUP BY commit_sha;
```

**Agent post-processing:** JOIN the two result sets on `first_commit_sha = commit_sha`,
then compute totals and FTPR %:

```
total_merged_prs   = len(A rows)
prs_with_ci_data   = count where B.all_passed IS NOT NULL
first_time_passes  = count where B.all_passed = 1
ftpr_pct           = first_time_passes / prs_with_ci_data * 100
```

---

### 2.2 FTPR Over Time

**Metric:** Weekly FTPR percentage with 4-week rolling average.

Re-use Query 2.1-A and 2.1-B. After joining in the agent, group by `YEARWEEK(merged_date)`:

```
week_key    = YEARWEEK of merged_date
total       = count of PRs per week
passes      = count where all_passed = 1 per week
with_ci     = count where all_passed IS NOT NULL per week
ftpr_pct    = passes / with_ci * 100
```

**Post-processing:** Agent computes 4-week rolling average from the weekly rows.

If a single-query form is preferred, Query 2.1-A can be run with a weekly GROUP BY as a
self-contained query that returns `week_key, pr_id, first_commit_sha` — then the agent
joins to 2.1-B results.

---

### 2.3 FTPR Pass/Fail Breakdown

Same result set as 2.1 agent post-processing. Present as:

```
passed       = first_time_passes
failed       = prs_with_ci_data - first_time_passes
no_ci_data   = total_merged_prs - prs_with_ci_data
ftpr_pct     = passed / (passed + failed) * 100
```

---

## Metric Group 3: Code Coverage (4 metrics)

**Source nodes:** `node-metric_coverage_key_metrics.js`, `node-metric_coverage_by_team.js`,
`node-metric_coverage_line_breakdown.js`, `node-metric_coverage_trend.js`

**Data sources:** `lake._tool_codecov_commit_coverages`, `lake._tool_codecov_comparisons`,
`lake._tool_codecov_commits`, `lake.project_mapping`, `lake.repos`

**Coverage table note:** `repo_id` in codecov tables uses `owner/repo` format (e.g.
`konflux-ci/build-service`). Product-level join uses repos table as bridge.

### Coverage Product-Level Join

```sql
-- Get all codecov repo_ids for the Konflux product
SELECT DISTINCT r.name AS codecov_repo_id
FROM lake.repos r
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104);
-- Results: list of 'owner/repo' strings for use in subsequent WHERE clauses
```

### 3.1 Coverage Key Metrics

**Metrics:** Avg Coverage (%), Avg Patch Coverage (%), Trend (start→end delta).

```sql
-- Latest overall coverage per repo
SELECT
    cc.repo_id,
    ROUND(cc.overall_coverage, 2) AS total_coverage,
    cc.hits, cc.misses, cc.partials
FROM lake._tool_codecov_commit_coverages cc
INNER JOIN (
    SELECT repo_id, MAX(commit_timestamp) AS max_ts
    FROM lake._tool_codecov_commit_coverages
    WHERE overall_coverage > 0
    GROUP BY repo_id
) latest ON cc.repo_id = latest.repo_id AND cc.commit_timestamp = latest.max_ts
WHERE cc.overall_coverage > 0
  AND cc.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
);

-- Avg patch coverage in period
SELECT
    comp.repo_id,
    ROUND(AVG(comp.patch), 2) AS avg_patch_coverage
FROM lake._tool_codecov_comparisons comp
INNER JOIN lake._tool_codecov_commits cm
    ON comp.repo_id = cm.repo_id AND comp.commit_sha = cm.commit_sha
WHERE comp.patch IS NOT NULL
  AND cm.commit_timestamp >= '{from_date}'
  AND cm.commit_timestamp <= '{to_date}'
  AND comp.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
GROUP BY comp.repo_id;

-- Earliest coverage in period (for trend delta)
SELECT
    cc.repo_id,
    ROUND(cc.overall_coverage, 2) AS earliest_coverage
FROM lake._tool_codecov_commit_coverages cc
INNER JOIN (
    SELECT repo_id, MIN(commit_timestamp) AS min_ts
    FROM lake._tool_codecov_commit_coverages
    WHERE overall_coverage > 0
      AND commit_timestamp >= '{from_date}'
    GROUP BY repo_id
) earliest ON cc.repo_id = earliest.repo_id AND cc.commit_timestamp = earliest.min_ts
WHERE cc.overall_coverage > 0
  AND cc.repo_id IN (
    SELECT DISTINCT r.name FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
);
```

**Post-processing:** Agent computes avg coverage = AVG of `total_coverage` across repos,
trend = avg(latest) - avg(earliest). Label: `+N%` if delta > 1, `-N%` if delta < -1,
`Stable` otherwise.

---

### 3.2 Coverage by Team

**Metric:** Average coverage per Konflux team (grouped by `project_name`).

```sql
SELECT
    pm.project_name,
    COUNT(DISTINCT cc.repo_id)                 AS repo_count,
    ROUND(AVG(cc.overall_coverage), 2)         AS avg_coverage
FROM lake._tool_codecov_commit_coverages cc
JOIN lake.repos r ON r.name = cc.repo_id
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
INNER JOIN (
    SELECT repo_id, MAX(commit_timestamp) AS max_ts
    FROM lake._tool_codecov_commit_coverages WHERE overall_coverage > 0
    GROUP BY repo_id
) latest ON cc.repo_id = latest.repo_id AND cc.commit_timestamp = latest.max_ts
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND cc.overall_coverage > 0
GROUP BY pm.project_name
ORDER BY avg_coverage DESC;
```

**Post-processing:** Agent extracts team name from project_name using the last segment after
the last ` - ` delimiter (e.g., `Secureflow - Konflux - Build` → `Build`).

---

### 3.3 Coverage Line Breakdown

**Metric:** Total covered, partial, uncovered lines across all Konflux repos.

```sql
SELECT
    SUM(cc.hits)     AS total_covered,
    SUM(cc.partials) AS total_partial,
    SUM(cc.misses)   AS total_uncovered,
    SUM(cc.hits + cc.partials + cc.misses) AS total_lines
FROM lake._tool_codecov_commit_coverages cc
INNER JOIN (
    SELECT repo_id, MAX(commit_timestamp) AS max_ts
    FROM lake._tool_codecov_commit_coverages WHERE overall_coverage > 0
    GROUP BY repo_id
) latest ON cc.repo_id = latest.repo_id AND cc.commit_timestamp = latest.max_ts
WHERE cc.overall_coverage > 0
  AND cc.repo_id IN (
    SELECT DISTINCT r.name FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
);
```

---

### 3.4 Coverage Trend Over Time

**Metric:** Weekly average overall and patch coverage with 4-week rolling average.

```sql
-- Daily overall coverage (for weekly aggregation)
SELECT
    DATE(cc.commit_timestamp) AS date_val,
    ROUND(AVG(cc.overall_coverage), 2) AS daily_coverage_avg
FROM lake._tool_codecov_commit_coverages cc
WHERE cc.overall_coverage > 0
  AND cc.commit_timestamp >= '{from_date}'
  AND cc.commit_timestamp <= '{to_date}'
  AND cc.repo_id IN (
    SELECT DISTINCT r.name FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
GROUP BY DATE(cc.commit_timestamp)
ORDER BY DATE(cc.commit_timestamp);

-- Daily patch coverage
SELECT
    DATE(cm.commit_timestamp) AS date_val,
    ROUND(AVG(comp.patch), 2) AS daily_patch_avg
FROM lake._tool_codecov_comparisons comp
JOIN lake._tool_codecov_commits cm
    ON comp.repo_id = cm.repo_id AND comp.commit_sha = cm.commit_sha
WHERE comp.patch IS NOT NULL
  AND cm.commit_timestamp >= '{from_date}'
  AND cm.commit_timestamp <= '{to_date}'
  AND comp.repo_id IN (
    SELECT DISTINCT r.name FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
GROUP BY DATE(cm.commit_timestamp)
ORDER BY DATE(cm.commit_timestamp);
```

**Post-processing:** Agent aggregates daily → weekly, computes 4-week rolling average.

---

## Skill File Structure

Each SKILL.md follows this structure:

```
---
name: lm-{group}-metrics
description: {one-line purpose}
---

# LM {Group} Metrics Skill

## Purpose
## When to Use
## Parameters
## Available MCP Tools
## Konflux Product Blueprint IDs
## Bot Filter Pattern
## Queries
  ### {metric name}
    - Definition
    - SQL
    - Post-processing (if any)
    - Example output
## Report Template
  How to format results as markdown for PM consumption
## Interpretation Guide
  What trends to flag, healthy vs concerning thresholds
```

Skills live in `konflux-devlake-mcp/skills/`:
- `lm-pr-metrics/SKILL.md`
- `lm-ftpr-metrics/SKILL.md`
- `lm-coverage-metrics/SKILL.md`

---

## Implementation Notes

### execute_query SQL Constraints

The `execute_query` MCP tool passes queries through `security.py → validate_sql_query()`,
which enforces:

1. **Must start with `SELECT`** — `WITH` (CTEs) are rejected outright. All queries in the
   SKILL.md files must be written as nested subqueries / derived tables.
2. **No semicolons** — each `execute_query` call is a single statement; multi-statement
   batches are not possible.
3. **No SQL comments** (`--` or `/* */`) — strip all comments from production queries.
4. **Max query length: 10,000 characters** — keep queries under this limit; for complex
   multi-CTE queries, split into multiple `execute_query` calls and merge results in the
   agent.

**Impact on spec SQL examples:** The SQL blocks in sections 1.1 – 2.3 use CTEs for
readability. When implementing the SKILL.md files, every `WITH ... AS (SELECT ...) SELECT`
pattern must be rewritten as `SELECT ... FROM (SELECT ...) alias`. The window function
(`ROW_NUMBER()`, `LAG()`) expressions remain valid — they just live inside a derived table
rather than a named CTE.

### FTPR Product-Level Aggregation

Same join strategy as PR cycle time — `project_mapping` + blueprint ID filter applied at
two points:

1. On the **PR side**: `JOIN lake.project_mapping pm ON ... AND pm.row_id = pr.base_repo_id`
   → filters which PRs belong to Konflux.
2. On the **pipeline side**: `JOIN lake.repos r ... JOIN lake.project_mapping pm ON ... AND
   pm.row_id = r.id` → filters which CICD pipeline commits / ci_test_jobs belong to Konflux.

Both sides use `WHERE bp.id IN (...)`. The SQL examples in section 2.x already reflect this.

### Coverage Product-Level Aggregation

Coverage tables (`_tool_codecov_commit_coverages`, `_tool_codecov_comparisons`) use
`repo_id` as an `owner/repo` string (e.g. `konflux-ci/build-service`) — not the numeric
`repos.id`. Direct FK joins to `project_mapping` are therefore not possible.

Strategy: correlated `IN` subquery bridging through `repos.name`:

```sql
WHERE cc.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
```

For metrics that also need `project_name` (e.g. 3.2 Coverage by Team), use a direct
three-way JOIN with `repos r ON r.name = cc.repo_id` instead of the `IN` subquery, then
group by `pm.project_name`. The SQL in section 3.2 already uses this JOIN form.

The `IN` subquery form starts with `SELECT` at the outer level, so it passes the
`execute_query` security check.

### Approximations vs Exact n8n Logic

| Metric | Approximation | Impact |
|--------|--------------|--------|
| Median Interaction Time (1.1) | AVG-of-intervals per PR then median of AVGs | Small; directionally correct |
| Median per-repo (1.9) | AVG instead of median per repo | Small; use for trending not exact KPI |
| Conditional-AI bot filter | All github-actions[bot] excluded (not content-matched) | Conservative; slightly over-excludes |
| First Approval detection | Looks for APPROVED in comment body or /lgtm | May miss Prow-native LGTM label if not stored as comment |

### Coverage Table Caveat

The existing `get_codecov_coverage` MCP tool uses `lake._tool_codecov_coverages` (per-flag
coverage, with `flag_name`). The SQL skills use `lake._tool_codecov_commit_coverages` (overall
coverage per commit, the table referenced in the n8n dev guide SQL templates). These are
different tables and may return slightly different values. During implementation, verify
`_tool_codecov_commit_coverages` is populated for the target Konflux repos. If it is empty,
fall back to `_tool_codecov_coverages` aggregated across flags (take MAX coverage per repo).

### Blueprint ID Lookup — No Hardcoding in Skills

Blueprint IDs are **never hardcoded in the SKILL.md files**. The skill instructs the agent
to read them at query time from the `n8n-pulumi-poc` JSON files:

```
Step 1: Identify whether the request is product-level or team-level.
Step 2: Read the appropriate JSON file:
  - Product: n8n-pulumi-poc/containers/dashboard/products/<product-id>.json
  - Team:    n8n-pulumi-poc/containers/dashboard/teams/<team-id>.json
Step 3: Extract blueprintids (product) or blueprintid (team) for the dashboard type.
Step 4: Substitute into WHERE bp.id IN (...) in the SQL.
```

**If `n8n-pulumi-poc` is not cloned:** the skill should prompt the user to provide their
blueprint IDs manually, or fall back to a known product (e.g. Konflux default IDs).

**When a team is added to a product:** update only `n8n-pulumi-poc` (add the team's
blueprint ID to the product JSON). No changes to the SKILL.md files are needed — the agent
reads the updated JSON on the next run after `git pull`.

### MCP Tool to Use

```
mcp_konflux-devlake-mcp-prd_execute_query
```

All queries are SELECT-only and safe to run against the production DevLake database.
Use `LIMIT` clauses on large result sets to avoid timeouts (especially cross-repo queries).
