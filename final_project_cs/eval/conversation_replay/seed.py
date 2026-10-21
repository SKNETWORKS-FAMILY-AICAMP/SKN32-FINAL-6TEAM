# -*- coding: utf-8 -*-
"""에피소드 시작 상태를 **따로 만든 시험 DB** 에 넣는다(재생 시험 계획 「실행 환경」). `[2026-10-19]`

★운영 DB 에는 절대 쓰지 않는다 — `assert_test_db` 가 접속 주소에 시험 DB 표시(`replay`)가 없으면 멈춘다.
에피소드마다 **새 고객 · 새 여행**을 만든다(원래 id 는 이름 공간 uuid5 로 바꿔 옮긴다 — 같은 여행의 에피소드 여럿이 서로 섞이지 않게).

넣는 것(실제 대화 — 원래 DB 의 읽기 사본 `raw/20261019_more/<환경>.jsonl` 에서):
  - 여행(제목 · 인원 · 조건) · **시작 판까지의 모든 판과 항목**(「되돌려줘」가 앞 판을 보므로) · 항목이 가리키는 장소
  - 시작 시각 전의 대화 줄(`trip_chat_turns`)과 그 줄이 가리키는 Case(답 구조 `chat_reply` 를 대화 기록이 읽는다)
  - 시작 시각에 답을 기다리던 Case(`waiting_input`) — 원래 상태 전체가 사본에 없어 **Case 기록의 `state_patch` 를 차례로 합쳐 다시 만든다**(재구성 표시)
  - 시작 시각에 열려 있던 보류 제안(`pending_changes`)
표적 에피소드: 항목 · 장소 이름 · 실내 표시만 있다 — 장소는 이름으로 장소 목록에서 찾고, 못 찾으면 이름만 있는 장소를 만든다.
장소: 참고 자료 사본(x600 서버 `places`)이 있으면 같은 행을 쓰고, 없으면 **이름만 있는 장소**(좌표 · 영업시간 모름)를 만든다 — 결과에 「장소 자료 없음」으로 표시.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .state import parse_dt

TENANT = "demo"


def assert_test_db(url: str) -> None:
    if "replay" not in (url or ""):
        raise RuntimeError("재생 시험 DB 가 아니다 — 접속 주소에 'replay' 가 있는 DB 에만 쓴다(운영 DB 보호)")


def _uid(ns: str, old: Any) -> UUID:
    return uuid5(NAMESPACE_URL, f"replay:{ns}:{old}")


@dataclass
class RawIndex:
    """원래 DB 읽기 사본 — 여행 id 로 묶는다. 필요한 여행만 읽는다."""
    rows: dict[str, dict[str, list[dict]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))
    events: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))
    places: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, raw_dir: Path, trip_ids: set[str], *, places_file: Path | None = None) -> "RawIndex":
        idx = cls()
        case_trip: dict[str, str] = {}
        for env in ("x600", "oracle", "aws"):
            path = raw_dir / f"{env}.jsonl"
            if not path.exists():
                continue
            # ★읽는 순서: 사본 파일은 표 단위로 쓰여 `case` 줄이 `case_event` 줄보다 앞이다 → 필요한 Case 의 기록만 그 자리에서 골라 담는다
            #   (전부 담으면 x600 사본이 가상 메모리를 넘는다 — 2026-10-20 MemoryError). 근거 목록(`evidence`)은 큰데 재구성에 필요 없어 뺀다.
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    rec = json.loads(line)
                    t, r = rec["t"], rec["r"]
                    if t == "case_event":
                        if str(r["case_id"]) in case_trip:
                            patch = (r.get("payload") or {}).get("state_patch")
                            if isinstance(patch, dict) and "evidence" in patch:
                                patch.pop("evidence", None)
                            idx.events[str(r["case_id"])].append(r)
                        continue
                    tid = str(r.get("trip_id") or "")
                    if tid not in trip_ids:
                        continue
                    idx.rows[tid][t].append(r)
                    if t == "case":
                        case_trip[str(r["case_id"])] = tid
        if places_file and places_file.exists():
            with places_file.open(encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    if "t" in row and "r" in row:          # fetch_reference.py 모양 — places 줄만
                        if row["t"] != "places":
                            continue
                        row = row["r"]
                    idx.places[str(row["place_id"])] = row
        return idx


def _fold_state(case: dict, events: list[dict], until: datetime) -> tuple[dict, str, str | None]:
    """Case 기록을 시각 순으로 합쳐 시작 시각의 상태(state_json) · 상태 이름 · 담당 팀을 다시 만든다(재구성)."""
    state: dict[str, Any] = {}
    status = "new"
    owner = None
    to_status = {"created": "new", "classified": "classifying", "routed": "running", "missing_input": "waiting_input",
                 "valid_input": "resuming", "resumed": "running", "completed": "resolved", "guardrail_escalated": "escalated",
                 "routing_failed": "escalated", "classification_failed": "escalated", "cancelled": "cancelled"}
    waited_at = None
    for e in sorted(events, key=lambda x: (x.get("v") or 0)):
        at = parse_dt(e.get("at"))
        if at is not None and at >= until:
            break
        payload = e.get("payload") or {}
        state.update(payload.get("state_patch") or {})
        status = to_status.get(e.get("type"), status)
        owner = payload.get("owner_team_id") or owner
        if e.get("type") == "missing_input":
            waited_at = at
    if case.get("chat_reply") and "chat_reply" not in state:
        state["chat_reply"] = case["chat_reply"]
    if case.get("waiting") and "waiting_input" not in state:
        state["waiting_input"] = case["waiting"]
    if status == "waiting_input":
        state.setdefault("wait_reason", "customer_input")
        # ★재개 열쇠: 사본에는 가린 값(「[REDACTED]」)만 있다 → 시험용 해시를 새로 둔다(묵시적 재개는 저장된 해시를 그대로 쓴다).
        #   만료는 **원래 시각 기준으로 남아 있던 시간**을 지금 벽시계에 옮긴다 — 제품은 만료를 벽시계로 보므로 그대로 두면 모두 만료로 보인다.
        import hashlib
        from datetime import timezone

        from app.core.settings import get_guardrails

        ttl = timedelta(hours=float(get_guardrails().get("resume.token_ttl_hours")))
        left = ((waited_at or until) + ttl) - until
        state["resume_token_hash"] = hashlib.sha256(f"replay:{case.get('case_id')}".encode()).hexdigest()
        state["resume_token_used"] = False
        expires = datetime.now(timezone.utc) + left + timedelta(hours=1) if left.total_seconds() > 0             else datetime.now(timezone.utc) - timedelta(minutes=1)
        state["resume_token_expires_at"] = expires.isoformat()
    return state, status, owner


@dataclass
class Seeded:
    trip_id: UUID
    customer_id: UUID
    user_key: str
    item_map: dict[str, str]
    notes: list[str]
    place_rows: int = 0
    place_placeholders: int = 0


def _place_exists(cur, place_id: Any) -> bool:
    cur.execute("SELECT 1 FROM places WHERE place_id=%s", (str(place_id),))
    return cur.fetchone() is not None


def _insert_place(cur, *, place_id: UUID, name: str, kind: str, row: dict | None, trip_scope: UUID | None) -> bool:
    """장소 한 행. `row`(참고 자료 사본)가 있으면 그대로, 없으면 이름만. 돌려주는 값 — 참고 자료 행을 썼나."""
    if row:
        cur.execute("INSERT INTO places (place_id, tenant_id, name, kind, latitude, longitude, weather_sensitive, hours_confirmed_at, "
                    "open_at_slot, dietary, dietary_absent, source_name, source_content_id, source_content_type_id, source_resolved_at, "
                    "attributes, trip_scope) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT (place_id) DO NOTHING",
                    (place_id, TENANT, row.get("name") or name, row.get("kind") or kind, row.get("latitude"), row.get("longitude"),
                     row.get("weather_sensitive"), row.get("hours_confirmed_at"), row.get("open_at_slot"), row.get("dietary") or [],
                     row.get("dietary_absent") or [], row.get("source_name"), row.get("source_content_id"),
                     row.get("source_content_type_id"), row.get("source_resolved_at"), json.dumps(row.get("attributes") or {}),
                     trip_scope))          # 복사본은 늘 이 여행에 묶는다 — 공용 행(이름 · 종류 유일)과 겹치지 않게
        return True
    cur.execute("INSERT INTO places (place_id, tenant_id, name, kind, attributes, trip_scope) VALUES (%s,%s,%s,%s,%s::jsonb,%s) "
                "ON CONFLICT (place_id) DO NOTHING",
                (place_id, TENANT, name or "이름 모름", kind if kind in ("dining", "activity", "lodging") else "activity",
                 json.dumps({"replay_placeholder": True}), trip_scope))
    return False


def seed_episode(conn, ep: dict[str, Any], raw: RawIndex | None, *, run_tag: str,
                 catalog_find: Callable[[str], dict | None] | None = None) -> Seeded:
    """에피소드 하나를 시험 DB 에 넣는다. `run_tag` — 같은 에피소드를 여러 번 돌릴 때 id 를 가르는 이름(회차)."""
    from app.domains.travel_ops.modules.web_account import web_session

    ns = f"{run_tag}:{ep['episode_id']}"
    start_at = parse_dt(ep["now"])
    notes: list[str] = []
    customer_id, user_key = web_session.issue(conn, tenant_id=TENANT)
    trip_id = _uid(ns, "trip")
    seed = ep.get("seed") or {}
    v2 = seed.get("v2") or {}
    start_version = int(ep["start"]["version"] or 1)
    orig_trip = str(ep.get("trip_id") or "")
    rows = raw.rows.get(orig_trip, {}) if raw else {}
    constraints = v2.get("constraints_now") or seed.get("constraints") or {}
    party = v2.get("party_size_now")
    title = ep.get("trip_title") or "재생 시험 여행"
    item_map: dict[str, str] = {}
    place_map: dict[str, UUID] = {}
    name_map: dict[tuple[str, str], UUID] = {}
    out = Seeded(trip_id=trip_id, customer_id=customer_id, user_key=user_key, item_map=item_map, notes=notes)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO trips (trip_id, tenant_id, customer_id, title, locale, party_size, latest_version, status, constraints, created_at) "
                    "VALUES (%s,%s,%s,%s,'ko',%s,%s,'active',%s::jsonb,%s)",
                    (trip_id, TENANT, customer_id, title, party, start_version, json.dumps(constraints),
                     start_at.isoformat() if start_at else None))
        # 판 · 항목
        versions = sorted((r for r in rows.get("ver", []) if int(r["version"]) <= start_version), key=lambda r: int(r["version"]))
        items_by_v: dict[int, list[dict]] = defaultdict(list)
        for r in rows.get("item", []):
            if int(r["version"]) <= start_version:
                items_by_v[int(r["version"])].append(r)
        if not versions:
            versions = [{"version": start_version, "reason": "replay_seed", "cause_json": [], "created_at": None}]
            items_by_v = {start_version: [_item_from_start(i) for i in ep["start"]["items"]]}
            notes.append("판 기록 없음 — 시작 판만 넣음")
        elif start_version not in items_by_v and ep["start"]["items"]:
            items_by_v[start_version] = [_item_from_start(i) for i in ep["start"]["items"]]
        for v in versions:
            ver = int(v["version"])
            cur.execute("INSERT INTO itinerary_versions (trip_id, version, tenant_id, reason, cause_json, created_at) "
                        "VALUES (%s,%s,%s,%s,%s::jsonb,COALESCE(%s::timestamptz, now()))",
                        (trip_id, ver, TENANT, v.get("reason") or "replay_seed", json.dumps(v.get("cause_json") or []), v.get("created_at")))
        for v in versions:
            ver = int(v["version"])
            for r in sorted(items_by_v.get(ver, []), key=lambda x: int(x.get("seq") or 0)):
                old = str(r.get("item_id"))
                new = item_map.setdefault(old, str(_uid(ns, f"item:{old}")))
                rep = r.get("replaces_item_id")
                rep_new = item_map.setdefault(str(rep), str(_uid(ns, f"item:{rep}"))) if rep else None
                place_id = None
                if r.get("place_id") or r.get("place_name"):
                    old_place = str(r.get("place_id") or f"name:{r.get('place_name')}")
                    ref = raw.places.get(str(r.get("place_id"))) if (raw and r.get("place_id")) else None
                    if ref is None and catalog_find and r.get("place_name"):
                        ref = catalog_find(r["place_name"])
                    if ref is not None and not ref.get("trip_scope") and ref.get("place_id") and _place_exists(cur, ref["place_id"]):
                        # 공용 장소(여행에 묶이지 않은 행)는 참고 자료로 이미 시험 DB 에 있다 — 그 행을 그대로 가리킨다
                        place_id = UUID(str(ref["place_id"]))
                        out.place_rows += 1
                    else:
                        name = ((r.get("detail") or {}).get("provenance") or {}).get("place", {}).get("query") or r.get("place_name") or r.get("title")
                        # 같은 여행 안에서 이름 · 종류가 같은 장소는 한 행만 둔다(원래 DB 에는 같은 이름의 장소 행이 둘일 수 있다 — 유일 조건)
                        final_name = (ref or {}).get("name") or name
                        final_kind = (ref or {}).get("kind") or (r.get("kind") if r.get("kind") in ("dining", "activity", "lodging") else "activity")
                        existing = name_map.get((final_name, final_kind))
                        if existing is not None:
                            place_id = place_map.setdefault(old_place, existing)
                        else:
                            place_id = place_map.setdefault(old_place, _uid(ns, f"place:{old_place}"))
                            used = _insert_place(cur, place_id=place_id, name=name, kind=r.get("kind"), row=ref, trip_scope=trip_id)
                            name_map[(final_name, final_kind)] = place_id
                            out.place_rows += int(used)
                            out.place_placeholders += int(not used)
                    if r.get("place_id"):
                        place_map.setdefault(str(r["place_id"]), place_id)
                detail = dict(r.get("detail") or {})
                if r.get("indoor") is not None:
                    detail["replay_indoor"] = r["indoor"]
                cur.execute("INSERT INTO itinerary_items (item_id, trip_id, version, tenant_id, seq, kind, title, place_id, starts_at, ends_at, "
                            "locked, replaces_item_id, detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                            (new, trip_id, ver, TENANT, int(r.get("seq") or 0), r.get("kind") or "activity", r.get("title") or "",
                             place_id, r.get("starts_at"), r.get("ends_at"), bool(r.get("locked")), rep_new, json.dumps(detail)))
        # 대화 줄 · 그 줄의 Case · 기다리던 Case
        case_map: dict[str, UUID] = {}
        cases = {str(c["case_id"]): c for c in rows.get("case", [])}
        # 다시 만든 기록(Case 상태 · 보류 제안 안) 속 원래 id → 시험 DB 의 새 id(여행 · 항목 · 여행에 묶인 장소 · Case)
        remap = {orig_trip: str(trip_id), **item_map, **{k: str(v) for k, v in place_map.items()}}
        remap.update({old: str(_uid(ns, f"case:{old}")) for old in cases})

        def swap(obj: Any) -> Any:
            text = json.dumps(obj, ensure_ascii=False)
            for old, new in remap.items():
                if old and old != new and old in text:
                    text = text.replace(old, new)
            return json.loads(text)

        def case_uuid(old: str) -> UUID:
            if old not in case_map:
                case_map[old] = _uid(ns, f"case:{old}")
                c = cases.get(old) or {}
                state, status, owner = _fold_state(c, raw.events.get(old, []) if raw else [], start_at)
                state = swap(state)
                state["trip_message"] = {"trip_id": str(trip_id), "request_id": f"seed-{old[:8]}"}
                state["replay_reconstructed"] = True
                cur.execute("INSERT INTO customer_cases (case_id, tenant_id, customer_id, status, subject, state_json, intent, issue_code, "
                            "owner_team_id, version, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,1,"
                            "COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
                            (case_map[old], TENANT, customer_id, status, "(재생 시험 시작 상태)", json.dumps(state), c.get("intent"),
                             c.get("issue_code"), owner, c.get("created_at"), c.get("created_at")))
            return case_map[old]

        turns = [t for t in rows.get("chat", []) if (parse_dt(t.get("created_at")) or start_at) < start_at] if start_at else []
        for t in sorted(turns, key=lambda x: int(x.get("turn_id") or 0)):
            cid = case_uuid(str(t["case_id"])) if t.get("case_id") else None
            cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text, case_id, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                        (TENANT, trip_id, t["role"], t["text"], cid, t.get("created_at")))
        if not turns and (seed.get("prior_turns") or ep["start"].get("prior_turns")):
            prior = seed.get("prior_turns") or []
            for j, t in enumerate(prior):
                # 표적 에피소드의 앞 대화에는 시각이 없다 — 지금 시각 바로 앞 몇 분으로 둔다(대화 순서만 맞으면 된다)
                at = t.get("at") or (start_at - timedelta(minutes=len(prior) - j)).isoformat()
                cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text, created_at) VALUES (%s,%s,%s,%s,%s)",
                            (TENANT, trip_id, "assistant" if t.get("role") in ("assistant", "bot") else "customer",
                             t.get("text") or "", at))
        waiting = 0
        for old, c in cases.items():
            created = parse_dt(c.get("created_at"))
            if created is None or start_at is None or created >= start_at:
                continue
            _, status, _ = _fold_state(c, raw.events.get(old, []) if raw else [], start_at)
            if status == "waiting_input":
                case_uuid(old)
                waiting += 1
        if waiting:
            notes.append(f"기다리던 Case {waiting}개 재구성")
        # 보류 제안
        opened = 0
        for p in rows.get("pending", []):
            created = parse_dt(p.get("created_at"))
            decided = parse_dt(p.get("decided_at"))
            if created is None or start_at is None or created >= start_at or (decided is not None and decided < start_at):
                continue
            if int(p.get("base_version") or 0) > start_version:
                continue
            old_item = str(p.get("item_id"))
            cur.execute("INSERT INTO pending_changes (proposal_id, tenant_id, trip_id, item_id, base_version, reason, protected_by, safety, "
                        "cause_json, options_json, status, expires_at, created_at, proposal_scope) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,'open',%s,%s,%s)",
                        (_uid(ns, f"pending:{p.get('proposal_id')}"), TENANT, trip_id, item_map.get(old_item, str(_uid(ns, f"item:{old_item}"))),
                         int(p.get("base_version") or start_version), p.get("reason") or "other_options", p.get("protected_by"),
                         bool(p.get("safety")), json.dumps(swap(p.get("cause_json") or [])), json.dumps(swap(p.get("options_json") or [])),
                         p.get("expires_at"), p.get("created_at"), p.get("proposal_scope") or "change"))
            opened += 1
        if opened:
            notes.append(f"열린 보류 제안 {opened}개")
        g = [x for x in rows.get("guardian", []) if (parse_dt(x.get("created_at") or x.get("at")) or start_at) < start_at] if start_at else []
        if g:
            notes.append("항로 지킴이 설정은 넣지 않음(사본 모양 확인 전)")
    if out.place_placeholders:
        notes.append(f"장소 자료 없음 {out.place_placeholders}곳 — 이름만 넣음")
    conn.commit()
    return out


def _item_from_start(i: dict) -> dict:
    return {"item_id": i.get("item_id") or str(uuid4()), "seq": i.get("seq"), "kind": i.get("kind"), "title": i.get("title"),
            "place_id": i.get("place_id"), "place_name": i.get("place") or None, "starts_at": i.get("start"), "ends_at": i.get("end"),
            "locked": bool(i.get("pinned")), "replaces_item_id": None, "indoor": i.get("indoor"),
            "detail": {"customer_pinned": True} if i.get("pinned") else {}}


def read_view(conn, trip_id: UUID, item_map_rev: dict[str, str] | None = None):
    """시험 DB 의 지금 판 → `TripView`(계보 · 장소 이름 포함). `item_map_rev` — 새 id → 원래 id(시작 판 항목과 맞추려고)."""
    from .state import Item, TripView

    rev = item_map_rev or {}
    with conn.cursor() as cur:
        cur.execute("SELECT title, latest_version FROM trips WHERE trip_id=%s", (trip_id,))
        title, version = cur.fetchone()
        cur.execute("SELECT i.item_id, i.replaces_item_id FROM itinerary_items i WHERE i.trip_id=%s", (trip_id,))
        lineage = {rev.get(str(a), str(a)): rev.get(str(b), str(b)) for a, b in cur.fetchall() if b}
        cur.execute("SELECT i.item_id, i.seq, i.kind, i.title, p.name, i.starts_at, i.ends_at, i.locked, i.detail, i.replaces_item_id, "
                    "i.place_id, p.weather_sensitive, p.attributes FROM itinerary_items i LEFT JOIN places p ON p.place_id=i.place_id "
                    "WHERE i.trip_id=%s AND i.version=%s ORDER BY i.seq", (trip_id, version))
        items = []
        for (iid, seq, kind, ititle, pname, s, e, locked, detail, rep, pid, ws, attrs) in cur.fetchall():
            detail = detail or {}
            indoor = detail.get("replay_indoor")
            if indoor is None and isinstance(attrs, dict) and isinstance(attrs.get("indoor"), bool):
                indoor = attrs["indoor"]
            items.append(Item(item_id=rev.get(str(iid), str(iid)), seq=seq, kind=kind, title=ititle, place=pname, start=s, end=e,
                              pinned=bool(locked or detail.get("customer_pinned")), indoor=indoor,
                              replaces=rev.get(str(rep), str(rep)) if rep else None, place_id=str(pid) if pid else None))
    return TripView(version=int(version), items=items, title=title, lineage=lineage)
