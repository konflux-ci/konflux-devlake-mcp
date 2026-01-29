#!/usr/bin/env python3
"""
Unit Tests for Security Module

Tests the security classes including SQL injection detection,
data masking, and security validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from utils.security import KonfluxDevLakeSecurityManager, SQLInjectionDetector, DataMasking


@pytest.mark.unit
@pytest.mark.security
class TestSQLInjectionDetector:
    """Test suite for SQLInjectionDetector class."""

    @pytest.fixture
    def sql_detector(self):
        """Create SQLInjectionDetector instance."""
        return SQLInjectionDetector()

    def test_safe_select_queries(self, sql_detector):
        """Test that SELECT queries are considered safe."""
        safe_queries = [
            "SELECT * FROM incidents",
            "select id, title from incidents where status = 'DONE'",
            "SELECT COUNT(*) FROM deployments",
            "select * from incidents order by created_date desc limit 10",
        ]

        for query in safe_queries:
            is_injection, patterns = sql_detector.detect_sql_injection(query)
            assert is_injection is False
            assert patterns == []

    def test_dangerous_sql_operations(self, sql_detector):
        """Test detection of dangerous SQL operations."""
        dangerous_queries = [
            "DROP TABLE incidents",
            "DELETE FROM incidents WHERE id = 1",
            "INSERT INTO incidents VALUES (1, 'test')",
            "UPDATE incidents SET status = 'DONE'",
            "CREATE TABLE test (id INT)",
            "ALTER TABLE incidents ADD COLUMN test VARCHAR(255)",
        ]

        for query in dangerous_queries:
            is_injection, patterns = sql_detector.detect_sql_injection(query)
            assert is_injection is True
            assert len(patterns) > 0

        allowed_queries = [
            "TRUNCATE TABLE incidents",
            "GRANT ALL ON incidents TO user",
            "REVOKE SELECT ON incidents FROM user",
        ]

        for query in allowed_queries:
            is_injection, patterns = sql_detector.detect_sql_injection(query)

    def test_empty_query(self, sql_detector):
        """Test detection with empty query."""
        is_injection, patterns = sql_detector.detect_sql_injection("")
        assert is_injection is False
        assert patterns == []

    def test_none_query(self, sql_detector):
        """Test detection with None query."""
        is_injection, patterns = sql_detector.detect_sql_injection(None)
        assert is_injection is False
        assert patterns == []

    def test_case_insensitive_detection(self, sql_detector):
        """Test that detection is case insensitive."""
        dangerous_queries = [
            "drop table incidents",
            "DROP TABLE incidents",
            "Drop Table incidents",
            "dRoP tAbLe incidents",
        ]

        for query in dangerous_queries:
            is_injection, patterns = sql_detector.detect_sql_injection(query)
            assert is_injection is True


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
    def mock_config(self):
        """Create mock configuration."""
        config = Mock()
        config.allowed_ips = []
        config.api_keys = {}
        return config

    @pytest.fixture
    def security_manager(self, mock_config):
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
            assert "Query doesn't start with SELECT" in message

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
