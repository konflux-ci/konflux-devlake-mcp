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
| `product_name` | One of these | `konflux` | ID from products/ JSON filename |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON filename |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

---

## FTPR Definition

FTPR = (Merged PRs where ALL CI pipelines on the **first commit** passed) /
(Total merged PRs with CI data) × 100

- "First commit" = the chronologically earliest commit by `commit_authored_date`
- CI pipelines are deduplicated: if the same pipeline ran multiple times, keep the **latest** result
- Non-CI events (empty `result` field) are excluded
- Covers both GitHub Actions / GitLab CI (`cicd_pipelines`) and Prow / Tekton (`ci_test_jobs`)

---

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Before running any query, read the n8n-pulumi-poc JSON config to get blueprint IDs.

**If product-level** (user says "for Konflux", "for OpenShift Pipelines", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `"type": "ftpr"`
3. Extract the `blueprintids` array (strings) — convert each to integer
4. In every SQL below, replace the example `bp.id IN (...)` list with these integers

**If team-level** (user says "for the Konflux Build team", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find the entry in `dashboards` where `"type": "ftpr"`
3. Extract the single `blueprintid` string — convert to integer
4. Replace `bp.id IN (...)` with `bp.id = <integer>`

The example queries below use Konflux product IDs as placeholders. Always substitute
the resolved IDs before calling `execute_query`.

---

## Implementation Strategy — Two Queries + Agent Join

The FTPR calculation joins PR data with pipeline data on `commit_sha`. To stay within
the `execute_query` query-length limit, run **two separate queries** and join the results
in memory — the agent does this, not SQL.

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

**Output:** Multiple rows — `pr_id`, `merged_date`, `first_commit_sha` (may be NULL if no
commits found for that PR in DevLake).

---

## Query 2.1-B — Deduped Pipeline Pass/Fail per Commit

Returns one row per commit SHA indicating whether ALL pipelines passed.

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

**Output:** Multiple rows — `commit_sha`, `all_passed` (1 = all pipelines passed, 0 = any failed).

---

## Metric 2.1 — FTPR Key Metrics (agent post-processing)

After running both queries above, join them in memory on `first_commit_sha = commit_sha`:

```
total_merged_prs   = count of rows from Query A
prs_without_ci     = count where first_commit_sha IS NULL
                     OR first_commit_sha not found in Query B results
prs_with_ci_data   = count where first_commit_sha IS found in Query B results
first_time_passes  = count where all_passed = 1
first_time_fails   = count where all_passed = 0
ftpr_pct           = ROUND(first_time_passes / prs_with_ci_data * 100, 1)
                     (return 0 if prs_with_ci_data = 0)
```

---

## Metric 2.2 — FTPR Over Time (Weekly)

Using the same joined result from Queries 2.1-A and 2.1-B, group by YEARWEEK of `merged_date`:

```
For each week (YEARWEEK of merged_date):
  week_start     = MIN(merged_date) in that week
  total_merged   = count of PRs with that merged_date week
  with_ci        = count where first_commit_sha found in Query B results
  passes         = count where all_passed = 1
  ftpr_pct       = ROUND(passes / with_ci * 100, 1)  — use 0 if with_ci = 0
```

Sort by week ascending. Compute **4-week rolling average** of `ftpr_pct`:
for each week, average `ftpr_pct` of that week and the 3 preceding weeks in the result set.

---

## Metric 2.3 — FTPR Pass/Fail Breakdown

From the same joined result as Metric 2.1:

```
passed       = first_time_passes
failed       = first_time_fails
no_ci_data   = prs_without_ci
ftpr_pct     = ROUND(passed / (passed + failed) * 100, 1)  — use 0 if denominator = 0
fail_pct     = ROUND(failed / (passed + failed) * 100, 1)
no_ci_pct    = ROUND(no_ci_data / total_merged_prs * 100, 1)
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

---

## Interpretation Guide

| Signal | Threshold | Action |
|--------|-----------|--------|
| FTPR | < 70% | Significant CI instability or code quality concern — investigate failing pipelines |
| FTPR | 70–85% | Acceptable, room for improvement |
| FTPR | > 85% | Healthy |
| PRs without CI data | > 20% | CI coverage gap — some repos may not have pipeline data in DevLake |
| Declining weekly trend | 2+ consecutive weeks down | Check for recent infra changes or flaky tests |
