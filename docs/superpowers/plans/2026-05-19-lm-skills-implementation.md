# Leading Metrics SQL Skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create three SKILL.md files that let a Cursor agent run n8n-equivalent PR Cycle Time, FTPR, and Code Coverage metric queries against the DevLake MCP server, scoped to any product or team defined in `n8n-pulumi-poc`.

**Architecture:** Three markdown skill files under `skills/`, one per metric group. Each skill instructs the Cursor agent to (1) read blueprint IDs from the `n8n-pulumi-poc` product/team JSON, (2) substitute them into SQL templates, (3) call `mcp_konflux-devlake-mcp-prd_execute_query`, and (4) format results as a markdown report. No Python code is written — these are pure markdown instruction files.

**Tech Stack:** Markdown (SKILL.md format), MySQL 8.0 SQL (subquery form — no CTEs, no comments, no semicolons), DevLake `lake` schema, `n8n-pulumi-poc` JSON config files.

**Spec:** `docs/superpowers/specs/2026-05-19-lm-skills-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `skills/lm-pr-metrics/SKILL.md` | Create | 11 PR Cycle Time metrics |
| `skills/lm-ftpr-metrics/SKILL.md` | Create | 3 FTPR metrics |
| `skills/lm-coverage-metrics/SKILL.md` | Create | 4 Code Coverage metrics |

---

## Shared Reference — Bot Filter Pattern

Used in every skill's SQL. Applies to `pr.author_name` and reviewer `author_name`:

```
NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
```

Also always add `AND pr.is_draft = 0`.

## Shared Reference — execute_query Rules

The MCP `execute_query` tool enforces:
1. Query MUST start with `SELECT`
2. No `WITH` (CTEs) — use nested subqueries
3. No SQL comments (`--` or `/* */`)
4. No semicolons
5. Max 10,000 characters per query

## Shared Reference — Scope Resolution

Every skill must instruct the agent to resolve blueprint IDs from n8n-pulumi-poc JSON before running any SQL:

**Product-level:** Read `n8n-pulumi-poc/containers/dashboard/products/<product-id>.json`
→ find `dashboards` entry where `type` matches the skill group
→ extract `blueprintids` array (strings)
→ use as `WHERE bp.id IN (<comma-separated integers>)`

**Team-level:** Read `n8n-pulumi-poc/containers/dashboard/teams/<team-id>.json`
→ find `dashboards` entry where `type` matches the skill group
→ extract single `blueprintid` string
→ use as `WHERE bp.id = <integer>`

Dashboard type mapping:
- PR Cycle Time → `"prcycletime"`
- FTPR → `"ftpr"`
- Code Coverage → `"codecoverage"`

---

## Task 1: Create skills directory structure

**Files:**
- Create: `skills/lm-pr-metrics/` (directory)
- Create: `skills/lm-ftpr-metrics/` (directory)
- Create: `skills/lm-coverage-metrics/` (directory)

- [ ] **Step 1: Create the directories**

```bash
mkdir -p skills/lm-pr-metrics skills/lm-ftpr-metrics skills/lm-coverage-metrics
```

Expected: no output, exit 0.

- [ ] **Step 2: Verify**

```bash
ls skills/
```

Expected output:
```
lm-coverage-metrics  lm-ftpr-metrics  lm-pr-metrics
```

---

## Task 2: Create `skills/lm-pr-metrics/SKILL.md`

**Files:**
- Create: `skills/lm-pr-metrics/SKILL.md`

- [ ] **Step 1: Write the file** with the exact content below.

```markdown
---
name: lm-pr-metrics
description: PR Cycle Time leading metrics — total PRs, median cycle time, stages, flow, productivity, size, cross-repo comparison, z-score. Aggregates at product or team level using n8n-pulumi-poc JSON config.
---

# LM PR Metrics Skill

## Purpose

Run the 11 PR Cycle Time metric queries from the n8n leading-metrics dashboard against
the Konflux DevLake database and format results as a markdown report for program managers.

## When to Use

When a user asks for any of:
- PR cycle time, median cycle time, opened/closed PR counts
- PR stages (pickup time, approval time, integration time)
- PR flow (reviewed, approved, merged, abandoned percentages)
- PR productivity (merge rate vs abandonment)
- PR size distribution
- Cross-repo comparison
- Z-score classification (fast/average/slow PRs)
- Interaction time (time between review comments)

## Parameters

| Parameter | Required | Example | Notes |
|-----------|----------|---------|-------|
| `product_name` | One of these | `konflux` | ID from products/ JSON |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Before running any query, resolve the blueprint IDs:

**If product-level** (e.g. "show metrics for Konflux"):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `type` = `"prcycletime"`
3. Extract the `blueprintids` array — these are strings, convert to integers
4. Use: `WHERE bp.id IN (<ids>)`

**If team-level** (e.g. "show metrics for the Konflux Build team"):
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find the entry in `dashboards` where `type` = `"prcycletime"`
3. Extract the single `blueprintid` string — convert to integer
4. Use: `WHERE bp.id = <id>`

In all SQL below, replace `{BLUEPRINT_FILTER}` with the resolved WHERE clause.

## Bot Filter Pattern

Always apply to `pr.author_name`:
```
AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
AND pr.is_draft = 0
```

Always apply to reviewer `prc.author_name`:
```
AND prc.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
```

---

## Metric 1.1-A — Total Closed PRs

**Definition:** Count of merged or closed non-bot non-draft PRs whose close/merge date falls
within the selected range.

Run this query. Replace `{from_date}` and `{to_date}` with ISO dates. Replace the JOIN and
WHERE lines with the resolved scope from Step 0.

```sql
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
  AND pr.created_date IS NOT NULL
```

**Output:** Single row with `total_closed_prs` integer.

---

## Metric 1.1-B — Median Cycle Time (hours)

**Definition:** Median of `(close/merge date − created date)` in hours across all closed PRs
in range. Cycle time = `created_date → COALESCE(merged_date, closed_date)`.

```sql
SELECT ROUND(AVG(cycle_hours), 2) AS median_cycle_time_hours
FROM (
    SELECT cycle_hours,
           ROW_NUMBER() OVER (ORDER BY cycle_hours) AS rn,
           COUNT(*) OVER () AS cnt
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
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
```

**Output:** Single row with `median_cycle_time_hours` decimal.

---

## Metric 1.1-C — Opened PRs

**Definition:** Count of non-bot non-draft PRs whose `created_date` falls within the range.

```sql
SELECT COUNT(*) AS opened_prs
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.created_date >= '{from_date}'
  AND pr.created_date <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
```

**Output:** Single row with `opened_prs` integer.

---

## Metric 1.1-D — Median Interaction Time (hours)

**Definition:** For each PR, compute the median time (hours) between consecutive non-bot
review comments. Then take the median of those per-PR medians across all PRs in range.
**Note:** This is an approximation — uses AVG of intervals per PR, then median of those AVGs.

```sql
SELECT ROUND(AVG(avg_interval_hours), 2) AS median_interaction_time_hours
FROM (
    SELECT avg_interval_hours,
           ROW_NUMBER() OVER (ORDER BY avg_interval_hours) AS rn,
           COUNT(*) OVER () AS cnt
    FROM (
        SELECT pull_request_id, AVG(interval_hours) AS avg_interval_hours
        FROM (
            SELECT pull_request_id,
                   TIMESTAMPDIFF(MINUTE, prev_date, created_date) / 60.0 AS interval_hours
            FROM (
                SELECT prc.pull_request_id, prc.created_date,
                       LAG(prc.created_date) OVER (
                           PARTITION BY prc.pull_request_id ORDER BY prc.created_date ASC
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
        GROUP BY pull_request_id HAVING COUNT(*) >= 1
    ) pr_avg_interval
) ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
```

**Output:** Single row with `median_interaction_time_hours` decimal.

---

## Metric 1.2 — Daily Median Cycle Time (trend)

**Definition:** Per-day median cycle time. Agent computes 7-day rolling average from results.

```sql
SELECT close_day, ROUND(AVG(cycle_hours), 2) AS daily_median_cycle_hours, COUNT(*) AS pr_count
FROM (
    SELECT close_day, cycle_hours,
           ROW_NUMBER() OVER (PARTITION BY close_day ORDER BY cycle_hours) AS rn,
           COUNT(*) OVER (PARTITION BY close_day) AS cnt
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
          AND TIMESTAMPDIFF(MINUTE, pr.created_date, COALESCE(pr.merged_date, pr.closed_date)) >= 0
    ) base_prs
) daily_ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
GROUP BY close_day ORDER BY close_day
```

**Post-processing:** For each row, compute `rolling_7d_avg` = mean of `daily_median_cycle_hours`
for the current day and the 6 preceding days in the result set. Present as a table with
columns: `date`, `daily_median_hours`, `rolling_7d_avg`, `pr_count`.

---

## Metric 1.3-A — Median First Review Time (hours)

**Definition:** Median of `(first non-bot review comment date − PR created_date)` in hours.

```sql
SELECT ROUND(AVG(hours), 2) AS median_first_review_hours
FROM (
    SELECT hours,
           ROW_NUMBER() OVER (ORDER BY hours) AS rn,
           COUNT(*) OVER () AS cnt
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
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
```

---

## Metric 1.3-B — Median First Approval Time (hours)

**Definition:** Median of `(first APPROVED review or /lgtm comment date − PR created_date)`.

```sql
SELECT ROUND(AVG(hours), 2) AS median_first_approval_hours
FROM (
    SELECT hours,
           ROW_NUMBER() OVER (ORDER BY hours) AS rn,
           COUNT(*) OVER () AS cnt
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
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
```

**Integration Time:** Report as `median_cycle_time_hours − median_first_approval_hours`.

---

## Metric 1.4 — PR Flow

**Definition:** Of all closed PRs in range — how many were reviewed, approved, merged, abandoned?

```sql
SELECT
    COUNT(*) AS total_opened,
    SUM(CASE WHEN r.pull_request_id IS NOT NULL THEN 1 ELSE 0 END) AS reviewed,
    SUM(CASE WHEN a.pull_request_id IS NOT NULL THEN 1 ELSE 0 END) AS approved,
    SUM(CASE WHEN p.status = 'MERGED' THEN 1 ELSE 0 END) AS merged,
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
) a ON p.id = a.pull_request_id
```

**Post-processing:** Express each count as % of `total_opened`.

---

## Metric 1.5 — PR Activity (Top Repos)

**Definition:** Top 10 repositories by closed PR count in the selected period.

```sql
SELECT r.name AS repository, COUNT(DISTINCT pr.id) AS closed_prs
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
GROUP BY r.name ORDER BY closed_prs DESC LIMIT 10
```

---

## Metric 1.6 — PR Productivity

**Definition:** Merged % vs closed-without-merge (abandoned) % of all closed PRs in range.

```sql
SELECT
    SUM(CASE WHEN pr.status = 'MERGED' OR pr.merged_date IS NOT NULL THEN 1 ELSE 0 END) AS merged_count,
    SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END) AS abandoned_count,
    COUNT(*) AS total,
    ROUND(SUM(CASE WHEN pr.status = 'MERGED' OR pr.merged_date IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS merged_pct,
    ROUND(SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS abandoned_pct
FROM lake.pull_requests pr
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = pr.base_repo_id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
  AND pr.status IN ('MERGED', 'CLOSED')
  AND COALESCE(pr.merged_date, pr.closed_date) >= '{from_date}'
  AND COALESCE(pr.merged_date, pr.closed_date) <= '{to_date}'
  AND pr.author_name NOT REGEXP '\\[bot\\]|github-actions|github actions|-bot$|-robot$|copilot|cursor|claude'
  AND pr.is_draft = 0
```

---

## Metric 1.7 — Median Reviewers per PR

**Definition:** Median count of distinct non-bot reviewers per PR created in range.

```sql
SELECT ROUND(AVG(reviewer_count), 2) AS median_reviewers_per_pr
FROM (
    SELECT reviewer_count,
           ROW_NUMBER() OVER (ORDER BY reviewer_count) AS rn,
           COUNT(*) OVER () AS cnt
    FROM (
        SELECT prc.pull_request_id, COUNT(DISTINCT prc.author_name) AS reviewer_count
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
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
```

---

## Metric 1.8 — PR Size Distribution

**Definition:** Distribution of PRs by total lines changed (additions + deletions).

```sql
SELECT
    CASE
        WHEN (pr.additions + pr.deletions) <= 50   THEN 'XS (1-50 lines)'
        WHEN (pr.additions + pr.deletions) <= 200  THEN 'S (51-200 lines)'
        WHEN (pr.additions + pr.deletions) <= 500  THEN 'M (201-500 lines)'
        WHEN (pr.additions + pr.deletions) <= 1000 THEN 'L (501-1000 lines)'
        ELSE 'XL (>1000 lines)'
    END AS size_bucket,
    COUNT(*) AS pr_count,
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
ORDER BY FIELD(size_bucket, 'XS (1-50 lines)', 'S (51-200 lines)', 'M (201-500 lines)', 'L (501-1000 lines)', 'XL (>1000 lines)')
```

---

## Metric 1.9 — Cross-Repo Comparison

**Definition:** Per-repository summary: closed PRs, avg cycle time, abandonment %.
Note: uses AVG not median per repo (approximation).

```sql
SELECT
    r.name AS repository,
    COUNT(DISTINCT pr.id) AS closed_prs,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, pr.created_date, COALESCE(pr.merged_date, pr.closed_date)) / 60.0), 2) AS avg_cycle_hours,
    ROUND(SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS abandonment_pct
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
GROUP BY r.name ORDER BY avg_cycle_hours DESC LIMIT 30
```

---

## Metric 1.10 — Z-Score Classification

**Definition:** Classify PRs in the selected period as Fast / Average / Slow based on
log-normal z-score against a 90-day baseline ending at `{to_date}`.

**Run TWO queries in sequence:**

**Step A — Get baseline statistics (90-day lookback):**

```sql
SELECT AVG(log_val) AS mu_log,
       SQRT(AVG(log_val * log_val) - AVG(log_val) * AVG(log_val)) AS sigma_log,
       COUNT(*) AS baseline_pr_count
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
          AND TIMESTAMPDIFF(MINUTE, pr.created_date, COALESCE(pr.merged_date, pr.closed_date)) > 0
    ) baseline_prs
) log_vals
```

**Step B — Classify PRs (substitute `{mu_log}` and `{sigma_log}` from Step A result):**

```sql
SELECT
    CASE
        WHEN (LOG(cycle_hours + 1) - {mu_log}) / NULLIF({sigma_log}, 0) < -1 THEN 'Fast'
        WHEN (LOG(cycle_hours + 1) - {mu_log}) / NULLIF({sigma_log}, 0) > 1  THEN 'Slow'
        ELSE 'Average'
    END AS category,
    COUNT(*) AS pr_count,
    ROUND(AVG(cycle_hours / 24), 1) AS avg_days
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
      AND TIMESTAMPDIFF(MINUTE, pr.created_date, COALESCE(pr.merged_date, pr.closed_date)) > 0
) prs
GROUP BY category
```

---

## Report Template

Format the results of all queries as a single markdown report with these sections:

```
## PR Cycle Time Report — {product_name} — {from_date} to {to_date}

### Key Metrics
| Metric | Value |
|--------|-------|
| Total Closed PRs | {total_closed_prs} |
| Median Cycle Time | {median_cycle_time_hours} hrs |
| Opened PRs | {opened_prs} |
| Median Interaction Time | {median_interaction_time_hours} hrs |

### PR Stages
| Stage | Median Time |
|-------|-------------|
| First Review | {median_first_review_hours} hrs |
| First Approval | {median_first_approval_hours} hrs |
| Integration (approval → merge) | {integration_hours} hrs |

### PR Flow
| Stage | Count | % of Total |
|-------|-------|------------|
| Opened | {total_opened} | 100% |
| Reviewed | {reviewed} | {reviewed_pct}% |
| Approved | {approved} | {approved_pct}% |
| Merged | {merged} | {merged_pct}% |
| Abandoned | {abandoned} | {abandoned_pct}% |

### PR Productivity
Merged: {merged_pct}% | Abandoned: {abandoned_pct}%

### Median Reviewers per PR
{median_reviewers_per_pr}

### PR Size Distribution
| Bucket | PRs | Avg Lines |
|--------|-----|-----------|
...

### Z-Score Classification
| Category | PRs | Avg Days |
|----------|-----|---------|
| Fast | ... | ... |
| Average | ... | ... |
| Slow | ... | ... |

### Top Repos by Activity
| Repo | Closed PRs |
|------|-----------|
...

### Cross-Repo Comparison (avg cycle time)
| Repo | Closed PRs | Avg Cycle (hrs) | Abandonment % |
|------|-----------|-----------------|---------------|
...

### Cycle Time Trend (daily median, 7-day rolling avg)
| Date | Median (hrs) | 7-day Avg | PRs |
|------|-------------|-----------|-----|
...
```

## Interpretation Guide

- **Median cycle time > 72 hrs:** Flag for discussion — PRs may be too large or review process is slow.
- **First Review > 24 hrs:** Pickup time is high — consider review rotation or SLOs.
- **Abandoned % > 15%:** Indicates rework loops or misaligned PRs.
- **Z-score Slow > 20%:** Tail risk — investigate the outliers.
- **Reviewers/PR < 1.5:** Single-reviewer pattern — knowledge silo risk.
```

- [ ] **Step 2: Verify the file exists and is non-empty**

```bash
wc -l skills/lm-pr-metrics/SKILL.md
```

Expected: line count > 200.

- [ ] **Step 3: Commit**

```bash
git add skills/lm-pr-metrics/SKILL.md
git commit -m "feat(skills): add lm-pr-metrics SKILL.md with 11 PR cycle time metric queries"
```

---

## Task 3: Create `skills/lm-ftpr-metrics/SKILL.md`

**Files:**
- Create: `skills/lm-ftpr-metrics/SKILL.md`

- [ ] **Step 1: Write the file** with the exact content below.

```markdown
---
name: lm-ftpr-metrics
description: First Time Pass Rate (FTPR) leading metrics — overall FTPR %, weekly trend, pass/fail breakdown. Aggregates at product or team level using n8n-pulumi-poc JSON config.
---

# LM FTPR Metrics Skill

## Purpose

Calculate First Time Pass Rate (FTPR) metrics matching the n8n leading-metrics dashboard.
FTPR measures how often merged PRs pass ALL CI checks on their **first commit**.

## When to Use

When a user asks for:
- FTPR percentage, first-time pass rate
- CI pass/fail breakdown for PRs
- Weekly FTPR trend
- CI coverage (how many PRs had CI data)

## Parameters

| Parameter | Required | Example | Notes |
|-----------|----------|---------|-------|
| `product_name` | One of these | `konflux` | ID from products/ JSON |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

## FTPR Definition

FTPR = (Merged PRs where ALL CI pipelines on the **first commit** passed) /
       (Total merged PRs with CI data) × 100

- "First commit" = the chronologically earliest commit by `commit_authored_date`
- CI pipelines are deduplicated: if the same pipeline ran multiple times, keep the **latest** result
- Non-CI events (empty `result` field) are excluded
- Covers both GitHub Actions / GitLab CI (`cicd_pipelines`) and Prow / Tekton (`ci_test_jobs`)

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Before running any query, resolve the blueprint IDs:

**If product-level** (e.g. "show FTPR for Konflux"):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `type` = `"ftpr"`
3. Extract the `blueprintids` array — convert strings to integers
4. Use: `WHERE bp.id IN (<ids>)`

**If team-level** (e.g. "show FTPR for the Konflux Build team"):
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find the entry in `dashboards` where `type` = `"ftpr"`
3. Extract the single `blueprintid` string — convert to integer
4. Use: `WHERE bp.id = <id>`

## Implementation Strategy — Two Queries + Agent Join

The FTPR calculation requires joining PR data with pipeline data on `commit_sha`. To stay
within the `execute_query` query-length limit, run **two separate queries** and join the
results in memory (the agent does this, not SQL).

---

## Query 2.1-A — PRs with First Commit SHA

Returns one row per merged PR with its earliest commit SHA.

```sql
SELECT pr.id AS pr_id, pr.merged_date, fc.commit_sha AS first_commit_sha
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
  AND pr.is_draft = 0
```

**Output:** Multiple rows: `pr_id`, `merged_date`, `first_commit_sha` (may be NULL if no commits found).

---

## Query 2.1-B — Deduped Pipeline Pass/Fail per Commit

Returns one row per commit SHA with whether ALL pipelines passed.

```sql
SELECT commit_sha, MIN(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) AS all_passed
FROM (
    SELECT commit_sha, pipeline_name, result,
           ROW_NUMBER() OVER (
               PARTITION BY commit_sha, pipeline_name ORDER BY finished_at DESC
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
GROUP BY commit_sha
```

**Output:** Multiple rows: `commit_sha`, `all_passed` (1 = all passed, 0 = any failed).

---

## Metric 2.1 — FTPR Key Metrics (agent post-processing)

After running both queries, join them in memory on `first_commit_sha = commit_sha`:

```
total_merged_prs   = count of rows from Query A
prs_without_ci     = count where first_commit_sha IS NULL
                     OR first_commit_sha not found in Query B results
prs_with_ci_data   = count where first_commit_sha found in Query B
first_time_passes  = count where all_passed = 1
first_time_fails   = count where all_passed = 0
ftpr_pct           = ROUND(first_time_passes / prs_with_ci_data * 100, 1)
                     (return 0 if prs_with_ci_data = 0)
```

---

## Metric 2.2 — FTPR Over Time (Weekly)

After running both queries (2.1-A and 2.1-B), group the joined results by week:

```
For each week (YEARWEEK of merged_date):
  week_start     = MIN(merged_date) in that week
  total_merged   = count of PRs in that week
  with_ci        = count where first_commit_sha found in Query B
  passes         = count where all_passed = 1
  ftpr_pct       = ROUND(passes / with_ci * 100, 1)
```

Sort by week ascending. Compute **4-week rolling average** of `ftpr_pct`:
for each week, average `ftpr_pct` of that week and the 3 preceding weeks.

---

## Metric 2.3 — FTPR Pass/Fail Breakdown

From the same joined result as 2.1:

```
passed       = first_time_passes
failed       = first_time_fails
no_ci_data   = prs_without_ci
ftpr_pct     = ROUND(passed / (passed + failed) * 100, 1)
```

---

## Report Template

```
## FTPR Report — {product_name} — {from_date} to {to_date}

### Key Metrics
| Metric | Value |
|--------|-------|
| FTPR | {ftpr_pct}% |
| Total Merged PRs | {total_merged_prs} |
| First-Time Passes | {first_time_passes} |
| First-Time Fails | {first_time_fails} |
| PRs with CI Data | {prs_with_ci_data} / {total_merged_prs} |
| PRs without CI Data | {prs_without_ci} |

### Pass/Fail Breakdown
| Result | Count | % |
|--------|-------|---|
| Passed first time | {passed} | {ftpr_pct}% |
| Failed first time | {failed} | {fail_pct}% |
| No CI data | {no_ci_data} | {no_ci_pct}% |

### Weekly FTPR Trend
| Week | FTPR % | 4-week Rolling Avg | Merged PRs |
|------|--------|--------------------|-----------|
...
```

## Interpretation Guide

- **FTPR < 70%:** Significant CI instability or code quality concern — investigate failing pipelines.
- **FTPR 70–85%:** Acceptable, room for improvement.
- **FTPR > 85%:** Healthy.
- **PRs without CI data > 20%:** CI coverage gap — some repos may not have pipeline data in DevLake.
- **Declining weekly trend:** Check for recent infrastructure changes or flaky tests.
```

- [ ] **Step 2: Verify the file exists and is non-empty**

```bash
wc -l skills/lm-ftpr-metrics/SKILL.md
```

Expected: line count > 150.

- [ ] **Step 3: Commit**

```bash
git add skills/lm-ftpr-metrics/SKILL.md
git commit -m "feat(skills): add lm-ftpr-metrics SKILL.md with FTPR queries and two-query join pattern"
```

---

## Task 4: Create `skills/lm-coverage-metrics/SKILL.md`

**Files:**
- Create: `skills/lm-coverage-metrics/SKILL.md`

- [ ] **Step 1: Write the file** with the exact content below.

```markdown
---
name: lm-coverage-metrics
description: Code Coverage leading metrics — avg overall coverage, patch coverage, coverage by team, line breakdown, daily trend. Aggregates at product or team level using n8n-pulumi-poc JSON config.
---

# LM Coverage Metrics Skill

## Purpose

Calculate Code Coverage metrics from Codecov data stored in DevLake, matching the n8n
leading-metrics dashboard. Coverage data is per-repository and is identified by
`owner/repo` strings (not numeric IDs).

## When to Use

When a user asks for:
- Overall code coverage percentage
- Patch coverage (coverage of new/changed code)
- Coverage trend over time
- Coverage by team
- Line-level breakdown (covered, partial, uncovered lines)

## Parameters

| Parameter | Required | Example | Notes |
|-----------|----------|---------|-------|
| `product_name` | One of these | `konflux` | ID from products/ JSON |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date (for trend/patch queries) |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

## Coverage Tables

| Table | Purpose |
|-------|---------|
| `lake._tool_codecov_commit_coverages` | Overall coverage per commit: `repo_id`, `overall_coverage`, `commit_timestamp`, `hits`, `misses`, `partials` |
| `lake._tool_codecov_comparisons` | Patch coverage: `repo_id`, `commit_sha`, `patch` |
| `lake._tool_codecov_commits` | Commit metadata: `repo_id`, `commit_sha`, `commit_timestamp` |

**Important:** `repo_id` in all codecov tables is formatted as `owner/repo`
(e.g. `konflux-ci/build-service`). This matches `lake.repos.name`.

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Coverage tables do not have a direct FK to `_devlake_blueprints`. Scope is resolved via
a correlated subquery joining `repos` → `project_mapping` → `_devlake_blueprints`.

**If product-level** (e.g. "show coverage for Konflux"):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `type` = `"codecoverage"`
3. Extract the `blueprintids` array — convert strings to integers
4. The SQL uses: `WHERE cc.repo_id IN (SELECT DISTINCT r.name FROM lake.repos r JOIN lake.project_mapping pm ... JOIN lake._devlake_blueprints bp ... WHERE bp.id IN (<ids>))`

**If team-level**:
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find `dashboards` entry where `type` = `"codecoverage"`
3. Extract single `blueprintid`
4. Use the same subquery pattern with `WHERE bp.id = <id>`

In all SQL below, replace `{BLUEPRINT_ID_LIST}` with the resolved comma-separated integers.

---

## Metric 3.1-A — Latest Overall Coverage per Repo

Returns the most recent overall coverage for each repo in scope.

```sql
SELECT cc.repo_id, ROUND(cc.overall_coverage, 2) AS total_coverage,
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
)
```

**Post-processing:** `avg_coverage = AVG(total_coverage)` across all returned repos.

---

## Metric 3.1-B — Average Patch Coverage in Period

Returns average patch coverage per repo for commits in the selected date range.

```sql
SELECT comp.repo_id, ROUND(AVG(comp.patch), 2) AS avg_patch_coverage
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
GROUP BY comp.repo_id
```

**Post-processing:** `avg_patch_coverage = AVG(avg_patch_coverage)` across all returned repos.

---

## Metric 3.1-C — Earliest Coverage in Period (for trend)

Returns the oldest coverage reading per repo at or after `{from_date}`.

```sql
SELECT cc.repo_id, ROUND(cc.overall_coverage, 2) AS earliest_coverage
FROM lake._tool_codecov_commit_coverages cc
INNER JOIN (
    SELECT repo_id, MIN(commit_timestamp) AS min_ts
    FROM lake._tool_codecov_commit_coverages
    WHERE overall_coverage > 0 AND commit_timestamp >= '{from_date}'
    GROUP BY repo_id
) earliest ON cc.repo_id = earliest.repo_id AND cc.commit_timestamp = earliest.min_ts
WHERE cc.overall_coverage > 0
  AND cc.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
```

**Post-processing (Trend):**
```
avg_latest   = AVG(total_coverage) from Metric 3.1-A
avg_earliest = AVG(earliest_coverage) from this query
delta        = avg_latest - avg_earliest
trend_label  = if delta > 1: "+{delta}%"
               if delta < -1: "{delta}%"
               else: "Stable"
```

---

## Metric 3.2 — Coverage by Team

Returns average latest coverage grouped by DevLake project (team).

```sql
SELECT pm.project_name,
       COUNT(DISTINCT cc.repo_id) AS repo_count,
       ROUND(AVG(cc.overall_coverage), 2) AS avg_coverage
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
GROUP BY pm.project_name ORDER BY avg_coverage DESC
```

**Post-processing:** Extract team short-name from `project_name` using the last segment
after ` - ` (e.g. `Secureflow - Konflux - Build` → `Build`).

---

## Metric 3.3 — Coverage Line Breakdown

Returns total covered, partial, and uncovered lines across all in-scope repos (latest commit).

```sql
SELECT SUM(cc.hits) AS total_covered,
       SUM(cc.partials) AS total_partial,
       SUM(cc.misses) AS total_uncovered,
       SUM(cc.hits + cc.partials + cc.misses) AS total_lines
FROM lake._tool_codecov_commit_coverages cc
INNER JOIN (
    SELECT repo_id, MAX(commit_timestamp) AS max_ts
    FROM lake._tool_codecov_commit_coverages WHERE overall_coverage > 0
    GROUP BY repo_id
) latest ON cc.repo_id = latest.repo_id AND cc.commit_timestamp = latest.max_ts
WHERE cc.overall_coverage > 0
  AND cc.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
```

**Post-processing:** `covered_pct = total_covered / total_lines * 100`.

---

## Metric 3.4-A — Daily Overall Coverage Trend

```sql
SELECT DATE(cc.commit_timestamp) AS date_val,
       ROUND(AVG(cc.overall_coverage), 2) AS daily_coverage_avg
FROM lake._tool_codecov_commit_coverages cc
WHERE cc.overall_coverage > 0
  AND cc.commit_timestamp >= '{from_date}'
  AND cc.commit_timestamp <= '{to_date}'
  AND cc.repo_id IN (
    SELECT DISTINCT r.name
    FROM lake.repos r
    JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
    JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
    WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
)
GROUP BY DATE(cc.commit_timestamp) ORDER BY DATE(cc.commit_timestamp)
```

---

## Metric 3.4-B — Daily Patch Coverage Trend

```sql
SELECT DATE(cm.commit_timestamp) AS date_val,
       ROUND(AVG(comp.patch), 2) AS daily_patch_avg
FROM lake._tool_codecov_comparisons comp
JOIN lake._tool_codecov_commits cm
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
GROUP BY DATE(cm.commit_timestamp) ORDER BY DATE(cm.commit_timestamp)
```

**Post-processing (weekly):** Group daily rows by week, average within each week.
Compute **4-week rolling average** of weekly coverage and patch values.

---

## Report Template

```
## Code Coverage Report — {product_name} — {from_date} to {to_date}

### Key Metrics
| Metric | Value |
|--------|-------|
| Avg Overall Coverage | {avg_coverage}% |
| Avg Patch Coverage | {avg_patch_coverage}% |
| Trend (period delta) | {trend_label} |
| Repos Tracked | {repo_count} |

### Line Breakdown
| Category | Lines | % of Total |
|----------|-------|-----------|
| Covered | {total_covered} | {covered_pct}% |
| Partial | {total_partial} | {partial_pct}% |
| Uncovered | {total_uncovered} | {uncovered_pct}% |

### Coverage by Team
| Team | Repos | Avg Coverage |
|------|-------|-------------|
...

### Coverage Trend (weekly avg)
| Week | Overall Coverage | Patch Coverage | 4-week Avg |
|------|-----------------|---------------|-----------|
...
```

## Interpretation Guide

- **Overall coverage < 60%:** Low — significant untested surface area.
- **Overall coverage 60–80%:** Acceptable, room to grow.
- **Overall coverage > 80%:** Strong.
- **Patch coverage < 70%:** New code is under-tested — PR review concern.
- **Downward trend > 2 weeks:** Investigate — coverage debt accumulating.
- **Large gap between overall and patch:** Existing code is better tested than new additions.
```

- [ ] **Step 2: Verify the file exists and is non-empty**

```bash
wc -l skills/lm-coverage-metrics/SKILL.md
```

Expected: line count > 150.

- [ ] **Step 3: Commit**

```bash
git add skills/lm-coverage-metrics/SKILL.md
git commit -m "feat(skills): add lm-coverage-metrics SKILL.md with 4 coverage metric queries"
```

---

## Task 5: Final verification

- [ ] **Step 1: Confirm all three files exist**

```bash
ls -la skills/lm-pr-metrics/SKILL.md skills/lm-ftpr-metrics/SKILL.md skills/lm-coverage-metrics/SKILL.md
```

Expected: all three files present, all non-zero size.

- [ ] **Step 2: Check git log — expect 4 commits on this branch**

```bash
GIT_PAGER=cat git log --oneline -6
```

Expected recent commits:
```
<sha> feat(skills): add lm-coverage-metrics SKILL.md ...
<sha> feat(skills): add lm-ftpr-metrics SKILL.md ...
<sha> feat(skills): add lm-pr-metrics SKILL.md ...
<sha> feat(spec): generalize skills to any n8n-pulumi-poc product/team ...
```

- [ ] **Step 3: Check query character lengths (no query should exceed 10,000 chars)**

The longest queries are 1.1-D (interaction time) and 2.1-B (pipeline dedup UNION ALL).
Visually confirm neither exceeds ~8,000 characters in the SKILL.md.

- [ ] **Step 4: Spot-check SQL rules in each file**

For each SKILL.md, confirm:
- No query contains `WITH ` at the start (no CTEs)
- No query contains `--` or `/* */` (no SQL comments)
- No query contains `;` (no semicolons)
- Every query starts with `SELECT`

```bash
grep -n "^WITH\|^\s*WITH " skills/lm-pr-metrics/SKILL.md skills/lm-ftpr-metrics/SKILL.md skills/lm-coverage-metrics/SKILL.md
```

Expected: no output (no CTEs).

```bash
grep -n " -- \|^--" skills/lm-pr-metrics/SKILL.md skills/lm-ftpr-metrics/SKILL.md skills/lm-coverage-metrics/SKILL.md
```

Expected: no output (no SQL comments).

---

## Self-Review Checklist

- [x] All 11 PR cycle time queries present in lm-pr-metrics (1.1-A through 1.10)
- [x] FTPR two-query split pattern documented with agent post-processing instructions
- [x] All 4 coverage queries present (3.1-A/B/C, 3.2, 3.3, 3.4-A/B)
- [x] No CTEs in any SQL block
- [x] No SQL comments in any SQL block
- [x] Scope resolution Step 0 present in all three skills
- [x] n8n-pulumi-poc JSON lookup instructions complete in all three skills
- [x] Report templates present in all three skills
- [x] Interpretation guides present in all three skills
- [x] Bot filter pattern consistent across all skills

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-19-lm-skills-implementation.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute all tasks in this session with checkpoints after each task.

Which approach?
