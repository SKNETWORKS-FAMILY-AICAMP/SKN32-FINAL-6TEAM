# -*- coding: utf-8 -*-
"""별칭이 **한 장소**로 정하는 이름인가 — 활동 팀이 꽂는 자리. `[2026-10-22 사용자 지시]`

☆왜: 활동 팀 별칭(「MMCA 서울」 → 국립현대미술관 서울, 시드 CSV + 마이그레이션 306)이 배포됐지만 활동 팀 이름 찾기(`read.place_lookup`)만
  그것을 읽었다 — 고객이 쓰는 계획 읽기(`intake.places.resolve`) · 확인 화면 장소 검색(`intake.candidates.search`)은 읽지 않아
  「mmca 서울」이 우리 목록에 있는데도 카카오 결과로만 나왔다(x600 서버 실측). 이름 찾기 순서 하나를 모든 경로가 이 자리로 지킨다:

    ① 그 고객이 고친 별칭 → ② 우리 자료 정확 일치 → ③ **공용 별칭(여기)** → ④ 자모 오타 → ⑤ 관광공사 · 요식 원장 → ⑥ 카카오 → ⑦ 유료

    부품      "이 이름이 별칭으로 가리키는 곳 하나는?"   →  여기
    활동 팀   "별칭 자료(시드 CSV + DB 표)가 정본이다"  →  조립 때 `register()`

★미등록이면 `None`(별칭 없음) — 부르는 쪽은 별칭 단계만 건너뛴다. 지어낸 장소를 내지 않는다.
★바깥을 부르지 않는다. 시드 파일과 DB(활동 원장 · 별칭 표)만 읽는다. 카카오 값은 별칭에 넣지 않는다(카카오 운영정책 제5조, D-027).
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.service_bindings import collect_registration, read_binding

_target: Callable[..., dict[str, Any] | None] | None = None


def register(*, target: Callable[..., dict[str, Any] | None]) -> None:
    """조립 때 한 번. `target(conn, name)` → `{"content_id", "title", "content_type_id", "latitude", "longitude", "source"}` · `None`."""
    if collect_registration("place_aliases", locals()):
        return
    global _target
    _target = target


def clear() -> None:
    global _target
    _target = None


def is_registered() -> bool:
    return read_binding("place_aliases", "target", globals()["_target"]) is not None


def target(conn: Any | None, name: str | None) -> dict[str, Any] | None:
    """별칭이 한 곳만 가리키면 그곳. `conn` 이 없으면 시드 파일만 본다(정식 제목만 · 좌표 없음). ★미등록 · 별칭 아님 · 모호하면 `None`."""
    if not (name or "").strip():
        return None
    try:
        selected = read_binding("place_aliases", "target", globals()["_target"])
    except RuntimeError:
        # ★조립 밖(평가 러너 · 단독 스크립트)에서 이름 찾기를 부르면 별칭 단계만 건너뛴다 — 전에는 이 단계가 없던 길이라 멈추게 하지 않는다
        return None
    if selected is None:
        return None
    return selected(conn, name)
