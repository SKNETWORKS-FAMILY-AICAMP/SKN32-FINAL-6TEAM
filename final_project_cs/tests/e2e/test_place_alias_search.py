# -*- coding: utf-8 -*-
"""확인 화면 장소 검색의 공용 별칭 단계 — 활동 원장에만 있고 관광공사 목록(`place_catalog`)에 행이 없는 곳도 별칭으로 나와야 한다.

☆`[2026-10-23]` x600 서버 실서버 확인에서 「mmca 서울」이 별칭 단계 없이 카카오 결과로만 나왔다. 별칭이 가리키는 곳이 활동 원장에는 있고
  관광공사 목록에는 없으면, 원장 좌표로 만든 결과에 주소가 없어 검색어의 「서울」 지역 확인에서 `area_unverified` 로 빠졌다(결정 D-CS-021)."""
from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection

from .test_intake_review import Kakao, _catalog, _client, _item, _key, _send, rv  # noqa: F401 — rv 는 픽스처
from .test_trip_api import api  # noqa: F401 — rv 가 쓰는 픽스처

LOAD_ID = "00000000-0000-0000-0000-0000000a11a5"


class MmcaKakao(Kakao):
    """카카오 모방 — 「mmca 서울」을 같은 곳(국립현대미술관 서울)의 카카오 결과로 돌려준다."""

    def search(self, query, size=5, near=None, **_):
        if "mmca" in query.lower():
            return [{"id": "77", "name": "국립현대미술관 서울", "category": "문화,예술 > 미술관", "category_group": "CT1",
                     "address": "서울 종로구 삼청로 30", "latitude": 37.5792, "longitude": 126.9803}]
        return []


@pytest.fixture()
def ledger(rv):  # noqa: F811
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (load_id, source_file, file_sha256, row_count) VALUES (%s,'test','test',1) "
                    "ON CONFLICT DO NOTHING", (LOAD_ID,))
        cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, addr1, lat, lng, load_id) "
                    "VALUES ('1934593','14','국립현대미술관 서울','국립현대미술관서울','서울특별시 종로구 삼청로 30',37.5792,126.9803,%s) "
                    "ON CONFLICT DO NOTHING", (LOAD_ID,))
    yield rv
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM activity.ac_place WHERE load_id = %s", (LOAD_ID,))
        cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (LOAD_ID,))


def _search(client, headers, text):
    view = _send(client, headers)
    item = _item(view, "올리브영")
    base = f"/v1/web/trip-intakes/{view['intake_id']}/place-search?source_id={item['source_id']}&index={item['index']}"
    return client.get(base + "&q=" + text, headers=headers).json()


def test_alias_found_when_catalog_has_the_row(ledger):
    _catalog(ledger, "1934593", "14", "국립현대미술관 서울", 37.5792, 126.9803, address="서울특별시 종로구 삼청로 30")
    client, _, _ = _client(kakao=MmcaKakao())
    found = _search(client, _key(client), "mmca%20서울")
    assert [(r["place"]["name"], r["place"]["source"]) for r in found["results"]][:1] == [("국립현대미술관 서울", "tour_api")]


def test_alias_found_even_when_only_the_activity_ledger_has_the_row(ledger):
    client, _, _ = _client(kakao=MmcaKakao())
    found = _search(client, _key(client), "mmca%20서울")
    first = found["results"][0]["place"]
    assert (first["name"], first["source"], first["content_id"]) == ("국립현대미술관 서울", "tour_api", "1934593")
    assert "area_unverified" not in found["notes"] and first["address"].startswith("서울")


def test_alias_found_when_the_ledger_has_no_row_but_the_catalog_does(rv):  # noqa: F811
    """☆`[2026-10-23]` x600 서버의 실제 모양 — 1934593 이 활동 원장에는 없고 관광공사 목록에만 있다. 시드 파일의 정식 제목으로 별칭이 통해야 한다."""
    _catalog(rv, "1934593", "14", "국립현대미술관 서울", 37.5792, 126.9803, address="서울특별시 종로구 삼청로 30")
    client, _, _ = _client(kakao=MmcaKakao())
    found = _search(client, _key(client), "mmca%20서울")
    first = found["results"][0]["place"]
    assert (first["name"], first["source"], first["content_id"]) == ("국립현대미술관 서울", "tour_api", "1934593")


def test_alias_not_used_when_the_ledger_row_is_delisted(ledger):
    """폐지된 곳은 별칭으로 되살리지 않는다 — 원장에 행은 있으나 폐지 표시면 카카오 결과만 나온다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE activity.ac_place SET delisted_at = now() WHERE content_id = '1934593'")
    _catalog(ledger, "1934593", "14", "국립현대미술관 서울", 37.5792, 126.9803, address="서울특별시 종로구 삼청로 30")
    client, _, _ = _client(kakao=MmcaKakao())
    found = _search(client, _key(client), "mmca%20서울")
    assert [r["place"]["source"] for r in found["results"]][:1] == ["kakao"]
