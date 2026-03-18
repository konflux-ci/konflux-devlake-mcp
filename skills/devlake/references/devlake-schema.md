# DevLake Database Schema Reference

Key tables in the DevLake `lake` database. All queries must use `lake.table_name` format.
Schema validated against production Konflux DevLake instance.

## Core Tables

### `lake.pull_requests`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR(255) | Unique PR identifier |
| `base_repo_id` | VARCHAR(191) | Target repository ID (FK to `repos.id`) |
| `head_repo_id` | VARCHAR(191) | Source repository ID (for forks) |
| `title` | LONGTEXT | PR title |
| `description` | LONGTEXT | PR body/description |
| `url` | VARCHAR(255) | PR URL |
| `author_id` | VARCHAR(100) | Author account ID |
| `author_name` | VARCHAR(100) | Author display name |
| `status` | VARCHAR(100) | OPEN, CLOSED, MERGED |
| `original_status` | VARCHAR(100) | Raw status from source platform |
| `type` | VARCHAR(100) | PR type classification |
| `component` | VARCHAR(100) | Component tag |
| `created_date` | DATETIME | PR creation time |
| `merged_date` | DATETIME | PR merge time (null if not merged) |
| `closed_date` | DATETIME | PR close time |
| `additions` | BIGINT | Lines added |
| `deletions` | BIGINT | Lines deleted |
| `base_ref` | VARCHAR(255) | Target branch |
| `head_ref` | VARCHAR(255) | Source branch |
| `base_commit_sha` | VARCHAR(40) | Target branch commit SHA |
| `head_commit_sha` | VARCHAR(40) | Source branch commit SHA |
| `merge_commit_sha` | VARCHAR(40) | Merge commit SHA |
| `merged_by_id` | VARCHAR(100) | Merger account ID |
| `merged_by_name` | VARCHAR(100) | Merger display name |
| `parent_pr_id` | VARCHAR(100) | Parent PR (for stacked PRs) |
| `pull_request_key` | BIGINT | Platform-specific PR number |
| `is_draft` | TINYINT | 1 if draft PR |

> **Important:** The `coding_timespan`, `review_lag`, `review_timespan`, `merge_timespan`
> columns exist in upstream Apache DevLake but are **NOT present** in Konflux DevLake.
> Use `lake.project_pr_metrics` for cycle time data, or the `get_pr_cycle_time` MCP tool.

### `lake.project_pr_metrics`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | PR ID (FK to `pull_requests.id`) |
| `pr_cycle_time` | BIGINT | Total cycle time in minutes (1st commit to merged) |
| `pr_coding_time` | BIGINT | Coding time in minutes (1st commit to PR created) |
| `pr_pickup_time` | BIGINT | Pickup time in minutes (PR created to 1st review) |
| `pr_review_time` | BIGINT | Review time in minutes (1st review to merged) |

Join: `LEFT JOIN lake.project_pr_metrics prm ON pr.id = prm.id`

### `lake.cicd_deployments`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Deployment identifier |
| `cicd_scope_id` | VARCHAR | Associated scope/project |
| `name` | VARCHAR | Deployment name |
| `result` | VARCHAR | SUCCESS, FAILURE, ABORT |
| `status` | VARCHAR | DONE, IN_PROGRESS |
| `environment` | VARCHAR | Target environment (production, staging) |
| `started_date` | DATETIME | Deployment start |
| `finished_date` | DATETIME | Deployment end |
| `duration_sec` | FLOAT | Duration in seconds |

### `lake.cicd_pipelines`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Pipeline identifier |
| `name` | VARCHAR | Pipeline name |
| `result` | VARCHAR | SUCCESS, FAILURE, ABORT |
| `status` | VARCHAR | DONE, IN_PROGRESS |
| `type` | VARCHAR | CI, CD |
| `duration_sec` | FLOAT | Duration in seconds |
| `created_date` | DATETIME | Pipeline creation |
| `finished_date` | DATETIME | Pipeline completion |
| `cicd_scope_id` | VARCHAR | Associated scope |

### `lake.cicd_tasks`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Task identifier |
| `name` | VARCHAR | Job/task name |
| `pipeline_id` | VARCHAR | Parent pipeline |
| `result` | VARCHAR | SUCCESS, FAILURE |
| `status` | VARCHAR | DONE, IN_PROGRESS |
| `type` | VARCHAR | BUILD, TEST, DEPLOY |
| `duration_sec` | FLOAT | Duration in seconds |
| `started_date` | DATETIME | Task start |
| `finished_date` | DATETIME | Task end |

### `lake.repos`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Repository identifier |
| `name` | VARCHAR | Repository name |
| `url` | VARCHAR | Repository URL |
| `language` | VARCHAR | Primary language |
| `created_date` | DATETIME | Repository creation |

### `lake.issues`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Issue identifier |
| `title` | VARCHAR | Issue title |
| `status` | VARCHAR | Issue status |
| `type` | VARCHAR | BUG, INCIDENT, REQUIREMENT |
| `priority` | VARCHAR | Priority level |
| `created_date` | DATETIME | Issue creation |
| `resolution_date` | DATETIME | Issue resolution |
| `lead_time_minutes` | BIGINT | Time to resolution in minutes |

### `lake.accounts`
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Account identifier |
| `full_name` | VARCHAR | Display name |
| `user_name` | VARCHAR | Username |
| `email` | VARCHAR | Email address |

## Join / Mapping Tables

### `lake.project_mapping`
Maps projects to scopes. **Required** for filtering by DevLake project.
- `project_name` — DevLake project name
- `table` — Source table name (e.g., `'repos'`)
- `row_id` — FK to the source table's ID

Example join:
```sql
JOIN lake.project_mapping pm ON r.id = pm.row_id
  AND pm.`table` = 'repos'
WHERE pm.project_name = 'My Project'
```

### `lake.pull_request_commits`
Links PRs to commits.
- `pull_request_id` — FK to `pull_requests.id`
- `commit_sha` — Commit SHA
- `commit_author_name` — Author name
- `commit_author_email` — Author email
- `commit_authored_date` — Authored timestamp

### `lake.pull_request_comments`
PR review comments.
- `id` — Comment ID
- `pull_request_id` — FK to `pull_requests.id`
- `account_id` — Commenter account ID
- `created_date` — Comment timestamp
- `body` — Comment text
- `type` — Comment type
- `review_id` — Review ID
- `status` — Comment status

### `lake.cicd_deployment_commits`
Links deployments to commits: `cicd_deployment_id` → `commit_sha`

## Codecov Tables

Coverage data uses vendor-specific tables (not standard DevLake tables):

- `_tool_codecov_coverages` — Coverage metrics per repo/flag
- `_tool_codecov_comparisons` — Patch coverage comparisons
- `_tool_codecov_commits` — Commit-level coverage data
- `_tool_codecov_repos` — Codecov repo mapping

Project scoping: `JOIN project_mapping pm ON c.repo_id = pm.row_id AND pm.table = '_tool_codecov_repos'`

## Table Relationships

```
pull_requests ──(base_repo_id)──► repos ◄──(row_id)── project_mapping
     │                                                       │
     ├──► pull_request_commits ──► cicd_deployment_commits   (table = 'repos')
     │                                     │
     ├──► pull_request_comments            ▼
     │                              cicd_deployments
     └──► project_pr_metrics
              (cycle time data)
```
