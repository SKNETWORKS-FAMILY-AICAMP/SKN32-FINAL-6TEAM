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


def case_type_of(issue_code: str | None, *, fallback: str | None = None,
                 hint: str | None = None, hint_wins: bool = False) -> str:
    """`issue_code` 의 접두를 돌려준다. 없으면 `fallback`, 그것도 없으면 빈 문자열.

    ★`fallback` 이 있는 이유는 **하위호환**이다. `issue_code` 가 없는 옛 Case
      (분류 전이거나 옛 도메인 기록)는 전처럼 `intent` 로 라우팅한다. 없애면
      살아 있는 Case 가 조용히 라우팅 실패로 떨어진다.

    ★`_` 가 없는 코드는 **그대로 돌려준다** — 억지로 쪼개 팀을 고르지 않는다.
      받는 팀이 없으면 `RegistryError` 가 나고 Case 는 `escalated` 로 간다.
      모르는 것을 아무 팀에나 보내는 것보다 낫다.

    ★`hint` 는 **분류가 대상 접두를 못 붙였을 때만** 쓴다(`[결정 2026-09-17]`).
      Case 가 가리키는 대상(`state_json.subject_ref`)을 서버가 확인하면서 그 대상
      부분의 종류를 힌트로 남긴다. 분류가 접두를 붙였으면 **분류가 이긴다** —
      힌트는 「어느 객체 얘기인지 문장에 없다」를 메우는 자리이지 분류를 덮는
      자리가 아니다.
    ★예외 하나 — `hint_wins`. 클라이언트가 대상 부분을 **지정하고 서버가 확인한** 경우 그 종류는
      추측이 아니라 사실이다. 화면 버튼이 보낸 「화면에서 다른 안 선택」 같은 문장에 분류가 아무
      접두나 붙여도 그 사실이 이긴다(2026-09-17, 식당 항목이 activity 로 가서 escalated 된 것을 보고).
    """
    code = (issue_code or "").strip()
    wanted = (hint or "").strip()
    if wanted and hint_wins:
        return wanted
    if not code:
        return wanted or (fallback or "").strip()
    prefix, separator, _rest = code.partition("_")
    if separator:
        return prefix
    return wanted or code


__all__ = ["case_type_of"]
