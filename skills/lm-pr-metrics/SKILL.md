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
| `product_name` | One of these | `konflux` | ID from products/ JSON filename |
| `team_name` | OR this | `konflux-build` | ID from teams/ JSON filename |
| `from_date` | Yes | `2026-04-01` | ISO 8601 date |
| `to_date` | Yes | `2026-04-30` | ISO 8601 date |

## Available MCP Tools

- `mcp_konflux-devlake-mcp-prd_execute_query` — run SQL SELECT queries

---

## Step 0 — Resolve Scope (ALWAYS DO THIS FIRST)

Before running any query, read the n8n-pulumi-poc JSON config to get blueprint IDs.

**If product-level** (user says "for Konflux", "for OpenShift Pipelines", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/products/<product_name>.json`
2. Find the entry in `dashboards` where `"type": "prcycletime"`
3. Extract the `blueprintids` array (strings) — convert each to integer
4. In every SQL below, replace the example `bp.id IN (...)` list with these integers

**If team-level** (user says "for the Konflux Build team", etc.):
1. Read `n8n-pulumi-poc/containers/dashboard/teams/<team_name>.json`
2. Find the entry in `dashboards` where `"type": "prcycletime"`
3. Extract the single `blueprintid` string — convert to integer
4. Replace `bp.id IN (...)` with `bp.id = <integer>`

The example queries below use Konflux product IDs as placeholders. Always substitute
the resolved IDs before calling `execute_query`.

---

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

**Definition:** Count of merged or closed non-bot non-draft PRs whose close/merge date
falls within the selected range.

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

**Output:** Single row — `total_closed_prs` integer.

---

## Metric 1.1-B — Median Cycle Time (hours)

**Definition:** Median of `(COALESCE(merged_date, closed_date) − created_date)` in hours
across all closed non-bot non-draft PRs in the date range.

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

**Output:** Single row — `median_cycle_time_hours` decimal.

---

## Metric 1.1-C — Opened PRs

**Definition:** Count of non-bot non-draft PRs whose `created_date` falls in the range.

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

**Output:** Single row — `opened_prs` integer.

---

## Metric 1.1-D — Median Interaction Time (hours)

**Definition:** Approximation of median-of-medians interaction time. For each PR, compute
the average time (hours) between consecutive non-bot review comments. Then take the median
of those per-PR averages across all PRs in the range.

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

**Output:** Single row — `median_interaction_time_hours` decimal.

---

## Metric 1.2 — Daily Median Cycle Time (trend)

**Definition:** Per-day median cycle time for the selected period.

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
          AND TIMESTAMPDIFF(MINUTE, pr.created_date,
              COALESCE(pr.merged_date, pr.closed_date)) >= 0
    ) base_prs
) daily_ranked
WHERE rn IN (FLOOR((cnt + 1) / 2), CEIL((cnt + 1) / 2))
GROUP BY close_day ORDER BY close_day
```

**Post-processing:** For each row, compute `rolling_7d_avg` = mean of `daily_median_cycle_hours`
for the current day and the 6 preceding days in the result set.

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

**Integration Time:** Compute as `median_cycle_time_hours − median_first_approval_hours`.

---

## Metric 1.4 — PR Flow

**Definition:** Of all closed PRs in range — how many reached each stage?

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

**Definition:** Median count of distinct non-bot reviewers per PR created in the range.

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
ORDER BY FIELD(size_bucket,
    'XS (1-50 lines)', 'S (51-200 lines)', 'M (201-500 lines)',
    'L (501-1000 lines)', 'XL (>1000 lines)')
```

---

## Metric 1.9 — Cross-Repo Comparison

**Definition:** Per-repository summary — closed PRs, avg cycle time (hours), abandonment %.
Note: uses AVG not median per repo (approximation for trend use, not exact KPI).

```sql
SELECT
    r.name AS repository,
    COUNT(DISTINCT pr.id) AS closed_prs,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, pr.created_date,
        COALESCE(pr.merged_date, pr.closed_date)) / 60.0), 2) AS avg_cycle_hours,
    ROUND(SUM(CASE WHEN pr.status = 'CLOSED' AND pr.merged_date IS NULL THEN 1 ELSE 0 END)
          * 100.0 / COUNT(*), 1) AS abandonment_pct
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

**Definition:** Classify PRs in the selected period as Fast / Average / Slow using a
log-normal z-score against a 90-day baseline ending at `{to_date}`.

Run TWO queries sequentially. Substitute `{mu_log}` and `{sigma_log}` from Step A into Step B.

**Step A — Baseline statistics (90-day lookback):**

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
          AND TIMESTAMPDIFF(MINUTE, pr.created_date,
              COALESCE(pr.merged_date, pr.closed_date)) > 0
    ) baseline_prs
) log_vals
```

**Step B — Classify PRs (substitute actual mu_log and sigma_log values from Step A):**

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
      AND TIMESTAMPDIFF(MINUTE, pr.created_date,
          COALESCE(pr.merged_date, pr.closed_date)) > 0
) prs
GROUP BY category
```

---

## Report Template

Format results as a single markdown report:

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
| First Review (Pickup) | {median_first_review_hours} hrs |
| First Approval | {median_first_approval_hours} hrs |
| Integration (approval → merge) | {integration_hours} hrs |

### PR Flow
| Stage | Count | % of Total |
|-------|-------|------------|
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
| XS (1-50) | ... | ... |
| S (51-200) | ... | ... |
| M (201-500) | ... | ... |
| L (501-1000) | ... | ... |
| XL (>1000) | ... | ... |

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

### Cross-Repo Comparison
| Repo | Closed PRs | Avg Cycle (hrs) | Abandonment % |
|------|-----------|-----------------|---------------|
...

### Cycle Time Trend (daily median + 7-day rolling avg)
| Date | Median (hrs) | 7-day Avg | PRs |
|------|-------------|-----------|-----|
...
```

---

## Interpretation Guide

| Signal | Threshold | Action |
|--------|-----------|--------|
| Median cycle time | > 72 hrs | Flag — PRs may be too large or review process slow |
| First Review (pickup) | > 24 hrs | High pickup time — consider review SLOs |
| Abandoned % | > 15% | Rework loops or misaligned scope |
| Z-score Slow | > 20% of PRs | Investigate outliers |
| Reviewers/PR | < 1.5 | Single-reviewer pattern — knowledge silo risk |
| Interaction time | > 8 hrs | Slow back-and-forth — async review friction |
