#!/usr/bin/env python3
import time
import pytest
from unittest.mock import patch, MagicMock

from utils.ldap_service import LDAPGroupCache, LDAPService


@pytest.mark.unit
class TestLDAPGroupCache:
    @pytest.fixture
    def cache(self):
        return LDAPGroupCache(ttl_seconds=60)

    def test_get_missing(self, cache):
        assert cache.get("nobody") is None

    def test_set_and_get(self, cache):
        cache.set("alice", {"group1", "group2"})
        result = cache.get("alice")
        assert result == {"group1", "group2"}

    def test_get_expired(self, cache):
        cache.set("alice", {"group1"})
        cache._cache["alice"] = ({"group1"}, time.time() - 120)
        assert cache.get("alice") is None

    def test_size(self, cache):
        assert cache.size() == 0
        cache.set("alice", {"g1"})
        cache.set("bob", {"g2"})
        assert cache.size() == 2


@pytest.mark.unit
class TestLDAPService:
    @pytest.fixture
    def service(self):
        with patch.dict(
            "os.environ",
            {
                "LDAP_BIND_DN": "cn=svc,dc=test",
                "LDAP_BIND_PASSWORD": "secret",
                "LDAP_ADMIN_GROUP": "devlakemcpadmin",
            },
        ):
            svc = LDAPService()
            svc.bind_dn = "cn=svc,dc=test"
            svc.bind_password = "secret"
            return svc

    def test_get_user_groups_cached(self, service):
        service._cache.set("alice", {"devlakemcpadmin", "team-a"})
        result = service.get_user_groups("alice")
        assert result == {"devlakemcpadmin", "team-a"}

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_get_user_groups_from_ldap(self, mock_server_cls, mock_conn_cls, service):
        mock_entry = MagicMock()
        mock_entry.memberOf.values = [
            "cn=devlakemcpadmin,cn=groups,dc=test",
            "cn=team-a,cn=groups,dc=test",
        ]
        mock_conn = MagicMock()
        mock_conn.entries = [mock_entry]
        mock_conn_cls.return_value = mock_conn

        result = service.get_user_groups("bob")
        assert "devlakemcpadmin" in result
        assert "team-a" in result
        mock_conn.unbind.assert_called_once()

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_get_user_groups_no_entries(self, mock_server_cls, mock_conn_cls, service):
        mock_conn = MagicMock()
        mock_conn.entries = []
        mock_conn_cls.return_value = mock_conn

        result = service.get_user_groups("unknown")
        assert result == set()

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_query_ldap_groups_ldap_exception(self, mock_server_cls, mock_conn_cls, service):
        from ldap3.core.exceptions import LDAPException

        mock_conn_cls.side_effect = LDAPException("connection failed")
        result = service._query_ldap_groups("alice")
        assert result == set()

    @patch("utils.ldap_service.Connection")
    @patch("utils.ldap_service.Server")
    def test_query_ldap_groups_unexpected_exception(self, mock_server_cls, mock_conn_cls, service):
        mock_conn_cls.side_effect = RuntimeError("unexpected")
        result = service._query_ldap_groups("alice")
        assert result == set()

    def test_is_admin_true(self, service):
        service._cache.set("alice", {"devlakemcpadmin", "team-a"})
        assert service.is_admin("alice") is True

    def test_is_admin_false(self, service):
        service._cache.set("bob", {"team-b"})
        assert service.is_admin("bob") is False

    def test_get_cache_stats(self, service):
        stats = service.get_cache_stats()
        assert stats["admin_group"] == "devlakemcpadmin"
        assert stats["bind_dn_configured"] is True
        assert stats["cache_size"] == 0
        assert "cache_ttl" in stats

    def test_init_no_bind_credentials(self):
        with patch.dict(
            "os.environ",
            {"LDAP_BIND_DN": "", "LDAP_BIND_PASSWORD": ""},
            clear=False,
        ):
            svc = LDAPService()
            svc.bind_dn = ""
            svc.bind_password = ""
            stats = svc.get_cache_stats()
            assert stats["bind_dn_configured"] is False
