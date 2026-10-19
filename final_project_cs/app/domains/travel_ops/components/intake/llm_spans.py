# -*- coding: utf-8 -*-
"""남은 줄 — 모델이 **어디가 무엇인지만** 가리키고, 값은 서버가 원문에서 잘라 낸다. `[2026-09-27]` 설계서 §3-4

★규칙이 못 읽은 줄(「점심은 토속촌에서 먹을래」 「저녁엔 광장시장 가 보고 싶어」)만 모델에 보낸다.
★모델이 내는 것: `{"spans": [{"line": 줄 번호, "quote": 원문 조각, "role": 역할}]}`.
  ☆설계서 §3-4 는 (시작, 끝) **글자 위치**를 받으라 했다. 언어 모델은 글자 수 세기가 약해서, 여기서는 **원문 조각을
    그대로 인용**하게 하고 서버가 그 조각을 원문에서 찾는다. ★원문에 **글자 그대로 없는** 인용은 버린다 — 실측
    (guguroute : RAG, 2026-09-26)에서 모델이 「토속촌」을 「토속툰」으로 바꿔 적었다. 그런 값은 원문에 없으니 들어오지 못한다.
★시각·날짜는 인용 조각을 **규칙으로 다시 읽어** 값을 만든다 — 모델이 정규화한 값을 쓰지 않는다.
★`[2026-10-16 2회차 합의 · 사용자 승인]` 남은 줄을 **한 번에** 보내고 답을 **조금씩 받는다**(모델이 있으면 `json_stream`) — 첫 조각 · 조각 사이 멈춤 감시,
  로컬이 멈추면 유료가 처음부터 다시 읽는다(한 계획은 한 모델이 읽는다). 유료까지 실패하면 `ReadingFailed` 를 올린다 — 조용히 남은 줄로 두지 않는다.
★모델 호출: 설정의 기본 모델(`ollama_model` — 2026-10-14 부터 가르친 E4B `tripilot-pointer:e4b-ft`, 설계 당시에는 `gemma4:12b`) · think=false · 온도 0 · JSON(설계서 §3-4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
import time
from typing import Any, Callable

from .rules import _EAT, _EAT_BEFORE, TIME, Claim, Span, _date_in, _hhmm, _narrow, eat_mention, meal_mention
from .span_segments import split_segments

ROLES = ("place", "time", "date", "meal", "eat", "booking_no", "party", "plan_request", "ignore")

SYSTEM = (
    "You label parts of a traveller's itinerary lines (usually Korean). You get numbered lines. "
    "For each useful part, return the line number, the EXACT substring copied character-for-character from that line "
    "(never fix typos, never translate, never add words), and its role.\n"
    "Roles: place (a place/shop/sight the traveller will visit), time (a clock time or time of day), "
    "date (a date or relative day such as 내일), time also includes relative-now expressions such as 지금/당장/현재, "
    "meal (breakfast/lunch/dinner word), "
    "eat (words saying the traveller will eat or drink AT that place, e.g. 먹고, 맛집, 한잔, 브런치, 카페, 커피 — not a meal word "
    "that only tells the time such as 저녁 무렵 or 점심쯤, and not eating before leaving for the place such as 아침 먹고 나와서), "
    "booking_no (reservation number), "
    "party (number of people), plan_request (they ask us to make a plan, e.g. '일정 짜 줘'), ignore.\n"
    'Return JSON only: {"spans": [{"line": 1, "quote": "...", "role": "place"}]}. '
    "If nothing is useful, return {\"spans\": []}.")



@dataclass
class SpanItem:
    """남은 줄의 장소 하나에서 모은 항목 — 규칙 항목과 같은 모양으로 합친다. ★한 줄에 장소가 여럿이면 항목도 여럿이다."""

    line: int
    title: Span | None
    start: str | None
    meal: str | None
    date: str | None
    time_claim: Claim | None = None
    segment: Span | None = None


class ReadingFailed(RuntimeError):
    """남은 줄을 읽는 모델이 로컬 · 유료 모두 답하지 못했다 — 부르는 쪽이 접수를 「읽기 실패」로 드러낸다(`pipeline`). `[2026-10-16]`"""


def _call_path() -> dict[str, Any] | None:
    """직전 모델 호출이 어느 경로(로컬 · 유료)로 답했나 — 넘김 장치가 꺼져 있으면 None."""
    try:
        from app.infrastructure import llm_failover

        return llm_failover.current_path()
    except Exception:                                    # noqa: BLE001 — 기록용이다. 못 읽어도 읽기를 막지 않는다
        return None


def _clear_path() -> None:
    try:
        from app.infrastructure import llm_failover

        llm_failover.clear_path()
    except Exception:                                    # noqa: BLE001
        pass


_OBJECT = re.compile(r"\{[^{}]*\}")


class _Progress:
    """받는 중인 답에서 **원문 검사를 통과한 서로 다른 줄 수 / 보낸 줄 수**를 센다 — 지어낸 진행률이 아니다.
    ★줄 수는 멈춤 판정에 쓰지 않는다(느린 한 줄을 쓰는 동안 안 늘 수 있다 — 멈춤은 조각 도착으로 본다).
    ★`every` 초마다 한 번 알린다. 경로가 바뀌면(로컬 → 유료) 곧바로 0 부터 다시 알린다(`phase: reading_api`)."""

    def __init__(self, lines: list[str], unread: list[int], tell: Callable[[dict[str, Any]], None] | None, *,
                 every: float, clock: Callable[[], float]) -> None:
        self.lines, self.unread, self.tell, self.every, self.clock = lines, unread, tell, every, clock
        self.path, self.text, self.last = "local", "", None

    def count(self) -> int:
        seen: set[int] = set()
        for match in _OBJECT.finditer(self.text):
            try:
                entry = json.loads(match.group(0))
                asked, quote = int(entry["line"]), str(entry["quote"])
            except (ValueError, KeyError, TypeError):
                continue
            numbers = ([self.unread[asked - 1]] if 1 <= asked <= len(self.unread) else []) + ([asked] if asked in self.unread else [])
            for number in numbers:
                if quote.strip() and quote in self.lines[number - 1]:
                    seen.add(number)
                    break
        return len(seen)

    def emit(self, *, final: bool = False) -> None:
        if self.tell is None:
            return
        body: dict[str, Any] = {"phase": "reading_api" if self.path == "api" else "reading", "done": self.count(),
                                "total": len(self.unread)}
        if final:
            body["final"] = True
        self.last = self.clock()
        try:
            self.tell(body)
        except Exception:                                # noqa: BLE001 — 진행 알림은 부가 기능이다
            pass

    def piece(self, text: str, path: str = "local") -> None:
        switched = path != self.path
        self.path, self.text = path, text
        if switched or self.last is None or self.clock() - self.last >= self.every:
            self.emit()


def output_budget(lines: int, chars: int, settings: dict[str, Any] | None) -> int:
    """답 토큰 상한 — `max(바닥, 줄당 × 보낸 줄 수 + 글자당 × 보낸 글자 수)`. 0 이면 상한 없음(설정이 없을 때).
    근거: 실측 답 토큰(gpt-6-luna) 666~1,509 — 글자당 1.2~2.8(줄이 짧을수록 · 한 줄에 장소가 많을수록 크다). 줄 수만으로 정했더니(40 × 22줄 = 1,024)
    장소가 빽빽한 계획(답 1,107토큰)이 잘려 읽기 실패가 났다(2026-10-16 확인 실행). 지금 식은 시험지 6건 모두 실제 답의 1.6배 이상이다."""
    if not settings:
        return 0
    return max(int(settings["output_tokens_base"]),
               int(settings["output_tokens_per_line"]) * int(lines) + int(settings["output_tokens_per_char"]) * int(chars))


def label_lines(lines: list[str], unread: list[int], chat: Any, *, now: datetime | None = None,
                stream: dict[str, Any] | None = None, on_progress: Callable[[dict[str, Any]], None] | None = None,
                clock: Callable[[], float] = time.monotonic) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    """(claims, 항목, 보고). ★모델이 가리킨 조각 중 원문에 그대로 있는 것만 받는다.

    ★`[2026-10-14]` 한 줄을 장소마다 나눈다 — 줄마다 항목 하나로 묶었더니 「서촌 … 저녁 무렵 남산타워」에서 남산타워가 빠지고
      「저녁」이 서촌에 붙었다(테스트 서버 접수 87858b77). 시각 · 날짜 · 끼니는 같은 원문 구간의 장소에 붙인다.
    ★끼니는 모델이 가리키지 않아도 **그 장소 몫의 원문**에서 규칙으로 다시 본다(`rules.meal_mention`) — 같은 접수에서 모델이
      「점심은 통인시장 근처에서」의 「점심」을 가리키지 않아 식사가 활동이 됐다.
    ★`[2026-10-16]` 보내는 줄 번호는 **목록 안 순서(1부터)** 이고 답의 번호를 원래 줄로 되돌린다 — 가르친 E4B 는 받은 번호(16 · 17 · 18 · 20)를
      무시하고 순서(1 · 2 · 3 · 4)로 답했다(실측 보고서 「줄 번호」).
    ★`[2026-10-16 2회차 합의 · 사용자 승인]` `stream`(가드레일 `travel.intake_reading` 값)이 있고 모델이 `json_stream` 을 가지면 **한 번에 보내고 조금씩 받는다** —
      첫 조각 `first_token_seconds` · 조각 사이 `stall_seconds` · 맨 위 `max_seconds` · 답 토큰 상한 `output_budget`(줄 수 · 글자 수로). 로컬이 멈추면 넘김 장치가 유료로 처음부터 다시 읽는다.
      `on_progress({phase: reading|reading_api, done, total})` — 시작할 때 한 번 · `progress_seconds` 마다(경로가 바뀌면 곧바로) · 끝에 한 번(`final`).
      `done` = 원문 검사를 통과한 서로 다른 줄 수, `total` = 보낸 줄 수.
    ☆2026-10-16 앞 판(d618279f)은 8줄 묶음 · 실패한 묶음만 유료 · 상한을 넘으면 남은 묶음을 남은 줄로 두었다 — 한 계획을 두 모델이 섞어 읽고 줄을 버린다는
      이유로 사용자가 반대해 바꿨다.
    ★모델이 끝내 답하지 못하면 `ReadingFailed` — 예전처럼 이 단계만 건너뛰어 줄을 조용히 남은 줄로 두지 않는다."""
    report: dict[str, Any] = {"asked_lines": len(unread), "spans": 0, "accepted": 0, "rejected": [], "plan_request": False}
    if not unread or chat is None:
        return [], [], report
    user = "\n".join(f"{at}: {lines[n - 1]}" for at, n in enumerate(unread, start=1))
    streamer = getattr(chat, "json_stream", None) if stream else None
    progress: _Progress | None = None
    _clear_path()
    started = clock()
    try:
        if callable(streamer):
            progress = _Progress(lines, unread, on_progress, every=float(stream["progress_seconds"]), clock=clock)
            progress.emit()
            budget = output_budget(len(unread), sum(len(lines[n - 1]) for n in unread), stream)
            raw = streamer(SYSTEM, user, on_piece=progress.piece, first_wait=float(stream["first_token_seconds"]),
                           stall=float(stream["stall_seconds"]), max_seconds=float(stream["max_seconds"]), max_tokens=budget)
            report["output_tokens"] = budget
        else:
            raw = chat.json(SYSTEM, user)
    except Exception as exc:                             # noqa: BLE001 — 숨기지 않고 부르는 쪽에 올린다(접수 「읽기 실패」)
        reasons = (_call_path() or {}).get("reasons")
        raise ReadingFailed(f"{type(exc).__name__}: {exc}"[:200] + (f" · 경로 {reasons}" if reasons else "")) from exc
    report["seconds"] = round(clock() - started, 2)
    path = _call_path()
    if path:
        report["path"] = path.get("path")
        if path.get("reasons"):
            report["reasons"] = [list(r) for r in path["reasons"]]
    accepted: dict[int, list[tuple[int, int, str, str]]] = {}
    cursors: dict[tuple[int, str, str], int] = {}
    _accept(lines, list(unread), raw.get("spans") if isinstance(raw, dict) else None, report, accepted, cursors)
    if progress is not None:
        progress.emit(final=True)
    return _collect(lines, accepted, now, report)


def _accept(lines: list[str], batch: list[int], spans: Any, report: dict[str, Any],
            accepted: dict[int, list[tuple[int, int, str, str]]], cursors: dict[tuple[int, str, str], int]) -> None:
    """모델 답 → 받은 조각. 답의 줄 번호(보낸 목록 안 순서, 1부터)를 원래 줄 번호로 되돌린다.
    ★그 순서의 줄에 인용이 글자 그대로 없고, 답의 번호가 **보낸 줄의 원래 번호**이며 그 줄에 인용이 있으면 원래 번호로 본다 —
      원래 번호로 답하는 모델(2026-10-16 전 계약 · 그 계약으로 쓴 시험)도 같은 결과가 나오게. 어느 쪽이든 인용이 그 줄에 있어야 받는다.
    ★원문에 글자 그대로 없는 인용 · 보낸 목록 밖 번호 · 모르는 역할은 버린다."""
    for entry in spans or []:
        report["spans"] += 1
        try:
            asked, quote, role = int(entry["line"]), str(entry["quote"]), str(entry["role"])
        except (KeyError, TypeError, ValueError):
            report["rejected"].append({"why": "모양이 다르다", "entry": str(entry)[:80]})
            continue
        candidates = [batch[asked - 1]] if 1 <= asked <= len(batch) else []
        if asked in batch and asked not in candidates:
            candidates.append(asked)
        if not candidates or role not in ROLES or not quote.strip():
            report["rejected"].append({"why": "남은 줄이 아니거나 모르는 역할", "line": asked, "role": role})
            continue
        number, at = candidates[0], -1
        for number in candidates:
            at = lines[number - 1].find(quote, cursors.get((number, role, quote), 0))
            if at >= 0:
                break
        number = number if at >= 0 else candidates[0]
        key = number, role, quote
        if at < 0:
            # ★원문에 글자 그대로 없다 — 모델이 바꿔 적었다. 받지 않는다
            report["rejected"].append({"why": "원문에 없는 인용", "line": number, "quote": quote})
            continue
        cursors[key] = at + len(quote)
        if role == "plan_request":
            report["plan_request"] = True
        accepted.setdefault(number, []).append((at, at + len(quote), quote, role))
        report["accepted"] += 1


def _collect(lines: list[str], accepted: dict[int, list[tuple[int, int, str, str]]], now: datetime | None,
             report: dict[str, Any]) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    claims: list[Claim] = []
    items: list[SpanItem] = []
    for number in sorted(accepted):
        text = lines[number - 1]
        mine = _line_items(number, text, accepted[number])
        for start, end, quote, role in sorted(accepted[number]):
            if role in ("place", "plan_request", "ignore", "booking_no", "party") or not mine:
                continue
            item = _owner(mine, start)
            if role == "time" and item.time_claim is None:
                claim = _time_claim(number, start, quote, now, item)
                if claim is not None:
                    item.time_claim = claim
                    claims.append(claim)
            elif role == "date":
                value, match = _date_in(quote)
                if match:
                    item.date = value
            # 끼니는 _line_items가 항목의 전체 구간과 장소 위치로 판정한다.
            # 모델이 따로 낸 meal 조각으로 다른 항목의 판정을 덮지 않는다.
        items += mine
    return claims, items, report


def _line_items(number: int, text: str, spans: list[tuple[int, int, str, str]]) -> list[SpanItem]:
    """줄의 장소 조각마다 항목 하나 — 겹치지 않는 원문 구간을 보존한다."""
    places: list[tuple[int, int]] = []
    eaten: set[tuple[int, int]] = set()
    for start, end, _, role in sorted(spans):
        if role != "place":
            continue
        s, e = _narrow(text, start, end)
        # ★`[2026-10-15]` 모델이 「성수동 맛집」 · 「연남동 카페」처럼 「먹는다」 말까지 장소로 가리키면 그 앞까지가 이름이고 식사다(규칙 읽기와 같다)
        inner = _EAT.search(text, s + 1, e) if e > s else None
        if inner is not None and not _EAT_BEFORE.match(text, inner.end()):
            s, e = _narrow(text, s, inner.start())
            eaten.add((s, e))
        if e > s and not any(s < pe and ps < e for ps, pe in places):    # 겹치는 조각은 앞 것만
            places.append((s, e))
    # 모델이 끼니 말을 **시각**(숫자 없는 때)으로 짚었으면 그 판단을 따른다 — 「저녁엔 광장시장 가 보고 싶어」는 저녁에 가는 것이다.
    # 짚지 않았거나 끼니로 짚었으면 규칙이 정한다(「점심은 통인시장 근처에서」 — 모델이 아무것도 안 짚었다).
    as_time = [(start, end) for start, end, quote, role in spans if role == "time" and not TIME.search(quote)]
    eats = [(start, end) for start, end, _, role in spans if role == "eat"]
    items: list[SpanItem] = []
    for (s, e), (left, right) in zip(places, split_segments(text, places)):
        mention = meal_mention(text[left:right], place_start=s - left)
        meal = mention[1] if mention and mention[2] else None
        if meal and any(left <= start < right and mention[0] in text[start:end] for start, end in as_time):
            meal = None
        if meal is None and ((s, e) in eaten or eat_mention(text[left:right], place_end=e - left)):
            meal = "meal"                 # ★`[2026-10-15]` 끼니 말 없이 「먹고」 · 「맛집」 · 「한잔」 — 끼니는 모르고 식사인 것만 안다
        if meal is None and any(s <= start < right and not _EAT_BEFORE.match(text, end) for start, end in eats):
            # ★`[2026-10-15]` 모델이 그 장소 **이름 뒤** 구간의 「먹는다」 조각을 원문 그대로 가리켰다 — 규칙 낱말 목록 밖의 말(「요기」 · 「칼국수」 …).
            #   ☆이름 앞 조각은 받지 않는다 — 「밥 먹고 나서 창덕궁」의 「밥 먹고」를 모델이 eat 로 짚었다(실제 접수 모양 측정)
            meal = "meal"
        items.append(SpanItem(number, Span(number, s, e, text[s:e]), None, meal, None,
                              segment=Span(number, left, right, text[left:right])))
    return items


def _owner(items: list[SpanItem], at: int) -> SpanItem:
    """조각이 포함된 원문 구간의 장소. 장소 뒤의 「지금」도 그 장소에 붙는다."""
    return next((item for item in items if item.segment.start <= at < item.segment.end), items[-1])


def _time_claim(number: int, at: int, quote: str, now: datetime | None, item: SpanItem) -> Claim | None:
    match = TIME.search(quote)
    if match:
        value, review, note = _hhmm(match)
        if value:
            item.start = value
            return Claim("", value, Span(number, at + match.start(), at + match.end(), match.group(0)),
                         needs_review=review, note=note, method="llm_span")
    elif now is not None and any(word in quote for word in ("지금", "현재", "당장")):
        from zoneinfo import ZoneInfo
        instant = now.astimezone(ZoneInfo("Asia/Seoul"))
        value = instant.strftime("%H:%M")
        item.start = value
        item.date = instant.date().isoformat()
        return Claim("", value, Span(number, at, at + len(quote), quote), note="접수 시각 기준 현재 시각",
                     method="llm_span")
    return None


def make_labeler(chat: Any) -> Callable[[list[str], list[int]], tuple[list[Claim], list[SpanItem], dict[str, Any]]]:
    return lambda lines, unread: label_lines(lines, unread, chat)


__all__ = ["ROLES", "SYSTEM", "ReadingFailed", "SpanItem", "label_lines", "make_labeler", "output_budget"]
