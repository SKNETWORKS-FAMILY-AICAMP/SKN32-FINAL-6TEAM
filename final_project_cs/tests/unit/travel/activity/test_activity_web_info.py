# -*- coding: utf-8 -*-
"""웹 검색 장소 정보의 계약 · 검증(`web_info`) · 저장 SQL(`web_info_store`) — LLM · 실제 DB 없이 본다. `[2026-10-19]`

★핵심: ① 이미 채워진 칸은 웹 검색하지 않는다 ② 모델이 지어낸 값(검색하지 않은 URL · 인용에 없는 숫자 · 인용 없음)은 버린다
  ③ 원장 값이 먼저, 비었을 때만 웹 값(만료 전) ④ 소개글 · 체험 안내는 다루지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import web_info as wi
from app.domains.travel_ops.instances.activity.db_search import web_info_store as store

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
URL = "https://www.example.go.kr/info?id=1"


def _item(value, quote=None, url=URL, published="2026-10-01"):
    return {"value": value, "quote": quote if quote is not None else value, "url": url, "published_at": published}


def _check(output, wanted=("business_hours", "closed_days", "address"), sources=(URL,), max_age=3650):
    return wi.validate(output, wanted=wanted, sources=sources, now=NOW, max_age_days=max_age)


# ── 어떤 칸을 웹으로 채우나 ──────────────────────────────────────

def test_fields_exclude_overview_experience_guide_and_ids():
    assert "overview" not in wi.FIELDS and "experience_guide" not in wi.FIELDS
    assert not {"content_id", "lcls1", "lat", "lng"} & set(wi.FIELDS)


def test_filled_ledger_columns_are_skipped_and_empty_ones_are_asked():
    ledger = {"usetime_text": "09:00~18:00", "restdate_text": "", "reservation_text": None, "addr1": "서울특별시 종로구 1"}
    assert wi.missing_fields(ledger, None, NOW, wanted=("address", "business_hours", "closed_days", "reservation_info")) \
        == ["closed_days", "reservation_info"]


def test_a_place_not_in_the_ledger_asks_for_everything_wanted():
    assert wi.missing_fields(None, None, NOW) == list(wi.FIELDS)


def test_unexpired_web_values_are_not_asked_again_but_expired_ones_are():
    fresh = wi.Entry("business_hours", "09:00~18:00", "web", "q", URL, None, NOW + timedelta(days=5))
    old = wi.Entry("closed_days", "월요일", "web", "q", URL, None, NOW - timedelta(days=1))
    assert wi.missing_fields({}, {"business_hours": fresh, "closed_days": old}, NOW,
                             wanted=("business_hours", "closed_days")) == ["closed_days"]


def test_columns_without_a_ledger_counterpart_are_always_asked_when_no_web_value():
    assert "homepage" in wi.missing_fields({"addr1": "x"}, None, NOW) and "pet" in wi.missing_fields({}, None, NOW)


# ── 쓸 값 — 원장 먼저, 비었을 때만 웹 ────────────────────────────

def test_ledger_value_wins_over_the_web_value():
    web = wi.Entry("business_hours", "10:00~20:00", "web", "q", URL, None, NOW + timedelta(days=5))
    assert wi.effective("business_hours", "09:00~18:00", web, NOW) == ("09:00~18:00", "ledger")


def test_web_value_fills_only_an_empty_ledger_value_and_only_before_it_expires():
    fresh = wi.Entry("business_hours", "10:00~20:00", "web", "q", URL, None, NOW + timedelta(days=5))
    stale = wi.Entry("business_hours", "10:00~20:00", "web", "q", URL, None, NOW - timedelta(seconds=1))
    assert wi.effective("business_hours", "  ", fresh, NOW) == ("10:00~20:00", "web")
    assert wi.effective("business_hours", None, stale, NOW) == (None, None)
    assert wi.effective("business_hours", None, None, NOW) == (None, None)


# ── 모델 입력 · 출력 ─────────────────────────────────────────────

def test_schema_is_strict_with_nullable_items_and_payload_has_no_kakao_data():
    schema = wi.schema(("business_hours", "address"))
    assert schema["additionalProperties"] is False and schema["required"] == ["business_hours", "address"]
    assert "null" in schema["properties"]["address"]["type"]
    body = wi.payload("OO 카페", ["business_hours"], address=None, today=NOW.date())
    assert body == {"kind": "place_info", "place_name": "OO 카페", "address": None, "fields": ["business_hours"], "today": "2026-10-19"}


# ── 검증 ────────────────────────────────────────────────────────

def test_a_good_answer_passes_with_ttl_and_evidence():
    entries, dropped = _check({"business_hours": _item("09:00~18:00", "운영시간 09:00~18:00 (월요일 휴관)"),
                               "closed_days": None, "address": _item("서울특별시 종로구 사직로 161", "주소: 서울특별시 종로구 사직로 161")})
    assert dropped == [] and [e.field for e in entries] == ["business_hours", "address"]
    hours = entries[0]
    assert hours.source == "web" and hours.url == URL and hours.expires_at == NOW + timedelta(days=30)


def test_null_means_unknown_and_is_not_an_error():
    assert _check({"business_hours": None, "closed_days": None, "address": None}) == ([], [])


@pytest.mark.parametrize("item, reason", [
    (_item("09:00~18:00", quote=""), "business_hours:missing_evidence"),
    (_item("09:00~18:00", url=""), "business_hours:missing_evidence"),
    (_item("", quote="x"), "business_hours:missing_evidence"),
    (_item("09:00~18:00", url="https://other.example/page"), "business_hours:url_not_in_sources"),     # 검색하지 않은 페이지
    (_item("09:00~21:00", quote="운영시간 09:00~18:00"), "business_hours:value_not_in_quote"),          # 인용에 없는 숫자
    (_item("09:00~18:00", published="2010-01-01"), None),
    ("not a dict", "business_hours:not_object"),
])
def test_invented_or_unsupported_values_are_dropped(item, reason):
    entries, dropped = _check({"business_hours": item}, wanted=("business_hours",), max_age=365)
    assert entries == [] and (reason is None or reason in dropped) and dropped


def test_stale_citations_are_dropped_but_undated_ones_are_kept():
    _, dropped = _check({"business_hours": _item("09:00~18:00", published="2020-01-01")}, wanted=("business_hours",), max_age=365)
    assert dropped == ["business_hours:stale"]
    entries, dropped = _check({"business_hours": _item("09:00~18:00", published=None)}, wanted=("business_hours",), max_age=365)
    assert dropped == [] and entries[0].published_at is None


def test_url_match_ignores_www_utm_and_trailing_slash():
    entries, _ = _check({"business_hours": _item("09:00~18:00", url="https://example.go.kr/info/?id=1&utm_source=x")},
                        wanted=("business_hours",), sources=("https://www.example.go.kr/info?id=1",))
    assert len(entries) == 1


def test_value_must_appear_verbatim_in_the_quote_even_when_the_numbers_match():
    """숫자(9 = 09)가 맞아도 값이 인용 안에 **글자 그대로** 없으면 버린다 — 모델이 문장을 새로 쓰지 못하게."""
    entries, dropped = _check({"business_hours": _item("9시~18시", "09:00~18:00 운영")}, wanted=("business_hours",))
    assert entries == [] and dropped == ["business_hours:value_not_verbatim"]


def test_operating_hours_pass_when_the_quote_contains_the_value_as_written():
    entries, dropped = _check({"business_hours": _item("09:00~18:00", "관람시간 09:00~18:00 (입장마감 17:30)")}, wanted=("business_hours",))
    assert dropped == [] and [e.field for e in entries] == ["business_hours"]
    entries, dropped = _check({"business_hours": _item("오전 9시~오후 6시", "운영시간 09:00~18:00")}, wanted=("business_hours",))
    assert entries == [] and dropped                                       # 새로 쓴 문장 — 원문 그대로가 아니다


def test_address_must_be_in_seoul_homepage_a_url_and_tel_long_enough():
    _, dropped = _check({"address": _item("부산광역시 중구 1", "부산광역시 중구 1")}, wanted=("address",))
    assert dropped == ["address:out_of_area"]
    _, dropped = _check({"homepage": _item("example.go.kr", "example.go.kr")}, wanted=("homepage",))
    assert dropped == ["homepage:not_url"]
    _, dropped = _check({"tel": _item("02-12", "02-12")}, wanted=("tel",))
    assert dropped == ["tel:too_short"]


def test_fields_nobody_asked_for_are_ignored_even_if_the_model_adds_them():
    entries, _ = _check({"business_hours": _item("09:00~18:00"), "overview": _item("멋진 곳입니다", "멋진 곳입니다")},
                        wanted=("business_hours",))
    assert [e.field for e in entries] == ["business_hours"]


def test_non_dict_output_is_rejected():
    assert wi.validate(None, wanted=("business_hours",), sources=(), now=NOW, max_age_days=10) == ([], ["output:not_object"])


# ── 장소 키 ─────────────────────────────────────────────────────

def test_place_key_is_the_content_id_or_a_normalized_customer_name():
    assert wi.place_key("126535", "남산타워") == "126535"
    assert wi.place_key(None, "OO 카페 (본점)") == "web:oo카페"
    assert wi.place_key(None, "  ") is None


# ── 저장 SQL(가짜 커서) ──────────────────────────────────────────

class _Cur:
    def __init__(self, exists=True, rows=()):
        self.exists, self.rows, self.sql, self.many = exists, list(rows), [], []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))

    def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))

    def fetchone(self):
        return (self.exists,)

    def fetchall(self):
        return self.rows


def test_save_upserts_one_row_per_entry_with_evidence_and_model():
    cur = _Cur()
    entry = wi.Entry("business_hours", "09:00~18:00", "web", "운영시간 09:00~18:00", URL, None, NOW + timedelta(days=30))
    assert store.save_entries(cur, "126535", [entry], model="gpt-x", now=NOW) is True
    sql, rows = cur.many[0]
    assert sql == store.UPSERT_SQL and rows[0]["place_key"] == "126535" and rows[0]["model"] == "gpt-x"
    assert rows[0]["quote"] and rows[0]["url"] == URL and rows[0]["checked_at"] == NOW


def test_save_without_the_table_writes_nothing_and_says_so():
    cur = _Cur(exists=False)
    entry = wi.Entry("fee", "3,000원", "web", "3,000원", URL, None, NOW + timedelta(days=1))
    assert store.save_entries(cur, "1", [entry], model=None, now=NOW) is False and cur.many == []


def test_save_nothing_is_a_no_op_that_succeeds():
    cur = _Cur()
    assert store.save_entries(cur, "1", [], model=None, now=NOW) is True and cur.sql == [] and cur.many == []


def test_read_groups_entries_by_place_and_field_and_returns_empty_without_the_table():
    row = ("126535", "business_hours", "09:00~18:00", "web", "q", URL, None, NOW)
    assert store.read_entries(_Cur(rows=[row]), ["126535", ""])["126535"]["business_hours"].value == "09:00~18:00"
    assert store.read_entries(_Cur(exists=False), ["126535"]) == {}
    assert store.read_entries(_Cur(), []) == {}
