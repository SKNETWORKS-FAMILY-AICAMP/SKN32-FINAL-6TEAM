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
