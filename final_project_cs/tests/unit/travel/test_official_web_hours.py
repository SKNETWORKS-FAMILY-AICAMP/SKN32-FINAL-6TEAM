# -*- coding: utf-8 -*-
"""사람이 공식 페이지에서 확인한 운영시간(`official_web`) — 새벽 작업은 관광공사 응답이 채워진 칸만 바꾸고,
화면 출처 표시는 그 값을 「ⓒ한국관광공사」로 말하지 않는다. DB 없이 본다.

`[2026-10-12 사용자]` `wiki/teams/db_column.md` 30번 `field_sources` · `wiki/external/rest-endpoints.md` 장소 정보.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.domains.travel_ops.components.places import catalog_hours as ch
from app.domains.travel_ops.components.places.place_info import official_web_note

SRC = {"by": "human", "url": "https://www.example.go.kr/info", "checked": "2026-10-12"}
KST = timezone(timedelta(hours=9))
NIGHT = datetime(2030, 1, 1, 3, 30, tzinfo=KST)
HUMAN_READ = {"source": "official_web", "method": "csv_rule", "field_sources": {"closed_days": SRC}}
HUMAN_ORIGIN = {"usetime": "09:00~18:00", "restdate": "매주 화요일"}


# ── 합치기 ────────────────────────────────────────────────────────
def test_tourapi_rows_are_not_merged():
    assert ch.merge_official_web({"source": "tour_api"}, HUMAN_ORIGIN, "10:00~17:00", "") is None
    assert ch.merge_official_web(None, None, "10:00~17:00", "") is None


def test_only_cells_tourapi_filled_replace_the_human_text():
    use, rest, remaining = ch.merge_official_web(HUMAN_READ, HUMAN_ORIGIN, "10:00~17:00", "")
    assert (use, rest, remaining) == ("10:00~17:00", "매주 화요일", {"closed_days": SRC})
    use, rest, remaining = ch.merge_official_web(HUMAN_READ, HUMAN_ORIGIN, "10:00~17:00", "매주 월요일")
    assert (use, rest, remaining) == ("10:00~17:00", "매주 월요일", {})
    _, rest, remaining = ch.merge_official_web(HUMAN_READ, HUMAN_ORIGIN, "", "<br>")        # 태그뿐이면 빈 칸
    assert rest == "매주 화요일" and remaining == {"closed_days": SRC}


# ── 새벽 작업 한 틱(가짜 연결) ────────────────────────────────────
class _Conn:
    def __init__(self, rows):
        self.rows, self.writes = rows, []

    def cursor(self):
        return self

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.last = sql
        if sql.startswith(("INSERT", "UPDATE")):
            self.writes.append((sql.split()[0], params))

    def fetchone(self):
        return (0,)

    def fetchall(self):
        return self.rows


class _Tour:
    def __init__(self, usetime, restdate):
        self.intro = {"usetime_text": usetime, "restdate_text": restdate}

    def operating(self, content_id, type_id):
        return self.intro


def _tick(conn, tour):
    return ch.prefill(conn, tenant_id="t", source=tour, chat=None, now=NIGHT, start="03:00", until="08:00",
                      per_night=600, per_tick=10, retry_days=7)


def test_empty_tourapi_answer_keeps_the_human_hours_and_only_syncs_the_modified_time():
    conn = _Conn([("1", "12", "경복궁", "20261012", HUMAN_READ, HUMAN_ORIGIN)])
    out = _tick(conn, _Tour("", ""))
    assert out["kept_official_web"] == 1
    assert conn.writes == [("UPDATE", ("20261012", "t", "1"))]


def test_filled_tourapi_answer_replaces_only_that_cell_and_keeps_the_rest_attributed():
    conn = _Conn([("1", "12", "경복궁", "20261012", HUMAN_READ, HUMAN_ORIGIN)])
    _tick(conn, _Tour("10:00~17:00", ""))
    kind, params = conn.writes[-1]
    record, origin = json.loads(params[4]), json.loads(params[5])
    assert kind == "INSERT" and origin == {"usetime": "10:00~17:00", "restdate": "매주 화요일"}
    assert record["source"] == "official_web" and record["field_sources"] == {"closed_days": SRC}


def test_tourapi_filling_every_human_cell_turns_the_row_back_into_tourapi():
    conn = _Conn([("1", "12", "경복궁", "20261012", HUMAN_READ, HUMAN_ORIGIN)])
    out = _tick(conn, _Tour("10:00~17:00", "매주 월요일"))
    record = json.loads(conn.writes[-1][1][4])
    assert record["source"] == "tour_api" and "field_sources" not in record
    assert out["official_web_replaced"] == 1


def test_tourapi_rows_are_still_overwritten_by_an_empty_answer():
    conn = _Conn([("1", "12", "경복궁", "20261012", {"source": "tour_api"}, HUMAN_ORIGIN)])
    _tick(conn, _Tour("", ""))
    kind, params = conn.writes[-1]
    assert kind == "INSERT" and json.loads(params[5]) == {"usetime": "", "restdate": ""}


# ── 출처 표시 ────────────────────────────────────────────────────
def test_note_names_the_official_page_and_its_date():
    note, evidence = official_web_note({"source": "official_web",
                                        "field_sources": {"business_hours": {**SRC, "checked": "2026-10-01"},
                                                          "closed_days": SRC}})
    assert note == "운영시간 · 휴무일: 공식 페이지(2026-10-12 확인)"
    assert [e["column"] for e in evidence] == ["business_hours", "closed_days"]
    assert official_web_note({"source": "tour_api", "field_sources": {"closed_days": SRC}}) == (None, None)
    assert official_web_note({}) == (None, None)


class _NoCatalog:
    """관광공사 목록 표가 비어 있는 연결 — `place_info` 가 장소 속성만으로 답한다."""

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a):
        pass

    def fetchall(self):
        return []


def _place(read):
    from app.domains.travel_ops.components.places.place_hours import read_by_rule

    week = read_by_rule("09:00~18:00", "매주 화요일").week
    return {"name": "경복궁", "kind": "activity",
            "attributes": {"source": "tour_api", "hours_week": week, "hours_read": read}}


def test_screen_note_keeps_tourapi_credit_and_adds_the_official_page():
    from app.domains.travel_ops.components.places.place_info import place_info

    human = place_info(_NoCatalog(), "t", _place(HUMAN_READ))
    assert human["source_note"] == "ⓒ한국관광공사 · 휴무일: 공식 페이지(2026-10-12 확인)"
    assert human["hours_source"] == ["official_web"] and human["hours_evidence"][0]["url"] == SRC["url"]
    tour = place_info(_NoCatalog(), "t", _place({"source": "tour_api"}))
    assert tour["source_note"] == "ⓒ한국관광공사" and tour["hours_evidence"] is None


def test_chat_stored_hours_line_names_the_official_page():
    from types import SimpleNamespace

    from app.domains.travel_ops.components.conversation.trip_facts import _hours_answer

    item = SimpleNamespace(place=_place(HUMAN_READ), title="경복궁",
                           starts_at=datetime(2030, 1, 7, 10, 0, tzinfo=KST))            # 월요일
    answer = _hours_answer(item, None)
    assert "경복궁 영업시간(저장된 값 · 휴무일: 공식 페이지(2026-10-12 확인)): 09:00~18:00" in answer
    plain = _hours_answer(SimpleNamespace(place=_place({"source": "tour_api"}), title="경복궁",
                                          starts_at=item.starts_at), None)
    assert "영업시간(저장된 값): " in plain


def test_values_claude_found_are_marked_as_ai_checked():
    note, evidence = official_web_note({"source": "official_web",
                                        "field_sources": {"closed_days": {**SRC, "by": "claude", "quote": "매주 월요일 휴관"}}})
    assert note == "휴무일: 공식 페이지(2026-10-12 AI 확인)" and evidence[0]["by"] == "claude"


def test_values_a_person_told_without_a_url_are_not_called_an_official_page():
    note, _ = official_web_note({"source": "official_web", "field_sources": {
        "closed_days": {"by": "human", "checked": "2026-10-12", "note": "사용자 확인"}}})
    assert note == "휴무일: 직접 확인(2026-10-12)"
