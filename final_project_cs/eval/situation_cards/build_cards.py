# -*- coding: utf-8 -*-
"""상황 카드 초안 — RAG 60장 · LLM 60장 · 작성자 시트(블라인드).

무엇인가
- 사람이 **고객 문장**만 쓰게 하는 카드다. 카드가 상황을 정하므로 정답(키)은 카드를 만들 때 정해진다.
- RAG 카드: 규정 표(`knowledge/travel_ext/` 의 국내여행 · 공연 · 레저 기준)에서 **기대 결과를 계산**한다.
- LLM 카드: 고객이 바라는 성질(실내 · 역사 · 체험 …)과 단서 출처를 정답 키로 둔다. 후보 3곳은
  DB(활동 원장 `activity.ac_place`)를 켠 뒤 운영 코드(`rank_alternatives`)로 붙인다 — `binding` 이 후보 조건이다.

★정답 키는 `travel_ext` **초안**(README 「사실 확인 대기」) 기준이다. 원문 대조 전에는 `source_status` 가
  `draft` 이고, 해석이 갈릴 수 있는 카드는 `needs_review=true` 로 표시한다.
★작성자 시트(`sheet_*.csv`)에는 상황 문장만 싣는다 — 정답 키 · 묶음 · 규정 용어를 싣지 않는다(블라인드).
★LLM 호출 없음 · DB 없음 · 난수는 고정 seed.

실행: `python eval/situation_cards/build_cards.py` (final_project_cs 에서)
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
VERSION = "v0"
SEED = 1016
WRITERS = 4
WEEKDAY = "월화수목금토일"

# ── 규정 절(골드) — 문서 id#절 제목. 제목은 knowledge/travel_ext/documents/*.md 의 `##` 와 같다 ──
S = {
    "t1_scope": "t_ext_01#표준약관이 다루는 범위",
    "t1_cancel": "t_ext_01#출발 전 계약 해제와 손해 배상",
    "t1_force": "t_ext_01#천재지변·정부 명령 등 위약금 없이 해제할 수 있는 공통 사유",
    "t1_personal": "t_ext_01#가족 사망·질병 등 개인 사유로 위약금 없이 해제하는 경우",
    "t1_minimum": "t_ext_01#최저 인원이 채워지지 않았을 때",
    "t2_traveler": "t_ext_02#여행자 사유로 취소하는 경우",
    "t2_agency": "t_ext_02#여행사 사유로 취소하는 경우",
    "t2_change": "t_ext_02#여행사가 계약 조건을 바꿔 해지하는 경우",
    "t2_minimum": "t_ext_02#인원 미달로 여행사가 취소하는 경우",
    "t2_force": "t_ext_02#천재지변·정부 명령 같은 불가항력으로 취소하는 경우",
    "t2_disease": "t_ext_02#감염병과 재난으로 해제를 요청하는 경우",
    "t3_facility": "t_ext_03#시설을 정상적으로 이용할 수 없을 때",
    "t3_ad": "t_ext_03#광고나 계약 내용과 실제가 다른 경우",
    "t3_biz": "t_ext_03#사업자 책임으로 해제하는 경우의 반환 금액",
    "t3_consumer": "t_ext_03#소비자 책임으로 해제하는 경우의 반환 금액",
    "t3_show_cancel": "t_ext_03#공연이 취소되거나 연기된 경우",
    "t3_show_refund": "t_ext_03#관객이 환급을 요구하는 경우",
}
CAVEAT = "참고 · 권고 기준이며 업체(계약) 약관이 확인되면 그것이 우선"

PARTIES = ["친구 3명과", "가족 4명이", "부모님을 모시고", "회사 동료 2명과", "연인과", "대학 동기 5명과"]
PERSONAL = ["회사에 급한 일이 생겨서", "다른 약속과 날짜가 겹쳐서", "일행끼리 일정이 안 맞아서",
            "마음이 바뀌어서", "이사 날짜가 당겨져서", "예산이 부족해져서"]


def _day(d: date) -> str:
    return f"{d.month}월 {d.day}일({WEEKDAY[d.weekday()]})"


def _when(days: int) -> str:
    return "당일" if days == 0 else f"{days}일 전"


# ── RAG 계산 규칙(초안 기준) ───────────────────────────────────────────────
def traveler_rate(kind: str, days: int) -> int | None:
    """여행자 사유 — None = 전액 환급. 당일: 3일 전까지 전액 · 2일 10 · 1일 20 · 당일 30.
    숙박: 5일 전까지 전액 · 「2일 전까지」10(=4~2일) · 1일 20 · 당일 30."""
    full = 3 if kind == "당일" else 5
    if days >= full:
        return None
    return {0: 30, 1: 20}.get(days, 10)


def agency_rate(kind: str, days: int) -> int | None:
    """여행사 사유 · 조건 변경 해지 — None = 계약금 환급만. 그 밖은 계약금 환급 + 요금 비율 배상."""
    return traveler_rate(kind, days)


def show_deduction(days: int) -> int | None:
    """관객 환급 요구 — None = 전액. 10일 전까지 전액 · 7일 10 · 3일 20 · 1일 30 · 당일(시작 전) 90."""
    if days >= 10:
        return None
    if days >= 7:
        return 10
    if days >= 3:
        return 20
    if days >= 1:
        return 30
    return 90


def _other_rates(rate: int | None, pool=(10, 20, 30)) -> list[str]:
    out = [f"{p}%" for p in pool if p != rate]
    if rate is not None:
        out.append("전액 환급")
    return out


# ── RAG 카드 ──────────────────────────────────────────────────────────────
def rag_cards(rng: random.Random) -> list[dict]:
    cards: list[dict] = []
    base = date(2026, 11, 7)

    def add(stratum, situation, behavior, gold, facts, forbidden, *, required=None, review=None, caveat=True, meta=None):
        cards.append({
            "card_id": f"R-{len(cards) + 1:02d}", "kind": "rag", "stratum": stratum, "situation": situation,
            "expected_behavior": behavior, "gold_sections": gold, "required_sections": required or [],
            "required_facts": facts, "forbidden_claims": forbidden, "must_caveat": caveat and behavior == "answer",
            "needs_review": review or "", "source_status": "draft", "meta": meta or {}, "label_by": "card-rule",
        })

    # 1) 여행자 사유 — 국내 당일 5 · 숙박 7 · 연락 없이 불참 2 (14)
    plan = [("당일", d) for d in (5, 3, 2, 1, 0)] + [("숙박", d) for d in (7, 5, 4, 3, 2, 1, 0)]
    for i, (kind, days) in enumerate(plan):
        dep = base + timedelta(days=i * 2)
        notice = dep - timedelta(days=days)
        rate = traveler_rate(kind, days)
        product = "당일치기 국내 여행 상품" if kind == "당일" else "1박 2일 국내 여행 상품"
        situation = (f"{rng.choice(PARTIES)} 여행사에서 {product}을 예약했습니다. 출발은 {_day(dep)}입니다. "
                     f"{rng.choice(PERSONAL)} {_day(notice)}에 취소하려고 합니다. 돈을 얼마나 돌려받을 수 있는지 궁금합니다.")
        result = "전액 환급" if rate is None else f"요금의 {rate}% 배상"
        boundary = (kind == "당일" and days == 3) or (kind == "숙박" and days == 5)
        review = ""
        if boundary:
            review = "경계일 — 「N일 전까지」의 날짜 세는 법을 원문으로 확인"
        elif kind == "숙박" and days in (3, 4):
            review = "숙박 4~3일 전을 「2일 전까지 10%」 구간으로 읽었다 — 원문 표로 확인"
        add("D" if boundary or review else "C", situation, "answer", [S["t2_traveler"], S["t1_cancel"]],
            [{"k": "구분", "v": f"{kind}여행"}, {"k": "통보 시점", "v": _when(days)}, {"k": "결과", "v": result}],
            _other_rates(rate), review=review, meta={"departure": str(dep), "notice": str(notice), "days_before": days})
    for kind in ("당일", "숙박"):
        dep = base + timedelta(days=30 if kind == "당일" else 32)
        add("C", f"{rng.choice(PARTIES)} {kind if kind == '당일' else '1박 2일'} 국내 여행 상품을 예약했는데, "
                 f"출발일({_day(dep)}) 아침에 늦잠을 자서 연락도 못 하고 못 갔습니다. 환불이 되는지 궁금합니다.",
            "answer", [S["t2_traveler"]],
            [{"k": "구분", "v": f"{kind}여행"}, {"k": "통보 시점", "v": "당일 · 연락 없이 불참"}, {"k": "결과", "v": "요금의 30% 배상"}],
            _other_rates(30), meta={"departure": str(dep), "days_before": 0})

    # 2) 여행사 사유 4 · 조건 변경 해지 2 (6)
    for kind, days in (("당일", 4), ("당일", 1), ("숙박", 6), ("숙박", 0)):
        dep = base + timedelta(days=40 + days)
        notice = dep - timedelta(days=days)
        rate = agency_rate(kind, days)
        result = "계약금 환급" if rate is None else f"계약금 환급 + 요금의 {rate}% 배상"
        add("E", f"{rng.choice(PARTIES)} {'당일치기' if kind == '당일' else '1박 2일'} 국내 여행 상품을 예약했습니다(출발 {_day(dep)}). "
                 f"{_day(notice)}에 여행사에서 '차량을 구하지 못해 여행을 취소한다'고 연락이 왔습니다. 무엇을 받을 수 있는지 궁금합니다.",
            "answer", [S["t2_agency"]],
            [{"k": "구분", "v": f"{kind}여행"}, {"k": "통보 시점", "v": _when(days)}, {"k": "결과", "v": result}],
            _other_rates(rate) + ["위약금을 내야"], meta={"departure": str(dep), "days_before": days})
    for kind, days, change in (("숙박", 2, "숙소가 다른 지역으로 바뀐다"), ("당일", 3, "방문지 두 곳이 빠진다")):
        dep = base + timedelta(days=50 + days)
        notice = dep - timedelta(days=days)
        rate = agency_rate(kind, days)
        result = "계약금 환급" if rate is None else f"계약금 환급 + 요금의 {rate}% 배상"
        add("E", f"출발 {_day(dep)}인 {'1박 2일' if kind == '숙박' else '당일치기'} 국내 여행 상품인데, {_day(notice)}에 여행사가 "
                 f"'{change}'고 알려 왔습니다. 약속과 달라 계약을 그만두고 싶습니다.",
            "answer", [S["t2_change"]],
            [{"k": "구분", "v": f"{kind}여행"}, {"k": "통보 시점", "v": _when(days)}, {"k": "결과", "v": result}],
            _other_rates(rate) + ["위약금을 내야"], meta={"departure": str(dep), "days_before": days})

    # 3) 인원 미달 (4) — 통지 기한: 당일 24시간 · 숙박 48시간
    for kind, hours in (("당일", 30), ("당일", 10), ("숙박", 72), ("숙박", 36)):
        deadline = 24 if kind == "당일" else 48
        ok = hours >= deadline
        result = "계약금 환급(추가 배상 없음)" if ok else "계약금 환급 + 계약금의 100% 배상"
        add("E", f"{'당일치기' if kind == '당일' else '1박 2일'} 국내 여행 상품을 예약했는데, 출발 {hours}시간 전에 여행사에서 "
                 "'신청한 사람이 모자라 여행을 진행하지 않는다'는 연락을 받았습니다. 보상이 있는지 궁금합니다.",
            "answer", [S["t2_minimum"], S["t1_minimum"]],
            [{"k": "구분", "v": f"{kind}여행"}, {"k": "통지 기한", "v": f"{deadline}시간 전"}, {"k": "결과", "v": result}],
            ["계약금의 100%"] if ok else ["배상 없음"], meta={"hours_before": hours, "deadline_hours": deadline})

    # 4) 불가항력 3 · 감염병 · 재난 3 (6)
    for cause in ("태풍으로 배 운항이 모두 중단돼", "폭설로 가는 길이 통제돼", "정부 명령으로 방문지가 폐쇄돼"):
        add("E", f"{rng.choice(PARTIES)} 예약한 1박 2일 국내 여행이 {cause} 갈 수 없게 됐습니다. 돈은 어떻게 되는지 궁금합니다.",
            "answer", [S["t2_force"], S["t1_force"]],
            [{"k": "사유", "v": "불가항력"}, {"k": "결과", "v": "계약금 환급(배상 없음)"}],
            ["30%", "위약금을 내야", "여행사가 배상"])
    add("E", "1급 감염병이 돌아 여행지 시설에 운영 중단 명령이 내려졌습니다. 예약한 국내 여행을 취소하고 싶습니다.",
        "answer", [S["t2_disease"]],
        [{"k": "사유", "v": "행정명령으로 이행 불가"}, {"k": "결과", "v": "위약금 없이 계약금 환급"}], ["50% 감경"])
    add("E", "여행 가려던 지역에 재난사태가 선포됐습니다. 시설은 열려 있다는데 가기 어려워 취소하려 합니다. 위약금이 있나요?",
        "answer", [S["t2_disease"]],
        [{"k": "사유", "v": "재난사태 선포"}, {"k": "결과", "v": "위약금 50% 감경"}], ["위약금 없이", "전액 환급"])
    add("E", "감염병 위기경보가 '심각' 단계가 됐다는 뉴스를 봤습니다. 다음 주 국내 여행을 취소하면 위약금이 줄어드나요?",
        "answer", [S["t2_disease"]],
        [{"k": "사유", "v": "위기경보 심각 단계"}, {"k": "결과", "v": "위약금 50% 감경"}], ["위약금 없이"],
        review="1급 감염병 여부가 상황에 없다 — 조건 확인이 정답일 수도 있음(라벨러 판단)")

    # 5) 표준약관 개인 사유 — 해당 4 · 해당 안 됨 2 (6)
    personal = [
        ("본인이 독감에 걸려 참가할 수 없어", True, "본인 질병"),
        ("이모가 돌아가셔서", True, "3촌 이내 친족 사망"),
        ("남편이 수술로 5일 동안 입원하게 돼", True, "배우자 3일 이상 입원"),
        ("아이가 장염으로 4일 입원해서 출발 때까지 퇴원이 어려워", True, "직계비속 3일 이상 입원"),
        ("사촌 형이 돌아가셔서", False, "사촌은 4촌 — 3촌 이내가 아니다"),
        ("어머니가 하루 입원하셨다가 출발 전에 퇴원하실 예정이지만 걱정돼서", False, "입원 3일 미만 · 출발 전 퇴원"),
    ]
    for i, (why, ok, note) in enumerate(personal):
        dep = base + timedelta(days=60 + i)
        notice = dep - timedelta(days=1)
        if ok:
            facts = [{"k": "사유", "v": note}, {"k": "결과", "v": "위약금 없이 해제 가능"}]
            gold, req, forbidden = [S["t1_personal"]], [S["t1_personal"]], ["20%"]
        else:
            facts = [{"k": "판단", "v": f"위약금 없는 해제 사유 아님 ({note})"},
                     {"k": "결과", "v": "여행자 사유 기준 — 숙박 1일 전 요금의 20% 배상"}]
            gold, req, forbidden = [S["t1_personal"], S["t2_traveler"]], [S["t1_personal"], S["t2_traveler"]], ["위약금 없이"]
        add("F", f"출발 {_day(dep)}인 1박 2일 국내 여행 상품을 예약했는데, {why} {_day(notice)}에 취소하려 합니다. 위약금을 내야 하나요?",
            "answer", gold, facts, forbidden, required=req,
            review="" if ok else "개인 사유 해당 여부 → 여행자 사유 표로 넘어가는 두 절 연결",
            meta={"departure": str(dep), "days_before": 1})

    # 6) 공연 관객 환급 (8)
    show = base + timedelta(days=70)
    for days in (12, 10, 8, 5, 2, 0):
        ded = show_deduction(days)
        req_day = show - timedelta(days=days)
        when = "공연 당일 공연 시작 2시간 전" if days == 0 else _day(req_day)
        result = "전액 환급" if ded is None else f"{ded}% 공제 후 환급"
        add("D" if days in (10,) else "C",
            f"{_day(show)} 저녁 뮤지컬 표를 한 달 전에 예매했습니다. 사정이 생겨 {when}에 표를 취소하려 합니다. 얼마나 돌려받나요?",
            "answer", [S["t3_show_refund"]],
            [{"k": "요구 시점", "v": f"공연 {_when(days)}"}, {"k": "결과", "v": result}],
            [f"{p}% 공제" for p in (10, 20, 30, 90) if p != ded] + ([] if ded is None else ["전액 환급"]),
            review="경계일 — 10일 전 날짜 세는 법 확인" if days == 10 else "", meta={"days_before": days})
    add("C", f"{_day(show)} 콘서트 표를 어제 저녁 9시에 예매했는데, 오늘 오후 3시에 마음이 바뀌어 취소하려 합니다(공연까지 5일 넘게 남음).",
        "answer", [S["t3_show_refund"]],
        [{"k": "조건", "v": "예매 후 24시간 이내 · 공연 3일 전까지"}, {"k": "결과", "v": "전액 환급"}], ["20% 공제"],
        review="비영업일은 시간 계산에서 뺀다 — 예매 요일이 주말이 아닌지 확인")
    add("E", "이틀 뒤 공연 표를 오늘 아침에 예매했는데 몇 시간 만에 취소하려 합니다. 예매하고 하루 안 지났으니 전액 환불되나요?",
        "answer", [S["t3_show_refund"]],
        [{"k": "판단", "v": "공연 3일 전이 지나 24시간 전액 환급 조건에 해당하지 않음"}, {"k": "결과", "v": "30% 공제 후 환급"}],
        ["전액 환급"])

    # 7) 공연 취소 (3)
    for why, result, forbidden in (
        ("주최 측 사정으로 공연이 취소됐다는 문자를 받았습니다", "입장료 환급 + 입장료의 10% 배상", ["입장료만 환급"]),
        ("태풍 때문에 야외 공연이 취소됐습니다", "입장료 환급(배상 없음)", ["10% 배상"]),
        ("공연 당일 주연 배우가 예고 없이 바뀌었습니다", "입장료 환급 + 입장료의 10% 배상", ["환급 불가"]),
    ):
        add("E", f"예매한 공연에 대해 묻습니다. {why}. 어떻게 보상받을 수 있나요?", "answer", [S["t3_show_cancel"]],
            [{"k": "결과", "v": result}], forbidden)

    # 8) 레저 · 체육시설 (5)
    leisure = [
        ("스키장 리프트가 고장 나서 예약한 날 거의 타지 못했습니다", [S["t3_facility"]], "이용 시기별 금액 환급 또는 동급 시설 대체", ["전액 환급만"]),
        ("예약하고 갔는데 정원이 꽉 찼다며 입장을 못 했습니다", [S["t3_facility"]], "이용 시기별 금액 환급 또는 동급 시설 대체", ["환급 불가"]),
        ("패러글라이딩 체험이 광고 영상과 전혀 다르게 진행됐습니다", [S["t3_ad"]], "이용료 전액 환급", ["10% 공제"]),
        ("다음 주 서핑 강습을 예약했는데 개인 사정으로 시작 전에 취소하려 합니다", [S["t3_consumer"]], "이용료에서 위약금(10분의 1)을 뺀 금액 환급", ["전액 환급"]),
        ("업체가 강사를 못 구했다며 시작 전에 수상스키 강습을 취소했습니다", [S["t3_biz"]], "이용료 + 위약금(10분의 1) 반환", ["위약금을 빼고"]),
    ]
    for why, gold, result, forbidden in leisure:
        add("C", f"{why}. 돈을 얼마나 돌려받을 수 있나요?", "answer", gold, [{"k": "결과", "v": result}], forbidden)

    # 9) 모호 — 조건 확인 (4)
    for text, gold in (
        ("다음 주 여행을 취소하면 얼마나 돌려받을 수 있는지 그냥 물어보고 싶습니다(언제 · 왜 취소하는지, 어떤 여행인지는 말하지 마세요)",
         [S["t2_traveler"], S["t2_agency"]]),
        ("공연 표를 환불하고 싶다고만 물어보세요(공연 날짜 · 예매 시각은 말하지 마세요)", [S["t3_show_refund"], S["t3_show_cancel"]]),
        ("여행사가 여행을 취소했다는 연락을 받았다고만 말하세요(언제 연락받았는지, 이유는 말하지 마세요)",
         [S["t2_agency"], S["t2_minimum"], S["t2_force"]]),
        ("체험 예약을 취소하면 위약금이 있는지 물어보세요(누구 사정인지, 언제인지는 말하지 마세요)", [S["t3_consumer"], S["t3_biz"]]),
    ):
        add("G", text, "clarify", gold, [{"k": "행동", "v": "빠진 조건(시점 · 사유 · 종류)을 묻거나 경우별로 나눠 답함"}],
            ["단정한 비율 하나만 제시"], caveat=False)

    # 10) 범위 밖 (4)
    for text in ("일본 오사카 패키지 여행을 취소하면 위약금이 얼마인지 궁금합니다",
                 "제주 가는 항공권을 취소하면 수수료가 얼마인지 궁금합니다",
                 "호텔 앱으로 직접 예약한 서울 호텔을 취소하면 환불되는지 궁금합니다",
                 "여행사가 환불을 안 해 줘서 소송을 하려는데 절차를 알려 달라고 하세요"):
        add("H", text, "out_of_scope", [], [{"k": "행동", "v": "자료로 확인할 수 없다고 안내 + 업체 약관 · 기관 확인 권유"}],
            ["국내여행 기준 비율을 그대로 적용"], caveat=False)
    return cards


# ── LLM 카드 ──────────────────────────────────────────────────────────────
#: ★`[2026-10-16 사용자 결정]` 설문 동행(`party`)은 접수 문항이 묻지 않아 비어 있다 — 카드 설문에 넣지 않는다.
#:  아이 · 어르신은 고객이 이번 문장에서 직접 말할 때만(2순위) 쓴다. 설문 항목끼리는 순서가 없다(계획서 1-1).
#: 속성 — `inferable` 은 후보 정보(이름 · 관광공사 분류 · 거리)만으로 라벨러가 판단할 수 있는가
ATTR = {
    "indoor": ("실내", True), "outdoor": ("야외", True), "history": ("역사 유적", True), "nature": ("자연 · 산책", True),
    "experience": ("직접 하는 체험", True), "culture": ("전시 · 공연", True), "shopping": ("쇼핑", True),
    "leisure": ("몸을 쓰는 레저", True), "night_view": ("야경 · 전망", True), "kid": ("아이와 함께 하기 좋음", False),
    "low_walking": ("많이 걷지 않음", False), "none": ("특별한 선호 없음", True),
}

TEXT_CUES = [  # (원래 장소, 시각, 바뀐 사유, 동행, 작성자에게 줄 바람, 속성)
    ("북촌한옥마을", "토요일 14:00", "비 예보로 야외 일정이 어렵다는 안내를 받았습니다", "친구 2명과", "비를 피할 수 있는 곳이면 좋겠습니다", "indoor"),
    ("서울숲", "일요일 10:00", "미세먼지가 '매우 나쁨'이라는 안내를 받았습니다", "가족 4명이", "바깥 공기를 피하고 싶습니다", "indoor"),
    ("낙산공원", "화요일 13:00", "폭염 경보가 내려졌습니다", "연인과", "시원한 실내에서 보내고 싶습니다", "indoor"),
    ("국립중앙박물관", "월요일 10:00", "가 보니 정기 휴관일이었습니다", "친구 1명과", "오전 내내 실내에만 있어서 바깥 바람을 쐬고 싶습니다", "outdoor"),
    ("경복궁", "화요일 11:00", "그날이 휴궁일이라는 걸 알았습니다", "7살 아이와", "아이가 직접 만들어 보는 체험을 하고 싶어 합니다", "experience"),
    ("남산서울타워", "수요일 15:00", "전망대가 점검 중이라는 안내를 받았습니다", "부모님과", "부모님이 옛 궁궐이나 역사 유적을 좋아하십니다", "history"),
    ("동대문디자인플라자", "목요일 14:00", "전시 교체로 문을 닫았습니다", "친구 3명과", "나무 많은 곳을 걷고 싶습니다", "nature"),
    ("광장시장", "월요일 12:00", "임시 휴무라는 공지를 봤습니다", "직장 동료와", "미술 전시 같은 걸 보고 싶습니다", "culture"),
    ("창덕궁", "월요일 10:00", "휴궁일이었습니다", "친구 2명과", "공방 같은 데서 뭔가 직접 만들어 보고 싶습니다", "experience"),
    ("하늘공원", "금요일 16:00", "강풍 주의보로 출입이 통제됐습니다", "외국인 친구와", "친구에게 줄 기념품을 사고 싶습니다", "shopping"),
    ("서울식물원", "월요일 10:00", "휴관일이었습니다", "운동 좋아하는 친구와", "몸을 움직이는 활동을 하고 싶습니다", "leisure"),
    ("경복궁 야간관람", "토요일 19:00", "표가 매진됐습니다", "연인과", "밤에 야경을 볼 수 있는 곳이면 좋겠습니다", "night_view"),
    ("북한산 둘레길", "일요일 09:00", "호우 주의보가 내려졌습니다", "70대 부모님과", "부모님 무릎이 안 좋아 많이 걷지 않는 곳이 좋습니다", "low_walking"),
    ("낙산성곽길", "토요일 10:00", "공사로 길 일부가 막혔습니다", "유모차를 끄는 가족이", "유모차로 다니기 쉬운 곳이 좋겠습니다", "low_walking"),
    ("리버시티수상스키장", "일요일 14:00", "강풍으로 운영이 취소됐습니다", "외국인 친구와", "한국 전통 문화를 보여 주고 싶습니다", "history"),
    ("어린이대공원", "토요일 11:00", "비가 많이 온다는 예보가 있습니다", "5살 아이와", "아이가 지쳐서 실내에서 쉬엄쉬엄 놀았으면 합니다", "indoor"),
]

SURVEY_ONLY = [  # (원래 장소, 시각, 사유, 설문, 속성)
    ("서울숲", "토요일 10:00", "비 예보가 있습니다", {"indoor_outdoor": {"activity": "indoor"}}, "indoor"),
    ("롯데월드타워 전망대", "일요일 15:00", "점검으로 닫았습니다", {"theme": "역사"}, "history"),
    ("국립현대미술관", "월요일 11:00", "휴관일입니다", {"theme_details": ["체험"]}, "experience"),
    ("남산공원", "수요일 14:00", "폭염 경보가 내려졌습니다", {"theme_details": ["전시 관람"]}, "culture"),
    ("코엑스몰", "목요일 13:00", "정전으로 일부 구역이 닫혔습니다", {"theme": "자연"}, "nature"),
    ("덕수궁", "월요일 10:00", "휴궁일입니다", {"custom_answers": {"활동": "전시 보는 걸 좋아해요"}}, "culture"),
    ("리버시티수상스키장", "토요일 13:00", "강풍으로 운영이 취소됐습니다", {"theme": "역사"}, "history"),
    ("국립중앙박물관", "월요일 10:00", "휴관일입니다", {"indoor_outdoor": {"activity": "outdoor"}}, "outdoor"),
]

CONFLICTS = [  # (원래 장소, 사유, 설문, 오늘의 바람, 이기는 속성, 지는 속성)
    ("서울숲", "비 예보가 있습니다", {"indoor_outdoor": {"activity": "outdoor"}, "theme": "자연"}, "오늘은 비가 오니 실내로 가고 싶습니다", "indoor", "outdoor"),
    ("경복궁", "휴궁일입니다", {"theme": "역사"}, "아이가 역사는 지루해해서 오늘은 체험 같은 걸 하고 싶습니다", "experience", "history"),
    ("국립중앙박물관", "휴관일입니다", {"indoor_outdoor": {"activity": "indoor"}}, "날씨가 너무 좋아서 오늘은 밖에 있고 싶습니다", "outdoor", "indoor"),
    ("명동", "행사로 너무 붐빕니다", {"theme": "쇼핑"}, "오늘은 쇼핑 말고 조용히 전시를 보고 싶습니다", "culture", "shopping"),
    ("하늘공원", "강풍으로 통제됐습니다", {"theme": "자연"}, "일행이 발목을 다쳐서 많이 걷지 않는 곳이 좋겠습니다", "low_walking", "nature"),
    ("북촌전통공예체험관", "예약이 마감됐습니다", {"theme_details": ["체험"]}, "오늘은 뭘 만들기보다 그냥 구경만 하고 싶습니다", "culture", "experience"),
    ("어린이대공원", "비 예보가 있습니다", {"theme": "자연"}, "오늘은 어른 둘이서 역사 유적에 가고 싶습니다", "history", "nature"),
    ("리버시티수상스키장", "강풍으로 취소됐습니다", {"theme": "레저"}, "너무 피곤해서 오늘은 앉아서 보는 실내 공연이나 전시가 좋겠습니다", "culture", "leisure"),
    ("동대문디자인플라자", "전시 교체로 닫았습니다", {"indoor_outdoor": {"activity": "any"}, "theme": "문화"}, "바깥 산책을 하고 싶습니다", "nature", "culture"),
    ("인사동 쌈지길", "임시 휴무입니다", {"custom_answers": {"활동": "사진 찍기 좋은 곳"}}, "사진은 이미 많이 찍어서 오늘은 역사 공부가 되는 곳이 좋겠습니다", "history", "night_view"),
]

TIES = [  # 같은 속성 후보가 둘 — 허용 답 2곳
    ("북촌한옥마을", "비 예보가 있습니다", "비를 피할 수 있는 실내면 어디든 좋습니다", "indoor"),
    ("남산서울타워", "점검 중입니다", "궁궐 같은 역사 유적이면 좋겠습니다", "history"),
    ("코엑스 아쿠아리움", "정전으로 닫았습니다", "공원이나 숲길을 걷고 싶습니다", "nature"),
    ("국립중앙박물관", "휴관일입니다", "직접 해 보는 체험이면 좋겠습니다", "experience"),
    ("광장시장", "임시 휴무입니다", "전시나 공연을 보고 싶습니다", "culture"),
    ("서울숲", "미세먼지가 매우 나쁩니다", "실내에서 놀 수 있으면 됩니다", "indoor"),
]

TRAPS = [  # 입력에 없는 정보 요구 — 지어내지 않아야 한다
    ("가장 싼 곳으로 해 주세요", ["원", "무료", "저렴", "입장료"]),
    ("덜 붐비는 곳으로 바꿔 주세요", ["한산", "붐비지 않", "혼잡", "사람이 적"]),
    ("후기 좋은 곳으로 골라 주세요", ["후기", "평점", "리뷰", "인기"]),
    ("주차하기 편한 곳이면 좋겠어요", ["주차"]),
    ("입장료 없는 곳으로 해 주세요", ["무료", "입장료", "원"]),
    ("지금 줄 안 서고 바로 들어갈 수 있는 곳이요", ["대기", "줄", "바로 입장"]),
    ("요즘 SNS에서 인기 많은 곳으로요", ["인기", "SNS", "핫플"]),
    ("와이파이 잘 되는 곳이면 좋겠어요", ["와이파이", "wifi"]),
]

OUT_OF_LIST = [
    "목록 말고 롯데월드로 바꿔 주세요",
    "원래 가려던 곳을 그냥 내일로 미뤄 주세요",
    "보여 준 곳 말고 다른 데 추천해 주세요",
    "세 곳 다 마음에 안 들어요",
    "강남 쪽 아무 데나 다른 곳으로 해 주세요",
    "후보에 없는 남산타워로 가고 싶어요",
]

NO_CUE = [
    "다른 곳으로 바꿔 주세요", "아무 데나 괜찮아요", "가까운 곳이면 돼요",
    "알아서 정해 주세요", "추천해 준 순서대로 갈게요", "네, 바꿔 주세요",
]
NO_CUE_ORIGINS = [("경복궁", "휴궁일입니다"), ("서울숲", "비 예보가 있습니다"), ("남산서울타워", "점검 중입니다"),
                  ("국립중앙박물관", "휴관일입니다"), ("광장시장", "임시 휴무입니다"), ("하늘공원", "강풍으로 통제됐습니다")]


def llm_cards(rng: random.Random) -> list[dict]:
    cards: list[dict] = []

    def add(stratum, situation, survey, target, behavior, binding, *, forbidden=None, hint=None, note=""):
        attr = target.get("attribute", "none")
        cards.append({
            "card_id": f"L-{len(cards) + 1:02d}", "kind": "llm", "stratum": stratum, "situation": situation,
            "writer_hint": hint or "", "origin_hint": target.pop("origin"), "survey": survey,
            "preference_target": {**target, "label": ATTR[attr][0], "inferable": ATTR[attr][1]},
            "expected_behavior": behavior, "binding": binding, "forbidden_claims": forbidden or [],
            "needs_review": note or ("" if ATTR[attr][1] else "후보 이름 · 분류만으로 판단이 갈릴 수 있음 — 2인 라벨 필수"),
            "label_by": "card-draft",
        })

    reorder = {"need_match": 1, "need_nonmatch": 1, "code_first_matches": False}
    # A. 단서 없음 (6)
    for (origin, why), text in zip(NO_CUE_ORIGINS, NO_CUE):
        add("A", f"서울 여행 중 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"특별히 바라는 것은 없습니다. 챗봇에게 바꿔 달라는 말을 써 주세요.",
            {}, {"origin": origin, "cue_source": "none", "attribute": "none"}, "keep_code_order",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None}, hint=f"예: 「{text}」처럼 취향 없이")
    # B. 고객 문장 단서 (16)
    for origin, when, why, party, want, attr in TEXT_CUES:
        add("B", f"{party} 서울 여행 중입니다. {when}에 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"{want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            {}, {"origin": origin, "cue_source": "customer_text", "attribute": attr}, "reorder_to_match", dict(reorder))
    # B. 설문만 단서 (8)
    for origin, when, why, survey, attr in SURVEY_ONLY:
        add("B", f"서울 여행 중입니다. {when}에 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 "취향은 말하지 말고 짧게 바꿔 달라고만 써 주세요.",
            survey, {"origin": origin, "cue_source": "survey", "attribute": attr}, "reorder_to_match", dict(reorder))
    # C. 단서 충돌 (10)
    for origin, why, survey, want, win, lose in CONFLICTS:
        add("C", f"서울 여행 중입니다. {origin}에 가려 했는데 {why}. 여행 전 설문에는 평소 취향을 적어 두었지만, "
                 f"오늘은 {want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            survey, {"origin": origin, "cue_source": "customer_text_over_survey", "attribute": win, "loses_to": lose},
            "reorder_to_match", {"need_match": 1, "need_nonmatch": 1, "need_survey_match": 1, "code_first_matches": False},
            hint="설문 내용은 문장에 쓰지 마세요 — 오늘 바라는 것만")
    # D. 동점 (6)
    for origin, why, want, attr in TIES:
        add("D", f"서울 여행 중입니다. {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"{want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            {}, {"origin": origin, "cue_source": "customer_text", "attribute": attr}, "reorder_to_match",
            {"need_match": 2, "need_nonmatch": 1, "code_first_matches": False}, note="허용 답 2곳 — 두 후보 모두 맞음")
    # E. 함정 — 입력에 없는 정보 (8)
    origins = rng.sample([o for o, *_ in TEXT_CUES], len(TRAPS))
    for origin, (want, words) in zip(origins, TRAPS):
        add("E", f"서울 여행 중 {origin} 일정이 바뀌어 앱이 대체 장소 3곳을 보여 줬습니다. 이렇게 부탁하고 싶습니다: "
                 f"「{want}」. 같은 뜻으로 자연스럽게 1~2문장 써 주세요.",
            {}, {"origin": origin, "cue_source": "unavailable_info", "attribute": "none"}, "no_fabrication",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None}, forbidden=words,
            note="후보 정보에 없는 기준 — 순서는 무엇이든 허용, 이유에 지어낸 사실이 있으면 근거 위반")
    # F. 범위 이탈 (6)
    origins = rng.sample([o for o, *_ in CONFLICTS], len(OUT_OF_LIST))
    for origin, want in zip(origins, OUT_OF_LIST):
        add("F", f"서울 여행 중 {origin} 일정이 바뀌어 앱이 대체 장소 3곳을 보여 줬습니다. 이렇게 말하고 싶습니다: "
                 f"「{want}」. 같은 뜻으로 자연스럽게 1~2문장 써 주세요.",
            {}, {"origin": origin, "cue_source": "out_of_list", "attribute": "none"}, "valid_ids_only",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None},
            forbidden=["롯데월드", "남산타워", "내일로"], note="후보 밖 id · 장소를 1순위로 내면 위험 오답. 순서는 코드 순서 유지가 기본")
    return cards


# ── 출력 ─────────────────────────────────────────────────────────────────
def write(cards: list[dict], name: str, rng: random.Random) -> None:
    with (OUT / f"cards_{name}_{VERSION}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for card in cards:
            fh.write(json.dumps(card, ensure_ascii=False) + "\n")
    order = cards[:]
    rng.shuffle(order)  # ★묶음이 이어지지 않게 섞는다 — 작성자가 패턴을 읽지 않게
    with (OUT / f"sheet_{name}_{VERSION}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["카드", "작성자", "상황", "참고", "고객이 보낼 말(1~2문장)", "메모"])
        for i, card in enumerate(order):
            out.writerow([card["card_id"], f"작성자{i % WRITERS + 1}", card["situation"], card.get("writer_hint", ""), "", ""])


def main() -> None:
    rng = random.Random(SEED)
    rag, llm = rag_cards(rng), llm_cards(rng)
    assert len(rag) == 60 and len(llm) == 60, (len(rag), len(llm))
    write(rag, "rag", rng)
    write(llm, "llm", rng)
    for name, cards in (("rag", rag), ("llm", llm)):
        strata: dict[str, int] = {}
        for c in cards:
            strata[c["stratum"]] = strata.get(c["stratum"], 0) + 1
        review = sum(1 for c in cards if c["needs_review"])
        print(f"{name}: {len(cards)}장 · 묶음 {dict(sorted(strata.items()))} · 확인 필요 {review}/{len(cards)}")


if __name__ == "__main__":
    main()
