-- Konflux DevLake Test Database Schema
-- This creates the test database structure for integration tests

USE lake;

-- Incidents table
CREATE TABLE incidents (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_key VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    severity VARCHAR(50) DEFAULT 'MEDIUM',
    component VARCHAR(255),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolution_date TIMESTAMP NULL,
    lead_time_minutes INT DEFAULT 0,
    url VARCHAR(1000),
    assignee VARCHAR(255),
    reporter VARCHAR(255),
    labels JSON,

    INDEX idx_incident_key (incident_key),
    INDEX idx_status (status),
    INDEX idx_component (component),
    INDEX idx_created_date (created_date),
    INDEX idx_updated_date (updated_date)
);

-- CICD Deployments table
CREATE TABLE cicd_deployments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    deployment_id VARCHAR(255) NOT NULL,
    display_title VARCHAR(500),
    url VARCHAR(1000),
    result VARCHAR(50) DEFAULT 'UNKNOWN',
    status VARCHAR(50) DEFAULT 'PENDING',
    environment VARCHAR(100) DEFAULT 'UNKNOWN',
    project VARCHAR(255),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    started_date TIMESTAMP NULL,
    finished_date TIMESTAMP NULL,
    duration_sec INT DEFAULT 0,
    commit_sha VARCHAR(255),
    branch VARCHAR(255),

    UNIQUE KEY uk_deployment_id (deployment_id),
    INDEX idx_result (result),
    INDEX idx_environment (environment),
    INDEX idx_project (project),
    INDEX idx_finished_date (finished_date)
);

-- CICD Deployment Commits table
CREATE TABLE cicd_deployment_commits (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    deployment_id VARCHAR(255) NOT NULL,
    cicd_deployment_id VARCHAR(255) NOT NULL,
    cicd_scope_id VARCHAR(255),
    display_title VARCHAR(500),
    url VARCHAR(1000),
    result VARCHAR(50) DEFAULT 'UNKNOWN',
    environment VARCHAR(100) DEFAULT 'UNKNOWN',
    finished_date TIMESTAMP NULL,
    commit_sha VARCHAR(255) NOT NULL,
    commit_message TEXT,
    commit_author VARCHAR(255),
    commit_date TIMESTAMP NULL,
    _raw_data_table VARCHAR(255) DEFAULT '',

    INDEX idx_deployment_id (deployment_id),
    INDEX idx_cicd_deployment_id (cicd_deployment_id),
    INDEX idx_commit_sha (commit_sha),
    INDEX idx_finished_date (finished_date),
    FOREIGN KEY (deployment_id) REFERENCES cicd_deployments(deployment_id) ON DELETE CASCADE
);

-- Project Mapping table
CREATE TABLE project_mapping (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    `table` VARCHAR(255) NOT NULL DEFAULT 'cicd_scopes',
    row_id VARCHAR(255),
    raw_data_table VARCHAR(255),
    params JSON,

    INDEX idx_project_name (project_name),
    INDEX idx_table (`table`),
    INDEX idx_row_id (row_id)
);
