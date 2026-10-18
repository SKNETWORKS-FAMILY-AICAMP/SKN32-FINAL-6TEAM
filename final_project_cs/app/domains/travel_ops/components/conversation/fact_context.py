"""읽기 전용 질문의 대상 연결. 일정 ID는 현재 여행에서만 확인한다."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import re
import unicodedata
from typing import Any

ITEM_FACTS = frozenset({"detail", "address", "hours", "phone", "time", "move", "next", "booking", "route_here",
                        "description", "duration", "price", "entry_booking", "food"})


def _compact(text: str) -> str:
    return re.sub(r"[^\w가-힣]", "", unicodedata.normalize("NFKC", text).casefold())


def named_items(items: list[Any], message: str) -> list[Any]:
    text = _compact(message)
    found = []
    for item in items:
        if item.kind == "mobility":
            continue
        names = (item.title, (item.place or {}).get("name") or "")
        variants = {_compact(n) for n in names if n}
        # 혼합 문자 이름의 한국어 부분도 비교한다. 특정 장소 이름을 예외로 두지 않는다.
        variants |= {re.sub(r"[^가-힣]", "", n) for n in names if len(re.sub(r"[^가-힣]", "", n)) >= 3}
        if any(len(n) >= 2 and n in text for n in variants):
            found.append(item)
    return found


def resolve(decision, *, items, message, selected, turns, version, now, ttl_seconds):
    """(확인된 결정, 근거, 만료된 명시 선택). 쓰기 행동과 해석 실패에는 적용하지 않는다."""
    item_fact = decision.fact in ITEM_FACTS or (decision.fact == "outdoor" and decision.query is None)
    if decision.action != "answer_fact" or not item_fact:
        return decision, None, False
    by_id = {str(i.item_id): i for i in items if i.kind != "mobility"}
    if selected is not None and str(selected) not in by_id:
        return replace(decision, item=None), None, True
    named = named_items(items, message)
    reference = decision.reads[0].get("reference") if decision.reads else None
    source, item = None, None
    if reference == "explicit" and decision.item is not None and str(decision.item.item_id) in by_id:
        # 각 질문에서 해석한 명시 대상(별칭 포함)을 다른 질문의 이름으로 덮어쓰지 않는다.
        source, item = "message", by_id[str(decision.item.item_id)]
    elif len(named) == 1:
        source, item = "message", named[0]
    elif len(named) > 1:
        # 배제·출발·도착 등을 해석한 대상이 현재 여행의 항목인지 확인한다.
        if reference == "explicit" and decision.item is not None and str(decision.item.item_id) in by_id:
            source, item = "message", by_id[str(decision.item.item_id)]
        else:
            return replace(decision, item=None), None, True
    else:
        # 다른 날·시각·끼니를 명시한 문장에 옛 일정을 덮어씌우지 않는다.
        scoped = bool(re.search(r"\d\s*(?:일차|월|일|시|:)|오늘|내일|아침|점심|저녁|첫|마지막", message))
        bare = not scoped and bool(re.fullmatch(
            r"\s*(?:(?:거기|그거|그곳|저거|그건|거긴|그것)(?:에|은|는|의|을|를)?\s*)?"
            r"(?:(?:좀|더)\s*)?(?:자세히|상세|주소|위치|영업시간|운영시간|전화번호)?\s*"
            r"(?:알려\s*줘|알려\s*주세요|어디야|어딨어|뭐야)[.!?？]*\s*", message))
        # ★`[2026-10-14]` 모델이 고른 대상으로 대신할 수 있나 — 대상 없이 이어 묻는 짧은 문장(`bare`)은 대신하지 않는다(아래 그대로).
        #   학습 E4B 는 「정오에 뭐 해?」 「내일 첫 일정 몇 시야?」 같은 **스스로 대상을 말한 문장**도 「앞에서 말한 것」으로 적는다
        #   (시간 어휘 질문 103개 중 57개 — 유료 대체는 11개). 그때 앞 대상이 없으면 모델이 맞게 고른 일정까지 버리고
        #   「일정을 확인하지 못했어요」로 끝났다(x600 서버 웹 채팅 재시험 2026-10-14). 답에는 고른 일정 이름이 나온다.
        #   「거기 · 그쪽 · 그거」처럼 앞을 가리키는 말이 있으면 진짜 이어 묻기다 — 앞 대상이 없으면 모델 추측으로 답하지 않고 되묻는다.
        pointing = bool(re.search(r"거기|거긴|그거|그건|그것|그곳|그쪽|저거|저기|저곳|(?:^|\s)그\s", message))
        fallback = (by_id.get(str(decision.item.item_id))
                    if decision.item is not None and not bare and not pointing else None)
        if selected is not None and not scoped and reference not in ("explicit", "previous"):
            source, item = "selection", by_id[str(selected)]
        elif bare or (reference == "previous" and not scoped):
            # 날짜·시각·끼니를 말한 문장(`scoped`)은 「앞에서 말한 것」 표시가 있어도 옛 일정을 덮어씌우지 않는다 — 아래 `decision` 으로 간다
            previous = next((t for t in reversed(turns) if t.get("role") == "assistant"), {})
            focus = (previous.get("reply") or {}).get("focus") or {}
            try:
                age = (now - datetime.fromisoformat(focus["at"])).total_seconds()
                if focus.get("version") == version and 0 <= age <= ttl_seconds:
                    item = by_id.get(str(focus.get("item_id")))
                    source = "previous_fact"
                if item is None and fallback is None:
                    return replace(decision, item=None), None, True
            except (KeyError, TypeError, ValueError):
                # 문맥이 없거나 읽을 수 없으면 짧은 이어 묻기에 모델이 고른 다른 일정을 자동 승계하지 않는다.
                if fallback is None:
                    return replace(decision, item=None), None, reference == "previous"
            if item is None:
                source, item = "decision_without_previous", fallback
        elif decision.item is not None:
            item = by_id.get(str(decision.item.item_id))
            source = "decision"
    if item is None:
        return decision, None, False
    return replace(decision, item=item), {"item_id": str(item.item_id), "version": version,
                                          "at": now.isoformat(), "source": source}, False
