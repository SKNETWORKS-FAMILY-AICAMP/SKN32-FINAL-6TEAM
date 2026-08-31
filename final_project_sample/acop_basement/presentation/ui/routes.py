from __future__ import annotations

import html
import json
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import acop_basement.core.settings as settings_module
from acop_basement.infrastructure.llm.openai import OpenAITeamLLM
from acop_basement.infrastructure.messaging.outbox import OutboxBrokerAdapter
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.core.remote_team.executor import LocalTeamExecutor
from acop_basement.infrastructure.rag import retriever as rag_retriever
from acop_basement.presentation.security import _development_key, masked
from acop_basement.presentation.ui import theme

# ★고객사 대시보드 — 쇼핑몰 운영자가 자기 CS 를 본다. 납품되는 제품이다.
#   개발 콘솔(구 /ui/**)은 이 저장소에서 지워졌다 — final_project_ui 가 별도로 담당한다
#   (docs/handoff/11·12). Composer(/ui/composer)는 이 파일이 아니라
#   app/presentation/ui/composer.py 소유다.
tenant_router = APIRouter(prefix="/ops", tags=["tenant-ui"])
# ★VOC 화면만 따로 뗀다. `voc` 모듈을 끄면 이 라우터를 등록하지 않아 /ops/voc 가
#   404 가 된다. 한 라우터에 섞어 두면 끌 방법이 없다.
voc_router = APIRouter(prefix="/ops", tags=["tenant-ui"])


#: 지금 화면에 낼 상단 메뉴. `mount_ui()` 가 기동할 때 한 번 정한다.
_NAV: tuple[tuple[str, str], ...] = theme.TENANT_NAV


def configure_nav(config) -> tuple[tuple[str, str], ...]:
    """꺼진 모듈의 메뉴를 뺀다. 조립 때 한 번만 부른다.

    ★없는 화면으로 가는 링크를 남기면 눌렀을 때 404 가 뜨고, 운영자는 서버가
      죽은 줄 안다. 모듈을 빼면 그 표면도 함께 빠져야 한다.

    ★매 요청마다 선언을 다시 읽지 않는다. 라우터 등록은 기동 시점에 끝나는데
      메뉴만 나중 선언을 보면 둘이 어긋난다 — 메뉴에는 VOC 가 있는데 누르면
      404 인 상태가 만들어진다. 중앙 설정 저장소 모드에서는 매 요청 DB 읽기가
      되기도 한다. 그래서 조립과 같은 시점, 같은 선언으로 정한다.
    """
    global _NAV
    _NAV = tuple((href, label) for href, label in theme.TENANT_NAV
                 if href != "/ops/voc" or config.module_enabled("voc"))
    return _NAV


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _json(value: Any) -> str:
    return _safe(json.dumps(value or {}, ensure_ascii=False, default=str, indent=2))


def _page(title: str, body: str, *, current: str = "", lede: str = "",
          nav: Any = None, brand: str = "고객 지원") -> HTMLResponse:
    """★기본 brand 는 '고객 지원' 이다 — 이 파일의 화면 전부가 고객사 것이기 때문이다.
    개발 콘솔 화면(Composer 포함)은 이 저장소에 없다 — final_project_ui가 맡는다."""
    return HTMLResponse(theme.page(title, body, current=current, lede=lede,
                                   nav=nav if nav is not None else _NAV, brand=brand))


def _tenant() -> str:
    return settings_module.get_settings().tenant_id


def _cases() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id, status, intent, issue_code, sentiment, owner_team_id, version, updated_at FROM customer_cases WHERE tenant_id=%s ORDER BY updated_at DESC", (_tenant(),))
        keys = ("case_id", "status", "intent", "issue_code", "sentiment", "owner_team", "version", "updated_at")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


def _case(case_id: UUID) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id, status, subject, intent, issue_code, sentiment, owner_team_id, version, state_json, updated_at FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (_tenant(), case_id))
        row = cur.fetchone()
        if row is None:
            return None
        data = dict(zip(("case_id", "status", "subject", "intent", "issue_code", "sentiment", "owner_team", "version", "state_json", "updated_at"), row))
        cur.execute("SELECT event_id, aggregate_version, event_type, payload_json, actor_type, actor_id, created_at FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version", (_tenant(), case_id))
        data["events"] = [dict(zip(("event_id", "aggregate_version", "event_type", "payload", "actor_type", "actor_id", "created_at"), r)) for r in cur.fetchall()]
        data["trace_identity"] = {"case_id": str(data["case_id"]), "subject": data["subject"], "status": data["status"], "version": data["version"]}
        if data["events"]:
            data["events"][0]["payload"] = {"trace_case": data["trace_identity"], **(data["events"][0]["payload"] or {})}
        data["evidence"] = [{"source_type": "case_event", "source_id": str(e["event_id"]), "claim": e["event_type"]} for e in data["events"]]
        return data


def _actions() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT action_id, case_id, action_type, arguments_json, idempotency_key, status, created_at FROM action_requests WHERE tenant_id=%s AND status IN ('proposed','pending_approval') ORDER BY created_at", (_tenant(),))
        rows = [dict(zip(("action_id", "case_id", "action_type", "arguments", "idempotency_key", "status", "created_at"), r)) for r in cur.fetchall()]
        for row in rows:
            proposal_evidence = (row["arguments"] or {}).get("evidence", [])
            row["evidence"] = proposal_evidence if isinstance(proposal_evidence, list) else []
        return rows


def _voc() -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT period_start, period_end, metrics_json, alerts_json, created_at FROM feedback_analytics_reports WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 1", (_tenant(),))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("period_start", "period_end", "metrics", "alerts", "created_at"), row))


def _unknown_outbox() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT message_id, topic, payload_json, attempts, last_error, available_at, "
                    "now() - available_at AS elapsed FROM outbox "
                    "WHERE tenant_id=%s AND status='unknown' ORDER BY available_at", (_tenant(),))
        keys = ("message_id", "topic", "payload", "attempts", "last_error", "available_at", "elapsed")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


@tenant_router.get("/cases", response_class=HTMLResponse)
def cases() -> HTMLResponse:
    rows = _cases()
    if not rows:
        return _page("Case 목록", theme.empty_state(
            "표시할 Case가 없습니다.",
            hint="`python -m scripts.seed_demo_cases` 로 시연용 Case 를 만들 수 있습니다."),
            current="/ops/cases")

    # ★사람이 손대야 하는 건수를 맨 위에 세운다. 목록을 훑어 세게 하지 않는다.
    needs_human = sum(1 for r in rows if theme.tone_of(r["status"]) == "warn")
    critical = sum(1 for r in rows if theme.tone_of(r["status"]) == "critical")
    in_flight = sum(1 for r in rows if theme.tone_of(r["status"]) == "active")
    done = sum(1 for r in rows if theme.tone_of(r["status"]) == "done")
    summary = "<div class='grid'>" + "".join((
        theme.stat("전체", len(rows)),
        theme.stat("승인 대기", needs_human, tone="warn" if needs_human else "",
                   hint="사람이 결정해야 합니다" if needs_human else ""),
        theme.stat("에스컬레이션", critical, tone="critical" if critical else "",
                   hint="지금 확인이 필요합니다" if critical else ""),
        theme.stat("진행 중", in_flight),
        theme.stat("종결", done, tone="done" if done else ""),
    )) + "</div>"

    body_rows = [
        "<tr>"
        f"<td><a class='mono' href='/ops/cases/{r['case_id']}'>{_safe(masked(r['case_id']))}</a></td>"
        f"<td>{theme.pill(r['status'])}</td>"
        f"<td>{_safe(r['intent']) or '<span class=muted>미분류</span>'}</td>"
        f"<td>{_safe(r['issue_code']) or '<span class=muted>—</span>'}</td>"
        f"<td>{_safe(r['sentiment']) or '<span class=muted>—</span>'}</td>"
        f"<td>{_safe(r['owner_team']) or '<span class=muted>미배정</span>'}</td>"
        f"<td class='mono'>v{_safe(r['version'])}</td>"
        f"<td class='muted'>{_safe(r['updated_at'])}</td>"
        "</tr>" for r in rows]
    listing = theme.table(
        ("case", "status", "intent", "issue_code", "sentiment", "owner_team", "version", "updated_at"),
        body_rows)
    return _page("Case 목록", summary + theme.card(None, listing),
                 current="/ops/cases",
                 lede="분류 실패는 빈칸이 아니라 '미분류'로 적습니다 — 추정으로 채우지 않습니다.")


@tenant_router.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Case 상세", theme.empty_state("Case를 찾을 수 없습니다."), current="/ops/cases")

    state = data["state_json"] or {}
    # ★degraded 를 숨기지 않는다. 축소된 근거로 만든 답이면 화면이 먼저 말한다.
    banner = ""
    if state.get("degraded"):
        omissions = state.get("omissions") or []
        banner = theme.notice(
            "이 Case 의 ContextPack 은 축소됐습니다(degraded). 빠진 것: "
            + (", ".join(str(o) for o in omissions) or "기록 없음"), tone="critical")

    facts = theme.kv_table((
        ("status", data["status"]),
        ("version", f"v{data['version']}"),
        ("intent", data["intent"] or "미분류"),
        ("issue_code", data["issue_code"] or "미분류"),
        ("sentiment", data["sentiment"] or "미분류"),
        ("owner_team", data["owner_team"] or "미배정"),
        ("updated_at", data["updated_at"]),
    ))
    head = theme.card(
        "요약", f"<p>{theme.pill(data['status'])}</p>" + facts,
        subtitle=f"{len(data['events'])}개 이벤트")
    evidence = theme.card("Evidence", theme.evidence_block(data["evidence"], masker=masked),
                          subtitle="각 주장이 무엇에 근거하는지")
    raw = theme.card(None, theme.details("state_json 원문", f"<pre>{_json(state)}</pre>"))
    link = ("<div class='actions'>"
            f"<a href='/ops/cases/{case_id}/trace'><button>Trace 타임라인 보기</button></a></div>")
    return _page("Case 상세", banner + head + evidence + raw + link, current="/ops/cases")


@tenant_router.get("/cases/{case_id}/trace", response_class=HTMLResponse)
def trace(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Trace", theme.empty_state("Case를 찾을 수 없습니다."), current="/ops/cases")

    items = "".join(
        "<li class='tl'>"
        f"<div class='tl__head'><span class='tl__v'>v{theme.esc(e['aggregate_version'])}</span>"
        f"{theme.pill(e['event_type'], label=e['event_type'])}</div>"
        f"<p class='tl__meta'>{_safe(masked(e['actor_id']))} "
        f"({_safe(e['actor_type'])}) · {_safe(e['created_at'])}</p>"
        f"<pre>{_json(e['payload'])}</pre></li>"
        for e in data["events"])
    timeline = f"<ul class='timeline'>{items}</ul>" if items else theme.empty_state("이벤트 없음")
    note = theme.notice(
        "이 타임라인은 append-only case_events 입니다. 수정·삭제 기능은 제공하지 않습니다.",
        tone="info")
    return _page("Trace · append-only timeline",
                 note + theme.card(None, timeline), current="/ops/cases",
                 lede=f"case {case_id}")


@tenant_router.get("/approvals", response_class=HTMLResponse)
def approvals() -> HTMLResponse:
    rows = _actions()
    if not rows:
        return _page("Approval", theme.empty_state("대기 중인 승인 요청이 없습니다."),
                     current="/ops/approvals")

    blocked = sum(1 for r in rows if not r["evidence"])
    summary = "<div class='grid'>" + "".join((
        theme.stat("대기 중", len(rows), tone="warn"),
        theme.stat("근거 없어 잠김", blocked, tone="critical" if blocked else "",
                   hint="승인할 수 없습니다" if blocked else ""),
    )) + "</div>"

    cards = []
    for r in rows:
        evidence = r["evidence"]
        args = r["arguments"] or {}
        # ★근거가 없으면 버튼을 잠근다. 그리고 **왜 잠겼는지 적는다** —
        #   이유를 안 적으면 운영자가 UI 결함으로 오해한다 (2026-08-14 에 실제로 그랬다).
        disabled = " disabled" if not evidence else ""
        lock_note = theme.notice(
            "근거가 없어 승인·거절이 잠겼습니다. 확정 답변에는 Evidence 가 필요합니다.",
            tone="critical") if not evidence else ""

        facts = theme.kv_table((
            ("case", masked(r["case_id"])),
            ("action", masked(r["action_id"])),
            ("risk_level", args.get("risk_level") or "미지정"),
            ("idempotency_key", masked(r["idempotency_key"])),
        ))
        cards.append(theme.card(
            r["action_type"],
            facts
            + "<h3>rationale evidence</h3>"
            + theme.evidence_block(evidence, masker=masked)
            + lock_note
            + theme.details("arguments 원문", f"<pre>{_json(args)}</pre>")
            + f"<form class='actions' method='post' action='/ops/approvals/{r['case_id']}/{r['action_id']}'>"
              f"<button name='decision' value='approved'{disabled}>승인</button>"
              f"<button class='ghost' name='decision' value='rejected'{disabled}>거절</button></form>",
            subtitle=str(r["status"]),
            tone="critical" if not evidence else "warn"))

    return _page("Approval", summary + "".join(cards), current="/ops/approvals",
                 lede="승인은 되돌릴 수 없습니다. 근거를 먼저 읽고 누르십시오.")


@tenant_router.post("/approvals/{case_id}/{action_id}")
async def approve(request: Request, case_id: UUID, action_id: UUID) -> RedirectResponse:
    form = await request.form()
    decision = str(form.get("decision", "rejected"))
    settings = settings_module.get_settings()
    token = _development_key("action:approve", settings.secret_key)
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url=str(request.base_url).rstrip("/")) as client:
        response = await client.post(f"/v1/cases/{case_id}/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"}, json={"decision": decision, "approver_id": "ui-operator"})
    # ★두 분기가 같은 응답을 내고 있었다 — 승인이 실패해도 운영자는 목록으로 돌아올 뿐
    #   무엇이 잘못됐는지 알 수 없었다. 승인은 되돌릴 수 없는 행위인데 실패를 삼키면
    #   "눌렀으니 됐겠지" 로 넘어간다 (CLAUDE.md §3 — 조용한 스킵을 만들지 않는다).
    if response.is_error:
        detail = _safe(response.text[:400]) or f"HTTP {response.status_code}"
        return _page("Approval 실패", (
            f"<p class='card'><strong>승인이 처리되지 않았습니다.</strong> "
            f"HTTP {response.status_code}</p><pre class='card'>{detail}</pre>"
            "<p><a href='/ops/approvals'>승인 목록으로</a></p>"))
    return RedirectResponse("/ops/approvals", status_code=303)


@tenant_router.get("/outbox", response_class=HTMLResponse)
def outbox() -> HTMLResponse:
    rows = _unknown_outbox()
    if not rows:
        return _page("Outbox · unknown", theme.empty_state("unknown 상태 메시지가 없습니다"),
                     current="/ops/outbox")

    cards = []
    for row in rows:
        message_id = row["message_id"]
        facts = theme.kv_table((
            ("message_id", masked(message_id)), ("topic", row["topic"]),
            ("attempts", row["attempts"]), ("last_error", row["last_error"] or "—"),
            ("available_at", row["available_at"]), ("elapsed", row["elapsed"]),
        ))
        form = (f"<form method='post' action='/ops/outbox/{message_id}'>"
                "<label class='field'>확인 기록 (필수)"
                "<input name='note' required minlength='1' placeholder='하류 시스템에서 확인한 근거를 적으세요'></label>"
                "<div class='actions'>"
                "<button name='resolution' value='confirmed_delivered'>배달 확인됨</button>"
                "<button name='resolution' value='requeue'>배달 안 됨(재시도)</button>"
                "<button class='ghost' name='resolution' value='confirmed_not_delivered'>배달 안 됨(포기)</button>"
                "</div></form>")
        cards.append(theme.card("unknown 메시지", facts + theme.details("payload_json 요약", f"<pre>{_json(row['payload'])}</pre>") + form,
                                subtitle="자동 재시도 없음", tone="critical"))
    return _page("Outbox · unknown", "".join(cards), current="/ops/outbox",
                 lede="하류 시스템을 직접 확인한 뒤, 근거를 기록하고 결론을 선택하십시오.")


@tenant_router.post("/outbox/{message_id}")
async def resolve_outbox(request: Request, message_id: UUID):
    form = await request.form()
    resolution = str(form.get("resolution", ""))
    note = str(form.get("note", ""))
    settings = settings_module.get_settings()
    token = _development_key("action:approve", settings.secret_key)
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url=str(request.base_url).rstrip("/")) as client:
        response = await client.post(f"/v1/outbox/{message_id}/resolve",
                                     headers={"Authorization": f"Bearer {token}"},
                                     json={"resolution": resolution, "note": note, "resolved_by": "ui-operator"})
    if response.is_error:
        return _page("Outbox 처리 실패", f"<p class='card'><strong>처리되지 않았습니다.</strong> HTTP {response.status_code}</p>"
                     f"<pre class='card'>{_safe(response.text[:400])}</pre><p><a href='/ops/outbox'>Outbox 목록으로</a></p>")
    return RedirectResponse("/ops/outbox", status_code=303)


@voc_router.get("/voc", response_class=HTMLResponse)
def voc() -> HTMLResponse:
    report = _voc()
    if report is None:
        return _page("VOC 일일 리포트", "<p class='card'>리포트 없음</p>")
    metrics = report["metrics"]
    counts = metrics.get("intent_issue_count") or {}
    today = counts.get("today") or {}
    prior = counts.get("prior_7_days") or {}

    # ★intent → {issue: n} 이 중첩돼 있다. 파이썬 dict 를 그대로 찍으면
    #   `{'charged_after_cancellation': 1}` 처럼 나온다 — 읽으라고 만든 화면이 아니게 된다.
    #   (intent, issue) 로 펴서 한 줄에 하나씩 낸다.
    def _pairs(bucket: dict) -> dict[tuple[str, str], int]:
        flat: dict[tuple[str, str], int] = {}
        for intent, issues in (bucket or {}).items():
            if isinstance(issues, dict):
                for issue, n in issues.items():
                    flat[(str(intent), str(issue))] = n
            else:
                flat[(str(intent), "—")] = issues
        return flat

    today_flat, prior_flat = _pairs(today), _pairs(prior)
    count_rows = []
    for intent, issue in sorted(set(today_flat) | set(prior_flat)):
        # ★"데이터 없음" 과 "미분류" 는 다른 사실이다.
        #   미분류 = 분류가 실패했다 / 없음 = 그 기간에 건이 없었다.
        #   전에는 둘 다 "미분류" 로 찍어 **없는 실패를 있는 것처럼 보고했다.**
        t = today_flat.get((intent, issue))
        p = prior_flat.get((intent, issue))
        count_rows.append(
            f"<tr><th>{_safe(intent)}</th><td>{_safe(issue)}</td>"
            f"<td class='mono'>{_safe(t) if t is not None else '<span class=muted>없음</span>'}</td>"
            f"<td class='mono'>{_safe(p) if p is not None else '<span class=muted>없음</span>'}</td></tr>")
    count_table = theme.table(("intent", "issue_code", "오늘", "직전 7일"), count_rows,
                              empty="집계된 분류가 없습니다")
    alerts = report["alerts"] or []
    if alerts:
        alert_items = alerts if isinstance(alerts, list) else [alerts]
        alert_text = "".join(f"<li>{_safe(a if isinstance(a, str) else json.dumps(a, ensure_ascii=False, default=str))}</li>" for a in alert_items)
        alert_card = theme.card("급증 alert", f"<ul>{alert_text}</ul>", tone="critical",
                                subtitle="즉시 확인이 필요한 변화")
    else:
        alert_card = theme.card("급증 alert", theme.notice("탐지된 급증이 없습니다.", tone="info"),
                                subtitle="v5 §14-3 급증식 기준")

    # ★비율도 dict 로 오면 그대로 찍혔다 — {"today":0.5,"prior_7_days":0.0}.
    #   오늘과 직전 7일은 **비교하라고 있는 숫자**다. 나란히 세운다.
    def _ratio(name: str, key: str) -> str:
        raw = metrics.get(key)
        if not isinstance(raw, dict):
            return theme.stat(name, raw if raw is not None else "미집계")
        now, before = raw.get("today"), raw.get("prior_7_days")
        hint = f"직전 7일 {before:.0%}" if isinstance(before, (int, float)) else "직전 7일 데이터 없음"
        worse = isinstance(now, (int, float)) and isinstance(before, (int, float)) and now > before
        return theme.stat(name, f"{now:.0%}" if isinstance(now, (int, float)) else "미집계",
                          tone="warn" if worse else "", hint=hint)

    totals = metrics.get("totals") or {}
    summary = ("<div class='grid'>"
               + theme.stat("오늘 건수", totals.get("today", "미집계"),
                            hint=f"직전 7일 {totals.get('prior_7_days', '—')}건")
               + _ratio("부정 비율", "negative_ratio")
               + _ratio("미해결 비율", "unresolved_ratio")
               + "</div>"
               + theme.card("집계 기간",
                            theme.kv_table((("기간", f"{report['period_start']} ~ {report['period_end']}"),))))
    counts_card = theme.card("intent / issue count", count_table,
                             subtitle="건이 없는 칸은 0 이 아니라 '없음' 으로 적습니다")
    return _page("VOC 일일 리포트", summary + counts_card + alert_card,
                 current="/ops/voc", lede="분류·이슈 변화와 급증 신호를 확인합니다.")
