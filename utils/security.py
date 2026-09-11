#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Security Utility
"""

import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from utils.request_context import is_current_user_admin
from utils.logger import get_logger

# Blocklist for identifier values passed as bound parameters.  Since the
# driver escapes these values, we only reject patterns that indicate an
# injection *attempt* rather than characters that appear in legitimate
# names (e.g. apostrophes in "O'Reilly").
_SQL_INJECTION_RE = re.compile(
    r";|--(?:\s|$)|/\*|\*/|\bUNION\s+SELECT\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$")

# Schemas that must never be queried (credential hashes, privilege info, internals).
# Also REVOKE at the MySQL grant level as a separate hardening step.
_BLOCKED_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")

# Extracts schema.table or bare table references after FROM, JOIN, a comma
# (for comma-separated table lists), or DESCRIBE/DESC/SHOW TABLES FROM.
# group(1) = schema or bare table, group(2) = table when schema is present.
_TABLE_REF_RE = re.compile(
    r"(?:FROM|JOIN|,|DESCRIBE|DESC)\s+`?(\w+)`?(?:\.`?(\w+)`?)?",
    re.IGNORECASE,
)


class KonfluxDevLakeSecurityManager:
    """Konflux DevLake Security Manager"""

    def __init__(self, config):
        self.config = config
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeSecurityManager")
        self.allowed_ips = getattr(config, "allowed_ips", [])
        self.api_keys = getattr(config, "api_keys", {})
        self.session_tokens = {}
        self.rate_limits = {}

    def validate_identifier(self, value: str, field_name: str = "identifier") -> str:
        """Validate a project_name, repo_name, or similar identifier.

        Uses a blocklist to reject SQL injection characters while allowing
        legitimate values (including spaces, hyphens, etc.).

        Args:
            value: The identifier string to validate.
            field_name: Name of the field for error messages.

        Returns:
            The validated string.

        Raises:
            ValueError: If the value contains disallowed characters or patterns.
        """
        if not value or len(value) > 256:
            raise ValueError(f"Invalid {field_name}: must be 1-256 characters")
        if _SQL_INJECTION_RE.search(value):
            raise ValueError(f"Invalid {field_name}: contains disallowed characters or patterns")
        return value

    def validate_date_string(self, value: str, field_name: str = "date") -> str:
        """Validate a date string is ISO-8601 format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS).

        Args:
            value: The date string to validate.
            field_name: Name of the field for error messages.

        Returns:
            The validated string.

        Raises:
            ValueError: If the value is not a valid date.
        """
        if not _ISO_DATE_RE.match(value):
            raise ValueError(f"Invalid {field_name}: must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
        try:
            if len(value) == 10:
                datetime.strptime(value, "%Y-%m-%d")
            else:
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(f"Invalid {field_name}: not a valid date")
        return value

    def validate_positive_int(self, value, field_name: str = "value") -> int:
        """Validate and cast a value to a non-negative integer.

        Args:
            value: The value to validate and cast.
            field_name: Name of the field for error messages.

        Returns:
            The validated integer.

        Raises:
            ValueError: If the value is not a non-negative integer.
        """
        try:
            int_val = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid {field_name}: must be a positive integer")
        if int_val < 0:
            raise ValueError(f"Invalid {field_name}: must be non-negative")
        return int_val

    def is_table_denied(self, table_name: str, is_admin: Optional[bool] = None) -> bool:
        """Check whether access to a table should be denied.

        Access tiers:
        - DENY (always blocked): credentials, tokens, raw API blobs.
        - ADMIN_ONLY: DevLake internal orchestration (_devlake_*). Allowed only
          for administrators during an authenticated request.
        - ALLOW: normalized domain model tables (incidents, pull_requests,
          repos, ...) and the _tool_* plugin layer behind them.

        Args:
            table_name: The table name to check (may include backticks).
            is_admin: Whether the caller has admin privileges. If omitted, the
                value is read from the current request context, which fails
                closed to non-administrator when no user is authenticated.

        Returns:
            True if the table is denied for the given role, False otherwise.
        """
        if is_admin is None:
            is_admin = is_current_user_admin()

        name = table_name.lower().strip("`").strip()

        # --- DENY tier: always blocked, regardless of role ---
        if name in ("_devlake_api_keys", "auth_sessions"):
            return True
        if name.endswith("_connections"):
            return True
        if name.startswith("_raw_"):
            return True

        # --- ADMIN_ONLY tier: DevLake internal orchestration ---
        # _devlake_* holds blueprints, pipelines, tasks, migration_history,
        # locking, notifications,.
        if not is_admin:
            if name.startswith("_devlake_"):
                return True

        # --- ALLOW tier: normalized domain model tables ---
        return False

    def extract_and_check_table_refs(self, query: str, is_admin: Optional[bool] = None) -> None:
        """Extract FROM/JOIN table references and reject blocked schemas or denied tables.

        Args:
            query: The SQL query string to inspect.
            is_admin: Whether the caller has admin privileges. If omitted,
                resolve it from the current request context, which fails closed
                to non-administrator when no user is authenticated.

        Raises:
            ValueError: If the query references a blocked schema or denied table.
        """
        if is_admin is None:
            is_admin = is_current_user_admin()

        for match in _TABLE_REF_RE.finditer(query):
            if match.group(2):
                schema = match.group(1).lower().strip("`")
                table = match.group(2).lower().strip("`")
                if schema in _BLOCKED_SCHEMAS:
                    raise ValueError(f"Access to schema '{schema}' is not allowed")
            else:
                table = match.group(1).lower().strip("`")
            if self.is_table_denied(table, is_admin=is_admin):
                raise ValueError(f"Access to table '{table}' is denied")

    # Read-only statement prefixes allowed through validation.
    # "with" covers CTE queries (WITH ... AS (...) SELECT ...).
    # "show" is handled separately via _validate_show_query to restrict subcommands.
    _ALLOWED_STATEMENT_PREFIXES = ("select", "describe", "desc", "explain", "with")

    # SHOW subcommands that are safe to execute.  Anything else (SHOW GRANTS,
    # SHOW CREATE USER, SHOW VARIABLES, SHOW STATUS, ...) is blocked.
    _ALLOWED_SHOW_RE = re.compile(r"^show\s+(databases|tables\b)", re.IGNORECASE)

    # Extracts the schema name from "SHOW TABLES FROM <schema>".
    _SHOW_TABLES_FROM_RE = re.compile(r"^show\s+tables\s+from\s+`?(\w+)`?", re.IGNORECASE)

    def _validate_show_query(self, query_lower: str) -> None:
        """Validate a SHOW statement against the safe subcommand allowlist.

        Only SHOW DATABASES and SHOW TABLES [FROM <schema>] are permitted.
        For SHOW TABLES FROM, the schema is checked against _BLOCKED_SCHEMAS.

        Args:
            query_lower: The lowercased, stripped query string.

        Raises:
            ValueError: If the SHOW variant or target schema is not allowed.
        """
        if not self._ALLOWED_SHOW_RE.match(query_lower):
            raise ValueError("Only SHOW DATABASES and SHOW TABLES are allowed")
        m = self._SHOW_TABLES_FROM_RE.match(query_lower)
        if m:
            schema = m.group(1).lower().strip("`")
            if schema in _BLOCKED_SCHEMAS:
                raise ValueError(f"Access to schema '{schema}' is not allowed")

    def validate_sql_query(self, query: str, is_admin: Optional[bool] = None) -> Tuple[bool, str]:
        """Validate a SQL query for security.

        Allows read-only statements (SELECT, SHOW DATABASES, SHOW TABLES,
        DESCRIBE, EXPLAIN, WITH) and rejects everything else.  Also checks
        for dangerous patterns, blocked schemas, and denied tables.

        This method is called from db.execute_query() so that ALL queries --
        whether from analytics tools or the generic execute_query tool -- go
        through the same validation.
        """
        try:
            query_lower = query.lower().strip()

            # SHOW is handled by its own validator with subcommand restrictions
            if query_lower.startswith("show"):
                self._validate_show_query(query_lower)
            elif not any(query_lower.startswith(p) for p in self._ALLOWED_STATEMENT_PREFIXES):
                self.logger.info("Query blocked - not a read-only statement")
                raise ValueError("Only read-only statements are allowed (SELECT, SHOW, DESCRIBE)")

            # Check for balanced parentheses
            if query_lower.count("(") != query_lower.count(")"):
                self.logger.warning("Unbalanced parentheses in SQL query")
                raise ValueError("Unbalanced parentheses in SQL query")

            # Check for unsupported patterns
            unsupported_patterns = [
                r";",  # Multiple statements
                r"--",  # SQL comments
                r"/\*.*?\*/",  # Multi-line comments
                r"\bload_file\b",  # MYSQL file read operations
                r"\binto\s+(outfile|dumpfile)\b",  # MYSQL file write operations
            ]

            # Check for forbiden patterns
            for pattern in unsupported_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    self.logger.warning(f"Unsupported pattern detected: {pattern}")
                    raise ValueError(f"Unsupported pattern detected: {pattern}")

            # Check for reasonable query length
            if len(query) > 10000:  # 10KB limit
                self.logger.warning("SQL query too long")
                raise ValueError("SQL query too long")

            # Block queries that reference denied tables or non-lake schemas
            self.extract_and_check_table_refs(query, is_admin=is_admin)

            return True, "Query validation passed"

        except Exception as e:
            self.logger.error(f"Error validating SQL query: {e}")
            return False, f"Error validating SQL query: {str(e)}"

    def sanitize_input(self, input_str: str) -> str:
        """Sanitize user input"""
        if not input_str:
            return ""

        # Remove potentially dangerous characters
        dangerous_chars = ["<", ">", '"', "'", "&", ";", "|", "`", "$", "(", ")", "{", "}"]
        sanitized = input_str

        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "")

        # Remove multiple spaces
        sanitized = " ".join(sanitized.split())

        return sanitized

    def validate_database_name(self, db_name: str) -> Tuple[bool, str]:
        """Validate database name"""
        if not db_name:
            return False, "Database name cannot be empty"

        # Check for valid characters
        if not re.match(r"^[a-zA-Z0-9_]+$", db_name):
            return False, "Database name contains invalid characters"

        # Check length
        if len(db_name) > 64:
            return False, "Database name too long"

        # Check for reserved words
        reserved_words = [
            "information_schema",
            "mysql",
            "performance_schema",
            "sys",
            "test",
            "tmp",
            "temp",
        ]

        if db_name.lower() in reserved_words:
            return False, f"Database name '{db_name}' is reserved"

        return True, "Database name validation passed"

    def validate_table_name(self, table_name: str) -> Tuple[bool, str]:
        """Validate table name"""
        if not table_name:
            return False, "Table name cannot be empty"

        # Check for valid characters
        if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
            return False, "Table name contains invalid characters"

        # Check length
        if len(table_name) > 64:
            return False, "Table name too long"

        return True, "Table name validation passed"

    def generate_api_key(self, user_id: str) -> str:
        """Generate API key for user"""
        # Generate a random key
        key = secrets.token_urlsafe(32)

        # Store the key
        self.api_keys[user_id] = {"key": key, "created": datetime.now(), "last_used": None}

        self.logger.info(f"Generated API key for user: {user_id}")
        return key

    def validate_api_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate API key"""
        if not api_key:
            return False, "API key is required"

        # Check if key exists
        for user_id, key_info in self.api_keys.items():
            if key_info["key"] == api_key:
                # Update last used time
                key_info["last_used"] = datetime.now()
                return True, f"Valid API key for user: {user_id}"

        return False, "Invalid API key"

    def generate_session_token(self, user_id: str) -> str:
        """Generate session token"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=24)

        self.session_tokens[token] = {
            "user_id": user_id,
            "created": datetime.now(),
            "expires": expiry,
        }

        self.logger.info(f"Generated session token for user: {user_id}")
        return token

    def validate_session_token(self, token: str) -> Tuple[bool, str]:
        """Validate session token"""
        if not token:
            return False, "Session token is required"

        if token not in self.session_tokens:
            return False, "Invalid session token"

        token_info = self.session_tokens[token]

        # Check if token has expired
        if datetime.now() > token_info["expires"]:
            del self.session_tokens[token]
            return False, "Session token has expired"

        return True, f"Valid session token for user: {token_info['user_id']}"

    def check_rate_limit(self, user_id: str, operation: str) -> Tuple[bool, str]:
        """Check rate limit for user operation"""
        current_time = datetime.now()
        key = f"{user_id}:{operation}"

        if key not in self.rate_limits:
            self.rate_limits[key] = []

        # Remove old entries (older than 1 minute)
        self.rate_limits[key] = [
            time for time in self.rate_limits[key] if current_time - time < timedelta(minutes=1)
        ]

        # Check if rate limit exceeded (max 100 operations per minute)
        if len(self.rate_limits[key]) >= 100:
            return False, "Rate limit exceeded"

        # Add current operation
        self.rate_limits[key].append(current_time)

        return True, "Rate limit check passed"

    def validate_ip_address(self, ip_address: str) -> bool:
        """Validate IP address"""
        if not self.allowed_ips:
            return True  # No restrictions

        return ip_address in self.allowed_ips

    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security event"""
        self.logger.warning(f"Security event - {event_type}: {details}")

    def cleanup_expired_tokens(self):
        """Clean up expired session tokens"""
        current_time = datetime.now()
        expired_tokens = []

        for token, token_info in self.session_tokens.items():
            if current_time > token_info["expires"]:
                expired_tokens.append(token)

        for token in expired_tokens:
            del self.session_tokens[token]

        if expired_tokens:
            self.logger.info(f"Cleaned up {len(expired_tokens)} expired session tokens")

    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        return {
            "active_api_keys": len(self.api_keys),
            "active_session_tokens": len(self.session_tokens),
            "rate_limit_entries": len(self.rate_limits),
            "allowed_ips": len(self.allowed_ips),
        }


class DataMasking:
    """Data Masking Utility"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.DataMasking")

        # Sensitive data patterns
        self.sensitive_patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }

    def mask_sensitive_data(self, data: str) -> str:
        """Mask sensitive data in string"""
        if not data:
            return data

        masked_data = data

        # Mask email addresses
        masked_data = re.sub(
            self.sensitive_patterns["email"],
            lambda m: m.group(0)[:3] + "***@" + m.group(0).split("@")[1],
            masked_data,
        )

        # Mask phone numbers
        masked_data = re.sub(self.sensitive_patterns["phone"], "***-***-****", masked_data)

        # Mask SSN
        masked_data = re.sub(self.sensitive_patterns["ssn"], "***-**-****", masked_data)

        # Mask credit card numbers
        masked_data = re.sub(
            self.sensitive_patterns["credit_card"], "****-****-****-****", masked_data
        )

        # Mask IP addresses
        masked_data = re.sub(self.sensitive_patterns["ip_address"], "***.***.***.***", masked_data)

        return masked_data

    def mask_database_result(self, result: Any) -> Any:
        """Mask sensitive data in database result"""
        if not result:
            return result

        # Handle list of records
        if isinstance(result, list):
            return [
                (
                    self.mask_database_result(item)
                    if isinstance(item, dict)
                    else self.mask_sensitive_data(str(item)) if isinstance(item, str) else item
                )
                for item in result
            ]

        # Handle dictionary
        if isinstance(result, dict):
            masked_result = {}
            for key, value in result.items():
                if isinstance(value, str):
                    masked_result[key] = self.mask_sensitive_data(value)
                elif isinstance(value, dict):
                    masked_result[key] = self.mask_database_result(value)
                elif isinstance(value, list):
                    masked_result[key] = self.mask_database_result(value)
                else:
                    masked_result[key] = value
            return masked_result

        # Handle other types
        if isinstance(result, str):
            return self.mask_sensitive_data(result)

        return result
