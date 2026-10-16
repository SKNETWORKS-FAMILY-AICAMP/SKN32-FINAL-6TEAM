"""Stage a generated first plan in its existing intake, without registering a trip."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo

from . import pipeline
from .assemble import collect, effective


KST = ZoneInfo("Asia/Seoul")


def _at(value: Any) -> datetime:
    try:
        found = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise pipeline.IntakeRejected("generated_invalid_time", "생성한 일정의 날짜와 시각을 확인하지 못했어요.") from None
    return (found if found.tzinfo is not None else found.replace(tzinfo=KST)).astimezone(KST)


def _place(value: dict, kind: str) -> dict:
    attrs = deepcopy(value.get("attributes") or {})
    source = value.get("source") or attrs.get("source") or "places"
    content_id = value.get("content_id") or attrs.get("source_content_id") or attrs.get("license_mgt_no")
    content_type = value.get("content_type_id") or attrs.get("source_content_type_id")
    got = {"name": value["name"], "kind": value.get("kind") or kind,
           "latitude": value["lat"], "longitude": value["lon"], "source": source, "attributes": attrs}
    if content_id is not None:
        got["content_id"] = str(content_id)
    if content_type is not None:
        got["content_type_id"] = str(content_type)
    if attrs.get("dining_place_uid") is not None:
        got["dining_place_uid"] = str(attrs["dining_place_uid"])
    if attrs.get("address"):
        got["address"] = attrs["address"]
    if attrs.get("pick_origin"):
        got["origin"] = attrs["pick_origin"]
    if value.get("place_id"):
        # A planner key is not a registered place_id. Copy only an explicit ID.
        got["place_id"] = str(value["place_id"])
    known_hours = {name: deepcopy(attrs[name]) for name in ("hours", "hours_week", "hours_read", "break")
                   if name in attrs}
    if known_hours:
        got["_hours"] = known_hours
    if "weather_sensitive" in value:
        got["weather_sensitive"] = value["weather_sensitive"]
    return got


def build_rows(body: dict) -> list[dict]:
    """Project the planner's structured body to claims; never parse generated prose.

    Existing intake collection does not support arbitrary cross-day activity or
    meal ends. Reject them explicitly instead of losing their end date. Mobility
    is recalculated by the existing review engine from the staged place/time facts.
    """
    digest = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    places = {place["key"]: place for place in body.get("places", [])}
    rows: list[dict] = []

    def add(field, value, path, *, line=None, method="rule"):
        evidence = {"source": "planner_generated", "how": "structured_generated", "body_hash": digest, "path": path}
        if line is not None:
            evidence["line"] = line
        rows.append({"field": field, "value": deepcopy(value), "method": method, "evidence": evidence,
                     "needs_review": False, "note": None})

    if body.get("title"):
        add("trip.title", body["title"], "/title")
    if body.get("party_size") is not None:
        add("trip.party_size", body["party_size"], "/party_size")
    if "constraints" in body:
        add("trip.constraints", body["constraints"], "/constraints")
    first_day = None
    index = 0
    for original_index, item in enumerate(body.get("items", [])):
        if item["kind"] == "mobility":
            continue
        if item["kind"] not in {"activity", "dining"}:
            raise pipeline.IntakeRejected("generated_kind_unsupported", "이 종류의 생성 일정은 확인 화면에 아직 넣을 수 없어요.")
        start = _at(item["starts_at"])
        end = _at(item["ends_at"]) if item.get("ends_at") is not None else None
        if end is not None and end.date() != start.date():
            raise pipeline.IntakeRejected("generated_cross_day_unsupported", "자정을 넘는 생성 일정은 일반 일정 입력에서 확인해 주세요.")
        if end is not None and end <= start:
            raise pipeline.IntakeRejected("generated_invalid_time", "생성한 일정의 끝은 시작보다 늦어야 해요.")
        place = places.get(item.get("place"))
        if place is None:
            raise pipeline.IntakeRejected("generated_place_missing", "생성한 일정의 실제 장소를 확인하지 못했어요.")
        path = f"/items/{original_index}"
        prefix = f"items[{index}]"
        line = index + 1
        for name, value in (("title", item["title"]), ("kind", item["kind"]), ("date", start.date().isoformat()),
                            ("starts_at", start.strftime("%H:%M"))):
            add(prefix + "." + name, value, path + ("/starts_at" if name == "date" else "/" + name), line=line)
        if end is not None:
            add(prefix + ".ends_at", end.strftime("%H:%M"), path + "/ends_at", line=line)
            add(prefix + ".end_date", end.date().isoformat(), path + "/ends_at", line=line)
        add(prefix + ".place", _place(place, item["kind"]), path + "/place", line=line, method="lookup")
        if (item.get("detail") or {}).get("customer_pinned") is True or item.get("locked") is True:
            add(prefix + ".locked", True, path + "/detail/customer_pinned", line=line)
        first_day = min(first_day, start.date()) if first_day is not None else start.date()
        index += 1
    if not index:
        raise pipeline.IntakeRejected("generated_no_items", "생성한 일정에 식사나 활동 항목이 없어요.")
    add("trip.first_day", first_day.isoformat(), "/items")
    return rows


def _transcript(rows: list[dict]) -> str:
    items: dict[int, dict] = {}
    for row in rows:
        if row["field"].startswith("items["):
            index = int(row["field"].split("[", 1)[1].split("]", 1)[0])
            items.setdefault(index, {})[row["field"].split("].", 1)[1]] = row["value"]
    return "\n".join(f"{item['date']} {item['starts_at']}–{item.get('ends_at') or '?'} "
                     + " ".join(item["title"].split()) for item in items.values())


def stage_generated(conn, *, tenant_id, customer_id, intake_id, revision: int, body: dict) -> dict:
    """Lock the owned, empty initial intake and return its fully reviewed next revision."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision, reopen_trip_id, trip_id FROM trip_intakes "
                    "WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, intake_id, customer_id))
        owner = cur.fetchone()
        if owner is None:
            raise LookupError("intake")
        status, current, reopened, registered = owner
        if status != "review" or registered is not None:
            raise pipeline.IntakeConflict("intake_not_editable", "지금은 생성한 초안을 넣을 수 없는 접수예요.", status=status)
        if current != revision:
            raise pipeline.IntakeConflict("stale_revision", "그 사이 일정이 바뀌었어요. 새로 불러와 주세요.", current_revision=current)
        if reopened is not None:
            raise pipeline.IntakeConflict("intake_reopened", "등록한 여행에서는 최초 일정을 새로 만들 수 없어요.")
        sources = pipeline._sources(conn, tenant_id, intake_id)
        claims = pipeline._claims(conn, tenant_id, intake_id, current)
        if collect(sources=sources, claims=claims).rows:
            raise pipeline.IntakeConflict("intake_has_items", "이미 읽은 일정이 있어요. 기존 일정을 확인하거나 수정해 주세요.")
        rows = build_rows(body)
        existing_trip = {claim["field"]: claim for claim in effective(claims) if claim["field"].startswith("trip.")}
        rows = [row for row in rows if not (row["field"] != "trip.constraints" and row["field"] in existing_trip
                                           and existing_trip[row["field"]].get("value") is not None)]
        transcript = _transcript(rows)
        raw = transcript.encode()
        position = max((source["position"] for source in sources), default=-1) + 1
        cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, transcript) "
                    "VALUES (%s,%s,%s,'chat',%s,%s,%s) RETURNING source_id",
                    (intake_id, tenant_id, position, hashlib.sha256(raw).hexdigest(), len(raw), transcript))
        source_id = cur.fetchone()[0]
        new = current + 1
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, "
                    "evidence, needs_review, note, created_at) SELECT intake_id, tenant_id, %s, source_id, field, "
                    "value_json, method, evidence, needs_review, note, created_at FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s", (new, tenant_id, intake_id, current))
        for row in rows:
            evidence = {**row["evidence"], "source_id": str(source_id)}
            cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, "
                        "method, evidence, needs_review, note, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,false,NULL,clock_timestamp())",
                        (intake_id, tenant_id, new, source_id, row["field"], json.dumps(row["value"], ensure_ascii=False),
                         row["method"], json.dumps(evidence, ensure_ascii=False)))
        cur.execute("UPDATE trip_intakes SET revision=%s, stage='review', updated_at=now() "
                    "WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s AND revision=%s",
                    (new, tenant_id, intake_id, customer_id, current))
        if cur.rowcount != 1:
            raise pipeline.IntakeConflict("stale_revision", "그 사이 일정이 바뀌었어요. 새로 불러와 주세요.")
        found, error = pipeline._review_of(conn, tenant_id, intake_id, new, pipeline._sources(conn, tenant_id, intake_id),
                                           effective(pipeline._claims(conn, tenant_id, intake_id, new)), force=True)
        if found is None:
            raise pipeline.IntakeConflict("schedule_check_failed", "생성한 일정의 검사를 끝내지 못해 저장하지 않았어요.", reason=error)
        result = pipeline.view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
        if result is None:
            raise LookupError("intake")
        return result


__all__ = ["build_rows", "stage_generated"]
