# -*- coding: utf-8 -*-
"""계획 읽기 — 웹 입구 `/v1/web/trip-intakes`. `[2026-09-27]` 설계서 1주차

★완료 기준(설계서 §8 1주차): 실측 사진이 **6/6 항목, 값 변조 0** 으로 `intake_claims` 에 들어간다.
  여기서는 받아쓰기 모델을 흉내 낸다(사진의 원문을 그대로 돌려준다) — 실제 gemma4:12b 로는 같은 사진에서
  6/6·변조 0·누락 0 을 쟀다(2026-09-27, 1회, 전체+반쪽 둘 56.6초).
★값은 모두 원문의 (줄, 시작, 끝) 근거를 들고 다닌다 — 근거 없는 값 0.

재현:

    python -m pytest tests/e2e/test_trip_intake_api.py -v
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.presentation.api.app import create_app
from app.modules.travel_ops.trip_api import build_trip_router

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다

PHOTO = Path(__file__).resolve().parents[1] / "fixtures" / "intake" / "seoul_2n3d_plan.png"
#: 사진에 그려 넣은 원문 — 가짜 받아쓰기가 그대로 돌려준다
PHOTO_TEXT = """서울 2박3일 가족여행 (4명)

1일차 · 10월 15일 (수)
09:00 경복궁 관람
12:30 토속촌삼계탕 점심
19:00 명동난타극장 · 예약번호 KY-20931

2일차 · 10월 16일 (목)
10:00 북촌한옥마을 산책
13:00 광장시장 빈대떡
15:30 N서울타워"""
WANT = [("09:00", "경복궁 관람"), ("12:30", "토속촌삼계탕"), ("19:00", "명동난타극장"),
        ("10:00", "북촌한옥마을 산책"), ("13:00", "광장시장 빈대떡"), ("15:30", "N서울타워")]


class Vision:
    """받아쓰기 흉내 — 전체든 반쪽이든 원문을 돌려준다(반쪽 누락 검사가 「빠진 줄 없음」이 되게)."""

    def __init__(self):
        self.calls = 0

    def see(self, prompt, image):
        self.calls += 1
        assert "그대로" in prompt                  # ★구조화를 시키지 않는다 — 받아 적기만
        return PHOTO_TEXT


def _client(vision=None):
    return TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other",
                                                          "sentiment": "neutral"},
                                 domain_routers=[build_trip_router(chat_factory=(lambda: vision)
                                                                   if vision else None)]))


def _key(client) -> dict:
    return {"X-User-Key": client.post("/v1/web/session").json()["user_key"]}


def _send(client, headers, *, text="", files=()):
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text},
                           files=[("files", (name, data, "application/octet-stream")) for name, data in files])
    assert response.status_code == 202, response.text
    return client.get(f"/v1/web/trip-intakes/{response.json()['intake_id']}", headers=headers).json()


def _items(view, source=0):
    return [(i["fields"]["starts_at"]["value"] if "starts_at" in i["fields"] else None,
             i["fields"]["title"]["value"] if "title" in i["fields"] else None)
            for i in view["sources"][source]["items"]]


def test_a_photo_plan_is_read_six_of_six_with_every_value_cut_from_the_transcript(api):
    vision = Vision()
    client = _client(vision)
    headers = _key(client)
    view = _send(client, headers, files=[("plan.png", PHOTO.read_bytes())])
    assert view["status"] == "review", view
    assert vision.calls == 3                                   # 전체 + 위·아래 반쪽(누락 검사)
    source = view["sources"][0]
    assert source["kind"] == "image" and source["transcribed"] and source["missing"] == []
    assert _items(view) == WANT                                 # ★6/6
    lines = PHOTO_TEXT.splitlines()
    for item in source["items"]:                                # ★값 변조 0 — 이름은 원문 조각 그대로
        title = item["fields"]["title"]
        ev = title["evidence"]
        assert lines[ev["line"] - 1][ev["start"]:ev["end"]] == title["value"] == ev["text"]
        assert title["method"] == "rule"
    booking = [i["fields"]["booking_no"]["value"] for i in source["items"] if "booking_no" in i["fields"]]
    assert booking == ["KY-20931"]
    assert source["trip"]["party_size"]["value"] == 4 and source["trip"]["nights"]["value"] == 2
    assert [(i["day"], i["date"]) for i in source["items"]][:1] == [(1, "--10-15")]
    assert [(i["day"], i["date"]) for i in source["items"]][3:4] == [(2, "--10-16")]


def test_a_chat_style_plan_is_read_into_items(api):
    client = _client()
    view = _send(client, _key(client),
                 text="첫날은 9시에 경복궁 가고, 12시 반에 토속촌에서 점심 먹고 오후 3시에 인사동 가요\n"
                      "둘째 날 10시~12시 한강 카약, 저녁 7시에 명동")
    assert view["status"] == "review" and view["sources"][0]["kind"] == "chat"
    assert _items(view) == [("09:00", "경복궁"), ("12:30", "토속촌"), ("15:00", "인사동"),
                            ("10:00", "한강 카약"), ("19:00", "명동")]
    ends = [i["fields"].get("ends_at", {}).get("value") for i in view["sources"][0]["items"]]
    assert ends[3] == "12:00"


def test_an_unclear_hour_is_marked_for_review_and_unread_lines_are_kept(api):
    client = _client()
    view = _send(client, _key(client), text="3시에 남산타워\n저녁은 아무 데나 괜찮아요")
    assert [r["field"] for r in view["needs_review"]] == ["items[0].starts_at"]
    lines = view["sources"][0]["lines"]
    assert [line["read"] for line in lines] == [True, False]     # 남은 줄 — 2주차에 LLM 이 위치만 가리킨다


def test_pdf_docx_and_xlsx_are_read_with_their_own_parsers(api):
    import docx
    import fitz
    import openpyxl

    pdf = fitz.open()
    page = pdf.new_page()
    # 내장 한국어 글꼴 — 맑은 고딕 파일을 통째로 넣으면 10MB 제한을 넘는다(제한은 그대로 둔다)
    page.insert_text((72, 72), "1일차 2026-10-15\n09:00 경복궁\n12:30 토속촌삼계탕", fontname="korea", fontsize=12)
    pdf_bytes = pdf.tobytes()
    document = docx.Document()
    document.add_paragraph("1일차 2026-10-15")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "09:00", "경복궁"
    buffer = io.BytesIO()
    document.save(buffer)
    book = openpyxl.Workbook()
    book.active.append(["1일차", "2026-10-15"])
    book.active.append(["09:00", "경복궁"])
    sheet = io.BytesIO()
    book.save(sheet)

    client = _client()
    view = _send(client, _key(client), files=[("a.pdf", pdf_bytes), ("b.docx", buffer.getvalue()),
                                               ("c.xlsx", sheet.getvalue())])
    assert view["status"] == "review", view
    assert [s["kind"] for s in view["sources"]] == ["pdf", "docx", "xlsx"]
    assert _items(view, 0) == [("09:00", "경복궁"), ("12:30", "토속촌삼계탕")]
    assert _items(view, 1) == [("09:00", "경복궁")]
    assert _items(view, 2) == [("09:00", "경복궁")]


def test_unknown_files_are_refused_at_the_door_and_photos_need_a_reader(api):
    client = _client()
    headers = _key(client)
    refused = client.post("/v1/web/trip-intakes", headers=headers,
                          files=[("files", ("x.bin", b"\x00\x01\x02binary", "application/octet-stream"))])
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "unsupported_format"
    empty = client.post("/v1/web/trip-intakes", headers=headers, data={"text": "  "})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_intake"
    # 받아쓰기 모델이 없으면 사진은 「읽지 못함」— 지어내지 않는다
    view = _send(client, headers, files=[("plan.png", PHOTO.read_bytes())])
    assert view["status"] == "fatal" and view["fatal"]["code"] == "unsupported_format", view


def test_an_intake_is_yours_only(api):
    client = _client()
    mine = _key(client)
    other = _key(client)
    response = client.post("/v1/web/trip-intakes", headers=mine, data={"text": "09:00 경복궁"})
    intake = response.json()["intake_id"]
    assert client.get(f"/v1/web/trip-intakes/{intake}", headers=other).status_code == 404
    assert client.get(f"/v1/web/trip-intakes/{intake}").status_code == 401
    assert client.post("/v1/web/trip-intakes", data={"text": "09:00 경복궁"}).status_code == 401


@pytest.mark.parametrize("name", ["plan.PNG.pdf", "plan.txt"])
def test_the_kind_comes_from_the_bytes_not_the_name(api, name):
    """★확장자가 PDF 라도 첫 바이트가 PNG 면 사진이다."""
    vision = Vision()
    client = _client(vision)
    view = _send(client, _key(client), files=[(name, PHOTO.read_bytes())])
    assert view["sources"][0]["kind"] == "image" and _items(view) == WANT
