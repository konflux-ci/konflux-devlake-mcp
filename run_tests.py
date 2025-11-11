#!/usr/bin/env python3
"""
Test Runner for Konflux DevLake MCP Server

This script provides a convenient way to run different types of tests
with various options and configurations.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description="", suppress_output=False):
    """Run a command and handle the output."""
    if description and not suppress_output:
        print(f"\n🔄 {description}")

    if not suppress_output:
        print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if not suppress_output:
        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")

    try:
        import pytest

        print(f"✅ pytest {pytest.__version__} is installed")
    except ImportError:
        print("❌ pytest is not installed. Run: pip install -r requirements.txt")
        return False

    try:
        import pytest_asyncio

        ver = getattr(pytest_asyncio, "__version__", "")
        if ver:
            print(f"✅ pytest-asyncio {ver} is installed")
        else:
            # Reference the module so it's not considered unused
            _ = pytest_asyncio
            print("✅ pytest-asyncio is installed")
    except ImportError:
        print("❌ pytest-asyncio is not installed. Run: pip install -r requirements.txt")
        return False

    return True


def run_unit_tests(verbose=False, specific_test=None):
    """Run unit tests."""
    cmd = ["python", "-m", "pytest", "tests/unit/", "-m", "unit or security"]

    if verbose:
        cmd.append("-v")

    if specific_test:
        cmd.append(specific_test)

    return run_command(cmd, "Running unit tests")


def run_all_tests(verbose=False):
    """Run all tests."""
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "Running all tests")


def run_security_tests(verbose=False):
    """Run security-related tests."""
    cmd = ["python", "-m", "pytest", "tests/unit/", "-m", "security"]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, "Running security tests")


def run_integration_tests(verbose=False):
    """Run integration tests."""
    print("🧪 Running integration tests...")
    print("ℹ️  Note: Integration tests require a MySQL database to be running.")
    print("ℹ️  Use 'make test-integration' for automatic database setup.")

    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/integration/",
        "-m",
        "integration",
        "-vv",
        "--tb=short",
    ]
    if verbose:
        cmd.append("-s")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def run_specific_test_file(test_file, verbose=False):
    """Run a specific test file."""
    cmd = ["python", "-m", "pytest", test_file]

    if verbose:
        cmd.append("-v")

    return run_command(cmd, f"Running tests in {test_file}")


def clean_test_artifacts():
    """Clean test artifacts and cache files."""
    print("🧹 Cleaning test artifacts...")

    artifacts = [".pytest_cache", "__pycache__", "*.pyc", "*.pyo"]

    for artifact in artifacts:
        if os.path.exists(artifact):
            if os.path.isdir(artifact):
                import shutil

                shutil.rmtree(artifact)
                print(f"Removed directory: {artifact}")
            else:
                os.remove(artifact)
                print(f"Removed file: {artifact}")

    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                dir_path = os.path.join(root, dir_name)
                import shutil

                shutil.rmtree(dir_path)
                print(f"Removed directory: {dir_path}")


def main():
    """Main function to handle command line arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test runner for Konflux DevLake MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\nExamples:\n"
            "  python run_tests.py --unit                    # Run unit tests only\n"
            "  python run_tests.py --all                     # Run all tests\n"
            "  python run_tests.py --security                # Run security tests only\n"
            "  python run_tests.py --integration\n"
            "    # Run integration tests (requires database)\n"
            "  python run_tests.py --file test_config.py     # Run specific test file\n"
            "  python run_tests.py --clean                   # Clean test artifacts\n"
        ),
    )

    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--security", action="store_true", help="Run security tests only")
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests only (requires database)",
    )
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument(
        "--test",
        type=str,
        help=("Run specific test (e.g., " "test_config.py::TestDatabaseConfig::test_defaults)"),
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean test artifacts and cache files",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check if dependencies are installed",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    success = True

    if args.clean:
        clean_test_artifacts()
        return

    if args.check_deps:
        if check_dependencies():
            print("✅ All dependencies are installed")
        else:
            print("❌ Some dependencies are missing")
            sys.exit(1)
        return

    if not check_dependencies():
        print("❌ Cannot run tests without required dependencies")
        sys.exit(1)

    if args.unit:
        success = run_unit_tests(args.verbose, args.test) and success
    elif args.security:
        success = run_security_tests(args.verbose) and success
    elif args.integration:
        success = run_integration_tests(args.verbose) and success
    elif args.file:
        success = run_specific_test_file(args.file, args.verbose) and success
    elif args.all:
        success = run_all_tests(args.verbose) and success
    elif args.test:
        success = run_unit_tests(args.verbose, args.test) and success
    else:
        success = run_unit_tests(args.verbose) and success

    if success:
        print("\n✅ All operations completed successfully!")
    else:
        print("\n❌ Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
