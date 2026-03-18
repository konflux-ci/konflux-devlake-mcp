# Report Category Definitions

Reference for the scaffold skill. Each category maps to a DSPy task file,
child pipeline template variables, and specific DevLake data sources.

## Categories

### dora
- **Name**: DORA Metrics
- **Description**: Deployment frequency, lead time, change fail rate, recovery time, rework rate
- **Prompt Dir**: `dora`
- **Task File**: `dora-metrics.yml`
- **Subgroup Task File**: (same — DORA is typically org-level)
- **SCHEDULER_TYPE aliases**: `dora`, `dora_all`, `all`
- **Scope**: Org-level preferred, subgroup optional

### pr_cycle_time
- **Name**: PR Cycle Time
- **Description**: Code change cycle time breakdown — coding, pickup, review time
- **Prompt Dir**: `pr-cycle-time`
- **Task File**: `pr-cycle-time.yml`
- **Subgroup Task File**: `pr-cycle-time-subgroup.yml`
- **SCHEDULER_TYPE aliases**: `pr_cycle_time`, `dora_all`, `all`
- **Scope**: Both org-level and subgroup

### engineering_excellence
- **Name**: Engineering Excellence
- **Description**: CI bottlenecks, PR analysis, flaky tests, GH Actions health, bottleneck score
- **Prompt Dir**: `engineering-excellence`
- **Task File**: `engineering-excellence.yml`
- **Subgroup Task File**: (same)
- **SCHEDULER_TYPE aliases**: `engineering_excellence`, `dora_all`, `all`
- **Scope**: Subgroup preferred

### coverage
- **Name**: Code Coverage
- **Description**: Test coverage metrics across repositories with trends
- **Prompt Dir**: `coverage`
- **Task File**: `coverage.yml`
- **Subgroup Task File**: (same)
- **SCHEDULER_TYPE aliases**: `coverage`, `all`
- **Scope**: Both org-level and subgroup

### retest
- **Name**: Retest Analysis
- **Description**: PR retest patterns, common failure identification, resource impact
- **Prompt Dir**: `retest`
- **Task File**: `single-repo.yml`
- **Subgroup Task File**: `summary.yml`
- **SCHEDULER_TYPE aliases**: `retest`, `all`
- **Scope**: Per-repo jobs + summary
