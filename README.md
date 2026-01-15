# Konflux DevLake MCP Server

[![Unit Tests](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/unit.yaml/badge.svg)](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/unit.yaml)
[![Integration Tests](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/integration.yaml/badge.svg)](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/integration.yaml)
[![E2E Tests](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/e2e.yaml/badge.svg)](https://github.com/konflux-ci/konflux-devlake-mcp/actions/workflows/e2e.yaml)

A MCP server that enables natural language querying of Konflux DevLake databases. This server acts as a bridge between AI assistants and your DevLake database, allowing you to ask questions in plain language and get structured data back.

## Documentation

- **[Full Architecture Documentation](./docs/ARCHITECTURE.md)** - Complete system architecture and design patterns
- **[Documentation Index](./docs/README.md)** - Visual diagrams and documentation catalog
- **[Architecture Diagrams](./docs/)** - System diagrams in Mermaid format

## Quick Start

### Option 1: Python (Development)

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

1. **Start the server**:

```bash
python konflux-devlake-mcp.py --transport http --host 0.0.0.0 --port 3000 --db-host localhost --db-port 3306 --db-user root --db-password password --db-database lake
```

### Option 2: Docker (Production)

1. **Build the Docker image**:

```bash
docker build -t konflux-devlake-mcp:latest .
```

1. **Run the container**:

```bash
docker run -d \
  --name konflux-mcp-server \
  -p 3000:3000 \
  -e DB_HOST=your_db_host \
  -e DB_PORT=3306 \
  -e DB_USER=root \
  -e DB_PASSWORD=your_password \
  -e DB_DATABASE=lake \
  -e LOG_LEVEL=INFO \
  konflux-devlake-mcp:latest
```

1. **Push to registry (if needed)**:

```bash
docker tag konflux-devlake-mcp:latest quay.io/flacatus/mcp-lake:1.0.0
docker push quay.io/flacatus/mcp-lake:1.0.0
```

## Configuration

### Command Line Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--transport` | Transport protocol (stdio/http) | `--transport http` |
| `--host` | Server host | `--host 0.0.0.0` |
| `--port` | Server port | `--port 3000` |
| `--db-host` | Database host | `--db-host localhost` |
| `--db-port` | Database port | `--db-port 3306` |
| `--db-user` | Database username | `--db-user root` |
| `--db-password` | Database password | `--db-password your_password` |
| `--db-database` | Database name | `--db-database lake` |
| `--log-level` | Logging level | `--log-level INFO` |

### Timeout Configuration

The server includes configurable timeout settings optimized for LLM connections:

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SERVER_TIMEOUT_KEEP_ALIVE` | HTTP keep-alive timeout in seconds | `600` (10 minutes) |
| `SERVER_TIMEOUT_GRACEFUL_SHUTDOWN` | Graceful shutdown timeout in seconds | `120` (2 minutes) |
| `DB_CONNECT_TIMEOUT` | Database connection timeout in seconds | `60` (1 minute) |
| `DB_READ_TIMEOUT` | Database read timeout in seconds | `600` (10 minutes) |
| `DB_WRITE_TIMEOUT` | Database write timeout in seconds | `120` (2 minutes) |

These high default values ensure that long-running LLM requests and complex database queries don't timeout prematurely.

### OIDC Authentication (Red Hat SSO / Keycloak)

The server supports OIDC authentication for securing MCP endpoints. When enabled, all requests to `/mcp` endpoints require a valid JWT token.

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OIDC_ENABLED` | Enable OIDC authentication | `false` |
| `OIDC_ISSUER_URL` | OIDC issuer URL (e.g., `https://sso.redhat.com/auth/realms/redhat-external`) | - |
| `OIDC_CLIENT_ID` | OIDC client ID / audience | - |
| `OIDC_REQUIRED_SCOPES` | Comma-separated list of required scopes | - |
| `OIDC_JWKS_CACHE_TTL` | JWKS cache TTL in seconds | `3600` |
| `OIDC_SKIP_PATHS` | Comma-separated paths to skip auth | `/health,/security` |
| `OIDC_VERIFY_SSL` | Verify SSL certificates | `true` |

**Example: Enable Red Hat SSO authentication**

```bash
export OIDC_ENABLED=true
export OIDC_ISSUER_URL="https://sso.redhat.com/auth/realms/redhat-external"
export OIDC_CLIENT_ID="cloud-services"
```

Clients must include the `Authorization: Bearer <token>` header with a valid JWT token obtained from the OIDC provider.

### Environment Variables (Alternative)

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_DATABASE=lake
export TRANSPORT=http
export SERVER_HOST=0.0.0.0
export SERVER_PORT=3000
export LOG_LEVEL=INFO

# Timeout Configuration (for LLM connections)
export SERVER_TIMEOUT_KEEP_ALIVE=600      # HTTP keep-alive timeout in seconds (default: 600)
export SERVER_TIMEOUT_GRACEFUL_SHUTDOWN=120  # Graceful shutdown timeout in seconds (default: 120)
export DB_CONNECT_TIMEOUT=60              # Database connection timeout in seconds (default: 60)
export DB_READ_TIMEOUT=600                # Database read timeout in seconds (default: 600)
export DB_WRITE_TIMEOUT=120               # Database write timeout in seconds (default: 120)
```

Then run:

```bash
python konflux-devlake-mcp.py
```

### Help Command

```bash
python konflux-devlake-mcp.py --help
```

## Available Tools

This server provides several specialized tools for working with your DevLake data:

- **Database Tools**: Connect to your database, list available databases and tables, execute custom SQL queries, and get detailed table schemas
- **Incident Analysis**: Get unique incidents with automatic deduplication, analyze incident patterns, and track resolution times. Returns data in TOON format for token efficiency.
- **Deployment Tracking**: Monitor deployment data with advanced filtering, track deployment frequency, and analyze service distribution
- **PR Retest Analysis**: Comprehensive analysis of pull requests that required manual retest commands (`/retest`). Provides detailed statistics including:
  - Total count of manual retest comments (excluding bot comments)
  - Number of PRs affected and average retests per PR
  - Top PRs with most retests (including PR title, URL, duration, changes, and status)
  - Analysis of root causes and failure patterns
  - Breakdown by PR category (bug fixes, features, dependencies, etc.)
  - Timeline visualization data
  - Actionable recommendations to reduce retest frequency
  - Returns data in TOON format for token efficiency

## Features

- **Natural Language Processing**: Convert plain English questions into SQL queries automatically
- **Security First**: Built-in SQL injection detection and comprehensive query validation to protect your data
- **DevLake Integration**: Specialized tools for analyzing incident, deployment, and PR retest data from Konflux DevLake
- **Token-Efficient Responses**: Uses TOON format for tool responses (incident tools and PR retest tools), reducing token consumption by 30-60% compared to JSON
- **Project & Repository Filtering**: Advanced filtering capabilities for analyzing data by DevLake project and repository name
- **Flexible Transport**: Support for both HTTP and stdio transport protocols with graceful error handling
- **Comprehensive Logging**: Detailed logging with rotation, error tracking, and intelligent filtering of expected disconnection errors
- **LLM-Optimized Timeouts**: High default timeout values (10 minutes keep-alive) to support long-running LLM requests and database queries
- **Configurable Timeouts**: All timeout settings are configurable via environment variables for different deployment scenarios
- **Enhanced Error Handling**: Graceful handling of client disconnections (`ClosedResourceError`) and server shutdowns (`CancelledError`) without noisy error logs

## Security

Your data security is our priority:

- **OIDC Authentication**: Optional JWT-based authentication via Red Hat SSO / Keycloak
- **SQL Injection Protection**: Automatic detection and prevention of potential SQL injection attacks
- **Query Validation**: Every query is validated and sanitized before execution
- **Data Masking**: Sensitive information is automatically masked in query results
- **Access Control**: Database-level access control ensures only authorized operations are performed

## Response Format

The server uses **TOON format** (Token-Optimized Object Notation) for tool responses to reduce token consumption:

- **Incident Tools**: All responses use TOON format (30-60% token reduction vs JSON)
- **PR Retest Analysis Tool**: All responses use TOON format (30-60% token reduction vs JSON)
- **Deployment Tools**: Currently use JSON format
- **Database Tools**: Currently use JSON format

TOON format is a compact, human-readable serialization format that significantly reduces token costs when working with LLMs while maintaining full data fidelity.

## Monitoring

Keep track of your server's health and performance:

- **Application Logs**: `logs/konflux_devlake_mcp_server.log` - General server activity and operations
- **Error Logs**: `logs/konflux_devlake_mcp_server_error.log` - Detailed error information for troubleshooting
- **Health Check**: `GET http://localhost:3000/health` - Monitor server status and connectivity
- **Error Handling**: The server gracefully handles client disconnections and server shutdowns without logging expected errors (e.g., `ClosedResourceError`, `CancelledError`)

### Testing

Use Makefile to easily run local tests on MCP tools (requires docker engine and LLM API key):

```bash
make install

make test-unit
make test-integration
make test-e2e

make test-all
```

### Linting & pre-commit

Automatically run linters when making a commit:

```bash
make install
pre-commit install

pre-commit run --all-files
```

Configured tools:
- black (python formatting)
- flake8 (python style/lint)
- yamllint (YAML validation)

## Contributing

We welcome contributions to improve this project:

1. Fork the repository
2. Create a feature branch for your changes
3. Make your improvements and add tests
4. Submit a pull request with a clear description of your changes

## Use Cases

This MCP server is particularly useful for:

- **Data Analysts**: Quickly query DevLake data without writing complex SQL
- **DevOps Teams**: Monitor incidents and deployments through natural language queries
- **AI Assistants**: Enable AI tools to access and analyze your DevLake data with optimized token usage
- **Business Intelligence**: Generate reports and insights from your DevLake database
- **Development Teams**: Debug and analyze application performance data, identify PR retest patterns, and optimize CI/CD workflows
- **Quality Assurance**: Analyze PR retest frequency, identify flaky tests, and improve test reliability

## Recent Updates

### Version 1.0.0+ Features

- **PR Retest Analysis Tool**: New comprehensive tool for analyzing pull requests that required manual retest commands
- **TOON Format Support**: Incident tools and PR retest tools now use TOON format for 30-60% token reduction
- **Enhanced Timeout Configuration**: High default timeouts (10 minutes) optimized for LLM connections
- **Improved Error Handling**: Graceful handling of client disconnections and server shutdowns
- **Database Timeout Settings**: Configurable timeouts for database connections to handle long-running queries
- **Project & Repository Filtering**: Enhanced filtering capabilities for precise data analysis
