"""
MySQL TLS integration tests.

These tests exercise the opt-in TLS support (ssl_enabled / ssl_ca_path) in
KonfluxDevLakeConnection against a real MySQL instance that enforces
`require_secure_transport=ON`, proving that:
  - a connection without TLS enabled is rejected by the server, and
  - a connection with a correct CA bundle succeeds with real certificate
    verification (no CERT_NONE / check_hostname=False shortcuts).

A dedicated, ephemeral MySQL container is started for this module (separate
from the docker-compose `mysql` service used by the rest of the integration
suite, which has no TLS enforcement). The container runtime is taken from
the CONTAINER_RUNTIME env var (set by `make test-integration-tls`'s
$(RUNTIME) so Make and pytest agree on the same tool), falling back to
detecting `docker` then `podman` on PATH for standalone `pytest` runs.
"""

import datetime
import ipaddress
import os
import shutil
import socket
import subprocess
import time

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from utils.db import KonfluxDevLakeConnection

CONTAINER_NAME = "devlake-mcp-test-mysql-tls"
ROOT_PASSWORD = "test_password"
DB_NAME = "lake"
DB_USER = "devlake"
DB_PASSWORD = "devlake_password"
COMMON_NAME = "127.0.0.1"


def _container_runtime():
    """Return the path to a usable container runtime CLI, or None.

    Honors CONTAINER_RUNTIME if set (e.g. by `make test-integration-tls`),
    otherwise detects docker/podman directly on PATH.
    """
    preferred = os.environ.get("CONTAINER_RUNTIME")
    if preferred:
        return shutil.which(preferred)
    return shutil.which("docker") or shutil.which("podman")


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _generate_self_signed_cert(cert_path, key_path):
    """Generate a self-signed cert/key pair usable as both server cert and CA."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, COMMON_NAME)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(COMMON_NAME))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o644)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert_path.chmod(0o644)


@pytest.fixture(scope="module")
def tls_certs(tmp_path_factory):
    """Self-signed cert/key pair, also usable as the client CA bundle."""
    certs_dir = tmp_path_factory.mktemp("mysql-tls-certs")
    cert_path = certs_dir / "server-cert.pem"
    key_path = certs_dir / "server-key.pem"
    _generate_self_signed_cert(cert_path, key_path)
    return {"dir": certs_dir, "cert": cert_path, "key": key_path}


@pytest.fixture(scope="module")
def tls_mysql_container(tls_certs):
    """Start a MySQL container that enforces require_secure_transport=ON."""
    runtime = _container_runtime()
    if runtime is None:
        pytest.skip("No container runtime (docker/podman) available on PATH")

    port = _free_tcp_port()
    subprocess.run([runtime, "rm", "-f", CONTAINER_NAME], capture_output=True, check=False)

    run_cmd = [
        runtime,
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"{port}:3306",
        "-e",
        f"MYSQL_ROOT_PASSWORD={ROOT_PASSWORD}",
        "-e",
        f"MYSQL_DATABASE={DB_NAME}",
        "-e",
        f"MYSQL_USER={DB_USER}",
        "-e",
        f"MYSQL_PASSWORD={DB_PASSWORD}",
        "-v",
        f"{tls_certs['dir']}:/certs:ro",
        "mysql:8.0",
        "--default-authentication-plugin=mysql_native_password",
        "--require_secure_transport=ON",
        "--ssl-ca=/certs/server-cert.pem",
        "--ssl-cert=/certs/server-cert.pem",
        "--ssl-key=/certs/server-key.pem",
    ]
    result = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.fail(f"Could not start TLS-enforcing MySQL container: {result.stderr}")

    try:
        _wait_for_container_ready(runtime)
        yield {"host": COMMON_NAME, "port": port}
    finally:
        subprocess.run([runtime, "rm", "-f", CONTAINER_NAME], capture_output=True, check=False)


def _wait_for_container_ready(runtime, max_retries=30, retry_delay=2):
    """Wait for MySQL to accept connections via the (TLS-exempt) local socket."""
    ping_cmd = [
        runtime,
        "exec",
        CONTAINER_NAME,
        "mysqladmin",
        "ping",
        "-h",
        "localhost",
        "-uroot",
        f"-p{ROOT_PASSWORD}",
    ]
    for _ in range(max_retries):
        result = subprocess.run(ping_cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return
        time.sleep(retry_delay)

    pytest.fail(f"TLS-enforcing MySQL container did not become ready after {max_retries} attempts")


@pytest.mark.integration
@pytest.mark.asyncio
class TestMySQLTLSIntegration:
    """Integration tests for opt-in TLS support against a TLS-enforcing server."""

    async def test_connection_without_tls_setting_fails(self, tls_mysql_container):
        """A server enforcing require_secure_transport must reject plain TCP."""
        connection = KonfluxDevLakeConnection(
            {
                "host": tls_mysql_container["host"],
                "port": tls_mysql_container["port"],
                "user": DB_USER,
                "password": DB_PASSWORD,
                "database": DB_NAME,
            }
        )

        result = await connection.connect()

        assert result["success"] is False
        await connection.close()

    async def test_connection_with_correct_ca_succeeds(self, tls_mysql_container, tls_certs):
        """A connection with the matching CA bundle must succeed over TLS."""
        connection = KonfluxDevLakeConnection(
            {
                "host": tls_mysql_container["host"],
                "port": tls_mysql_container["port"],
                "user": DB_USER,
                "password": DB_PASSWORD,
                "database": DB_NAME,
                "ssl_enabled": True,
                "ssl_ca_path": str(tls_certs["cert"]),
            }
        )

        result = await connection.connect()

        assert result["success"] is True
        assert "version" in result

        healthy = await connection.test_connection()
        assert healthy is True

        await connection.close()

    async def test_existing_non_tls_database_unaffected(self, integration_db_connection):
        """The default docker-compose MySQL (no TLS enforcement) must still
        work fine when ssl_enabled is left unset."""
        assert await integration_db_connection.test_connection() is True
