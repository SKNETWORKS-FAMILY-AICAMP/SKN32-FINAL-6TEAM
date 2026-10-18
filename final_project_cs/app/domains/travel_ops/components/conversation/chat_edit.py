# -*- coding: utf-8 -*-
"""채팅으로 일정 고치기 — 시각 · 날짜 옮기기 · 넣기 · 빼기 · 이름 말한 곳으로 바꾸기 · 순서 바꾸기 · 고정. `[2026-10-15]`

**새 실행기를 만들지 않는다.** 웹 「일정 수정」과 같은 길을 그대로 탄다:
    다시 열기(`reopen.open_for_trip`) → 고치기(`pipeline.edit` — 장소는 이름만 주면 서버가 다시 찾는다) → 검사(`pipeline.view`)
    → 「완료」(`reopen_commit.commit` — 판정 · 새 판 · 변경 이력 · 알림 하나) → 실패하면 그 수정 접수를 닫는다(`reopen.cancel`)
`[2026-10-13 사용자 결정]` 「일정 수정은 계획 확인 단계의 기능을 그대로 쓴다 · 채팅 변경이 쓰는 반영 길을 그대로 쓴다」.

☆왜: 채팅은 이 요청들을 「아직 채팅에서 하지 못해요」로 막고 있었다(10-14 x600 재시험 — 옮기기 51건 중 40 · 넣기 8/8 · 빼기 10/11 ·
  이름 말한 곳 바꾸기는 「바로 바꾸는 기능 없어요」). 같은 일을 웹 「일정 수정」은 이미 하고 있었다. 사용자 지적(10-15):
  「고객이 원하는 걸 정확히 이야기했으면 최소한 우리 db 검색은 할 수 있는 거 아니야 … 이미 있는 기능 그냥 써서 처리해서 답 주면 되는 건데」.

★고객이 고친 것이라 「먼저 물어보기」(항로 지킴이 · D-020)를 지나지 않는다 — 웹 「일정 수정」과 같은 `customer_request` 변경이다.
  고정 · 예약 · 지난 일정 · 판정 위반은 웹과 같은 규칙으로 막고, 막힌 까닭을 그대로 답한다(지어내지 않는다).
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
log = logging.getLogger(__name__)
#: 넣을 일정의 끝을 말하지 않았을 때 머무는 시간 — ★우리가 고른 값(확인 화면의 끝 채우기와 같은 크기)
DEFAULT_STAY = timedelta(minutes=60)


@dataclass
class EditOp:
    """고칠 것 하나. `kind` = time(시각 · 날짜) · place(이름 말한 곳) · remove · add · lock · unlock."""

    kind: str
    item_id: UUID | None = None
    date: str | None = None          # YYYY-MM-DD
    starts_at: str | None = None     # HH:MM
    ends_at: str | None = None       # HH:MM
    place_name: str | None = None
    title: str | None = None
    item_kind: str | None = None     # 넣기: activity · dining
    reflow: bool = False             # 명시된 시각을 지키며 같은 날 뒤 일정을 맞춘다


class EditRefused(Exception):
    """고치지 못했다 — `code` 는 기록용, `message` 는 고객에게 그대로 보여 줄 말."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


def _hm(value: datetime) -> str:
    return value.astimezone(KST).strftime("%H:%M")


def _refusal(code: str, message: str) -> str:
    """접수 · 「완료」의 거절 → 고객 말. 웹 화면이 보이는 문장과 같은 뜻으로 쓴다."""
    if code == "place_not_found" and ("budget_exhausted" in message or "조회가 막혀" in message):
        # 찾는 쪽(관광 정보 조회)의 오늘 한도가 찼거나 막힌 것 — 없는 곳이라는 뜻이 아니다(실서버 확인 10-15: 안내가 「고객이 고친다」로 샜다)
        return "지금 장소 조회가 잠시 막혀 찾지 못해 일정은 바꾸지 않았어요. 잠시 뒤 다시 말씀해 주세요."
    if code == "place_not_found":
        return f"말씀하신 곳을 장소 목록 · 관광 정보 · 지도에서 하나로 찾지 못해 일정은 바꾸지 않았어요({message}). 장소 이름을 조금 더 정확히 알려 주세요."
    if code == "item_in_past":
        return f"이미 지난 일정은 바꿀 수 없어 일정은 바꾸지 않았어요 — {message.split(':', 1)[-1].strip()}."
    if code == "itinerary_infeasible":
        return f"그렇게 바꾸면 일정이 맞지 않아 바꾸지 않았어요 — {message.split(':', 1)[-1].strip()}"
    if code == "stale_itinerary":
        return "그 사이 일정이 바뀌어 바꾸지 않았어요. 최신 일정에서 다시 말씀해 주세요."
    if code in ("lock_with_changes", "locked_item", "item_locked"):
        return "고정한 일정이라 바꾸지 않았어요. 「○○ 고정 풀어줘」라고 먼저 말씀해 주세요."
    return f"일정을 바꾸지 못했어요 — {message}"


def run(*, store: Any, connect: Callable[[], Any], tenant: str, customer_id: UUID, trip_id: UUID, base_version: int,
        ops: list[EditOp], lookups: Callable[[], tuple[Any, Any, Any]], now: datetime,
        cause_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """고칠 것들 → 같은 여행의 새 판. `{"version", "changed", "summary", "plan"}`. 못 고치면 `EditRefused`(고객 말 포함).

    `lookups()` = (관광공사, 카카오, 요식 원장) — 웹 고치기와 같은 이름 찾기 부품(부를 때만 만든다)."""
    if not ops:
        raise EditRefused("no_edits", "무엇을 바꿀지 알아듣지 못해 일정은 바꾸지 않았어요. 바꿀 일정과 내용을 알려 주세요.")
    # ★`[2026-10-15 Codex 검토]` 한 여행의 채팅 고치기는 **한 번에 하나** — 두 요청이 같은 수정 접수를 나눠 쓰다 한쪽 실패가 다른 쪽 접수를
    #   닫지 않게, 이 연결이 끝날 때까지 여행 단위 잠금을 쥔다(못 쥐면 지금 처리 중이라고 답한다)
    with connect() as guard:
        with guard.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (f"{tenant}:chat_edit:{trip_id}",))
            if not cur.fetchone()[0]:
                raise EditRefused("busy", "같은 여행의 다른 변경을 처리하는 중이라 이번 요청은 바꾸지 않았어요. 잠시 뒤 다시 말씀해 주세요.")
        try:
            return _run_locked(store=store, connect=connect, tenant=tenant, customer_id=customer_id, trip_id=trip_id,
                               base_version=base_version, ops=ops, lookups=lookups, now=now, cause_extra=cause_extra)
        finally:
            with guard.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (f"{tenant}:chat_edit:{trip_id}",))


def _run_locked(*, store: Any, connect: Callable[[], Any], tenant: str, customer_id: UUID, trip_id: UUID, base_version: int,
                ops: list[EditOp], lookups: Callable[[], tuple[Any, Any, Any]], now: datetime,
                cause_extra: dict[str, Any] | None) -> dict[str, Any]:
    from app.domains.travel_ops.components.intake import pipeline, reopen
    from app.domains.travel_ops.components.intake.reopen_commit import CommitRefused, commit

    with connect() as conn:
        trip, items = store.latest(conn, trip_id)
        if int(trip["version"]) != int(base_version):
            raise EditRefused("stale_itinerary", _refusal("stale_itinerary", ""))
        intake_id, existed = reopen.open_for_trip(conn, tenant_id=tenant, customer_id=customer_id, trip=trip, items=items,
                                                  now=now)
        revision = _revision(conn, tenant, intake_id)
        if existed and revision > 1:
            # 고객이 웹 「일정 수정」에서 고치던 값이 있다 — 그 위에 채팅 고치기를 섞어 한꺼번에 쓰지 않는다
            raise EditRefused("edit_screen_open", "일정 수정 화면에서 고치던 내용이 있어 채팅으로는 바꾸지 않았어요. "
                                                  "화면에서 「완료」하거나 「취소」한 뒤 다시 말씀해 주세요.")
        if existed:
            # ★`[2026-10-15 Codex 검토]` 웹이 열어만 둔 빈 수정 접수(고친 값 없음)는 웹 것이다 — 같이 쓰지 않고 닫은 뒤 채팅 몫을 새로 연다.
            #   웹 화면이 그대로 열려 있으면 다음 고치기에서 「다시 열어 주세요」가 된다(판이 바뀌었으므로 어차피 그렇다)
            reopen.cancel(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id)
            intake_id, _ = reopen.open_for_trip(conn, tenant_id=tenant, customer_id=customer_id, trip=trip, items=items, now=now)
            revision = _revision(conn, tenant, intake_id)
    committed = False
    try:
        with connect() as conn:
            claims = pipeline._claims(conn, tenant, intake_id, revision)
            sources = pipeline._sources(conn, tenant, intake_id)
        source_id = str(sources[0]["source_id"])
        where = {item_id: index for (_sid, index), item_id in reopen.origins(claims).items()}
        added_index = max(where.values(), default=-1) + 1
        frozen = {str(i.item_id) for i in items if i.kind != "mobility"} - {str(k) for k in where}
        by_id = {i.item_id: i for i in items}
        tour, kakao, dining = lookups() if any(o.kind in ("place", "add") for o in ops) else (None, None, None)
        for op in ops:
            if op.kind == "add" and op.item_kind is None:
                # 넣기는 종류(활동 · 식사)를 함께 보내야 한다 — 웹 「＋」 가 고른 곳의 종류를 싣는 것과 같다. 같은 이름 찾기로 먼저 찾는다
                from app.domains.travel_ops.components.intake.places import resolve

                with connect() as conn:
                    found = resolve(op.place_name or "", our_places=pipeline._our_places(conn, tenant), tour=tour,
                                    kakao=kakao, dining=dining)
                if found.status != "resolved":
                    raise EditRefused("place_not_found", _refusal("place_not_found", found.note or "찾지 못함"))
                op.item_kind = "dining" if found.kind == "dining" else "activity"
        edits: list[dict[str, Any]] = []
        locks: list[dict[str, Any]] = []
        unpinned: set[Any] = set()
        auto_pinned = {f"items[{where[i.item_id]}]" for i in items
                       if i.item_id in where and not i.locked and (i.detail or {}).get("customer_pinned")}
        for op in ops:
            if op.kind == "add":
                fields = {"title": op.title or op.place_name, "date": op.date, "starts_at": op.starts_at,
                          "ends_at": op.ends_at, "kind": op.item_kind or "activity", "place": {"name": op.place_name}}
                edits += [{"source_id": source_id, "field": f"items[{added_index}].{name}", "value": value}
                          for name, value in fields.items()]
                added_index += 1
                continue
            if op.item_id not in where:
                item = by_id.get(op.item_id)
                title = item.title if item else "그 일정"
                if str(op.item_id) in frozen:
                    raise EditRefused("frozen_item", f"「{title}」은(는) 이미 지났거나 예약이 묶인 일정이라 채팅으로 바꾸지 않았어요.")
                raise EditRefused("unknown_item", "바꿀 일정을 지금 일정에서 하나로 찾지 못해 일정은 바꾸지 않았어요. 일정 이름을 알려 주세요.")
            if reopen._policy_locked(by_id[op.item_id]):
                # `[2026-10-15 ST4F-490]` 숙소 · 항공 · 업체 예약 일정은 수정 접수에 **잠금**으로 들어온다(웹 「일정 수정」에서 풀어 고친다). 채팅은 전처럼 바꾸지 않고
                #   「일정 수정」으로 안내한다 — 채팅으로 푼 잠금은 다음 요청의 수정 접수에서 다시 잠겨 「고정 풀어줘」 안내가 되풀이됐다
                raise EditRefused("locked_kind", f"「{by_id[op.item_id].title}」은(는) 숙소 · 항공 · 예약 일정이라 채팅으로는 바꾸지 않았어요. "
                                                 "「일정 수정」에서 잠금을 풀고 고쳐 주세요.")
            prefix = f"items[{where[op.item_id]}]"
            if op.kind in ("place", "remove", "time") and prefix in auto_pinned and op.item_id not in unpinned:
                # ★`[2026-10-15 실서버 확인]` 서버가 **고객이 만진 일정**(되돌리기 · 앞선 고치기 · 직접 지정한 곳)에 붙인 자동 표시(`customer_pinned`)는 다시 열면
                #   「고정」으로 실려 장소 바꾸기 · 빼기가 「고정한 일정이라 바꿀 수 없습니다」로 거절됐다(x600 「경복궁 대신 창덕궁 가자」). 고객이 지금 직접 말한 요청이므로
                #   같은 요청 안에서 푼다 — 자동 표시와 고객이 「고정해줘」라고 한 표시는 같은 칸(`customer_pinned`)이라 가를 수 없고, **나중에 한 직접 요청이 이긴다**.
                #   예약이 묶인 일정(`locked`)은 푸는 대상이 아니라 그대로 거절한다
                edits.append({"source_id": source_id, "field": f"{prefix}.locked", "value": False})
                unpinned.add(op.item_id)
            if op.kind == "time":
                for name in ("date", "starts_at", "ends_at"):
                    value = getattr(op, name)
                    if value is not None:
                        edits.append({"source_id": source_id, "field": f"{prefix}.{name}", "value": value})
            elif op.kind == "place":
                # ★`[2026-10-15 x600 실서버 확인]` 식사 일정에 「덕수궁」이라고만 쓰면 웹 고치기는 식사 일정이라 **식당에서** 찾아 「탁사발두부공방 덕수궁점」으로 바꿨다.
                #   고객이 이름으로 말했으니 종류 힌트 없이 먼저 찾고, 찾은 곳의 종류(활동 · 식사)가 일정의 종류와 다르면 일정의 종류도 함께 맞춘다
                item = by_id[op.item_id]
                if item.kind in ("dining", "activity") and op.place_name:
                    from app.domains.travel_ops.components.intake.places import resolve

                    with connect() as conn:
                        named = resolve(op.place_name, our_places=pipeline._our_places(conn, tenant), tour=tour, kakao=kakao, dining=dining)
                    new_kind = "dining" if named.kind == "dining" else ("activity" if named.kind else None)
                    if named.status == "resolved" and new_kind and new_kind != item.kind:
                        edits.append({"source_id": source_id, "field": f"{prefix}.kind", "value": new_kind})
                edits.append({"source_id": source_id, "field": f"{prefix}.place", "value": {"name": op.place_name}})
                if op.title:
                    edits.append({"source_id": source_id, "field": f"{prefix}.title", "value": op.title})
            elif op.kind == "remove":
                edits.append({"source_id": source_id, "field": f"{prefix}.removed", "value": True})
            elif op.kind in ("lock", "unlock"):
                # 고정은 따로 보낸다(`pipeline.edit` — 고정 요청에 다른 고치기를 섞지 않는다)
                locks.append({"source_id": source_id, "field": f"{prefix}.locked", "value": op.kind == "lock"})
        relock: list[dict[str, Any]] = []
        for batch in (edits, locks):
            if not batch:
                continue
            try:
                with connect() as conn:
                    revision = pipeline.edit(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id,
                                             revision=revision, edits=batch, tour=tour, kakao=kakao, dining=dining, learn_aliases=False,
                                             reflow=any(o.reflow for o in ops))
            except pipeline.IntakeConflict as exc:
                add_days = {o.date for o in ops if o.kind == "add" and o.date}
                if batch is not edits or exc.code != "schedule_conflict" or not add_days:
                    raise
                # ★`[2026-10-15 사용자 결정]` 넣기가 앞뒤 고정 일정에 막히면 **B: 그날 고정 표시를 이 요청 동안만 풀고 뒤 일정을 밀어 자리를 만든 뒤 다시 고정한다.
                #   그래도 안 되면 C: 빈 시간을 찾아 「이 시각에 넣을까요」로 안내한다**
                with connect() as conn:
                    pinned_now = {pipeline._item_no(c["field"]) for c in pipeline.effective(pipeline._claims(conn, tenant, intake_id, revision))
                                  if c["field"].endswith(".locked") and c["value"] is True}
                # `[2026-10-15 ST4F-490]` 숙소 · 항공 · 업체 예약(정책 잠금)은 풀지 않는다 — 넣기 때문에 비행기 · 체크인 시각을 밀지 않는다
                release = [f"items[{index}]" for item_id, index in where.items()
                           if index in pinned_now and by_id[item_id].starts_at.astimezone(KST).date().isoformat() in add_days
                           and not reopen._policy_locked(by_id[item_id])]
                retry = [{"source_id": source_id, "field": f"{p}.locked", "value": False} for p in release] + edits
                try:
                    if not release:
                        raise exc
                    with connect() as conn:
                        revision = pipeline.edit(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id,
                                                 revision=revision, edits=retry, tour=tour, kakao=kakao, dining=dining, learn_aliases=False)
                    relock = [{"source_id": source_id, "field": f"{p}.locked", "value": True} for p in release]
                    log.info("chat edit add: pushed past pinned stops trip=%s released=%d", trip_id, len(release))
                except pipeline.IntakeConflict as again:
                    if again.code != "schedule_conflict":
                        raise
                    raise EditRefused("no_room", _no_room_text(ops, items, now)) from None
        for lock in relock:
            try:
                with connect() as conn:
                    revision = pipeline.edit(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id,
                                             revision=revision, edits=[lock], tour=tour, kakao=kakao, dining=dining, learn_aliases=False)
            except (pipeline.IntakeConflict, pipeline.IntakeRejected):
                log.warning("chat edit relock skipped field=%s", lock["field"])        # 다시 고정하지 못해도 넣기는 이미 됐다
        with connect() as conn:
            pipeline.view(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id)   # 그 판의 검사(이동 · 운영시간)
            status, _, built = pipeline.draft(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id,
                                              revision=revision)
            reopened = reopen.session(conn, tenant_id=tenant, intake_id=intake_id)
        version, changed, plan = commit(store=store, connect=connect, tenant=tenant, intake_id=intake_id, revision=revision,
                                        reopened=reopened, status=status, built=built, now=now,
                                        cause_extra={"via": "chat", **(cause_extra or {})})
        if changed:
            with connect() as conn:
                pipeline.mark_confirmed(conn, tenant_id=tenant, intake_id=intake_id, trip_id=trip_id)
            committed = True
    except EditRefused:
        raise
    except pipeline.IntakeRejected as exc:
        raise EditRefused(exc.code, _refusal(exc.code, exc.message)) from None
    except pipeline.IntakeConflict as exc:
        raise EditRefused(exc.code, _refusal(exc.code, exc.message)) from None
    except CommitRefused as exc:
        raise EditRefused(exc.code, _refusal(exc.code, exc.message), **exc.detail) from None
    finally:
        if not committed:
            # ★`[2026-10-15 Codex 검토]` 끝까지 쓰지 못했으면(거절 · 바뀐 것 없음 · 예상 밖 오류 모두) **이 요청이 연 수정 접수를 닫는다** —
            #   열린 채 남으면 다음 웹 「일정 수정」이 그 접수를 다시 쓴다. 닫기 실패는 기록만 하고 원래 결과를 가리지 않는다
            try:
                with connect() as conn:
                    reopen.cancel(conn, tenant_id=tenant, customer_id=customer_id, intake_id=intake_id)
            except Exception:                                    # noqa: BLE001
                log.warning("chat edit intake close failed intake=%s", intake_id, exc_info=True)
    return {"version": version, "changed": changed, "plan": plan, "intake_id": str(intake_id)}


def _no_room_text(ops: list[EditOp], items: list[Any], now: datetime) -> str:
    """넣기가 앞뒤 일정에 막혔을 때 — 그날의 **빈 시간**을 찾아 「이 시각에 넣을까요」로 안내한다(C). 이동 여유 15분 · 머무는 시간 60분을 두고 찾는다."""
    op = next(o for o in ops if o.kind == "add")
    name = op.place_name or op.title or "그곳"
    stay = timedelta(minutes=60)
    gap = timedelta(minutes=15)
    stops = sorted((i for i in items if i.kind != "mobility" and i.starts_at.astimezone(KST).date().isoformat() == op.date),
                   key=lambda i: i.starts_at)
    wanted = datetime.fromisoformat(f"{op.date}T{op.starts_at}").replace(tzinfo=KST)
    best = None
    cursor = None
    for stop in stops:
        end = (stop.ends_at or stop.starts_at + stay).astimezone(KST)
        if cursor is not None:
            start = _round5(cursor + gap)
            if stop.starts_at.astimezone(KST) - gap - start >= stay and start >= wanted - timedelta(minutes=1) and best is None:
                best = start
        cursor = end if cursor is None or end > cursor else cursor
    if best is None and cursor is not None and _round5(cursor + gap) + stay <= datetime.fromisoformat(f"{op.date}T22:00").replace(tzinfo=KST):
        best = _round5(cursor + gap)
    if best is None:
        return f"그 날은 앞뒤 일정 때문에 「{name}」을(를) 넣을 빈 시간이 없어 넣지 못했어요. 넣고 싶은 시각을 바꾸거나 다른 일정을 빼 주세요."
    hhmm = best.strftime("%H:%M")
    return (f"그 자리에는 앞뒤 일정 때문에 「{name}」을(를) 넣지 못했어요. 대신 {hhmm}에는 넣을 수 있어요 — "
            f"「{hhmm}에 {name} 넣어줘」라고 말씀해 주세요.")


def _revision(conn, tenant: str, intake_id: UUID) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant, intake_id))
        return int(cur.fetchone()[0])


def shifted(item: Any, minutes: int) -> tuple[str, str, str | None]:
    """일정 하나를 `minutes` 만큼 옮긴 (날짜, 시작, 끝) — 머무는 시간은 그대로. 날짜를 넘어가면 날짜도 바뀐다."""
    starts = item.starts_at.astimezone(KST) + timedelta(minutes=minutes)
    ends = (item.ends_at.astimezone(KST) + timedelta(minutes=minutes)) if item.ends_at else None
    return starts.date().isoformat(), starts.strftime("%H:%M"), ends.strftime("%H:%M") if ends else None


def moved_to(item: Any, *, day: str | None, start: str | None) -> tuple[str, str, str | None]:
    """일정 하나를 그 날 · 그 시각으로 옮긴 (날짜, 시작, 끝) — 말하지 않은 것은 그대로, 머무는 시간도 그대로."""
    starts = item.starts_at.astimezone(KST)
    new_day = day or starts.date().isoformat()
    new_start = start or starts.strftime("%H:%M")
    begin = datetime.fromisoformat(f"{new_day}T{new_start}").replace(tzinfo=KST)
    ends = (begin + (item.ends_at - item.starts_at)) if item.ends_at else None
    return new_day, new_start, ends.strftime("%H:%M") if ends else None


# ── 해석 → 고칠 것 ─────────────────────────────────────────────────────
_TIME = __import__("re").compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
#: 이름이 아니라 **종류만** 말한 장소 — 이 낱말뿐이면 장소로 찾지 않고 되묻는다
_GENERIC_PLACE = __import__("re").compile(
    r"(?:(?:괜찮은|좋은|근처|아무|어디)\s*)*(?:카페|커피숍?|커피\s*집|식당|맛집|음식점|레스토랑|밥집|술집|바|빵집|디저트(?:\s*카페)?|관광지|명소|공원|박물관|미술관|쇼핑몰?|시장|점심|저녁|아침|간식|장소|곳)"
    r"(?:\s*(?:하나|한\s*곳|한\s*군데|좀))?")


def _day_of(token: str | None, stops: list[Any], now: datetime) -> str | None:
    """해석의 날(today · tomorrow · dN) → YYYY-MM-DD. 말하지 않았으면 None."""
    if not token or token in ("none", "all") or not stops:
        return None
    today = now.astimezone(KST).date()
    if token == "today":
        return today.isoformat()
    if token == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if token.startswith("d") and token[1:].isdigit():
        first = min(s.starts_at.astimezone(KST).date() for s in stops)
        return (first + timedelta(days=int(token[1:]) - 1)).isoformat()
    return None


#: 「오늘 저녁으로」 · 「점심으로」 처럼 **끼니 말로 옮길 곳**을 말했을 때의 시각 — 문장에 시각이 없을 때만 쓰는 서버의 약속값(고객이 말한 끼니 → 그 끼니의 보통 시각)
_MEAL_AT = {"아침": "08:00", "점심": "12:00", "저녁": "18:00", "밤": "20:00"}
_TO_MEAL = __import__("re").compile(r"(?:(오늘|내일|모레)\s*)?(아침|점심|저녁|밤)\s*(?:으로|로|에)(?![가-힣])")


def spoken_meal_target(message: str, now: datetime) -> tuple[str | None, str] | None:
    """「내일 점심을 오늘 저녁으로 옮겨줘」 → (오늘 날짜, 18:00). 옮길 곳을 **끼니 말**(+ 오늘 · 내일 · 모레)로 말했을 때만 — 문장의 **마지막** 「…(으)로 · 에」 끼니 말이다
    (앞의 「점심을」은 옮길 대상이라 조사가 달라 걸리지 않는다). 없으면 None."""
    found = list(_TO_MEAL.finditer(message or ""))
    if not found:
        return None
    day_word, meal = found[-1].group(1), found[-1].group(2)
    today = now.astimezone(KST).date()
    day = {"오늘": today, "내일": today + timedelta(days=1), "모레": today + timedelta(days=2)}.get(day_word or "")
    return (day.isoformat() if day else None), _MEAL_AT[meal]


def _inside_trip(day: str, stops: list[Any]) -> bool:
    dates = [s.starts_at.astimezone(KST).date() for s in stops]
    return bool(dates) and min(dates).isoformat() <= day <= max(dates).isoformat()


def _round5(moment: datetime) -> datetime:
    extra = (-moment.minute) % 5
    return (moment + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def _same_day(day: str, start: str, end: str | None, title: str) -> None:
    if end is not None and end <= start:
        raise EditRefused("crosses_midnight", f"「{title}」이(가) 자정을 넘기게 돼 채팅으로는 옮기지 않았어요. 일정 수정 화면에서 날짜와 시각을 함께 고쳐 주세요.")


_ALL = __import__("re").compile(r"전부|전체|모두|다\s*(?:미뤄|밀어|당겨|늦춰)|all\s+(?:of\s+)?(?:my|the)|everything", __import__("re").IGNORECASE)
_PERIOD_WORDS = (("morning", __import__("re").compile(r"오전|아침")), ("afternoon", __import__("re").compile(r"오후")),
                 ("evening", __import__("re").compile(r"저녁|밤|evening|night", __import__("re").IGNORECASE)))


def _range_from_sentence(message: str, token: str | None, stops: list[Any], now: datetime) -> dict[str, str] | None:
    """「오후 일정 전부 한 시간씩 밀어줘」 — 모델이 범위(`query`)를 안 적었어도 문장의 「전부」 · 시간대 말로 범위를 만든다.
    ★문장에 **전부 · 전체 · 모두**가 있을 때만 — 일정 하나를 가리킨 말이면 범위로 보지 않는다. 날을 말하지 않았으면 오늘 이후 일정이 있는 가장 가까운 날."""
    if not message or not _ALL.search(message) or not stops:
        return None
    dates = sorted({s.starts_at.astimezone(KST).date() for s in stops})
    today = now.astimezone(KST).date()
    if token and token not in ("none", "all"):
        day = token
    else:
        # 날을 말하지 않았다 — 오늘 이후 일정이 있는 가장 가까운 날(오늘 일정이 없으면 다음 일정 날, 다 지났으면 1일차)
        pick = next((d for d in dates if d >= today), dates[0])
        day = "today" if pick == today else f"d{(pick - dates[0]).days + 1}"
    period = next((name for name, rx in _PERIOD_WORDS if rx.search(message)), "all")
    return {"day": day, "period": period, "kind": "all", "position": "all"}


def ops_for(decision: Any, *, items: list[Any], now: datetime, message: str = "",
            read_plan: Callable[[str, Any], Any] | None = None) -> tuple[list[EditOp], str]:
    """해석(`decision_unit.Decision`) → 고칠 것들 · 무엇을 하는지 한 줄. 값이 모자라면 `EditRefused`(고객에게 물을 말).

    `read_plan` `[2026-10-16 D-025]` — 채팅 수정 요청과 계획서는 **같은 입구**다. 「넣기」면 메시지를 계획서와 같은 이해 에이전트(`intake.agent_read`)로
      읽어(원문 인용 · 시각 다시 계산을 그대로 거친다) 장소 여럿 · 시각을 한 번에 넣는다. 못 읽으면(모델 실패 · 시각 없음) 아래 한 곳 넣기로 간다.

    ★값은 해석이 낸 칸만 쓴다 — 시각(`anchor_time`) · 날(`at_day`) · 옮길 크기(`minutes`, 문장에 적힌 시간 · 분) · 기준 일정(`anchor_item`) ·
      넣을 곳 이름(`destination_text`). 서버가 짐작으로 채우지 않는다(모르면 묻는다)."""
    from app.domains.travel_ops.components.conversation import trip_facts
    from app.domains.travel_ops.components.conversation.schedule_query import matching

    stops = trip_facts._stops(items)
    by_alias = {f"i{n}": item for n, item in enumerate(stops, 1)}
    raw = decision.raw or {}
    action, item = decision.action, decision.item
    anchor_time = raw.get("anchor_time") if isinstance(raw.get("anchor_time"), str) and _TIME.match(raw.get("anchor_time") or "") else None
    if raw.get("anchor_kind") not in (None, "time", "none"):
        anchor_time = None                                  # 기준이 일정 · 지금 · 앞 답이면 시각 칸이 아니다
    day = _day_of(raw.get("at_day"), stops, now)
    other = by_alias.get(str(raw.get("anchor_item") or "none"))
    name = str(raw.get("destination_text") or "").strip()[:80]

    if action == "change_time":
        from .edit_intent import time_ops

        semantic = time_ops(decision, items=items, now=now)
        if semantic is not None:
            return semantic
        targets = [item] if item is not None else []
        query = decision.query if item is None else None
        if item is None and query is None and decision.minutes:
            query = _range_from_sentence(message, raw.get("at_day"), stops, now)
        if item is None and query is not None:
            # 범위 안에서 **아직 안 지났고 예약이 묶이지 않은** 활동 · 식사만(지난 일정 · 예약 일정은 웹과 같이 못 옮기므로 빼고 나머지를 옮긴다)
            targets = [i for i in matching(query, items=items, now=now)[0]
                       if i.kind in ("activity", "dining") and (i.ends_at or i.starts_at) > now and not i.booking_id]
        if not targets:
            raise EditRefused("need_target", "어느 일정을 옮길지 알려 주세요. 일정 이름이나 「점심」처럼 말씀해 주시면 옮길게요.")
        ops = []
        meal = None
        if not decision.minutes and raw.get("anchor_kind") in (None, "none", "time"):
            meal = spoken_meal_target(message, now)
            if meal is not None:
                # 시각은 모델이 낸 것이 우선(없으면 끼니의 약속값), **날은 문장의 말(오늘 · 내일 · 모레)이 우선**이다 —
                # ★`[2026-10-15 x600 실서버 확인]` 「모레 점심으로」를 모델이 12:00 · 1일차로 읽어 모레가 아닌 날로 옮겼다
                anchor_time = anchor_time or meal[1]
                day = meal[0] or day
        for target in targets:
            if raw.get("anchor_kind") == "now" and len(targets) == 1 and not decision.minutes:
                # 「지금 경복궁 갈래」 — 지금(5분 올림)으로 옮긴다. 머무는 시간은 그대로
                begin = _round5(now.astimezone(KST))
                new_day, start, end = moved_to(target, day=begin.date().isoformat(), start=begin.strftime("%H:%M"))
            elif anchor_time and len(targets) == 1:
                new_day, start, end = moved_to(target, day=day, start=anchor_time)
            elif decision.minutes:
                new_day, start, end = shifted(target, decision.minutes)
            elif day and len(targets) == 1:
                new_day, start, end = moved_to(target, day=day, start=None)
            else:
                raise EditRefused("need_time", f"「{target.title}」을(를) 몇 시로(또는 몇 분) 옮길지 알려 주세요.")
            if not _inside_trip(new_day, stops):
                # ★`[2026-10-15 x600 실서버 확인]` 「내일 점심을 오늘 저녁으로」 — 오늘이 여행 날이 아닌데 「이미 되어 있어요」가 나왔다. 여행 밖의 날로는 옮기지 않고 그렇게 알린다
                first = min(s.starts_at.astimezone(KST).date() for s in stops)
                last = max(s.starts_at.astimezone(KST).date() for s in stops)
                span = first.strftime("%m월 %d일") if first == last else f"{first.strftime('%m월 %d일')}~{last.strftime('%m월 %d일')}"
                raise EditRefused("day_outside_trip", f"{new_day[5:7]}월 {new_day[8:10]}일은 이 여행에 없는 날이라 「{target.title}」은(는) 옮기지 않았어요. 여행은 {span}이에요.")
            _same_day(new_day, start, end, target.title)
            ops.append(EditOp("time", item_id=target.item_id, date=new_day, starts_at=start, ends_at=end))
        what = (f"{targets[0].title} 시각 옮기기" if len(targets) == 1 else f"일정 {len(targets)}개 시각 옮기기")
        return ops, what
    if action == "remove_item":
        if item is None:
            raise EditRefused("need_target", "어느 일정을 뺄지 알려 주세요.")
        return [EditOp("remove", item_id=item.item_id)], f"{item.title} 빼기"
    if action in ("lock_item", "unlock_item"):
        if item is None:
            raise EditRefused("need_target", "어느 일정을 고정할지 알려 주세요." if action == "lock_item" else "어느 일정의 고정을 풀지 알려 주세요.")
        return [EditOp("lock" if action == "lock_item" else "unlock", item_id=item.item_id)], f"{item.title} {'고정' if action == 'lock_item' else '고정 풀기'}"
    if action == "replace_named":
        if item is None:
            raise EditRefused("need_target", f"어느 일정을 「{name}」(으)로 바꿀지 알려 주세요.")
        if not name:
            raise EditRefused("need_place", "어디로 바꿀지 장소 이름을 알려 주세요.")
        return [EditOp("place", item_id=item.item_id, place_name=name, title=name)], f"{item.title} → {name}"
    if action == "swap_order":
        if item is None or other is None or other.item_id == item.item_id:
            raise EditRefused("need_target", "순서를 바꿀 두 일정을 알려 주세요.")
        first, second = sorted((item, other), key=lambda i: i.starts_at)
        if first.starts_at.astimezone(KST).date() == second.starts_at.astimezone(KST).date():
            # 같은 날 — 앞 칸 시작에 뒤 일정을 놓고, 그것이 끝난 뒤 원래 간격만큼 띄워 앞 일정을 놓는다(머무는 시간은 각자 그대로).
            #   시작 시각만 맞바꾸면 머무는 시간이 다를 때 두 일정이 겹친다
            gap = second.starts_at - (first.ends_at or first.starts_at + DEFAULT_STAY)
            day_s = first.starts_at.astimezone(KST).date().isoformat()
            b_day, b_start, b_end = moved_to(second, day=day_s, start=first.starts_at.astimezone(KST).strftime("%H:%M"))
            b_until = second.ends_at - second.starts_at if second.ends_at else DEFAULT_STAY
            a_begin = first.starts_at.astimezone(KST) + b_until + max(gap, timedelta(0))
            a_day, a_start, a_end = moved_to(first, day=a_begin.date().isoformat(), start=a_begin.strftime("%H:%M"))
            pairs = ((second, b_day, b_start, b_end), (first, a_day, a_start, a_end))
        else:
            # 다른 날 — 날과 시작 시각을 맞바꾼다(머무는 시간은 각자 그대로)
            pairs = tuple((x, *moved_to(x, day=y.starts_at.astimezone(KST).date().isoformat(),
                                        start=y.starts_at.astimezone(KST).strftime("%H:%M"))) for x, y in ((item, other), (other, item)))
        for target, d, st, en in pairs:
            _same_day(d, st, en, target.title)
        return [EditOp("time", item_id=t.item_id, date=d, starts_at=st, ends_at=en) for t, d, st, en in pairs], f"{item.title} · {other.title} 순서 바꾸기"
    if action == "add_item" and read_plan is not None:
        read_ops = _read_adds(message, read_plan, stops=stops, now=now, day=day)
        if read_ops:
            names = " · ".join(op.title or "" for op in read_ops)
            return read_ops, f"{names} 넣기"
    if action == "add_item":
        if not name or _GENERIC_PLACE.fullmatch(name.strip()):
            # ★`[2026-10-15 x600 실서버 확인]` 「오후 3시에 카페 하나 추가해줘」 — 종류만 말했는데 「카페」라는 이름을 장소로 찾으러 가 조회 한도만 쓰고 막혔다.
            #   종류만 말했으면 찾지 않고 이름을 되묻는다
            raise EditRefused("need_place", "어떤 곳을 넣을지 장소 이름을 알려 주세요. 이름을 알려 주시면 그곳을 찾아 넣을게요. "
                                            "예: 「오후 3시에 ○○ 카페 넣어줘」")
        if anchor_time:
            first_day = min((s.starts_at.astimezone(KST).date() for s in stops), default=now.astimezone(KST).date())
            today = now.astimezone(KST).date()
            begin = datetime.fromisoformat(f"{day or (today if today >= first_day else first_day).isoformat()}T{anchor_time}").replace(tzinfo=KST)
        elif other is not None and raw.get("relation") in ("after", "before"):
            if raw.get("relation") == "after":
                begin = _round5((other.ends_at or other.starts_at + DEFAULT_STAY).astimezone(KST) + timedelta(minutes=10))
            else:
                begin = _round5(other.starts_at.astimezone(KST) - timedelta(minutes=10) - DEFAULT_STAY)
        else:
            raise EditRefused("need_time", f"「{name}」을(를) 몇 시에(또는 어느 일정 앞뒤에) 넣을지 알려 주세요.")
        end = begin + DEFAULT_STAY
        _same_day(begin.date().isoformat(), begin.strftime("%H:%M"), end.strftime("%H:%M") if end.date() == begin.date() else "00:00", name)
        return [EditOp("add", date=begin.date().isoformat(), starts_at=begin.strftime("%H:%M"), ends_at=end.strftime("%H:%M"),
                       place_name=name, title=name)], f"{name} 넣기"
    raise EditRefused("not_an_edit", "무엇을 바꿀지 알아듣지 못해 일정은 바꾸지 않았어요.")


def _read_adds(message: str, read_plan: Callable[[str, Any], Any], *, stops: list[Any], now: datetime, day: str | None) -> list[EditOp]:
    """이해 에이전트가 읽은 메시지 → 넣을 일정들. ★시각이 있는 항목만 넣는다(없으면 묻는 길로) · 이미 일정에 있는 이름은 넣지 않는다 ·
    날짜는 에이전트 값 → 해석의 날 → 여행 첫날(오늘이 여행 안이면 오늘) 순."""
    try:
        got = read_plan(message, now.astimezone(KST).date())
    except Exception:                                  # noqa: BLE001 — 읽기 실패는 한 곳 넣기로(지금 길)
        log.info("chat add: reader failed", exc_info=True)
        return []
    have = {(s.title or "").strip() for s in stops}
    first_day = min((s.starts_at.astimezone(KST).date() for s in stops), default=now.astimezone(KST).date())
    today = now.astimezone(KST).date()
    fallback_day = day or (today if today >= first_day else first_day).isoformat()
    ops: list[EditOp] = []
    for it in getattr(got, "items", []) or []:
        title = it.title.text.strip()[:80]
        if not it.start or not title or title in have or _GENERIC_PLACE.fullmatch(title):
            continue
        when = it.date or fallback_day
        begin = datetime.fromisoformat(f"{when}T{it.start}").replace(tzinfo=KST)
        end = datetime.fromisoformat(f"{when}T{it.end}").replace(tzinfo=KST) if it.end and it.end > it.start else begin + DEFAULT_STAY
        if end.date() != begin.date():
            continue
        _same_day(when, it.start, end.strftime("%H:%M"), title)
        ops.append(EditOp("add", date=when, starts_at=it.start, ends_at=end.strftime("%H:%M"), place_name=title, title=title,
                          item_kind="dining" if it.kind == "dining" else "activity"))
    return ops


def done_text(ops: list[EditOp], *, items_after: list[Any], plan: Any) -> str:
    """바꾼 뒤 답 — 바뀐 일정의 새 날 · 시각 · 장소를 그대로 보인다(지어내지 않는다)."""
    from app.domains.travel_ops.components.conversation import trip_facts

    lines = []
    by_id = {i.item_id: i for i in items_after}
    for item_id in dict.fromkeys([*plan.changed_ids, *plan.added_ids]):
        row = by_id.get(item_id)
        if row is not None:
            lines.append(f"· {trip_facts._day_label(row.starts_at.astimezone(KST).date())} "
                         f"{_hm(row.starts_at)}{'~' + _hm(row.ends_at) if row.ends_at else ''} {row.title}")
    head = {"add": "일정에 넣었어요.", "remove": "일정에서 뺐어요.", "lock": "그 일정을 고정했어요 — 자동으로 바꾸지 않아요.",
            "unlock": "고정을 풀었어요.", "place": "말씀하신 곳으로 바꿨어요.", "time": "시각을 옮겼어요."}[ops[0].kind]
    if plan.removed:
        lines += [f"· 뺀 일정: {t}" for t in plan.removed]
    tail = "이동 시간과 운영시간은 바뀐 일정으로 다시 확인했어요. 마음에 안 드시면 「되돌려 줘」라고 말씀해 주세요."
    return "\n".join([head, *lines, tail])


__all__ = ["DEFAULT_STAY", "EditOp", "EditRefused", "done_text", "moved_to", "ops_for", "run", "shifted"]
