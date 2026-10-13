# -*- coding: utf-8 -*-
"""재난 문자 본문이 **여행 일정에 영향을 주는 일**을 말하나 — 공용 판정 한 곳 `[2026-10-13 사용자 지시]`.

★왜. 재해구분 「기타」로 온 문자는 앱이 통째로 버렸다. 2026 서울 「기타」 고유 문자 208건 중 189건이 여행에 영향이 있었다
  (버스 파업 · 마라톤 통제 · 고가 붕괴 · 정전 등 — `wiki/records/reports/2026-10-13_0200_기타문자_여행영향_실수율.md`).
  재해구분 칸이 비거나 「기타」여도 본문으로 무슨 일인지 가른다.
★무엇을 내나 — 영향 종류 하나 또는 None(영향 없음):
    road     도로 통제 · 정체 · 사고 · 결빙 · 행사 교통 혼잡     bus      버스 파업 · 운행 중단
    rail     지하철 · 열차 운행 중단 · 무정차                      utility  정전 · 단수 · 가스 공급 · 통신 장애
    crowd    인파 밀집 · 축제 · 공연                               hazard   화재 · 붕괴 · 폭발 · 가스 누출 · 방류 · 야생동물
    outdoor  폭염 · 한파 · 대기질 · 산불 입산 통제 등 야외 활동 위험
    closure  장소가 문을 닫음 — 휴관 · 휴장 · 폐쇄 · 관람 · 입장 · 출입 중단 (`[2026-10-13]` 활동 팀 요청 1번)
★`[2026-10-13]` closure 를 더한 이유: 「경복궁 임시 휴관」 · 「창덕궁 오늘 폐쇄」 · 「운영 중단」이 어느 종류에도 안 걸려 버려졌다 — 활동 팀이
  그 장소를 막지 못하고 「성립」으로 답했다. 「경복궁 관람 전면 중단」만 「관람」 낱말 때문에 crowd 로 **우연히** 넘어갔다.
  누구 장소인지는 여기서 가리지 않는다 — 장소 이름 대조는 활동 팀 판정(`place_closure_keywords`)이 한다.
★놓치는 쪽이 위험하다(일정 감시에 안 간다). 그래서 넓게 잡고, 분명한 생활 안내(물놀이 수칙 · 실종자 찾기 · 병원 안내 · 예방 캠페인)만 뺀다.
★규칙은 전국 재난 문자(2023-09 ~ 2026-10) 정답 세트의 dev 몫만 보고 만들었다. 숫자는 holdout 몫으로 낸다(`datasets/safety/disaster_msg_korea_2023_2026`).
★남은 한계: 낱말 규칙이다. 새 말투는 놓칠 수 있다 — 2차 확인 모델과 「하나라도 영향 있으면」으로 합친다(OR).
"""
from __future__ import annotations

import re
from typing import Callable

#: 영향이 없는 생활 안내 — 이것만 있고 아래 사건 낱말이 없으면 None
_NOT_TRAVEL = re.compile(
    r"찾습니다|실종|배회|구명조끼|물놀이\s*(?:시|사고|안전)|수상\s*안전|안전\s*수칙|준비운동|문\s*여는\s*(?:병|의료|약국)|병·?의원|응급의료포털|"
    r"사칭|보이스피싱|스미싱|사기\s*(?:주의|피해|전화|문자)|투표|선거|접종|예방접종|헌혈|에어쇼|비행\s*소음|"
    r"(?:화재|산불)\s*예방(?!.{0,20}(?:통제|입산\s*금지|대피))|소각\s*(?:행위\s*)?금지|화기\s*(?:사용\s*)?(?:주의|금지)")
#: 실제 사건이 났다는 말 — 이게 있으면 위 생활 안내 낱말이 있어도 영향 있음으로 본다
#: ★「발생할 위험」 · 「안전사고」 같은 캠페인 말은 사건이 아니다 — 「발생」은 이미 났을 때만, 「사고」 낱말은 안 본다
_EVENT = re.compile(r"발생(?!할|\s*위험|하지|빈도|될\s*수|되지|에\s*유의|\s*우려|\s*시\b|\s*시\s)|통제|중단|중지|운행\s*(?:중단|중지|불가)|대피|누출|정전|단수|붕괴|전복|"
                    r"파업|출몰|출현|탈출|결빙|빙판|살얼음|블랙\s*아이스|입산\s*(?:금지|통제|자제)|통행|휴관|휴장|폐관|폐장|폐쇄")

#: 장소가 문을 닫는다는 말 — 휴관 · 휴장 · 폐쇄 · 관람 · 입장 · 출입 · 운영이 멈춘다. crowd 의 「관람」과 closure 가 같이 쓴다
_STOPS = r"\s*(?:을|를|이|가|은|는)?\s*(?:전면\s*|일시\s*|임시\s*|잠정\s*|당분간\s*)?(?:중단|중지|제한|불가|통제|취소|금지|폐쇄)"
#: 「폐쇄」는 도로 · 역에도 쓴다 — 시설 이름 뒤(몇 글자 안 · 사이에 도로 낱말 없이)에 올 때만 장소 닫힘으로 본다.
#:  한 글자 말(사 · 원 · 관)은 넣지 않는다 — 「도로 공사로 차로 폐쇄」의 「사」가 걸린다. 「시설」도 뺀다 — 「노후시설물 등 출입금지」 · 「시설 방문 외부인 출입통제」
_PLACES = (r"궁|궁궐|왕릉|박물관|미술관|기념관|전시관|도서관|체육관|문화원|수목원|식물원|동물원|공원|유원지|놀이공원|테마파크|광장|"
           r"전시실|전망대|체험장|물놀이장|놀이터|야영장|캠핑장|해수욕장|둘레길|탐방로|산성|성곽|사찰|정원|시장|쇼핑몰|백화점|타워")
_NOT_ROAD_GAP = r"(?:(?!도로|차로|차선|차량|터널|교량|지하차도|하상도로|언더패스|IC|나들목)[^.,!?\n]){0,8}?"

#: (종류, 패턴) — 위에서부터 처음 맞는 것. 순서가 우선순위다
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("bus", re.compile(r"버스.{0,15}(?:파업|운행\s*중단|운행하지|미운행|결행|감축)|파업.{0,20}버스|(?:시내|마을|농어촌|광역)\s*버스|셔틀\s*버스|복지카")),
    ("rail", re.compile(r"무정차|지하철|전철|열차|철도|\d\s*호선|KTX|SRT|ITX|경의중앙|선로|역\s*(?:출입|폐쇄)|trains?\s*skip|subway")),
    ("hazard", re.compile(r"화재|불이\s*나|폭발|붕괴|지반\s*침하|싱크홀|가스\s*(?:누출|유출)|누출|유출|암모니아|유독|매연|연기|방류|수문|"
                          r"멧돼지|사슴|야생동물|맹견|유기견|들개|곰\s|출몰|탈출|발파|진동|지진|해일|낙석|산사태|대피")),
    ("utility", re.compile(r"정전|단전|전력|변압기|단수|누수|상수(?:도|관)|급수|흐린\s*물|탁수|흙탕물|수돗물|용수|물\s*사용|통신\s*(?:장애|오류)|인터넷\s*장애|"
                           r"가스\s*(?:공급|중단)|도시가스")),
    # ★`[2026-10-13]` 「관람」 뒤에 중단 · 제한이 오면 인파가 아니라 장소 닫힘이다(아래 closure) — 「경복궁 관람 전면 중단」
    ("crowd", re.compile(r"인파|밀집|혼잡(?!.{0,6}(?:도로|교통))|축제|공연|콘서트|불꽃|드론\s*쇼|해맞이|해넘이|카운트다운|행사장|"
                         r"관람(?!" + _STOPS + r")|Crowds?|performance|festival|concert")),
    # ★`[2026-10-13]` 장소 닫힘 — crowd 다음(「불꽃축제 관람 … 축구장 출입 금지」는 인파), road 앞(「덕수궁 출입 통제」는 도로가 아니다)
    #   「출입 금지 · 통제」와 「폐쇄」는 시설 이름 뒤에서만 — 호우 문자의 「하천변 · 해안가 출입금지」(전국 5만 건 중 372건)는
    #   야외 위험 · 도로 그대로 둔다. 「문을 닫」은 넣지 않는다 — 「창문을 닫아」 · 「문을 닫아 황사 유입을 막고」가 걸린다.
    #   「밀폐장소」의 「폐장」도 뺀다
    ("closure", re.compile(r"휴관|휴장|임시\s*휴무|폐관|(?<!밀)폐장|"
                           r"(?:관람|입장|입관|개방|운영|탐방)" + _STOPS + r"|"
                           r"(?:" + _PLACES + r")" + _NOT_ROAD_GAP + r"(?:출입" + _STOPS + r"|폐쇄)|"
                           r"closed\s+to\s+(?:the\s+)?(?:public|visitors)|temporarily\s+closed")),
    ("road", re.compile(r"통제|우회|정체|차로|차선|교통|도로|통행|IC|JC|나들목|터널|고속도로|국도|교량|지하차도|하상도로|언더패스|"
                        r"사고|추돌|전복|고장\s*차량|결빙|빙판|살얼음|블랙\s*아이스|미끄럼|미끄러|눈길|제설|강설|폭설|마라톤|자전거\s*대회|"
                        r"closed|road|traffic")),
    ("outdoor", re.compile(r"폭염|무더위|온열|열대야|한파|강추위|영하|동파|오존|미세먼지|황사|대기\s*정체|강풍|태풍|호우|폭우|소나기|"
                           r"입산|등산|산행|야외|실외|하천|계곡|해수욕|산불|비상저감|건조")),
]


IMPACT_KINDS = ("road", "bus", "rail", "utility", "crowd", "hazard", "outdoor", "closure")
#: 영향 종류가 「가는 길」에 걸리는 것 — 나머지(utility · crowd · hazard)는 그 근처 장소, outdoor 는 야외 장소에만 건다
ROUTE_KINDS = frozenset({"road", "bus", "rail"})

#: 2차 확인 — 본문 → 영향 종류(IMPACT_KINDS 중 하나) · "none" · None(못 정함). 조립이 꽂는다(`notice_end_model.register_from_settings`)
_second_opinion: Callable[[str], str | None] | None = None


def set_second_opinion(judge: Callable[[str], str | None] | None) -> None:
    global _second_opinion
    _second_opinion = judge


def rule_impact(text: str | None) -> str | None:
    """낱말 규칙만으로 낸 여행 영향 종류. 영향이 없어 보이면 None."""
    text = " ".join(str(text or "").split())
    if not text:
        return None
    if _NOT_TRAVEL.search(text) and not _EVENT.search(text):
        return None
    for kind, pattern in _RULES:
        if pattern.search(text):
            return kind
    return None


def impact_detail(text: str | None) -> dict:
    """여행 영향 판정과 누가 냈는지 — `{"impact": 종류 | None, "by": "rule" | "model" | None}`.

    ★`[2026-10-13 사용자 결정]` **규칙 또는 모델**(OR) — 놓치는 쪽이 위험하다(감시에 안 간다). 규칙이 영향 있음이면 그대로 쓰고
      모델은 부르지 않는다. 규칙이 없음일 때만 모델에 묻는다. 모델을 못 부르면 규칙 결과(없음)다.
      전국 재난 문자 holdout 99건에서 규칙 놓침 2 · 모델 0 · 둘 중 하나 0(잘못 보냄 13/28 — `wiki/records/reports/2026-10-13_0430_전국재난문자_규칙보강.md`).
    """
    rule = rule_impact(text)
    if rule is not None:
        return {"impact": rule, "by": "rule"}
    if _second_opinion is not None:
        model = _second_opinion(" ".join(str(text or "").split()))
        if model in IMPACT_KINDS:
            return {"impact": model, "by": "model"}
        if model == "none":                            # 모델도 「영향 없음」이라 했다(못 정함 None 과 구분 — 걸러진 문자 기록에 쓴다)
            return {"impact": None, "by": None, "model_checked": True,
                    "prompt_version": getattr(_second_opinion, "prompt_version", None)}
    return {"impact": None, "by": None}


def travel_impact(text: str | None) -> str | None:
    """본문 하나의 여행 영향 종류(규칙 또는 모델). 영향이 없어 보이면 None."""
    return impact_detail(text)["impact"]


__all__ = ["IMPACT_KINDS", "ROUTE_KINDS", "impact_detail", "rule_impact", "set_second_opinion", "travel_impact"]
