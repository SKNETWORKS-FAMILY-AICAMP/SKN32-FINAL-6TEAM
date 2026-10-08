# -*- coding: utf-8 -*-
"""모델이 낸 항공 해석을 **검증**한다 — 모델은 문장을 구조로 옮기고(도시 이름 → 공항 코드 포함), 쓸 수 있는지는 서버가 정한다. `[2026-10-08]`

- 프롬프트: `prompts/flight/interpret.v2.md` (키 `flight.interpret`). 모델 호출은 한 번이다.
- 모양이 틀리면 `InterpretationInvalid` — 고쳐 맞추지 않는다. 공항 코드는 영문 대문자 3글자만 받는다.
- 무엇이 빠졌는지는 `needs()` 가 값으로 다시 센다 — 지난 출발일 · 출발일보다 앞선 귀국일 · 출발지와 같은 도착지는 없는 값으로 본다.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

REQUIRED = ("origin", "destination", "depart_date", "adults")
LABELS = {"origin": "출발지", "destination": "도착지", "depart_date": "출발 날짜", "adults": "성인 인원",
          "return_date": "돌아오는 날짜"}
_CODE = r"^[A-Z]{3}$"


class InterpretationInvalid(ValueError):
    """모델 출력이 약속한 모양이 아니다."""


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: Literal["search", "status", "unclear"]
    origin: str | None = Field(default=None, pattern=_CODE)
    destination: str | None = Field(default=None, pattern=_CODE)
    depart_date: date | None = None
    return_date: date | None = None
    adults: int | None = Field(default=None, ge=1, le=9)
    children: int | None = Field(default=None, ge=0, le=9)
    infants: int | None = Field(default=None, ge=0, le=9)
    cabin: Literal["ECONOMY", "BUSINESS", "FIRST"] | None = None
    depart_date_text: str | None = None
    return_date_text: str | None = None
    direct_only: bool | None = None
    domestic: bool | None = None
    missing: list[str] = Field(default_factory=list)
    question: str | None = None


def parse(raw: Any) -> Interpretation:
    if not isinstance(raw, dict):
        raise InterpretationInvalid(f"not an object: {type(raw).__name__}")
    cleaned = {key: (value.strip() or None) if isinstance(value, str) else value for key, value in raw.items()}
    try:
        found = Interpretation.model_validate(cleaned)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise InterpretationInvalid(f"invalid fields: {fields}") from exc
    if found.task == "search" and found.origin and found.destination and found.domestic is None:
        # ★공항 둘을 알면서 국내 · 국제를 안 정했다 — 어느 도구를 부를지 서버가 추측하지 않는다
        raise InterpretationInvalid("invalid fields: ['domestic']")
    return found


def needs(found: Interpretation, *, today: date) -> list[str]:
    """이 해석으로 검색하려면 아직 받아야 하는 값의 이름들(순서 고정). 귀국일이 틀렸으면 `return_date` 를 더한다."""
    if found.task != "search":
        return []
    values = found.model_dump()
    if found.depart_date is not None and found.depart_date < today:
        values["depart_date"] = None
    if found.origin and found.destination and found.origin == found.destination:
        values["destination"] = None
    missing = [name for name in REQUIRED if values.get(name) in (None, "")]
    if found.return_date is not None and values["depart_date"] is not None and found.return_date < found.depart_date:
        missing.append("return_date")
    return missing


def ask(found: Interpretation, missing: list[str]) -> str:
    """되묻는 문장. 모델이 센 빠진 값이 서버가 센 것과 **같을 때만** 모델 문장을 쓰고, 다르면 빠진 값의 이름을 나열한다.

    값은 읽었는데 서버가 쓸 수 없다고 본 것(지난 날짜 · 같은 공항 · 뒤집힌 날짜)은 **읽은 값을 같이 보여 준다** —
    ☆2026-10-08 14:58 playdata, 「11월 6일」을 모델이 2023-11-06 으로 옮겼고 서버가 지난 날짜로 거른 뒤 「출발 날짜를 알려 달라」고만 물었다.
      고객은 날짜를 말했는데 다시 묻는 꼴이었다.
    """
    values = found.model_dump(mode="json")
    rejected = [f"{LABELS[name]} {values[name]}" for name in missing if values.get(name) not in (None, "")]
    if rejected:
        return (f"{' · '.join(rejected)}(으)로 읽었는데 지난 날짜이거나 앞뒤가 맞지 않습니다. "
                f"{' · '.join(LABELS[name] for name in missing)}을(를) 다시 알려 주세요.")
    if found.question and set(found.missing) == set(missing):
        return found.question
    return f"{' · '.join(LABELS[name] for name in missing)}을(를) 알려 주시면 이어서 찾아 드리겠습니다."

#: 날짜 값 → 그 값의 근거로 모델이 옮겨 적은 문장 조각 칸
GROUNDS = {"depart_date": "depart_date_text", "return_date": "return_date_text"}


def ground(found: Interpretation, text: str, *, has_trip: bool) -> tuple[Interpretation, list[str]]:
    """날짜마다 모델이 적은 근거 조각이 **고객 문장에 실제로 있는지** 본다. 없으면 그 날짜를 비운다(없는 값으로 다시 묻는다).

    ☆2026-10-08 15:26 playdata — 「서울에서 3박 할 숙소 추천해줘」에 모델이 체크인을 오늘(2026-10-08)로 지어냈다.
      프롬프트에 「지어내지 말라」가 있었는데도 그랬다. 그래서 값 대신 **근거를 받아 서버가 문장과 맞춰 본다** —
      뜻을 서버가 해석하는 것이 아니라, 모델이 인용한 글자가 문장에 있는지만 본다(공백 무시).
      근거가 `"trip"` 이면 Case 에 여행 일정이 붙어 있을 때만 받는다.
    """
    squeezed = "".join(text.split())
    cleared: list[str] = []
    for field, evidence in GROUNDS.items():
        if getattr(found, field) is None:
            continue
        if field in found.missing:
            # ★모델 스스로 「빠졌다」고 적은 값은 채워 와도 쓰지 않는다. ☆15:30 playdata — 체크인을 오늘로 채우고 근거로 「3박」을
            #   인용하면서, 같은 답의 `missing` 에는 check_in 을 넣었다. 인용 글자는 문장에 있어 위 확인만으로는 못 걸렀다
            cleared.append(field)
            continue
        quote = getattr(found, evidence)
        if quote == "trip" and has_trip:
            continue
        if quote and "".join(quote.split()) in squeezed:
            continue
        cleared.append(field)
    return found.model_copy(update={field: None for field in cleared}), cleared


__all__ = ["GROUNDS", "Interpretation", "InterpretationInvalid", "LABELS", "REQUIRED", "ask", "ground", "needs", "parse"]
