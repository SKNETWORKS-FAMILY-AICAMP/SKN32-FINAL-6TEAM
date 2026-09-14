# -*- coding: utf-8 -*-
"""라우팅 축을 뽑는다 — ★**어휘는 모른다.**

★2026-09-09 실행으로 확인된 것. `Controller` 는 `resolve(case_type=intent)` 로
  **한 축을 두 번 썼다.** 어떤 도메인에서는 우연히 맞는다 — 요청 종류의 이름과
  팀이 받는 대상 종류의 이름이 같은 말이면 그렇다. 두 이름이 갈리는 도메인에서는
  같은 값을 넣는 순간 **어느 팀에도 도달하지 못한다**(v11 §5-B).

★**이 파일은 basement 다.** 그래서 두 축의 **어휘를 여기 적지 않는다** — 실제
  라벨이 무엇인지는 도메인 모듈(`app/modules/*/feedback.py`)이 정하고, 여기
  하는 일은 `_` 앞을 자르는 것뿐이다. 어휘 예시가 궁금하면 그 모듈을 본다.
  `tests/architecture/test_basement_is_domain_free.py` 가 이 경계를 센다 —
  실제로 이 파일의 첫 판이 그 검사에 걸렸다(도메인 이름을 주석에 적어 뒀다).
"""
from __future__ import annotations


def case_type_of(issue_code: str | None, *, fallback: str | None = None) -> str:
    """`issue_code` 의 접두를 돌려준다. 없으면 `fallback`, 그것도 없으면 빈 문자열.

    ★`fallback` 이 있는 이유는 **하위호환**이다. `issue_code` 가 없는 옛 Case
      (분류 전이거나 옛 도메인 기록)는 전처럼 `intent` 로 라우팅한다. 없애면
      살아 있는 Case 가 조용히 라우팅 실패로 떨어진다.

    ★`_` 가 없는 코드는 **그대로 돌려준다** — 억지로 쪼개 팀을 고르지 않는다.
      받는 팀이 없으면 `RegistryError` 가 나고 Case 는 `escalated` 로 간다.
      모르는 것을 아무 팀에나 보내는 것보다 낫다.
    """
    code = (issue_code or "").strip()
    if not code:
        return (fallback or "").strip()
    prefix, separator, _rest = code.partition("_")
    return prefix if separator else code


__all__ = ["case_type_of"]
