# -*- coding: utf-8 -*-
"""접수 입구의 **빠른 거름** — 빈 글 · 분명히 여행과 무관한 글은 모델 읽기 전에 바로 돌려보낸다. `[2026-10-19 사용자 결정]`

설계 `wiki/records/plans/2026-10-19_로딩설문_읽은칸빼고_빈칸만묻기.md` §5 · 계약 `wiki/external/rest-endpoints/web-intakes.md` 「접수 입구의 빠른 거름」 · D-025 덧붙임.

★왜. 「파이썬 for 루프에 대해서 알려줘」 같은 글도 모델 읽기를 다 거친 뒤(오라클 ARM 4초 · 24초)에야 「일정 없음」이 됐고, 그동안 로딩 설문이 떴다.
★**규칙만** 쓴다 — 모델 · 유료 호출 0, DB 는 장소 목록 한 번만 읽는다(1초 안).
★**애매하면 거르지 않는다** — 여행 단서가 **하나라도** 있으면 지금처럼 읽는다. 잘못 거르는 것보다 늦게 읽는 쪽이 손해가 작다는 판단이다(설계 §5).
    여행 단서 = 날짜 · 시각 · 서울 장소(우리 장소 목록 · 대표 장소 정답표 · 지명 사전 · 「역 · 궁 · 시장 · 공원 · 박물관 · 호텔 · 식당 · 카페」류 꼬리말) · 여행 낱말.
★**파일이 붙은 접수는 거르지 않는다** — 사진 · PDF 는 받아쓰기 전에는 내용을 모른다. 한글 · 로마자가 아닌 글(일본어 · 중국어 등)도 거르지 않는다(이 규칙이 그 말의 단서를 모른다).
★거른 접수는 원문(글 원본 줄)과 걸린 규칙(`trip_intakes.screened`)을 남긴다 — 사후에 오판을 셀 수 있게.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable

#: 날짜 · 기간 말
_DATE = re.compile(r"\d{4}\s*[-./년]\s*\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일?|\d{1,2}\s*/\s*\d{1,2}|\d+\s*일\s*차|\d+\s*박|\d+\s*일\s*(?:동안|간)|"
                   r"오늘|내일|모레|글피|주말|평일|[월화수목금토일]요일|day\s*\d+|\bd\d\b", re.IGNORECASE)
#: 시각 말
_TIME = re.compile(r"\d{1,2}\s*시|\d{1,2}\s*:\s*\d{2}|오전|오후|아침|점심|저녁|새벽|밤에|\d{1,2}\s*(?:am|pm)\b|\b(?:morning|noon|evening|night)\b",
                   re.IGNORECASE)
#: 서울 장소의 꼬리말 · 장소 종류 말(이름 없이 종류만 적어도 여행 단서다 — 「성수 예약 식당」)
_PLACE_TAIL = re.compile(r"[가-힣A-Za-z0-9]+(?:역|궁|시장|공원|박물관|미술관|전시관|기념관|호텔|숙소|게스트하우스|식당|카페|맛집|타워|한옥마을|거리|길|"
                         r"광장|성당|사찰|절|산|한강|섬|전망대|백화점|쇼핑몰|아울렛|몰|극장|공연장|놀이공원|랜드|월드)\b|"
                         r"식당|카페|맛집|호텔|숙소|시장|공원|박물관|미술관|공연|전시|축제|투어|체크인|체크아웃|"
                         r"\b(?:station|palace|market|museum|park|hotel|cafe|restaurant|tower|gallery|temple)\b", re.IGNORECASE)
#: 여행 낱말
_TRAVEL = re.compile(r"여행|일정|관광|코스|구경|방문|놀러|나들이|데이트|서울|먹고|먹기|가고\s*싶|가볼|가 볼|들르|들를|숙박|투숙|이동|택시|지하철|버스|"
                     r"\b(?:trip|travel|itinerary|tour|visit|sightseeing|seoul|plan)\b", re.IGNORECASE)
#: 분명히 다른 일 — 걸린 규칙을 남길 때만 쓴다(여행 단서가 없을 때만 거르므로 이 말만으로 거르지는 않는다)
_OTHER_TASK = re.compile(r"파이썬|python|코드|코딩|프로그래밍|함수|변수|알고리즘|자바스크립트|javascript|java|sql|에러|오류 고쳐|숙제|과제|리포트|논문|"
                         r"번역해|수학|방정식|미적분|계산해|요약해|시 써|소설", re.IGNORECASE)
#: 이 규칙이 아는 글자(한글 · 로마자 · 숫자 · 기호). 그 밖의 글자가 섞이면(일본어 · 중국어 …) 거르지 않는다
_OTHER_SCRIPT = re.compile(r"[぀-ヿ㐀-䶿一-鿿Ѐ-ӿ฀-๿؀-ۿ]")


def _flat(text: str) -> str:
    return re.sub(r"[\s·\-_/]+", "", unicodedata.normalize("NFKC", text)).lower()


def travel_clue(text: str, *, place_names: Callable[[str], bool] | None = None, area_keys: set[str] | None = None,
                landmark_keys: set[str] | None = None) -> str | None:
    """글에 여행 단서가 있나 — 있으면 무엇이 걸렸는지(`date` · `time` · `place` · `travel`), 없으면 None.

    `place_names(text)` — 우리 장소 목록에 글 속 이름이 있나(DB). `area_keys` · `landmark_keys` — 지명 사전 · 대표 장소 정답표의 열쇠(띄어쓰기 없이 소문자)."""
    if _DATE.search(text):
        return "date"
    if _TIME.search(text):
        return "time"
    if _PLACE_TAIL.search(text):
        return "place"
    if _TRAVEL.search(text):
        return "travel"
    flat = _flat(text)
    for keys in (landmark_keys or set(), area_keys or set()):
        if any(len(key) >= 2 and key in flat for key in keys):
            return "place"
    if place_names is not None and place_names(text):
        return "place"
    return None


def screen(text: str | None, *, has_files: bool, place_names: Callable[[str], bool] | None = None,
           area_keys: set[str] | None = None, landmark_keys: set[str] | None = None) -> dict[str, str] | None:
    """거를 접수면 `{code: empty | off_topic, rule}`, 지금처럼 읽을 접수면 None.

    - 파일이 붙었다 → 거르지 않는다.
    - 글 · 파일이 모두 비었다 → `empty`.
    - 한글 · 로마자가 아닌 글자가 섞였다 → 거르지 않는다(단서를 모른다).
    - 여행 단서가 하나도 없다 → `off_topic`(`rule` 은 다른 일 낱말이 있었으면 `other_task`, 아니면 `no_travel_clue`)."""
    if has_files:
        return None
    body = (text or "").strip()
    if not body:
        return {"code": "empty", "rule": "empty"}
    if _OTHER_SCRIPT.search(body):
        return None
    if travel_clue(body, place_names=place_names, area_keys=area_keys, landmark_keys=landmark_keys):
        return None
    return {"code": "off_topic", "rule": "other_task" if _OTHER_TASK.search(body) else "no_travel_clue"}


__all__ = ["screen", "travel_clue"]
