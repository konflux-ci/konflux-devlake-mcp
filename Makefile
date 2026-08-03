# Makefile for Konflux DevLake MCP Server Test Suite

.PHONY: help install install-dev test test-unit test-all test-file test-clean run run-http dev docker-build docker-run clean check-deps ci-quick ci quick-test watch-tests docs pre-commit test-parallel test-verbose test-debug test-performance test-integration test-integration-tls test-e2e test-integration-setup test-integration-teardown setup-dev help-test check-compose check-runtime

# Container compose command (evaluated once): prefers `docker compose`, then
# `docker-compose`, then `podman compose`, then `podman-compose`. Empty if
# none are available on PATH.
COMPOSE := $(shell \
	if docker compose version >/dev/null 2>&1; then echo "docker compose"; \
	elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; \
	elif podman compose version >/dev/null 2>&1; then echo "podman compose"; \
	elif command -v podman-compose >/dev/null 2>&1; then echo "podman-compose"; \
	fi)

# Raw container runtime (no compose), for starting standalone containers -
# e.g. the TLS-enforcing MySQL container managed directly by pytest rather
# than via compose. Empty if neither is available on PATH.
RUNTIME := $(shell command -v docker >/dev/null 2>&1 && echo docker || { command -v podman >/dev/null 2>&1 && echo podman; })

check-compose:
	@if [ -z "$(COMPOSE)" ]; then \
		echo "❌ No docker compose / docker-compose / podman compose / podman-compose found on PATH"; \
		exit 1; \
	fi

check-runtime:
	@if [ -z "$(RUNTIME)" ]; then \
		echo "❌ Neither docker nor podman found on PATH"; \
		exit 1; \
	fi

# Default target
help: ## Show this help message
	@echo "Konflux DevLake MCP Server - Development Commands"
	@echo "=================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install dependencies plus dev/test tooling
	pip install -r requirements.txt
	pip install pytest-cov pytest-timeout pytest-xdist

# Testing commands
test-unit: ## Run unit tests (mocked DB, no containers required)
	python run_tests.py --unit --verbose

test-integration: check-compose ## Run integration tests (requires docker/podman, auto setup/teardown)
	@echo "🚀 Starting integration tests with database setup..."
	@echo "📦 Starting MySQL database..."
	@$(COMPOSE) up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Running integration tests..."
	@python run_tests.py --integration --verbose; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	$(COMPOSE) down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-integration-tls: check-compose check-runtime ## Run MySQL TLS integration tests (require_secure_transport=ON, requires docker/podman compose, plus docker or podman)
	@echo "🔐 Starting MySQL TLS integration tests..."
	@echo "📦 Starting non-TLS MySQL database (for the regression check)..."
	@$(COMPOSE) up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Running TLS integration tests..."
	@echo "ℹ️  A second, TLS-enforcing MySQL container is started/stopped automatically by the tests"
	@CONTAINER_RUNTIME=$(RUNTIME) python -m pytest tests/integration/test_mysql_tls_integration.py -m integration -vv --tb=short; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	$(COMPOSE) down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-e2e: check-compose ## Run LLM end-to-end tests (requires GEMINI_API_KEY)
	@echo "🤖 Running LLM E2E tests..."
	@{ \
	  if [ -n "$$E2E_TEST_MODELS" ]; then \
	    IFS=,; out=""; \
	    for m in $$E2E_TEST_MODELS; do \
	      case "$$m" in \
	        gemini/*) [ -n "$$GEMINI_API_KEY" ] && out="$${out:+$${out},}$$m" ;; \
	        *) out="$${out:+$${out},}$$m" ;; \
	      esac; \
	    done; \
	    echo "   Models: $${out:-none}"; \
	  else \
	    out=""; \
	    [ -n "$$GEMINI_API_KEY" ] && out="$${out:+$${out},}gemini/gemini-2.5-pro"; \
	    echo "   Models: $${out:-none}"; \
	  fi; \
	}
	@if [ -z "$$GEMINI_API_KEY" ]; then \
		echo "❌ No LLM API keys set. Set GEMINI_API_KEY."; \
		exit 1; \
	fi
	@$(COMPOSE) up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Initializing database (via container mysql client)..."
	@$(COMPOSE) exec -T mysql mysql -uroot -ptest_password -e "DROP DATABASE IF EXISTS lake; CREATE DATABASE lake;"
	@$(COMPOSE) exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/01-schema.sql
	@$(COMPOSE) exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/02-test-data.sql
	@echo "🧪 Running tests (stdio by default)..."
	@LITELLM_LOGGING=0 LITELLM_DISABLE_LOGGING=1 LITELLM_VERBOSE=0 LITELLM_LOGGING_QUEUE=0 pytest tests/e2e -vv --maxfail=1 --tb=short; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	$(COMPOSE) down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-all: check-compose ## Run unit + integration + e2e tests
	@echo "🚀 Running comprehensive test suite..."
	@echo "📦 Starting MySQL database..."
	@$(COMPOSE) up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 35
	@echo "🧪 Running all tests..."
	@python run_tests.py --all --verbose; \
	CORE_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	$(COMPOSE) down -v; \
	echo "✅ Database cleaned up"; \
	if [ $$CORE_RESULT -ne 0 ]; then \
		echo "❌ Core tests failed"; \
		exit $$CORE_RESULT; \
	fi; \
	echo "🤖 Running LLM E2E tests..."; \
	$(MAKE) --no-print-directory test-e2e; \
	E2E_RESULT=$$?; \
	if [ $$E2E_RESULT -ne 0 ]; then \
		echo "❌ E2E tests failed"; \
		exit $$E2E_RESULT; \
	fi; \
	echo ""; \
	echo "✅ All tests passed"

# Container image commands
docker-build: check-runtime ## Build container image
	@$(RUNTIME) build -t konflux-devlake-mcp .

docker-run: check-runtime ## Run container image
	@$(RUNTIME) run -p 3000:3000 konflux-devlake-mcp

# Utility commands
test-clean: ## Clean test artifacts and cache
	python run_tests.py --clean

check-deps: ## Check if test dependencies are installed
	python run_tests.py --check-deps

# Environment setup
setup-dev: install-dev ## Install dev dependencies and prepare local environment
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything is working"

# Help for specific commands
help-test: ## Show detailed testing command reference
	@echo "Testing Commands:"
	@echo ""
	@echo "  Unit Tests (Tests tool logic and parameter validation):"
	@echo "    test-unit        - Unit tests only"
	@echo ""
	@echo "  Integration Tests (Tests tool functionality against a SQL database):"
	@echo "    test-integration     - Integration tests (requires docker/podman compose, auto setup/teardown)"
	@echo "    test-integration-tls - MySQL TLS (require_secure_transport=ON) tests (requires docker/podman compose, plus docker or podman)"
	@echo ""
	@echo "  E2E Tests (Tests tool functionality using a LLM):"
	@echo "    test-e2e         - E2E tests with LLM integration"
	@echo "                       Default: gemini/gemini-2.5-pro"
	@echo "                       Note: Gemini requires 'gemini/' prefix"
	@echo "                       Requires: GEMINI_API_KEY"
	@echo ""
	@echo "  All Tests (Unit + Integration + E2E):"
	@echo "    test-all         - All tests (requires integration and e2e requirements to be met)"
	@echo ""
	@echo "  Utilities:"
	@echo "    test-clean       - Clean test artifacts and cache"
	@echo "    check-deps       - Check if dependencies are installed"
