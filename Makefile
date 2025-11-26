# Makefile for Konflux DevLake MCP Server Test Suite

.PHONY: help install install-dev test test-unit test-all test-file test-clean run run-http dev docker-build docker-run clean check-deps ci-quick ci quick-test watch-tests docs pre-commit test-parallel test-verbose test-debug test-performance test-integration test-e2e test-integration-setup test-integration-teardown setup-dev help-test

# Default target
help:
	@echo "Konflux DevLake MCP Server - Development Commands"
	@echo "=================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest-cov pytest-timeout pytest-xdist

# Testing commands
test-unit:
	python run_tests.py --unit --verbose

test-integration:
	@echo "🚀 Starting integration tests with database setup..."
	@echo "📦 Starting MySQL database..."
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Running integration tests..."
	@python run_tests.py --integration --verbose; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-e2e:
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
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Initializing database (via container mysql client)..."
	@docker compose exec -T mysql mysql -uroot -ptest_password -e "DROP DATABASE IF EXISTS lake; CREATE DATABASE lake;"
	@docker compose exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/01-schema.sql
	@docker compose exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/02-test-data.sql
	@echo "🧪 Running tests (stdio by default)..."
	@LITELLM_LOGGING=0 LITELLM_DISABLE_LOGGING=1 LITELLM_VERBOSE=0 LITELLM_LOGGING_QUEUE=0 pytest tests/e2e -vv --maxfail=1 --tb=short; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-all:
	@echo "🚀 Running comprehensive test suite..."
	@echo "📦 Starting MySQL database..."
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 35
	@echo "🧪 Running all tests..."
	@python run_tests.py --all --verbose; \
	CORE_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
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

# Docker commands
docker-build: ## Build Docker image
	docker build -t konflux-devlake-mcp .

docker-run: ## Run Docker container
	docker run -p 3000:3000 konflux-devlake-mcp

# Utility commands
test-clean:
	python run_tests.py --clean

check-deps:
	python run_tests.py --check-deps

# Environment setup
setup-dev: install-dev
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything is working"

# Help for specific commands
help-test:
	@echo "Testing Commands:"
	@echo ""
	@echo "  Unit Tests (Tests tool logic and parameter validation):"
	@echo "    test-unit        - Unit tests only"
	@echo ""
	@echo "  Integration Tests (Tests tool functionality against a SQL database):"
	@echo "    test-integration - Integration tests (requires docker engine to be running, auto setup/teardown)"
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
