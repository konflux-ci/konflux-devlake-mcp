#!/usr/bin/env python3
"""
Tool Handler for MCP Server

This module handles tool execution requests, including security validation,
data masking, authorization, and error handling.
"""

import contextvars
import json
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from utils.logger import get_logger
from utils.db import DateTimeEncoder
from utils.security import SQLInjectionDetector, DataMasking
from utils.rbac import AuthorizationService

# Context variable to store current user info for the request
# This allows the tool handler to access user info set by the auth middleware
current_user_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "current_user_context", default=None
)


def set_user_context(user_info: Optional[Dict[str, Any]]) -> None:
    """
    Set the current user context for the request.

    Args:
        user_info: User information from OIDC authentication (id, username, groups, etc.)
    """
    current_user_context.set(user_info)


def get_user_context() -> Optional[Dict[str, Any]]:
    """
    Get the current user context for the request.

    Returns:
        User information dict or None if not authenticated
    """
    return current_user_context.get()


class ToolHandler:
    """
    Handles tool execution requests with security validation, authorization, and data masking.

    This class provides a centralized way to execute tools while ensuring
    proper security validation, role-based access control, and data protection.
    """

    def __init__(
        self,
        tools_manager,
        security_manager,
        authorization_service: Optional[AuthorizationService] = None,
        rbac_enabled: bool = True,
    ):
        """
        Initialize the tool handler.

        Args:
            tools_manager: Tools management system
            security_manager: Security validation system
            authorization_service: RBAC authorization service (created if None and rbac_enabled)
            rbac_enabled: Whether to enforce role-based access control
        """
        self.tools_manager = tools_manager
        self.security_manager = security_manager
        self.sql_injection_detector = SQLInjectionDetector()
        self.data_masking = DataMasking()
        self.logger = get_logger(f"{__name__}.ToolHandler")

        # RBAC configuration
        self.rbac_enabled = rbac_enabled
        if rbac_enabled:
            self.authorization_service = authorization_service or AuthorizationService()
            self.logger.info("RBAC enabled for tool handler")
        else:
            self.authorization_service = None
            self.logger.info("RBAC disabled for tool handler")

    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Handle a tool execution request with authorization and security validation.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            List of TextContent objects with the tool result
        """
        try:
            self.logger.info(f"Handling tool call request: {name}")

            # Check authorization (RBAC) if enabled
            if self.rbac_enabled and self.authorization_service:
                auth_result = self._check_authorization(name)
                if not auth_result["authorized"]:
                    self.logger.warning(
                        f"Authorization denied for tool '{name}': {auth_result['reason']}"
                    )
                    return self._create_error_response(auth_result["reason"])

            # Perform security validation
            validation_result = await self._validate_tool_request(name, arguments)
            if not validation_result["valid"]:
                return self._create_error_response(validation_result["error"])

            # Execute the tool
            result = await self.tools_manager.call_tool(name, arguments)

            # Apply data masking to sensitive information
            masked_result = self._mask_sensitive_data(result)

            return [TextContent(type="text", text=masked_result)]

        except Exception as e:
            self.logger.error(f"Failed to handle tool call request: {e}")
            return self._create_error_response(f"Tool call failed: {str(e)}", name, arguments)

    def _check_authorization(self, tool_name: str) -> Dict[str, Any]:
        """
        Check if the current user is authorized to call the specified tool.

        Uses Rover group membership for role assignment.

        Args:
            tool_name: Name of the tool being called

        Returns:
            Dict with 'authorized' bool and 'reason' string if denied
        """
        user_context = get_user_context()

        # If no user context and RBAC is enabled, deny access
        if user_context is None:
            return {
                "authorized": False,
                "reason": "Access denied: authentication required for this tool",
            }

        # Extract username from context
        username = user_context.get("username", "unknown")

        # Check authorization
        if self.authorization_service.is_authorized(tool_name, username):
            self.logger.debug(f"User '{username}' authorized for tool '{tool_name}'")
            return {"authorized": True}

        # Get detailed denial reason
        reason = self.authorization_service.get_denied_reason(tool_name, username)
        return {"authorized": False, "reason": reason}

    async def _validate_tool_request(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tool request for security and correctness.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Validation result with valid flag and optional error message
        """
        # Security validation for query-based tools
        if name in ["execute_query"]:
            query = arguments.get("query", "")
            if query:
                # Validate SQL query
                is_valid, validation_msg = self.security_manager.validate_sql_query(query)
                if not is_valid:
                    self.logger.warning(f"SQL query validation failed: {validation_msg}")
                    return {
                        "valid": False,
                        "error": f"SQL query validation failed: {validation_msg}",
                        "security_check": "failed",
                    }

                # Check for SQL injection
                is_injection, patterns = self.sql_injection_detector.detect_sql_injection(query)
                if is_injection:
                    self.logger.warning(f"Potential SQL injection detected: {patterns}")
                    return {
                        "valid": False,
                        "error": "Potential SQL injection detected",
                        "security_check": "failed",
                        "detected_patterns": patterns,
                    }

        # Validate database and table names
        if name in ["list_tables", "get_table_schema"]:
            database = arguments.get("database", "")
            is_valid, validation_msg = self.security_manager.validate_database_name(database)
            if not is_valid:
                self.logger.warning(f"Database name validation failed: {validation_msg}")
                return {
                    "valid": False,
                    "error": f"Database name validation failed: {validation_msg}",
                    "security_check": "failed",
                }

        if name == "get_table_schema":
            table = arguments.get("table", "")
            is_valid, validation_msg = self.security_manager.validate_table_name(table)
            if not is_valid:
                self.logger.warning(f"Table name validation failed: {validation_msg}")
                return {
                    "valid": False,
                    "error": f"Table name validation failed: {validation_msg}",
                    "security_check": "failed",
                }

        return {"valid": True}

    def _mask_sensitive_data(self, result: str) -> str:
        """
        Apply data masking to sensitive information in tool results.

        Args:
            result: Tool execution result

        Returns:
            Result with sensitive data masked
        """
        try:
            result_dict = json.loads(result)
            if isinstance(result_dict, dict) and "data" in result_dict:
                # Use the updated mask_database_result method that handles both lists and dicts
                result_dict["data"] = self.data_masking.mask_database_result(result_dict["data"])
                return json.dumps(result_dict, indent=2, cls=DateTimeEncoder)
        except (json.JSONDecodeError, KeyError):
            # If result is not JSON or doesn't have expected structure, return as is
            pass

        return result

    def _create_error_response(
        self, error_message: str, tool_name: str = None, arguments: Dict = None
    ) -> List[TextContent]:
        """
        Create a standardized error response.

        Args:
            error_message: Error description
            tool_name: Name of the tool that failed (optional)
            arguments: Tool arguments (optional)

        Returns:
            List containing error response as TextContent
        """
        error_result = {
            "success": False,
            "error": error_message,
        }

        if tool_name:
            error_result["tool_name"] = tool_name

        if arguments:
            error_result["arguments"] = arguments

        return [
            TextContent(type="text", text=json.dumps(error_result, indent=2, cls=DateTimeEncoder))
        ]
