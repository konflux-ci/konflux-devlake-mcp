# SQL Query Patterns for DevLake

Pre-built query patterns. Compose these rather than writing from scratch.
All queries use subqueries (no CTEs), `lake.table_name` format, and `project_mapping` for scoping.

> **Prefer MCP tools** over raw SQL when possible. These patterns are for
> questions that the specialized tools don't cover.

## PR Cycle Time (using project_pr_metrics)

```sql
SELECT
  r.name AS repo,
  COUNT(DISTINCT pr.id) AS merged_prs,
  CAST(ROUND(AVG(COALESCE(prm.pr_coding_time, 0) / 60), 1) AS CHAR) AS avg_coding_hours,
  CAST(ROUND(AVG(COALESCE(prm.pr_pickup_time, 0) / 60), 1) AS CHAR) AS avg_pickup_hours,
  CAST(ROUND(AVG(COALESCE(prm.pr_review_time, 0) / 60), 1) AS CHAR) AS avg_review_hours
FROM lake.pull_requests pr
LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
JOIN lake.repos r ON pr.base_repo_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND pr.merged_date IS NOT NULL
  AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY r.name
ORDER BY merged_prs DESC
LIMIT 20
```

> Or use the `get_pr_cycle_time` MCP tool which runs this automatically.

## Deployment Frequency

```sql
SELECT
  DATE_FORMAT(d.finished_date, '%Y-%m-%d') AS deploy_date,
  COUNT(*) AS deployments,
  CAST(SUM(CASE WHEN d.result = 'SUCCESS' THEN 1 ELSE 0 END) AS CHAR) AS successful,
  CAST(SUM(CASE WHEN d.result = 'FAILURE' THEN 1 ELSE 0 END) AS CHAR) AS failed
FROM lake.cicd_deployments d
JOIN lake.project_mapping pm ON d.cicd_scope_id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND d.finished_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND d.environment = 'production'
GROUP BY DATE_FORMAT(d.finished_date, '%Y-%m-%d')
ORDER BY deploy_date DESC
LIMIT 30
```

## Change Fail Rate

```sql
SELECT
  CAST(COUNT(*) AS CHAR) AS total_deployments,
  CAST(SUM(CASE WHEN d.result = 'FAILURE' THEN 1 ELSE 0 END) AS CHAR) AS failed_deployments,
  CAST(ROUND(
    SUM(CASE WHEN d.result = 'FAILURE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
  ) AS CHAR) AS change_fail_rate_pct
FROM lake.cicd_deployments d
JOIN lake.project_mapping pm ON d.cicd_scope_id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND d.finished_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND d.environment = 'production'
```

## Pipeline Success Rate (by repo)

```sql
SELECT
  r.name AS repo,
  COUNT(*) AS total_pipelines,
  CAST(ROUND(
    SUM(CASE WHEN p.result = 'SUCCESS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
  ) AS CHAR) AS success_rate_pct,
  CAST(ROUND(AVG(p.duration_sec) / 60, 1) AS CHAR) AS avg_duration_min
FROM lake.cicd_pipelines p
JOIN lake.repos r ON p.cicd_scope_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND p.finished_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND p.status = 'DONE'
GROUP BY r.name
ORDER BY total_pipelines DESC
LIMIT 20
```

## Open PR Aging

```sql
SELECT
  pr.title,
  pr.url,
  pr.author_name AS author,
  pr.created_date,
  DATEDIFF(CURDATE(), pr.created_date) AS age_days,
  CASE
    WHEN DATEDIFF(CURDATE(), pr.created_date) > 14 THEN 'CRITICAL'
    WHEN DATEDIFF(CURDATE(), pr.created_date) > 7 THEN 'WARNING'
    ELSE 'OK'
  END AS status
FROM lake.pull_requests pr
JOIN lake.repos r ON pr.base_repo_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND pr.status = 'OPEN'
ORDER BY pr.created_date ASC
LIMIT 30
```

## Retest Detection (PRs with /retest comments)

> Prefer the `analyze_pr_retests` MCP tool for this analysis.

```sql
SELECT
  pr.title,
  pr.url,
  COUNT(prc.id) AS retest_count,
  pr.status
FROM lake.pull_requests pr
JOIN lake.pull_request_comments prc ON prc.pull_request_id = pr.id
JOIN lake.repos r ON pr.base_repo_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND prc.body LIKE '%/retest%'
  AND pr.created_date >= DATE_SUB(NOW(), INTERVAL 90 DAY)
GROUP BY pr.id, pr.title, pr.url, pr.status
HAVING COUNT(prc.id) > 3
ORDER BY retest_count DESC
LIMIT 20
```

## Lead Time for Changes

```sql
SELECT
  r.name AS repo,
  CAST(ROUND(AVG(
    TIMESTAMPDIFF(HOUR, pr.created_date, d.finished_date)
  ), 1) AS CHAR) AS avg_lead_time_hours,
  COUNT(*) AS sample_size
FROM lake.pull_requests pr
JOIN lake.cicd_deployment_commits dc ON dc.commit_sha IN (
  SELECT prc.commit_sha FROM lake.pull_request_commits prc
  WHERE prc.pull_request_id = pr.id
)
JOIN lake.cicd_deployments d ON d.id = dc.cicd_deployment_id
JOIN lake.repos r ON pr.base_repo_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND d.finished_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  AND d.result = 'SUCCESS'
  AND d.environment = 'production'
GROUP BY r.name
ORDER BY avg_lead_time_hours DESC
LIMIT 20
```

## PR Size Distribution

```sql
SELECT
  CASE
    WHEN (pr.additions + pr.deletions) <= 50 THEN 'XS (1-50)'
    WHEN (pr.additions + pr.deletions) <= 200 THEN 'S (51-200)'
    WHEN (pr.additions + pr.deletions) <= 500 THEN 'M (201-500)'
    WHEN (pr.additions + pr.deletions) <= 1000 THEN 'L (501-1000)'
    ELSE 'XL (>1000)'
  END AS size_category,
  COUNT(*) AS pr_count,
  CAST(ROUND(AVG(COALESCE(prm.pr_cycle_time, 0) / 60), 1) AS CHAR) AS avg_cycle_hours
FROM lake.pull_requests pr
LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id
JOIN lake.repos r ON pr.base_repo_id = r.id
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = '{PROJECT_NAME}'
  AND pr.merged_date IS NOT NULL
  AND pr.merged_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY size_category
ORDER BY
  CASE size_category
    WHEN 'XS (1-50)' THEN 1
    WHEN 'S (51-200)' THEN 2
    WHEN 'M (201-500)' THEN 3
    WHEN 'L (501-1000)' THEN 4
    ELSE 5
  END
```
