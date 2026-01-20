# Konflux DevLake MCP Server - Architecture Documentation

## Overview

The Konflux DevLake MCP Server is a production-ready Model Context Protocol (MCP) server that provides **intelligent natural language to SQL query transformation** capabilities for Konflux DevLake databases. It serves as a bridge between AI assistants and DevLake data, enabling users to ask questions in plain language and receive structured data results.

### Core Capability: Natural Language to SQL Processing

The server's primary innovation is its ability to:
1. Accept natural language queries from AI assistants (e.g., "Show me all incidents from October")
2. Transform these queries into validated, secure SQL statements
3. Execute queries with full security validation and result masking
4. Return structured, readable data to the user

This eliminates the need for users to know SQL syntax while maintaining security and performance through direct database queries.

**Version**: 1.0.0
**License**: Open Source
**Language**: Python 3.11+
**Framework**: MCP Protocol

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Overview](#component-overview)
3. [Transport Layer](#transport-layer)
4. [Tools System](#tools-system)
5. [Authentication](#authentication)
6. [Security Architecture](#security-architecture)
7. [Database Layer](#database-layer)
8. [Configuration Management](#configuration-management)
9. [Logging and Monitoring](#logging-and-monitoring)
10. [Deployment Architecture](#deployment-architecture)
11. [API Reference](#api-reference)
12. [Extension Points](#extension-points)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MCP Client (AI Assistant)                     │
└─────────────────────────────┬───────────────────────────────────────┘
                               │
                               │ MCP Protocol
                               │ (JSON-RPC over HTTP/STDIO)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Konflux DevLake MCP Server                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Transport Layer                            │ │
│  │  ┌───────────────┐                    ┌──────────────┐         │ │
│  │  │ HTTP Transport│                    │STDIO Transport│        │ │
│  │  │ (Production)  │                    │ (Development)│        │ │
│  │  └───────┬───────┘                    └──────┬───────┘         │ │
│  └──────────┼───────────────────────────────────┼─────────────────┘ │
│             │                                     │                   │
│             ▼                                     ▼                   │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Core MCP Server                              │ │
│  │  ┌──────────────────────────────┐                              │ │
│  │  │    Tool Handler              │                              │ │
│  │  │  - Security Validation      │                              │ │
│  │  │  - Data Masking             │                              │ │
│  │  │  - Error Handling           │                              │ │
│  │  └──────────┬───────────────────┘                              │ │
│  └─────────────┼────────────────────────────────────────────────┘ │
│                │                                                      │
│                ▼                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Tools Manager                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │   Database   │  │  Incidents  │  │   Deployments       │  │ │
│  │  │    Tools     │  │    Tools    │  │      Tools          │  │ │
│  │  └──────┬───────┘  └──────┬──────┘  └──────────┬───────────┘  │ │
│  └─────────┼──────────────────┼────────────────────┼─────────────┘ │
│            │                  │                     │                │
│            ▼                  ▼                     ▼                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Database Connection Manager                        │  │
│  │              (Async connection pooling,                        │  │
│  │              PyMySQL with DictCursor)                          │  │
│  └────────────────────┬──────────────────────────────────────────┘  │
│                       │                                              │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │   DevLake MySQL      │
              │   Database Server    │
              └─────────────────────┘
```

### Key Design Principles

1. **Natural Language Interface**: AI-powered natural language to SQL transformation enabling intuitive database queries
2. **Modular Architecture**: Separation of concerns with clear module boundaries
3. **Security First**: Built-in SQL injection protection, data masking, and validation
4. **Async/Await**: Full asynchronous I/O for high performance
5. **Transport Agnostic**: Support for HTTP (production) and STDIO (development) with graceful error handling
6. **Extensibility**: Plugin-based tools system for easy extension
7. **Production Ready**: Comprehensive logging, error handling, and monitoring
8. **Token Efficiency**: TOON format support for reduced token consumption in LLM interactions
9. **Robust Error Handling**: Intelligent filtering of expected errors, graceful shutdown, and connection error management

---

## Natural Language to SQL Query Processing

### Overview

The Konflux DevLake MCP Server provides an intelligent natural language processing layer that transforms human queries into executable SQL statements. This capability enables non-technical users and AI assistants to interact with complex DevLake databases using conversational language.

### How It Works

```
User Query (Natural Language)
    ↓
"I want to see all open incidents in October"
    ↓
AI Agent (Claude/GPT/LLM)
    ↓
Natural Language Analysis
    ↓
SQL Query Generation
    ↓
SELECT * FROM lake.incidents WHERE status = 'TODO'
  AND created_date >= '2025-10-01' AND created_date < '2025-11-01'
    ↓
Execute Query via execute_query Tool
    ↓
Retrieve and Return Results
```

### Query Transformation Process

1. **Intent Recognition**
   - User expresses query in plain language
   - AI agent analyzes intent and entities
   - Extracts key parameters (dates, filters, aggregations)

2. **Schema Awareness**
   - Access to database schema via `get_table_schema` tool
   - Understanding of table relationships
   - Knowledge of available fields and types

3. **SQL Generation**
   - Constructs valid SQL SELECT queries
   - Applies proper filtering, joins, and aggregations
   - Includes safety constraints (SELECT-only operations)

4. **Query Execution**
   - Uses `execute_query` tool with security validation
   - Applies result limits for performance
   - Returns structured JSON results

### Natural Language Capabilities

**Supported Query Types**:

1. **Incident Analysis**
   - "Show me all critical incidents in the last 30 days"
   - "What incidents are still open?"
   - "Find incidents related to the integration service"

2. **Deployment Tracking**
   - "Show me recent production deployments"
   - "What builds were deployed to staging this week?"
   - "Find all failed deployments for the build service"

3. **Data Exploration**
   - "List all tables in the lake database"
   - "Show me the schema of the incidents table"
   - "What databases are available?"

4. **Custom Analysis**
   - "Count how many PRs had retests in the last 3 months"
   - "Show me PRs with more than 20 retests"
   - "Find the average deployment frequency"

### Example Transformations

**Example 1: Time-Based Filtering**
```
Natural Language: "Show me incidents from October 2025"
SQL Generated: SELECT * FROM lake.incidents
  WHERE created_date >= '2025-10-01'
    AND created_date <= '2025-10-31'
```

**Example 2: Status Filtering**
```
Natural Language: "Find all open incidents"
SQL Generated: SELECT * FROM lake.incidents
  WHERE status = 'TODO' OR status = 'IN_PROGRESS'
```

**Example 3: Complex Aggregation**
```
Natural Language: "Count retests per PR for integration service"
SQL Generated:
  SELECT
    pr.title,
    pr.url,
    COUNT(*) as retest_count
  FROM lake.pull_request_comments prc
  INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
  WHERE prc.body LIKE '%/retest%'
    AND pr.url LIKE '%integration-service%'
  GROUP BY pr.id, pr.title, pr.url
  ORDER BY retest_count DESC
```

### Security in Natural Language Processing

**Query Validation**:
- Only SELECT queries allowed
- SQL injection pattern detection
- Dangerous keyword blocking
- Query length limits
- Schema validation

**Data Protection**:
- Automatic sensitive data masking
- PII detection and redaction
- Result pagination
- Access logging

### Tool Integration

The natural language processing integrates seamlessly with the tool system:

```python
# User asks AI assistant
"Show me the integration service PRs with the most retests"

# AI transforms to tool call
{
  "name": "execute_query",
  "arguments": {
    "query": "SELECT pr.title, pr.url, COUNT(*) as retests " +
             "FROM lake.pull_request_comments prc " +
             "INNER JOIN lake.pull_requests pr " +
             "WHERE pr.url LIKE '%integration-service%' " +
             "GROUP BY pr.id ORDER BY retests DESC LIMIT 10",
    "limit": 10
  }
}

# Server executes with full security validation
# Returns masked, structured results
```

### Benefits

1. **User-Friendly**: No SQL knowledge required
2. **Powerful**: Leverages AI for complex query generation
3. **Safe**: Built-in security validation prevents injection
4. **Fast**: Direct SQL execution without middleware
5. **Flexible**: Supports any SELECT query pattern

### Advanced Features

**Query Optimization**:
- Automatic LIMIT application
- Pagination support
- Efficient join generation
- Index usage awareness

**Intelligent Filtering**:
- Automatic date range parsing
- Status normalization
- Component matching
- Fuzzy search support

**Result Enhancement**:
- Automatic formatting
- Timezone handling
- Unit conversion (minutes to hours)
- Summary statistics

---

## Component Overview

### 1. Server Core (`server/core/`)

#### KonfluxDevLakeMCPServer

**Purpose**: Core MCP protocol server implementation
**Key Responsibilities**:
- MCP protocol handling and request routing
- Tool registration and management
- Protocol event handling (tool lists, calls)
- Server lifecycle management

**Key Methods**:
```python
async def start(transport: BaseTransport) -> None
async def shutdown() -> None
def _setup_protocol_handlers() -> None
def get_server_info() -> Dict[str, Any]
```

**Dependencies**:
- `mcp.server.Server` (MCP SDK)
- `server.handlers.tool_handler.ToolHandler`
- `server.transport.base_transport.BaseTransport`

---

### 2. Factory Pattern (`server/factory/`)

#### ServerFactory

**Purpose**: Dependency injection and server construction
**Key Responsibilities**:
- Server instance creation
- Transport layer initialization
- Configuration validation
- Component assembly

**Factory Methods**:
```python
create_server(config: KonfluxDevLakeConfig) -> KonfluxDevLakeMCPServer
create_transport(transport_type: str, **kwargs) -> BaseTransport
validate_configuration(config: KonfluxDevLakeConfig) -> bool
```

**Benefits**:
- Centralized configuration management
- Easy testing through dependency injection
- Clean separation of concerns

---

### 3. Transport Layer (`server/transport/`)

#### BaseTransport (Abstract)

**Purpose**: Define transport interface
**Interface Methods**:
```python
async def start(server: Server) -> None
async def stop() -> None
def get_transport_info() -> Dict[str, Any]
```

#### HTTP Transport

**Purpose**: Production-ready HTTP/HTTPS communication
**Technology**: Uvicorn + Starlette
**Features**:
- Health check endpoints (`/health`)
- Security statistics (`/security/stats`)
- Graceful error handling
- Stateless session management
- Keep-alive support

**Configuration**:
```python
class HttpTransport:
    def __init__(self, host: str = "0.0.0.0", port: int = 3000)
```

**Endpoints**:
- `POST /mcp` - MCP protocol endpoint
- `GET /health` - Health check
- `GET /security/stats` - Security statistics

**Performance**:
- Async request handling
- Connection pooling
- Configurable timeouts

#### STDIO Transport

**Purpose**: Local development and testing
**Technology**: Standard input/output streams
**Features**:
- Direct process communication
- Simplified debugging
- No network overhead

---

### 4. Tools System (`tools/`)

#### Tools Manager

**Purpose**: Coordinate all tool modules
**Architecture**: Plugin-based modular system

**Module Types**:
1. **Database Tools** (`tools/database_tools.py`)
   - `connect_database`: Database connectivity
   - `list_databases`: Database discovery
   - `list_tables`: Table exploration
   - `get_table_schema`: Schema inspection
   - `execute_query`: SQL query execution

2. **Incident Tools** (`tools/devlake/incident_tools.py`)
   - `get_incidents`: Incident analysis with filtering
   - Automatic deduplication by `incident_key`
   - Resolution time calculation

3. **Deployment Tools** (`tools/devlake/deployment_tools.py`)
   - `get_deployments`: Deployment tracking
   - Environment filtering (PRODUCTION, STAGING, etc.)
   - Project-based filtering

4. **PR Retest Analysis Tools** (`tools/devlake/pr_retest_tools.py`)
   - `analyze_pr_retests`: Comprehensive PR retest analysis
   - Project and repository filtering
   - Retest pattern analysis and root cause identification
   - Category breakdown (bug fixes, features, dependencies, etc.)
   - Timeline visualization data
   - Actionable recommendations
   - Returns data in TOON format for token efficiency (30-60% reduction vs JSON)

**Base Tool Interface**:
```python
class BaseTool:
    async def call_tool(name: str, arguments: Dict[str, Any]) -> str
    def get_tools() -> List[Tool]
```

**Tool Registration Flow**:
```
1. ToolsManager initializes all tool modules
2. Creates tool name → module mapping
3. Routes incoming requests to appropriate module
4. Returns serialized results (JSON or TOON format)
```

**Response Format**:
- Most tools return JSON format for compatibility
- PR Retest Analysis tool uses TOON format for token efficiency
- TOON format reduces token consumption by 30-60% compared to JSON
- Automatic format selection based on tool type

**Project and Repository Filtering**:
- All DevLake tools support project-based filtering via `project_mapping` table
- Repository filtering available for PR and deployment analysis
- Filters applied at SQL query level for optimal performance
- Supports partial matching for repository names

---

## Authentication

### OIDC Authentication (`server/middleware/`)

The server supports OIDC (OpenID Connect) authentication for securing MCP endpoints. When enabled, requests to `/mcp` endpoints require a valid JWT token from a configured OIDC provider (e.g., Red Hat SSO / Keycloak).

#### Components

**OIDCAuthenticator** (`server/middleware/oidc_auth.py`)
- Fetches and caches JWKS from the OIDC provider
- Validates JWT token signatures using RS256
- Verifies token claims (issuer, audience, expiration)
- Extracts user information (sub, username, email, groups)
- Supports Keycloak-specific `realm_access.roles` for group extraction

**AuthMiddleware** (`server/middleware/auth_middleware.py`)
- ASGI middleware that intercepts HTTP requests
- Skips authentication for configured paths (e.g., `/health`, `/security`)
- Extracts Bearer tokens from Authorization headers
- Returns 401/403 responses for failed authentication
- Adds user info to request scope for downstream handlers

#### Configuration

```python
@dataclass
class OIDCConfig:
    enabled: bool = False
    issuer_url: str = ""
    client_id: str = ""
    required_scopes: List[str] = []
    jwks_cache_ttl: int = 3600
    skip_paths: List[str] = ["/health", "/security"]
    verify_ssl: bool = True
    # Offline token support
    offline_token_enabled: bool = False
    token_exchange_client_id: str = ""
    access_token_cache_buffer: int = 60
```

#### Authentication Flow

The server supports two authentication modes:

**Mode 1: Access Token (default)**
- Client obtains JWT access token from OIDC provider
- Client sends access token in Authorization header
- Server validates JWT directly

**Mode 2: Offline Token (when `offline_token_enabled=True`)**
- Client sends offline/refresh token in Authorization header
- Server detects non-JWT token format
- Server exchanges offline token for access token via OIDC provider
- Server caches access token and refreshes when needed
- Server validates the access token

```
Client Request
    |
    v
+-------------------+
|  Auth Middleware  |
+-------------------+
    |
    +-- Skip auth for /health, /security
    |
    +-- Extract Bearer token
    |
    +-- Fetch JWKS from OIDC provider
    |
    +-- Validate JWT signature
    |
    +-- Verify claims (iss, aud, exp)
    |
    +-- Check required scopes
    |
    v
+-------------------+
|   MCP Handler     |
| (with user info)  |
+-------------------+
```

#### Environment Variables

| Variable | Description |
|----------|-------------|
| `OIDC_ENABLED` | Enable OIDC authentication (`true`/`false`) |
| `OIDC_ISSUER_URL` | OIDC issuer URL |
| `OIDC_CLIENT_ID` | OIDC client ID / audience |
| `OIDC_REQUIRED_SCOPES` | Comma-separated required scopes |
| `OIDC_JWKS_CACHE_TTL` | JWKS cache TTL in seconds |
| `OIDC_SKIP_PATHS` | Comma-separated paths to skip auth |
| `OIDC_VERIFY_SSL` | Verify SSL certificates |
| `OIDC_OFFLINE_TOKEN_ENABLED` | Accept offline tokens (`true`/`false`) |
| `OIDC_TOKEN_EXCHANGE_CLIENT_ID` | Client ID for token exchange |
| `OIDC_ACCESS_TOKEN_CACHE_BUFFER` | Seconds before expiry to refresh token |

---

### 7. Security Architecture (`utils/security.py`)

#### Security Manager

**Purpose**: Centralized security validation and management

**Components**:

1. **SQL Injection Detection**
   - Pattern-based detection
   - Only allows SELECT queries
   - Blacklist dangerous keywords
   - Validates balanced parentheses

2. **Data Masking**
   - Email addresses
   - Phone numbers
   - IP addresses
   - Credit card numbers
   - SSN patterns

3. **Query Validation**
   - Database name validation
   - Table name validation
   - Query length limits
   - Reserved word checking

4. **Session Management**
   - Token generation
   - Expiration handling
   - Cleanup procedures

**Security Features**:
```python
# Example: SQL query validation
def validate_sql_query(query: str) -> Tuple[bool, str]:
    # Only allows SELECT queries
    # Blocks DROP, DELETE, INSERT, UPDATE, etc.
    # Validates structure and length
```

**Data Masking**:
```python
# Mask sensitive data in results
def mask_database_result(result: Any) -> Any:
    # Recursively masks emails, phones, IPs, etc.
```

---

### 8. Database Layer (`utils/db.py`)

#### Database Connection Manager

**Purpose**: Async database connectivity and query execution
**Technology**: PyMySQL with DictCursor

**Key Features**:
- Connection pooling
- Async query execution
- Automatic datetime serialization
- Result limiting and pagination
- Error handling and logging

**Connection Management**:
```python
class KonfluxDevLakeConnection:
    async def connect() -> Dict[str, Any]
    async def execute_query(query: str, limit: int = 100) -> Dict[str, Any]
    async def close()
    async def test_connection() -> bool
```

**DateTime Handling**:
- Custom `DateTimeEncoder` for JSON serialization
- Automatic ISO format conversion
- Recursive datetime serialization in nested structures

---

### 9. Configuration Management (`utils/config.py`)

#### Configuration Hierarchy

```
Command Line Arguments
    ↓
Environment Variables
    ↓
Default Values
```

**Configuration Structure**:
```python
@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

@dataclass
class ServerConfig:
    transport: str
    host: str
    port: int

@dataclass
class LoggingConfig:
    level: str
    format: str
```

**Validation**:
- Database credentials validation
- Port range checks
- Required field validation

---

### 10. Logging and Monitoring (`utils/logger.py`)

#### Logging Features

1. **Structured Logging**
   - Timestamp, module, level, message
   - Automatic log rotation
   - Separate error logs

2. **Log Levels**
   - DEBUG: Detailed debugging information
   - INFO: General operational messages
   - WARNING: Unexpected but recoverable events
   - ERROR: Error conditions

3. **Log Files**
   - `logs/konflux_devlake_mcp_server.log` - General logs
   - `logs/konflux_devlake_mcp_server_error.log` - Errors only

4. **Operation Logging**
   - Tool call tracking
   - Database operation logging
   - Security event logging

5. **Intelligent Error Filtering**
   - Suppresses expected errors (e.g., `ClosedResourceError` from client disconnections)
   - Filters MCP library noise (connection errors, normal disconnections)
   - Reduces log clutter while maintaining important error visibility
   - Graceful handling of `CancelledError` during server shutdown

**Example Logging**:
```python
logger.info("Starting Konflux DevLake MCP Server")
logger.debug(f"Tool call: {name} with args {arguments}")
logger.warning("Potential SQL injection detected")
```

---

## Deployment Architecture

### Kubernetes Deployment

**Components**:
- Deployment with 1 replica
- Service exposing port 3000
- ConfigMap for configuration
- Secret for database credentials
- ServiceAccount with RBAC

**Resource Requests**:
- Memory: 512Mi (request), 1Gi (limit)
- CPU: 250m (request), 500m (limit)

**Security**:
- Non-root user execution
- Read-only filesystem where possible
- Security context restrictions
- Network policies

**Health Checks**:
- Liveness probe: `/health` endpoint
- Readiness probe: Connection testing
- Startup probe: Initial grace period

### Docker Container

**Base Image**: `python:3.11-slim`
**Multi-stage Build**: Builder + Runtime stages
**User**: Non-root `app` user
**Port**: 3000

**Build Process**:
```dockerfile
# Stage 1: Builder
- Install system dependencies
- Install Python packages

# Stage 2: Runtime
- Copy dependencies from builder
- Copy application code
- Set up non-root user
- Configure health checks
```

---

## API Reference

### Available Tools

#### Database Tools

**`connect_database`**
- **Description**: Test database connectivity
- **Arguments**: None
- **Returns**: Connection status and database information

**`list_databases`**
- **Description**: List all available databases
- **Arguments**: None
- **Returns**: Array of database names

**`list_tables`**
- **Description**: List tables in a database
- **Arguments**: `database` (string, required)
- **Returns**: Array of table names

**`get_table_schema`**
- **Description**: Get detailed table schema
- **Arguments**: `database` (string), `table` (string)
- **Returns**: Column definitions with types and constraints

**`execute_query`**
- **Description**: Execute custom SQL query (SELECT only) with natural language support. This tool enables AI agents to transform natural language questions into SQL queries and retrieve data from the DevLake database. Supports complex queries including JOINs, GROUP BY, aggregations, and filtering.
- **Arguments**: `query` (string), `limit` (integer, optional)
- **Returns**: Query results with row count and structured data
- **Natural Language Example**: User asks "Show me incidents from October" → AI generates SQL → Tool executes query → Returns masked results

#### Incident Tools

**`get_incidents`**
- **Description**: Get incidents with deduplication and filtering
- **Arguments**: Multiple filter parameters
- **Returns**: Deduplicated incident list with metadata

#### Deployment Tools

**`get_deployments`**
- **Description**: Get deployments with filtering
- **Arguments**: Multiple filter parameters
- **Returns**: Deployment list with metadata

#### PR Retest Analysis Tools

**`analyze_pr_retests`**
- **Description**: Comprehensive analysis of pull requests that required manual retest commands (comments containing '/retest'). Provides detailed statistics, pattern analysis, and actionable recommendations.
- **Arguments**:
  - `repo_name` (string, optional): Repository name to analyze (e.g., 'integration-service')
  - `project_name` (string, optional): DevLake project name (e.g., 'Secureflow - Konflux - Global')
  - `days_back` (integer, optional): Number of days back to analyze (default: 90)
  - `start_date` (string, optional): Start date for analysis (format: YYYY-MM-DD)
  - `end_date` (string, optional): End date for analysis (format: YYYY-MM-DD)
  - `top_n` (integer, optional): Number of top PRs to return (default: 15, max: 50)
  - `exclude_bots` (boolean, optional): Exclude bot comments from analysis (default: true)
- **Returns**: TOON-encoded string containing:
  - Executive summary (total retests, affected PRs, average retests per PR)
  - Top PRs by retest count with detailed metrics
  - Category breakdown (bug fixes, features, dependencies, etc.)
  - Timeline data for visualization
  - Pattern analysis by PR status
  - Actionable recommendations
- **Features**:
  - Exact `/retest` command matching (case-insensitive, handles quoted comments)
  - Project and repository filtering via `project_mapping` table
  - Bot comment exclusion
  - Token-efficient TOON format (30-60% reduction vs JSON)

---

## Extension Points

### Adding New Tools

1. **Create Tool Module**:
```python
from tools.base.base_tool import BaseTool

class MyNewTools(BaseTool):
    def get_tools(self) -> List[Tool]:
        # Define tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        # Implement tool logic
```

2. **Register in Tools Manager**:
```python
self._tool_modules.append(MyNewTools(self.db_connection))
```

3. **Add to Security Validation** (if needed):
```python
def _validate_tool_request(self, name: str, arguments: Dict[str, Any]):
    if name == "my_new_tool":
        # Add validation logic
```

### Adding New Transports

1. **Extend BaseTransport**:
```python
class MyCustomTransport(BaseTransport):
    async def start(self, server: Server) -> None:
        # Implement transport

    async def stop(self) -> None:
        # Implement cleanup
```

2. **Register in Factory**:
```python
def create_transport(self, transport_type: str, **kwargs):
    if transport_type == "my_custom":
        return MyCustomTransport(**kwargs)
```

---

## Security Features

### SQL Injection Prevention

1. **Keyword Blacklist**: Blocks dangerous SQL keywords
2. **Pattern Detection**: Identifies injection patterns
3. **SELECT-only Policy**: Only allows read operations
4. **Query Validation**: Structure and length validation

### Data Masking

1. **Automatic Masking**: Sensitive data patterns
2. **Custom Encoders**: DateTime serialization
3. **Recursive Processing**: Handles nested data structures

### Access Control

1. **Input Validation**: All arguments validated
2. **Name Sanitization**: Database and table names
3. **Rate Limiting**: Per-user operation limits

---

## Performance Considerations

### Async I/O

- Fully async database operations
- Non-blocking request handling
- Concurrent tool execution capability

### Connection Management

- Connection pooling
- Automatic reconnection
- Graceful degradation

### Query Optimization

- Result limiting (`limit` parameter)
- Pagination support
- Efficient cursor usage

---

## Monitoring and Observability

### Health Checks

- `/health` endpoint for liveness
- Database connectivity testing
- Security statistics endpoint

### Logging

- Structured JSON logging
- Operation tracking
- Error aggregation

### Metrics (Future)

- Request count
- Response time
- Error rate
- Security events

---

## Best Practices

### For Developers

1. Use type hints throughout
2. Follow async/await patterns
3. Implement proper error handling
4. Add comprehensive logging
5. Write unit tests

### For Operators

1. Monitor health endpoint
2. Review error logs regularly
3. Set appropriate resource limits
4. Enable security monitoring
5. Backup configurations

### For Security

1. Rotate credentials regularly
2. Enable audit logging
3. Monitor security events
4. Keep dependencies updated
5. Review access patterns

---

## Troubleshooting

### Common Issues

**1. Database Connection Failure**
- Check credentials
- Verify network connectivity
- Review connection logs

**2. SQL Injection Warnings**
- Verify query syntax
- Check for nested SQL
- Review security patterns

**3. High Memory Usage**
- Reduce result limits
- Implement pagination
- Review connection pooling

---

## Future Enhancements

1. GraphQL support
2. WebSocket transport
3. Caching layer (Redis)
4. Metrics collection (Prometheus)
5. Distributed tracing
6. Rate limiting per tool
7. Result caching

---

## Contributing

See `CONTRIBUTING.md` for guidelines on:
- Code style
- Testing requirements
- Pull request process
- Issue reporting

---

## License

Open Source - See LICENSE file for details

---

## Authors

The Konflux DevLake MCP Server development team

---

**Last Updated**: January 2026
**Version**: 1.1.0
**Status**: Production Ready
