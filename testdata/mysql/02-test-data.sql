-- Test data for integration tests
USE lake;

-- Insert test incidents
INSERT INTO incidents (
    incident_key, title, description, status, severity, component,
    created_date, updated_date, resolution_date, lead_time_minutes,
    url, assignee, reporter, labels
) VALUES
(
    'INC-2024-001',
    'API Service High Response Time',
    'The API service is experiencing high response times affecting user experience',
    'DONE',
    'HIGH',
    'api-service',
    '2024-01-15 10:00:00',
    '2024-01-15 14:30:00',
    '2024-01-15 14:30:00',
    270,
    'https://konflux.example.com/incidents/INC-2024-001',
    'john.doe@example.com',
    'monitoring@example.com',
    '{"environment": "production", "team": "platform"}'
),
(
    'INC-2024-002',
    'Database Connection Pool Exhaustion',
    'Database connection pool is exhausted causing service failures',
    'IN_PROGRESS',
    'CRITICAL',
    'database-service',
    '2024-01-16 08:15:00',
    '2024-01-16 09:45:00',
    NULL,
    0,
    'https://konflux.example.com/incidents/INC-2024-002',
    'jane.smith@example.com',
    'alerts@example.com',
    '{"environment": "production", "team": "database"}'
),
(
    'INC-2024-003',
    'Frontend Build Pipeline Failure',
    'Frontend build pipeline is failing due to dependency issues',
    'OPEN',
    'MEDIUM',
    'frontend-service',
    '2024-01-17 12:30:00',
    '2024-01-17 12:30:00',
    NULL,
    0,
    'https://konflux.example.com/incidents/INC-2024-003',
    NULL,
    'ci-cd@example.com',
    '{"environment": "staging", "team": "frontend"}'
);

-- Insert test deployments
INSERT INTO cicd_deployments (
    deployment_id, display_title, url, result, status, environment, project,
    created_date, updated_date, started_date, finished_date, duration_sec,
    commit_sha, branch
) VALUES
(
    'deploy-api-prod-001',
    'API Service Production Deployment v1.2.3',
    'https://konflux.example.com/deployments/deploy-api-prod-001',
    'SUCCESS',
    'COMPLETED',
    'PRODUCTION',
    'Konflux_Pilot_Team',
    '2024-01-15 09:00:00',
    '2024-01-15 09:15:00',
    '2024-01-15 09:00:00',
    '2024-01-15 09:15:00',
    900,
    'abc123def456',
    'main'
),
(
    'deploy-db-prod-002',
    'Database Service Production Deployment v2.1.0',
    'https://konflux.example.com/deployments/deploy-db-prod-002',
    'FAILURE',
    'FAILED',
    'PRODUCTION',
    'Konflux_Pilot_Team',
    '2024-01-16 07:30:00',
    '2024-01-16 08:00:00',
    '2024-01-16 07:30:00',
    '2024-01-16 08:00:00',
    1800,
    'def456ghi789',
    'main'
),
(
    'deploy-frontend-staging-003',
    'Frontend Service Staging Deployment v3.0.0-rc1',
    'https://konflux.example.com/deployments/deploy-frontend-staging-003',
    'SUCCESS',
    'COMPLETED',
    'STAGING',
    'Konflux_Frontend_Team',
    '2024-01-17 11:00:00',
    '2024-01-17 11:10:00',
    '2024-01-17 11:00:00',
    '2024-01-17 11:10:00',
    600,
    'ghi789jkl012',
    'release/v3.0.0'
);

-- Insert deployment commits
INSERT INTO cicd_deployment_commits (
    deployment_id, cicd_deployment_id, cicd_scope_id, display_title, url, result, environment, finished_date,
    commit_sha, commit_message, commit_author, commit_date, _raw_data_table
) VALUES
(
    'deploy-api-prod-001',
    'deploy-api-prod-001',
    'scope-001',
    'API Service Production Deployment v1.2.3',
    'https://konflux.example.com/deployments/deploy-api-prod-001',
    'SUCCESS',
    'PRODUCTION',
    '2024-01-15 09:15:00',
    'abc123def456',
    'feat: improve API response time and add caching',
    'john.doe@example.com',
    '2024-01-15 08:45:00',
    'raw_deployments'
),
(
    'deploy-db-prod-002',
    'deploy-db-prod-002',
    'scope-002',
    'Database Service Production Deployment v2.1.0',
    'https://konflux.example.com/deployments/deploy-db-prod-002',
    'FAILURE',
    'PRODUCTION',
    '2024-01-16 08:00:00',
    'def456ghi789',
    'fix: resolve connection pool configuration issues',
    'jane.smith@example.com',
    '2024-01-16 07:15:00',
    'raw_deployments'
),
(
    'deploy-frontend-staging-003',
    'deploy-frontend-staging-003',
    'scope-003',
    'Frontend Service Staging Deployment v3.0.0-rc1',
    'https://konflux.example.com/deployments/deploy-frontend-staging-003',
    'SUCCESS',
    'STAGING',
    '2024-01-17 11:00:00',
    'ghi789jkl012',
    'feat: add new dashboard components and improve UX',
    'bob.wilson@example.com',
    '2024-01-17 10:30:00',
    'raw_deployments'
);

-- Insert project mappings
INSERT INTO project_mapping (
    project_name, `table`, row_id, raw_data_table, params
) VALUES
(
    'Konflux_Pilot_Team',
    'cicd_scopes',
    'scope-001',
    'raw_deployments',
    '{"source": "jenkins", "environment": ["PRODUCTION", "STAGING"]}'
),
(
    'Konflux_Pilot_Team',
    'cicd_scopes',
    'scope-002',
    'raw_deployments',
    '{"source": "jenkins", "environment": ["PRODUCTION", "STAGING"]}'
),
(
    'Konflux_Frontend_Team',
    'cicd_scopes',
    'scope-003',
    'raw_deployments',
    '{"source": "github-actions", "environment": ["STAGING", "DEVELOPMENT"]}'
),
(
    'Konflux_Platform_Team',
    'incidents',
    'incident-001',
    'raw_incidents',
    '{"source": "jira", "severity": ["HIGH", "CRITICAL"]}'
);
