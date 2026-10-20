# -*- coding: utf-8 -*-
"""대체 후보 순서 — 코드가 찾고 검증한 후보 **안에서** LLM 이 고객 취향에 맞춰 먼저 보여 줄 순서를 정한다. `[2026-10-12 사용자 결정]`

★역할 나눔:
  - 코드: 대체 후보를 찾고(같은 분류 · 반경 1→10km) 휴무 · 운영시간 · 재난을 다시 확인한다(`rank_alternatives` · `_recheck_disaster`).
    **화면에 보일 3곳(`SHOW`)도 코드가 정한다.**
  - LLM: 그 3곳의 **보여 줄 순서**(1순위)와 그 이유 한 줄만 정한다. 후보를 새로 만들지도, 고르지도 않는다.
    `[2026-10-13 사용자 결정 A안]` 전에는 더보기까지 8곳을 넘겨 LLM 이 더보기 후보를 상위 3곳으로 올릴 수 있었다 — 어떤 3곳이 보이는지가
    모델 판단으로 흔들려 3곳 → 3곳 순서만으로 좁혔다. 더보기(7곳)는 코드 순서 그대로다.
★지키는 것:
  - LLM 이 목록에 없는 장소를 내면 버린다. 빠진 후보는 코드 순서대로 뒤에 붙인다 — 검증된 후보는 하나도 잃지 않는다.
  - 취향 단서(설문 · 고객 문장)가 없으면 부르지 않는다. 실패 · 시간 초과 · 예산 초과면 코드 순서 그대로다.
  - 순서를 바꿨는데 이유가 없으면(`used_preference=false` 이거나 `reason` 이 비었으면) 그 답을 쓰지 않고 코드 순서로 둔다.
  - 이유는 고객에게 그대로 보이므로 길이를 자르고, 모델이 「취향을 쓰지 않았다」고 하면 싣지 않는다.
★취향은 설문(`trips.constraints.survey` — 테마 · 동행 · 우선순위 · 실내외 · 세부 테마 · 직접 쓴 선호)과 고객 문장에서 온다.
  `[2026-10-14]` 예약 성립 판정은 예약이 속한 여행의 설문을 도구로 읽어 넘긴다(`replacement._survey` — 전달 8번 회신).
  여행을 못 찾으면 고객 문장만 쓴다.
★모델: 판정 어댑터가 모든 판정에 같은 모델(`activity_judge_model`)을 쓴다. 팀원 실험(대안 선택 27문제)에서는 `gpt-6-luna`
  59.3% · `gpt-5.4-nano` 40.7% — 이 판정만 다른 모델로 부르려면 어댑터에 모델 인자가 필요하다(코어 파일, 10-12 사용자 결정으로
  고치지 않음). 프롬프트도 허용 목록(`read_tools.ALLOWED_PROMPT_KEYS`)에 키가 있어야 운영 어댑터가 부른다 — 그 전에는 호출이
  실패하고 코드 순서로 답한다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.domains.travel_ops.components.planning.survey import ACTIVITY_DETAILS

from .alternatives import SHOW

#: 판정 종류 · 프롬프트 키 — `kind_modes.alternative_order` 로 켜고 끈다(표에 없으면 `rule` = 부르지 않음)
KIND = "alternative_order"
PROMPT_KEY = f"activity_judge.{KIND}"
#: 한 번에 넘기는 후보 수 — 화면에 보이는 3곳뿐이다(`SHOW`). 더보기는 넘기지 않는다.
MAX_CANDIDATES = SHOW
#: 고객에게 보이는 이유의 최대 길이
REASON_MAX = 120
#: 설문에서 넘기는 칸 — 취향과 관계없는 칸(이동 수단 · 내국인 여부 · 일정 밀도 등)은 넘기지 않는다
#: ★`[2026-10-20 사용자 결정]` 우선순위(`priority` — 음식 · 활동 · 이동 중 무엇을 먼저)도 뺀다. 취향이 아니라 **후보를 뽑는 범위**다
#:   (`alternatives.preference_from_survey`, 계획서 1-1). 감시 경로 실측(20261019T144241Z)에서 우선순위만 받은 사례 4/99 가
#:   `mobility` 를 「이동 편의」 취향으로 읽고 순서를 바꿨다. 세부 취향(`priority_details.activity`)은 그대로 넘긴다.
SURVEY_FIELDS = ("theme", "party", "indoor_outdoor", "theme_details", "custom_answers")


#: 감시 루프가 연 Case 의 `trigger_source` — `trip_watch_cases` 가 `open_case(trigger_source="schedule")` 로 연다
WATCH_TRIGGER = "schedule"


def customer_words(input_text: str | None, state: dict[str, Any] | None) -> str | None:
    """고객이 실제로 쓴 말만. `[2026-10-19]`

    ★감시 루프가 연 Case 의 `input_text` 는 Case 제목(`[감시] 경복궁 — closure` 같은 시스템 문구)이다. 전에는 그것을
      고객 문장으로 넘겨 ①설문이 비어도 취향 단서가 있는 것처럼 LLM 을 불렀고 ②모델이 시스템 문구를 취향으로 읽을 수 있었다.
      감시 Case 는 고객이 답한 말(`customer_input`)만 쓰고, 없으면 고객 문장 없음이다.
    ★고객이 연 Case 는 그대로 — `input_text` 가 고객 말이다(답이 있으면 코어가 「원래 요청 + 추가 답변」으로 합친다).
    """
    state = state or {}
    if state.get("trigger_source") == WATCH_TRIGGER:
        reply = state.get("customer_input")
        return reply if isinstance(reply, str) else None
    return input_text


def preference_inputs(survey: dict[str, Any] | None, customer_text: str | None) -> dict[str, Any] | None:
    """LLM 에 넘길 취향. 단서가 하나도 없으면 `None`(부르지 않는다)."""
    picked: dict[str, Any] = {}
    for field in SURVEY_FIELDS:
        value = (survey or {}).get(field)
        if value not in (None, "", [], {}):
            picked[field] = value
    details = ((survey or {}).get("priority_details") or {}).get("activity")
    if details:
        # ★`[2026-10-19]` 세부는 관광 분류 코드(EV · EX …)로 온다 — 모델에는 뜻을 알 수 있게 화면 글로 넘긴다(모르는 옛 값은 그대로)
        picked["activity_details"] = [ACTIVITY_DETAILS.get(code, code) for code in details]
    text = (customer_text or "").strip()
    if not picked and not text:
        return None
    return {"survey": picked, "customer_text": text or None}


#: 관광공사 분류 코드 → 이름(대 > 중 > 소). `[2026-10-20]` TourAPI `lclsSystmCode2` 를 한 번 받아 둔 것(ⓒ한국관광공사).
CLASS_NAMES_FILE = Path(__file__).with_name("kto_class_names.json")


@lru_cache(maxsize=1)
def _class_names() -> dict[str, str]:
    return json.loads(CLASS_NAMES_FILE.read_text(encoding="utf-8"))["names"]


def class_path(code: str | None) -> str | None:
    """`HS010100` → 「역사관광 > 역사유적지 > 고궁」. 모르는 코드는 아는 단계까지, 하나도 모르면 `None`."""
    if not code:
        return None
    names = _class_names()
    parts = [names[c] for c in (code[:2], code[:4], code) if c in names]
    return " > ".join(dict.fromkeys(parts)) or None


def candidate_rows(candidates: list[dict[str, Any]], classes: dict[str, str] | None = None, *,
                   with_class_name: bool = False) -> list[dict[str, Any]]:
    """모델에게 보낼 후보 — 이름 · 코드가 잰 이유 · 거리 · 관광공사 분류만. 좌표 · 주소 원문은 보내지 않는다.

    ★`[2026-10-20 실험 E1]` `with_class_name` 이면 분류 이름(`class_name`)도 싣는다 — 코드만 주면 모델이 뜻을 짐작해
      팔각정(랜드마크 · 건물)을 궁궐로, 봉수대 터(역사)를 자연으로 읽었다. 프롬프트 v3 와 함께 켠다.
      `[2026-10-20]` holdout-2 판정 뒤 운영(`replacement._order_alternatives`)이 켠다 — 기본값 False 는 v2 비교 실행용이다.
    """
    rows = []
    for c in candidates[:MAX_CANDIDATES]:
        code = (classes or {}).get(str(c.get("contentid")))
        row = {"id": str(c.get("contentid")), "title": c.get("title"), "code_reason": c.get("reason"),
               "distance_km": c.get("distance_km"), "class": code}
        if with_class_name:
            row["class_name"] = class_path(code)
        rows.append(row)
    return rows


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
            classes: dict[str, str] | None = None, *, with_class_name: bool = False) -> dict[str, Any]:
    return {"kind": KIND, "origin": origin_title,
            "candidates": candidate_rows(candidates, classes, with_class_name=with_class_name), "preference": preference}


#: ★`[2026-10-20]` 이유 문장 지킴이 — 후보 정보로 확인할 수 없는 말. 고객이 이 조건을 말해도 이유에서 「맞다」고 하면 지어냄이다
#:  (holdout-2: 「조용한 전시관에 맞다」 · dev 스트레스: 지시문 v4 로도 「조용한 실내에 맞게」 34/48 이 남았다)
UNVERIFIABLE = ("조용", "한적", "붐비", "붐빔", "혼잡", "사람이 적", "주차", "와이파이", "wifi", "WiFi", "대기", "줄 서", "줄 안",
                "웨이팅", "후기", "리뷰", "평점", "별점", "인기", "유명", "요금", "입장료", "가격", "무료", "음식 반입", "음식 가지고")
#: 고객이 둘 다 원한다고 한 말(「A 아니면 B」) — 이때 이유가 「제외 · 말고」면 거꾸로 읽은 것이다(holdout-2 심각 H-63)
EITHER = re.compile(r"아니면|또는|이나 |이든|든지")
REFUSED_IN_REASON = re.compile(r"제외|말고|피했|피해|빼고|빼서")
#: 장소 번호를 이유에 쓰지 않는다(고객에게 의미 없는 내부 id)
CONTENT_ID = re.compile(r"\d{5,}")


def _particle(word: str) -> str:
    """을/를 — 마지막 한글 글자의 받침으로(괄호 · 숫자 뒤는 건너뛴다: 「(드론)」 → 「론」)."""
    last = next((ch for ch in reversed(word) if "가" <= ch <= "힣"), "")
    return "을" if last and (ord(last) - 0xAC00) % 28 else "를"


def guard_reason(reason: str, customer_text: str | None, first: dict[str, Any], class_code: str | None
                 ) -> tuple[str, str | None]:
    """이유 문장을 확인한다. 문제가 있으면 분류 이름으로 만든 정해진 문장으로 바꾼다 — (이유, 바꾼 까닭 | None).

    ★순서는 LLM 답 그대로 쓴다. 바꾸는 것은 고객에게 보이는 문장뿐이다(지어낸 말이 화면에 나가지 않게).
    """
    why = None
    if any(w in reason for w in UNVERIFIABLE):
        why = "unverifiable"
    elif customer_text and EITHER.search(customer_text) and REFUSED_IN_REASON.search(reason):
        why = "reversed_either"
    elif CONTENT_ID.search(reason):
        why = "content_id"
    if why is None:
        return reason, None
    leaf = (class_path(class_code) or "").split(" > ")[-1]
    title = str(first.get("title") or "")
    named = f"‘{title}’({leaf})" if leaf else f"‘{title}’"
    return f"요청에 맞춰 {named}{_particle(leaf or title)} 먼저 보여 드려요.", why


def apply(candidates: list[dict[str, Any]], output: Any, *, customer_text: str | None = None,
          classes: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """모델 답을 검증해 후보 순서를 바꾼다. 쓸 수 없는 답이면 `None`(코드 순서 그대로).

    반환: (새 순서의 후보 전부, `order` 기록 — by · ids · reason · dropped · reason_guard).
    `[2026-10-20]` `customer_text` · `classes` 를 주면 이유 문장 지킴이(`guard_reason`)를 거친다.
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
    ids = [*chosen, *rest]
    reason = str(output.get("reason") or "").strip()[:REASON_MAX] if output.get("used_preference") else ""
    # ★`[2026-10-13]` 순서를 바꿨으면 이유가 있어야 한다 — 근거 없이 순서만 바뀌는 것을 받지 않는다(코드 순서 그대로)
    if ids != [str(c.get("contentid")) for c in pool] and not reason:
        return None
    guard = None
    if reason:
        reason, guard = guard_reason(reason, customer_text, by_id[ids[0]], (classes or {}).get(ids[0]))
    ordered = [by_id[k] for k in ids] + candidates[MAX_CANDIDATES:]
    return ordered, {"by": "llm", "ids": ids, "reason": reason or None, "dropped": dropped, "reason_guard": guard}
