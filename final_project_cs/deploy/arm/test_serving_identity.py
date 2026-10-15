"""시험 계정 재사용과 인증 실패 시 신규 발급 금지 회귀."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch
os.environ.setdefault("DEPLOY_BASE", tempfile.gettempdir())
import serving_checks


class IdentityTests(unittest.TestCase):
    def test_reuses_existing_accounts_without_issuing_sessions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(serving_checks, "BASE", Path(tmp)):
            p = Path(tmp) / "probe_identity.json"
            p.write_text(json.dumps({"key": "owner-test", "other": "other-test"}))
            calls = []
            def check(name, path, **kwargs):
                calls.append((path, kwargs["key"]))
                return {"trips": []}
            for _ in range(3):
                self.assertEqual(serving_checks.test_identities(check)[:2], ("owner-test", "other-test"))
            self.assertEqual(calls, [("/v1/web/trips", "owner-test"), ("/v1/web/trips", "other-test")] * 3)

    def test_invalid_cached_identity_fails_without_new_account(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(serving_checks, "BASE", Path(tmp)):
            p = Path(tmp) / "probe_identity.json"
            p.write_text(json.dumps({"key": "expired", "other": "other"}))
            before = p.read_bytes()
            calls = []
            def check(name, path, **kwargs):
                calls.append(path)
                return {"error": {"code": "unauthenticated"}}
            with self.assertRaisesRegex(RuntimeError, "stored_test_identity_unavailable"):
                serving_checks.test_identities(check)
            self.assertEqual(calls, ["/v1/web/trips"])
            self.assertEqual(p.read_bytes(), before)

    def test_initial_pair_is_cached_for_next_round(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(serving_checks, "BASE", Path(tmp)):
            calls = []
            def check(name, path, payload=None, **kwargs):
                calls.append(path)
                return {"user_key": name} if payload == {} else {"trips": []}
            serving_checks.test_identities(check)
            serving_checks.test_identities(check)
            self.assertEqual(calls, ["/v1/web/session", "/v1/web/session", "/v1/web/trips", "/v1/web/trips"])


def fixture():
    return {"trip_id": "synthetic", "title": "ARM 서빙 시험용 서울 여행", "version": 1,
            "items": [{"seq": 1, "kind": "activity", "title": "경복궁 관람",
                       "starts_at": "2099-10-18T10:00:00+09:00", "ends_at": "2099-10-18T11:00:00+09:00"},
                      {"seq": 2, "kind": "dining", "title": "점심 식사",
                       "starts_at": "2099-10-18T12:00:00+09:00", "ends_at": "2099-10-18T13:00:00+09:00"}]}


class FixtureTests(unittest.TestCase):
    def test_guest_repeat_reuses_owned_fixture_without_create_or_delete(self):
        value = fixture()
        calls = []
        def check(name, path, payload=None, key=None, **kwargs):
            self.assertIsNone(payload)
            self.assertEqual(key, "owner")
            self.assertTrue(kwargs["validate"](value))
            calls.append((name, path))
            return deepcopy(value)
        for _ in range(3):
            trip, mode = serving_checks.prepare_test_trip(check, "owner", {"title": value["title"]},
                                                         [{"trip_id": "synthetic", "title": value["title"]}])
            self.assertEqual(trip, value)
            self.assertEqual(mode, "reused_same_synthetic_trip_with_history")
        self.assertEqual(calls, [("prepare_synthetic_trip", "/v1/web/trips/synthetic")] * 3)

    def test_unexpected_account_trip_is_never_read_or_modified(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected_test_account_trips"):
            serving_checks.prepare_test_trip(lambda *a, **k: self.fail("unexpected HTTP"), "owner",
                                             {"title": fixture()["title"]}, [{"trip_id": "customer", "title": "다른 여행"}])

    def test_changed_or_stale_fixture_is_rejected(self):
        changes = [lambda v: v.update(version=2),
                   lambda v: v["items"][1].update(starts_at="2099-10-18T10:00:00+09:00"),
                   lambda v: v["items"][0].update(title="다른 장소"),
                   lambda v: v["items"][1].update(ends_at="2099-10-19T13:00:00+09:00"),
                   lambda v: v["items"][0].update(starts_at="2000-10-18T10:00:00+09:00")]
        for change in changes:
            with self.subTest(change=change):
                value = fixture(); change(value)
                self.assertFalse(serving_checks.valid_test_fixture(value))

    def test_valid_fixture_has_expected_times_and_timezone(self):
        self.assertTrue(serving_checks.valid_test_fixture(fixture()))
        value = fixture(); value["items"][0]["starts_at"] = "2099-10-18T10:00:00"
        self.assertFalse(serving_checks.valid_test_fixture(value))

    def test_bad_fixture_stops_without_silently_creating_another(self):
        calls = []
        def check(name, path, **kwargs):
            calls.append(path)
            return {"error": {"code": "unauthenticated"}}
        with self.assertRaisesRegex(RuntimeError, "stored_test_fixture_changed_or_stale"):
            serving_checks.prepare_test_trip(check, "owner", {"title": fixture()["title"]},
                                             [{"trip_id": "synthetic", "title": fixture()["title"]}])
        self.assertEqual(calls, ["/v1/web/trips/synthetic"])


if __name__ == "__main__":
    unittest.main()
