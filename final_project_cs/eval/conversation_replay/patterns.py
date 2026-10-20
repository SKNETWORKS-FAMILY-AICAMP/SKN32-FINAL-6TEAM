# -*- coding: utf-8 -*-
"""봇 답 문구 판정표 — 실패형 답 · 완료를 말한 답 · 사실 문장 · 열린 질문 · 짧은 답 모양. `[2026-10-19]`

기준선 코드(결정 단위)의 답에는 구조화된 「바꾼 항목」 칸이 없어서 **문구로** 가른다(재생 시험 계획 「채점」 ① 거짓 완료).
문구는 제품 답 문장(`trip_replies.py` · `decision_unit` 경로 · `case_dispatch.py`)에서 뽑았다. 못 가르는 답은 「판정 불가」로 둔다 — 통과로 세지 않는다.
"""
from __future__ import annotations

import re
import unicodedata

#: 실패형 답 — 유형별(재생 시험 계획 ③ 「실패형 답」, 10-19 진단의 분류와 같은 이름)
FAIL_TYPES: dict[str, re.Pattern[str]] = {
    "모델 오류": re.compile(r"해석 모델 응답 오류|문장을 읽는 기능이 잠시 멈춰|분류하지 못해 처리하지 못"),
    "못 알아들음": re.compile(r"알아듣지 못|이해하지 못했|말씀을 정확히|다음 중 하나인가요"),
    "어느 일정": re.compile(r"어느 일정|어떤 일정을|무슨 일정|어느 일정을 물으신|가리키는 일정을 찾지"),
    "채팅에서 못 함": re.compile(r"채팅에서[^.\n]{0,20}(하지 못|할 수 없|못 해|안 돼)|화면에서 직접|아직 채팅에서"),
    "장소 못 찾음": re.compile(r"(장소|곳)[^.\n]{0,30}찾지 못|한 곳으로 찾지 못|찾지 못해 (그대로|일정은)"),
    "제목과 장소 다름": re.compile(r"제목의 「[^」]*」 자체 정보는 아니"),
    "처리 못 함": re.compile(r"요청을 처리하지 못했"),
}

#: 「바꿨다」류 완료 문구. 06 조립 스크립트의 DONE_RE 를 그대로 두고 부정형을 따로 뺀다.
DONE_RE = re.compile(r"(바꿨|바꿔 ?(두었|놨|드렸)|옮겼|옮겨 ?(두었|놨|드렸)|추가했|넣었|넣어 ?(두었|드렸)|뺐|삭제했|지웠|되돌렸|"
                     r"요청하신 대로|반영했|당겼|늦췄|미뤘|변경했|저장했|고르신 안으로)")
NOT_DONE_RE = re.compile(r"(바꾸지 않았|바꾸지는 않았|그대로 (두었|뒀)|적용하지 않았|저장하지 않았|못 바꿨|바꿀 수 없|"
                         r"바꾸지 않고|일정은 바꾸지|변경하지 않았)")
#: 지난 일을 말하는 완료(「이미 바꿨어요」)는 이 턴의 저장과 맞출 수 없다 → 판정 불가
PAST_DONE_RE = re.compile(r"(이미|아까|앞서|전에) [^.\n]{0,12}(바꿨|옮겼|넣었|뺐|되돌렸)")

#: 사실 문장 — 06 조립 스크립트의 FACT_RE 와 같은 낱말(영업 · 운영시간 · 가격 · 주소 · 날씨 · 막차 …)
FACT_RE = re.compile(r"(영업|운영 ?시간|문 ?여|문을 ?닫|휴무|휴관|정기 ?휴|입장료|요금|가격|[0-9,]+ ?원\b|주소|도로명|"
                     r"번지|기온|날씨|강수|비 (와|올)|막차|첫차)")
#: 사실 값 — 시각 · 금액 · 전화 · 도로명 주소 조각
FACT_VALUES = [
    ("time", re.compile(r"\b([01]?\d|2[0-4]):([0-5]\d)\b")),
    ("price", re.compile(r"([0-9][0-9,]{2,})\s?원")),
    ("phone", re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b")),
    ("road", re.compile(r"([가-힣0-9]+(?:로|길))\s?(\d+(?:-\d+)?)")),
    ("temp", re.compile(r"(-?\d+(?:\.\d+)?)\s?(?:도|℃)")),
]

#: 열린 질문(봇이 고객 답을 기다린다)
QUESTION_RE = re.compile(r"(\?|할까요|인가요|알려 주세요|골라 주세요|고르세요|고르시면|번호로|말씀해 주세요|원하시는|드릴까요|맞나요|볼까요)")
YES_RE = re.compile(r"^(네|넵|예|응|ㅇㅇ|ㅇㅋ|오케이|ok|okay|좋아|좋아요|그래|그래요|맞아|맞아요|해줘|해 줘|해주세요|해 주세요|진행|진행해|ㄱㄱ|ㄱ)[.!~ ]*$", re.I)
NO_RE = re.compile(r"^(아니|아니요|아뇨|ㄴㄴ|싫어|안 ?해|하지 마|됐어|괜찮아)[.!~ ]*$")
NUMBER_RE = re.compile(r"^\s*(\d{1,2})\s*(?:번(?:이요|요)?|번째)?[.!]?\s*$")

_PUNCT = re.compile(r"[\s·・\-_'\"()\[\]{}<>~,.!?/|:;→▶「」『』…]+")


def norm(value: str | None) -> str:
    """NFKC · 소문자 · 공백 · 문장부호 제거 — 이름 비교용."""
    return _PUNCT.sub("", unicodedata.normalize("NFKC", value or "").lower())


def fail_types(answer: str | None) -> list[str]:
    text = answer or ""
    return [name for name, rx in FAIL_TYPES.items() if rx.search(text)]


def claims_done(answer: str | None) -> bool:
    """완료를 말한 답인가 — 「바꿨어요」가 있고, 같은 답에 「바꾸지 않았어요」가 없다."""
    text = answer or ""
    return bool(DONE_RE.search(text)) and not NOT_DONE_RE.search(text)


def has_fact_sentence(answer: str | None) -> bool:
    return bool(FACT_RE.search(answer or ""))


def fact_values(answer: str | None) -> list[tuple[str, str]]:
    """사실 문장이 있는 줄에서만 값을 뽑는다(일정 시각 안내 줄을 사실 값으로 세지 않게)."""
    out: list[tuple[str, str]] = []
    for line in re.split(r"[\n.]", answer or ""):
        if not FACT_RE.search(line):
            continue
        for kind, rx in FACT_VALUES:
            for m in rx.finditer(line):
                out.append((kind, m.group(0)))
    return out


def is_open_question(answer: str | None, choices: list | None = None) -> bool:
    if choices:
        return True
    text = (answer or "").strip()
    return bool(QUESTION_RE.search(text[-160:]))


def answer_shape(text: str, n_choices: int = 0, choice_names: list[str] | None = None) -> str | None:
    """고객 줄이 질문의 답 모양인가 — `number` · `yes` · `no` · `name`(선택지 이름) · None(답 모양 아님)."""
    t = (text or "").strip()
    m = NUMBER_RE.match(t)
    if m:
        k = int(m.group(1))
        return "number" if (n_choices == 0 or 1 <= k <= n_choices) else None
    if YES_RE.match(t):
        return "yes"
    if NO_RE.match(t):
        return "no"
    nt = norm(t)
    if nt and choice_names and any(nt and (nt in norm(c) or norm(c) in nt) for c in choice_names if norm(c)):
        return "name"
    return None
