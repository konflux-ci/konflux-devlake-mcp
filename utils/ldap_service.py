#!/usr/bin/env python3
"""IPA LDAP service for Rover group membership lookups."""

import time
from threading import Lock
from typing import Dict, Optional, Set

from utils.config import KonfluxDevLakeConfig
from utils.logger import get_logger

try:
    from ldap3 import ALL, ROUND_ROBIN, SIMPLE, SUBTREE, Connection, Server, ServerPool
    from ldap3.core.exceptions import LDAPException
    from ldap3.utils.conv import escape_filter_chars
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    ALL = SIMPLE = SUBTREE = ROUND_ROBIN = None
    Connection = Server = ServerPool = None

    class LDAPException(Exception):
        """Fallback exception when ldap3 is not installed."""

    def escape_filter_chars(value: str) -> str:
        """Fallback LDAP escaping implementation."""
        return (
            value.replace("\\", "\\5c")
            .replace("*", "\\2a")
            .replace("(", "\\28")
            .replace(")", "\\29")
            .replace("\x00", "\\00")
        )


# Seconds an unreachable replica stays benched before the pool retries it.
LDAP_POOL_EXHAUST_SECONDS = 60
LDAP_LOOKUP_LOCK_STRIPES = 64


class LDAPGroupCache:
    """Simple TTL cache for LDAP group membership results."""

    def __init__(self, ttl_seconds: int):
        self._cache: Dict[str, tuple[Set[str], float]] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, username: str) -> Optional[Set[str]]:
        """Return cached groups, or None when missing or expired."""
        with self._lock:
            cached = self._cache.get(username)
            if cached is None:
                return None

            groups, timestamp = cached
            if time.time() - timestamp > self._ttl:
                self._cache.pop(username, None)
                return None
            return set(groups)

    def set(self, username: str, groups: Set[str]) -> None:
        """Cache groups for a username."""
        with self._lock:
            self._cache[username] = (set(groups), time.time())

    def size(self) -> int:
        """Return the number of cached users."""
        with self._lock:
            return len(self._cache)


class LDAPService:
    """Query IPA LDAP for Rover group membership."""

    def __init__(self, config: Optional[Dict[str, object]] = None):
        self.logger = get_logger(f"{__name__}.LDAPService")

        # utils.config owns every LDAP default and all environment parsing; an
        # explicit config mapping overrides those values key by key.
        settings: Dict[str, object] = KonfluxDevLakeConfig().get_ldap_config()
        settings.update(config or {})

        self.server_url = str(settings["server_url"])
        self.base_dn = str(settings["base_dn"])
        self.user_base_dn = str(settings["user_base_dn"])
        self.admin_group = str(settings["admin_group"])
        self.bind_dn = str(settings["bind_dn"])
        self.bind_password = str(settings["bind_password"])
        self._cache = LDAPGroupCache(int(settings["cache_ttl"]))
        # A bounded set of locks prevents duplicate concurrent lookups for the
        # same user without retaining one lock for every username ever seen.
        self._lookup_locks = tuple(Lock() for _ in range(LDAP_LOOKUP_LOCK_STRIPES))

        if not self.bind_dn or not self.bind_password:
            self.logger.warning(
                "LDAP service-account credentials are not configured; "
                "group lookups cannot grant admin access"
            )

    def _build_server(self):
        """Build a Server, or a ServerPool when several replicas are configured.

        LDAP_SERVER_URL accepts a single URL or a comma-separated list; IPA is
        replicated, so a list lets a lookup fail over instead of failing closed.
        """
        hosts = [host.strip() for host in self.server_url.split(",") if host.strip()]
        if len(hosts) <= 1:
            return Server(hosts[0] if hosts else self.server_url, get_info=ALL)

        return ServerPool(
            [Server(host, get_info=ALL) for host in hosts],
            ROUND_ROBIN,
            active=len(hosts),
            exhaust=LDAP_POOL_EXHAUST_SECONDS,
        )

    def get_user_groups(self, username: str) -> Set[str]:
        """Return groups for a username, using a short-lived cache."""
        cached = self._cache.get(username)
        if cached is not None:
            return cached

        lookup_lock = self._lookup_locks[hash(username) % len(self._lookup_locks)]
        with lookup_lock:
            # Another worker may have populated the cache while this worker
            # waited for the same user's lookup lock.
            cached = self._cache.get(username)
            if cached is not None:
                return cached

            groups = self._query_ldap_groups(username)
            self._cache.set(username, groups)
            return groups

    def _query_ldap_groups(self, username: str) -> Set[str]:
        """Query IPA LDAP using the configured service account."""
        if not self.bind_dn or not self.bind_password:
            self.logger.error("LDAP service-account credentials are not configured")
            return set()

        if Connection is None or Server is None:
            self.logger.error("ldap3 is not installed; LDAP lookup unavailable")
            return set()

        groups: Set[str] = set()
        conn = None
        try:
            server = self._build_server()
            conn = Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                authentication=SIMPLE,
                auto_bind=True,
            )
            search_filter = f"(uid={escape_filter_chars(username)})"
            conn.search(
                search_base=self.user_base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["memberOf"],
            )

            if conn.entries:
                entry = conn.entries[0]
                for member_of in getattr(entry, "memberOf", []).values:
                    if isinstance(member_of, str) and member_of.lower().startswith("cn="):
                        groups.add(member_of.split(",", 1)[0][3:])
            else:
                self.logger.warning(
                    "LDAP search matched no entry for uid '%s' under %s; "
                    "treating the user as having no groups (admin access denied)",
                    username,
                    self.user_base_dn,
                )
        except LDAPException as exc:
            self.logger.error("LDAP query failed for '%s': %s", username, exc, exc_info=True)
        except Exception as exc:
            self.logger.error("Unexpected LDAP error for '%s': %s", username, exc, exc_info=True)
        finally:
            if conn is not None:
                try:
                    conn.unbind()
                except Exception:
                    self.logger.debug("LDAP connection cleanup failed", exc_info=True)

        return groups

    def is_admin(self, username: str) -> bool:
        """Return whether the user belongs to the configured admin group."""
        return self.admin_group.lower() in {
            group.lower() for group in self.get_user_groups(username)
        }

    def get_cache_stats(self) -> Dict[str, object]:
        """Return non-sensitive LDAP cache configuration details."""
        return {
            "server": self.server_url,
            "user_base_dn": self.user_base_dn,
            "admin_group": self.admin_group,
            "bind_dn_configured": bool(self.bind_dn),
            "cache_size": self._cache.size(),
            "cache_ttl": self._cache._ttl,
        }
