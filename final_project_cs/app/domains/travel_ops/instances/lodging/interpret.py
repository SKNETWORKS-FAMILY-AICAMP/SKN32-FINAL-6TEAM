# -*- coding: utf-8 -*-
"""모델이 낸 해석을 **검증**한다 — 모델은 문장을 구조로 옮기기만 하고, 쓸 수 있는지는 서버가 정한다. `[2026-10-07]`

- 프롬프트: `prompts/lodging/interpret.v4.md` (키 `lodging.interpret`). 모델 호출은 한 번이다.
- 모양이 틀리면 `InterpretationInvalid` — 고쳐 맞추지 않는다(지어내지 않는다).
- 모델이 적은 `missing` 은 되묻는 문장을 고를 때만 본다. 무엇이 빠졌는지는 `needs()` 가 값으로 다시 센다 —
  날짜가 날짜가 아니거나, 체크아웃이 체크인보다 늦지 않거나, 체크인이 오늘보다 앞이면 그 값은 없는 것으로 본다.
"""
from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domains.travel_ops.instances._shared.interpret_dates import (
    CALENDAR_DAYS, ground_dates, keep_quoted, model_context, settle_dates)

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
    check_in_text: str | None = None
    check_out_text: str | None = None
    #: `[2026-10-11]` 반영 못 하는 요청(문장 조각 — 「욕조 있는」 「한강이 보이는」)
    other_requests: list[str] = Field(default_factory=list)
    domestic: bool | None = None
    missing: list[str] = Field(default_factory=list)
    question: str | None = None


def parse(raw: Any) -> Interpretation:
    if not isinstance(raw, dict):
        raise InterpretationInvalid(f"not an object: {type(raw).__name__}")
    cleaned = {key: (value.strip() or None) if isinstance(value, str) else value for key, value in raw.items()}
    if not isinstance(cleaned.get("other_requests"), list):
        cleaned["other_requests"] = []
    price = cleaned.get("max_price_per_night")
    if isinstance(price, (int, float)) and not isinstance(price, bool) and price <= 0:
        # `[2026-10-16 평가 2차 I-05]` 「숙박비는 0원」 — 0 을 상한으로 내 해석 전체가 거절(escalate)됐다. 상한 없음으로 두고
        #   그 말은 「반영 못 한 요청」으로 남긴다
        cleaned["max_price_per_night"] = None
        cleaned["other_requests"] = [*cleaned["other_requests"], "숙박비 0원"]
    rating = cleaned.get("min_rating")
    if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 5 < rating <= 10:
        # ☆2026-10-11 16:13 playdata 사용자 문장 「평점 9.5 이상」 — 10점 만점 값을 그대로 내 해석 전체가 거절됐다. 5점 만점으로 바꾼다
        cleaned["min_rating"] = round(rating / 2, 2)
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


#: `[2026-10-17 GPT 검수 2차]` 되묻는 문장이 그 칸을 묻는지 볼 말 — ☆10-16 17:14 새 문장 N8-27 · N12-27: 모델이 빠진 칸을 지역 · 체크아웃 둘로 적고
#:   문장은 「어느 지역으로 찾을까요?」만 물었다. 세는 것(`missing`)이 같아도 문장이 다 묻지 않으면 서버 문장을 쓴다
_ASKS = {"keyword": r"지역|어디|어느\s*곳|동네|위치|근처",
         "stay_name": r"숙소\s*이름|어느\s*숙소|어떤\s*숙소|이름",
         "check_in": r"체크인|입실|언제|날짜|며칠|일정",
         "check_out": r"체크아웃|퇴실|몇\s*박|며칠\s*(?:동안|묵)|언제까지|박\s*수|나가",
         "adults": r"인원|몇\s*(?:분|명)|성인|어른"}


def covers(question: str, missing: list[str]) -> bool:
    """되묻는 문장이 빠진 칸을 하나도 빼지 않고 묻는가(칸마다 그 칸을 묻는 말이 있나)."""
    def asked(name: str) -> bool:
        if name == "check_out" and "check_in" in missing:
            return asked("check_in")        # 둘 다 빠졌으면 「언제 묵으실지」 한 번으로 묻는다
        return bool(re.search(_ASKS.get(name, re.escape(LABELS.get(name, name))), question))

    return all(asked(name) for name in missing)


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
    if found.question and set(found.missing) == set(missing) and covers(found.question, missing):
        return found.question
    return f"{' · '.join(LABELS[name] for name in missing)}을(를) 알려 주시면 이어서 찾아 드리겠습니다."

#: 날짜 값 → 그 값의 근거로 모델이 옮겨 적은 문장 조각 칸
GROUNDS = {"check_in": "check_in_text", "check_out": "check_out_text"}


def ground(found: Interpretation, text: str, *, has_trip: bool,
           trip: dict[str, Any] | None = None) -> tuple[Interpretation, list[str]]:
    """날짜마다 모델이 적은 근거 조각이 **고객 문장에 실제로 있는지** 본다. 없으면 그 날짜를 비운다(없는 값으로 다시 묻는다).

    ☆2026-10-08 15:26 playdata — 「서울에서 3박 할 숙소 추천해줘」에 모델이 체크인을 오늘(2026-10-08)로 지어냈다.
      프롬프트에 「지어내지 말라」가 있었는데도 그랬다. 그래서 값 대신 **근거를 받아 서버가 문장과 맞춰 본다** —
      뜻을 서버가 해석하는 것이 아니라, 모델이 인용한 글자가 문장에 있는지만 본다(공백 무시).
    `[2026-10-10]` 확인 규칙은 `_shared/interpret_dates.ground_dates` 로 옮겼다(숙소 · 항공 공용). 모델의 `missing` 은 더 보지 않는다 —
      맞는 날짜를 missing 에 적어 지워지던 것이 17:55 · 17:58 측정의 숙소 오답 대부분이었다.
    """
    found, cleared = ground_dates(found, text, grounds=GROUNDS, start="check_in", end="check_out", has_trip=has_trip, trip=trip)
    return found.model_copy(update={"other_requests": keep_quoted(found.other_requests, text)}), cleared


#: 「N만원대」 — 문장에 하나만 있을 때 상한을 그 구간 끝으로 맞춘다(프롬프트 규칙: 15만원대 → 159999, 20만원대 → 299999)
_BAND = re.compile(r"(\d+)\s*만\s*원?\s*대")
#: 「1박(에) 40까지」 「하루 30 정도」처럼 단위 없는 가격 숫자(만 · 원 · 천 · 박 · 명 · 일 · 월 · 시가 붙지 않은 2~3자리)
#: 「2박으로 100만원」 — 박 수 바로 뒤의 가격은 머무는 동안 전체 값이다(1박 상한 = 값 ÷ 박 수). 「1박에 40」은 1박 값
_TOTAL_PRICE = re.compile(r"(\d+)박(?:으로|에|동안|간)?(?:총)?(\d+)만원?")
_BARE_PRICE = re.compile(r"(?:1박|하루|박당)에?(?:최대)?(\d{2,3})(?=까지|까진|이하|이내|선|정도|쯤|아래|안쪽)")


def settle_years(found: Interpretation, *, today: date, text: str = "") -> tuple[Interpretation, list[str]]:
    """날 · 연도 · 요일을 근거 조각과 맞추고(`_shared/interpret_dates.settle_dates`), 가격 구간 상한을 맞춘다. (해석, 고친 칸)

    ☆2026-10-10 21:59 playdata 해석 측정 — 「15만원대」를 150000 으로 냈다(프롬프트 예시는 159999). 모델 값이 구간의 **시작**과 같을
      때만 끝으로 바꾼다(다른 값이면 모델이 다르게 읽은 것이니 건드리지 않는다).
    """
    found, fixed = settle_dates(found, grounds=GROUNDS, today=today, text=text)
    squeezed = "".join((text or "").split())
    quote = "".join((found.check_out_text or "").split())
    uses = squeezed.count(quote) if quote else 0
    if found.check_out is not None and quote in ("하루", "1박") and uses \
            and uses == len(re.findall(re.escape(quote) + r"에?(?:약)?\d+만", squeezed)):
        # ☆2026-10-11 16:21 「가격은 하루에 15만원정도」 — 가격 말의 「하루」를 숙박 일수로 읽어 체크아웃을 만들었다
        found, fixed = found.model_copy(update={"check_out": None}), [*fixed, "check_out"]
    bare = _BARE_PRICE.findall(squeezed)
    if len(bare) == 1 and found.max_price_per_night in (int(bare[0]), int(bare[0]) * 1000):
        # ☆16:21 「1박에 40까진 쓸게」 — 단위 없는 숫자를 40000 으로 읽었다. 숙소 1박 가격의 맨숫자는 만 원 단위다
        found, fixed = found.model_copy(update={"max_price_per_night": int(bare[0]) * 10000}), [*fixed, "max_price_per_night"]
    totals = _TOTAL_PRICE.findall(squeezed)
    if len(totals) == 1 and int(totals[0][0]) > 1 and found.max_price_per_night == int(totals[0][1]) * 10000:
        # ☆2026-10-11 17:50 playdata U-L03 「2박으로 100만원 정도」 — 전체 값 100만원을 1박 상한으로 냈다(16:50 에는 50만원으로 맞게)
        nights, total = int(totals[0][0]), int(totals[0][1]) * 10000
        found, fixed = found.model_copy(update={"max_price_per_night": total // nights}), [*fixed, "max_price_per_night"]
    bands = _BAND.findall(text or "")
    if len(bands) == 1 and found.max_price_per_night == int(bands[0]) * 10000:
        n = int(bands[0])
        top = n * 10000 + (99999 if n % 10 == 0 else 9999)
        found, fixed = found.model_copy(update={"max_price_per_night": top}), [*fixed, "max_price_per_night"]
    return found, fixed


#: `[2026-10-15 사용자 판정 L02]` 모델이 날짜를 비웠을 때만 쓰는 규칙 — 「11월 14일부터 2박」
_RULE_MONTH_DAY = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_RULE_NIGHTS = re.compile(r"(?<!\d)(\d{1,2})\s*박(?!\s*에?\s*(?:최대\s*)?\d+\s*만)(?!\s*\d+\s*만)")
_RULE_UNTIL = re.compile(r"(?<!\d)(\d{1,2})\s*일\s*까지")
#: 「1/12부터 3박」 — 범위가 아닌 「월/일」 하나(☆10-16 최종 평가 N5-18: 모델이 비워 되물음)
_RULE_SLASH_DAY = re.compile(r"(?<![\d/.~\-–])(?<![~\-–]\s)(?:20\d{2}\s*[./]\s*)?(\d{1,2})\s*/\s*(\d{1,2})(?!\s*[\d/~\-–])")


def rule_dates(found: Interpretation, text: str, *, today: date) -> tuple[Interpretation, bool]:
    """모델이 체크인을 **비웠을 때만** 문장 규칙으로 채운다. (해석, 채웠나)

    ☆2026-10-15 17:49 playdata 검수 L02 — 「11월 14일부터 2박 어른 2명 아이 2명 …」에서 모델이 날짜를 비워 되물었다(17:32 에는 읽음).
    문장에 「N월 N일」이 **하나**이고 박 수(가격 말 「1박 20만 원」은 뺀다)가 한 값이거나 「N일까지」가 있을 때만 — 애매하면 그대로 둔다.
    연도는 오늘 뒤로 가장 가까운 해. 근거 조각(`check_in_text` · `check_out_text`)도 문장 글자 그대로 남긴다."""
    if found.check_in is not None or found.task not in ("search", "my_stay"):
        return found, False
    days = list(_RULE_MONTH_DAY.finditer(text or "")) or list(_RULE_SLASH_DAY.finditer(text or ""))
    if len(days) != 1:
        return found, False
    month, day = int(days[0].group(1)), int(days[0].group(2))
    try:
        start = date(today.year, month, day)
        if start < today:
            start = date(today.year + 1, month, day)
    except ValueError:
        return found, False
    nights = {int(match.group(1)) for match in _RULE_NIGHTS.finditer(text)}
    until = list(_RULE_UNTIL.finditer(text))
    end, end_text = None, None
    if len(nights) == 1 and not until:
        count = nights.pop()
        if 1 <= count <= 30:
            end, end_text = start + timedelta(days=count), f"{count}박"
    elif not nights and len(until) == 1:
        try:
            end = date(start.year, start.month, int(until[0].group(1)))
        except ValueError:
            end = None
        end_text = until[0].group(0) if end and end > start else None
        end = end if end_text else None
    update = {"check_in": start, "check_in_text": days[0].group(0)}
    if end is not None and found.check_out is None:
        update.update(check_out=end, check_out_text=end_text)
    return found.model_copy(update=update), True


#: `[2026-10-16 평가 2차]` 날짜 범위 표기 — 「12/24~26」 「1/23~25」 「12/18-12/20」 「1월 15~17일」 「11월 18일~19일」
#:  「11월 29일 들어가서 12월 1일 나올」 「1월 9일 입실 11일 퇴실」. 모델이 체크아웃을 비우거나(근거 조각이 문장 글자와 달라 지워짐)
#:  「1/11~13」을 11/1~11/13 으로 읽었다. 문장에 범위가 **하나**일 때만 쓴다
_RANGE_SLASH = re.compile(r"(?<![\d/.])(?:20\d{2}\s*[./]\s*)?(\d{1,2})\s*[/.]\s*(\d{1,2})\s*(?:일)?\s*[~\-–]\s*(?:(\d{1,2})\s*[/.]\s*)?(\d{1,2})(?![\d/.])")
#: `[2026-10-16 최종 평가 뒤]` 「11월 28~29」(끝 「일」 없음) · 「2027.1.22~24」(연도 앞붙음)도 범위 — 끝 숫자 뒤가 값 단위(만 · 원 · 박 · 명)면 아니다
#: `[2026-10-18 D23b]` 「1월 16일 토욜~18일 월욜」 — 요일이 사이에 끼어도 범위(☆D23 fix-set N31-26)
_RANGE_KO = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일?\s*(?:\(?\s*[월화수목금토일](?:요일|욜)?\s*\)?\s*)?(?:부터)?\s*[~\-–]\s*(?:(\d{1,2})\s*월\s*)?(\d{1,2})"
                       r"(?:\s*일|(?![\d.])(?!\s*(?:만|천|원|박|명|인|시|분|%)))")
_RANGE_WORDS = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:에\s*)?(?:들어가|입실|체크\s*인|드러가)[^0-9]{0,12}?"
                          r"(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일\s*(?:에\s*)?(?:나오|나올|나와|나가|퇴실|체크\s*아웃)")


#: `[2026-10-18 D22]` 「12월 31일 밤부터 1월 1일 아침까지」 — 시작 · 끝이 「부터 … 까지」로 이어진 범위(☆5차 N25-22)
_RANGE_FROM_TO = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일[^0-9]{0,8}?부터[^0-9]{0,6}?(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일[^0-9]{0,6}?까지")


#: `[2026-10-18 D23]` 「도착 11월 19일 / 퇴실 11월 22일」 「체크인 1월 3일, 체크아웃 1월 5일」 — 말이 날짜 앞에 붙은 범위(☆6차 N31-07)
_RANGE_LABELS = re.compile(r"(?:도착|입실|체크\s*인)\s*(?:은|는|일은|:)?\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일[^0-9]{0,8}?"
                           r"(?:퇴실|체크\s*아웃|출발)\s*(?:은|는|일은|:)?\s*(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일")


def _next_date(today: date, month: int, day: int) -> date | None:
    try:
        found = date(today.year, month, day)
        return date(today.year + 1, month, day) if found < today else found
    except ValueError:
        return None


def rule_ranges(found: Interpretation, text: str, *, today: date) -> tuple[Interpretation, bool]:
    """문장의 날짜 범위가 하나로 정해지면 체크인 · 체크아웃을 그 값으로(모델 값이 다르거나 비었을 때). (해석, 고쳤나)"""
    if found.task not in ("search", "my_stay"):
        return found, False
    hits = [m for pattern in (_RANGE_KO, _RANGE_WORDS, _RANGE_SLASH, _RANGE_FROM_TO, _RANGE_LABELS) for m in pattern.finditer(text or "")]
    if len({tuple(m.groups()) for m in hits}) != 1:        # 없거나 둘 이상이면 모델 값 그대로
        return found, False
    month, day, end_month, end_day = hits[0].groups()
    start = _next_date(today, int(month), int(day))
    if start is None:
        return found, False
    month_out = int(end_month) if end_month else start.month
    year_out = start.year + (1 if month_out < start.month else 0)
    try:
        end = date(year_out, month_out, int(end_day))
    except ValueError:
        return found, False
    if not end_month and end <= start:              # 「12/30~2」 — 다음 달로 넘어간 날
        nxt = (start.month % 12) + 1
        try:
            end = date(start.year + (1 if nxt == 1 else 0), nxt, int(end_day))
        except ValueError:
            return found, False
    if end <= start or (end - start).days > 30:
        return found, False
    if found.check_in == start and found.check_out == end:
        return found, False
    return found.model_copy(update={"check_in": start, "check_out": end, "check_in_text": hits[0].group(0),
                                    "check_out_text": hits[0].group(0)}), True


#: `[2026-10-16 최종 평가 뒤]` 요일로 말한 날짜 — 모델이 「1월 둘째 주 금요일」을 1/15, 「다음 달 첫 주말」을 11/4 로 읽었고
#:  「3주 뒤 금요일」은 비웠다(N1-03 · N3-01 · N2-30). 달력 계산이라 서버가 한다. 문장에 이런 말이 **하나**일 때만
_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_ORDINALS = {"첫": 1, "첫째": 1, "둘째": 2, "두번째": 2, "셋째": 3, "세번째": 3, "넷째": 4, "네번째": 4, "다섯째": 5, "마지막": -1}
_NTH_WEEKDAY = re.compile(r"(?:(\d{1,2})\s*월|(다음\s*달|담달|이번\s*달))\s*(?:의\s*)?(첫째|첫|둘째|두\s*번째|셋째|세\s*번째|넷째|네\s*번째|다섯째|마지막)\s*"
                          r"(?:주\s*(?:의\s*)?)?(?:([월화수목금토일])(?:요일|욜)|(주말))")
#: `[2026-10-17 D17]` 「다음 달 주말」(차례 말 없음) — 그 달 첫 주말로(☆N10-11: 모델이 10/21 로 읽었다)
_MONTH_WEEKEND = re.compile(r"(?:(\d{1,2})\s*월|(다음\s*달|담달|이번\s*달))\s*(?:의\s*)?주말")
#: `[2026-10-17 D20]` 「다음 달 중순 주말」 「11월 말 주말」 「다음 달 초 주말」 — 모델이 11/12(목) · 10/30(이번 달)으로 읽었다(☆4차 N24-05 · N24-23).
#:  초 = 첫 토요일, 중순 = 11일 이후 첫 토요일, 말 · 하순 = 마지막 토요일. 토 → 일 1박(박수가 있으면 그 박수). 「11월 중에 주말」은 아니다(F-06)
_MONTH_PART_WEEKEND = re.compile(r"(?:(\d{1,2})\s*월|(다음\s*달|담달|이번\s*달))\s*(?:의\s*)?(초순|초|중순|하순|말)\s*(?:쯤\s*)?(?:의\s*|에\s*)?주말")
_WEEKS_LATER = re.compile(r"(\d|한|두|세|네|다섯)\s*주\s*(?:뒤|후)\s*(?:의\s*)?(?:([월화수목금토일])(?:요일|욜)|(주말))")
_WEEK_NUM = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}


def _nth_weekday(year: int, month: int, nth: int, weekday: int) -> date | None:
    if nth == -1:
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        last = nxt - timedelta(days=1)
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = date(year, month, 1)
    day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    return day if day.month == month else None


def rule_weekdays(found: Interpretation, text: str, *, today: date) -> tuple[Interpretation, bool]:
    """「N월 둘째 주 금요일」 · 「다음 달 첫 주말」 · 「3주 뒤 금요일」 → 체크인(모델 값과 다르면 바꾼다). 체크아웃은 박수로, 박수가 없고
    「주말」이면 토 → 일 1박, 그 밖엔 비운다(되묻는다). (해석, 고쳤나)"""
    if found.task != "search":
        return found, False
    hits = list(_NTH_WEEKDAY.finditer(text or "")) + list(_WEEKS_LATER.finditer(text or "")) + list(_MONTH_WEEKEND.finditer(text or "")) \
        + list(_MONTH_PART_WEEKEND.finditer(text or ""))
    if len({m.group(0) for m in hits}) != 1:
        return found, False
    m = hits[0]
    part = None
    if m.re is _MONTH_PART_WEEKEND:
        month_word, relative, part = m.groups()
        ordinal, day_word, weekend = "첫", None, "주말"
    if m.re is _MONTH_WEEKEND:
        month_word, relative = m.groups()
        ordinal, day_word, weekend = "첫", None, "주말"
    if m.re in (_NTH_WEEKDAY, _MONTH_WEEKEND, _MONTH_PART_WEEKEND):
        if m.re is _NTH_WEEKDAY:
            month_word, relative, ordinal, day_word, weekend = m.groups()
        if month_word:
            month = int(month_word)
            year = today.year + (1 if month < today.month else 0)
        else:
            month = today.month % 12 + 1 if re.sub(r"\s", "", relative) in ("다음달", "담달") else today.month
            year = today.year + (1 if month < today.month else 0)
        if not 1 <= month <= 12:
            return found, False
        start = _nth_weekday(year, month, _ORDINALS[re.sub(r"\s", "", ordinal)], _WEEKDAYS[day_word] if day_word else 5)
        if part == "중순" and start is not None:
            start = date(year, month, 11) + timedelta(days=(5 - date(year, month, 11).weekday()) % 7)
        elif part in ("하순", "말"):
            start = _nth_weekday(year, month, -1, 5)
    else:
        count, day_word, weekend = m.groups()
        weeks = int(count) if count.isdigit() else _WEEK_NUM[count]
        later = today + timedelta(days=7 * weeks)
        start = later + timedelta(days=(_WEEKDAYS[day_word] if day_word else 5) - later.weekday())
    if start is None or start < today:
        return found, False
    counts = {int(n.group(1)) if n.group(1) else _NIGHT_WORDS["".join(n.group(2).split())] for n in _NIGHTS.finditer(text or "")}
    next_day = re.search(r"(?:다음\s*날|담날|이튿날)[^.,]{0,8}?(?:나오|나올|나가|퇴실|체크\s*아웃)", text or "")
    nights = counts.pop() if len(counts) == 1 else (1 if weekend or next_day else None)
    end = start + timedelta(days=nights) if nights and 1 <= nights <= 30 else None
    if found.check_in == start and (end is None or found.check_out == end):
        return found, False
    return found.model_copy(update={"check_in": start, "check_out": end, "check_in_text": m.group(0),
                                    "check_out_text": m.group(0) if end else None}), True


#: `[2026-10-16 평가 4차]` 체크인만 있고 체크아웃이 비었을 때 박수 — 「11월 12일부터 하룻밤」(G-38)을 모델이 비워 되물었다.
#: 「1박 6만 원」 · 「1박에 10만」 · 「1박당」처럼 값 단위로 쓴 「N박」은 박수가 아니다
_NIGHTS = re.compile(r"(\d+)\s*박(?!\s*(?:에\s*|당\s*|최대\s*|최고\s*|기준\s*|은\s*|는\s*|방값\s*|요금\s*|가격\s*|숙박비\s*|비용\s*)*[\d,]+\s*(?:만|천|원))(?!\s*당)|(하룻\s*밤|한\s*밤|두\s*밤|세\s*밤|이틀\s*밤|사흘\s*밤)")
_NIGHT_WORDS = {"하룻밤": 1, "한밤": 1, "두밤": 2, "이틀밤": 2, "세밤": 3, "사흘밤": 3}


def rule_nights(found: Interpretation, text: str) -> tuple[Interpretation, bool]:
    """체크인은 있는데 체크아웃이 없으면, 문장의 박수가 하나로 정해질 때 체크아웃 = 체크인 + 박수. (해석, 채웠나)"""
    if found.task != "search" or found.check_in is None or found.check_out is not None:
        return found, False
    counts = {int(m.group(1)) if m.group(1) else _NIGHT_WORDS["".join(m.group(2).split())] for m in _NIGHTS.finditer(text or "")}
    if len(counts) != 1 or not 1 <= (nights := counts.pop()) <= 30:
        return found, False
    return found.model_copy(update={"check_out": found.check_in + timedelta(days=nights)}), True


#: `[2026-10-16 평가 2차]` 날 숫자도 · 정해진 날 말도 없는 근거(「주말」 「연말」 「11월 중」)는 날짜로 쓰지 않는다 — 「11월 중에 주말 2박」을 11/6~8 로 정했다
#: 「1월의 마지막 토요일」 · 「첫째 주 금요일」처럼 몇째 요일도 날짜(F-33). 「주말」만 있으면 어느 주인지 몰라 날짜가 아니다
_DAY_GIVEN = re.compile(r"\d+\s*일|\d+\s*[/.]\s*\d+|오늘|내일|모레|이번|다음|담주|금주|크리스마스|성탄|이브|새해|신정|첫날|마지막\s*날|말일|\d+\s*(?:st|nd|rd|th)|"
                        r"(?:첫|첫째|둘째|셋째|넷째|다섯째|마지막)\s*(?:주\s*)?(?:[월화수목금토일]요일|주말)|"
                        r"(?:\d|한|두|세|네|다섯)\s*주\s*(?:뒤|후)|"
                        # `[2026-10-17 D17]` 「12월 24~26」의 근거 조각 「12월 24」(일 없음) · 「한 달 뒤에」(☆N12-02 · N10-14 — 모델 값이 맞는데 비웠다)
                        r"\d{1,2}\s*월\s*\d{1,2}|(?:\d|한|두|세)\s*달\s*(?:뒤|후)|"
                        r"(?:first|second|third|fourth|last)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend)|"
                        r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", re.I)
#: 「오늘 · 내일」은 숙박 말과 붙어 있을 때만 날짜 — 「오늘 날씨 진짜 추운데」의 「오늘」을 체크인으로 읽었다(H-39)
_RELATIVE_STAY = re.compile(r"(오늘|내일|모레)\s*(?:부터|밤|하룻밤|\d+\s*박|체크\s*인|입실|묵|숙박|자|들어|저녁|당일|1박)")
#: 인원 근거 — 숫자 + 명 · 인, 혼자 · 둘 · 커플 · 부부 …. 없는데 모델이 인원을 냈으면 지운다(B-22 「부모님 모시고」를 2명으로)
_PEOPLE = re.compile(r"\d+\s*(?:명|인(?!실)|분|adults?|people|persons?|pax)|(?<![가-힣])[일이삼사오]\s*인(?!실|분|용|가|데)|혼자|혼행|혼숙|한\s*명|두\s*명|세\s*명|네\s*명|다섯|여섯|"
                     r"둘|셋|넷|성인|어른|부부|커플|연인|여자\s*친구|남자\s*친구|여친|남친|신혼|solo|couple|single|"
                     # 「엄마랑 아빠, 그리고 아기 세 식구」(H-31) — 식구 수 · 엄마 아빠 둘 다는 인원 근거. 「부모님 모시고」는 아니다(B-22)
                     r"\d+\s*식구|[두세네]\s*식구|다섯\s*식구|엄마.{0,6}아빠|아빠.{0,6}엄마", re.I)


#: `[2026-10-17 D17]` 「1월 15일부터」처럼 시작을 못박은 날짜 — 모델이 「새해 1월 15일부터」를 1/1 로 읽었다(☆N7-20)
_START_DAY = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:부터|에\s*(?:들어|체크\s*인|입실)|체크\s*인|입실)")


def rule_start(found: Interpretation, text: str, *, today: date) -> tuple[Interpretation, bool]:
    """문장에 「N월 N일부터」가 **하나**인데 모델 체크인이 그 날이 아니면 체크인을 그 날로(체크아웃은 박수를 지켜 같이 옮긴다). (해석, 고쳤나)"""
    if found.task != "search" or found.check_in is None:
        return found, False
    hits = {m.groups() for m in _START_DAY.finditer(text or "")}
    if len(hits) != 1:
        return found, False
    month, day = (int(x) for x in hits.pop())
    start = _next_date(today, month, day)
    if start is None or (found.check_in.month, found.check_in.day) == (month, day):
        return found, False
    end = start + (found.check_out - found.check_in) if found.check_out is not None and found.check_out > found.check_in else None
    return found.model_copy(update={"check_in": start, "check_out": end}), True


#: `[2026-10-17 D17]` 「저랑 부모님 두 분」 「나랑 부모님」 — 성인 3명(☆N7-21 · N8-22: 모델이 비워 되물었다). 「부모님 모시고」만은 그대로 둔다(B-22)
#: `[2026-10-17 D19]` 「저랑 남편이랑」 「나랑 와이프」 — 성인 2명(☆qa_1017_200257 N15-21: 모델이 비워 되물었다)
_ME_AND_PARTNER = re.compile(r"(?:나|저)\s*(?:랑|하고|와|이랑)\s*,?\s*(?:우리\s*)?(?:남편|아내|와이프|신랑|배우자|남친|여친|애인|남자\s*친구|여자\s*친구)")
_ME_AND_PARENTS = re.compile(r"(?:나|저)\s*(?:랑|하고|와|이랑)\s*,?\s*(?:우리\s*)?부모님|부모님\s*(?:두\s*분)?\s*(?:이랑|하고|과|와|랑)\s*(?:나|저)(?![가-힣])")


#: `[2026-10-18 D22]` 「나 포함 성인 친구 다섯」 — 다섯이 모두(모델이 6명으로 셌다, ☆5차 N25-23) · 「이인 숙소」 — 2명(☆N28-02)
_COUNT_WORDS = {"둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8}
_WITH_ME = re.compile(r"(?:나|저)\s*(?:까지\s*)?포함(?:해서|하면|해)?\s*(?:\S+\s*){0,3}?(\d|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟)\s*(?:명|이|사람)?(?![가-힣]*(?:박|살|시|분))")
_SINO_PEOPLE = re.compile(r"(?<![가-힣])(일|이|삼|사|오)\s*인(?!실|분|용|가|데)")


def rule_people(found: Interpretation, text: str) -> tuple[Interpretation, bool]:
    """모델이 성인 수를 비웠고 문장이 「나 + 부모님」이면 성인 3명. (해석, 채웠나)"""
    if found.task != "search":
        return found, False
    me = _WITH_ME.search(text or "")
    if me and not found.children:
        total = int(me.group(1)) if me.group(1).isdigit() else _COUNT_WORDS.get(me.group(1))
        if total and found.adults != total:
            return found.model_copy(update={"adults": total}), True
    if found.adults is not None:
        return found, False
    sino = _SINO_PEOPLE.search(text or "")
    if sino:
        return found.model_copy(update={"adults": "일이삼사오".index(sino.group(1)) + 1}), True
    if _ME_AND_PARENTS.search(text or ""):
        return found.model_copy(update={"adults": 3}), True
    if _ME_AND_PARTNER.search(text or ""):
        return found.model_copy(update={"adults": 2}), True
    return found, False


#: `[2026-10-17 D20]` 말로 쓴 날짜를 숫자 날짜로 — 「11월 열흘」 「스물여덟 날」 「열하룻날」 「일곱째 날」 「11-18」 「2027-01-28」 「이틀 자고」 「이박」
#:  ☆qa_1017_214452(4차 held-out) 21건: 모델이 날짜를 비우거나, 근거 조각(「11월 열흘에」)이 숫자가 아니라 `rule_checks` 가 지웠다.
#:  뜻을 새로 정하지 않고 글자만 숫자로 바꾼 문장을 기존 규칙(`rule_ranges` · `rule_dates` · `rule_nights`)에 다시 넣는다.
_NATIVE_ONES = {"하나": 1, "한": 1, "하루": 1, "하룻": 1, "둘": 2, "두": 2, "이틀": 2, "셋": 3, "세": 3, "사흘": 3, "넷": 4, "네": 4, "나흘": 4,
                "이튿": 2, "사흗": 3, "나흗": 4,          # `[2026-10-18 D22]` 「열이튿날 · 열나흗날」(ㄷ 받침 꼴, ☆5차 N27-25)
                "다섯": 5, "닷새": 5, "여섯": 6, "엿새": 6, "일곱": 7, "이레": 7, "여덟": 8, "여드레": 8, "아홉": 9, "아흐레": 9}
_NATIVE_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30}
_ONES = "|".join(sorted(_NATIVE_ONES, key=len, reverse=True))
_NATIVE_DAY = re.compile(rf"(?:(열흘|보름)|(열|스물|스무|서른)\s*({_ONES})?|({_ONES}))(?=\s*(?:째\s*)?(?:날|일)|\s*(?:에|부터|까지|입실|퇴실|체크|들어|나오|나와|나올|나가|가서|~|$|[,.!\s]))")
_ORDINAL_DAY = re.compile(rf"(?<![가-힣])((?:열|스물|스무|서른)(?:\s*(?:{_ONES}))?|{_ONES}|첫)\s*(?:번\s*)?째\s*날")   # `[2026-10-18 D23]` 「스물두 번째 날」(☆6차 N31-28)
_ISO_DAY = re.compile(r"(?<![\d\-/.])(?:(20\d{2})\s*-\s*)?(\d{1,2})\s*-\s*(\d{1,2})(?![\d\-])")
_SPAN_WORDS = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5}
_SPAN = re.compile(r"(하루|이틀|사흘|나흘|닷새)(?=\s*(?:만\s*)?(?:자|묵|숙박(?!비|료)|머물|지내|밤(?!\s*(?:에\s*)?\S*\s*\S*만)|동안|뒤|후|있))")   # `[2026-10-18 D24]` 「하루 숙박비」는 가격
#: `[2026-10-18 D23]` 「…부터 이틀이야」 「…부터 사흘!」 「숙박은 하루예요」 — 날 수를 박 수로(평가 라벨: 이틀 = 2박 · 사흘 = 3박, ☆6차 N31-15 · N31-20 · N31-27 · N33-03)
_SPAN_FROM = re.compile(r"(?:부터|에서)\s*(하루|이틀|사흘|나흘|닷새)(?![가-힣]*(?:\s*(?:뒤|후|전)))(?=\s*(?:이야|이에요|예요|요|만|간|동안|지낼|지내|묵|머물|자|!|,|\.|$|\s))"
                        r"|(?:숙박|묵는\s*건|자는\s*건|머무는\s*건|머무르는\s*건)\s*(?:은|는|이|기간은)?\s*(하루|이틀|사흘|나흘|닷새)")
_SINO_NIGHTS = re.compile(r"(?<![가-힣])(일|이|삼|사|오)\s*박(?![가-힣])")
_COUNT_NIGHTS = re.compile(r"(?<![가-힣])(두|세|네)\s*밤")


def _native_number(tens: str | None, ones: str | None) -> int | None:
    value = (_NATIVE_TENS.get(tens or "", 0)) + (_NATIVE_ONES.get(ones or "", 0))
    return value or None


_SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
#: `[2026-10-18 D22]` 「11월 십팔일」(한자어 수사, ☆5차 N25-07) · 「12월의 마지막 밤」 · 「새해 첫날」(☆N25-22) · 「새해 1월 2일」(☆N27-21)
_SINO_DAY = re.compile(r"(\d{1,2})\s*월\s*((?:[이삼]?십)?[일이삼사오육칠팔구]?)\s*일")
_MONTH_LAST = re.compile(r"(\d{1,2})\s*월\s*의?\s*마지막\s*(?:날|밤)")


def _sino(word: str) -> int | None:
    m = re.fullmatch(r"([이삼]?)(십)?([일이삼사오육칠팔구]?)", word or "")
    if not m or not word:
        return None
    tens = (_SINO.get(m.group(1), 1) if m.group(2) else 0) * 10 if (m.group(2) or not m.group(1)) else None
    if tens is None:
        return None
    return tens + _SINO.get(m.group(3), 0) or None


def spoken_days(text: str) -> str:
    """말로 쓴 날짜 · 박수를 숫자로 바꾼 문장. 바꿀 것이 없으면 그대로. 「N월」 뒤이거나, 들어가고 나오는 말 · 「째 날」이 붙은 것만 날로 본다."""
    out = text or ""
    out = re.sub(r"(?<![가-힣])(십일|십이|시)\s*월", lambda m: {"십일": "11", "십이": "12", "시": "10"}[m.group(1)] + "월", out)   # `[2026-10-18 D24]` 「십일월 십사일」(☆7차 N39-04 · N41-01)
    out = _SINO_DAY.sub(lambda m: f"{m.group(1)}월 {_sino(m.group(2))}일" if _sino(m.group(2)) and _sino(m.group(2)) <= 31 else m.group(0), out)
    # `[2026-10-18 D24]` 달 없이 쓴 끝날 「십육일 퇴실」(☆7차 N39-04)
    out = re.sub(r"(?<![가-힣\d])((?:[이삼]?십)[일이삼사오육칠팔구]?)\s*일(?=\s*(?:에\s*)?(?:퇴실|체크\s*아웃|나오|나와|나올|나가|까지))",
                 lambda m: f"{_sino(m.group(1))}일" if _sino(m.group(1)) and _sino(m.group(1)) <= 31 else m.group(0), out)

    def last_day(m: re.Match) -> str:
        month = int(m.group(1))
        if not 1 <= month <= 12:
            return m.group(0)
        nxt = date(2001 if month < 12 else 2002, month % 12 + 1, 1)
        return f"{month}월 {(nxt - timedelta(days=1)).day}일"
    out = _MONTH_LAST.sub(last_day, out)
    out = re.sub(r"새해\s*첫\s*날", "1월 1일", out)
    out = re.sub(r"(\d{1,2}\s*월\s*)(열흘|보름)\s*째\s*(?:되는\s*)?날", lambda m: m.group(1) + ("10일" if m.group(2) == "열흘" else "15일"), out)   # `[2026-10-18 D24]` 「11월 열흘째 되는 날」(☆7차 N37-03)
    out = re.sub(r"(?<![가-힣])(열한|열두|열)\s*월", lambda m: {"열": "10", "열한": "11", "열두": "12"}[m.group(1)] + "월", out)   # `[2026-10-18 D23]` 「열한 월」(☆6차 N33-03)
    out = re.sub(r"새해\s*(?=\d{1,2}\s*월)", "", out)
    out = _ISO_DAY.sub(lambda m: f"{int(m.group(2))}월 {int(m.group(3))}일" if 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31
                       else m.group(0), out)

    def ordinal(m: re.Match) -> str:
        word = "".join(m.group(1).split())
        if word == "첫":
            return "1일"
        tens = next((t for t in _NATIVE_TENS if word.startswith(t)), None)
        rest = word[len(tens):] if tens else word
        rest = {"둘": "둘", "셋": "셋", "넷": "넷"}.get(rest, rest)
        value = _native_number(tens, rest or None)
        return f"{value}일" if value and value <= 31 else m.group(0)
    out = _ORDINAL_DAY.sub(ordinal, out)

    def native(m: re.Match) -> str:
        special, tens, ones, alone = m.groups()
        before = out[:m.start()]
        month_before = re.search(r"\d{1,2}\s*월\s*$", before)
        if special:                                 # 「11월 열흘에」 「8일~열흘」 「여드레에 가서 열흘에 나와」 — 날. 「열흘 동안」은 아니다
            day_like = month_before or re.search(r"(?:~|부터|가서|들어가\S*|입실\S*|일\s*에?)\s*$", before) \
                or re.match(r"\s*(?:에|부터|까지|입실|퇴실|체크|나오|나와|나올|나가)", out[m.end():])
            return ("10일" if special == "열흘" else "15일") if day_like else m.group(0)
        if alone and alone in _SPAN_WORDS and not month_before:
            return m.group(0)                       # 「이틀 자고」는 박수 — 아래에서 바꾼다
        if alone and not month_before and not re.search(r"(?:~|부터|들어가\S*|입실\S*|가서|일\s*에?)\s*$", before):
            return m.group(0)                       # 「다섯 명」 「둘이」 같은 말은 날이 아니다
        if alone in ("한", "두", "세", "네", "하룻", "이튿", "사흗", "나흗"):
            # `[2026-10-18 D23]` 「이튿날 퇴실」은 다음 날이다(「2일」이 아님) — ㄷ 꼴은 「열이튿날」처럼 십 단위와 함께일 때만 날(☆6차 N33-21 · N35-20)
            return m.group(0)
        value = _native_number(tens, ones) if tens else _NATIVE_ONES.get(alone or "")
        if not value or value > 31:
            return m.group(0)
        tail = out[m.end():]
        return f"{value}일" + ("" if re.match(r"\s*(?:째\s*)?(?:날|일)", tail) else "")
    out = _NATIVE_DAY.sub(native, out)
    out = re.sub(r"(\d{1,2})일\s*(?:째\s*)?(?:날|일)", r"\1일", out)        # 「28일 날」 「11일날」 → 「28일」
    out = _SPAN_FROM.sub(lambda m: m.group(0).replace(m.group(1) or m.group(2), f"{_SPAN_WORDS[m.group(1) or m.group(2)]}박"), out)
    out = _SPAN.sub(lambda m: f"{_SPAN_WORDS[m.group(1)]}박", out)
    out = _SINO_NIGHTS.sub(lambda m: f"{'일이삼사오'.index(m.group(1)) + 1}박", out)
    out = _COUNT_NIGHTS.sub(lambda m: f"{'두세네'.index(m.group(1)) + 2}박", out)
    return out


#: `[2026-10-17 D20]` 체크인은 있는데 체크아웃이 빈 때 — 「4일 아침에 나와요」 「셋째 날 체크아웃」 「토욜 아침에 나와요」 「월요일에 나오는」 「다음 날 나와요」
_END_DAY = re.compile(r"(?<!\d)(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일\s*(?:에\s*|아침\s*에?\s*|오전\s*에?\s*)?(?:까지|나오|나와|나올|나가|나갈|퇴실|체크\s*아웃)")
_END_WEEKDAY = re.compile(r"([월화수목금토일])(?:요일|욜)\s*(?:에\s*|아침\s*에?\s*|오전\s*에?\s*)?(?:까지|나오|나와|나올|나가|나갈|퇴실|체크\s*아웃)")
_END_NEXT = re.compile(r"(?:다음\s*날|담날|이튿날)\s*(?:에\s*|아침\s*에?\s*)?(?:나오|나와|나올|나가|퇴실|체크\s*아웃)"
                       # `[2026-10-18 D22]` 「퇴실은 그 이튿날」(말 순서가 반대, ☆5차 N25-16)
                       r"|(?:퇴실|체크\s*아웃)\s*(?:은|는|일은)?\s*(?:그\s*)?(?:다음\s*날|이튿날|담날)")


def rule_end(found: Interpretation, text: str) -> tuple[Interpretation, bool]:
    """체크인만 있을 때 문장의 나오는 날(하나로 정해질 때)로 체크아웃. (해석, 채웠나)"""
    if found.task != "search" or found.check_in is None or found.check_out is not None:
        return found, False
    start, ends = found.check_in, set()
    for m in _END_DAY.finditer(text or ""):
        month = int(m.group(1)) if m.group(1) else start.month
        year = start.year + (1 if month < start.month else 0)
        try:
            end = date(year, month, int(m.group(2)))
        except ValueError:
            continue
        if not m.group(1) and end <= start:        # 「12월 30일 … 2일까지」 — 다음 달
            nxt = start.month % 12 + 1
            try:
                end = date(start.year + (nxt == 1), nxt, int(m.group(2)))
            except ValueError:
                continue
        ends.add(end)
    for m in _END_WEEKDAY.finditer(text or ""):
        gap = (_WEEKDAYS[m.group(1)] - start.weekday()) % 7 or 7
        ends.add(start + timedelta(days=gap))
    if _END_NEXT.search(text or ""):
        ends.add(start + timedelta(days=1))
    ends = {end for end in ends if 0 < (end - start).days <= 30}
    if len(ends) != 1:
        return found, False
    return found.model_copy(update={"check_out": ends.pop()}), True


def rule_spoken(found: Interpretation, text: str, *, today: date) -> tuple[Interpretation, bool]:
    """말로 쓴 날짜를 숫자로 바꾼 문장으로 날짜 규칙을 한 번 더 돌린다(`rule_checks` 뒤). (해석, 고쳤나)"""
    if found.task != "search":
        return found, False
    spoken = spoken_days(text)
    changed = False
    if spoken != (text or ""):
        found, by_range = rule_ranges(found, spoken, today=today)
        found, by_date = rule_dates(found, spoken, today=today)
        changed = by_range or by_date
    found, by_end = rule_end(found, spoken)
    found, by_nights = rule_nights(found, spoken)
    found, by_fix = rule_end_fix(found, spoken)
    return found, changed or by_end or by_nights or by_fix


def rule_end_fix(found: Interpretation, spoken: str) -> tuple[Interpretation, bool]:
    """`[2026-10-18 D23]` 모델이 채운 체크아웃이 문장과 다를 때 고친다 — 「1월 4일 입실해서 이튿날 퇴실」을 2/2 로, 「27일부터 사흘! 1박 방값 …」을 1박으로 읽었다
    (☆6차 N33-21 · N35-20 · N31-20). 문장에 끝을 정하는 말이 **하나**(이튿날 · 다음 날 / N박 · 숫자로 바꾼 날 수)이고 끝 날짜 · 요일을 말하지 않았을 때만. (해석, 고쳤나)"""
    if found.task != "search" or found.check_in is None:
        return found, False
    # `[2026-10-18 D24]` 「11/06~11/08 … 하루 숙박비 팔만 원」 「하룻밤 팔만 원」 — 범위를 말했거나, 박수 말이 가격 말이면 고치지 않는다(☆7차 N37-02 · N39-02 · N41-28 회귀)
    if any(pattern.search(spoken) for pattern in (_RANGE_KO, _RANGE_WORDS, _RANGE_SLASH, _RANGE_FROM_TO, _RANGE_LABELS)):
        return found, False
    others = bool(_END_DAY.search(spoken) or _END_WEEKDAY.search(spoken))
    ends = {int(m.group(1)) if m.group(1) else _NIGHT_WORDS["".join(m.group(2).split())] for m in _NIGHTS.finditer(spoken)
            if not re.match(r"\s*(?:에|당)?\s*(?:숙박비|방값|요금|가격|비용)?\s*(?:은|는|이)?\s*[\d,일이삼사오육칠팔구십]+\s*(?:만|천|원)", spoken[m.end():])}
    if _END_NEXT.search(spoken):
        ends.add(1)
    if others or len(ends) != 1 or not 1 <= min(ends) <= 30:
        return found, False
    end = found.check_in + timedelta(days=ends.pop())
    if found.check_out == end:
        return found, False
    return found.model_copy(update={"check_out": end}), True


#: `[2026-10-21 D25]` 달의 초 · 중순 · 하순 · 말(주말 · 말일은 아님)과 날을 정한 말
_MONTH_PART = re.compile(r"(?:\d{1,2}\s*월|다음\s*달|담달|이번\s*달)\s*(?:의\s*)?(?:초순|중순|하순|초|말)(?!일)(?!\s*(?:쯤\s*)?(?:의\s*|에\s*)?주말)")
_PART_DAY = re.compile(r"(?<!박)(?<!박\s)(?<!\d)\d{1,2}\s*일(?!\s*(?:간|동안|정도|짜리))|\d{1,2}\s*[/.]\s*\d{1,2}|\d{1,2}\s*월\s*\d{1,2}(?!\d|\s*박)|[일이삼]?십[일이삼사오육칠팔구]?\s*일|"
                       r"(?:[첫둘셋넷]째|마지막|첫)\s*(?:주\s*)?(?:[월화수목금토일]요일|주말)")


def rule_checks(found: Interpretation, text: str) -> tuple[Interpretation, list[str]]:
    """모델 값 가운데 문장에 근거가 약한 것을 비운다(되묻게 된다). (해석, 비운 칸)"""
    if found.task != "search":
        return found, []
    cleared, update = [], {}
    quote = found.check_in_text or ""
    if found.check_in is not None and quote and not _DAY_GIVEN.search(quote):
        update.update(check_in=None, check_out=None)
        cleared.append("check_in")
    elif found.check_in is not None and _MONTH_PART.search(text or "") and not _PART_DAY.search(text or ""):
        # `[2026-10-21 D25]` 「다음 달 말에 2박」 — 날을 정하지 않은 말. 모델이 11/01(말 = 끝을 못 읽음)로 정했다(☆7차 N38-16).
        #   「12월 중순쯤」은 근거에 날이 없어 이미 되묻는다 — 「다음 달 · 이번 달」도 같게 되묻는다. 「말 주말」은 `rule_weekdays` 가 정한다
        update.update(check_in=None, check_out=None)
        cleared.append("check_in")
    elif found.check_in is not None and re.search(r"오늘|내일|모레", quote) and not _RELATIVE_STAY.search(text or ""):
        update.update(check_in=None, check_out=None)
        cleared.append("check_in")
    if found.adults is not None and not _PEOPLE.search(text or ""):
        update["adults"] = None
        cleared.append("adults")
    return (found.model_copy(update=update), cleared) if update else (found, [])


__all__ = ["CALENDAR_DAYS", "rule_dates", "rule_ranges", "rule_checks", "rule_nights", "rule_people", "rule_spoken", "rule_start", "rule_weekdays", "spoken_days", "rule_end", "rule_end_fix", "model_context", "settle_years", "GROUNDS", "Interpretation", "InterpretationInvalid", "LABELS", "REQUIRED", "ask", "ground", "needs", "parse"]
