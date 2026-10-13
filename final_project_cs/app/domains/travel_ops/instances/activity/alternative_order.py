# -*- coding: utf-8 -*-
"""대체 후보 순서 — 코드가 찾고 검증한 후보 **안에서** LLM 이 고객 취향에 맞춰 먼저 보여 줄 순서를 정한다. `[2026-10-12 사용자 결정]`

★역할 나눔:
  - 코드: 대체 후보를 찾고(같은 분류 · 반경 1→10km) 휴무 · 운영시간 · 재난을 다시 확인한다(`rank_alternatives` · `_recheck_disaster`).
  - LLM: 그 후보 가운데 **어느 곳을 먼저 보여 줄지**와 그 이유 한 줄만 정한다. 후보를 새로 만들지 않는다.
★지키는 것:
  - LLM 이 목록에 없는 장소를 내면 버린다. 빠진 후보는 코드 순서대로 뒤에 붙인다 — 검증된 후보는 하나도 잃지 않는다.
  - 취향 단서(설문 · 고객 문장)가 없으면 부르지 않는다. 실패 · 시간 초과 · 예산 초과면 코드 순서 그대로다.
  - 이유는 고객에게 그대로 보이므로 길이를 자르고, 모델이 「취향을 쓰지 않았다」고 하면 싣지 않는다.
★취향은 설문(`trips.constraints.survey` — 테마 · 동행 · 우선순위 · 실내외 · 세부 테마 · 직접 쓴 선호)과 고객 문장에서 온다.
  예약 성립 판정 Case 에는 설문이 아직 오지 않는다(코어 전달 8번 — `TEAM_STATE_KEYS`). 그 전까지는 고객 문장만 쓴다.
★모델: 판정 어댑터가 모든 판정에 같은 모델(`activity_judge_model`)을 쓴다. 팀원 실험(대안 선택 27문제)에서는 `gpt-6-luna`
  59.3% · `gpt-5.4-nano` 40.7% — 이 판정만 다른 모델로 부르려면 어댑터에 모델 인자가 필요하다(코어 파일, 10-12 사용자 결정으로
  고치지 않음). 프롬프트도 허용 목록(`read_tools.ALLOWED_PROMPT_KEYS`)에 키가 있어야 운영 어댑터가 부른다 — 그 전에는 호출이
  실패하고 코드 순서로 답한다.
"""
from __future__ import annotations

from typing import Any

#: 판정 종류 · 프롬프트 키 — `kind_modes.alternative_order` 로 켜고 끈다(표에 없으면 `rule` = 부르지 않음)
KIND = "alternative_order"
PROMPT_KEY = f"activity_judge.{KIND}"
#: 한 번에 넘기는 후보 수 — 안내 3곳 + 더보기 5곳(지금 화면이 보여 주는 만큼)
MAX_CANDIDATES = 8
#: 고객에게 보이는 이유의 최대 길이
REASON_MAX = 120
#: 설문에서 넘기는 칸 — 취향과 관계없는 칸(이동 수단 · 내국인 여부 · 일정 밀도 등)은 넘기지 않는다
SURVEY_FIELDS = ("theme", "party", "priority", "indoor_outdoor", "theme_details", "custom_answers")


def preference_inputs(survey: dict[str, Any] | None, customer_text: str | None) -> dict[str, Any] | None:
    """LLM 에 넘길 취향. 단서가 하나도 없으면 `None`(부르지 않는다)."""
    picked: dict[str, Any] = {}
    for field in SURVEY_FIELDS:
        value = (survey or {}).get(field)
        if value not in (None, "", [], {}):
            picked[field] = value
    details = ((survey or {}).get("priority_details") or {}).get("activity")
    if details:
        picked["activity_details"] = details
    text = (customer_text or "").strip()
    if not picked and not text:
        return None
    return {"survey": picked, "customer_text": text or None}


def candidate_rows(candidates: list[dict[str, Any]], classes: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """모델에게 보낼 후보 — 이름 · 코드가 잰 이유 · 거리 · 관광공사 분류만. 좌표 · 주소 원문은 보내지 않는다."""
    return [{"id": str(c.get("contentid")), "title": c.get("title"), "code_reason": c.get("reason"),
             "distance_km": c.get("distance_km"), "class": (classes or {}).get(str(c.get("contentid")))}
            for c in candidates[:MAX_CANDIDATES]]


def schema() -> dict[str, Any]:
    """Structured Outputs(strict) — 순서(후보 id) · 취향을 썼나 · 이유 한 줄."""
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "order": {"type": "array", "items": {"type": "string"}},
            "used_preference": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["order", "used_preference", "reason"],
    }


def payload(origin_title: str | None, candidates: list[dict[str, Any]], preference: dict[str, Any],
            classes: dict[str, str] | None = None) -> dict[str, Any]:
    return {"kind": KIND, "origin": origin_title, "candidates": candidate_rows(candidates, classes),
            "preference": preference}


def apply(candidates: list[dict[str, Any]], output: Any) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """모델 답을 검증해 후보 순서를 바꾼다. 쓸 수 없는 답이면 `None`(코드 순서 그대로).

    반환: (새 순서의 후보 전부, `order` 기록 — by · ids · reason · dropped).
    """
    if not isinstance(output, dict) or not isinstance(output.get("order"), list):
        return None
    pool = candidates[:MAX_CANDIDATES]
    by_id = {str(c.get("contentid")): c for c in pool}
    chosen: list[str] = []
    dropped = 0
    for raw in output["order"]:
        key = str(raw)
        if key in by_id and key not in chosen:
            chosen.append(key)
        else:
            dropped += 1                      # ★목록에 없거나 겹친 id — 지어낸 장소를 싣지 않는다
    if not chosen:
        return None
    rest = [str(c.get("contentid")) for c in pool if str(c.get("contentid")) not in chosen]
    ordered = [by_id[k] for k in [*chosen, *rest]] + candidates[MAX_CANDIDATES:]
    reason = str(output.get("reason") or "").strip()[:REASON_MAX] if output.get("used_preference") else ""
    return ordered, {"by": "llm", "ids": [*chosen, *rest], "reason": reason or None, "dropped": dropped}
