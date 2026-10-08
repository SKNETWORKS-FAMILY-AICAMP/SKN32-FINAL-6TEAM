# -*- coding: utf-8 -*-
"""사진 받아쓰기가 같은 줄을 **두 번 다르게 읽었을 때** 접수 전체 흐름에서 그 줄의 제목이 「확인 필요」가 된다. `[2026-10-06 사용자 지시 — 계획 읽기 값 변조 줄이기]`

단위 시험 `tests/unit/travel/test_intake_transcription_differs.py` 가 비교 · 표시를 본다. 여기서는 **실제 DB · 실제 접수 흐름**(`/v1/web/trip-intakes`)으로
①전체 받아쓰기는 글자를 오독하고(「삼계탕」→「삼겹탕」) 반쪽 받아쓰기는 바르게 읽은 사진 ②그 줄의 제목만 확인 필요가 되고 값은 읽은 그대로다 ③저장 · 조회에 다르게 읽은 줄이 남는다
④마이그레이션 055 가 안 올라간 DB 에서도 읽기는 돈다(다르게 읽은 줄만 없다) 를 본다. 받아쓰기 모델은 흉내다(실제 모델 재서 본 것은 평가 리포트).

재현:

    python -m pytest tests/e2e/test_intake_transcription_differs_db.py -v
"""
from __future__ import annotations

from uuid import UUID

from psycopg import Rollback

from app.infrastructure.db.session import get_connection

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_trip_intake_api import PHOTO, PHOTO_TEXT, _client, _items, _key, _send

MISREAD = PHOTO_TEXT.replace("토속촌삼계탕", "토속촌삼겹탕")


class Vision:
    """받아쓰기 흉내 — 첫 부름(전체)은 한 줄을 오독하고, 반쪽 둘은 원문 그대로 읽는다."""

    def __init__(self, full, halves):
        self.full, self.halves, self.calls = full, halves, 0

    def see(self, prompt, image):
        self.calls += 1
        return self.full if self.calls == 1 else self.halves


def _title(view, wanted):
    for item in view["sources"][0]["items"]:
        title = item["fields"]["title"]
        if wanted in title["value"]:
            return title
    raise AssertionError(f"제목 {wanted!r} 없음")


def test_a_title_on_a_line_the_two_readings_disagree_about_needs_review_and_keeps_its_value(api):
    vision = Vision(MISREAD, PHOTO_TEXT)
    client = _client(vision)
    headers = _key(client)
    view = _send(client, headers, files=[("plan.png", PHOTO.read_bytes())])
    assert view["status"] == "review" and vision.calls == 3
    source = view["sources"][0]
    assert [d["text"] for d in source["differs"]] == ["12:30 토속촌삼겹탕 점심"] and source["differs"][0]["other"] == "12:30 토속촌삼계탕 점심"
    wrong = _title(view, "삼겹탕")
    assert wrong["value"] == "토속촌삼겹탕"                                                              # ★값은 읽은 그대로 — 서버는 어느 쪽이 맞는지 모른다
    assert wrong["needs_review"] is True and wrong["evidence"]["transcription_differs"]["other"] == "12:30 토속촌삼계탕 점심"
    assert "두 가지로 읽었어요" in wrong["note"]
    for clean in ("경복궁 관람", "명동난타극장", "북촌한옥마을 산책"):                                   # 다른 줄은 그대로(전처럼 규칙으로 읽은 값 — 확인 필요 아님)
        assert _title(view, clean)["needs_review"] is False
    assert (view["needs_review"] and any(n["field"].endswith(".title") and n["value"] == "토속촌삼겹탕" for n in view["needs_review"]))   # 확인 화면의 「확인 필요」 목록에 오른다


def test_when_both_readings_agree_nothing_is_flagged(api):
    client = _client(Vision(PHOTO_TEXT, PHOTO_TEXT))
    view = _send(client, _key(client), files=[("plan.png", PHOTO.read_bytes())])
    assert view["sources"][0]["differs"] == []
    assert _items(view)[1][1] == "토속촌삼계탕" and all(_title(view, name)["needs_review"] is False for name in ("경복궁 관람", "토속촌삼계탕"))


def test_the_differing_lines_are_stored_and_read_back(api):
    client = _client(Vision(MISREAD, PHOTO_TEXT))
    view = _send(client, _key(client), files=[("plan.png", PHOTO.read_bytes())])
    from app.domains.travel_ops.components.intake import pipeline

    with get_connection() as conn:
        [row] = [s for s in pipeline._sources(conn, api["tenant"], UUID(view["intake_id"])) if s["kind"] == "image"]  # noqa: SLF001
    assert [d["line"] for d in row["differs_json"]] == [5] and row["differs_json"][0]["half"] in ("top", "bottom")
    assert row["transcript"] == MISREAD and row["missing_json"] != []                                 # 빠진 줄 검사는 전과 같게 따로 남는다(다르게 읽은 줄의 반쪽 읽기도 적힌다)


def test_without_migration_055_reading_and_saving_still_work_and_only_the_differences_are_missing(api):
    """마이그레이션이 아직 안 올라간 DB(x600 서버가 새 코드로 먼저 뜨는 순간 등) — 칸을 지워 본 트랜잭션 안에서 접수를 열고 받아쓰기를 저장 · 조회한다. 끝에 되돌린다."""
    from app.domains.travel_ops.components.intake import pipeline
    from app.domains.travel_ops.components.intake.sources import SourceText

    with get_connection() as conn:
        with conn.transaction():
            conn.execute("ALTER TABLE intake_sources DROP COLUMN differs_json")
            intake_id = pipeline.open_intake(conn, tenant_id=api["tenant"], customer_id=api["customer"], text=None, files=[("plan.png", PHOTO.read_bytes())])
            [row] = pipeline._sources(conn, api["tenant"], intake_id)                                  # noqa: SLF001 — 칸이 없어도 읽는다
            assert "differs_json" not in row
            result = SourceText("image", MISREAD, transcribed_pages=[1], missing=[], differs=[{"line": 5, "text": "a", "other": "b", "ratio": 0.8}])
            with conn.cursor() as cur:
                pipeline._store_transcript(conn, cur, row["source_id"], api["tenant"], result)         # noqa: SLF001 — 칸이 없어도 저장한다
            [again] = pipeline._sources(conn, api["tenant"], intake_id)                                # noqa: SLF001
            assert again["transcript"] == MISREAD and again["transcribed"] is True
            raise Rollback()                                                                          # DDL 도 되돌린다 — 다른 시험에 칸이 없는 채로 남지 않게
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name='intake_sources' AND column_name='differs_json'")
        assert cur.fetchone() is not None                                                             # 칸이 그대로 돌아왔다


# ───────── 계획 확인 화면이 그리는 검토 응답(`review`) `[2026-10-07 uiux 요청]` ─────────
def _review_item(view, title):
    return next(i for i in view["review"]["items"] if title in i["title"])


def test_the_review_marks_the_item_for_review_and_gives_the_two_readings_to_draw_buttons(api):
    client = _client(Vision(MISREAD, PHOTO_TEXT))
    view = _send(client, _key(client), files=[("plan.png", PHOTO.read_bytes())])
    item = _review_item(view, "삼겹탕")
    assert item["status"] == "review" and item["can_lock"] is False                                    # 고객이 고를 때까지 확정 못 한다
    assert item["rereads"] == [{"field": "title", "current": "토속촌삼겹탕", "other": "토속촌삼계탕"}]    # 줄 전체가 아니라 값만
    [place] = [row for row in item["rows"] if row["row"] == "place"]                                   # 장소 줄 하나에 말이 덧붙는다(같은 줄이 둘로 나가지 않는다)
    # 못 찾은 장소의 차단 판정은 두 해석 안내를 붙여도 낮추지 않는다.
    assert item["place_state"] == "unresolved" and place["result"] == "bad"
    assert "두 가지로 읽었어요" in place["text"] and "토속촌삼계탕" in place["text"]
    assert view["review"]["ready"] is False
    for clean in ("경복궁 관람", "명동난타극장"):
        assert _review_item(view, clean)["rereads"] == []                                              # 다른 줄은 빈 목록


def test_when_the_customer_picks_a_value_the_reread_and_the_warning_go_away(api):
    client = _client(Vision(MISREAD, PHOTO_TEXT))
    headers = _key(client)
    view = _send(client, headers, files=[("plan.png", PHOTO.read_bytes())])
    item = _review_item(view, "삼겹탕")
    response = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers, json={
        "revision": view["revision"],
        "edits": [{"source_id": item["source_id"], "field": f"items[{item['index']}].title", "value": "토속촌삼계탕"}]})
    assert response.status_code == 200, response.text
    again = _review_item(response.json(), "삼계탕")
    assert again["rereads"] == []
    assert "두 가지로 읽었어요" not in " ".join(row["text"] for row in again["rows"])


def test_the_review_event_stream_item_event_carries_the_rereads_key(api):
    from app.domains.travel_ops.components.intake import review as review_module

    assert "rereads" in review_module._ITEM_EVENT_FIELDS                                              # noqa: SLF001 — 실시간으로 내려가는 항목 이벤트도 같은 칸을 가진다


def test_a_booking_number_read_two_ways_adds_a_booking_line_and_a_reread():
    from app.domains.travel_ops.components.intake.review import _with_note, rereads_of

    claim = {"value": "AB1234", "method": "rule", "evidence": {"transcription_differs": {"text": "예약번호 AB1234", "other": "예약번호 A81234", "other_value": "A81234"}}}
    [reread] = rereads_of({"claims": {"booking_no": claim}})
    assert (reread["field"], reread["current"], reread["other"]) == ("booking_no", "AB1234", "A81234") and "A81234" in reread["note"]
    line = _with_note(None, "booking", reread["note"])
    assert line["row"] == "booking" and line["result"] == "warn"
    merged = _with_note({"row": "booking", "result": "ok", "text": "예약이 있다고 적혀 있어요"}, "booking", reread["note"])
    assert merged["result"] == "warn" and merged["text"].startswith("예약이 있다고 적혀 있어요 · ")
    assert rereads_of({"claims": {"booking_no": {**claim, "method": "customer"}}}) == []               # 고객이 고친 칸은 건너뛴다
    assert rereads_of({"claims": {"title": {"value": "x", "method": "rule", "evidence": {}}}}) == []


def test_a_reread_note_keeps_an_unresolved_place_blocked():
    from app.domains.travel_ops.components.intake.review import _with_note

    merged = _with_note({"row": "place", "result": "bad", "text": "장소를 정하지 못했어요"}, "place", "사진을 두 가지로 읽었어요")
    assert merged == {"row": "place", "result": "bad", "text": "장소를 정하지 못했어요 · 사진을 두 가지로 읽었어요"}
