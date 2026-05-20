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
| `product_name` | One of these | `konflux` | ID from products/ JSON filename |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON filename |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date (for trend/patch queries) |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

---

## Coverage Tables

| Table | Purpose |
|-------|---------|
| `lake._tool_codecov_commit_coverages` | Overall coverage per commit: `repo_id`, `overall_coverage`, `commit_timestamp`, `hits`, `misses`, `partials` |
| `lake._tool_codecov_comparisons` | Patch coverage per commit: `repo_id`, `commit_sha`, `patch` |
| `lake._tool_codecov_commits` | Commit metadata: `repo_id`, `commit_sha`, `commit_timestamp` |

**Important:** `repo_id` in all codecov tables is formatted as `owner/repo`
(e.g. `konflux-ci/build-service`). This matches `lake.repos.name`.

---

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Coverage tables do not have a direct FK to `_devlake_blueprints`. Scope is resolved by
joining `_tool_codecov_*` tables through `lake.repos` → `lake.project_mapping` →
`lake._devlake_blueprints`.

**If product-level** (user says "for Konflux", "for OpenShift Pipelines", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `"type": "codecoverage"`
3. Extract the `blueprintids` array (strings) — convert each to integer
4. Build the repo subquery: `WHERE bp.id IN (<ids>)` inside the subquery shown below

**If team-level** (user says "for the Konflux Build team", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find the entry in `dashboards` where `"type": "codecoverage"`
3. Extract the single `blueprintid` string — convert to integer
4. Use `WHERE bp.id = <integer>` inside the subquery

### Scope Subquery Pattern

In all SQL below, `{SCOPE_REPO_SUBQUERY}` expands to:

```sql
SELECT DISTINCT r.name
FROM lake.repos r
JOIN lake.project_mapping pm ON pm.`table` = 'repos' AND pm.row_id = r.id
JOIN lake._devlake_blueprints bp ON bp.project_name = pm.project_name
WHERE bp.id IN (2, 4, 5, 6, 7, 8, 9, 10, 13, 17, 20, 87, 89, 90, 96, 101, 104)
```

Replace the `bp.id IN (...)` list with the integers resolved from the JSON. The result
set of this subquery is the list of `owner/repo` strings for the product/team.

---

## Metric 3.1-A — Latest Overall Coverage per Repo

Returns the most recent overall coverage for each in-scope repo.

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

**Post-processing:** `avg_coverage = ROUND(AVG(total_coverage), 2)` across all returned repos.

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

**Post-processing:** `avg_patch_coverage = ROUND(AVG(avg_patch_coverage), 2)` across repos.

---

## Metric 3.1-C — Earliest Coverage in Period (for trend delta)

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

**Post-processing (Trend delta):**
```
avg_latest   = AVG(total_coverage) from Metric 3.1-A
avg_earliest = AVG(earliest_coverage) from this query
delta        = avg_latest - avg_earliest
trend_label  = if delta > 1: "+{delta:.1f}%"
               if delta < -1: "{delta:.1f}%"
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

Returns total covered, partial, and uncovered lines across all in-scope repos (latest commit per repo).

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

**Post-processing:**
```
covered_pct  = ROUND(total_covered / total_lines * 100, 1)
partial_pct  = ROUND(total_partial / total_lines * 100, 1)
uncovered_pct = ROUND(total_uncovered / total_lines * 100, 1)
```

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

**Post-processing (weekly rollup):** Group daily rows by ISO week, average within each week.
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

---

## Interpretation Guide

| Signal | Threshold | Action |
|--------|-----------|--------|
| Overall coverage | < 60% | Low — significant untested surface area |
| Overall coverage | 60–80% | Acceptable, room to grow |
| Overall coverage | > 80% | Strong |
| Patch coverage | < 70% | New code is under-tested — PR review concern |
| Downward trend | > 2 consecutive weeks | Investigate — coverage debt accumulating |
| Gap: overall vs patch | > 15pp | Existing code better tested than new additions |
