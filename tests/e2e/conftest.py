import os
import asyncio
import pytest
import socket
import time
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

os.environ.setdefault("LITELLM_LOGGING", "False")
os.environ.setdefault("LITELLM_VERBOSE", "0")
os.environ.setdefault("LITELLM_DISABLE_LOGGING", "1")
os.environ.setdefault("LITELLM_LOGGING_QUEUE", "0")


def _present_models_from_env():
    present = []
    if os.environ.get("GEMINI_API_KEY"):
        present.append("gemini/gemini-2.5-pro")
    return present


def _has_api_key_for_model(model_name):
    name = model_name.lower()
    if "gemini" in name:
        return bool(os.environ.get("GEMINI_API_KEY"))
    return False


_requested_env = os.environ.get("E2E_TEST_MODELS", "").strip()
if _requested_env:
    requested_models = [m.strip() for m in _requested_env.split(",") if m.strip()]
    models = [m for m in requested_models if _has_api_key_for_model(m)]
    if not models:
        pytest.exit(
            "E2E_TEST_MODELS is set but no matching API keys found. "
            "Set the appropriate key or unset E2E_TEST_MODELS for auto-selection."
        )
else:
    present = _present_models_from_env()
    if not present:
        pytest.exit("No LLM API keys found. Set GEMINI_API_KEY to run E2E tests.")
    models = present

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def e2e_log_file():
    import datetime

    base_dir = os.path.abspath(os.environ.get("E2E_LOG_DIR", os.path.join(os.getcwd(), "e2e_logs")))
    os.makedirs(base_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(base_dir, f"e2e-run-{ts}.md")
    os.environ["E2E_LOG_MD_PATH"] = path
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("# E2E Test Run\n\n")
        fh.write(f"Generated: {ts}\n\n")
    return path


@pytest.fixture(autouse=True)
def e2e_test_name(request, e2e_log_file):
    os.environ["E2E_TEST_NAME"] = request.node.nodeid
    yield
    os.environ.pop("E2E_TEST_NAME", None)


@pytest.fixture(autouse=True)
def _reset_litellm_logging_between_tests():
    try:
        import litellm  # type: ignore

        try:
            litellm.callbacks = []
        except Exception:
            pass
        try:
            litellm.success_callback = []
            litellm.failure_callback = []
        except Exception:
            pass
        try:
            from litellm.litellm_core_utils import logging_worker  # type: ignore

            try:
                if hasattr(logging_worker, "shutdown"):
                    logging_worker.shutdown()
            except Exception:
                pass
            for name in ("_queue", "_QUEUE", "_worker", "_WORKER"):
                try:
                    if hasattr(logging_worker, name):
                        setattr(logging_worker, name, None)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass
    yield
    # best-effort shutdown again after test
    try:
        from litellm.litellm_core_utils import logging_worker  # type: ignore

        if hasattr(logging_worker, "shutdown"):
            logging_worker.shutdown()
        for name in ("_queue", "_QUEUE", "_worker", "_WORKER"):
            try:
                if hasattr(logging_worker, name):
                    setattr(logging_worker, name, None)
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture
def db_env():
    host = os.environ.get("TEST_DB_HOST", os.environ.get("DB_HOST", "localhost"))
    port = os.environ.get("TEST_DB_PORT", os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("TEST_DB_USER", os.environ.get("DB_USER", "devlake"))
    password = os.environ.get("TEST_DB_PASSWORD", os.environ.get("DB_PASSWORD", "devlake_password"))
    database = os.environ.get("TEST_DB_NAME", os.environ.get("DB_DATABASE", "lake"))

    return {
        "DB_HOST": host,
        "DB_PORT": str(port),
        "DB_USER": user,
        "DB_PASSWORD": password,
        "DB_DATABASE": database,
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "ERROR"),
    }


@pytest.fixture
async def mcp_client(db_env):
    host = db_env["DB_HOST"]
    port = int(db_env["DB_PORT"])
    deadline = time.time() + float(os.environ.get("E2E_DB_WAIT_SECS", "20"))
    last_err = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                break
        except Exception as e:
            last_err = e
            time.sleep(1)
    else:
        pytest.skip(f"MySQL not reachable at {host}:{port} ({last_err})")

    server_path = os.environ.get("MCP_SERVER_PATH", "python konflux-devlake-mcp.py")
    if " " in server_path:
        parts = server_path.split()
        command = parts[0]
        args = parts[1:] + [
            "--transport",
            "stdio",
            "--log-level",
            os.environ.get("LOG_LEVEL", "ERROR"),
            "--db-host",
            db_env["DB_HOST"],
            "--db-port",
            db_env["DB_PORT"],
            "--db-user",
            db_env["DB_USER"],
            "--db-password",
            db_env["DB_PASSWORD"],
            "--db-database",
            db_env["DB_DATABASE"],
        ]
    else:
        command = server_path
        args = [
            "--transport",
            "stdio",
            "--log-level",
            os.environ.get("LOG_LEVEL", "ERROR"),
            "--db-host",
            db_env["DB_HOST"],
            "--db-port",
            db_env["DB_PORT"],
            "--db-user",
            db_env["DB_USER"],
            "--db-password",
            db_env["DB_PASSWORD"],
            "--db-database",
            db_env["DB_DATABASE"],
        ]

    env = dict(db_env)
    env["MCP_STDIO"] = "true"
    params = StdioServerParameters(command=command, args=args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            try:
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=float(os.environ.get("E2E_INIT_TIMEOUT", "20")),
                )
            except Exception as e:
                pytest.skip(f"MCP server did not initialize in time: {e}")
            yield session
