# -*- coding: utf-8 -*-
"""요식 판정 에이전트의 도구 — **읽기 전용**. 규칙 도구는 판정까지 계산해 돌려주고, 자료 도구는 사실 · 원문을 돌려준다. `[2026-10-13 · 설계 §5]`

★LLM은 지휘하고 규칙은 도구다(설계 §3). 규칙 도구의 판정은 **지금 규칙 판정과 같은 함수**(원장 SQL `open_at_slot` · `is_closed_on` ·
  `attribute_state` …)다 — 그래서 에이전트 결과와 규칙 결과가 다르면 원인은 「무엇을 골랐나 · 원문 해석 · 출처 충돌 판단」뿐이다.
★「원장 먼저, 없으면 지도」 순서는 `find_place` **안의 코드**가 지킨다 — LLM에게 순서를 맡기지 않는다.
★호출마다 id(`c1` …)를 붙이고 결과를 남긴다(`calls`) — 근거 검증(§6)이 「인용한 값이 그 호출 결과에 그대로 있나」를 본다.
★상한 — 한 번의 판정에서 실제 조회 `max_calls` 회. 같은 도구 · 같은 인자의 확인 결과는 원 call_id로 재사용한다.
★바깥 API(카카오 · 구글)는 부르는 쪽이 넣는다(`kakao` · `google`, 예산 장치를 가진 어댑터). 없으면 그 도구는 「unknown(설정 없음)」 —
  지어내지 않는다. 카카오 결과는 저장하지 않고, 구글은 place_id 와 판정만 쓴다(약관 — 원문을 돌려주지 않는다).
★이 파일은 코어를 import 하지 않는다(팀 경계 — `ledger.py` 와 같다). DB 연결은 `connect()` 가 연다.
"""
from __future__ import annotations

import json
from copy import deepcopy
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from app.domains.travel_ops.instances.dining.ledger import (DEFAULT_ORDER_MARGIN_MIN, _as_datetime, find_license_shop_by_name,
                                                            find_place_by_name, find_place_inside_name)

KST = timezone(timedelta(hours=9))
#: 판정 한 번의 도구 호출 상한 — 설계 §4 「식사 항목당 8회」 × 식사 넷 안팎
DEFAULT_MAX_CALLS = 40
#: 근처 찾기 반경 상한(m) — 걸어서 15분 안팎
NEARBY_MAX_M = 1500
#: 속성 — 에이전트가 쓰는 말 → 원장 속성 코드
ATTRIBUTES = {"halal": "halal", "vegetarian": "vegetarian_menu", "kids": "kids_allowed", "card": "card_payment",
              "parking": "parking", "takeout": "takeout"}
FOOD_GROUPS = ("FD6", "CE7")


class ToolRefused(Exception):
    """상한 · 반복 · 모르는 도구 · 인자 오류 — 결과 대신 이유를 돌려준다."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: str                       # rule(판정을 돌려준다) · data(사실 · 원문을 돌려준다)
    description: str
    parameters: dict[str, Any]      # JSON 스키마(OpenAI 함수 · FastMCP 둘 다 이것으로)


def _obj(required: list[str], **props: Any) -> dict[str, Any]:
    return {"type": "object", "required": required, "properties": props, "additionalProperties": False}


_STR = {"type": "string"}
_NUM = {"type": "number"}
_UID = {"type": "string", "description": "원장 가게 번호(find_place 결과의 place_uid)"}
_AT = {"type": "string", "description": "ISO 시각(서울), 예 2026-10-21T12:00"}

SPECS: dict[str, ToolSpec] = {s.name: s for s in [
    ToolSpec("find_place", "rule",
             "식당을 이름으로 특정한다. 원장(요식 DB)에서 먼저 찾고, 없으면 안에서 지도(카카오)로 한 번 더 찾는다. "
             "match(exact · branch · prefix · typo · dish · license · map)와 needs_review 를 같이 돌려준다. "
             "verdict = ok(하나로 정해짐) · unknown(찾았지만 확인 필요) · bad(못 찾음).",
             _obj(["name"], name=_STR, lat=_NUM, lng=_NUM)),
    ToolSpec("check_open_at", "rule",
             "그 시각에 영업하나(원장 판정 — 휴무 · 브레이크 · 자정 넘김 · 폐업 포함) · 라스트오더(도착+20분이 라스트오더를 넘으면 bad, "
             "종료 60분 안이면 경고) · 명절 맥락. verdict = ok · bad · unknown.",
             _obj(["place_uid", "start"], place_uid=_UID, start=_AT, end=_AT)),
    ToolSpec("check_closed_day", "rule", "그 날짜가 정기 · 임시 휴무인가와 걸린 휴무 규칙 원문. verdict = ok(안 쉰다) · bad(쉰다) · unknown.",
             _obj(["place_uid", "date"], place_uid=_UID, date={"type": "string", "description": "YYYY-MM-DD"})),
    ToolSpec("check_business", "rule", "폐업 · 이전 · 상호 변경 상태(원장 기록 · 폐업 대조).", _obj(["place_uid"], place_uid=_UID)),
    ToolSpec("check_attributes", "rule",
             "가게 속성을 원장에서 읽는다 — 속성마다 yes · limited · no · unknown 과 출처 원문 · 확인일. "
             f"wanted 는 {sorted(ATTRIBUTES)} 중에서. "
             "고객이 요청한 조건(결제 · 아이 · 식이)은 그 조건이 적용되는 식사마다 반드시 이 도구로 확인한다. "
             "고객이 말하지 않은 조건만 확인하지 않는다.",
             _obj(["place_uid", "wanted"], place_uid=_UID,
                  wanted={"type": "array", "items": {"type": "string", "enum": sorted(ATTRIBUTES)}})),
    ToolSpec("live_open_check", "rule",
             "구글로 그 시각 영업을 실시간 확인한다(호출 비용이 든다 — 원장이 unknown 이거나, 출처가 어긋나거나, 원장 밖 가게일 때만). "
             "원장 가게는 place_uid, 원장 밖 가게(find_place 의 place_uid 가 null · source 가 license · map)는 "
             "find_call_id(그 find_place 의 call_id)로 준다. verdict = open · closed · unknown.",
             _obj(["start"], place_uid=_UID,
                  find_call_id={"type": "string", "description": "원장 밖 가게를 찾은 find_place 의 call_id"},
                  start=_AT, end=_AT)),
    ToolSpec("place_detail", "data",
             "가게의 분류 · 음식 결 · 주소와 **영업시간 · 휴무 원문**(규칙으로 옮기기 전 글) · 그날 규칙화된 영업 구간. 규칙 도구가 unknown 일 때 직접 읽는다.",
             _obj(["place_uid"], place_uid=_UID, date={"type": "string", "description": "YYYY-MM-DD(그날 영업 구간을 볼 때)"})),
    ToolSpec("nearby_places", "data", "좌표 근처의 원장 식당(가까운 순) — 거리 · 분류 · 결.",
             _obj(["lat", "lng"], lat=_NUM, lng=_NUM, radius_m={"type": "integer", "maximum": NEARBY_MAX_M},
                  style=_STR, limit={"type": "integer", "maximum": 15})),
    ToolSpec("map_search", "data", "지도(카카오) 검색 — 이름 · 분류 · 좌표 · 주소. 원장에서 못 찾았을 때 **다른 말로 다시 찾기**용. 결과는 저장하지 않는다.",
             _obj(["query"], query=_STR, lat=_NUM, lng=_NUM)),
]}


def _kst(value: Any) -> datetime:
    got = _as_datetime(value)
    if got is None:
        raise ToolRefused(f"시각을 읽지 못했다: {value!r}")
    return got.astimezone(KST)


def _day(value: Any) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ToolRefused(f"날짜를 읽지 못했다: {value!r}") from exc


def _hm(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    return f"{int(minutes) // 60 % 24:02d}:{int(minutes) % 60:02d}"


def _plain(value: Any) -> Any:
    """JSON 으로 옮길 수 있는 값 — 날짜 · UUID 는 글자로."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def scope_key(name: Any) -> str:
    """장소 이름 비교용 — 띄어쓰기 · 대소문자를 무시한다."""
    return "".join(str(name or "").split()).lower()


def _reusable(result: dict[str, Any]) -> bool:
    """확인된 반환값만 재사용한다. 미확인·오류는 새 조회로 확인할 여지를 남긴다."""
    if any(result.get(key) for key in ("refused", "error", "failure")):
        return False
    if result.get("verdict") == "unknown" or result.get("found") is False:
        return False
    if any(key in result and not result[key] for key in ("hits", "places", "attributes")):
        return False
    if "verdict" not in result and result.get("reason"):
        return False
    attributes = result.get("attributes")
    if isinstance(attributes, dict) and any(a.get("state") not in ("yes", "limited", "no") for a in attributes.values()):
        return False
    return True


@dataclass
class DiningTools:
    """한 번의 판정 동안 쓰는 도구 묶음. `connect()` 는 DB 연결을 여는 컨텍스트 관리자를 돌려준다."""

    connect: Callable[[], AbstractContextManager[Any]]
    kakao: Any = None
    google: Any = None
    max_calls: int = DEFAULT_MAX_CALLS
    #: 이 판정에서 쓸 수 있는 도구(없으면 전부) — 비교 실험 A(「LLM 직접」)는 규칙 도구를 빼고 자료 도구만 준다(설계 §7)
    allowed: frozenset[str] | None = None
    #: `[2026-10-20]` 식사가 아닌 일정 항목의 장소 이름(띄어쓰기 · 대소문자 무시) — 이 이름으로 찾기를 부르면 거절한다(`agent.off_scope_names`)
    off_scope: frozenset[str] = frozenset()
    calls: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    reused: list[dict[str, str]] = field(default_factory=list)

    # ── 부르는 문 하나 ──
    def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """도구를 부른다. 결과에 `call_id` 를 붙여 돌려준다. 거절이면 `{"refused": 이유}` — 예외를 올리지 않는다(에이전트가 읽고 고친다)."""
        args = deepcopy(dict(args or {}))
        try:
            if name not in SPECS:
                raise ToolRefused(f"모르는 도구: {name}")
            if self.allowed is not None and name not in self.allowed:
                raise ToolRefused(f"이 판정에서 쓸 수 없는 도구: {name}")
            query = args.get("name") if name == "find_place" else args.get("query") if name == "map_search" else None
            if query is not None and scope_key(query) in self.off_scope:
                # ☆`[2026-10-19 실측]` 활동 장소(경복궁)를 식당처럼 찾고 영업 · 휴무 · 폐업 도구까지 불렀다(gpt-4o-mini 개발용 18/240판)
                raise ToolRefused(f"「{query}」는 식사가 아닌 일정 항목의 장소다 — 식사 항목의 가게만 찾는다")
            key = (name, json.dumps(args, sort_keys=True, ensure_ascii=False))
            previous = next((c for c in reversed(self.calls)
                             if (c["tool"], json.dumps(c["args"], sort_keys=True, ensure_ascii=False)) == key
                             and _reusable(c["result"])), None)
            if previous is not None:
                self.reused.append({"tool": name, "call_id": previous["id"]})
                return {"call_id": previous["id"], **deepcopy(previous["result"]), "reused": True}
            if len(self.calls) >= self.max_calls:
                raise ToolRefused(f"도구 호출 상한({self.max_calls}회)을 넘었다")
            missing = [p for p in SPECS[name].parameters["required"] if args.get(p) in (None, "", [])]
            if missing:
                raise ToolRefused(f"필수 인자가 없다: {missing}")
            # ★`[2026-10-16 luna 실측]` 모델이 가게 번호의 한 칸을 빼고 넘겨 SQL 이 uuid 오류를 냈고 그날 판정이 통째로 사라졌다(3번 중 2번).
            #   DB 에 보내기 전에 거절로 돌려준다 — 모델이 읽고 find_place 결과의 번호를 다시 옮긴다
            if "place_uid" in args:
                try:
                    UUID(str(args["place_uid"]))
                except ValueError:
                    raise ToolRefused(f"place_uid 형식이 아니다: {args['place_uid']!r} — find_place 결과의 place_uid 를 그대로 옮긴다") from None
            result = _plain(getattr(self, f"_{name}")(**deepcopy(args)))
        except ToolRefused as exc:
            self.refused.append({"tool": name, "args": args, "why": str(exc)})
            return {"refused": str(exc)}
        except TypeError as exc:                     # 모르는 인자
            self.refused.append({"tool": name, "args": args, "why": f"인자 오류: {exc}"})
            return {"refused": f"인자 오류: {exc}"}
        call_id = f"c{len(self.calls) + 1}"
        self.calls.append({"id": call_id, "tool": name, "args": args, "result": result})
        return {"call_id": call_id, **deepcopy(result)}

    def result_of(self, call_id: str) -> dict[str, Any] | None:
        return deepcopy(next((c["result"] for c in self.calls if c["id"] == call_id), None))

    # ── 규칙 도구 ──
    def _find_place(self, name: str, lat: float | None = None, lng: float | None = None) -> dict[str, Any]:
        """★규칙 도구는 모두 `verdict` 를 낸다 — 찾음(확정) ok · 찾았지만 확인 필요 unknown · 못 찾음 bad.
        ☆`[2026-10-13 실측]` 이 칸이 없을 때 gpt-4o-mini 가 `verdict: ok` 를 근거로 지어 적었다(검증기가 거절)."""
        got = self._find(name, lat, lng)
        if not got["found"]:
            verdict, reason = "bad", got["reason"]
        elif got["needs_review"]:
            verdict, reason = "unknown", got.get("note") or "찾았지만 같은 가게인지 확인이 필요하다"
        else:
            verdict, reason = "ok", "원장에서 같은 이름의 가게 하나로 정해졌다"
        return {"verdict": verdict, **got, "reason": reason}

    def _find(self, name: str, lat: float | None, lng: float | None) -> dict[str, Any]:
        near = (float(lat), float(lng)) if lat is not None and lng is not None else None
        with self.connect() as conn:
            found = find_place_by_name(conn, name, near=near)
            if found is None and near is not None:
                # ★`[2026-10-15]` 「광화문 미진」 — 원장은 「미진」. 이름 단계가 못 맞추면 준 좌표(그 항목 장소) 100m 안에서 이름 안의 원장 가게를 본다
                found = find_place_inside_name(conn, name, near)
            if found is not None:
                return {"found": True, "source": "ledger", "place_uid": found.get("dining_place_uid"),
                        "name": found["matched_title"], "address": found.get("address"),
                        "lat": found["latitude"], "lng": found["longitude"], "category": found.get("category"),
                        "match": found["match"], "needs_review": bool(found.get("needs_review")),
                        "others": found.get("others", 0), "note": found.get("note")}
            license_shop = find_license_shop_by_name(conn, name, near=near)
        if license_shop is not None:
            # ★인허가 가게는 영업시간을 모른다 — 판정 도구에 넣을 place_uid 가 없다
            return {"found": True, "source": "license", "place_uid": None, "name": license_shop["matched_title"],
                    "address": license_shop["address"], "lat": license_shop["latitude"], "lng": license_shop["longitude"],
                    "category": license_shop.get("category"), "match": "license", "needs_review": True,
                    "note": "원장에 없고 인허가 기록에만 있다 — 영업은 live_open_check(find_call_id)로 확인한다"}
        hits = self._map(name, near)
        if hits is None:
            return {"found": False, "source": None, "reason": "원장에 없고 지도 검색을 부를 수 없다(설정 · 예산)"}
        if not hits:
            return {"found": False, "source": None, "reason": "원장 · 지도 모두 없다"}
        top = hits[0]
        return {"found": True, "source": "map", "place_uid": None, "map_id": top["map_id"], "name": top["name"],
                "address": top["address"], "lat": top["lat"], "lng": top["lng"], "category": top["category"],
                "match": "map", "needs_review": True, "others": len(hits) - 1,
                "note": "원장에 없다 — 지도 결과라 영업은 live_open_check(find_call_id)로 확인한다"}

    def _check_open_at(self, place_uid: str, start: str, end: str | None = None) -> dict[str, Any]:
        at = _kst(start)
        until = _kst(end) if end else None
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT dining.open_at_slot(%s::uuid, %s, %s), dining.needs_last_order_check(%s::uuid, %s, %s), "
                        "dining.holiday_context(%s::uuid, %s)", (place_uid, at, until, place_uid, at, until, place_uid, at))
            open_at, needs_check, holiday = cur.fetchone()
            order_ok = None
            if open_at is True:
                cur.execute("SELECT dining.open_at_slot(%s::uuid, %s, %s)",
                            (place_uid, at + timedelta(minutes=DEFAULT_ORDER_MARGIN_MIN), until))
                order_ok = cur.fetchone()[0]
        if open_at is False:
            verdict, reason = "bad", "그 시각에 영업하지 않는다(휴무 · 브레이크 · 영업시간 밖 · 폐업)"
        elif open_at is None:
            verdict, reason = "unknown", "원장에 그날 영업 규칙이 없다"
        elif order_ok is False:
            verdict, reason = "bad", f"도착 {DEFAULT_ORDER_MARGIN_MIN}분 뒤가 라스트오더를 넘는다 — 주문할 여유가 없다"
        else:
            verdict, reason = "ok", "그 시각에 영업한다" + (" — 단 마감이 가까워 라스트오더 확인이 필요하다" if needs_check else "")
        return {"verdict": verdict, "reason": reason, "open_at_slot": open_at, "order_ok": order_ok,
                "last_order_warning": bool(needs_check), "holiday_context": holiday}

    def _check_closed_day(self, place_uid: str, date: str) -> dict[str, Any]:  # noqa: A002 — 도구 인자 이름
        day = _day(date)
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT dining.is_closed_on(%s::uuid, %s), dining.closure_state(%s::uuid)", (place_uid, day, place_uid))
            closed, coverage = cur.fetchone()
            # ★`is_closed_on` 은 규칙이 하나도 없어도 거짓이다 — 「안 쉰다」는 휴무 정보가 있거나(present) 「정기 휴무 없음」을 확인했을(none) 때만.
            #   아니면 모름이다(모름을 없음으로 바꾸지 않는다 — `closure_state` 210)
            if closed is False and coverage not in ("present", "none"):
                closed = None
            cur.execute("SELECT pattern_kind, weekday, nth, holiday_name, closed_date, source_text "
                        "FROM dining.v_closure_rule_active WHERE place_uid = %s::uuid ORDER BY closure_id", (place_uid,))
            rules = []
            for k, w, n, h, d, t in cur.fetchall():          # 출처 여럿이 같은 규칙을 말하면 하나로
                rule = {"pattern": k, "weekday": w, "nth": n, "holiday": h, "date": d, "source_text": t}
                if rule not in rules:
                    rules.append(rule)
        verdict = {True: "bad", False: "ok"}.get(closed, "unknown")
        reason = {"bad": "그날은 휴무다", "ok": "그날 휴무 규칙에 걸리지 않는다", "unknown": "휴무 규칙을 모른다"}[verdict]
        return {"verdict": verdict, "reason": reason, "closed": closed, "closure_info": coverage, "rules": rules}

    def _check_business(self, place_uid: str) -> dict[str, Any]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name_ko, record_status, dining.closure_state(place_uid), dining.needs_closure_check(place_uid) "
                        "FROM dining.dn_place WHERE place_uid = %s::uuid", (place_uid,))
            row = cur.fetchone()
        if row is None:
            return {"verdict": "unknown", "reason": "원장에 없는 가게 번호다"}
        name, status, closure, needs_check = row
        verdict = "bad" if status == "closed" else "ok"
        # ★`unknown` 은 「폐업 기록이 없다」이지 「영업을 확인했다」가 아니다 — 말을 부풀리지 않는다
        reason = {"closed": "폐업으로 기록됐다", "active": "영업 중으로 확인돼 있다"}.get(status, "폐업 기록이 없다(영업 상태를 따로 확인하지는 않았다)")
        return {"verdict": verdict, "reason": reason,
                "name": name, "record_status": status, "closure_state": closure, "needs_closure_check": needs_check}

    def _check_attributes(self, place_uid: str, wanted: list[str]) -> dict[str, Any]:
        unknown = [w for w in wanted if w not in ATTRIBUTES]
        if unknown:
            raise ToolRefused(f"모르는 속성: {unknown} — {sorted(ATTRIBUTES)} 중에서")
        out: dict[str, Any] = {}
        with self.connect() as conn, conn.cursor() as cur:
            for word in wanted:
                code = ATTRIBUTES[word]
                cur.execute("SELECT dining.attribute_state(%s::uuid, %s)", (place_uid, code))
                state = cur.fetchone()[0]
                cur.execute("SELECT value_state, source_text, source_code, verified_at FROM dining.v_attribute_active "
                            "WHERE place_uid = %s::uuid AND attr_code = %s ORDER BY verified_at DESC NULLS LAST LIMIT 1",
                            (place_uid, code))
                row = cur.fetchone()
                out[word] = {"state": state or "unknown", "source_text": row[1] if row else None,
                             "source": row[2] if row else None, "verified_at": row[3] if row else None}
        return {"attributes": out}

    def _live_open_check(self, start: str, end: str | None = None, place_uid: str | None = None,
                         find_call_id: str | None = None) -> dict[str, Any]:
        """★`[2026-10-21]` 원장 밖 가게(인허가 · 카카오로 찾은 가게)는 원장 번호가 없다 — 그 `find_place` 결과의 이름 · 좌표로 구글을 찾는다.
        ☆전에는 원장 번호만 받아 그런 가게는 구글을 부를 길이 없었고 영업 줄이 늘 「확인 필요」였다(사람 정답 평가 33번)."""
        if (place_uid is None) == (find_call_id is None):
            raise ToolRefused("place_uid(원장 가게) · find_call_id(원장 밖 가게) 중 하나만 준다")
        source = "ledger"
        if find_call_id is not None:
            spot = self._outside_spot(find_call_id)
            source = spot[3]
        if self.google is None:
            return {"verdict": "unknown", "reason": "실시간 확인(구글)이 설정되지 않았다"}
        at = _kst(start)
        until = _kst(end) if end else at + timedelta(hours=1)
        if find_call_id is not None:
            row = spot[:3]
        else:
            with self.connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT name_ko, lat, lng FROM dining.dn_place WHERE place_uid = %s::uuid", (place_uid,))
                row = cur.fetchone()
            if row is None or row[1] is None:
                return {"verdict": "unknown", "reason": "원장에 없거나 좌표가 없다"}
        found = self.google.find_place_id(name=row[0], latitude=float(row[1]), longitude=float(row[2]))
        if found is None:
            return {"verdict": "unknown", "reason": "구글을 부르지 못했다(예산 · 오류)"}
        if found == "unmatched":
            return {"verdict": "unknown", "reason": "구글에서 같은 가게를 찾지 못했다"}
        google_id, metres = found
        got = self.google.open_verdict(google_id, start=at, end=until)
        if got is None:
            return {"verdict": "unknown", "reason": "구글 영업 정보를 부르지 못했다", "google_place_id": google_id}
        verdict, why = got
        return {"verdict": verdict, "reason": why, "google_place_id": google_id, "match_distance_m": round(metres),
                "place_source": source}

    def _outside_spot(self, find_call_id: str) -> tuple[str, float, float, str]:
        """원장 밖 가게를 찾은 `find_place` 호출 → (이름, 위도, 경도, 출처). 모델이 이름 · 좌표를 적어 넘기지 않게 기록에서 꺼낸다."""
        call = next((c for c in self.calls if c["id"] == find_call_id), None)
        if call is None or call["tool"] != "find_place":
            raise ToolRefused(f"{find_call_id} 는 find_place 호출이 아니다 — 가게를 찾은 find_place 의 call_id 를 준다")
        got = call["result"]
        if not got.get("found") or got.get("source") not in ("license", "map"):
            raise ToolRefused("원장 밖에서 찾은 가게가 아니다 — 원장 가게는 place_uid 로 확인한다")
        if got.get("lat") is None or got.get("lng") is None:
            raise ToolRefused("찾은 가게에 좌표가 없다 — 구글에서 같은 가게인지 가릴 수 없다")
        return str(got.get("name") or call["args"].get("name")), float(got["lat"]), float(got["lng"]), str(got["source"])

    # ── 자료 도구 ──
    def _place_detail(self, place_uid: str, date: str | None = None) -> dict[str, Any]:  # noqa: A002
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name_ko, branch_name, coalesce(road_address, jibun_address), category, style, record_status "
                        "FROM dining.dn_place WHERE place_uid = %s::uuid", (place_uid,))
            row = cur.fetchone()
            if row is None:
                return {"found": False, "reason": "원장에 없는 가게 번호다"}
            cur.execute("SELECT DISTINCT source_text FROM dining.v_hours_rule_active "
                        "WHERE place_uid = %s::uuid AND source_text IS NOT NULL LIMIT 8", (place_uid,))
            hours_text = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT source_text FROM dining.v_closure_rule_active "
                        "WHERE place_uid = %s::uuid AND source_text IS NOT NULL LIMIT 8", (place_uid,))
            closure_text = [r[0] for r in cur.fetchall()]
            intervals = None
            if date:
                cur.execute("SELECT open_min, close_min, last_order_min FROM dining.day_intervals(%s::uuid, %s) ORDER BY seq",
                            (place_uid, _day(date)))
                intervals = [{"open": _hm(o), "close": _hm(c), "last_order": _hm(lo)} for o, c, lo in cur.fetchall()]
        name, branch, address, category, style, status = row
        return {"found": True, "name": name, "branch": branch, "address": address, "category": category, "style": style,
                "record_status": status, "hours_text": hours_text, "closure_text": closure_text,
                **({"date": date, "intervals": intervals} if date else {})}

    def _nearby_places(self, lat: float, lng: float, radius_m: int = 500, style: str | None = None,
                       limit: int = 10) -> dict[str, Any]:
        radius = max(50, min(int(radius_m), NEARBY_MAX_M))
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT place_uid::text, name_ko, category, style, dining.distance_m(lat, lng, %s, %s) AS d "
                        "FROM dining.dn_place WHERE record_status <> 'closed' AND NOT is_synthetic AND lat IS NOT NULL "
                        "  AND dining.distance_m(lat, lng, %s, %s) <= %s AND (%s::text IS NULL OR style = %s) "
                        "ORDER BY d, place_uid LIMIT %s",
                        (lat, lng, lat, lng, radius, style, style, max(1, min(int(limit), 15))))
            rows = cur.fetchall()
        return {"places": [{"place_uid": u, "name": n, "category": c, "style": s, "distance_m": round(d)} for u, n, c, s, d in rows]}

    def _map_search(self, query: str, lat: float | None = None, lng: float | None = None) -> dict[str, Any]:
        near = (float(lat), float(lng)) if lat is not None and lng is not None else None
        hits = self._map(query, near)
        if hits is None:
            return {"hits": [], "reason": "지도 검색을 부를 수 없다(설정 · 예산)"}
        return {"hits": hits}

    def _map(self, query: str, near: tuple[float, float] | None) -> list[dict[str, Any]] | None:
        if self.kakao is None:
            return None
        got = self.kakao.search(query, size=5, near=near)
        if got is None:
            return None
        return [{"map_id": h.get("id"), "name": h.get("name"), "category": h.get("category"), "address": h.get("address"),
                 "lat": h.get("latitude"), "lng": h.get("longitude")}
                for h in got if (h.get("category_group") in FOOD_GROUPS or not h.get("category_group"))]


def openai_tools(names: list[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI 함수 호출 형식의 도구 목록 — 같은 정의(`SPECS`)에서 만든다."""
    return [{"type": "function", "function": {"name": s.name, "description": s.description, "parameters": s.parameters}}
            for s in SPECS.values() if names is None or s.name in names]


def build_mcp(tools_factory: Callable[[], DiningTools]):
    """같은 도구를 FastMCP 서버로 — 내부 에이전트 · 개발 도구(MCP 클라이언트)가 쓴다. ★고객용 `/mcp/`(사용자 키)와 따로다.
    테넌트 · 연결은 서버가 넣는다(`tools_factory`) — LLM이 정하지 않는다."""
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.tools.base import Tool
    from mcp.server.fastmcp.utilities.func_metadata import func_metadata
    from mcp.types import ToolAnnotations

    class SpecTool(Tool):
        """스키마는 `SPECS` 그대로 보이고, 인자는 `DiningTools.call` 이 검사한다(함수 서명으로 스키마를 만들지 않는다 — 정의가 둘이 되지 않게)."""

        async def run(self, arguments: dict[str, Any], context: Any = None, convert_result: bool = False) -> Any:
            result = self.fn(**arguments)
            return self.fn_metadata.convert_result(result) if convert_result else result

    def _shape() -> dict[str, Any]:                    # 결과 변환용 서명(dict 하나를 돌려준다)
        return {}

    server = FastMCP("tripilot-dining-tools")
    for spec in SPECS.values():
        def handler(_name: str = spec.name, **kwargs: Any) -> dict[str, Any]:
            return tools_factory().call(_name, kwargs)

        server._tool_manager._tools[spec.name] = SpecTool(
            fn=handler, name=spec.name, description=spec.description, parameters=spec.parameters,
            fn_metadata=func_metadata(_shape), is_async=False, context_kwarg=None,
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=spec.name in ("live_open_check", "map_search")))
    return server


__all__ = ["ATTRIBUTES", "DiningTools", "SPECS", "ToolRefused", "ToolSpec", "build_mcp", "openai_tools"]
