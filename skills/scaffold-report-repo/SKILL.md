---
name: scaffold-report-repo
description: >
  Trigger when the user wants to create a new GitLab repo for automated,
  scheduled engineering reports — setting up CI pipelines, DSPy prompts,
  and GitLab Pages publishing from DevLake data.
disable-model-invocation: true
---

# Scaffold Report Repo Skill

Generate a complete GitLab repository structure with CI pipelines for automated, scheduled DevLake report generation and GitLab Pages publishing.

This skill follows the **Pipeline + Inversion pattern**: gather all requirements through structured questions before generating any files.

## Available Resources

Read these as needed:

- `references/category-definitions.md` — Report category metadata: keys, prompt dirs, task files, SCHEDULER_TYPE aliases, scope preferences. **Read this before Step 3.**
- `templates/` — Jinja2 templates for all generated files. The skill renders these with user-provided variables.
- `../../skills/devlake/references/devlake-schema.md` — Actual prod schema (for verifying SQL patterns in prompts)

## Interactive Workflow

**IMPORTANT: DO NOT generate any files until ALL steps (1-7) are complete and the user has confirmed the summary in Step 7. Each step must be answered before proceeding to the next.**

### Step 1: DevLake MCP Discovery

Query the user's configured DevLake MCP server to discover available organizations.

```
Querying DevLake MCP for available projects...

Available organizations:
  1. Org A
  2. Org B
  3. Org C

Select organization: [user picks or provides in prompt]
```

If the user already specified the org in their prompt, skip discovery.

**Gate: Do not proceed until organization is confirmed.**

### Step 2: Sub-group Discovery

Query for sub-groups/teams under the selected organization.

```
Sub-groups under "Org A":
  1. Team Alpha (12 repos)
  2. Team Beta (8 repos)
  3. Team Gamma (15 repos)

Select sub-groups for per-team reports (comma-separated, or "all"):
```

**Gate: Do not proceed until sub-groups are confirmed.**

### Step 3: Report Category Selection

Read `references/category-definitions.md` for the full category list.

```
Available report categories:
  1. DORA Metrics - Deployment frequency, lead time, change fail rate, recovery time
  2. PR Cycle Time - Code change cycle time breakdown (coding, pickup, review)
  3. Engineering Excellence - CI bottlenecks, PR analysis, flaky tests, GH Actions health
  4. Code Coverage - Test coverage metrics across repositories with trends
  5. Retest Analysis - PR retest patterns, common failure identification

Select categories (comma-separated, or "all" for default): [all]
```

**Gate: Do not proceed until categories are confirmed.**

### Step 4: Pipeline Configuration

```
a. Pipeline structure:
   1. Org-level only - Single report for the entire organization
   2. Sub-group level (default) - Per-team reports + org-level summary
   3. Both - Org-level + per-team reports
   Select: [2]

b. GitLab runner tag (REQUIRED - wrong tag causes jobs to hang):
   Tag: [user provides, e.g., "shared", "docker", "kubernetes"]

c. AI provider:
   1. claude (default)
   2. gemini
   3. openai
   Select: [1]
```

### Step 5: CI Template Include Method

```
cicaddy-gitlab CI template include method:
  a. remote (default) - include from GitHub raw URL
  b. project - include from internal GitLab project (provide path)

Select method: [a]
```

If user selects `b`, ask for the GitLab project path (e.g., `my-group/cicaddy-gitlab-mirror`).

### Step 6: SSL Certificate Configuration (Optional)

```
Does your GitLab instance or DevLake MCP endpoint use certificates
signed by an internal/custom CA? (e.g., corporate CA, self-signed)

  a. No (default) - standard public CA certificates are sufficient
  b. Yes - provide the CA certificate bundle download URL

If yes, provide:
  CA certificate bundle URL: [e.g., https://certs.example.com/ca-bundle.pem]
```

If the user provides a CA cert URL, the scaffold generates:
- `.gitlab/templates/base/ssl_setup.yml` with the cert download and trust store configuration
- Child pipelines extend `.ssl_setup` in their `before_script`
- `VARIABLES.md` documents the `CUSTOM_CA_CERT_URL` variable as an override option

### Step 7: Confirmation & Generate

Present a summary of all choices and ask for confirmation before generating.

```
Summary:
  Organization:      Org A
  Sub-groups:        Team Alpha, Team Beta, Team Gamma
  Categories:        DORA, PR Cycle Time, Engineering Excellence, Coverage, Retest
  Pipeline structure: Sub-group level
  Runner tag:        shared
  AI provider:       claude
  CI template:       remote (GitHub)
  SSL cert:          No
  Output directory:  ./my-org-reports/

Confirm and generate? [yes/no]
```

**Gate: DO NOT generate files until the user confirms.**

Then render templates from `templates/` and write the repo structure to the user's specified directory.

## Generated Repo Structure

```
<repo-name>/
├── .gitlab-ci.yml                         # Main entry: stages, workflow rules, includes
├── .gitlab/
│   ├── templates/
│   │   ├── base/
│   │   │   └── ssl_setup.yml              # (optional) Custom CA cert setup
│   │   └── mcp/
│   │       └── devlake.yml                # MCP server config (user's endpoint + auth)
│   ├── workflows/
│   │   ├── scheduled-analysis.yml         # Trigger jobs with SCHEDULER_TYPE routing
│   │   └── pages-deployment.yml           # GitLab Pages artifact collection
│   ├── child-pipelines/
│   │   ├── dora.yml                       # DORA: org-level job
│   │   ├── pr-cycle-time.yml              # PR Cycle Time: org-level + per-subgroup jobs
│   │   ├── engineering-excellence.yml     # Eng Excellence: per-subgroup jobs
│   │   ├── coverage.yml                   # Coverage: org-level + per-subgroup jobs
│   │   └── retest.yml                     # Retest: per-repo jobs + summary
│   ├── prompts/                           # DSPy task files per category
│   │   └── ...
│   └── report-template.html               # Shared HTML/CSS report template
├── VARIABLES.md                           # CI/CD variable setup instructions
└── README.md                              # Setup, usage, report categories
```

## Gotchas

- **Runner tags** — ask the user for their GitLab runner tag (Step 4b). There is no universal default; using the wrong tag causes jobs to hang in "pending" indefinitely.
- **AI provider API key** — the generated repo requires an AI provider API key as a CI/CD variable. Remind the user to set it during the confirmation step.
- **`include: remote:` may be blocked** — some GitLab instances block external URLs in CI includes. If the user reports this, suggest switching to `project:` method with a synced mirror repo.
- **Artifact expiration** — generated pipelines set `expire_in: 30 days`. Warn users that older reports will be deleted unless they adjust this or copy to GitLab Pages.
- **SCHEDULER_TYPE must be set per schedule** — the variable is per-schedule, not global. Each GitLab schedule needs its own `SCHEDULER_TYPE` value. Users often miss this and wonder why all reports run on every schedule.
- **Child pipeline context** — `AI_TASK_FILE` paths use `../` prefix because child pipelines run in a subdirectory. If users restructure the generated repo, these paths will break.
- **MCP endpoint must be HTTPS** — the DevLake MCP endpoint should use HTTPS to protect the auth token in transit. Warn during Step 7 if the user provides an HTTP URL.
- **Schema alignment** — the generated DSPy task files reference tables/columns validated against the deployed Konflux DevLake instance. Check `skills/VERSION` for the validated MCP version.

## Design Principles

- **No internal names**: All templates use variables (`{{DEVLAKE_PROJECT_NAME}}`, `{{DEVLAKE_MCP_ENDPOINT}}`)
- **Generic prompts**: DSPy task files reference standard DevLake table schemas
- **Consistent pattern**: Every category uses the same cicaddy agent + DSPy task approach
- **Version-stamped**: Include refs pinned to the cicaddy-gitlab version at generation time
