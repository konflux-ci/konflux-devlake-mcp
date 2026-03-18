---
name: report
description: >
  Trigger when the user wants a formatted HTML report file — DORA metrics report,
  PR cycle time report, engineering excellence report, coverage report, or retest
  analysis report. Not for quick questions (use devlake skill instead).
disable-model-invocation: true
---

# Report Generation Skill

Generate a structured HTML engineering report using DevLake MCP data. This skill follows the **Generator pattern**: load the DSPy task template, read the style guide, gather data, produce the report.

## Available Resources

Read these as needed during report generation:

- `references/report-checklist.md` — Quality checklist to verify the report before saving. **Read this after generating the report to self-check.**
- `../../docs/.prompts/` — Existing prompt templates for coverage and retest reports
- Report template: `references/report-template.html` — HTML/CSS design system with component usage guide

## Report Categories

| Category | MCP Tools to Use | Prompt Reference |
|----------|-----------------|------------------|
| DORA Metrics | `get_deployment_frequency`, `get_lead_time_for_changes`, `get_failed_deployment_recovery_time` | DORA 2025 benchmarks |
| PR Cycle Time | `get_pr_cycle_time` | Coding/Pickup/Review breakdown |
| Engineering Excellence | `get_github_actions_health`, `analyze_pr_retests`, `get_pr_stats` | Bottleneck score |
| Code Coverage | `get_codecov_coverage`, `get_codecov_summary` | `docs/.prompts/coverage/` |
| Retest Analysis | `analyze_pr_retests` | `docs/.prompts/quality_reports/` |

## Workflow

1. **Ask the user** which report category they want (or infer from context)
2. **Read the HTML template** from `references/report-template.html` — understand the CSS component library and placeholder format
3. **Gather scope from user**:
   - `project_name` — the DevLake project/organization name
   - Team/sub-group name (optional)
   - Analysis period (default: 30 days)
4. **Gather data using MCP tools** — prefer specialized tools over raw SQL:
   - For DORA: use `get_deployment_frequency`, `get_lead_time_for_changes`, `get_failed_deployment_recovery_time`
   - For PR metrics: use `get_pr_cycle_time`, `get_pr_stats`
   - For retests: use `analyze_pr_retests`
   - For coverage: use `get_codecov_coverage`, `get_codecov_summary`
   - For custom queries: use `execute_query` with patterns from `skills/devlake/references/sql-patterns.md`
5. **Produce HTML output**:
   - Use the report template CSS classes — do not write custom CSS
   - Replace template placeholders: `{{REPORT_TITLE}}`, `{{BADGE_LABEL}}`, `{{REPORT_DATE}}`, `{{ANALYSIS_DAYS}}`, etc.
   - Every section must have a kebab-case `id` and clickable `.section-anchor`
   - Include `.metrics-grid` cards at the top, `.executive-summary` box, data tables with `.explanation-box`, and recommendations
6. **Self-check**: Read `references/report-checklist.md` and verify the report against it
7. **Save the report** to the user's working directory as `<category>_report_<date>.html`

## Gotchas

- **Don't skip the HTML template read** — the report template has specific CSS variables, component classes, and placeholder conventions. Reports that don't use the template look broken.
- **Section IDs must be kebab-case** — `executive-summary` not `executiveSummary`. The anchor links depend on this format.
- **Metric card color classes** — use `.success` (green) for good values, `.warning` (amber) for concerning, `.danger` (red) for critical, `.info` (cyan) for neutral. Don't hardcode color values.
- **Chart.js is optional** — only use `<canvas>` charts if the data genuinely benefits from visualization. Tables are usually clearer for small datasets.
- **Font loading** — the template uses Google Fonts (Space Grotesk + JetBrains Mono). These require internet access to render.
- **Large reports** — if a report has more than 8 data tables, consider adding a table of contents after the header.
- **Empty data** — if a query returns no data for a section, don't omit the section. Include it with a note explaining no data was found for the period.
