#!/usr/bin/env python3
"""
Tool Handler for MCP Server

This module handles tool execution requests, including security validation,
data masking, and error handling.
"""

import json
from typing import Any, Dict, List

from mcp.types import TextContent

from utils.logger import get_logger
from utils.db import DateTimeEncoder
from utils.security import SQLInjectionDetector, DataMasking


class ToolHandler:
    """
    Handles tool execution requests with security validation and data masking.

    This class provides a centralized way to execute tools while ensuring
    proper security validation and data protection.
    """

    def __init__(self, tools_manager, security_manager):
        """
        Initialize the tool handler.

        Args:
            tools_manager: Tools management system
            security_manager: Security validation system
        """
        self.tools_manager = tools_manager
        self.security_manager = security_manager
        self.sql_injection_detector = SQLInjectionDetector()
        self.data_masking = DataMasking()
        self.logger = get_logger(f"{__name__}.ToolHandler")

    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Handle a tool execution request with full security validation.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            List of TextContent objects with the tool result
        """
        try:
            self.logger.info(f"Handling tool call request: {name}")

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
