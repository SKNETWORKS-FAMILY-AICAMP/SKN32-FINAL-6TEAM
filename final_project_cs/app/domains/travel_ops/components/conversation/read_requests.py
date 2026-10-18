"""모든 읽기 질문의 대상·범위를 각각 검증하고 실제 자료만 답한다."""
from __future__ import annotations

import re
from copy import copy
from dataclasses import is_dataclass, replace

from . import fact_context, schedule_query, time_anchor, trip_facts

#: ★`[2026-10-15]` 「지금 몇 시야?」 — 일정이 아니라 **지금 시각**을 묻는 말. 전에는 일정을 찾다 「어느 일정을 물으신 건지 찾지 못했어요」로 끝났다
#:  (x600 서버 웹 채팅 재시험 2026-10-14 12:14 · 16:23). 서버 시계로 답한다 — 모델이 시각을 말하게 하지 않는다. 문장 전체가 이 모양일 때만 쓴다.
_CLOCK_QUESTION = re.compile(r"^\s*(?:지금|현재)\s*(?:은\s*)?(?:몇\s*시|시각|시간)\s*(?:이야|야|예요|에요|인가요|입니까|니|죠|지|알려\s*줘|알려\s*줄래|알려\s*주세요)?\s*[?？]?\s*$")
_WEEKDAYS = "월화수목금토일"


def _clock_text(now) -> str:
    local = now.astimezone(trip_facts.KST)
    return f"지금은 {local.month}월 {local.day}일({_WEEKDAYS[local.weekday()]}) {local:%H:%M}이에요(한국 시각). 일정은 바꾸지 않았어요."


def _origin_matches(items, phrase):
    fragment = fact_context._compact(phrase)
    if len(fragment) < 2:
        return []
    return [i for i in items if i.kind != "mobility" and any(fragment in fact_context._compact(name)
            for name in (i.title, (i.place or {}).get("name") or ""))]


def _names_differ(title, place_name):
    """제목과 장소 이름이 서로 다른 곳을 가리키나 — 한쪽이 다른 쪽을 품으면(「경복궁 관람」 · 「경복궁」) 같은 곳으로 본다."""
    a, b = fact_context._compact(title), fact_context._compact(place_name)
    return bool(a and b) and a not in b and b not in a


def _renamed(item, title):
    """답에 쓸 이름만 바꾼 사본 — 원래 일정 항목은 건드리지 않는다."""
    if is_dataclass(item):
        return replace(item, title=title)
    clone = copy(item)
    clone.title = title
    return clone


def _route(origin, destination, mode):
    if mode == "any":
        return None, None
    from .trip_here import _dest_place
    from ..team_hooks import legs
    modes = ["subway", "bus"] if mode == "transit" else [mode]
    planner = legs.leg_planner(None, {}, modes=modes)
    if planner is None:
        return None, "이동 계산기를 사용할 수 없어요."
    got, why = planner(_dest_place(origin), _dest_place(destination), destination.starts_at,
                       origin.ends_at or origin.starts_at)
    if got is None:
        return None, "지정한 수단의 이동 경로를 계산하지 못했어요."
    route = got.get("route") or {}
    option = next((o for o in route.get("options") or [] if o.get("id") == route.get("planned")), {})
    return (f"{origin.title} → {destination.title}: {option.get('label') or '요청한 수단'} 약 {got['eta_min']}분 "
            f"(시간표 기준, {trip_facts._hm(got['starts_at'])} 출발). 일정은 바꾸지 않았어요."), None


def reply(decision, *, items, message, selected, turns, version, now, context_now, ttl_seconds, place_source):
    by_alias = {f"i{n}": item for n, item in enumerate(trip_facts._stops(items), 1)}
    answers, details, evidence = [], [], []
    focus = None
    for request in decision.reads:
        fact = request["fact"]
        item = by_alias.get(request["target_item"])
        if (fact == "time" and item is None and request.get("anchor_kind", "none") in ("none", "now")
                and _CLOCK_QUESTION.match(request.get("text") or message or "")):
            core = _clock_text(now)
            if core not in answers:
                answers.append(core)
            evidence.append({"kind": "clock", "item_id": None, "version": version, "now": now.isoformat()})
            continue
        # ★`[2026-10-14]` 앞뒤 · 시각 질문은 모델이 적은 **기준**(일정 · 끼니 · 시각 · 지금 · 앞 답)으로 서버가 답할 일정을 계산한다
        #   (`time_anchor.py`, Codex 와 합의한 D안) — 모델이 고른 일정보다 앞선다. 「다음」 사실은 그 자체로 「기준 바로 뒤」다.
        clause = request.get("text") or ""
        clause = clause if clause and clause in message else message
        anchor_read = request
        if (fact == "next" and request.get("relation", "at") == "at"
                and (request.get("anchor_kind", "none") != "none" or request.get("target_item", "none") == "none")):
            anchor_read = {**request, "relation": "after"}
        anchored, anchor_basis = time_anchor.resolve(
            anchor_read, items=items, anchor=by_alias.get(request.get("anchor_item") or "none"),
            previous=time_anchor.previous_item(turns, items, version=version, now=context_now, ttl_seconds=ttl_seconds),
            named=fact_context.named_items(items, clause), now=now, target=item)
        anchor_conflict = bool(anchor_basis and anchor_basis.get("time_anchor") == "anchor_conflict")
        if anchored is not None:
            item, fact = anchored, ("time" if fact == "next" else fact)
            request = {**request, "fact": fact, "reference": "explicit",
                       "target_item": next((a for a, i in by_alias.items() if i.item_id == anchored.item_id), "none")}
        sub = replace(decision, item=item, fact=fact, query=request.get("query"), reads=[request])
        fragment = request.get("text") or ""
        scoped_message = fragment if fragment and fragment in message else message
        sub, resolved, stale = fact_context.resolve(
            sub, items=items, message=scoped_message, selected=selected, turns=turns, version=version,
            now=context_now, ttl_seconds=ttl_seconds)
        item = sub.item
        basis = {"kind": fact, "item_id": str(item.item_id) if item else None, "version": version}
        if anchor_basis:
            basis["time_anchor"] = anchor_basis
        place = (item.place or {}) if item else {}
        provenance = (item.detail.get("provenance") or {}).get("place") or {} if item else {}
        note = ""
        if (item is not None and provenance.get("method") == "customer" and place.get("name")
                and fact not in ("time", "duration", "next") and _names_differ(item.title, place["name"])):
            # ★`[2026-10-14]` 고객이 등록 때 **직접 고른** 장소다 — 되묻기만 하지 않고 그 장소로 답하되, 제목과 다른 곳이라는 것을 먼저 밝힌다.
            #   전에는 「어느 장소인지 확인해 주세요」로만 끝나 고른 장소의 정보도 받지 못했다(「서울역 도착」에 고른 「광화문」,
            #   x600 서버 웹 채팅 재시험 2026-10-14). 답의 이름도 고른 장소로 바꿔 제목 장소의 정보처럼 읽히지 않게 한다.
            note = (f"「{item.title}」 일정에 연결된 장소는 등록 때 고르신 「{place['name']}」이라 「{place['name']}」 기준으로 답할게요. "
                    f"제목의 「{item.title}」 자체 정보는 아니에요.")
            basis["place_identity"] = {"title": item.title, "place": place["name"], "method": "customer"}
            item = _renamed(item, place["name"])
        if anchor_conflict:
            # 문장 속 일정 이름과 모델이 적은 기준 일정이 다르다 — 어느 쪽인지 추측하지 않고 되묻는다
            text = "어느 일정을 기준으로 물으셨는지 하나로 확인하지 못했어요. 기준이 되는 일정 이름을 알려 주세요."
            basis["unresolved"] = "anchor"
        elif stale:
            text = "가리키는 일정을 현재 여행에서 하나로 확인하지 못했어요. 일정 이름이나 날짜를 알려 주세요."
            basis["unresolved"] = "target"
        elif fact in (*schedule_query.QUERY_FACTS, "day", "outdoor"):
            text, query_basis = schedule_query.reply("schedule" if fact in ("day", "outdoor") else fact,
                                                      request["query"], items=items, now=now)
            basis.update(query_basis)
            if request["query"].get("position") in ("first", "last") and len(query_basis["item_ids"]) == 1:
                resolved = {"item_id": query_basis["item_ids"][0], "version": version,
                            "at": context_now.isoformat(), "source": "query_scope"}
            if fact == "outdoor":
                ids = set(query_basis["item_ids"])
                lines = []
                for stop in items:
                    if str(stop.item_id) not in ids:
                        continue
                    attrs = (stop.place or {}).get("attributes") or {}
                    indoor = attrs.get("indoor")
                    if not isinstance(indoor, bool):
                        label = "실내·야외 분류가 확인되지 않음"
                    else:
                        label = "실내" if indoor else "야외"
                    lines.append(f"· {stop.title}: {label}")
                text += "\n실내·야외 확인:\n" + "\n".join(lines)
                text += "\n비가 온다면 야외 이동 때 우산과 미끄럽지 않은 신발을 준비하세요. 실제 강수 예보를 조회한 답은 아니며, 일정을 바꾸지는 않았어요."
        elif fact == "move" and request.get("origin_item") != "none":
            origin = by_alias.get(request.get("origin_item"))
            origins = _origin_matches(items, request.get("origin_text") or "")
            if len(origins) > 1:
                text = "출발지가 여러 일정으로 읽혀요: " + " · ".join(i.title for i in origins) + ". 어느 일정에서 출발하시나요?"
                basis["unresolved"] = "ambiguous_origin"
            elif origin is None or item is None or origin.item_id == item.item_id:
                text = "이동할 출발지와 도착지를 서로 다른 일정으로 알려 주세요."
                basis["unresolved"] = "endpoints"
            else:
                if (((origin.detail.get("provenance") or {}).get("place") or {}).get("method") == "customer" and origin.place
                        and _names_differ(origin.title, origin.place.get("name") or "")):
                    # ★`[2026-10-14]` 위 도착지와 같다 — 고객이 고른 출발 장소로 계산하고 그 사실을 먼저 밝힌다
                    note = (f"출발 일정 「{origin.title}」에 연결된 장소는 등록 때 고르신 「{origin.place['name']}」이라 "
                            f"그곳에서 출발하는 것으로 계산했어요.") + (f"\n{note}" if note else "")
                    basis["origin_identity"] = {"title": origin.title, "place": origin.place["name"], "method": "customer"}
                    origin = _renamed(origin, origin.place["name"])
                mode = request.get("transport_mode", "any")
                text, problem = _route(origin, item, mode)
                if problem:
                    text = problem + " 도보 추정값으로 요청한 수단의 소요 시간을 대신하지 않았어요."
                    basis["unresolved"] = "requested_route"
                elif text is None:
                    text = trip_facts._pair_move_answer(items, origin, item)
                basis["origin_item_id"] = str(origin.item_id)
                basis["transport_mode"] = mode
        elif fact == "move" and request.get("reference") == "explicit":
            text = "출발지를 하나로 확인하지 못했어요. 어느 일정에서 출발하는지 이름이나 시각을 알려 주세요. 도착지의 다음 구간으로 대신 답하지 않았어요."
            basis["unresolved"] = "origin"
        elif fact in ("description", "duration", "price", "entry_booking", "food"):
            if item is None:
                text = "어느 장소인지 확인할 수 있도록 일정 이름을 알려 주세요."
                basis["unresolved"] = "target"
            elif fact == "duration":
                if item.ends_at is None:
                    text = f"{item.title}의 종료 시각이 일정에 등록되지 않아 머무는 시간을 계산할 수 없어요."
                    basis["unresolved"] = "ends_at"
                else:
                    minutes = int((item.ends_at - item.starts_at).total_seconds() / 60)
                    text = f"{item.title}: {trip_facts._hm(item.starts_at)}~{trip_facts._hm(item.ends_at)}, {minutes}분 머무는 일정이에요."
            else:
                lookup = trip_facts.look_up_place(item.place, place_source) if item.place else {}
                basis["lookups"] = lookup
                attrs = (item.place or {}).get("attributes") or {}
                if fact == "description":
                    category = lookup.get("category") or attrs.get("category") or trip_facts.KIND_LABEL.get(item.kind, item.kind)
                    text = f"{item.title}: 등록 자료의 분류는 {category}입니다."
                    detail, _ = trip_facts.fact_reply("detail", message=message, items=items, now=now, item=item, place_source=place_source)
                    text += "\n" + detail
                elif fact in ("price", "entry_booking"):
                    field = "price_text" if fact == "price" else "reservation_text"
                    value = lookup.get(field)
                    label = "이용 요금" if fact == "price" else "방문 예약 안내"
                    if value:
                        text = f"{item.title} {label} — {trip_facts._clean(value)} (출처: {lookup.get('source')}, 조회: {context_now.isoformat()})."
                    elif fact == "price" and attrs.get("price_krw") is not None:
                        text = f"{item.title}의 저장된 요금은 {int(attrs['price_krw']):,}원이에요. 성인·전망대 등 세부 조건과 최신 판매가는 확인되지 않았어요."
                        basis["unresolved"] = "price_conditions"
                    else:
                        text = f"{item.title} {label}: 연결된 자료에서 확인되지 않았어요. 예약 기록이 없다는 사실을 예약이 필요 없다는 뜻으로 해석하지 않았어요."
                        basis["unresolved"] = field
                    if lookup.get("homepage"):
                        text += f"\n공식 안내: {lookup['homepage']}"
                else:
                    text = f"{item.title}의 개별 점포 메뉴·재료는 확인한 자료가 없어 요청하신 식단 조건 충족 여부를 확정할 수 없어요."
                    if request.get("advice"):
                        text += "\n일반 식단 조언: " + str(request["advice"])[:500]
                    text += "\n일정은 바꾸지 않았어요."
                    basis["unresolved"] = "verified_menu"
        else:
            # ★`[2026-10-13]` 대상은 결정 단위 · 위의 확인(`fact_context.resolve`)이 정했다 — 문장을 다시 읽어 덮지 않는다
            text, fact_basis = trip_facts.fact_reply(fact, message=message, items=items, now=now,
                                                    item=item, place_source=place_source, retarget=False)
            basis.update(fact_basis)
        if note and not basis.get("unresolved"):
            text = f"{note}\n{text}"
        core, _, more = text.partition(trip_facts.MORE_MARK)
        if core not in answers:
            answers.append(core)
        if more:
            details.append(more)
        evidence.append(basis)
        if resolved and not basis.get("unresolved"):
            focus = resolved
    if decision.social:
        answers.insert(0, decision.social)
    return {"status": "answered", "text": "\n\n".join(answers),
            **({"more": "\n\n".join(details)} if details else {})}, {"kind": "multi_read", "questions": evidence}, focus
