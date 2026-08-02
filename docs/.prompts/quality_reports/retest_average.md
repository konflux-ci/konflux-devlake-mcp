# Manual Retest Analysis Prompt

This prompt generates a comprehensive analysis of manual retest activity (comments containing `/retest` or `/rerun`) across pull requests in a specific repository within the Secureflow - Konflux - Global project. The analysis helps identify patterns, root causes, and actionable insights to improve CI/CD reliability and reduce developer friction.

## Usage

Replace placeholders with your specific values:

- `[REPO_NAME]` with your target repository (e.g., `integration-service`, `build-service`, `release-service`, `infra-deployments`)
- `[DevLake Project]` with your project name (e.g., `Secureflow - Konflux - Global`, `Project Alpha`, `DevOps - Production`)
- `[Desired time]` with the analysis window (e.g., `3 months`, `6 months`, `1 year`)

## Prompt

```txt
I need a detailed analysis of all pull requests in the [REPO_NAME] repository
within the [DevLake Project] project that required manual retest
commands (comments containing "/retest" or "/rerun") in the last [Desired time].

Please provide:
1. Total count of manual /retest and /rerun comments (exclude bot comments)
2. Number of PRs affected
3. Average retests per PR
4. Top 10-15 PRs with most retests including:
   - PR title and URL
   - Number of retests
   - PR duration (days)
   - Changes (lines added/deleted)
   - Status (MERGED/OPEN/CLOSED)
5. Analysis of root causes and failure patterns
6. Breakdown by PR category (bug fixes, features, dependencies, etc.)
7. Timeline visualization showing retest activity over time
8. Actionable recommendations to reduce retest frequency

Do NOT include:
- Estimated costs or financial impacts
- Author usernames or personal attribution
- Hypothetical scenarios or projections

Focus on technical patterns, systemic issues, and actionable insights.
```

## Expected Output Format

The analysis should follow this structure:

### Executive Summary

- Total manual `/retest` and `/rerun` comments
- Number of affected PRs
- Average retests per PR
- Time period analyzed

### Detailed Findings

- Top 10-15 PRs ranked by retest count
- Breakdown by PR category (bug fixes, features, dependencies, etc.)
- Timeline showing retest activity patterns
- Root cause analysis identifying systemic issues

### Recommendations

Prioritized action items focusing on:

- Immediate fixes for critical issues
- Short-term improvements
- Long-term systematic improvements

### Visualizations

- Retest distribution chart
- Timeline activity graph
- Category breakdown charts
- PR lifecycle impact analysis

## Repository-Specific Considerations

### Integration Service

- High-frequency service with complex testing
- Often requires retests due to E2E test flakiness
- Focus on HTTP client reliability and nil pointer access patterns

### Infra-Deployments

- Lower retest frequency
- Manifest formatting common issue
- Service update deployments may need optimization

### Build/Release Services

- Typically lower retest counts
- Focus on pipeline reliability
- Deployment-related issues more common

## Notes

- This analysis is based on data from the DevLake MCP database
- Only includes non-bot manual retest comments
- Analysis window: Last 3 months
- Focuses on technical patterns, not individual performance
