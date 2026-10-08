# -*- coding: utf-8 -*-
"""사진 · 스캔 받아쓰기가 **같은 줄을 두 번 다르게 읽은 곳**을 잡아 「확인 필요」로 표시한다. `[2026-10-06 사용자 지시 — 계획 읽기 값 변조 줄이기]`

배경: 평가셋 60건의 값 변조 12/350 = 3.4% 가 전부 사진 · 스캔 받아쓰기의 글자 오독(「창경궁」→「청경궁」)이었고, 반쪽 받아쓰기 검사는 **빠진 줄**만 잡고 **바뀐 글자**는 못 잡았다.
계약 `components/intake/sources.py`(`differing_lines` · `_transcribe`) · `pipeline.flag_differing` · 마이그레이션 055. DB 없이 도는 단위 시험(DB 쪽은 `tests/e2e/test_intake_transcription_differs_db.py`).

★지키려는 것
 ①같은 줄이 전체 · 반쪽에 똑같이 있으면 통과, **닮았지만 다르면**(글자 하나 오독) 다르게 읽은 줄이다 — 줄 번호는 전체 받아쓴 글 기준
 ②반쪽 경계에서 잘린 줄(절반 넘게 남은 조각) · 짧은 줄 · 전혀 다른 줄은 다르게 읽은 것으로 세지 않는다(오탐을 줄인다)
 ③스캔 PDF 는 쪽을 이어 붙인 글의 줄 번호로 맞춘다(쪽 번호도 남긴다)
 ④그 줄에서 읽은 **제목 · 예약번호**만 「확인 필요」가 되고 값은 안 바뀐다. 근거에 두 읽기가 남고 다른 줄 · 다른 칸은 건드리지 않는다
 ⑤`read_source` 가 그대로 쓴다(없으면 전과 같다)

재현:

    python -m pytest tests/unit/travel/test_intake_transcription_differs.py -v
"""
from __future__ import annotations

import io
from datetime import date

import pytest
from PIL import Image

from app.domains.travel_ops.components.intake import sources
from app.domains.travel_ops.components.intake.pipeline import differs_by_line, flag_differing, read_source
from app.domains.travel_ops.components.intake.sources import differing_lines

TODAY = date(2026, 10, 3)


# ── ① · ② 비교 ────────────────────────────────────────────────────
def test_a_line_read_differently_is_reported_with_both_readings():
    full = "1일차\n11:00 청경궁 관람\n13:00 점심 광장시장"
    halves = [("top", "1일차\n11:00 창경궁 관람"), ("bottom", "13:00 점심 광장시장")]
    [got] = differing_lines(full, halves)
    assert got["line"] == 2 and got["text"] == "11:00 청경궁 관람" and got["other"] == "11:00 창경궁 관람" and got["half"] == "top" and 0.5 <= got["ratio"] < 1


def test_identical_lines_in_any_half_pass_and_spacing_punctuation_do_not_matter():
    full = "11:00 창경궁 관람\n13:00 점심 · 광장시장"
    halves = [("top", "11:00  창경궁  관람"), ("bottom", "13:00 점심 광장시장")]
    assert differing_lines(full, halves) == []


def test_a_line_cut_by_the_half_boundary_is_the_same_line():
    full = "15:00 국립중앙박물관 상설전시 관람"
    assert differing_lines(full, [("top", "15:00 국립중앙박물관 상설전시")]) == []              # 잘린 앞 조각(절반 넘게 남음)
    assert differing_lines(full, [("bottom", "국립중앙박물관 상설전시 관람")]) == []              # 잘린 뒤 조각


def test_short_unrelated_and_unmatched_lines_are_not_reported():
    full = "1일차\n점심\n11:00 창경궁 관람\n19:00 완전히 다른 식당 예약"
    halves = [("top", "1일차\n점심\n11:00 창경궁 관람"), ("bottom", "ABCDEFG 1234567")]
    assert differing_lines(full, halves) == []                                                        # 짧은 줄 · 반쪽에 없는 줄 · 전혀 다른 줄은 말하지 않는다(빠진 줄은 누락 검사가 본다)


def test_a_fragment_that_merely_sits_inside_a_long_line_is_not_a_cut_line():
    full = "11:00 경복굼 관람 후 광화문 산책"
    assert differing_lines(full, [("top", "11:00")]) == []                                           # 너무 짧은 조각은 비교 대상이 아니다
    assert differing_lines(full, [("top", "11:00 경복궁 관람 후 광화문 산책")])[0]["line"] == 1       # 글자 하나 다르면 잡는다(오타를 고쳐 적은 경우)


# ── _transcribe 연결 ─────────────────────────────────────────────
def _png(width=40, height=100) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class _See:
    """받아쓰기 흉내 — 부른 차례(전체 → 위 반쪽 → 아래 반쪽)대로 정해 둔 글을 준다."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def __call__(self, prompt, image):
        self.calls += 1
        return self.answers.pop(0)


def test_transcribe_returns_missing_lines_and_differing_lines_separately():
    see = _See("1일차\n11:00 청경궁 관람", "1일차\n11:00 창경궁 관람", "13:00 점심 광장시장")
    text, missing, differs = sources._transcribe(_png(), see=see, check_halves=True)
    assert text == "1일차\n11:00 청경궁 관람" and see.calls == 3
    assert [m["text"] for m in missing] == ["11:00 창경궁 관람", "13:00 점심 광장시장"]                  # 전체에 없는 시각 줄 — 기존 누락 검사(전과 같다: 다르게 읽은 줄의 반쪽 읽기도 「없는 줄」로 적힌다)
    assert [d["line"] for d in differs] == [2]                                                        # 다르게 읽은 줄 — 새 검사(어느 줄이 어느 줄과 닮았는지 이어 준다)
    off, missing_off, differs_off = sources._transcribe(_png(), see=_See("x"), check_halves=False)
    assert (off, missing_off, differs_off) == ("x", [], [])                                           # 반쪽 검사를 끄면 전과 같다


def test_a_scanned_pdf_page_gets_its_line_numbers_shifted_by_the_pages_before_it():
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "first page text line one\nsecond line of the first page text", fontsize=12)
    document.new_page()                                                                               # 글자 없는 쪽 = 스캔
    data = document.tobytes()
    see = _See("11:00 청경궁 관람", "11:00 창경궁 관람", "")                                           # 둘째 쪽 전체 · 위 반쪽 · 아래 반쪽
    see.answers[2] = "13:00 점심 광장시장"
    result = sources.to_text(data, filename="plan.pdf", see=see)
    assert result.transcribed_pages == [2]
    lines = result.text.splitlines()
    [got] = result.differs
    assert lines[got["line"] - 1] == "11:00 청경궁 관람" and got["page"] == 2                          # 쪽을 이은 글에서 그 줄이 맞는 번호다


# ── ④ 표시 ───────────────────────────────────────────────────────
def _row(field, line, value="값", needs_review=False, note=None):
    return {"field": field, "value": value, "method": "rule", "evidence": {"source": "text", "line": line}, "needs_review": needs_review, "note": note}


def test_only_title_and_booking_number_claims_on_a_differing_line_are_flagged_and_values_stay():
    differs = differs_by_line([{"line": 3, "text": "11:00 청경궁 관람", "other": "11:00 창경궁 관람", "ratio": 0.88}])
    rows = [_row("items[0].title", 3, "청경궁 관람"), _row("items[0].booking_no", 3, "AB1234"), _row("items[0].starts_at", 3, "11:00"),
            _row("items[1].title", 4, "광장시장"), _row("items[2].title", 3, "다른 값", needs_review=True, note="모델이 가리킨 원문 조각")]
    flag_differing(rows, differs)
    title, booking, start, other_line, already = rows
    assert title["needs_review"] is True and title["value"] == "청경궁 관람" and "두 가지로 읽었어요" in title["note"] and "창경궁" in title["note"]
    assert title["evidence"]["transcription_differs"] == {"text": "11:00 청경궁 관람", "other": "11:00 창경궁 관람", "ratio": 0.88,
                                                          "other_value": "창경궁 관람"} and title["evidence"]["line"] == 3     # ★다른 읽기는 줄 전체가 아니라 값만
    assert "요 —" in title["note"] and title["note"].endswith("골라 주세요")                            # 고객 화면에 그대로 나가는 말 — 존댓말
    assert booking["needs_review"] is True and booking["value"] == "AB1234"
    assert start["needs_review"] is False and "transcription_differs" not in start["evidence"]            # 시각 칸 · 다른 줄은 그대로
    assert other_line["needs_review"] is False and "transcription_differs" not in other_line["evidence"]
    assert already["needs_review"] is True and already["note"].startswith("모델이 가리킨 원문 조각 · ")     # 앞의 메모를 지우지 않는다


def test_without_differences_nothing_changes():
    rows = [_row("items[0].title", 3, "창경궁 관람")]
    before = [dict(r) for r in rows]
    flag_differing(rows, None)
    flag_differing(rows, {})
    assert rows == before
    assert differs_by_line(None) == {} and differs_by_line([{"line": "x"}, "이상한 값", {"text": "줄 번호 없음"}]) == {}


# ── ⑤ read_source ────────────────────────────────────────────────
class _Tour:
    misses: dict = {}

    def find(self, name, area_code=None):
        return None


class _Kakao:
    misses: dict = {}

    def search(self, query, size=5, near=None):
        return []


TEXT = "2026-10-10 1일차\n11:00 청경궁 관람\n13:00 점심 광장시장\n"


def test_read_source_flags_the_title_read_on_the_differing_line_and_streams_the_flag():
    streamed = []
    rows = read_source(TEXT, tour=_Tour(), kakao=_Kakao(), our_places=[], today=TODAY, on_rows=streamed.extend,
                       differs=differs_by_line([{"line": 2, "text": "11:00 청경궁 관람", "other": "11:00 창경궁 관람", "ratio": 0.9}]))
    title = next(r for r in rows if r["field"].endswith(".title") and "청경궁" in str(r["value"]))
    lunch = next(r for r in rows if r["field"].endswith(".title") and "광장시장" in str(r["value"]))
    assert title["needs_review"] is True and title["evidence"]["transcription_differs"]["other"] == "11:00 창경궁 관람"
    assert not lunch["evidence"].get("transcription_differs")
    streamed_title = next(r for r in streamed if r["field"] == title["field"])
    assert streamed_title["needs_review"] is True                                                    # 실시간으로 내려가는 값도 같은 표시다


def test_read_source_without_the_argument_behaves_as_before():
    plain = read_source(TEXT, tour=_Tour(), kakao=_Kakao(), our_places=[], today=TODAY)
    assert not any((r.get("evidence") or {}).get("transcription_differs") for r in plain)


# ── ⑥ 다른 읽기의 값(`other_value`) `[2026-10-07 uiux 요청]` ─────────────────────────
@pytest.mark.parametrize("value,text,other,expected", [
    ("청경궁 관람", "11:00 청경궁 관람", "11:00 창경궁 관람", "창경궁 관람"),                      # 글자 하나가 바뀜
    ("AB1234", "예약번호 AB1234 확인", "예약번호 A81234 확인", "A81234"),                         # 예약번호
    ("토속촌삼겹탕 점심", "12:30 토속촌삼겹탕 점심", "12:30 토속촌삼계탕 점심", "토속촌삼계탕 점심"),     # 값 앞에 시각이 붙어 있어도 값 자리만
    ("국립중앙박물관", "13:00 국립중앙박물관", "13:00 국립중앙박물", "국립중앙박물"),                  # 뒤가 잘려 읽힘
    ("경복궁", "09:30 경복궁 관람", "09:30 경복굼 관람", "경복굼"),                              # 줄 가운데 일부
])
def test_other_reading_is_the_value_cut_out_of_the_other_line(value, text, other, expected):
    assert sources.other_reading(value, text, other) == expected


@pytest.mark.parametrize("value,text,other", [
    ("없는 값", "09:30 경복궁 관람", "09:30 경복굼 관람"),             # 값이 줄 안에서 글자 그대로 안 보인다(모델이 다듬은 값)
    ("경복궁", "09:30 경복궁", "09:30 경복궁"),                        # 같은 값
    ("", "09:30 경복궁", "09:30 경복굼"),                              # 값이 비었다
    ("경복궁", "09:30 경복궁", ""),                                    # 다른 줄이 비었다
    ("경복궁", "09:30 경복궁", "전혀 다른 아주아주아주아주아주 긴 문장입니다 정말로"),   # 맞춤이 어긋나 길이가 너무 다르다
])
def test_other_reading_is_none_when_it_cannot_be_told(value, text, other):
    assert sources.other_reading(value, text, other) is None


def test_the_streamed_title_also_carries_the_other_value():
    streamed = []
    read_source(TEXT, tour=_Tour(), kakao=_Kakao(), our_places=[], today=TODAY, on_rows=streamed.extend,
                differs=differs_by_line([{"line": 2, "text": "11:00 청경궁 관람", "other": "11:00 창경궁 관람", "ratio": 0.9}]))
    title = next(r for r in streamed if r["field"].endswith(".title") and "청경궁" in str(r["value"]))
    assert title["evidence"]["transcription_differs"]["other_value"] in ("창경궁 관람", "창경궁")      # 값이 줄에서 어디까지인지는 읽기 규칙이 정한다
