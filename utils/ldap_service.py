#!/usr/bin/env python3
"""
LDAP Service for Rover Group Lookups

Checks if users are members of the devlakemcpadmin Rover group
by querying ldap.corp.redhat.com.
"""

import time
from typing import Dict, Optional, Set

from ldap3 import Connection, Server, SUBTREE, ALL
from ldap3.core.exceptions import LDAPException

from utils.logger import get_logger

LDAP_SERVER = "ldaps://ldap.corp.redhat.com"
LDAP_BASE_DN = "dc=redhat,dc=com"
LDAP_CACHE_TTL = 300
LDAP_ADMIN_GROUP = "devlakemcpadmin"


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
    """Service for querying LDAP for Rover group membership."""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.LDAPService")
        self.server_url = LDAP_SERVER
        self.base_dn = LDAP_BASE_DN
        self.admin_group = LDAP_ADMIN_GROUP
        self._cache = LDAPGroupCache(LDAP_CACHE_TTL)
        self.logger.info(
            f"LDAP service initialized: server={self.server_url}, "
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
        """Query LDAP for a user's group memberships."""
        groups = set()

        try:
            # Create LDAP connection (anonymous bind for read-only queries)
            server = Server(self.server_url, get_info=ALL)
            conn = Connection(server, auto_bind=True)

            # Search for the user
            search_filter = f"(uid={username})"
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["memberOf"],
            )

            if conn.entries:
                entry = conn.entries[0]
                # Extract group names from memberOf DNs
                # Format: cn=groupname,ou=adhoc,ou=managedGroups,dc=redhat,dc=com
                for member_of in entry.memberOf.values if hasattr(entry, "memberOf") else []:
                    # Extract CN (group name) from the DN
                    if member_of.startswith("cn="):
                        group_name = member_of.split(",")[0][3:]  # Remove "cn=" prefix
                        groups.add(group_name)

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
            "admin_group": self.admin_group,
            "cache_size": self._cache.size(),
            "cache_ttl": self._cache._ttl,
        }
