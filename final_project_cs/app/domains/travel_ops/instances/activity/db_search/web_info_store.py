# -*- coding: utf-8 -*-
"""웹 검색으로 채운 장소 정보 표(`activity.ac_place_web_info`, 마이그레이션 307)의 읽기 · 쓰기. `[2026-10-19]`

★SQL 만 한다 — 무엇을 저장할지 · 검증은 `web_info.py` 가 한다. 연결(`cur`)은 부르는 쪽이 연다.
★표가 아직 없으면(마이그레이션 307 전) 읽기는 빈 결과, 쓰기는 **쓰지 않고 `False`** 다 — 웹 정보가 없을 뿐 오류가 아니다(별칭 표와 같다).
★원장 `ac_place` 를 건드리지 않는다 — 적재(`load_places.py`)가 덮어쓰거나 `--prune` 이 지우지 않는 별도 표다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from ..web_info import Entry

EXISTS_SQL = "SELECT to_regclass('activity.ac_place_web_info') IS NOT NULL"
READ_SQL = ("SELECT place_key, field, value, source, quote, url, published_at, expires_at "
            "FROM activity.ac_place_web_info WHERE place_key = ANY(%s)")
UPSERT_SQL = ("INSERT INTO activity.ac_place_web_info "
              "(place_key, field, value, source, quote, url, published_at, model, checked_at, expires_at) "
              "VALUES (%(place_key)s, %(field)s, %(value)s, %(source)s, %(quote)s, %(url)s, %(published_at)s, %(model)s, %(checked_at)s, %(expires_at)s) "
              "ON CONFLICT (place_key, field) DO UPDATE SET value = EXCLUDED.value, source = EXCLUDED.source, quote = EXCLUDED.quote, "
              "url = EXCLUDED.url, published_at = EXCLUDED.published_at, model = EXCLUDED.model, "
              "checked_at = EXCLUDED.checked_at, expires_at = EXCLUDED.expires_at")


def _table_exists(cur: Any) -> bool:
    cur.execute(EXISTS_SQL)
    row = cur.fetchone()
    return bool(row and row[0])


def read_entries(cur: Any, place_keys: Iterable[str]) -> dict[str, dict[str, Entry]]:
    """`{place_key: {field: Entry}}`. 만료된 줄도 돌려준다(`web_info.effective` 가 만료를 본다). 표가 없으면 빈 dict."""
    keys = [k for k in place_keys if k]
    if not keys or not _table_exists(cur):
        return {}
    cur.execute(READ_SQL, (keys,))
    out: dict[str, dict[str, Entry]] = {}
    for place_key, field, value, source, quote, url, published_at, expires_at in cur.fetchall():
        out.setdefault(str(place_key), {})[str(field)] = Entry(str(field), str(value), str(source), quote, url, published_at, expires_at)
    return out


def save_entries(cur: Any, place_key: str, entries: Iterable[Entry], *, model: str | None, now: datetime) -> bool:
    """줄들을 덮어써 저장한다(같은 `place_key` · `field` 면 갱신). 표가 없으면 쓰지 않고 `False`."""
    rows = [{"place_key": place_key, "field": e.field, "value": e.value, "source": e.source, "quote": e.quote, "url": e.url,
             "published_at": e.published_at, "model": model, "checked_at": now, "expires_at": e.expires_at} for e in entries]
    if not rows:
        return True
    if not _table_exists(cur):
        return False
    cur.executemany(UPSERT_SQL, rows)
    return True
