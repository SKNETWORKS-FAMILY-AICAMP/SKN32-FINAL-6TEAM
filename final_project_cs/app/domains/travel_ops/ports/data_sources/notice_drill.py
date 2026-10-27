# -*- coding: utf-8 -*-
"""재난 · 공지 문자가 **훈련 · 가상 상황 문자인가** — 공용 판정 한 곳 `[2026-10-27 C 전수검사 · 알려진 이슈 (a)]`.

★왜 바꿨나. 전에는 세 곳(재난문자 판정 `disaster_msg.judge` · 재난 정지 `planning.safety._from_message` ·
  활동 성립 `activity.disaster_impact`)이 제외 낱말(`travel.safety.exclude_keywords` = 「훈련」 · 「실제 상황이 아」)을
  **글자 그대로 한 번 포함되면** 문자 전체를 버렸다. 두 방향으로 틀렸다.
  ① 놓침 — 「훈련」이란 낱말 없이 가상 상황을 알리는 문자(「가상 상황입니다」 · 「시험 발송」 · 「실제상황이 아닙니다」처럼
     띄어쓰기가 다른 문자)는 거르지 못해 지진 · 긴급재난으로 판정됐다.
  ② 통째 제외 — 「훈련 중 실제 화재 발생」 · 「훈련이 아닌 실제 상황입니다」처럼 **실제 사건을 말하는** 문자도 「훈련」
     한 낱말 때문에 버려졌다(가장 위험한 쪽).
  ③ 「○○ 훈련장 화재」처럼 장소 이름 안의 「훈련」도 훈련 문자로 읽었다.

판정(띄어쓰기를 지우고 본다 — 「실제상황이 아닙니다」 · 「실제 상황이 아닙니다」가 같다):

    1. 장소 이름 낱말(`drill_place_words` — 훈련장 · 훈련소 …)은 먼저 지운다 — 훈련 표지가 아니다.
    2. 실제 사건 표지(`drill_actual_keywords` — 「실제 상황입니다」 · 「실제 화재」 · 「훈련이 아닌」 …)가 하나라도 있으면
       **훈련이 아니다**(실제가 이긴다 — 놓치는 쪽보다 한 번 더 알리는 쪽으로 틀린다).
    3. 그렇지 않고 훈련 표지(`exclude_keywords` — 훈련 · 실제 상황이 아 · 가상 상황 · 시험 발송 …)가 있으면 훈련이다.

★판정 근거(`basis`)는 걸린 표지 원값이다 — 근거 없는 판정을 만들지 않는다. 낱말은 모두 `config/guardrails.yaml`
  `travel.safety.*` 한 곳에서 읽는다(정본 한 곳). 남은 한계: 낱말 규칙이다 — 표지 없이 가상 상황을 말하는 새 말투는 거르지 못한다
  (실제 사건 쪽으로 틀린다).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SPACE = re.compile(r"\s+")


def _key(text: Any) -> str:
    return _SPACE.sub("", str(text or ""))


@dataclass(frozen=True)
class DrillStatus:
    drill: bool
    #: 걸린 표지(띄어쓰기 지운 원값) — 훈련이면 훈련 표지, 실제가 이겼으면 실제 사건 표지, 둘 다 없으면 None
    basis: str | None = None


def drill_status(text: Any, *, drill_words: tuple[str, ...], actual_words: tuple[str, ...] = (),
                 place_words: tuple[str, ...] = ()) -> DrillStatus:
    body = _key(text)
    for word in place_words:
        if _key(word):
            body = body.replace(_key(word), " ")
    actual = next((_key(w) for w in actual_words if _key(w) and _key(w) in body), None)
    if actual is not None:
        return DrillStatus(False, actual)
    drill = next((_key(w) for w in drill_words if _key(w) and _key(w) in body), None)
    return DrillStatus(drill is not None, drill)


def is_drill(text: Any, *, drill_words: tuple[str, ...], actual_words: tuple[str, ...] = (),
             place_words: tuple[str, ...] = ()) -> bool:
    return drill_status(text, drill_words=drill_words, actual_words=actual_words, place_words=place_words).drill
