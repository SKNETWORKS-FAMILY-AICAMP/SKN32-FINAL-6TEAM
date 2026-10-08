# -*- coding: utf-8 -*-
"""모델이 낸 해석을 **검증**한다 — 모델은 문장을 구조로 옮기기만 하고, 쓸 수 있는지는 서버가 정한다. `[2026-10-07]`

- 프롬프트: `prompts/lodging/interpret.v1.md` (키 `lodging.interpret`). 모델 호출은 한 번이다.
- 모양이 틀리면 `InterpretationInvalid` — 고쳐 맞추지 않는다(지어내지 않는다).
- 모델이 적은 `missing` 은 되묻는 문장을 고를 때만 본다. 무엇이 빠졌는지는 `needs()` 가 값으로 다시 센다 —
  날짜가 날짜가 아니거나, 체크아웃이 체크인보다 늦지 않거나, 체크인이 오늘보다 앞이면 그 값은 없는 것으로 본다.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

#: 작업마다 서버가 움직이려면 있어야 하는 값
REQUIRED = {"search": ("keyword", "check_in", "check_out", "adults"),
            "my_stay": ("stay_name", "check_in", "check_out")}
#: 되묻는 문장에 쓰는 이름 — 모델이 문장을 주지 않았을 때만 쓴다
LABELS = {"keyword": "지역", "stay_name": "숙소 이름", "check_in": "체크인 날짜", "check_out": "체크아웃 날짜",
          "adults": "성인 인원"}


class InterpretationInvalid(ValueError):
    """모델 출력이 약속한 모양이 아니다."""


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: Literal["search", "my_stay", "status", "unclear"]
    keyword: str | None = None
    stay_name: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)
    max_price_per_night: int | None = Field(default=None, ge=1)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    domestic: bool | None = None
    missing: list[str] = Field(default_factory=list)
    question: str | None = None


def parse(raw: Any) -> Interpretation:
    if not isinstance(raw, dict):
        raise InterpretationInvalid(f"not an object: {type(raw).__name__}")
    cleaned = {key: (value.strip() or None) if isinstance(value, str) else value for key, value in raw.items()}
    try:
        return Interpretation.model_validate(cleaned)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise InterpretationInvalid(f"invalid fields: {fields}") from exc


def needs(found: Interpretation, *, today: date) -> list[str]:
    """이 해석으로 서버가 움직이려면 아직 받아야 하는 값의 이름들(순서 고정)."""
    values = found.model_dump()
    if found.check_in is not None and found.check_in < today:
        values["check_in"] = None
    if found.check_in is not None and found.check_out is not None and found.check_out <= found.check_in:
        values["check_out"] = None
    return [name for name in REQUIRED.get(found.task, ()) if values.get(name) in (None, "")]


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


__all__ = ["Interpretation", "InterpretationInvalid", "LABELS", "REQUIRED", "ask", "needs", "parse"]
