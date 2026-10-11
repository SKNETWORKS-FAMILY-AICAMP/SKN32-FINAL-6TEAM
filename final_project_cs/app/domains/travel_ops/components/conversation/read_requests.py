"""모든 읽기 질문의 대상·범위를 각각 검증하고 실제 자료만 답한다."""
from __future__ import annotations

from dataclasses import replace

from . import fact_context, schedule_query, trip_facts


def _origin_matches(items, phrase):
    fragment = fact_context._compact(phrase)
    if len(fragment) < 2:
        return []
    return [i for i in items if i.kind != "mobility" and any(fragment in fact_context._compact(name)
            for name in (i.title, (i.place or {}).get("name") or ""))]


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
        sub = replace(decision, item=item, fact=fact, query=request.get("query"), reads=[request])
        fragment = request.get("text") or ""
        scoped_message = fragment if fragment and fragment in message else message
        sub, resolved, stale = fact_context.resolve(
            sub, items=items, message=scoped_message, selected=selected, turns=turns, version=version,
            now=context_now, ttl_seconds=ttl_seconds)
        item = sub.item
        basis = {"kind": fact, "item_id": str(item.item_id) if item else None, "version": version}
        place = (item.place or {}) if item else {}
        provenance = (item.detail.get("provenance") or {}).get("place") or {} if item else {}
        conflict = (item is not None and provenance.get("method") == "customer" and place.get("name")
                    and fact not in ("time", "duration", "next")
                    and fact_context._compact(item.title) != fact_context._compact(place["name"]))
        if conflict:
            text = (f"일정 제목은 「{item.title}」이지만 등록할 때 선택된 실제 장소는 「{place['name']}」이에요. "
                    "서로 다른 장소일 수 있어 선택된 장소의 정보를 일정 제목의 장소 정보로 답할 수 없어요. 어느 장소를 물으시는지 확인해 주세요.")
            basis["unresolved"] = "place_identity"
            focus = resolved
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
            elif ((origin.detail.get("provenance") or {}).get("place") or {}).get("method") == "customer" and origin.place and fact_context._compact(origin.title) != fact_context._compact(origin.place.get("name") or ""):
                text = f"출발지의 일정 제목 「{origin.title}」과 선택된 장소 「{origin.place['name']}」가 달라요. 어느 장소에서 출발하는지 확인해 주세요."
                basis["unresolved"] = "origin_identity"
            else:
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
            text, fact_basis = trip_facts.fact_reply(fact, message=message, items=items, now=now,
                                                    item=item, place_source=place_source)
            basis.update(fact_basis)
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
