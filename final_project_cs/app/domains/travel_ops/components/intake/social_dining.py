"""고객이 보관한 SNS 식당 후보 → 검증된 식사 변경안 → 명시적 적용.

미리보기는 실제 edit/view 경로를 저장점에서 실행하고 반드시 되돌린다.
선택은 서버가 보관한 장소만 허용하며, 외부 URL은 social_links만 읽는다.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import re
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from app.core.settings import get_guardrails
from app.core.team_availability import TeamUnavailable
from ..team_hooks import dining_ledger
from . import candidates, pipeline, social_dining_rank, social_links, survey_answers
from .assemble import effective

KST = ZoneInfo("Asia/Seoul")
_MESSAGES = {
    "no_meal_slots": "아직 식사 일정이 없어요. 먼저 일정을 만들거나 등록한 뒤 반영해 주세요.",
    "no_future_meal_slots": "바꿀 수 있는 남은 식사 일정이 없어요. 지난 일정·고정 일정·기존 예약은 유지해요.",
    "restaurant_choice_required": "게시물에 여러 식당이 있어요. 원하는 식당을 골라 주세요.",
    "place_choice_required": "같은 이름의 식당이나 지점이 여러 곳이에요. 가게와 주소를 골라 주세요.",
    "place_not_found": "실제 식당을 확인하지 못했어요. 식당명과 지역·지점을 보완해 주세요.",
    "unknown_facts": "영업·휴무 등 방문에 필요한 정보를 확인하지 못해 배치를 보류했어요.",
    "does_not_fit": "영업시간·식이 조건·이동시간 검사에 맞지 않아 배치하지 않았어요.",
    "already_scheduled": "같은 식당이 이미 일정에 들어 있어 중복으로 넣지 않았어요.",
    "selected_place_unavailable": "고르신 지점을 이번 확인에서 다시 찾지 못해 보류했어요. 선택은 그대로 두었어요.",
    "duplicate_restaurant": "같은 지점의 다른 링크와 연결했어요.",
    "no_available_slot": "다른 희망 식당을 포함하면 배치할 수 있는 식사 시간이 남지 않아요.",
    "activity_change_required": "다른 활동의 시각이나 장소 변경이 필요해요. 일반 일정 수정에서 확인해 주세요.",
    "full_validation_failed": "전체 일정 검증을 통과하지 못해 반영하지 않았어요.",
    "preview_budget_exhausted": "이번 확인 한도에 도달했어요. 식사 하나를 골라 다시 확인해 주세요.",
    "unknown_dietary": "요청하신 식이 조건에 맞는다는 근거를 확인하지 못해 배치를 보류했어요.",
    "dietary_conflict": "요청하신 식이 조건과 맞지 않는 것으로 확인되어 배치하지 않았어요.",
    "area_unverified": "요청하신 지역에 있는 식당인지 확인할 근거가 없어 배치를 보류했어요.",
    "area_mismatch": "확인한 식당의 위치가 요청하신 지역과 달라 배치하지 않았어요.",
    "branch_unverified": "요청하신 지점인지 확인하지 못해 배치를 보류했어요. 지점과 주소를 확인해 주세요.",
}


def _now() -> datetime:
    return datetime.now(KST)


def _limits() -> dict[str, Any]:
    return get_guardrails().get("travel.social_dining")


def _owner(conn, *, tenant_id, customer_id, intake_id, lock=False, editable=False) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s"
                    + (" FOR UPDATE" if lock else ""), (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
    if row is None:
        raise LookupError("intake")
    status, revision = row
    if editable and status != "review":
        raise pipeline.IntakeConflict("intake_not_editable", "지금은 고칠 수 없는 접수입니다", status=status)
    return {"status": status, "revision": revision}


def _load(conn, *, tenant_id, intake_id) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT links, proposal, applied FROM intake_dining_links WHERE tenant_id=%s AND intake_id=%s",
                    (tenant_id, intake_id))
        row = cur.fetchone()
        if row:
            return {"links": deepcopy(row[0]), "proposal": deepcopy(row[1]), "applied": dict(row[2])}
        # 다시 연 여행은 새 접수다. 같은 고객/tenant의 마지막 확정 접수에서 출처만 이어 받는다.
        cur.execute("SELECT links.links FROM intake_dining_links links JOIN trip_intakes previous "
                    "ON previous.intake_id=links.intake_id AND previous.tenant_id=links.tenant_id "
                    "JOIN trip_intakes current ON current.reopen_trip_id=previous.trip_id "
                    "AND current.tenant_id=previous.tenant_id AND current.customer_id=previous.customer_id "
                    "WHERE current.tenant_id=%s AND current.intake_id=%s AND previous.status='confirmed' "
                    "ORDER BY previous.updated_at DESC LIMIT 1", (tenant_id, intake_id))
        inherited = cur.fetchone()
    links = deepcopy(inherited[0]) if inherited else []
    for link in links:
        link.update(placement_status="waiting", placement_reason=None)
    return {"links": links, "proposal": None, "applied": {}}


def _save(conn, *, tenant_id, intake_id, data) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO intake_dining_links (tenant_id,intake_id,links,proposal,applied) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (intake_id) DO UPDATE SET links=EXCLUDED.links, "
                    "proposal=EXCLUDED.proposal,applied=EXCLUDED.applied,updated_at=now() "
                    "WHERE intake_dining_links.tenant_id=EXCLUDED.tenant_id",
                    (tenant_id, intake_id, Jsonb(data["links"]), Jsonb(data["proposal"]), Jsonb(data["applied"])))


def _revision(owner, revision):
    if revision != owner["revision"]:
        raise pipeline.IntakeConflict("stale_revision", "그 사이 일정이 바뀌었어요. 새로 불러와 주세요.",
                                      current_revision=owner["revision"])


def list_links(conn, *, tenant_id, customer_id, intake_id) -> dict[str, Any]:
    owner = _owner(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
    data = _load(conn, tenant_id=tenant_id, intake_id=intake_id)
    return {"revision": owner["revision"], "links": data["links"]}


def resolve(conn, *, tenant_id, customer_id, intake_id, entries, chat=None, fetch=None, progress=None) -> dict[str, Any]:
    with conn.transaction():
        owner = _owner(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, lock=True, editable=True)
        data = _load(conn, tenant_id=tenant_id, intake_id=intake_id)
        resolved = social_links.resolve_links(entries, chat=chat, fetch=fetch, limits=_limits(), progress=progress)
        indexed = {link["key"]: link for link in data["links"]}
        for link in resolved:
            old = indexed.get(link["key"])
            if old:
                old["source_urls"] = list(dict.fromkeys([*old.get("source_urls", []), *link.get("source_urls", [])]))
                # 실패한 링크의 재시도는 회복시키되 이미 확인한 고객 선택은 재전송으로 잃지 않는다.
                #   회복한 결과로 통째로 바꾼다 — 앞 시도의 실패 칸(source_failure 등)이 남지 않게(2026-10-15 브라우저 실측).
                if not old.get("restaurants") and link.get("restaurants"):
                    indexed[link["key"]] = {**link, "source_urls": old["source_urls"],
                                            "priority": "must" if "must" in (old.get("priority"), link.get("priority")) else link["priority"],
                                            "placement_status": old.get("placement_status", "waiting")}
            else:
                indexed[link["key"]] = {**link, "placement_status": "waiting"}
        if len(indexed) > int(_limits()["max_links"]):
            raise pipeline.IntakeRejected("too_many_links", "보관할 수 있는 링크 수를 넘었어요")
        data["links"], data["proposal"] = list(indexed.values()), None
        _save(conn, tenant_id=tenant_id, intake_id=intake_id, data=data)
    return {"revision": owner["revision"], "links": data["links"]}


def update(conn, *, tenant_id, customer_id, intake_id, key, priority=None, restaurant_index=None,
           selected_ref=None, name=None, area=None) -> dict[str, Any]:
    with conn.transaction():
        owner = _owner(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, lock=True, editable=True)
        data = _load(conn, tenant_id=tenant_id, intake_id=intake_id)
        link = next((link for link in data["links"] if link["key"] == key), None)
        if link is None:
            raise LookupError("dining_link")
        if priority is not None:
            if priority not in ("must", "if_fits"):
                raise pipeline.IntakeRejected("invalid_priority", "희망 우선순위가 올바르지 않아요")
            link["priority"] = priority
        if name is not None or area is not None:
            before = (link.get("restaurants") or [{}])[link.get("restaurant_index", 0)]
            text = str(name if name is not None else before.get("name") or "").strip()
            region = str(area if area is not None else before.get("area") or "").strip()
            if not text:
                raise pipeline.IntakeRejected("restaurant_name_required", "식당명을 알려 주세요")
            link["restaurants"] = [{"name": text, "area": region, "branch": None,
                                    "evidence": [{"source": "customer_note", "quote": f"{text} {region}".strip(),
                                                  "source_url": link["source_urls"][0], "checked_at": _now().isoformat()}]}]
            link.update(restaurant_index=0, choices=[], status="identified", reason=None)
            link.pop("selected_ref", None)
        if restaurant_index is not None:
            if (isinstance(restaurant_index, bool) or not isinstance(restaurant_index, int)
                    or not 0 <= restaurant_index < len(link.get("restaurants") or [])):
                raise pipeline.IntakeRejected("invalid_restaurant_choice", "저장된 식당 후보를 골라 주세요")
            if restaurant_index != link.get("restaurant_index"):
                link.update(restaurant_index=restaurant_index, choices=[], status="identified", reason=None)
                link.pop("selected_ref", None)
        if selected_ref is not None:
            if not any(choice.get("ref") == selected_ref for choice in link.get("choices", [])):
                raise pipeline.IntakeRejected("invalid_place_choice", "서버에서 확인한 가게·지점을 골라 주세요")
            link.update(selected_ref=selected_ref, status="confirmed", reason=None)
        link.update(placement_status="waiting", placement_reason=None)
        data["proposal"] = None
        _save(conn, tenant_id=tenant_id, intake_id=intake_id, data=data)
    return {"revision": owner["revision"], "links": data["links"]}


def _eligible(item, now) -> bool:
    if (item.get("kind") != "dining" or item.get("locked") or item.get("completed")
            or item.get("booked") is True or item.get("booking_no")):
        return False
    try:
        start = datetime.fromisoformat(f"{item['date']}T{item['starts_at']}").replace(tzinfo=KST)
    except (KeyError, TypeError, ValueError):
        return False
    return start > now


def _dietary_requirements(conn, *, tenant_id, customer_id, intake_id) -> tuple[str, ...]:
    """원래 여행과 접수 설문의 명시적 조건만 읽는다. 취향을 식이 제한으로 만들지 않는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT trip.constraints, intake.revision FROM trip_intakes intake LEFT JOIN trips trip "
                    "ON trip.trip_id=intake.reopen_trip_id AND trip.tenant_id=intake.tenant_id "
                    "AND trip.customer_id=intake.customer_id WHERE intake.tenant_id=%s "
                    "AND intake.intake_id=%s AND intake.customer_id=%s", (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
    constraints = [dict((row[0] if row else None) or {})]
    if row:
        current = effective(pipeline._claims(conn, tenant_id, intake_id, row[1]))
        constraints.extend(dict(claim["value"] or {}) for claim in current if claim["field"] == "trip.constraints")
    answers = survey_answers.stored(conn, tenant_id=tenant_id, intake_id=intake_id)
    resolved = survey_answers.stored_resolved(conn, tenant_id=tenant_id, intake_id=intake_id)
    intake_survey = survey_answers.to_survey(answers, resolved)
    required = set()
    aliases = {"vegetarian_menu": "vegetarian", "채식": "vegetarian", "할랄": "halal"}

    def tokens(raw):
        if isinstance(raw, str):
            return [raw] if raw.strip() else []
        return [value for value in raw if isinstance(value, str) and value.strip()] if isinstance(raw, (list, tuple)) else []

    for source in constraints:
        for value in tokens(source.get("dietary")):
            required.add(aliases.get(value, value))
        for value in tokens(source.get("allergies") or source.get("allergy")):
            required.add("allergy:" + value)
    # 음식 세부의 맛/친절 등은 기존 계약상 취향이며, 판정 근거가 필요한 조건만 가져온다.
    for survey in [source.get("survey") or {} for source in constraints] + [intake_survey]:
        details = survey.get("priority_details") or {}
        for value in tokens(details.get("food")):
            if value in ("vegetarian", "vegetarian_menu", "halal", "채식", "할랄", "vegan") or value.startswith(("allergy", "알레르기")):
                required.add(aliases.get(value, value))
        for value in tokens((survey.get("custom_answers") or {}).get("food")):
            # 자유문장으로 요청한 알레르기의 안전성을 파싱/추정하지 않는다. 확인할 수 없다는 사실을 남긴다.
            if "allerg" in value.lower() or "알레르기" in value:
                required.add("allergy:" + value)
    return tuple(sorted(required))


def _dietary_verdict(conn, *, tenant_id, place, item, required) -> str | None:
    if not required:
        return None
    start = datetime.fromisoformat(f"{item['date']}T{item['starts_at']}").replace(tzinfo=KST)
    end = (datetime.fromisoformat(f"{item['date']}T{item['ends_at']}").replace(tzinfo=KST)
           if item.get("ends_at") else None)
    ref = str(place.get("ref") or "")
    facts = None
    try:
        if ref.startswith("place:"):
            facts = dining_ledger.state(conn, tenant_id, ref.partition(":")[2], start, end)
        if facts is None:
            # 현재 이름 조회는 identity만 준다. 식이 근거가 없는 반환을 성공으로 올리지 않는다.
            found = dining_ledger.find_by_name(conn, place.get("name"))
            if (found and found.get("match") == "exact" and found.get("needs_review") is False
                    and found.get("latitude") == place.get("latitude") and found.get("longitude") == place.get("longitude")):
                facts = found
    except TeamUnavailable:
        return "unknown_dietary"
    if not facts or facts.get("source") != "dining_ledger" or facts.get("available") is False or facts.get("linked") is False:
        return "unknown_dietary"
    absent = set(facts.get("dietary_absent") or [])
    known = set(facts.get("dietary") or [])
    if absent.intersection(required):
        return "dietary_conflict"
    return None if set(required) <= known else "unknown_dietary"


def _ref(place) -> str:
    if place.get("ref"):
        return str(place["ref"])
    identity = json.dumps([place.get("name"), place.get("latitude"), place.get("longitude")], ensure_ascii=False)
    return "social-place:" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def _verified(candidate) -> bool:
    rows = candidate.get("rows") or candidate.get("checks") or []
    required = {row.get("row") for row in rows}
    return (candidate.get("fits") is True and {"place", "hours", "closed"} <= required
            and all(row.get("result") in ("ok", "filled") for row in rows))


#: 같은 가게로 보는 거리 — 요식 원장의 같은 이름 기준(`dining/ledger.SAME_NAME_RADIUS_M`)과 같다. components 는 instances 를 import 하지 않아 값을 옮겨 둔다.
SAME_SHOP_RADIUS_M = 150
_BRANCH_TAIL = re.compile(r"(본점|직영점|분점|별관|본관|신관|[가-힣a-z0-9]{1,8}점)")


def _name_and_branch(name: str) -> tuple[str, str]:
    """띄어 쓴 지점 꼬리 전체를 보존한다. 「별관 본점」의 마지막 말만 비교하지 않는다."""
    parts = re.sub(r"[\(\[（【].*?[\)\]）】]", "", name or "").split()
    tails = []
    while len(parts) > 1 and _BRANCH_TAIL.fullmatch(candidates.normalize_full(parts[-1])):
        tails.insert(0, parts.pop())
    return candidates.normalize_full(" ".join(parts)), candidates.normalize_full(" ".join(tails))


def _metres(a, b) -> float:
    p = math.pi / 180
    h = (math.sin((b[0] - a[0]) * p / 2) ** 2
         + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2)
    return 12_742_000 * math.asin(math.sqrt(h))


def _road_key(address):
    found = re.search(r"([가-힣A-Za-z0-9]+(?:로|길))\s*(\d+(?:-\d+)?)(?![가-힣\d-])", address or "")
    return f"{found[1]}{found[2]}" if found else None


def _same_place(a, b) -> bool:
    """같은 실제 가게인가. 제공자마다 이름 끝(「본점」)과 좌표가 조금씩 다르다(2026-10-15 실측: 장소 목록 「우래옥」 · 카카오 「우래옥 본점」).

    지점 표시를 뗀 이름이 같고 150m 안이며, 지점 표시가 서로 다르지 않을 때(한쪽이 없거나 같을 때)만 같다고 본다 —
    「서울역점」 · 「종로점」, 「본점」 · 「별관」처럼 다른 지점 표시는 가까워도 고객이 고른다."""
    if not a or not b:
        return False
    if a.get("ref") and a.get("ref") == b.get("ref"):
        return True
    (base_a, tail_a), (base_b, tail_b) = _name_and_branch(a.get("name") or ""), _name_and_branch(b.get("name") or "")
    if not base_a or not base_b or (tail_a and tail_b and tail_a != tail_b):
        return False
    roads = _road_key(a.get("address")), _road_key(b.get("address"))
    if all(roads) and roads[0] != roads[1]:
        return False
    try:
        here, there = (float(a["latitude"]), float(a["longitude"])), (float(b["latitude"]), float(b["longitude"]))
    except (KeyError, TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for point in (here, there) for value in point):
        return False
    if _metres(here, there) > SAME_SHOP_RADIUS_M:
        return False
    return base_a == base_b


def _richer(a, b) -> bool:
    """같은 가게의 두 결과 중 a 가 더 쓸모 있나 — 검사 통과(fits) 먼저, 그다음 카카오가 아닌 출처(운영시간 · 휴무가 있다)."""
    return (a.get("fits") is True, a.get("source") != "kakao") > (b.get("fits") is True, b.get("source") != "kakao")


def _canonical_choices(identities, branch_hint):
    """지점 없는 제공자 행이 본점/별관 둘을 연결하지 않게 하고, 지점 근거도 함께 본다."""
    choices = list(identities.values())
    ambiguous = set()
    for choice in choices:
        if _name_and_branch(choice.get("name") or "")[1]:
            continue
        labels = {_name_and_branch(other.get("name") or "")[1] for other in choices
                  if _same_place(choice, other)} - {""}
        if len(labels) > 1:
            ambiguous.add(choice["ref"])
    groups = []
    for choice in choices:
        group = next((group for group in groups if choice["ref"] not in ambiguous
                      and all(saved["ref"] not in ambiguous and _same_place(saved, choice) for saved in group)), None)
        if group is None:
            groups.append([choice])
        else:
            group.append(choice)
    canonical, aliases = [], {}
    requested = candidates.normalize_full(branch_hint or "")
    for group in groups:
        if requested and not any(requested == _name_and_branch(choice.get("name") or "")[1] for choice in group):
            continue
        kept = group[0]
        for choice in group[1:]:
            if _richer(choice, kept):
                kept = choice
        canonical.append(kept)
        aliases.update({choice["ref"]: kept["ref"] for choice in group if choice["ref"] != kept["ref"]})
    return canonical, aliases


def _search_hints(restaurant):
    name = str(restaurant.get("name") or "").strip()
    branch = str(restaurant.get("branch") or "").strip()
    area = str(restaurant.get("area") or "").strip()
    base = name[:-len(branch)].rstrip() if branch and name.endswith(branch) else name
    base = base or name
    query = " ".join(part for part in (name, branch if branch and not name.endswith(branch) else "", area) if part)
    return query, base, branch, area


def _held_by_wish(item, links) -> bool:
    """이 식사에 고객이 고른 다른 SNS 희망 식당이 이미 들어 있나 — 자동 배치가 그 자리를 다른 희망으로 바꾸지 않게(2026-10-15 실측)."""
    for link in links:
        chosen = next((choice for choice in link.get("choices") or [] if choice.get("ref") == link.get("selected_ref")), None)
        if chosen and _same_place(chosen, item.get("place")):
            return True
    return False


def _unplaced(link, reason) -> dict[str, Any]:
    restaurants = link.get("restaurants") or []
    index = link.get("restaurant_index", 0)
    name = restaurants[index].get("name") if 0 <= index < len(restaurants) else None
    link.update(placement_status="unplaced", placement_reason=reason)
    return {"key": link["key"], "name": name, "priority": link.get("priority", "if_fits"),
            "reason": reason, "message": _MESSAGES.get(reason, "식당 정보와 확인 결과를 보완해 주세요.")}


def _discover(conn, *, tenant_id, review, slots, links, kakao, now, limit, dietary):
    """장소 identity를 먼저 확인한다. 거리/검사 순서는 다수 지점 중 선택을 대신하지 않는다."""
    edges, by_key, failures = {}, {}, {}
    calls = 0
    for link in sorted(links, key=lambda link: link.get("priority") != "must"):
        link.pop("duplicate_of", None)
        key = link["key"]
        restaurants = link.get("restaurants") or []
        if not restaurants:
            failures[key] = link.get("reason") or "place_not_found"
            continue
        index = link.get("restaurant_index")
        if len(restaurants) > 1 and index is None:
            link.update(status="needs_choice", reason="restaurant_choice_required")
            failures[key] = "restaurant_choice_required"
            continue
        restaurant = restaurants[index if index is not None else 0]
        link["restaurant_index"] = index if index is not None else 0
        # 고른 지점이 이미 일정에 있으면 다시 찾지 않는다 — 그 식사가 검색에서 빠져 고른 지점을 잃고 「골라 주세요」로 돌아가던 것(2026-10-15 실측).
        chosen = next((choice for choice in link.get("choices") or [] if choice.get("ref") == link.get("selected_ref")), None)
        if chosen and any(_same_place(chosen, item.get("place")) for item in review["items"]):
            link.update(status="confirmed", reason=None)
            failures[key] = "already_scheduled"
            continue
        query, name_hint, branch_hint, area_hint = _search_hints(restaurant)
        identities, found, search_failures = {}, {}, set()
        for item in slots:
            if calls >= limit:
                break
            calls += 1
            results = candidates.search(conn, tenant_id=tenant_id, review=review, item=item, query=query,
                                        name_hint=name_hint, branch_hint=branch_hint, area_hint=area_hint,
                                        kakao=kakao, now=now)
            search_failures.update(note for note in results.get("notes", []) if note in {"area_unverified", "area_mismatch"})
            valid = []
            for result in results.get("results", []):
                place = result.get("place") or {}
                name = candidates.normalize_full(name_hint)
                if not name or name not in candidates.normalize_full(place.get("name") or "") or place.get("kind") != "dining":
                    continue
                if not all(isinstance(place.get(c), (int, float)) and not isinstance(place.get(c), bool)
                           for c in ("latitude", "longitude")):
                    continue
                if not (pipeline.SEOUL_LAT[0] <= place["latitude"] <= pipeline.SEOUL_LAT[1]
                        and pipeline.SEOUL_LON[0] <= place["longitude"] <= pipeline.SEOUL_LON[1]):
                    continue
                ref = _ref(place)
                choice = {**place, "ref": ref, "checks": deepcopy(result.get("rows") or []),
                          "fits": result.get("fits") is True, "status": result.get("status"), "reason": result.get("reason")}
                identities[ref] = choice
                valid.append((ref, result, choice))
            found[item["id"]] = valid
        canonical, aliases = _canonical_choices(identities, branch_hint)
        link["choices"] = canonical
        selected = link.get("selected_ref")
        selected = aliases.get(selected, selected)
        if selected and selected not in {choice["ref"] for choice in canonical}:
            if chosen:
                # 고객이 고른 지점이 이번 검색에 없다 — 선택을 지우고 남은 한 곳을 대신 넣지 않는다. 그 후보만 보류한다(2026-10-15).
                link["choices"] = [*canonical, chosen]
                link.update(status="confirmed", reason="selected_place_unavailable")
                failures[key] = "selected_place_unavailable"
                continue
            link.pop("selected_ref", None)
            selected = None
        if not selected and len(canonical) == 1:
            selected = canonical[0]["ref"]
        if not canonical:
            failures[key] = ("branch_unverified" if identities and branch_hint else
                             "area_unverified" if "area_unverified" in search_failures else
                             "area_mismatch" if "area_mismatch" in search_failures else
                             "preview_budget_exhausted" if calls >= limit else "place_not_found")
            link.update(status="needs_info", reason=failures[key])
            continue
        if not selected:
            link.update(status="needs_choice", reason="place_choice_required")
            failures[key] = "place_choice_required"
            continue
        choice = next(choice for choice in canonical if choice["ref"] == selected)
        link.update(selected_ref=selected, status="confirmed", reason=None)
        if any(_same_place(choice, item.get("place")) for item in review["items"]):
            failures[key] = "already_scheduled"
            continue
        edges[key] = []
        any_unknown = False
        dietary_failures = []
        by_slot = {item["id"]: item for item in slots}
        for item_id, results in found.items():
            for ref, result, _ in results:
                if aliases.get(ref, ref) != selected:
                    continue
                any_unknown |= any(row.get("result") == "unknown" for row in result.get("rows", []))
                if _verified(result):
                    diet = _dietary_verdict(conn, tenant_id=tenant_id, place=choice, item=by_slot[item_id], required=dietary)
                    if diet:
                        dietary_failures.append(diet)
                    else:
                        edges[key].append(item_id)
        by_key[key] = choice
        if not edges[key]:
            failures[key] = ("dietary_conflict" if "dietary_conflict" in dietary_failures else
                             "unknown_dietary" if dietary_failures else "unknown_facts" if any_unknown else "does_not_fit")
    return edges, by_key, failures


def _matching(links, edges, choices):
    assigned, seen_places, duplicate = {}, [], {}
    ordered = sorted(links, key=lambda link: link.get("priority") != "must")

    def place(key, visited):
        for slot in edges.get(key, []):
            if slot in visited:
                continue
            visited.add(slot)
            if slot not in assigned or place(assigned[slot], visited):
                assigned[slot] = key
                return True
        return False

    for link in ordered:
        key = link["key"]
        if key not in choices:
            continue
        same = next((previous for previous in seen_places if _same_place(choices[previous], choices[key])), None)
        if same:
            duplicate[key] = same
            continue
        seen_places.append(key)
        place(key, set())
    return {key: slot for slot, key in assigned.items()}, duplicate


def _edits(changes, items):
    by_id = {item["id"]: item for item in items}
    edits = []
    for change in changes:
        item = by_id[change["item_id"]]
        # 기존 장소 선택기가 받는 제공자만 보낸다. SNS provenance는 links에 그대로 남는다.
        place = {k: v for k, v in change["to"].items() if k in
                 ("name", "latitude", "longitude", "source", "kind", "category", "content_id", "content_type_id", "address", "ref")}
        for field, value in (("place", place), ("title", place["name"])):
            edits.append({"source_id": item["source_id"], "field": f"items[{item['index']}].{field}", "value": value})
    return edits


def _assert_view(before, view, changed):
    after = view.get("review") or {}
    old = [item for item in before["items"] if item.get("kind") != "dining"]
    new = [item for item in after.get("items", []) if item.get("kind") != "dining"]
    fields = ("id", "source_id", "index", "kind", "title", "date", "starts_at", "ends_at", "end_date", "place", "locked")
    def snapshot(item):
        value = {field: item.get(field) for field in fields}
        if value["place"]:
            value["place"] = {key: val for key, val in value["place"].items() if key != "place_id"}
        return value
    if [snapshot(item) for item in old] != [snapshot(item) for item in new]:
        raise pipeline.IntakeConflict("activity_change_required", _MESSAGES["activity_change_required"])
    # 고정 식사도 direct_schedule의 연쇄 조정으로 바뀌면 안 된다.
    by_id = {item["id"]: item for item in after.get("items", [])}
    for item in before["items"]:
        if item.get("kind") == "dining" and item["id"] not in changed:
            if snapshot(item) != snapshot(by_id.get(item["id"], {})):
                raise pipeline.IntakeConflict("activity_change_required", _MESSAGES["activity_change_required"])
    if not view.get("check", {}).get("ready") or not after.get("ready"):
        raise pipeline.IntakeConflict("full_validation_failed", _MESSAGES["full_validation_failed"])
    for item_id in changed:
        item = by_id.get(item_id)
        if item is None or not _verified({"fits": True, "rows": item.get("rows", [])}):
            raise pipeline.IntakeConflict("full_validation_failed", _MESSAGES["full_validation_failed"])
    if any(move.get("status") in ("review", "waiting") for move in after.get("moves", [])):
        raise pipeline.IntakeConflict("full_validation_failed", _MESSAGES["full_validation_failed"])
    for move in after.get("moves", []):
        if move.get("from") in changed or move.get("to") in changed:
            rows = move.get("rows") or []
            if (not {"route", "mode", "arrival"} <= {row.get("row") for row in rows}
                    or any(row.get("result") not in ("ok", "filled") for row in rows)):
                raise pipeline.IntakeConflict("full_validation_failed", _MESSAGES["full_validation_failed"])


class _RollbackPreview(Exception):
    pass


def _dry_run(conn, *, tenant_id, customer_id, intake_id, revision, review, changes, kakao):
    try:
        with conn.transaction(force_rollback=True):
            pipeline.edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision,
                          edits=_edits(changes, review["items"]), kakao=kakao, via="social_dining")
            view = pipeline.view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
            _assert_view(review, view, {change["item_id"] for change in changes})
            raise _RollbackPreview()
    except _RollbackPreview:
        pass


def preview(conn, *, tenant_id, customer_id, intake_id, revision, target_item_id=None, chat=None, kakao=None, now=None):
    now = now or _now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    with conn.transaction():
        owner = _owner(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, lock=True, editable=True)
        _revision(owner, revision)
        _, review = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
        data = _load(conn, tenant_id=tenant_id, intake_id=intake_id)
        meals = [item for item in review["items"] if item.get("kind") == "dining"]
        slots = [item for item in meals if _eligible(item, now)
                 and (item["id"] == target_item_id if target_item_id is not None else not _held_by_wish(item, data["links"]))]
        if target_item_id is not None and not any(item["id"] == target_item_id for item in meals):
            raise pipeline.IntakeRejected("invalid_target_item", "이 접수의 식사 일정을 골라 주세요")
        links, unplaced, changes = data["links"], [], []
        _, planning = social_dining_rank.rank_edges(links, {}, {}, slots=slots)
        if not slots:
            unplaced = [_unplaced(link, "no_meal_slots" if not meals else "no_future_meal_slots") for link in links]
        else:
            dietary = _dietary_requirements(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
            edges, choices, failures = _discover(conn, tenant_id=tenant_id, review=review, slots=slots, links=links,
                                                 kakao=kakao, now=now, limit=int(_limits()["max_preview_pairs"]), dietary=dietary)
            ranking_slots = []
            for item in slots:
                previous, following = candidates.neighbours(review["items"], item)
                ranking_slots.append({**item, "previous": previous, "next": following})
            edges, planning = social_dining_rank.rank_edges(links, edges, choices, slots=ranking_slots, chat=chat)
            assignment, duplicate = _matching(links, edges, choices)
            by_key = {link["key"]: link for link in links}
            for repeated, primary in duplicate.items():
                by_key[primary]["source_urls"] = list(dict.fromkeys([
                    *by_key[primary].get("source_urls", []), *by_key[repeated].get("source_urls", [])]))
            item_by_id = {item["id"]: item for item in slots}
            ordered = sorted(links, key=lambda link: link.get("priority") != "must")
            for link in ordered:
                key = link["key"]
                if key in assignment:
                    item = item_by_id[assignment[key]]
                    changes.append({"key": key, "item_id": item["id"], "from": deepcopy(item.get("place")),
                                    "to": deepcopy(choices[key]), "reason": "customer_wish"})
            if changes:
                try:
                    _dry_run(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision,
                             review=review, changes=changes, kakao=kakao)
                except (pipeline.IntakeConflict, pipeline.IntakeRejected):
                    # 충돌하는 묶음 때문에 독립적으로 가능한 다른 식당까지 버리지 않는다.
                    accepted = []
                    occupied = set()
                    for change in changes:
                        key = change["key"]
                        alternatives = list(dict.fromkeys([change["item_id"], *edges.get(key, [])]))
                        for slot_id in alternatives:
                            if slot_id in occupied:
                                continue
                            trial = {**change, "item_id": slot_id, "from": deepcopy(item_by_id[slot_id].get("place"))}
                            try:
                                _dry_run(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision,
                                         review=review, changes=[*accepted, trial], kakao=kakao)
                                accepted.append(trial)
                                occupied.add(slot_id)
                                failures.pop(key, None)
                                break
                            except (pipeline.IntakeConflict, pipeline.IntakeRejected) as candidate_exc:
                                failures[key] = ("activity_change_required" if candidate_exc.code == "activity_change_required"
                                                 else "full_validation_failed")
                    changes = accepted
            changed_keys = {change["key"] for change in changes}
            for link in links:
                key = link["key"]
                if key in changed_keys:
                    link.update(placement_status="waiting", placement_reason=None)
                elif key in duplicate:
                    link["duplicate_of"] = duplicate[key]
                    unplaced.append(_unplaced(link, "duplicate_restaurant"))
                else:
                    unplaced.append(_unplaced(link, failures.get(key, "no_available_slot")))
        proposal_id = str(uuid4()) if changes else None
        data["proposal"] = ({"proposal_id": proposal_id, "revision": revision, "changes": changes,
                             "edits": _edits(changes, review["items"]), "created_at": now.isoformat(),
                             "planning": planning} if changes else None)
        _save(conn, tenant_id=tenant_id, intake_id=intake_id, data=data)
    return {"revision": revision, "proposal_id": proposal_id, "changes": changes, "unplaced": unplaced,
            "links": links, "planning": planning}


def apply(conn, *, tenant_id, customer_id, intake_id, revision, proposal_id, kakao=None, dining=None):
    with conn.transaction():
        owner = _owner(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, lock=True, editable=True)
        data = _load(conn, tenant_id=tenant_id, intake_id=intake_id)
        if proposal_id in data["applied"]:
            return pipeline.view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
        _revision(owner, revision)
        proposal = data["proposal"]
        if not proposal or proposal["proposal_id"] != proposal_id:
            raise pipeline.IntakeConflict("proposal_not_found", "이 변경안은 더 이상 적용할 수 없어요. 다시 확인해 주세요.")
        _revision(owner, proposal["revision"])
        _, review = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id,
                                             revision=revision, force=True)
        eligible = {item["id"] for item in review["items"] if _eligible(item, _now())}
        if any(change["item_id"] not in eligible for change in proposal["changes"]):
            raise pipeline.IntakeConflict("meal_no_longer_editable", "식사가 시작됐거나 고정되었어요. 변경안을 다시 확인해 주세요.")
        dietary = _dietary_requirements(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
        by_id = {item["id"]: item for item in review["items"]}
        for change in proposal["changes"]:
            verdict = _dietary_verdict(conn, tenant_id=tenant_id, place=change["to"], item=by_id[change["item_id"]], required=dietary)
            if verdict:
                raise pipeline.IntakeConflict(verdict, _MESSAGES[verdict])
        pipeline.edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision,
                      edits=proposal["edits"], kakao=kakao, dining=dining, via="social_dining")
        _, after = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id,
                                            revision=revision + 1, force=True)
        view = pipeline.view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
        view["review"] = after
        _assert_view(review, view, {change["item_id"] for change in proposal["changes"]})
        changed = {change["key"] for change in proposal["changes"]}
        for link in data["links"]:
            if link["key"] in changed or link.get("duplicate_of") in changed:
                link.update(placement_status="applied", placement_reason=None)
        data["applied"][proposal_id] = revision + 1
        data["proposal"] = None
        _save(conn, tenant_id=tenant_id, intake_id=intake_id, data=data)
    return view


__all__ = ["list_links", "resolve", "update", "preview", "apply"]
