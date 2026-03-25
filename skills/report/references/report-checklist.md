# Report Quality Checklist

Use this checklist to verify generated reports before saving.

## Structure
- [ ] Starts with `<!DOCTYPE html>` — complete standalone document
- [ ] Uses report-template.html CSS design system (do not inline custom styles)
- [ ] Header contains team badge, report date, title, subtitle
- [ ] Metrics grid has 3-8 cards with appropriate color classes
- [ ] Every section has a kebab-case `id` attribute
- [ ] Every section header has a clickable anchor link with `.anchor-hash` span
- [ ] Executive summary section appears near the top
- [ ] Recommendations section appears at the bottom
- [ ] Footer with report metadata

## Data Quality
- [ ] All metric values are sourced from actual DevLake MCP tool calls or SQL queries (no hallucinated numbers)
- [ ] DECIMAL values are CAST to CHAR in any custom SQL queries
- [ ] Tables have explanation boxes explaining how to read them
- [ ] Status badges use correct classes: `.status-healthy`, `.status-warning`, `.status-critical`
- [ ] Priority tags use correct classes: `.priority-p0`, `.priority-p1`, `.priority-p2`
- [ ] Time periods are clearly labeled (e.g., "Last 30 days")

## DORA-Specific
- [ ] All 5 metrics present: Deployment Frequency, Lead Time, Change Fail Rate, Recovery Time, Rework Rate
- [ ] Each metric graded against DORA benchmarks (Elite/High/Medium/Low)
- [ ] Benchmark thresholds stated in each section

## Formatting
- [ ] No broken HTML tags
- [ ] No raw SQL or JSON in the report body
- [ ] Fonts load correctly (Space Grotesk + JetBrains Mono via Google Fonts)
- [ ] Responsive layout works (check `.metrics-grid` auto-fit)
- [ ] Color classes match data semantics (green=good, amber=warning, red=critical)
