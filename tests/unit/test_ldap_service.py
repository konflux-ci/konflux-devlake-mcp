#!/usr/bin/env python3
"""Unit tests for IPA LDAP group lookups."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from unittest.mock import MagicMock, patch

import pytest

from utils.ldap_service import LDAPGroupCache, LDAPService


@pytest.mark.unit
class TestLDAPGroupCache:
    def test_missing_and_cached_values(self):
        cache = LDAPGroupCache(ttl_seconds=60)
        assert cache.get("alice") is None
        cache.set("alice", {"team-a"})
        assert cache.get("alice") == {"team-a"}
        assert cache.size() == 1

    def test_expired_value(self):
        cache = LDAPGroupCache(ttl_seconds=60)
        cache._cache["alice"] = ({"team-a"}, time.time() - 120)
        assert cache.get("alice") is None

    def test_concurrent_expired_reads_are_serialized(self):
        """Concurrent readers must not race while evicting an expired entry."""

        class PausingDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._count_lock = Lock()
                self._get_count = 0
                self.first_get_started = Event()
                self.release_first_get = Event()
                self.second_get_started = Event()

            def get(self, key, default=None):
                with self._count_lock:
                    self._get_count += 1
                    get_number = self._get_count

                if get_number == 1:
                    self.first_get_started.set()
                    assert self.release_first_get.wait(timeout=2)
                elif get_number == 2:
                    self.second_get_started.set()

                return super().get(key, default)

        cache = LDAPGroupCache(ttl_seconds=60)
        entries = PausingDict({"alice": ({"team-a"}, time.time() - 120)})
        cache._cache = entries
        second_reader_started = Event()

        def read_from_second_worker():
            second_reader_started.set()
            return cache.get("alice")

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_result = executor.submit(cache.get, "alice")
            assert entries.first_get_started.wait(timeout=2)
            second_result = executor.submit(read_from_second_worker)
            assert second_reader_started.wait(timeout=2)

            second_entered_before_release = entries.second_get_started.wait(timeout=0.1)
            entries.release_first_get.set()

            assert first_result.result(timeout=2) is None
            assert second_result.result(timeout=2) is None

        assert second_entered_before_release is False
        assert cache.size() == 0


@pytest.mark.unit
class TestLDAPService:
    @pytest.fixture
    def service(self):
        return LDAPService(
            {
                "server_url": "ldaps://ldap.example.test",
                "base_dn": "dc=example,dc=test",
                "user_base_dn": "ou=users,dc=example,dc=test",
                "cache_ttl": 300,
                "admin_group": "devlakemcpadmin",
                "bind_dn": "cn=svc,dc=example,dc=test",
                "bind_password": "secret",
            }
        )

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_group_lookup_escapes_username_and_extracts_groups(
        self, mock_server, mock_connection, service
    ):
        entry = MagicMock()
        entry.memberOf.values = [
            "cn=devlakemcpadmin,cn=groups,dc=example,dc=test",
            "cn=team-a,cn=groups,dc=example,dc=test",
        ]
        connection = MagicMock()
        connection.entries = [entry]
        mock_connection.return_value = connection

        groups = service.get_user_groups("alice*)(uid=*")

        assert groups == {"devlakemcpadmin", "team-a"}
        search_filter = connection.search.call_args.kwargs["search_filter"]
        assert search_filter == r"(uid=alice\2a\29\28uid=\2a)"
        connection.unbind.assert_called_once()

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_ldap_failure_returns_no_groups_with_exception_context(
        self, mock_server, mock_connection, service, caplog
    ):
        mock_connection.side_effect = RuntimeError("connection failed")

        with caplog.at_level("ERROR"):
            assert service.get_user_groups("alice") == set()

        assert service.is_admin("alice") is False
        error_record = next(
            record
            for record in caplog.records
            if "Unexpected LDAP error for 'alice'" in record.getMessage()
        )
        assert error_record.exc_info is not None
        assert error_record.exc_info[0] is RuntimeError
        assert "_query_ldap_groups" in caplog.text
        assert "connection failed" in caplog.text
        assert service.bind_password not in caplog.text

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_no_matching_entry_warns(self, mock_server, mock_connection, service, caplog):
        connection = MagicMock()
        connection.entries = []
        mock_connection.return_value = connection

        with caplog.at_level("WARNING"):
            groups = service.get_user_groups("nosuchuser")

        assert groups == set()
        assert "matched no entry for uid 'nosuchuser'" in caplog.text

    def test_concurrent_lookup_cannot_overwrite_successful_admin_result(self, service):
        """Only one cache-miss lookup may run for a user at a time."""
        query_count = 0
        query_count_lock = Lock()
        first_query_started = Event()
        release_first_query = Event()
        second_query_started = Event()
        release_second_query = Event()
        second_worker_started = Event()

        def query_groups(username):
            nonlocal query_count
            assert username == "alice"
            with query_count_lock:
                query_count += 1
                query_number = query_count

            if query_number == 1:
                first_query_started.set()
                assert release_first_query.wait(timeout=2)
                return {"devlakemcpadmin"}

            second_query_started.set()
            assert release_second_query.wait(timeout=2)
            return set()

        def lookup_from_second_worker():
            second_worker_started.set()
            return service.get_user_groups("alice")

        with patch.object(service, "_query_ldap_groups", side_effect=query_groups):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first_result = executor.submit(service.get_user_groups, "alice")
                assert first_query_started.wait(timeout=2)
                second_result = executor.submit(lookup_from_second_worker)
                assert second_worker_started.wait(timeout=2)

                duplicate_query_started = second_query_started.wait(timeout=0.1)
                release_first_query.set()
                assert first_result.result(timeout=2) == {"devlakemcpadmin"}
                release_second_query.set()
                assert second_result.result(timeout=2) == {"devlakemcpadmin"}

        assert duplicate_query_started is False
        assert query_count == 1
        assert service.get_user_groups("alice") == {"devlakemcpadmin"}

    @patch("utils.ldap_service.Server")
    def test_single_server_url_builds_plain_server(self, mock_server, service):
        assert service._build_server() is mock_server.return_value
        assert mock_server.call_args.args[0] == "ldaps://ldap.example.test"

    @patch("utils.ldap_service.ServerPool")
    @patch("utils.ldap_service.Server")
    def test_comma_separated_urls_build_pool(self, mock_server, mock_pool, service):
        service.server_url = "ldaps://a.example.test, ldaps://b.example.test"

        assert service._build_server() is mock_pool.return_value
        assert [call.args[0] for call in mock_server.call_args_list] == [
            "ldaps://a.example.test",
            "ldaps://b.example.test",
        ]

    def test_pool_is_built_from_real_ldap3_objects(self, service):
        """Guard the split against ldap3 itself: a joined URL string is rejected
        by Server(), so the pool must be built from one URL per Server."""
        ldap3 = pytest.importorskip("ldap3")
        service.server_url = "ldaps://a.example.test,ldap://b.example.test:1389"

        pool = service._build_server()

        assert isinstance(pool, ldap3.ServerPool)
        assert [(s.host, s.port, s.ssl) for s in pool.servers] == [
            ("a.example.test", 636, True),
            ("b.example.test", 1389, False),
        ]

    def test_admin_membership_is_case_insensitive(self, service):
        service._cache.set("alice", {"DEVLAKEMCPADMIN"})
        assert service.is_admin("alice") is True

    def test_cache_stats_do_not_expose_password(self, service):
        stats = service.get_cache_stats()
        assert stats["bind_dn_configured"] is True
        assert "bind_password" not in stats
