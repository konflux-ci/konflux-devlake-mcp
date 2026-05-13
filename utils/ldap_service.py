#!/usr/bin/env python3
"""
LDAP Service for Rover Group Lookups

Checks if users are members of the devlakemcpadmin Rover group
by querying the Red Hat IPA LDAP service.
"""

import os
import time
from typing import Dict, Optional, Set

from ldap3 import ALL, SIMPLE, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException

from utils.logger import get_logger

LDAP_SERVER = os.getenv("LDAP_SERVER_URL", "ldap:///dc%3Dipa%2Cdc%3Dredhat%2Cdc%3Dcom")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=ipa,dc=redhat,dc=com")
LDAP_USER_BASE_DN = os.getenv("LDAP_USER_BASE_DN", "cn=users,cn=accounts,dc=ipa,dc=redhat,dc=com")
LDAP_CACHE_TTL = int(os.getenv("LDAP_CACHE_TTL", "300"))
LDAP_ADMIN_GROUP = os.getenv("LDAP_ADMIN_GROUP", "devlakemcpadmin")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")


class LDAPGroupCache:
    """Simple TTL cache for LDAP group membership results."""

    def __init__(self, ttl_seconds: int = LDAP_CACHE_TTL):
        self._cache: Dict[str, tuple] = {}  # username -> (groups, timestamp)
        self._ttl = ttl_seconds

    def get(self, username: str) -> Optional[Set[str]]:
        """Get cached groups for a user, or None if expired/missing."""
        if username not in self._cache:
            return None

        groups, timestamp = self._cache[username]
        if time.time() - timestamp > self._ttl:
            del self._cache[username]
            return None

        return groups

    def set(self, username: str, groups: Set[str]) -> None:
        """Cache groups for a user."""
        self._cache[username] = (groups, time.time())

    def size(self) -> int:
        """Get the number of cached entries."""
        return len(self._cache)


class LDAPService:
    """Service for querying IPA LDAP for Rover group membership."""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.LDAPService")
        self.server_url = LDAP_SERVER
        self.base_dn = LDAP_BASE_DN
        self.user_base_dn = LDAP_USER_BASE_DN
        self.admin_group = LDAP_ADMIN_GROUP
        self.bind_dn = LDAP_BIND_DN
        self.bind_password = LDAP_BIND_PASSWORD
        self._cache = LDAPGroupCache(LDAP_CACHE_TTL)

        if not self.bind_dn or not self.bind_password:
            self.logger.warning(
                "LDAP_BIND_DN or LDAP_BIND_PASSWORD is not set. "
                "IPA LDAP requires a service account; group lookups will fail until "
                "credentials are configured."
            )

        self.logger.info(
            f"LDAP service initialized: server={self.server_url}, "
            f"user_base_dn={self.user_base_dn}, "
            f"admin_group={self.admin_group}, cache_ttl={LDAP_CACHE_TTL}s"
        )

    def get_user_groups(self, username: str) -> Set[str]:
        """Get Rover groups for a user from LDAP."""
        cached = self._cache.get(username)
        if cached is not None:
            self.logger.debug(f"LDAP cache hit for user '{username}': {len(cached)} groups")
            return cached

        groups = self._query_ldap_groups(username)
        self._cache.set(username, groups)

        return groups

    def _query_ldap_groups(self, username: str) -> Set[str]:
        """Query IPA LDAP for a user's group memberships using a service account bind."""
        groups = set()

        if not self.bind_dn or not self.bind_password:
            self.logger.error(
                f"Cannot query LDAP for '{username}': service account credentials not configured "
                "(set LDAP_BIND_DN and LDAP_BIND_PASSWORD)"
            )
            return groups

        try:
            server = Server(self.server_url, get_info=ALL)
            conn = Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                authentication=SIMPLE,
                auto_bind=True,
            )

            # Search in the specific user subtree.
            search_filter = f"(uid={username})"
            conn.search(
                search_base=self.user_base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["memberOf"],
            )

            if conn.entries:
                entry = conn.entries[0]
                for member_of in entry.memberOf.values if hasattr(entry, "memberOf") else []:
                    if member_of.startswith("cn="):
                        groups.add(member_of.split(",")[0][3:])

            conn.unbind()

            self.logger.info(f"LDAP query for '{username}': found {len(groups)} groups")
            if self.admin_group in groups:
                self.logger.info(f"User '{username}' is member of admin group '{self.admin_group}'")

        except LDAPException as e:
            self.logger.error(f"LDAP query failed for '{username}': {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during LDAP query for '{username}': {e}")

        return groups

    def is_admin(self, username: str) -> bool:
        """Check if a user is a member of the admin Rover group."""
        groups = self.get_user_groups(username)
        return self.admin_group in groups

    def get_cache_stats(self) -> Dict:
        """Get cache statistics for monitoring."""
        return {
            "server": self.server_url,
            "user_base_dn": self.user_base_dn,
            "admin_group": self.admin_group,
            "bind_dn_configured": bool(self.bind_dn),
            "cache_size": self._cache.size(),
            "cache_ttl": self._cache._ttl,
        }
