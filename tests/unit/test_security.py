#!/usr/bin/env python3
"""
Unit Tests for Security Module

Tests the security classes including SQL injection detection,
data masking, and security validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from utils.security import (
    KonfluxDevLakeSecurityManager,
    DataMasking,
)


@pytest.fixture
def sec_mgr() -> KonfluxDevLakeSecurityManager:
    """Create a KonfluxDevLakeSecurityManager for validator tests."""
    config = Mock()
    config.allowed_ips = []
    config.api_keys = {}
    return KonfluxDevLakeSecurityManager(config)


@pytest.mark.unit
@pytest.mark.security
class TestValidateIdentifier:
    """Test suite for validate_identifier method."""

    def test_valid_identifiers(self, sec_mgr):
        """Test that legitimate project/repo names pass validation."""
        valid_names = [
            "Konflux_Pilot_Team",
            "Secureflow - Konflux - Global",
            "Secureflow - Konflux - Integration Team",
            "Secureflow - Konflux - Build Team",
            "integration-service",
            "build-service",
            "my_repo/sub-path",
            "simple",
        ]
        for name in valid_names:
            assert sec_mgr.validate_identifier(name) == name

    def test_rejects_sql_injection_payloads(self, sec_mgr):
        """Test that SQL injection payloads are rejected."""
        malicious = [
            "x') UNION SELECT user,authentication_string,host FROM mysql.user -- ",
            "x'; DROP TABLE incidents; --",
            "x\\'; DROP TABLE--",
            "x`; SELECT * FROM mysql.user",
            "x /* comment */ OR 1=1",
            "x */ UNION SELECT 1",
        ]
        for payload in malicious:
            with pytest.raises(ValueError):
                sec_mgr.validate_identifier(payload)

    def test_allows_names_with_apostrophes_and_quotes(self, sec_mgr):
        """Test that legitimate names with apostrophes/quotes are allowed.

        These are safe because identifier values are bound as parameters.
        """
        allowed = [
            "O'Reilly",
            'Team "Alpha"',
            "repo`name",
            "project\\path",
        ]
        for name in allowed:
            assert sec_mgr.validate_identifier(name) == name

    def test_rejects_empty_string(self, sec_mgr):
        """Test that empty string is rejected."""
        with pytest.raises(ValueError, match="must be 1-256 characters"):
            sec_mgr.validate_identifier("")

    def test_rejects_none(self, sec_mgr):
        """Test that None is rejected."""
        with pytest.raises(ValueError, match="must be 1-256 characters"):
            sec_mgr.validate_identifier(None)

    def test_rejects_too_long(self, sec_mgr):
        """Test that overly long strings are rejected."""
        with pytest.raises(ValueError, match="must be 1-256 characters"):
            sec_mgr.validate_identifier("a" * 257)

    def test_custom_field_name_in_error(self, sec_mgr):
        """Test that custom field_name appears in error message."""
        with pytest.raises(ValueError, match="Invalid project_name"):
            sec_mgr.validate_identifier("test; DROP TABLE--", "project_name")


@pytest.mark.unit
@pytest.mark.security
class TestValidateDateString:
    """Test suite for validate_date_string method."""

    def test_valid_dates(self, sec_mgr):
        """Test that valid date formats pass."""
        assert sec_mgr.validate_date_string("2024-01-15") == "2024-01-15"
        assert sec_mgr.validate_date_string("2024-01-15 10:30:00") == "2024-01-15 10:30:00"
        assert sec_mgr.validate_date_string("2024-12-31") == "2024-12-31"

    def test_rejects_invalid_format(self, sec_mgr):
        """Test that invalid formats are rejected."""
        with pytest.raises(ValueError):
            sec_mgr.validate_date_string("01/15/2024")
        with pytest.raises(ValueError):
            sec_mgr.validate_date_string("2024-1-5")
        with pytest.raises(ValueError):
            sec_mgr.validate_date_string("not-a-date")

    def test_rejects_invalid_date(self, sec_mgr):
        """Test that impossible dates are rejected."""
        with pytest.raises(ValueError, match="not a valid date"):
            sec_mgr.validate_date_string("2024-02-30")
        with pytest.raises(ValueError, match="not a valid date"):
            sec_mgr.validate_date_string("2024-13-01")

    def test_rejects_injection_in_date(self, sec_mgr):
        """Test that injection payloads in date fields are rejected."""
        with pytest.raises(ValueError):
            sec_mgr.validate_date_string("2024-01-01' OR '1'='1")


@pytest.mark.unit
@pytest.mark.security
class TestValidatePositiveInt:
    """Test suite for validate_positive_int method."""

    def test_valid_integers(self, sec_mgr):
        """Test that valid integers pass."""
        assert sec_mgr.validate_positive_int(30) == 30
        assert sec_mgr.validate_positive_int(0) == 0
        assert sec_mgr.validate_positive_int("100") == 100

    def test_rejects_negative(self, sec_mgr):
        """Test that negative values are rejected."""
        with pytest.raises(ValueError, match="must be non-negative"):
            sec_mgr.validate_positive_int(-1)

    def test_rejects_non_numeric(self, sec_mgr):
        """Test that non-numeric values are rejected."""
        with pytest.raises(ValueError, match="must be a positive integer"):
            sec_mgr.validate_positive_int("abc")
        with pytest.raises(ValueError, match="must be a positive integer"):
            sec_mgr.validate_positive_int(None)

    def test_custom_field_name_in_error(self, sec_mgr):
        """Test that custom field_name appears in error message."""
        with pytest.raises(ValueError, match="Invalid days_back"):
            sec_mgr.validate_positive_int("bad", "days_back")


@pytest.mark.unit
@pytest.mark.security
class TestIsTableDenied:
    """Test suite for is_table_denied method."""

    def test_explicit_deny_tables(self, sec_mgr):
        """Test that explicitly denied tables are blocked."""
        assert sec_mgr.is_table_denied("_devlake_api_keys") is True
        assert sec_mgr.is_table_denied("auth_sessions") is True

    def test_connection_tables_denied(self, sec_mgr):
        """Test that all *_connections tables are blocked."""
        connection_tables = [
            "_tool_github_connections",
            "_tool_jira_connections",
            "_tool_gitlab_connections",
            "_tool_codecov_connections",
            "_tool_slack_connections",
            "_tool_pagerduty_connections",
            "_tool_jenkins_connections",
            "_tool_bitbucket_connections",
            "_devlake_blueprint_connections",
        ]
        for table in connection_tables:
            assert sec_mgr.is_table_denied(table) is True, f"{table} should be denied"

    def test_raw_tables_denied(self, sec_mgr):
        """Test that all _raw_* tables are blocked."""
        raw_tables = [
            "_raw_github_api_pull_requests",
            "_raw_jira_api_issues",
            "_raw_gitlab_api_merge_requests",
            "_raw_codecov_api_commits",
            "_raw_pagerduty_incidents",
            "_raw_cicd_test_jobs",
        ]
        for table in raw_tables:
            assert sec_mgr.is_table_denied(table) is True, f"{table} should be denied"

    def test_allowed_domain_tables(self, sec_mgr):
        """Test that normalized domain model tables are allowed."""
        allowed_tables = [
            "incidents",
            "pull_requests",
            "repos",
            "cicd_deployments",
            "cicd_deployment_commits",
            "project_mapping",
            "project_pr_metrics",
            "pull_request_comments",
            "accounts",
            "issues",
            "commits",
        ]
        for table in allowed_tables:
            assert sec_mgr.is_table_denied(table) is False, f"{table} should be allowed"

    def test_allowed_tool_tables_used_by_analytics(self, sec_mgr):
        """Test that _tool_* tables used by current analytics are allowed."""
        tool_tables = [
            "_tool_github_repos",
            "_tool_github_runs",
            "_tool_github_jobs",
            "_tool_jira_issues",
            "_tool_jira_board_issues",
            "_tool_codecov_coverages",
            "_tool_codecov_comparisons",
            "_tool_codecov_commits",
        ]
        for table in tool_tables:
            assert sec_mgr.is_table_denied(table) is False, f"{table} should be allowed (for now)"

    def test_handles_backtick_quoting(self, sec_mgr):
        """Test that backtick-quoted table names are handled."""
        assert sec_mgr.is_table_denied("`_devlake_api_keys`") is True
        assert sec_mgr.is_table_denied("`_raw_github_api_pull_requests`") is True
        assert sec_mgr.is_table_denied("`incidents`") is False

    def test_case_insensitive(self, sec_mgr):
        """Test that check is case-insensitive."""
        assert sec_mgr.is_table_denied("_DEVLAKE_API_KEYS") is True
        assert sec_mgr.is_table_denied("_Raw_GitHub_Api_Issues") is True
        assert sec_mgr.is_table_denied("_Tool_GitHub_CONNECTIONS") is True

    def test_admin_only_tables_allowed_by_default(self, sec_mgr):
        """Test that _devlake_* and _tool_* tables are allowed with default is_admin=True."""
        admin_only_tables = [
            "_devlake_blueprints",
            "_devlake_pipelines",
            "_devlake_tasks",
            "_tool_github_repos",
            "_tool_jira_issues",
            "_tool_codecov_coverages",
        ]
        for table in admin_only_tables:
            assert (
                sec_mgr.is_table_denied(table) is False
            ), f"{table} should be allowed (is_admin=True)"

    def test_admin_only_tables_denied_for_non_admin(self, sec_mgr):
        """Test that _devlake_* and _tool_* tables are denied when is_admin=False."""
        # TODO(RBAC): This path activates once the default is flipped to False.
        admin_only_tables = [
            "_devlake_blueprints",
            "_devlake_pipelines",
            "_devlake_tasks",
            "_devlake_migration_history",
            "_devlake_subtasks",
            "_tool_github_repos",
            "_tool_jira_issues",
            "_tool_gitlab_projects",
            "_tool_codecov_coverages",
            "_tool_copilot_seats",
        ]
        for table in admin_only_tables:
            assert (
                sec_mgr.is_table_denied(table, is_admin=False) is True
            ), f"{table} should be denied for non-admin"

    def test_deny_tier_blocked_regardless_of_role(self, sec_mgr):
        """Test that DENY tier tables are blocked even for admins."""
        deny_tables = [
            "_devlake_api_keys",
            "auth_sessions",
            "_tool_github_connections",
            "_raw_github_api_pull_requests",
        ]
        for table in deny_tables:
            assert sec_mgr.is_table_denied(table, is_admin=True) is True
            assert sec_mgr.is_table_denied(table, is_admin=False) is True

    def test_allow_tier_accessible_regardless_of_role(self, sec_mgr):
        """Test that ALLOW tier tables are accessible for all roles."""
        allow_tables = ["incidents", "pull_requests", "repos", "project_mapping"]
        for table in allow_tables:
            assert sec_mgr.is_table_denied(table, is_admin=True) is False
            assert sec_mgr.is_table_denied(table, is_admin=False) is False


@pytest.mark.unit
@pytest.mark.security
class TestExtractAndCheckTableRefs:
    """Test suite for extract_and_check_table_refs and schema blocking."""

    def test_allows_normal_lake_queries(self, sec_mgr):
        """Test that normal queries against lake tables pass."""
        queries = [
            "SELECT * FROM lake.incidents",
            "SELECT * FROM lake.pull_requests pr JOIN lake.repos r ON pr.base_repo_id = r.id",
            "SELECT * FROM lake.cicd_deployment_commits cdc "
            "LEFT JOIN lake.project_mapping pm ON cdc.cicd_scope_id = pm.row_id",
        ]
        for query in queries:
            sec_mgr.extract_and_check_table_refs(query)  # should not raise

    def test_blocks_mysql_schema(self, sec_mgr):
        """Test that queries referencing mysql schema are blocked."""
        with pytest.raises(ValueError, match="Access to schema 'mysql' is not allowed"):
            sec_mgr.extract_and_check_table_refs("SELECT user FROM mysql.user")

    def test_blocks_information_schema(self, sec_mgr):
        """Test that queries referencing information_schema are blocked."""
        with pytest.raises(
            ValueError, match="Access to schema 'information_schema' is not allowed"
        ):
            sec_mgr.extract_and_check_table_refs("SELECT * FROM information_schema.tables")

    def test_blocks_performance_schema(self, sec_mgr):
        """Test that queries referencing performance_schema are blocked."""
        with pytest.raises(
            ValueError, match="Access to schema 'performance_schema' is not allowed"
        ):
            sec_mgr.extract_and_check_table_refs(
                "SELECT * FROM performance_schema.events_statements_summary_by_digest"
            )

    def test_blocks_sys_schema(self, sec_mgr):
        """Test that queries referencing sys schema are blocked."""
        with pytest.raises(ValueError, match="Access to schema 'sys' is not allowed"):
            sec_mgr.extract_and_check_table_refs("SELECT * FROM sys.version")

    def test_blocks_denied_table_with_schema(self, sec_mgr):
        """Test that denied tables are caught even with lake. prefix."""
        with pytest.raises(ValueError, match="Access to table '_devlake_api_keys' is denied"):
            sec_mgr.extract_and_check_table_refs("SELECT * FROM lake._devlake_api_keys")

    def test_blocks_denied_table_without_schema(self, sec_mgr):
        """Test that denied tables are caught without schema prefix."""
        with pytest.raises(ValueError, match="denied"):
            sec_mgr.extract_and_check_table_refs("SELECT * FROM _raw_github_api_pull_requests")

    def test_blocks_denied_table_in_join(self, sec_mgr):
        """Test that denied tables in JOIN clauses are caught."""
        with pytest.raises(ValueError, match="denied"):
            sec_mgr.extract_and_check_table_refs(
                "SELECT * FROM lake.incidents i "
                "JOIN lake._tool_github_connections c ON i.id = c.id"
            )

    def test_blocks_comma_separated_blocked_schema(self, sec_mgr):
        """Test that blocked schemas in comma-separated FROM lists are caught."""
        with pytest.raises(ValueError, match="Access to schema 'mysql' is not allowed"):
            sec_mgr.extract_and_check_table_refs(
                "SELECT u.user FROM lake.incidents i, mysql.user u"
            )

    def test_blocks_comma_separated_denied_table(self, sec_mgr):
        """Test that denied tables in comma-separated FROM lists are caught."""
        with pytest.raises(ValueError, match="denied"):
            sec_mgr.extract_and_check_table_refs(
                "SELECT * FROM lake.incidents i, lake._devlake_api_keys k"
            )

    def test_blocks_describe_blocked_schema(self, sec_mgr):
        """Test that DESCRIBE against blocked schemas is caught."""
        with pytest.raises(ValueError, match="Access to schema 'mysql' is not allowed"):
            sec_mgr.extract_and_check_table_refs("DESCRIBE mysql.user")

    def test_blocks_desc_blocked_schema(self, sec_mgr):
        """Test that DESC against blocked schemas is caught."""
        with pytest.raises(
            ValueError, match="Access to schema 'information_schema' is not allowed"
        ):
            sec_mgr.extract_and_check_table_refs("DESC information_schema.tables")

    def test_blocks_describe_denied_table(self, sec_mgr):
        """Test that DESCRIBE against denied tables is caught."""
        with pytest.raises(ValueError, match="denied"):
            sec_mgr.extract_and_check_table_refs("DESCRIBE lake._devlake_api_keys")

    def test_blocks_describe_denied_table_bare(self, sec_mgr):
        """Test that DESCRIBE against denied tables without schema prefix is caught."""
        with pytest.raises(ValueError, match="denied"):
            sec_mgr.extract_and_check_table_refs("DESCRIBE _raw_github_api_issues")

    def test_allows_describe_normal_table(self, sec_mgr):
        """Test that DESCRIBE against allowed tables passes."""
        sec_mgr.extract_and_check_table_refs("DESCRIBE lake.incidents")  # should not raise

    def test_blocks_union_select_from_denied_table(self, sec_mgr):
        """Test that UNION SELECT from denied tables in subqueries is caught."""
        with pytest.raises(ValueError, match="Access to schema 'mysql' is not allowed"):
            sec_mgr.extract_and_check_table_refs(
                "SELECT * FROM lake.incidents "
                "UNION SELECT user,host,authentication_string FROM mysql.user"
            )

    def test_blocks_backtick_quoted_schemas(self, sec_mgr):
        """Test that backtick-quoted blocked schemas are caught."""
        with pytest.raises(ValueError, match="Access to schema 'mysql' is not allowed"):
            sec_mgr.extract_and_check_table_refs("SELECT * FROM `mysql`.`user`")


@pytest.mark.unit
@pytest.mark.security
class TestValidateSqlQueryTableBlocking:
    """Test that validate_sql_query blocks denied tables and schemas."""

    @pytest.fixture
    def security_manager(self) -> KonfluxDevLakeSecurityManager:
        config = Mock()
        config.allowed_ips = []
        config.api_keys = {}
        return KonfluxDevLakeSecurityManager(config)

    def test_blocks_denied_table_in_select(self, security_manager):
        """Test that SELECT from a denied table is blocked."""
        is_valid, msg = security_manager.validate_sql_query("SELECT * FROM lake._devlake_api_keys")
        assert is_valid is False
        assert "_devlake_api_keys" in msg

    def test_blocks_raw_table_in_select(self, security_manager):
        """Test that SELECT from a _raw_ table is blocked."""
        is_valid, msg = security_manager.validate_sql_query(
            "SELECT * FROM lake._raw_github_api_pull_requests"
        )
        assert is_valid is False
        assert "_raw_github_api_pull_requests" in msg

    def test_blocks_connection_table_in_select(self, security_manager):
        """Test that SELECT from a _connections table is blocked."""
        is_valid, msg = security_manager.validate_sql_query(
            "SELECT * FROM lake._tool_github_connections"
        )
        assert is_valid is False
        assert "_tool_github_connections" in msg

    def test_blocks_blocked_schema_in_select(self, security_manager):
        """Test that SELECT from a blocked schema is blocked."""
        is_valid, msg = security_manager.validate_sql_query("SELECT user FROM mysql.user")
        assert is_valid is False
        assert "mysql" in msg

    def test_allows_normal_lake_select(self, security_manager):
        """Test that normal lake SELECT queries still pass."""
        is_valid, msg = security_manager.validate_sql_query(
            "SELECT * FROM lake.incidents WHERE status = 'DONE'"
        )
        assert is_valid is True


@pytest.mark.unit
@pytest.mark.security
class TestDataMasking:
    """Test suite for DataMasking class."""

    @pytest.fixture
    def data_masker(self):
        """Create DataMasking instance."""
        return DataMasking()

    def test_mask_email_addresses(self, data_masker):
        """Test email address masking."""
        test_data = "Contact user@example.com for support"
        masked = data_masker.mask_sensitive_data(test_data)

        assert "use***@example.com" in masked
        assert "user@example.com" not in masked

    def test_mask_phone_numbers(self, data_masker):
        """Test phone number masking."""
        test_cases = ["Call 123-456-7890 for help", "Phone: 123.456.7890", "Contact 1234567890"]

        for test_data in test_cases:
            masked = data_masker.mask_sensitive_data(test_data)
            assert "***-***-****" in masked
            assert "123" not in masked or "456" not in masked

    def test_mask_ssn(self, data_masker):
        """Test SSN masking."""
        test_data = "SSN: 123-45-6789"
        masked = data_masker.mask_sensitive_data(test_data)

        assert "***-**-****" in masked
        assert "123-45-6789" not in masked

    def test_mask_credit_card_numbers(self, data_masker):
        """Test credit card number masking."""
        test_cases = [
            "Card: 1234-5678-9012-3456",
            "Card: 1234 5678 9012 3456",
            "Card: 1234567890123456",
        ]

        for test_data in test_cases:
            masked = data_masker.mask_sensitive_data(test_data)
            assert "****-****-****-****" in masked
            assert "1234" not in masked or "5678" not in masked

    def test_mask_ip_addresses(self, data_masker):
        """Test IP address masking."""
        test_data = "Server IP: 192.168.1.100"
        masked = data_masker.mask_sensitive_data(test_data)

        assert "***.***.***.***" in masked
        assert "192.168.1.100" not in masked

    def test_mask_empty_data(self, data_masker):
        """Test masking with empty data."""
        assert data_masker.mask_sensitive_data("") == ""
        assert data_masker.mask_sensitive_data(None) is None

    def test_mask_database_result_simple(self, data_masker):
        """Test masking database result with simple structure."""
        result = {
            "user_email": "test@example.com",
            "phone": "123-456-7890",
            "description": "Normal text without sensitive data",
        }

        masked = data_masker.mask_database_result(result)

        assert "tes***@example.com" in masked["user_email"]
        assert "***-***-****" in masked["phone"]
        assert masked["description"] == "Normal text without sensitive data"

    def test_mask_database_result_nested(self, data_masker):
        """Test masking database result with nested structure."""
        result = {
            "user": {"email": "nested@example.com", "contact": {"phone": "987-654-3210"}},
            "metadata": {"ip": "10.0.0.1"},
        }

        masked = data_masker.mask_database_result(result)

        assert "nes***@example.com" in masked["user"]["email"]
        assert "***-***-****" in masked["user"]["contact"]["phone"]
        assert "***.***.***.***" in masked["metadata"]["ip"]

    def test_mask_database_result_with_arrays(self, data_masker):
        """Test masking database result with arrays."""
        result = {
            "emails": ["user1@example.com", "user2@example.com"],
            "contacts": [{"phone": "111-222-3333"}, {"phone": "444-555-6666"}],
        }

        masked = data_masker.mask_database_result(result)

        assert "use***@example.com" in masked["emails"][0]
        assert "use***@example.com" in masked["emails"][1]
        assert "***-***-****" in masked["contacts"][0]["phone"]
        assert "***-***-****" in masked["contacts"][1]["phone"]

    def test_mask_database_result_empty(self, data_masker):
        """Test masking with empty database result."""
        assert data_masker.mask_database_result({}) == {}
        assert data_masker.mask_database_result(None) is None


@pytest.mark.unit
@pytest.mark.security
class TestKonfluxDevLakeSecurityManager:
    """Test suite for KonfluxDevLakeSecurityManager class."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create mock configuration."""
        config = Mock()
        config.allowed_ips = []
        config.api_keys = {}
        return config

    @pytest.fixture
    def security_manager(self, mock_config) -> KonfluxDevLakeSecurityManager:
        """Create KonfluxDevLakeSecurityManager instance."""
        return KonfluxDevLakeSecurityManager(mock_config)

    def test_validate_sql_query_select_allowed(self, security_manager):
        """Test that SELECT queries are always allowed."""
        select_queries = [
            "SELECT * FROM incidents",
            "select id, title from incidents where status = 'DONE'",
            "SELECT COUNT(*) FROM deployments GROUP BY environment",
        ]

        for query in select_queries:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is True
            assert "Query validation passed" in message

    def test_validate_sql_query_show_and_describe_allowed(self, security_manager):
        """Test that SHOW and DESCRIBE queries are allowed."""
        read_only_queries = [
            "SHOW DATABASES",
            "SHOW TABLES FROM `lake`",
            "show tables from `lake`",
            "DESCRIBE `lake`.`incidents`",
            "describe `lake`.`pull_requests`",
            "DESC `lake`.`repos`",
            "EXPLAIN SELECT * FROM lake.incidents",
            "WITH cte AS (SELECT * FROM lake.incidents) SELECT * FROM cte",
            "with _rank AS (SELECT id, row_number() OVER() as rn FROM lake.cicd_deployment_commits)"
            " SELECT * FROM _rank WHERE rn = 1",
        ]

        for query in read_only_queries:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is True, f"Query should be allowed: {query}"

    def test_validate_sql_query_show_restricted(self, security_manager):
        """Test that dangerous SHOW variants are blocked."""
        blocked_show_queries = [
            "SHOW GRANTS",
            "SHOW GRANTS FOR CURRENT_USER",
            "SHOW CREATE USER root@localhost",
            "SHOW VARIABLES",
            "SHOW GLOBAL VARIABLES",
            "SHOW STATUS",
            "SHOW PROCESSLIST",
            "SHOW MASTER STATUS",
            "SHOW SLAVE STATUS",
            "SHOW ENGINES",
            "SHOW PLUGINS",
        ]
        for query in blocked_show_queries:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is False, f"Query should be blocked: {query}"
            assert "SHOW DATABASES" in message or "SHOW TABLES" in message

    def test_validate_sql_query_show_tables_blocked_schema(self, security_manager):
        """Test that SHOW TABLES FROM a blocked schema is rejected."""
        blocked = [
            "SHOW TABLES FROM mysql",
            "SHOW TABLES FROM `information_schema`",
            "SHOW TABLES FROM performance_schema",
            "show tables from sys",
        ]
        for query in blocked:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is False, f"Query should be blocked: {query}"
            assert "schema" in message.lower()

    def test_validate_sql_query_dangerous_operations(self, security_manager):
        """Test that dangerous operations are blocked."""
        dangerous_queries = [
            "DROP TABLE incidents",
            "DELETE FROM incidents",
            "UPDATE incidents SET status = 'DONE'",
            "INSERT INTO incidents VALUES (1, 'test')",
            "CREATE TABLE test (id INT)",
            "ALTER TABLE incidents ADD COLUMN test VARCHAR(255)",
        ]

        for query in dangerous_queries:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is False
            assert "read-only" in message

    def test_validate_sql_query_unbalanced_parentheses(self, security_manager):
        """Test detection of unbalanced parentheses."""
        invalid_queries = [
            "SELECT * FROM test WHERE id IN (1, 2",
            "SELECT COUNT(*) FROM test WHERE (status = 'DONE'",
            "SELECT * FROM test WHERE ((id = 1)",
        ]

        for query in invalid_queries:
            is_valid, message = security_manager.validate_sql_query(query)
            assert is_valid is False
            assert "Unbalanced parentheses" in message

    def test_validate_sql_query_too_long(self, security_manager):
        """Test rejection of overly long queries."""
        long_query = "SELECT * FROM incidents WHERE " + "id = 1 OR " * 2000 + "id = 2"

        is_valid, message = security_manager.validate_sql_query(long_query)
        assert is_valid is False
        assert "too long" in message

    def test_validate_database_name_valid(self, security_manager):
        """Test validation of valid database names."""
        valid_names = ["lake", "test_db", "database123", "my_database"]

        for name in valid_names:
            is_valid, message = security_manager.validate_database_name(name)
            assert is_valid is True
            assert "validation passed" in message

    def test_validate_database_name_invalid(self, security_manager):
        """Test validation of invalid database names."""
        invalid_cases = [
            ("", "cannot be empty"),
            ("database-with-dash", "invalid characters"),
            ("database with space", "invalid characters"),
            ("a" * 70, "too long"),
            ("information_schema", "reserved"),
            ("mysql", "reserved"),
        ]

        for name, expected_error in invalid_cases:
            is_valid, message = security_manager.validate_database_name(name)
            assert is_valid is False
            assert expected_error in message.lower()

    def test_validate_table_name_valid(self, security_manager):
        """Test validation of valid table names."""
        valid_names = ["incidents", "cicd_deployments", "table123", "my_table"]

        for name in valid_names:
            is_valid, message = security_manager.validate_table_name(name)
            assert is_valid is True
            assert "validation passed" in message

    def test_validate_table_name_invalid(self, security_manager):
        """Test validation of invalid table names."""
        invalid_cases = [
            ("", "cannot be empty"),
            ("table-with-dash", "invalid characters"),
            ("table with space", "invalid characters"),
            ("a" * 70, "too long"),
        ]

        for name, expected_error in invalid_cases:
            is_valid, message = security_manager.validate_table_name(name)
            assert is_valid is False
            assert expected_error in message.lower()

    def test_generate_api_key(self, security_manager):
        """Test API key generation."""
        user_id = "test_user"
        api_key = security_manager.generate_api_key(user_id)

        assert isinstance(api_key, str)
        assert len(api_key) > 0
        assert user_id in security_manager.api_keys
        assert security_manager.api_keys[user_id]["key"] == api_key
        assert isinstance(security_manager.api_keys[user_id]["created"], datetime)

    def test_validate_api_key_valid(self, security_manager):
        """Test validation of valid API key."""
        user_id = "test_user"
        api_key = security_manager.generate_api_key(user_id)

        is_valid, message = security_manager.validate_api_key(api_key)
        assert is_valid is True
        assert user_id in message

    def test_validate_api_key_invalid(self, security_manager):
        """Test validation of invalid API key."""
        is_valid, message = security_manager.validate_api_key("invalid_key")
        assert is_valid is False
        assert "Invalid API key" in message

    def test_validate_api_key_empty(self, security_manager):
        """Test validation of empty API key."""
        is_valid, message = security_manager.validate_api_key("")
        assert is_valid is False
        assert "API key is required" in message

    def test_generate_session_token(self, security_manager):
        """Test session token generation."""
        user_id = "test_user"
        token = security_manager.generate_session_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token in security_manager.session_tokens
        assert security_manager.session_tokens[token]["user_id"] == user_id

    def test_validate_session_token_valid(self, security_manager):
        """Test validation of valid session token."""
        user_id = "test_user"
        token = security_manager.generate_session_token(user_id)

        is_valid, message = security_manager.validate_session_token(token)
        assert is_valid is True
        assert user_id in message

    def test_validate_session_token_expired(self, security_manager):
        """Test validation of expired session token."""
        user_id = "test_user"
        token = security_manager.generate_session_token(user_id)

        security_manager.session_tokens[token]["expires"] = datetime.now() - timedelta(hours=1)

        is_valid, message = security_manager.validate_session_token(token)
        assert is_valid is False
        assert "expired" in message

    def test_cleanup_expired_tokens(self, security_manager):
        """Test cleanup of expired session tokens."""
        user1_token = security_manager.generate_session_token("user1")
        user2_token = security_manager.generate_session_token("user2")

        security_manager.session_tokens[user1_token]["expires"] = datetime.now() - timedelta(
            hours=1
        )

        security_manager.cleanup_expired_tokens()

        assert user1_token not in security_manager.session_tokens
        assert user2_token in security_manager.session_tokens

    def test_get_security_stats(self, security_manager):
        """Test security statistics retrieval."""
        security_manager.generate_api_key("user1")
        security_manager.generate_session_token("user1")

        stats = security_manager.get_security_stats()

        assert "active_api_keys" in stats
        assert "active_session_tokens" in stats
        assert "rate_limit_entries" in stats
        assert "allowed_ips" in stats
        assert stats["active_api_keys"] == 1
        assert stats["active_session_tokens"] == 1

    def test_sanitize_input(self, security_manager):
        """Test input sanitization."""
        dangerous_input = "<script>alert('xss')</script> & DROP TABLE"
        sanitized = security_manager.sanitize_input(dangerous_input)

        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "&" not in sanitized
        assert "script" in sanitized
        assert "alert" in sanitized
        assert "DROP TABLE" in sanitized

    def test_sanitize_input_empty(self, security_manager):
        """Test sanitization of empty input."""
        assert security_manager.sanitize_input("") == ""
        assert security_manager.sanitize_input(None) == ""
