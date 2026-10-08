from __future__ import annotations

import hmac
import html
import json
import re
import secrets
from typing import Any
from uuid import UUID

import contextvars
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.core.settings as settings_module
from app import composition
from app.core.project_config import ProjectConfigError
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.db.session import get_ops_read_connection as get_connection
from app.core.remote_team.executor import LocalTeamExecutor
from app.infrastructure.rag import retriever as rag_retriever
from app.core.redaction import masked
from app.presentation.ui import auth, theme

#: 이 요청의 운영자. 관문(`_require_login`)이 채우고 `_page` 가 머리에 적는다.
_OPERATOR: contextvars.ContextVar[auth.Operator | None] = contextvars.ContextVar("ui_operator", default=None)
#: 이 요청의 폼 위조 방지 토큰. 관문이 채우고 `_page` 가 모든 POST 폼에 숨은 칸으로 넣는다. `[2026-09-29]`
_CSRF: contextvars.ContextVar[str | None] = contextvars.ContextVar("ui_csrf", default=None)
_POST_FORM = re.compile(r"(<form\b[^>]*\bmethod=['\"]post['\"][^>]*>)", re.IGNORECASE)


def _with_csrf(page_html: str, token: str | None) -> str:
    """모든 POST 폼(로그아웃 포함)에 숨은 칸 `csrf` 를 넣는다 — 폼마다 손으로 넣다 빠뜨리지 않게 한 곳에서."""
    if not token:
        return page_html
    return _POST_FORM.sub(lambda m: m.group(1) + f"<input type='hidden' name='csrf' value='{html.escape(token)}'>",
                          page_html)


def _csrf_refused() -> HTTPException:
    return HTTPException(403, {"error": {"code": "csrf_failed",
                                         "message": "폼 확인값이 맞지 않는다 — 화면을 다시 열고 누른다. 아무것도 바뀌지 않았다"}})


async def _require_login(request: Request) -> auth.Operator:
    """★`[2026-09-23]` **운영 화면 전체의 관문.** 로그인 안 했으면 로그인 화면으로 보낸다.

    전에는 이 화면 전체에 로그인이 없었는데, 승인·바깥함·위임 버튼이 **서버가 scope 키를 스스로
    만들어** API 를 불렀다 — `/ui` 에 닿기만 하면 인증 없이 승인 권한을 쓰는 구조였다(D-CS-007).
    ★POST 도 같은 데로 보낸다 — 로그인 안 한 요청의 쓰기는 **아무것도 하지 않는다.**
    ★`async` 인 이유 — 동기 의존성은 스레드풀에서 돌아 거기서 설정한 `_OPERATOR` 가 요청 처리로
      **돌아오지 않는다**(실측: 화면 머리에 운영자 이름이 안 나왔다).
    """
    operator = auth.read(request.cookies.get(auth.COOKIE))
    if operator is None:
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise HTTPException(303, headers={"Location": "/ui/login?next=" + quote(target, safe="")})
    token = auth.csrf_for(request.cookies.get(auth.COOKIE) or "")
    if request.method == "POST":
        # ★`[2026-09-29]` 쓰기는 폼 위조 방지 토큰이 맞을 때만 — 다른 사이트가 운영자 브라우저로 승인을 누르게 하지 못하게
        #   (전에는 SameSite 쿠키에만 기댔다 · 운영자 콘솔 분리 Codex 합의 보강). 폼은 한 번 읽으면 끝에서 다시 읽힌다(캐시)
        form = await request.form()
        if not hmac.compare_digest(str(form.get("csrf", "")), token):
            raise _csrf_refused()
    request.state.operator = operator
    _OPERATOR.set(operator)
    _CSRF.set(token)
    return operator


router = APIRouter(prefix="/ui", tags=["operations-ui"], dependencies=[Depends(_require_login)])
ops_router = APIRouter(tags=["operations-ui"], dependencies=[Depends(_require_login)])
# ★VOC 화면만 따로 뗀다. `voc` 모듈을 끄면 이 라우터를 등록하지 않아 /ui/voc 가
#   404 가 된다(`docs/handoff/08` §2). 한 라우터에 섞어 두면 끌 방법이 없다.
voc_router = APIRouter(prefix="/ui", tags=["operations-ui"], dependencies=[Depends(_require_login)])
#: 로그인·로그아웃은 관문 **밖**이다(안에 두면 로그인하러 갈 수가 없다).
login_router = APIRouter(prefix="/ui", tags=["operations-ui"])


#: 지금 화면에 낼 상단 메뉴. `mount_ui()` 가 기동할 때 한 번 정한다.
_NAV: tuple[tuple[str, str], ...] = theme.NAV


def configure_nav(config) -> tuple[tuple[str, str], ...]:
    """꺼진 모듈의 메뉴를 뺀다. 조립 때 한 번만 부른다.

    ★없는 화면으로 가는 링크를 남기면 눌렀을 때 404 가 뜨고, 운영자는 서버가
      죽은 줄 안다. 모듈을 빼면 그 표면도 함께 빠져야 한다.

    ★매 요청마다 선언을 다시 읽지 않는다. 2026-08-30 첫 판이 그렇게 돼 있었다 —
      라우터 등록은 기동 시점에 끝나는데 메뉴만 나중 선언을 보면 둘이 어긋난다.
      메뉴엔 VOC 가 있는데 누르면 404 인 상태가 만들어진다.
      `final_project_sample` 이식(2026-08-31) 중에 발견해 양쪽을 같은 방식으로 맞췄다.
    """
    global _NAV
    _NAV = tuple((href, label) for href, label in theme.NAV
                 if href != "/ui/voc" or config.module_enabled("voc"))
    return _NAV


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _json(value: Any) -> str:
    return _safe(json.dumps(value or {}, ensure_ascii=False, default=str, indent=2))


def _page(title: str, body: str, *, current: str = "", lede: str = "") -> HTMLResponse:
    operator = _OPERATOR.get()
    return HTMLResponse(_with_csrf(theme.page(title, body, current=current, lede=lede, nav=_NAV,
                                              who=operator.id if operator else ""), _CSRF.get()))


def _forbidden(request: Request, scope: str, what: str, back: str) -> HTMLResponse:
    """★권한이 없으면 **아무것도 하지 않고** 그렇다고 말한다. 조용한 303 으로 삼키지 않는다."""
    operator: auth.Operator = request.state.operator
    return HTMLResponse(_with_csrf(theme.page("권한 없음", theme.card(
        f"{_safe(what)} 권한이 없습니다",
        f"<p>이 동작에는 <code>{_safe(scope)}</code> 가 필요합니다. "
        f"<b>{_safe(operator.id)}</b> 계정에는 없습니다.</p>"
        "<p>아무것도 바뀌지 않았습니다.</p>"
        f"<p><a href='{_safe(back)}'>돌아가기</a></p>", tone="critical"),
        nav=_NAV, who=operator.id), _CSRF.get()), status_code=403)


def _safe_next(value: str | None) -> str:
    """★로그인 뒤 돌아갈 곳은 **이 앱 안의 `/ui`·`/ops`** 로만. 바깥 주소를 받으면 로그인 화면이
    피싱 발판이 된다(`?next=https://…`)."""
    target = (value or "").strip()
    parsed = urlparse(target)
    if (parsed.scheme or parsed.netloc or target.startswith("//")
            or not (target.startswith("/ui") or target.startswith("/ops"))):
        return "/ui/cases"
    return target


def _login_page(message: str = "", *, next_url: str = "/ui/cases", status: int = 200,
                csrf: str | None = None) -> HTMLResponse:
    try:
        configured, broken = bool(auth.operators()), ""
    except auth.OperatorConfigError as exc:
        configured, broken = False, str(exc)
    if broken:
        note = theme.notice(f"운영자 설정이 잘못됐습니다 — {_safe(broken)}", tone="critical")
    elif not configured:
        note = theme.notice("운영자 계정이 하나도 설정되지 않았습니다. 이 화면은 닫혀 있습니다 — "
                            "python -m scripts.ui_operator 로 계정 한 줄을 만들어 ACOP_UI_OPERATORS 에 "
                            "넣고 앱을 다시 띄우십시오.", tone="critical")
    else:
        note = theme.notice(message, tone="critical") if message else ""
    csrf = csrf or secrets.token_urlsafe(24)
    form = ("<form method='post' action='/ui/login' class='card'>"
            f"<input type='hidden' name='csrf' value='{_safe(csrf)}'>"
            f"<input type='hidden' name='next' value='{_safe(next_url)}'>"
            "<p><label>운영자 id<br><input name='operator_id' autocomplete='username' required></label></p>"
            "<p><label>비밀번호<br><input name='password' type='password' "
            "autocomplete='current-password' required></label></p>"
            "<p><button type='submit'>로그인</button></p></form>")
    response = HTMLResponse(theme.page("로그인", note + form, nav=(),
                                       lede="운영 화면은 로그인한 운영자만 봅니다."), status_code=status)
    # ★로그인 전 폼 위조 방지 — 폼의 숨은 칸과 이 쿠키가 같아야 로그인을 받는다(이중 제출, 2026-09-29)
    response.set_cookie(auth.CSRF_COOKIE, csrf, httponly=True, samesite="strict", path="/ui/login")
    return response


@login_router.get("/login", response_class=HTMLResponse)
def login_form(next: str | None = None) -> HTMLResponse:  # noqa: A002 — 쿼리 이름이 next 다
    return _login_page(next_url=_safe_next(next))


@login_router.post("/login")
async def login(request: Request):
    form = await request.form()
    operator_id = str(form.get("operator_id", "")).strip()
    next_url = _safe_next(str(form.get("next", "")))
    expected = request.cookies.get(auth.CSRF_COOKIE) or ""
    if not expected or not hmac.compare_digest(str(form.get("csrf", "")), expected):
        return _login_page("화면을 다시 열고 로그인하십시오(폼 확인값이 맞지 않습니다).", next_url=next_url,
                           status=403)
    try:
        remaining = auth.locked(operator_id)
        operator = None if remaining else auth.authenticate(operator_id, str(form.get("password", "")))
    except auth.OperatorConfigError:
        return _login_page(next_url=next_url, status=503)
    if remaining:
        return _login_page(f"로그인 실패가 많아 잠시 막혔습니다 — 약 {int(remaining // 60) + 1}분 뒤 "
                           "다시 시도하십시오.", next_url=next_url, status=429)
    if operator is None:
        # ★없는 id 와 틀린 비밀번호를 같은 문장으로 — 어느 id 가 있는지 알려 주지 않는다
        return _login_page("id 또는 비밀번호가 맞지 않습니다.", next_url=next_url, status=401)
    hours = float(settings_module.get_guardrails().get("security.ui_session_hours"))
    response = RedirectResponse(next_url, status_code=303)
    response.set_cookie(auth.COOKIE, auth.issue(operator), httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", path="/", max_age=int(hours * 3600))
    return response


@login_router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/ui/login", status_code=303)
    response.delete_cookie(auth.COOKIE, path="/")
    return response


def _legacy_page(title: str, body: str) -> HTMLResponse:
    nav = "<nav><a href='/ui/cases'>Cases</a><a href='/ui/approvals'>Approvals</a><a href='/ui/voc'>VOC</a><a href='/ui/admin'>Admin</a></nav>"
    return HTMLResponse(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_safe(title)}</title><style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033;background:#f7f8fb}}nav{{display:flex;gap:1rem;margin-bottom:2rem}}a{{color:#155eef}}.card{{background:white;border:1px solid #dfe3eb;border-radius:12px;padding:1rem;margin:.8rem 0;box-shadow:0 2px 8px #1822300d}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;padding:.7rem;border-bottom:1px solid #e7eaf0;vertical-align:top}}th{{font-size:.8rem;color:#5c667a}}code,pre{{white-space:pre-wrap;word-break:break-word}}.muted{{color:#667085}}.badge{{display:inline-block;background:#eef4ff;color:#174ea6;border-radius:99px;padding:.2rem .6rem;font-size:.8rem}}button{{padding:.5rem .8rem;border:0;border-radius:7px;background:#155eef;color:white;cursor:pointer}}button:disabled{{background:#aab2c0;cursor:not-allowed}}.danger{{background:#b42318}}.evidence{{border-left:3px solid #12b76a;padding-left:.7rem;margin:.5rem 0}}</style></head><body>{nav}<h1>{_safe(title)}</h1>{body}</body></html>")


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
    """Return unresolved unknown messages for the current tenant."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT message_id, topic, payload_json, attempts, last_error, available_at, locked_at "
            "FROM outbox WHERE tenant_id=%s AND status='unknown' AND resolved_at IS NULL "
            "ORDER BY available_at, message_id", (_tenant(),))
        keys = ("message_id", "topic", "payload", "attempts", "last_error", "available_at", "locked_at")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


def _graph_port_name(tenant: str) -> str:
    """관리자 화면에 적을 GraphStorePort 구현 이름. 꺼져 있으면 껐다고 적는다.

    ★어댑터를 직접 만들지 않는다. 2026-08-30 이전에는 이 화면이 SqlGraphAdapter 를
      바로 생성해서, graph_store 모듈을 꺼도 Graph 줄이 그대로 떴다 —
      `docs/handoff/08` §6 검증기 4번이 잡아야 할 "꺼진 모듈을 부르는 경로"였다.
    ★빈칸으로 두지 않는다. 빈칸은 "껐다"와 "고장났다"를 구별해 주지 못한다.
    """
    try:
        return type(composition.build_graph_store(connection=None, tenant_id=tenant)).__name__
    except ProjectConfigError:
        return "모듈 꺼짐 (graph_store)"


def _admin_snapshot() -> dict[str, Any]:
    """Read-only projection of the composition and tenant-scoped operations state."""
    tenant = _tenant()
    registry = composition.build_registry()
    settings = settings_module.get_settings()
    guardrails = settings_module.get_guardrails().as_dict()
    # These are the concrete objects assembled by the composition boundary.
    # The graph adapter only needs a connection when a query runs; this page
    # intentionally executes none, so it passes None.
    executor = LocalTeamExecutor(registry)
    broker = OutboxBrokerAdapter(get_connection)
    graph_name = _graph_port_name(tenant)
    llm = OpenAITeamLLM()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s", (tenant,))
        document_count = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM knowledge_chunks kc
                       JOIN knowledge_documents kd ON kd.document_id=kc.document_id
                       WHERE kd.tenant_id=%s""", (tenant,))
        chunk_count = cur.fetchone()[0]
        cur.execute("SELECT status, count(*) FROM customer_cases WHERE tenant_id=%s GROUP BY status ORDER BY status", (tenant,))
        case_statuses = dict(cur.fetchall())
        cur.execute("SELECT status, count(*) FROM outbox WHERE tenant_id=%s GROUP BY status ORDER BY status", (tenant,))
        outbox_statuses = dict(cur.fetchall())
    return {
        "manifests": registry.manifests(),
        "ports": [
            ("TeamExecutorPort", type(executor).__name__),
            ("MessageBrokerPort", type(broker).__name__),
            ("GraphStorePort", graph_name),
            ("Vector 검색", f"{rag_retriever.__name__}.{rag_retriever.search_policy.__name__}"),
            ("LLM", type(llm).__name__),
        ],
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_key": "sk-****" if settings.openai_api_key else "없음",
        "guardrails": guardrails,
        "document_count": document_count,
        "chunk_count": chunk_count,
        "case_statuses": case_statuses,
        "outbox_statuses": outbox_statuses,
    }


def _admin_value(value: Any) -> str:
    return _json(value) if isinstance(value, (dict, list, tuple)) else _safe(value)


@router.get("/admin", response_class=HTMLResponse)
def admin() -> HTMLResponse:
    data = _admin_snapshot()
    cases_by_status = data["case_statuses"]
    outbox_by_status = data["outbox_statuses"]

    # ★unknown 은 "돈이 나갔는지 모르는" 상태다. 숫자 하나로 크게 띄운다.
    unknown_n = outbox_by_status.get("unknown", 0)
    dead_n = outbox_by_status.get("dead_letter", 0)
    overview = "<div class='grid'>" + "".join((
        theme.stat("Agent Team", len(data["manifests"])),
        theme.stat("지식 문서", data["document_count"]),
        theme.stat("지식 청크", data["chunk_count"]),
        theme.stat("Case", sum(cases_by_status.values())),
        theme.stat("outbox unknown", unknown_n, tone="critical" if unknown_n else "",
                   hint="사람이 provider 를 조회해야 합니다" if unknown_n else ""),
        theme.stat("dead letter", dead_n, tone="critical" if dead_n else ""),
    )) + "</div>"

    team_rows = [
        "<tr>"
        f"<td class='mono'>{_safe(m.team_id)}</td>"
        f"<td>{_safe(m.display_name)}</td>"
        f"<td>{theme.pill('active' if m.active else 'cancelled', label='active' if m.active else 'inactive')}</td>"
        f"<td>{_safe(', '.join(m.capabilities))}</td>"
        f"<td>{_safe(', '.join(m.allowed_tools))}</td>"
        f"<td>{_safe(', '.join(m.knowledge_scope))}</td>"
        f"<td class='mono'>{_safe(m.max_steps)}</td>"
        f"<td class='mono'>{_safe(m.implementation_revision)}</td>"
        "</tr>" for m in data["manifests"]]
    teams = theme.card(
        "Agent Team Modules",
        theme.table(("team_id", "이름", "상태", "capabilities", "allowed_tools",
                     "knowledge_scope", "max_steps", "revision"), team_rows),
        subtitle="Registry 가 실제로 들고 있는 것")

    port_rows = [f"<tr><td class='mono'>{_safe(p)}</td><td class='mono'>{_safe(impl)}</td></tr>"
                 for p, impl in data["ports"]]
    ports = theme.card(
        # ★엔티티를 직접 넣지 않는다 — theme.card() 가 esc() 를 하므로 이중 이스케이프된다
        #   ("Ports &amp;amp; Adapters" 로 화면에 떴다).
        "Ports & Adapters",
        theme.table(("Port", "현재 구현"), port_rows)
        + theme.kv_table((("LLM provider", data["llm_provider"]),
                          ("LLM model", data["llm_model"]),
                          ("API key", data["llm_key"]))),
        subtitle="교체점 — 구현을 바꿔 끼우는 자리")

    # ★가드레일을 JSON 덩어리로 던지지 않는다. 평평하게 펴서 읽을 수 있게 만든다.
    guard = theme.card("Guardrails", theme.kv_table(_flatten(data["guardrails"])),
                       subtitle="config/guardrails.yaml 단일 출처")

    health = theme.card(
        "상태 분포",
        "<h3>Case status</h3>" + theme.distribution(cases_by_status)
        + "<h3>Outbox status</h3>" + theme.distribution(outbox_by_status),
        subtitle="tenant 범위")

    return _page("Basement Admin", overview + teams + ports + guard + health,
                 current="/ui/admin", lede="tenant 범위 읽기 전용 뷰입니다. 여기서는 아무것도 바꾸지 않습니다.")


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """중첩 dict 를 `a.b.c` 키로 펴서 표에 넣을 수 있게 한다."""
    out: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, sub in value.items():
            out.extend(_flatten(sub, f"{prefix}.{key}" if prefix else str(key)))
    else:
        out.append((prefix, value))
    return out


@router.get("/cases", response_class=HTMLResponse)
def cases() -> HTMLResponse:
    rows = _cases()
    if not rows:
        return _page("Case 목록", theme.empty_state(
            "표시할 Case가 없습니다.",
            hint="`python -m scripts.seed_demo_cases` 로 시연용 Case 를 만들 수 있습니다."),
            current="/ui/cases")

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
        f"<td><a class='mono' href='/ui/cases/{r['case_id']}'>{_safe(masked(r['case_id']))}</a></td>"
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
                 current="/ui/cases",
                 lede="분류 실패는 빈칸이 아니라 '미분류'로 적습니다 — 추정으로 채우지 않습니다.")


@router.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Case 상세", theme.empty_state("Case를 찾을 수 없습니다."), current="/ui/cases")

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
            f"<a href='/ui/cases/{case_id}/trace'><button>Trace 타임라인 보기</button></a></div>")
    return _page("Case 상세", banner + head + evidence + raw + link, current="/ui/cases")


@router.get("/cases/{case_id}/trace", response_class=HTMLResponse)
def trace(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Trace", theme.empty_state("Case를 찾을 수 없습니다."), current="/ui/cases")

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
                 note + theme.card(None, timeline), current="/ui/cases",
                 lede=f"case {case_id}")


@router.get("/approvals", response_class=HTMLResponse)
def approvals() -> HTMLResponse:
    rows = _actions()
    if not rows:
        return _page("Approval", theme.empty_state("대기 중인 승인 요청이 없습니다."),
                     current="/ui/approvals")

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
            + f"<form class='actions' method='post' action='/ui/approvals/{r['case_id']}/{r['action_id']}'>"
              f"<button name='decision' value='approved'{disabled}>승인</button>"
              f"<button class='ghost' name='decision' value='rejected'{disabled}>거절</button></form>",
            subtitle=str(r["status"]),
            tone="critical" if not evidence else "warn"))

    return _page("Approval", summary + "".join(cards), current="/ui/approvals",
                 lede="승인은 되돌릴 수 없습니다. 근거를 먼저 읽고 누르십시오.")


@router.post("/approvals/{case_id}/{action_id}")
async def approve(request: Request, case_id: UUID, action_id: UUID):
    operator: auth.Operator = request.state.operator
    if not operator.can("action:approve"):
        return _forbidden(request, "action:approve", "승인", "/ui/approvals")
    form = await request.form()
    decision = str(form.get("decision", "rejected"))
    response = await _call_api(request, "POST", f"/v1/cases/{case_id}/actions/{action_id}/approve",
                               scope="action:approve", payload={"decision": decision, "approver_id": operator.id})
    # ★두 분기가 같은 응답을 내고 있었다 — 승인이 실패해도 운영자는 목록으로 돌아올 뿐
    #   무엇이 잘못됐는지 알 수 없었다. 승인은 되돌릴 수 없는 행위인데 실패를 삼키면
    #   "눌렀으니 됐겠지" 로 넘어간다 (CLAUDE.md §3 — 조용한 스킵을 만들지 않는다).
    if response.is_error:
        detail = _safe(response.text[:400]) or f"HTTP {response.status_code}"
        return _page("Approval 실패", (
            f"<p class='card'><strong>승인이 처리되지 않았습니다.</strong> "
            f"HTTP {response.status_code}</p><pre class='card'>{detail}</pre>"
            "<p><a href='/ui/approvals'>승인 목록으로</a></p>"))
    return RedirectResponse("/ui/approvals", status_code=303)


# ── 위임 — 승인 뒤 자동 실행을 여는 둘째 문 ────────────────────────────────────
# ★이 층은 도메인을 모른다(INV-CS-ARCH-001). 그래서 SQL 도 설정도 직접 읽지 않고,
#   조립이 붙인 도메인 경로 `/v1/delegations` 를 **같은 프로세스 안에서** 불러 그 응답을
#   그린다. 한계 값의 이름표(`limits[].label`·`value`)도 도메인이 붙여 준다 —
#   화면은 표로 그릴 뿐 그 숫자가 무슨 뜻인지 모른다.
# ★`/ui/scenario` 가 도메인 경로를 부르는 것과 같은 모양이되, **서버에서 그린다** —
#   화면이 200 을 내면서 비어 있던 사고가 이 저장소에 있었다. 브라우저 JS 로 그리면
#   그 상태를 시험이 못 본다.
_DELEGATION_PATH = "/v1/delegations"

#: 시험이 고객 API 앱을 이 자리에 끼운다. 실제 운영에서는 비어 있어 **진짜 HTTP** 로 간다.
API_TRANSPORT: httpx.AsyncBaseTransport | None = None


def _api_key(scope: str) -> str | None:
    """운영 앱의 scope 키 — 설정 `ACOP_OPS_API_KEYS`(JSON)에서만 읽는다. ★스스로 만들지 않는다."""
    raw = (getattr(settings_module.get_settings(), "ops_api_keys", "") or "").strip()
    try:
        keys = json.loads(raw) if raw else {}
    except ValueError:
        return None
    key = keys.get(scope) if isinstance(keys, dict) else None
    return str(key) if key else None


def _problem(status: int, code: str, message: str) -> httpx.Response:
    """부르지 못한 이유를 응답 모양으로 — 화면의 실패 경로가 그대로 그린다(조용히 삼키지 않는다)."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


async def _call_api(request: Request, method: str, path: str, *, scope: str,
                    payload: dict[str, Any] | None = None) -> httpx.Response:
    """**고객 API** 를 실제 HTTP 로 부른다(`ACOP_OPS_API_BASE_URL`). `[2026-09-29]` 운영자 콘솔 분리

    ★전에는 같은 프로세스 안에서(`ASGITransport(app=request.app)`) 서버 비밀키로 scope 키를 **만들어** 불렀다 —
      운영 화면이 고객 앱 안에 붙어 있어야만 되는 구조였다. 이제 운영 앱은 다른 프로세스라 실제로 부르고,
      키는 운영 앱 설정에만 둔다(`ACOP_OPS_API_KEYS`).
    ★시간 초과는 **결과를 모른다**는 뜻이다 — 다시 누르기 전에 목록에서 상태를 보라고 적는다. 스스로 다시 부르지 않는다.
      같은 승인을 두 번 보내도 두 번 실행되지 않는다(상태기계가 둘째를 거부한다).
    """
    token = _api_key(scope)
    if token is None:
        return _problem(503, "ops_api_key_missing",
                        f"운영 앱에 {scope} 키가 설정되지 않았다(ACOP_OPS_API_KEYS) — 아무것도 보내지 않았다")
    settings = settings_module.get_settings()
    timeout = float(settings_module.get_guardrails().get("security.ops_api_timeout_seconds"))
    try:
        async with httpx.AsyncClient(transport=API_TRANSPORT, base_url=settings.ops_api_base_url.rstrip("/"),
                                     timeout=timeout) as client:
            return await client.request(method, path, headers={"Authorization": f"Bearer {token}"}, json=payload)
    except httpx.TimeoutException:
        return _problem(504, "ops_api_timeout", "고객 API 가 제때 답하지 않았다 — 처리됐는지 모른다. "
                                                "다시 누르기 전에 목록에서 지금 상태를 확인한다")
    except httpx.HTTPError as exc:
        return _problem(502, "ops_api_unreachable", f"고객 API 에 닿지 못했다 — 아무것도 바뀌지 않았다 ({type(exc).__name__})")


def _failure_page(title: str, headline: str, response: httpx.Response, back: str) -> HTMLResponse:
    """★실패를 삼키지 않는다 — 무엇이 왜 안 됐는지 화면에 적는다.

    승인 화면에서 배운 것이다(2026-09-05): 성공과 실패가 같은 303 을 내던 동안
    운영자는 "눌렀으니 됐겠지" 로 넘어갔다. 되돌릴 수 없는 행위에서 가장 위험한 형태다.
    """
    reason = _safe(response.text[:600]) or f"HTTP {response.status_code}"
    return _page(title, theme.card(
        headline,
        f"<p>요청이 처리되지 않았습니다. HTTP {response.status_code}</p>"
        f"<pre>{reason}</pre>"
        f"<p><a href='{back}'>목록으로 돌아가기</a></p>", tone="critical"),
        current="/ui/delegations")


def _limits_table(limits: list[dict[str, Any]]) -> str:
    return theme.kv_table(tuple((row.get("label", ""), row.get("value", "")) for row in limits))


def _change_form(customer_id: str, action: str, label: str, *, ghost: bool = False) -> str:
    """한 줄짜리 상태 변경 폼. ★누가·왜 를 안 적으면 누를 수 없다(필수 입력)."""
    css = " class='ghost'" if ghost else ""
    return (f"<form class='deleg-form' method='post' action='/ui/delegations'>"
            f"<input type='hidden' name='action' value='{_safe(action)}'>"
            f"<input type='hidden' name='customer_id' value='{_safe(customer_id)}'>"
            f"<input name='actor_id' required minlength='1' placeholder='누가 (담당자)'>"
            f"<input name='note' required minlength='1' placeholder='왜 (근거)'>"
            f"<button{css}>{_safe(label)}</button></form>")


# ★브라우저로 열어 보고 고쳤다(2026-09-22). 폼 입력이 min-width 를 밀어 표가 넓어지자
#   「근거」칸이 **한 줄에 한 글자씩** 접혀 읽을 수 없었다. 운영자가 읽으려고 만든 칸이
#   읽히지 않으면 없는 것과 같다. 시각도 마이크로초까지 나와 세 줄로 접혔다 —
#   분까지만 보이고 원값은 title 로 남긴다(자르지만 버리지는 않는다).
_DELEG_CSS = """<style>
.deleg-form{display:flex;gap:.4rem;flex-wrap:wrap;align-items:center;margin:0}
.deleg-form input{font-size:.82rem;padding:.35rem .5rem;min-width:8rem}
.deleg-form button{padding:.35rem .8rem;font-size:.82rem}
td.deleg-note{min-width:11rem}
td.deleg-when,td.deleg-act{white-space:nowrap}
</style>"""


def _when(value: Any) -> str:
    """시각을 분까지만 보인다. ★원값은 title 에 남긴다 — 로그와 대조할 수 있어야 한다."""
    if not value:
        return "—"
    text = str(value)
    return f"<span title='{_safe(text)}'>{_safe(text[:16].replace('T', ' '))}</span>"


@router.get("/delegations", response_class=HTMLResponse)
async def delegations(request: Request) -> HTMLResponse:
    """위임 현황 — 누구에게 살아 있나 · 무엇을 맡긴 것인가 · 얼마가 이미 나갔나."""
    response = await _call_api(request, "GET", _DELEGATION_PATH, scope="delegation:read")
    if response.is_error:
        # ★빈 화면을 내지 않는다. 조립에 도메인 경로가 없으면 그 사실이 보여야 한다.
        return _failure_page("위임", "현황을 읽지 못했습니다", response, "/ui/cases")
    data = response.json()
    rows = data.get("rows") or []
    counts = data.get("counts") or {}

    warning = theme.notice(
        "위임을 주면 이 고객 건은 승인 뒤 사람 손 없이 업체 원장까지 반영됩니다. "
        "아래 범위를 벗어난 건은 그래도 사람에게 옵니다. 거두면 그 순간부터 막히며, "
        "이미 나간 건은 되돌림 경로로만 무를 수 있습니다.", tone="critical")
    summary = "<div class='grid'>" + "".join((
        theme.stat("살아 있는 위임", counts.get("live", 0),
                   tone="warn" if counts.get("live") else "",
                   hint="자동 실행이 열려 있습니다" if counts.get("live") else ""),
        theme.stat("거둔 위임", counts.get("revoked", 0)),
        theme.stat("기록 전체", counts.get("total", 0)),
    )) + "</div>"
    limits = theme.card("지금 맡기는 범위", _limits_table(data.get("limits") or []),
                        subtitle="config/guardrails.yaml 단일 출처 — 화면에서 바꾸지 않습니다")

    body_rows = []
    for row in rows:
        customer = str(row.get("customer_id"))
        live = row.get("state") == "live"
        action, label = ("revoke", "거두기") if live else ("grant", "다시 주기")
        body_rows.append(
            "<tr>"
            f"<td class='mono'>{_safe(customer)}</td>"
            f"<td>{theme.pill(row.get('state'), label='살아 있음' if live else '거둠')}</td>"
            f"<td class='muted deleg-when'>{_when(row.get('granted_at'))}<br>"
            f"{_safe(row.get('granted_by') or '기록 없음')}</td>"
            f"<td class='muted deleg-when'>{_when(row.get('revoked_at'))}<br>"
            f"{_safe(row.get('revoked_by') or '—')}</td>"
            f"<td class='mono'>{_safe(row.get('spent_label'))}</td>"
            f"<td class='mono'>{_safe(row.get('remaining_label'))}</td>"
            f"<td class='deleg-note'>{_safe(row.get('note') or '—')}</td>"
            f"<td class='deleg-act'>{_change_form(customer, action, label, ghost=live)}</td>"
            "</tr>")
    listing = theme.card(
        "위임 기록", theme.table(
            ("customer", "상태", "준 시각 · 사람", "거둔 시각 · 사람", "이미 나간 금액",
             "남은 여유", "근거", ""),
            body_rows, empty="위임 기록이 없습니다 — 아무에게도 자동 실행이 열려 있지 않습니다"),
        subtitle="이미 나간 금액은 판정이 쓰는 것과 같은 셈입니다")

    grant_card = theme.card(
        "새로 맡기기",
        "<p class='muted'>고객 id 는 Case 목록·상세에서 확인합니다. 누르면 "
        "<strong>무엇이 열리는지 먼저 보여 드리고</strong> 다시 한 번 확인합니다.</p>"
        "<form class='deleg-form' method='post' action='/ui/delegations'>"
        "<input type='hidden' name='action' value='grant'>"
        "<input name='customer_id' required minlength='1' placeholder='customer_id (UUID)' "
        "style='min-width:20rem'>"
        "<input name='actor_id' required minlength='1' placeholder='누가 (담당자)'>"
        "<input name='note' required minlength='1' placeholder='왜 (근거)'>"
        "<button>확인 화면으로</button></form>", tone="warn")

    return _page("위임", _DELEG_CSS + warning + summary + limits + listing + grant_card,
                 current="/ui/delegations",
                 lede="승인 뒤 자동 실행을 여는 둘째 문입니다. 승인 자체를 대신하지 않습니다.")


def _confirm_page(customer_id: str, actor_id: str, note: str, detail: dict[str, Any]) -> HTMLResponse:
    """★되돌릴 수 없는 쪽(맡기기)은 **무엇이 바뀌는지 먼저 보여 준다.**

    거두기는 이 단계를 두지 않는다 — 막는 방향이고, 한 번 더 묻는 사이에 자동 실행이
    나갈 수 있다.
    """
    state = detail.get("state")
    already = state == "live"
    history = detail.get("history") or []
    past = "".join(
        f"<li>{_when(e.get('at'))} · <strong>{_safe(e.get('action'))}</strong> · "
        f"{_safe(e.get('actor_id') or '기록 없음')} — {_safe(e.get('note') or '근거 없음')}</li>"
        for e in history[:10])
    facts = theme.kv_table((
        ("customer", customer_id),
        ("지금 상태", "살아 있음" if already else ("거둠" if state == "revoked" else "기록 없음")),
        ("이미 나간 금액", detail.get("spent_label")),
        ("남은 여유", detail.get("remaining_label")),
        ("맡기는 사람", actor_id),
        ("근거", note),
    ))
    notice = theme.notice(
        "이미 살아 있는 위임입니다. 다시 맡기면 준 시각이 지금으로 바뀝니다."
        if already else
        "확인을 누르면 이 고객 건은 승인 뒤 사람 손 없이 업체 원장까지 반영됩니다.",
        tone="warn" if already else "critical")
    form = ("<form class='deleg-form' method='post' action='/ui/delegations'>"
            "<input type='hidden' name='action' value='grant'>"
            "<input type='hidden' name='confirm' value='yes'>"
            f"<input type='hidden' name='customer_id' value='{_safe(customer_id)}'>"
            f"<input type='hidden' name='actor_id' value='{_safe(actor_id)}'>"
            f"<input type='hidden' name='note' value='{_safe(note)}'>"
            "<button>확인 — 맡긴다</button></form>"
            "<p><a href='/ui/delegations'>취소하고 목록으로</a></p>")
    body = (_DELEG_CSS + notice
            + theme.card("맡길 대상", facts, tone="critical")
            + theme.card("이 범위가 열립니다", _limits_table(detail.get("limits") or []),
                         subtitle="벗어난 건은 그대로 사람에게 옵니다")
            + theme.card("지금까지 주고 거둔 기록",
                         f"<ul>{past}</ul>" if past else theme.notice("기록 없음", tone="info"),
                         subtitle="덧붙이기만 합니다 — 지우거나 고치지 않습니다")
            + theme.card(None, form))
    return _page("위임 — 확인", body, current="/ui/delegations",
                 lede="누르기 전에 무엇이 열리는지 읽으십시오.")


@router.post("/delegations")
async def change_delegation(request: Request):
    """맡기기 · 거두기 — 도메인 API 로 보내고 **실패하면 사유를 화면에 띄운다.**"""
    # ★`[2026-09-23]` 전에는 `ui_delegation_write_enabled`(기본 꺼짐)로 막았다 — 이 화면에 로그인이
    #   없어서였다. 이제 관문이 로그인을 요구하고, 위임을 바꾸려면 **그 운영자에게 `delegation:write`**
    #   가 있어야 한다. 스위치 대신 권한이 막는다(D-CS-007).
    operator: auth.Operator = request.state.operator
    if not operator.can("delegation:write"):
        return _forbidden(request, "delegation:write", "위임 변경", "/ui/delegations")
    form = await request.form()
    action = str(form.get("action", ""))
    customer_id = str(form.get("customer_id", "")).strip()
    # ★누가 했는지는 **로그인한 운영자**다. 입력 칸의 값을 믿으면 남의 이름으로 맡기고 거둘 수 있다.
    actor_id = operator.id
    note = str(form.get("note", "")).strip()

    if action not in ("grant", "revoke"):
        return _page("위임 처리 실패", theme.card(
            "알 수 없는 요청", f"<p>지원하지 않는 동작입니다: <code>{_safe(action)}</code></p>"
            "<p><a href='/ui/delegations'>목록으로 돌아가기</a></p>", tone="critical"),
            current="/ui/delegations")
    try:
        UUID(customer_id)
    except ValueError:
        # ★서버까지 보내지 않고 여기서 막는다. 형식이 틀린 id 는 422 로 돌아와
        #   "무엇이 잘못됐는지" 가 오히려 흐려진다.
        return _page("위임 처리 실패", theme.card(
            "고객 id 형식이 아닙니다",
            f"<p>입력한 값: <code>{_safe(customer_id) or '(비어 있음)'}</code></p>"
            "<p>Case 목록·상세의 customer_id(UUID)를 그대로 붙여 넣으십시오.</p>"
            "<p><a href='/ui/delegations'>목록으로 돌아가기</a></p>", tone="critical"),
            current="/ui/delegations")

    if action == "grant" and str(form.get("confirm", "")) != "yes":
        detail = await _call_api(request, "GET", f"{_DELEGATION_PATH}/{customer_id}",
                                 scope="delegation:read")
        if detail.is_error:
            return _failure_page("위임 처리 실패", "이 고객을 확인하지 못했습니다", detail,
                                 "/ui/delegations")
        return _confirm_page(customer_id, actor_id, note, detail.json())

    response = await _call_api(request, "POST", f"{_DELEGATION_PATH}/{customer_id}/{action}",
                               scope="delegation:write",
                               payload={"actor_id": actor_id, "note": note})
    if response.is_error:
        headline = "맡기지 못했습니다" if action == "grant" else "거두지 못했습니다"
        return _failure_page("위임 처리 실패", headline, response, "/ui/delegations")
    return RedirectResponse("/ui/delegations", status_code=303)


@router.get("/ops/outbox", response_class=HTMLResponse)
def outbox() -> HTMLResponse:
    rows = _unknown_outbox()
    if not rows:
        return _page("Outbox · unknown", theme.empty_state(
            "미해결 unknown 메시지가 없습니다.",
            hint="unknown은 자동 재실행되지 않으며, 사람이 확인한 근거만 기록할 수 있습니다."),
            current="/ops/outbox")
    cards = []
    for row in rows:
        message_id = row["message_id"]
        facts = theme.kv_table((
            ("message_id", masked(message_id)), ("topic", row["topic"]),
            ("attempts", row["attempts"]), ("last_error", row["last_error"] or "—"),
            ("available_at", row["available_at"]), ("locked_at", row["locked_at"] or "—"),
        ))
        form = (f"<form method='post' action='/ops/outbox/{message_id}'>"
                "<label class='field'>확인 근거 (필수)"
                "<input name='note' required minlength='1' placeholder='하류 시스템 조회 결과와 확인 근거를 적으세요'></label>"
                "<div class='actions'>"
                "<button name='resolution' value='confirmed_delivered'>배달 완료 확인</button>"
                "<button class='ghost' name='resolution' value='confirmed_not_delivered'>미배달 확인</button>"
                "</div></form>")
        cards.append(theme.card("unknown 메시지", facts + theme.details(
            "payload_json", f"<pre>{_json(row['payload'])}</pre>") + form,
            subtitle="자동 재실행 없음 · 확인 기록만 저장", tone="critical"))
    return _page("Outbox · unknown", "".join(cards), current="/ops/outbox",
                 lede="하류 시스템을 직접 확인한 뒤, 근거와 결론을 기록하십시오. 이 화면은 메시지를 재발행하지 않습니다.")


@router.post("/ops/outbox/{message_id}")
async def resolve_outbox(request: Request, message_id: UUID):
    operator: auth.Operator = request.state.operator
    if not operator.can("action:approve"):
        return _forbidden(request, "action:approve", "바깥함 해소", "/ops/outbox")
    form = await request.form()
    response = await _call_api(request, "POST", f"/v1/outbox/{message_id}/resolve", scope="action:approve",
                               payload={"resolution": str(form.get("resolution", "")),
                                        "note": str(form.get("note", "")), "resolved_by": operator.id})
    if response.is_error:
        return _page("Outbox 처리 실패", theme.card(
            "처리되지 않았습니다", f"<p>HTTP {response.status_code}</p><pre>{_safe(response.text[:400])}</pre>"),
            current="/ops/outbox")
    return RedirectResponse("/ops/outbox", status_code=303)


# The customer-facing operations navigation uses /ui; keep the historical
# operator URL as a first-class alias without duplicating its implementation.
ops_router.add_api_route("/ops/outbox", outbox, methods=["GET"], response_class=HTMLResponse)
ops_router.add_api_route("/ops/outbox/{message_id}", resolve_outbox, methods=["POST"])


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
                 current="/ui/voc", lede="분류·이슈 변화와 급증 신호를 확인합니다.")
