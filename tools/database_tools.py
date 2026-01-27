#!/usr/bin/env python3
"""
Database Tools for Konflux DevLake MCP Server

Contains tools for database connectivity, exploration, and query execution
with improved modularity and maintainability.
"""

from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call, log_database_operation


class DatabaseTools(BaseTool):
    """
    Database-related tools for Konflux DevLake MCP Server.

    This class provides tools for database connectivity, exploration,
    and query execution with proper error handling and logging.
    """

    def __init__(self, db_connection):
        """
        Initialize database tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.DatabaseTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all database tools.

        Returns:
            List of Tool objects for database operations
        """
        return [
            Tool(
                name="connect_database",
                description=(
                    "**Database Connection Tool** - Establishes and verifies connection "
                    "to the Konflux DevLake database. Use this tool to test connectivity "
                    "before running other database operations. Returns connection status and "
                    "database information. This is typically the first tool you should call "
                    "to ensure the database is accessible."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="list_databases",
                description=(
                    "**Database Discovery Tool** - Lists all available databases in the "
                    "Konflux DevLake system. This tool shows you what data sources are "
                    "available, including the main 'lake' database containing incidents, "
                    "deployments, and other Konflux operational data. Use this to explore "
                    "what data is available before diving into specific tables."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="list_tables",
                description=(
                    "**Table Explorer Tool** - Lists all tables within a specific database. "
                    "This tool helps you discover what data is available in each database. "
                    "For the 'lake' database, you'll find tables like 'incidents', "
                    "'cicd_deployments', 'cicd_deployment_commits', and 'project_mapping'. "
                    "Use this to understand the data structure before querying specific tables."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {
                            "type": "string",
                            "description": (
                                "Database name to explore. Common options: "
                                "'lake' (main DevLake data), "
                                "'information_schema' (MySQL system tables), "
                                "'test_db' (test database)"
                            ),
                        }
                    },
                    "required": ["database"],
                },
            ),
            Tool(
                name="get_table_schema",
                description=(
                    "**Schema Inspector Tool** - Provides detailed schema information for "
                    "a specific table, including column names, data types, constraints, and "
                    "descriptions. This tool is essential for understanding the structure of "
                    "tables before writing queries. For example, the 'incidents' table "
                    "contains fields like 'incident_key', 'title', 'status', 'created_date', "
                    "and 'lead_time_minutes'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {
                            "type": "string",
                            "description": (
                                "Database name containing the table. Use 'lake' "
                                "for main DevLake tables like incidents, "
                                "deployments, etc."
                            ),
                        },
                        "table": {
                            "type": "string",
                            "description": (
                                "Table name to inspect. Common tables: "
                                "'incidents', 'cicd_deployments', "
                                "'cicd_deployment_commits', 'project_mapping'"
                            ),
                        },
                    },
                    "required": ["database", "table"],
                },
            ),
            Tool(
                name="execute_query",
                description=(
                    "**ADVANCED SQL Query Tool** - Executes custom SQL queries against the "
                    "Konflux DevLake database. **WARNING: This tool allows arbitrary SQL "
                    "execution and should be used with extreme caution.** Only use this tool "
                    "when other specialized tools cannot meet your needs. This tool supports "
                    "SELECT queries with filtering, aggregation, joins, and advanced SQL "
                    "features. Use this for custom analysis, reporting, and data exploration. "
                    "Example queries: 'SELECT * FROM lake.incidents WHERE status = \"DONE\"', "
                    "'SELECT COUNT(*) FROM lake.cicd_deployments WHERE environment = "
                    '"PRODUCTION"\'. **SECURITY NOTE: Always validate and sanitize your '
                    "queries before execution.**"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "SQL query to execute (e.g., 'SELECT * FROM lake.incidents "
                                "LIMIT 10'). WARNING: Only use SELECT queries for safety."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": (
                                "Maximum number of rows to return (default: 100, max: 1000)"
                            ),
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a database tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON string with tool execution result
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Route to appropriate tool method
            if name == "connect_database":
                result = await self._connect_database_tool()
            elif name == "list_databases":
                result = await self._list_databases_tool()
            elif name == "list_tables":
                result = await self._list_tables_tool(arguments)
            elif name == "get_table_schema":
                result = await self._get_table_schema_tool(arguments)
            elif name == "execute_query":
                result = await self._execute_query_tool(arguments)
            else:
                result = {"success": False, "error": f"Unknown database tool: {name}"}

            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"Database tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _connect_database_tool(self) -> Dict[str, Any]:
        """Test database connectivity and return connection information."""
        try:
            result = await self.db_connection.connect()
            log_database_operation("connect_database", success=result["success"])
            return result
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return {"success": False, "error": str(e)}

    async def _list_databases_tool(self) -> Dict[str, Any]:
        """List all available databases."""
        try:
            query = "SHOW DATABASES"
            result = await self.db_connection.execute_query(query)
            log_database_operation("list_databases", success=result["success"])
            return result
        except Exception as e:
            self.logger.error(f"List databases failed: {e}")
            return {"success": False, "error": str(e)}

    async def _list_tables_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List all tables in a specific database."""
        try:
            database = arguments.get("database", "")
            if not database:
                return {"success": False, "error": "Database name is required"}

            query = f"SHOW TABLES FROM `{database}`"
            result = await self.db_connection.execute_query(query)
            log_database_operation("list_tables", success=result["success"])
            return result
        except Exception as e:
            self.logger.error(f"List tables failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_table_schema_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed schema information for a specific table."""
        try:
            database = arguments.get("database", "")
            table = arguments.get("table", "")

            if not database or not table:
                return {"success": False, "error": "Database and table names are required"}

            query = f"DESCRIBE `{database}`.`{table}`"
            result = await self.db_connection.execute_query(query)
            log_database_operation("get_table_schema", success=result["success"])
            return result
        except Exception as e:
            self.logger.error(f"Get table schema failed: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a custom SQL query with enhanced security validation."""
        try:
            query = arguments.get("query", "")
            limit = arguments.get("limit", 100)

            if not query:
                return {"success": False, "error": "Query is required"}

            # Enhanced security validation
            query_upper = query.strip().upper()

            # Check for dangerous SQL operations (only as whole words)
            dangerous_keywords = [
                "DROP",
                "DELETE",
                "UPDATE",
                "INSERT",
                "CREATE",
                "ALTER",
                "TRUNCATE",
                "GRANT",
                "REVOKE",
                "EXEC",
                "EXECUTE",
            ]

            for keyword in dangerous_keywords:
                # Use word boundaries to avoid false positives like "created_date"
                import re

                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, query_upper):
                    return {
                        "success": False,
                        "error": (
                            f"Query contains dangerous keyword '{keyword}'. "
                            "Only SELECT queries are allowed for security "
                            "reasons."
                        ),
                        "security_check": "failed",
                    }

            # Ensure query starts with SELECT
            if not query_upper.startswith("SELECT"):
                return {
                    "success": False,
                    "error": (
                        "Query must start with SELECT for security reasons. "
                        "Only read operations are allowed."
                    ),
                    "security_check": "failed",
                }

            # Log the query for security monitoring
            self.logger.warning(f"Executing custom SQL query: {query[:100]}...")

            result = await self.db_connection.execute_query(query, limit)
            log_database_operation("execute_query", success=result["success"])
            return result
        except Exception as e:
            self.logger.error(f"Execute query failed: {e}")
            return {"success": False, "error": str(e)}
