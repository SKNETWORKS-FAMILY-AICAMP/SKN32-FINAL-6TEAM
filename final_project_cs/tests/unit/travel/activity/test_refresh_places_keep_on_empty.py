"""원문 바뀜 알아채기(`scripts/activity/refresh_places.py`) — 관광공사가 빈 값을 주면 채워 둔 운영시간 · 휴무 글을 NULL 로 덮지 않는다.
`[2026-10-27 장소 품질 전수검사]` 가짜 DB 경계(외부 호출 · 실 DB 없음).

☆2026-10-26 381건 판단의 남은 일: 관광공사 수정 시각이 바뀌면 상세를 다시 받아 그 값을 그대로 적었다 — 상세에 칸이 없으면(None)
  같은 매장군(sibling) · 사람 · Claude 가 채운 글이 NULL 로 덮였다. NULL 은 「휴무 없음」이 아니다(Codex Q2 · 2026-10-27 Q3).
★규칙: 빈 값 → 저장된 글이 있으면 유지(`kept_on_empty` 로 센다), 비어 있지 않은 다른 글 → 덮고 요일표를 비운다(전과 같다).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location("activity_refresh_places_unit", ROOT / "scripts" / "activity" / "refresh_places.py")
refresh_places = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refresh_places)


class _Conn:
    """`activity.ac_place` 한 행 — SELECT 는 그 행을, UPDATE 는 값을 바꾼다."""

    def __init__(self, cid, mod, use, rest):
        self.row = {"content_id": cid, "source_modified_at": mod, "usetime_text": use, "restdate_text": rest,
                    "hours_week": {"mon": "closed"}}
        self.updates = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args):
        if sql.startswith("SELECT"):
            r = self.row
            self._rows = [(r["content_id"], r["source_modified_at"], r["usetime_text"], r["restdate_text"])]
            return
        self.updates.append((sql, args))
        if "usetime_text = %s" in sql:
            use, rest, mod, clear_week, _clear_read, _cid = args
            self.row.update(usetime_text=use, restdate_text=rest, source_modified_at=mod)
            if clear_week:
                self.row["hours_week"] = None
        else:
            self.row["source_modified_at"] = args[0]

    def fetchall(self):
        return self._rows


def _listed(cid, mod):
    return [{"contentid": cid, "contenttypeid": "12", "modifiedtime": mod}]


def test_empty_detail_keeps_the_filled_text_and_week():
    conn = _Conn("126535", "20261001000000", "10:00~22:00", "매주 월요일")
    out = refresh_places.refresh(conn, _listed("126535", "20261027000000"), lambda c, t: {})      # 관광공사 상세에 두 칸 다 없음
    assert conn.row["usetime_text"] == "10:00~22:00" and conn.row["restdate_text"] == "매주 월요일"
    assert conn.row["hours_week"] == {"mon": "closed"}                   # 글이 그대로라 요일표도 그대로
    assert conn.row["source_modified_at"] == "20261027000000"            # 확인한 시각은 남긴다
    assert out["kept_on_empty"] == 1 and out["text_changed"] == 0


def test_provider_none_is_also_empty_not_no_holiday():
    conn = _Conn("126535", "20261001000000", "10:00~22:00", "매주 월요일")
    out = refresh_places.refresh(conn, _listed("126535", "20261027000000"), lambda c, t: None)    # 공급자 「항목 없음」
    assert (conn.row["usetime_text"], conn.row["restdate_text"]) == ("10:00~22:00", "매주 월요일")
    assert out["kept_on_empty"] == 1


def test_new_text_replaces_and_only_the_empty_field_is_kept():
    conn = _Conn("126535", "20261001000000", "10:00~22:00", "매주 월요일")
    out = refresh_places.refresh(conn, _listed("126535", "20261027000000"), lambda c, t: {"usetime": "10:00~23:00"})
    assert (conn.row["usetime_text"], conn.row["restdate_text"]) == ("10:00~23:00", "매주 월요일")
    assert conn.row["hours_week"] is None                                # 글이 바뀌었으니 다시 편다
    assert out["kept_on_empty"] == 1 and out["text_changed"] == 1


def test_empty_stored_field_stays_empty_and_is_not_counted():
    conn = _Conn("126535", "20261001000000", "10:00~22:00", None)
    out = refresh_places.refresh(conn, _listed("126535", "20261027000000"), lambda c, t: {"usetime": "10:00~22:00"})
    assert conn.row["restdate_text"] is None and out["kept_on_empty"] == 0 and out["text_changed"] == 0
