"""분리된 개발 콘솔 화면.

★대상의 `theme.py` 를 가져오지 않는다 (`CLAUDE.md` §0.2).
  이 프로그램의 화면은 이 프로그램이 만든다 — **대상이 하나도 없어도 떠야** 하기 때문이다.

★없는 것을 `0` 으로 채우지 않는다. `모름` 이라고 적는다.
★조용히 자르지 않는다. N개만 보이면 "전체 M개 중 M−N개는 화면에 없다" 를 적는다.
"""
from __future__ import annotations

import html
import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from console import composer as composer_client
from console.db import read_agent_runs, read_trace
from console.discovery import discover, inspect_path
from console.live import read_introspection
from console.profiles import profile_for
from console.readers import (judgement_counts, read_declaration, read_eval_runs,
                             read_guardrails, read_judgements)

#: 기본으로 훑을 루트. 이 저장소의 부모 = 형제 프로젝트들이 있는 곳.
DEFAULT_ROOT = Path(__file__).resolve().parents[2]

#: ★CSRF 토큰 — 프로세스마다 새로 만든다. 디스크에 저장하지 않는다.
#:
#:   왜 필요한가: 이 콘솔이 켜져 있는 동안 운영자가 **악성 웹페이지를 열면**,
#:   그 페이지가 `127.0.0.1:<port>/composer` 로 form POST 를 보낼 수 있다.
#:   폼 POST 는 CORS preflight 대상이 아니라 브라우저가 막지 않는다. 응답은
#:   못 읽어도 **부작용(대상 config `apply`)은 일어난다** — 그것도 이 프로세스가
#:   환경변수로 들고 있는 issuer secret 으로. (2026-08-19 인수인계 점검)
#:
#:   토큰은 우리가 그린 폼에만 들어 있고, 공격자 페이지는 동일출처 정책 때문에
#:   그 값을 **읽을 수 없다.** 그래서 위조할 수 없다.
#:
#:   ★이 때문에 `POST /composer` 는 **화면을 거쳐야만** 쓸 수 있다. 스크립트로
#:   자동화하려면 이 콘솔이 아니라 **대상의 `/composer/*` API 를 직접** 부르는 게
#:   맞다 — 그게 원래 계약이다(`CLAUDE.md` §0.3).
_CSRF_TOKEN = secrets.token_urlsafe(32)

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{--bg:#f5f7fa;--surface:#fff;--line:#e3e8ef;--text:#131a26;--dim:#5d6b7f;
 --accent:#2f5bd8;--ok:#0d7a4d;--warn:#9a6200;--bad:#c0362c;--idle:#5d6b7f;
 --mono:ui-monospace,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d1219;--surface:#161d27;--line:#28323f;
 --text:#e7ecf3;--dim:#93a1b4;--accent:#7aa2f7;--ok:#5bd6a0;--warn:#f2bd5c;--bad:#ff8b80;--idle:#93a1b4}}
body{margin:0;background:var(--bg);color:var(--text);font-size:15px;line-height:1.55;
 font-family:system-ui,"Segoe UI","Noto Sans KR",sans-serif}
.shell{max-width:1100px;margin:0 auto;padding:1.5rem 1.25rem 4rem}
.topbar{position:sticky;top:0;z-index:10;background:var(--surface);border-bottom:1px solid var(--line)}
.topbar__in{max-width:1100px;margin:0 auto;padding:.55rem 1.25rem;display:flex;align-items:center;gap:1rem}
.brand{font-weight:700;white-space:nowrap}
.topbar nav{display:flex;gap:.25rem;flex-wrap:wrap}
.topbar nav a,.topbar nav .nav-disabled{display:inline-block;padding:.3rem .65rem;border-radius:7px;text-decoration:none}
.topbar nav a{color:var(--text)}
.topbar nav a:hover{background:var(--bg)}
.topbar nav a[aria-current='page']{background:var(--accent);color:var(--surface);font-weight:600}
.topbar nav .nav-disabled{color:var(--dim);cursor:not-allowed}
a{color:var(--accent)}
h1{font-size:1.45rem;letter-spacing:-.02em;margin:.2rem 0 .3rem}
h2{font-size:1rem;margin:0}
.lede{color:var(--dim);margin:0 0 1.5rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
 padding:1rem 1.15rem;margin-bottom:1rem}
.card h2{margin-bottom:.7rem}
.grid{display:grid;gap:.9rem;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:1rem}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.85rem 1rem}
.stat b{display:block;font-size:1.55rem;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.stat span{font-size:.76rem;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.stat small{color:var(--dim);font-size:.8rem}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:.55rem .65rem;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
.mono{font-family:var(--mono);white-space:nowrap}
.dim{color:var(--dim)}
.pill{display:inline-block;border-radius:99px;padding:.1rem .55rem;font-size:.76rem;font-weight:600}
.p-ok{background:#e6f6ee;color:#0d7a4d}.p-warn{background:#fff6e2;color:#9a6200}
.p-bad{background:#fdecea;color:#c0362c}.p-idle{background:#eef1f6;color:#5d6b7f}
@media(prefers-color-scheme:dark){.p-ok{background:#12332a;color:#5bd6a0}
 .p-warn{background:#3a2c12;color:#f2bd5c}.p-bad{background:#3a1c1a;color:#ff8b80}
 .p-idle{background:#212a36;color:#93a1b4}}
.note{border:1px solid currentColor;border-radius:8px;padding:.5rem .75rem;margin:.5rem 0;font-size:.88rem}
.n-warn{color:var(--warn)}.n-bad{color:var(--bad)}.n-info{color:var(--dim)}
.empty{text-align:center;color:var(--dim);padding:2.5rem 1rem;border:1px dashed var(--line);border-radius:12px}
/* ── composer 폼 ── */
.card--fold{padding:0}
.card--fold>summary{list-style:none;cursor:pointer;padding:1rem 1.15rem;display:flex;
 align-items:baseline;gap:.6rem;flex-wrap:wrap}
.card--fold>summary::-webkit-details-marker{display:none}
.card--fold>summary::after{content:"▾";color:var(--dim);margin-left:auto}
.card--fold:not([open])>summary::after{content:"▸"}
.card--fold>summary h2{margin:0}
.card--fold>.body{padding:0 1.15rem 1.1rem}
.card--fold>summary .sub{color:var(--dim);font-size:.82rem}
.choice{display:flex;align-items:center;gap:.5rem;padding:.5rem .65rem;border:1px solid var(--line);
 border-radius:8px;background:var(--bg);margin:.35rem 0}
.choice input{accent-color:var(--accent)}
input,select,textarea{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--line);
 border-radius:7px;padding:.45rem .6rem}
input:focus,select:focus,textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
button{font:inherit;font-weight:600;font-size:.88rem;padding:.5rem 1.05rem;border:1px solid transparent;
 border-radius:8px;background:var(--accent);color:#fff;cursor:pointer}
button:hover{opacity:.92}
button.ghost{background:transparent;color:var(--bad);border-color:var(--bad)}
/* 구조도 — 실행 순서 레일 */
.flow{list-style:none;margin:0;padding:0 0 0 1.5rem;position:relative}
.flow::before{content:"";position:absolute;left:10px;top:.8rem;bottom:.8rem;width:2px;background:var(--line)}
.stage{position:relative;margin-bottom:1rem}
.stage__n{position:absolute;left:-1.5rem;top:.2rem;width:22px;height:22px;border-radius:50%;
 background:var(--accent);color:#fff;font-size:.72rem;font-weight:700;display:grid;place-items:center}
.stage>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.6rem}
.stage>summary::-webkit-details-marker{display:none}
.stage__title{margin:0;font-size:.92rem}
.stage__tally{font-size:.74rem;color:var(--dim)}
.stage__note{margin:.15rem 0 .4rem;color:var(--dim);font-size:.8rem}
.nodes{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.4rem}
.node{border-radius:8px;padding:.4rem .65rem;border:1px solid var(--line);background:var(--bg);
 font-size:.82rem}
.node--module{border-left:3px dashed var(--ok)}
.node--component{border-left:3px solid var(--accent)}
.node--instance{border-left:3px dashed var(--warn)}
.node--off{opacity:.5;text-decoration:line-through}
.flow-legend{color:var(--dim);font-size:.8rem;margin:0 0 .6rem}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def qs(value: Any) -> str:
    """쿼리스트링 **값**으로 들어갈 것. ★`esc()` 만으로는 부족하다.

    `esc()` 는 HTML 이스케이프일 뿐 URL 인코딩이 아니다. 폴더 이름에 `&`·`#` 가
    있으면(둘 다 파일명으로 합법이다) 브라우저가 각각 **쿼리 구분자**·**fragment**
    로 해석해서, 링크가 원래와 다른 경로를 가리킨다 —
    `a&b#c` → `path=...a` + 엉뚱한 파라미터 `b`, 그리고 `#c` 는 서버에 오지도 않는다.
    2026-08-19 인수인계 점검에서 실측했다.

    그래서 **URL 인코딩 먼저, HTML 이스케이프 나중**이다. 순서를 바꾸면
    `&` 가 `&amp;` 가 된 뒤 `%26amp%3B` 로 인코딩돼 값 자체가 변한다.
    """
    return esc(quote("" if value is None else str(value), safe=""))


def page(title: str, body: str, *, lede: str = "", path: str = "", current: str = "") -> HTMLResponse:
    lede_html = f"<p class='lede'>{esc(lede)}</p>" if lede else ""
    # Composer POST의 각 결과 분기도 동일한 화면 메뉴를 유지한다.
    if not current and title == "구성 조립(Composer)":
        current = "/composer"
        path = lede
    links = [("/", "프로젝트 목록")]
    if path:
        links.extend([(f"/project?path={qs(path)}", "조립"),
                      (f"/composer?path={qs(path)}", "Composer")])
    else:
        links.extend([(None, "조립"), (None, "Composer")])
    nav = "".join(
        (f"<a href='{href}'{' aria-current=\'page\'' if href.split('?', 1)[0] == current else ''}>{esc(label)}</a>"
         if href is not None else f"<span class='nav-disabled' aria-disabled='true'>{esc(label)}</span>")
        for href, label in links)
    return HTMLResponse(
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · 개발 콘솔</title><style>{CSS}</style></head><body>"
        f"<div class='topbar'><div class='topbar__in'><span class='brand'>개발 콘솔</span>"
        f"<nav aria-label='주 메뉴'>{nav}</nav></div></div>"
        f"<main class='shell'><h1>{esc(title)}</h1>{lede_html}{body}</main></body></html>")


def stat(label: str, value: Any, hint: str = "") -> str:
    hint_html = f"<small>{esc(hint)}</small>" if hint else ""
    return f"<div class='stat'><span>{esc(label)}</span><b>{esc(value)}</b>{hint_html}</div>"


def pill(text: str, kind: str = "idle") -> str:
    return f"<span class='pill p-{kind}'>{esc(text)}</span>"


def note(text: str, kind: str = "info") -> str:
    return f"<p class='note n-{kind}'>{esc(text)}</p>"


def table(headers: list[str], rows: list[str], empty: str = "없음") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(rows) or f"<tr><td class='dim' colspan='99'>{esc(empty)}</td></tr>"
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def collapsible_card(title: str, body: str, *, subtitle: str = "", open_: bool = True) -> str:
    sub = f"<span class='sub'>{esc(subtitle)}</span>" if subtitle else ""
    return (f"<details class='card card--fold'{' open' if open_ else ''}>"
            f"<summary><h2>{esc(title)}</h2>{sub}</summary>"
            f"<div class='body'>{body}</div></details>")


_NODE_BADGE = {"module": "모듈", "component": "고정", "instance": "인스턴스"}

#: ★대상의 원래 `/ui/composer` 화면에는 세 가지 노드 종류를 설명하는 범례가 있었다
#:   (`docs/backup/composer_ui_원본_2026-08-18/composer_ui_final_project_cs.py`).
#:   이 콘솔로 다시 쓸 때 그 설명이 빠져 있었다 — 노드 색만 보고는 "고정"·"모듈"·
#:   "인스턴스"가 뭐가 다른지 알 수 없다. 문구는 그대로 옮기지 않고 이 화면 톤에 맞게
#:   다시 썼다(§0.2 — 화면은 이 프로그램이 만든다).
FLOW_LEGEND = ("<p class='flow-legend'><b>고정</b> = 컴포넌트, 끌 수 없다 · "
              "<b>모듈</b> = 선택, 위 폼에서 켜고 끈다 · "
              "<b>인스턴스</b> = 개수가 바뀐다(Team처럼 추가·제거된다)</p>")


def _node(name: str, *, kind: str, enabled: bool | None, hint: str = "") -> str:
    off = " node--off" if enabled is False else ""
    badge = _NODE_BADGE.get(kind, kind)
    state = "" if enabled is None else (" · 켜짐" if enabled else " · 꺼짐")
    hint_html = f" <span class='dim'>— {esc(hint)}</span>" if hint else ""
    return f"<li class='node node--{kind}{off}'>{esc(name)} <span class='dim'>({badge}{state})</span>{hint_html}</li>"


def flow(stages: list[dict[str, Any]]) -> str:
    """실행 순서 구조도. ★목록·설명은 이 콘솔이 다시 쓴 것이다 — 대상 코드를
    가져오지 않는다(`CLAUDE.md` §0.2). 켜짐/꺼짐 상태만 지금 config 값을 그대로 반영한다."""
    rows = []
    for stage in stages:
        nodes = "".join(_node(n["name"], kind=n["kind"], enabled=n.get("enabled"), hint=n.get("hint", ""))
                        for n in stage["nodes"])
        note = f"<p class='stage__note'>{esc(stage['note'])}</p>" if stage.get("note") else ""
        rows.append(f"<li class='stage'><span class='stage__n'>{esc(stage['n'])}</span>"
                    f"<details class='stage' open><summary><h3 class='stage__title'>{esc(stage['title'])}</h3>"
                    f"<span class='stage__tally'>{len(stage['nodes'])}개</span></summary>"
                    f"{note}<ul class='nodes'>{nodes}</ul></details></li>")
    return FLOW_LEGEND + f"<ul class='flow'>{''.join(rows)}</ul>"


#: ★고정 인프라 — 모듈 토글 대상이 아니다. `docs/backup/composer_ui_원본_2026-08-18/`의
#:   원본 설명을 참고해 이 콘솔이 다시 썼다. 대상 코드가 바뀌면 이 목록은 갱신이 필요할 수
#:   있다 — 실시간으로 검증되지 않는 참고 정보임을 화면에 밝힌다.
COMPONENTS = (
    ("Case lifecycle", "상태 변경의 단일 진입점"),
    ("Contract models", "Team 계약(TeamTask/TeamResult 등)"),
    ("Team Registry", "capability 해석과 라우팅"),
    ("Context Broker", "컨텍스트 예산과 degraded 신호"),
    ("DB repository / session", "Source of Truth"),
    ("Outbox publisher", "트랜잭션과 이벤트 발행"),
    ("Controller", "전체 실행 루프"),
)


def _structure_stages(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """지금 config 값으로 그리는 실행 순서 구조도.

    ★정적 그림이 아니라 **지금 읽은 config의 투영**이다 — 꺼진 모듈은 꺼진 채로 그려진다.
    """
    def on(name: str) -> bool:
        m = cfg.get("modules", {}).get(name)
        return bool(m and m.get("enabled"))

    teams = cfg.get("teams", [])
    active = [t for t in teams if t.get("active")]
    executor = cfg.get("ports", {}).get("team_executor", "모름")
    # ★Team 은 "모듈"(고정된 목록에서 켜고 끄기)이 아니라 "인스턴스"다 — 개수 자체가
    #   Composer 화면에서 추가·제거로 바뀐다(`_config_from_form`). 원래 대상 화면도
    #   같은 구분을 썼다(`docs/backup/composer_ui_원본_2026-08-18/...` 참고).
    team_nodes = [{"name": t.get("team_id"), "kind": "instance", "enabled": t.get("active"),
                  "hint": "라우팅됨" if t.get("active") else "등록만 됨"} for t in teams] or \
        [{"name": "Team 없음", "kind": "instance", "enabled": False}]

    return [
        {"n": "1", "title": "입력", "note": "요청이 들어온다",
         "nodes": [{"name": "REST API", "kind": "component"},
                   {"name": "mcp", "kind": "module", "enabled": on("mcp"), "hint": "개인 AI 접속 · read-only"}]},
        {"n": "2", "title": "Case 생성 · 상태 전이", "note": "단일 진입점을 통해서만 상태가 바뀐다",
         "nodes": [{"name": "transition_case()", "kind": "component"},
                   {"name": "Contract models", "kind": "component"}]},
        {"n": "3", "title": "분류",
         "nodes": [{"name": "인라인 분류", "kind": "component"},
                   {"name": "voc", "kind": "module", "enabled": on("voc"), "hint": "일일 집계 · 급증 탐지"}]},
        {"n": "4", "title": "컨텍스트 조립",
         "nodes": [{"name": "Context Broker", "kind": "component"},
                   {"name": "vector_rag", "kind": "module", "enabled": on("vector_rag"), "hint": "정책 검색"},
                   {"name": "graph_store", "kind": "module", "enabled": on("graph_store"), "hint": "관계 조회"}]},
        {"n": "5", "title": "라우팅", "nodes": [{"name": "Team Registry", "kind": "component"}]},
        {"n": "6", "title": "실행", "note": f"현재 team_executor = {executor}",
         "nodes": [{"name": "TeamExecutorPort", "kind": "component"},
                   {"name": "a2a_executor", "kind": "module", "enabled": on("a2a_executor"),
                    "hint": "원격 Team 실행"}]},
        {"n": "7", "title": "Agent Team", "note": f"지금 {len(active)}/{len(teams)}개 라우팅",
         "nodes": team_nodes},
        {"n": "8", "title": "제안 · 승인",
         "nodes": [{"name": "Controller", "kind": "component"},
                   {"name": "Human Approval", "kind": "component"}]},
        {"n": "9", "title": "발행", "nodes": [{"name": "Outbox", "kind": "component"}]},
    ]


JUDGEMENT_KIND = {"통과": "ok", "부분통과": "warn", "미통과": "bad", "미착수": "idle"}


def _config_from_form(form: dict, module_names: list[str], port_names: list[str],
                      team_count: int) -> dict[str, Any]:
    """제출된 폼을 대상이 기대하는 raw dict 모양으로 되돌린다.

    ★필드 이름(`module_*`·`port_*`·`team_id_N`)만 안다 — 값의 **허용 범위**는
      모른다(어떤 port 값이 유효한지는 대상의 스키마다). 그래서 select 가 아니라
      text input 이다 — 잘못된 값은 validate 가 걸러 준다, 여기서 미리 막지 않는다.
    """
    modules = {name: {"enabled": form.get(f"module_{name}") == "on"} for name in module_names}
    ports = {name: str(form.get(f"port_{name}", "")) for name in port_names}
    teams = []
    for index in range(team_count):
        team_id = str(form.get(f"team_id_{index}", "")).strip()
        if not team_id and f"team_id_{index}" not in form:
            continue
        ref = str(form.get(f"implementation_ref_{index}", "")).strip()
        teams.append({"team_id": team_id, "active": form.get(f"active_{index}") == "on",
                      "implementation_ref": ref})
    return {"modules": modules, "ports": ports, "teams": teams}


def _csrf_refusal(request: Request, form: Any) -> HTMLResponse | None:
    """CSRF 검사. 통과하면 `None`, 막아야 하면 거부 화면을 돌려준다.

    ★막으려는 것: 콘솔이 켜져 있는 동안 운영자가 연 **악성 웹페이지**가
      `127.0.0.1:<port>/composer` 로 form POST 를 보내는 것. 폼 POST 는 CORS
      preflight 대상이 아니라 브라우저가 안 막는다. 응답은 못 읽어도 **부작용
      (대상 config 변경)은 일어난다** — 이 프로세스의 issuer secret 으로.

    ★두 겹이다:
      1. **토큰**(주 방어) — 우리가 그린 폼에만 있고, 공격자는 동일출처 정책
         때문에 그 값을 읽을 수 없다. 그래서 위조가 안 된다.
      2. **Origin**(보조) — 브라우저는 cross-origin POST 에 항상 `Origin` 을
         붙인다. 있으면 우리 것과 같아야 한다. 없으면(비-브라우저 클라이언트)
         토큰만으로 판정한다 — 브라우저는 생략할 수 없으므로 안전하다.
    """
    token = str(form.get("csrf_token", ""))
    if not secrets.compare_digest(token, _CSRF_TOKEN):
        return _csrf_denied(
            "이 요청에는 유효한 CSRF 토큰이 없습니다. 이 화면을 **다시 열어서** 제출하세요.")

    origin = request.headers.get("origin")
    if origin:
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin.rstrip("/") != expected.rstrip("/"):
            return _csrf_denied(f"다른 출처에서 온 요청입니다 — {esc(origin)}")
    return None


def _csrf_denied(reason: str) -> HTMLResponse:
    return page("구성 조립(Composer)",
                note(f"요청을 거부했습니다. {reason}", "bad")
                + "<div class='card'><p class='dim'>이 화면의 폼으로만 제출할 수 있습니다. "
                  "스크립트로 자동화하려면 이 콘솔이 아니라 <b>대상의 <code>/composer/*</code> API 를 "
                  "직접</b> 호출하세요 — 그게 원래 계약입니다(<code>CLAUDE.md</code> §0.3).</p></div>"
                + "<p><a href='/'>← 프로젝트 목록</a></p>",
                current="/composer")


def _composer_mode_badge(profile: Any) -> str:
    """지금 어느 방식으로 붙어 있는지 화면에 밝힌다 (2026-08-30).

    ★같은 화면이 **대상을 직접** 고치기도 하고 **중앙 설정 서비스**를 통해
      고치기도 한다. 어느 쪽인지 안 보이면 운영자가 "이 [적용] 버튼이 누구
      설정을 바꾸는가" 를 알 수 없다 — 그건 남의 설정을 건드리는 사고로 이어진다.
    """
    mode = getattr(profile, "composer_mode", "direct")
    deployment_id = getattr(profile, "composer_deployment_id", None)
    if mode == "central":
        if not deployment_id:
            # ★중앙인데 대상이 비었으면 요청이 400 으로 거부된다. 미리 말한다.
            return note("중앙 설정 서비스 방식인데 CONSOLE_COMPOSER_DEPLOYMENT_ID 가 "
                        "비어 있습니다 — 대상을 지정하지 않으면 요청이 거부됩니다.", "bad")
        # ★`note()` 는 본문 전체를 이스케이프한다(그게 안전한 기본값이다).
        #   여기에 태그를 넣었더니 화면에 `<code>` 가 **글자로** 나왔다
        #   (2026-08-30 캡처 검수에서 발견). 문구 검사는 통과했었다 —
        #   대상 이름이 문자열로는 들어 있었기 때문이다. 눈으로 봐야 잡힌다.
        return note(f"중앙 설정 서비스 방식 · 대상 {deployment_id} "
                    "— 이 화면의 변경은 중앙 저장소에 기록됩니다.", "info")
    return note("직접 방식 — 대상 제품에 설치된 Composer 를 직접 호출합니다.", "info")


def _composer_setup_help(target: Path, status: str) -> str:
    """★못 붙었을 때 **다음에 할 일**을 적는다.

    이 화면은 대상의 config 를 대상에게 물어봐서 그린다 — 이 콘솔이 대상의
    파이썬을 import 하지 않기 때문이다(`CLAUDE.md` §0.3). 그래서 대상 서버가
    떠 있어야 하고 연결 정보가 있어야 한다. 그 사실을 화면이 직접 말하지 않으면
    "화면을 이식했는데 왜 비어 있나" 로 읽힌다(실제로 그렇게 읽혔다).
    """
    if status not in ("연결 안 함", "토큰 발급 실패", "대상이 응답하지 않음", "인증 실패"):
        return ""
    return (
        "<div class='card'><h2>붙이려면</h2>"
        "<p class='dim'>이 화면은 <b>대상에게 물어봐서</b> 그립니다 — 이 콘솔은 대상의 "
        "파이썬을 import 하지 않고, 쓰기는 대상이 자기 계약으로 검증한 뒤 실행합니다"
        "(<code>CLAUDE.md</code> §0.3). 그래서 아래 둘이 필요합니다.</p>"
        "<ol>"
        f"<li><b>대상 서버를 띄웁니다</b> — <span class='mono'>{esc(str(target))}</span> 에서 "
        "그 프로젝트의 실행 방법대로 기동합니다.</li>"
        "<li><b>이 콘솔에 연결 정보를 줍니다</b>(환경변수, 파일에 저장하지 않습니다):"
        "<pre class='mono'>CONSOLE_COMPOSER_URL=http://127.0.0.1:&lt;대상포트&gt;/composer\n"
        "CONSOLE_COMPOSER_ISSUER_SECRET=&lt;대상의 /auth/token 발급자 비밀키&gt;</pre>"
        "그 다음 이 콘솔을 다시 시작합니다.</li>"
        "</ol>"
        "<p class='dim'>자세한 것은 <code>README.md</code> 의 “라이브 연결”.</p></div>")


#: v3 제안(`program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md` §2.1)에서
#: `modules`는 `enabled`, `teams`·`ports`는 `active`로 현재 상태를 담는다.
_TOGGLE_STATE_KEY = {"modules": "enabled", "teams": "active", "ports": "active"}
_TOGGLE_LABEL = {"modules": "모듈", "teams": "Team", "ports": "Port"}
_TOGGLE_TARGET_TYPE = {"modules": "module", "teams": "team", "ports": "port"}


def _registered_ids_from(value: Any) -> dict[str, list[str]] | None:
    """introspection 응답에서 v3 제안의 `registered_ids`를 뽑는다.

    ★모르는 계약 버전으로는 그리지 않는다(`CLAUDE.md` §1) — 호출부가
    `live.status == "읽음"`(= `contract_version`이 `CONSOLE_CONTRACT_VERSIONS`에
    있어 이미 알려진 버전으로 확인된 상태)일 때만 이 함수를 부른다. 그래도 형태가
    다르면(리스트가 아니거나 문자열이 아닌 원소) 그 종류만 조용히 뺀다 —
    지어내지 않는다(§0.4).
    """
    if not isinstance(value, dict):
        return None
    raw = value.get("registered_ids")
    if not isinstance(raw, dict):
        return None
    result = {kind: ids for kind in ("modules", "teams", "ports")
             if isinstance(ids := raw.get(kind), list) and all(isinstance(x, str) for x in ids)}
    return result or None


_TOGGLE_ID_KEY = {"modules": "name", "teams": "team_id", "ports": "name"}


def _toggle_state(value: Any, kind: str, target_id: str) -> bool | None:
    """introspection 응답에서 항목 하나의 현재 활성 상태를 읽는다.

    ★대상이 실제로 내는 형태는 종류마다 다르다(contract_version 1.0 실측).
    한때 여기서 `{id: {"enabled": bool}}` 한 가지만 기대해서 상태가 늘 `모름`이었고,
    `_toggle_row()`가 상태를 모르면 버튼을 안 그리므로 **토글 카드에 버튼이 하나도
    없었다** — 카드는 떠도 아무것도 못 바꿨다(2026-08-28 결함 점검에서 브라우저로 실측).

    | 형태 | 예 | 어디서 |
    |---|---|---|
    | boolean map | `{"vector_rag": true}` | 대상의 `modules` |
    | 객체 list | `[{"team_id": "voc", "active": true}]` | 대상의 `teams` |
    | 객체 map | `{"voc": {"active": true}}` | v3 설계 §2.2 제안 |

    셋 다 읽는다. 어느 것도 아니면 `None`을 돌려주고 화면은 `모름`이라고 적는다 —
    지어내지 않는다(`CLAUDE.md` §0.4).
    """
    bucket = (value or {}).get(kind)
    state_key = _TOGGLE_STATE_KEY[kind]

    if isinstance(bucket, dict):
        entry = bucket.get(target_id)
        if isinstance(entry, bool):                       # boolean map
            return entry
        if isinstance(entry, dict):                       # 객체 map
            state = entry.get(state_key)
            return state if isinstance(state, bool) else None
        return None

    if isinstance(bucket, list):                          # 객체 list
        id_key = _TOGGLE_ID_KEY[kind]
        for entry in bucket:
            if isinstance(entry, dict) and entry.get(id_key) == target_id:
                state = entry.get(state_key)
                return state if isinstance(state, bool) else None
    return None


def _toggle_row(kind: str, target_id: str, state: bool | None, *, target: Path, revision: str) -> str:
    state_label = "모름" if state is None else ("켜짐" if state else "꺼짐")
    state_kind = "idle" if state is None else ("ok" if state else "warn")
    action = ""
    if state is not None:
        # ★새 값은 현재 값의 반대다 — 화면이 이만큼만 "판단"한다. 등록 여부·형태
        #   검증은 대상 몫이다(`CLAUDE.md` §0.2 — 유효성 판정은 대상이 한다).
        action = f"""<form method='post' action='/composer/toggle'
              style='display:inline-flex;gap:.4rem;align-items:center;flex-wrap:wrap'>
          <input type='hidden' name='csrf_token' value='{esc(_CSRF_TOKEN)}'>
          <input type='hidden' name='path' value='{esc(str(target))}'>
          <input type='hidden' name='target_type' value='{esc(_TOGGLE_TARGET_TYPE[kind])}'>
          <input type='hidden' name='target_id' value='{esc(target_id)}'>
          <input type='hidden' name='active' value='{"false" if state else "true"}'>
          <input type='hidden' name='base_revision' value='{esc(revision)}'>
          <input name='reason' placeholder='사유' required style='width:9rem'>
          <button type='submit'>{'끄기' if state else '켜기'}</button>
        </form>"""
    return (f"<tr><td>{esc(_TOGGLE_LABEL[kind])}</td><td class='mono'>{esc(target_id)}</td>"
            f"<td>{pill(state_label, state_kind)}</td><td>{action}</td></tr>")


def _toggle_card(live: Any, target: Path) -> str:
    """v3 제안(`POST /composer/toggle`)이 대상에 있으면 등록 ID별 빠른 토글을 보여준다.

    ★없으면 이 카드 자체가 안 뜬다 — 순수 추가 기능이다. 기존 v2 화면·기능
    (`_composer_body`)은 이 카드의 유무와 무관하게 그대로 동작한다
    (사용자 결정: 안 C — 병행. 2026-08-24).

    이 카드는 v2 Composer 연결(`current.ok`)과 **별개로** introspection 연결
    (`live`)만 본다 — v2가 아직 안 붙어 있어도(또는 그 반대여도) 각자 뜬다.
    """
    registered = _registered_ids_from(live.value) if getattr(live, "status", "") == "읽음" else None
    if not registered:
        return ""
    revision = str((live.value or {}).get("config_revision", ""))
    rows = [_toggle_row(kind, target_id, _toggle_state(live.value, kind, target_id),
                        target=target, revision=revision)
            for kind in ("modules", "teams", "ports") for target_id in registered.get(kind, [])]
    return collapsible_card(
        "빠른 토글 (v3 제안)",
        note("대상이 등록해 둔 항목만 켜고 끕니다 — 새 선언을 만들거나 등록 목록 자체를 "
             "바꾸지 않습니다. 계약은 아직 잠정입니다"
             "(program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md §2).", "info")
        + table(["종류", "ID", "상태", ""], rows),
        subtitle=f"등록 {sum(len(v) for v in registered.values())}건 · revision {revision}" if revision
                 else f"등록 {sum(len(v) for v in registered.values())}건")


def _activation_hint(payload: dict[str, Any]) -> str:
    """`activation_state` 를 운영자에게 **감추지 않고** 덧붙인다.

    ★대상은 저장에 성공해도 `pending_restart` 를 돌려준다 — 조립은 프로세스가
      뜰 때 한 번만 일어나기 때문이다. 화면이 "적용됨" 만 보여주면 운영자는
      이미 반영된 줄 안다. 그게 이 프로젝트가 금지하는 조용한 성공 위장이다.
    """
    state = payload.get("activation_state")
    if state == "pending_restart":
        # ★2026-08-31 — 대상이 `POST /admin/reload`(scope `ops:reload`)를 갖게 돼
        #   재기동 말고 반영시키는 길이 생겼다. 이 콘솔은 그 호출을 하지 않으므로
        #   "재시작" 만 말하면 사실이 아니게 된다 — 두 길을 다 적는다.
        # ★태그를 넣지 않는다 — 이 문자열은 `note()` 로 들어가고 거기서 전부
        #   이스케이프된다(2026-08-30 에 같은 자리에서 `<code>` 가 글자로
        #   새어나갔다). 평문으로 쓴다.
        return (" · ★아직 반영 전입니다 — 대상을 재시작하거나 "
                "POST /admin/reload 를 불러야 실제로 적용됩니다.")
    if state:
        return f" · 반영 상태: {state}"
    return ""


#: 대상이 내는 `reload_state` 를 운영자 말로 옮긴다. ★이 문구는 이 콘솔이
#:  소유한다 — 대상의 상태 이름을 그대로 화면에 던지지 않는다.
_RELOAD_LABELS = {
    "active": "실행 중인 조립 = 저장된 선언",
    "stale": "★실행 중인 조립이 아직 옛 선언입니다 — 반영되지 않았습니다",
    "reload_failed": "★반영에 실패했습니다 — 옛 조립이 계속 돌고 있습니다",
    "unknown": "실행 중인 revision 을 대상이 알려주지 않습니다(모름)",
}


def _reload_state_note(payload: dict[str, Any] | None) -> str:
    """실행 중인 조립과 저장된 선언이 어긋났으면 **화면에서 말한다.**

    ★계약 1.0 대상은 이 필드가 없다. 없으면 아무 말도 하지 않는다 —
      모르는 것을 "정상" 으로 적지 않기 위해서다.
    """
    state = (payload or {}).get("reload_state")
    if not state:
        return ""
    label = _RELOAD_LABELS.get(state, f"반영 상태: {state}")
    kind = "bad" if state in ("stale", "reload_failed") else "info"
    active = (payload or {}).get("active_revision") or "모름"
    desired = (payload or {}).get("desired_revision") or "모름"
    detail = f"{label} · 실행 중 {active} / 저장됨 {desired}"
    error = (payload or {}).get("reload_error")
    if error:
        detail += f" · 마지막 실패: {error}"
    return note(detail, kind)


def _instance_rows(config: dict[str, Any] | None, revision: str, target: Path) -> list[str]:
    """선언에 있는 Team 인스턴스와 삭제 버튼.

    ★켜기/끄기는 위의 빠른 토글 카드가 한다 — 여기서는 **지우기**만 준다.
      같은 일을 두 곳에 두면 운영자가 어느 쪽이 맞는지 헷갈린다.
    """
    teams = (config or {}).get("teams") or []
    rows: list[str] = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = str(team.get("team_id", ""))
        state = pill("켜짐", "ok") if team.get("active") else pill("꺼짐", "warn")
        kind = "선언형" if team.get("parameters") else "코드형"
        form = f"""<form method='post' action='/composer/instance'
              style='display:inline-flex;gap:.4rem;align-items:center;flex-wrap:wrap'>
          <input type='hidden' name='csrf_token' value='{esc(_CSRF_TOKEN)}'>
          <input type='hidden' name='path' value='{esc(str(target))}'>
          <input type='hidden' name='operation' value='delete'>
          <input type='hidden' name='resource_type' value='team'>
          <input type='hidden' name='instance_id' value='{esc(team_id)}'>
          <input type='hidden' name='base_revision' value='{esc(revision)}'>
          <input name='reason' placeholder='사유' required style='width:9rem'>
          <button type='submit'>지우기</button>
        </form>"""
        rows.append(f"<tr><td class='mono'>{esc(team_id)}</td><td>{esc(kind)}</td>"
                    f"<td>{state}</td><td>{form}</td></tr>")
    return rows


def _catalog_card(catalog: "composer_client.ComposerResult",
                  current: "composer_client.ComposerResult", target: Path) -> str:
    """카탈로그에서 구현을 골라 **새 인스턴스를 만든다** (`POST /composer/changes`).

    ★이 카드가 "이름과 설정만 입력해 만든다" 를 실제로 하는 곳이다. 선택지도
      입력 항목도 **대상이 준다** — 화면은 그걸 그릴 뿐이고 어떤 값이 유효한지
      판정하지 않는다(`CLAUDE.md` §0.2 — 유효성 판정은 대상 몫).

    ★대상에 `/composer/catalog` 가 없으면 이 카드 자체가 안 뜬다. 기존 화면은
      그대로 동작한다 — 순수 추가 기능이다.
    """
    if not catalog.ok or not isinstance(catalog.value, dict):
        return ""
    implementations = catalog.value.get("implementations") or []
    teams = [i for i in implementations if isinstance(i, dict) and i.get("kind") == "team"]
    if not teams:
        return ""

    config = current.value.get("config") if isinstance(current.value, dict) else None
    revision = str((current.value or {}).get("revision", "")) if isinstance(current.value, dict) else ""

    options = "".join(
        f"<option value='{esc(str(i.get('implementation_id', '')))}'>"
        f"{esc(str(i.get('display_name') or i.get('implementation_id')))}"
        f"{' — 설정 입력 필요' if i.get('parameters_schema') else ''}</option>"
        for i in teams)

    catalog_rows = [
        f"<tr><td class='mono'>{esc(str(i.get('implementation_id', '')))}</td>"
        f"<td>{esc(str(i.get('display_name', '')))}</td>"
        f"<td>{esc(str(i.get('description', '')))}</td>"
        f"<td>{pill('필요', 'warn') if i.get('parameters_schema') else pill('없음', 'idle')}</td></tr>"
        for i in teams]

    create_form = f"""<form method='post' action='/composer/instance'>
      <input type='hidden' name='csrf_token' value='{esc(_CSRF_TOKEN)}'>
      <input type='hidden' name='path' value='{esc(str(target))}'>
      <input type='hidden' name='operation' value='create'>
      <input type='hidden' name='resource_type' value='team'>
      <input type='hidden' name='base_revision' value='{esc(revision)}'>
      <p><label>구현 종류 <select name='implementation_id'>{options}</select></label></p>
      <p><label>인스턴스 이름 <input name='instance_id' required
            placeholder='vip_return_review'></label></p>
      <p><label>설정(JSON)<br>
        <textarea name='parameters' rows='8' spellcheck='false' style='width:100%'
                  placeholder='선언형이면 필수입니다. 아래 표에서 "설정" 이 필요인 구현은 이 칸을 채웁니다.'></textarea>
      </label></p>
      <p><label>사유 <input name='reason' required placeholder='왜 만드는지'></label></p>
      <p><label><input type='checkbox' name='dry_run' value='true'> 검증만(저장 안 함)</label></p>
      <button type='submit'>만들기</button>
    </form>"""

    schema_note = ""
    declarative = next((i for i in teams if i.get("parameters_schema")), None)
    if declarative is not None:
        fields = sorted((declarative.get("parameters_schema") or {}).get("properties", {}))
        if fields:
            schema_note = note("설정 JSON 에 넣는 항목(대상이 준 스키마): " + ", ".join(fields),
                               "info")

    return collapsible_card(
        "인스턴스 만들기 (카탈로그)",
        note("코드 배포 없이 새 Team 을 만듭니다. 고를 수 있는 구현과 입력 항목은 "
             "대상이 알려줍니다 — 이 화면은 유효성을 판정하지 않고 그대로 보냅니다.", "info")
        + create_form + schema_note
        + "<h3>고를 수 있는 구현</h3>"
        + table(["implementation_id", "이름", "설명", "설정"], catalog_rows)
        + "<h3>지금 선언된 Team</h3>"
        + table(["team_id", "종류", "상태", ""], _instance_rows(config, revision, target),
                empty="선언된 Team 이 없습니다"),
        subtitle=f"revision {revision}" if revision else "")


def _composer_body(target: Path, current: "composer_client.ComposerResult", *,
                   config: dict[str, Any] | None = None) -> str:
    """★대상의 인증된 쓰기 채널만 부른다(`CLAUDE.md` §0.3 예외) — 여기서 직접 안 쓴다.

    ★모듈·Team·Port 를 구조화된 폼으로 편집한다 — 대상의 원래 `/ui/composer` 화면과
      같은 편집 기능이다(체크박스·행 추가/제거). 다만 대상의 `PortConfig` 타입힌트를
      가져와 select 의 선택지를 만들지는 않는다 — 그건 스키마를 복제하는 것이고
      `CLAUDE.md` §0.2 가 금지한다. port 는 현재 값을 보여주는 text input 이고,
      틀린 값이면 validate 가 잡는다.

    ★`reason`은 대상의 audit 계약이 요구하는 최소 근거다. basement 대상(예:
      final_project_sample)에 적용할 때는 실제 운영 변경이 아니라 **구조설계 테스트
      목적**임을 이 칸에 적는 것을 권장한다 — 코드로 대상을 구분하지 않는다,
      운영자가 매번 밝힌다.
    """
    import json as _json

    back = f"<p><a href='/project?path={qs(str(target))}'>← 프로젝트로</a></p>"
    if not current.ok:
        kind = "warn" if current.status == "연결 안 함" else "bad"
        # ★"composer_url 이 프로필에 없음" 만 띄우면 **무엇을 해야 하는지**를 안 알려준다.
        #   실제로 "Composer 를 이 콘솔로 이식한 것 아니었나?" 하는 오해를 불렀다
        #   (2026-08-19). 이식한 것은 **화면**이고, 값은 대상에게 물어봐야 한다 —
        #   대상 프로세스가 자기 Core 계약으로 검증한 뒤 쓰기 때문이다(`CLAUDE.md` §0.3).
        #   그 사실과 **다음에 할 일**을 화면이 직접 말한다.
        return (note(current.detail or current.status, kind)
                + _composer_setup_help(target, current.status) + back)

    revision = current.value.get("revision", "")
    cfg = config if config is not None else current.value.get("config", {})
    # ★대상이 이상한 것을 줘도 **콘솔은 떠야 한다**(`CLAUDE.md` §1).
    #   한때 대상이 `config: null`·배열·문자열을 주면 여기서 `.get()`/`.items()` 가
    #   터져 화면 전체가 500 이었다 — 어느 대상이 뭘 잘못 줬는지도 안 보였다.
    #   못 읽었으면 **못 읽었다고 적는다**(2026-08-19 인수인계 점검에서 실측).
    if not isinstance(cfg, dict):
        return note(f"대상이 준 config 를 읽지 못했습니다 — 객체가 아니라 "
                    f"{type(cfg).__name__} 입니다.", "bad") + back
    modules = cfg.get("modules") or {}
    ports = cfg.get("ports") or {}
    teams = cfg.get("teams") or []
    if not isinstance(modules, dict) or not isinstance(ports, dict) or not isinstance(teams, list):
        return note("대상이 준 config 의 modules·ports·teams 형태가 예상과 다릅니다 "
                    "— 편집 화면을 그리지 않습니다.", "bad") + back
    teams = [t for t in teams if isinstance(t, dict)]

    intro = note(
        "이 폼은 대상의 인증된 Composer API(/composer/current, /validate, /apply)만 호출합니다 — "
        "여기서 대상 파일을 직접 쓰지 않습니다. 적용은 대상이 revision 이 일치할 때만 원자적으로 반영합니다.",
        "info")

    module_rows = "".join(
        f"<label class='choice'><input type='checkbox' name='module_{esc(name)}' "
        f"{'checked' if (item or {}).get('enabled') else ''}> {esc(name)}</label>"
        for name, item in modules.items())

    port_rows = "".join(
        f"<p><label>{esc(name)} "
        f"<input name='port_{esc(name)}' value='{esc(value)}' style='width:16rem'></label></p>"
        for name, value in ports.items())

    team_rows = "".join(
        f"<tr><td><input name='team_id_{i}' value='{esc(t.get('team_id'))}'></td>"
        f"<td><input name='implementation_ref_{i}' value='{esc(t.get('implementation_ref'))}' size='42'></td>"
        f"<td><input type='checkbox' name='active_{i}' {'checked' if t.get('active') else ''}></td>"
        f"<td><button type='submit' name='remove_team' value='{i}'>제거</button></td></tr>"
        for i, t in enumerate(teams))

    raw = _json.dumps(cfg, ensure_ascii=False, indent=2)
    raw_view = f"<details><summary>원본 JSON (대조용)</summary><pre class='mono'>{esc(raw)}</pre></details>"

    active_n = sum(1 for t in teams if t.get("active"))
    on_n = sum(1 for m in modules.values() if (m or {}).get("enabled"))

    form = f"""
    <form method='post' action='/composer'>
      <input type='hidden' name='csrf_token' value='{esc(_CSRF_TOKEN)}'>
      <input type='hidden' name='path' value='{esc(str(target))}'>
      <input type='hidden' name='base_revision' value='{esc(revision)}'>
      <div class='stat'><span>REVISION</span><b class='mono'>{esc(revision)}</b></div>

      {collapsible_card("모듈", module_rows or note("모듈이 없습니다.", "info"),
                        subtitle=f"{on_n}/{len(modules)}종 켜짐")}

      {collapsible_card("Port", port_rows or note("Port가 없습니다.", "info"), subtitle=f"{len(ports)}종")}

      {collapsible_card("Team",
          table(["team_id", "implementation_ref", "active", ""], [team_rows], empty="Team이 없습니다.")
          + "<p><button type='submit' name='add_team' value='1'>Team 추가</button></p>",
          subtitle=f"{len(teams)}개 등록 · {active_n}개 라우팅")}

      <p><input name='reason' placeholder='사유 — 예: 모듈 구조 설계 테스트' style='width:100%;padding:.5rem'></p>
      <p>
        <button type='submit' name='action' value='validate'>검증</button>
        &nbsp;
        <button type='submit' name='action' value='apply'>적용</button>
      </p>
    </form>"""

    component_rows = "".join(f"<li><b>{esc(n)}</b> — {esc(r)}. 여기서 끌 수 없습니다.</li>" for n, r in COMPONENTS)
    structure = collapsible_card(
        "구조 — 실행 순서", flow(_structure_stages(cfg)),
        subtitle="지금 읽은 config의 투영입니다. 꺼진 모듈은 꺼진 채로 표시됩니다")
    components = collapsible_card(
        "컴포넌트 (읽기 전용)", f"<ul>{component_rows}</ul>",
        subtitle=f"{len(COMPONENTS)}종 — 참고용, 실시간 검증 안 됨", open_=False)

    return intro + form + structure + components + raw_view + back


def create_app() -> FastAPI:
    app = FastAPI(title="개발 콘솔")

    @app.get("/", response_class=HTMLResponse)
    def projects(root: str = Query(default=str(DEFAULT_ROOT))) -> HTMLResponse:
        found = discover(root)
        if not found:
            return page("프로젝트", f"<div class='empty'><p>{esc(root)} 아래에 폴더가 없습니다.</p></div>",
                        lede=str(root), current="/")

        rows = []
        for item in found:
            if item.is_project:
                link = f"<a class='mono' href='/project?path={qs(item.path)}'>{esc(item.name)}</a>"
                mark = pill("프로젝트", "ok")
            else:
                # ★조용히 빼지 않는다 — "왜 내 폴더가 안 보이나" 에 답해야 한다
                link = f"<span class='mono dim'>{esc(item.name)}</span>"
                mark = pill("아님", "idle")
            rows.append(f"<tr><td>{link}</td><td>{mark}</td>"
                        f"<td class='dim'>{esc(' · '.join(item.reasons))}</td></tr>")

        n = sum(1 for i in found if i.is_project)
        summary = ("<div class='grid'>"
                   + stat("프로젝트", n, f"훑은 폴더 {len(found)}개")
                   + stat("루트", Path(root).name, str(root))
                   + "</div>")
        return page("프로젝트", summary + "<div class='card'>" +
                    table(["폴더", "판별", "근거"], rows) + "</div>",
                    lede="경로를 주지 않으면 이 콘솔의 상위 폴더를 훑습니다.", current="/")

    @app.get("/project", response_class=HTMLResponse)
    def project(path: str = Query(default="")) -> HTMLResponse:
        # ★`path` 를 필수로 두면 FastAPI 가 **raw JSON 422** 를 낸다 — 주소창에
        #   `/project` 만 치거나 쿼리 없는 북마크로 들어오면 화면이 아니라 JSON 이
        #   뜬다. 다른 라우트(`/`·`/run`·`/composer`)는 전부 안내 화면을 낸다.
        #   여기만 다를 이유가 없다(2026-08-19 인수인계 점검에서 실측).
        if not path:
            return page("프로젝트", note(
                "프로젝트 경로가 없습니다 — `/project?path=<프로젝트 경로>` 로 여세요.", "warn")
                        + "<p><a href='/'>← 프로젝트 목록에서 고르기</a></p>",
                        current="/project")

        found = inspect_path(path)
        if not found.is_project:
            return page("프로젝트", note(
                f"프로젝트가 아닙니다 — {' · '.join(found.reasons)}", "bad"),
                        lede=str(path), path=path, current="/project")

        target = Path(path)
        profile = profile_for(target)
        declaration = read_declaration(target)
        guardrails = read_guardrails(target)
        judgements = read_judgements(target)
        evaluation = read_eval_runs(target, limit=6)

        # ── 조립 ──────────────────────────────────────────────────────────
        if not declaration.ok:
            assembly = note(f"선언을 읽지 못했습니다 — {declaration.error}", "bad")
            head = "<div class='grid'>" + stat("모듈", "모름") + stat("Team", "모름") + "</div>"
        else:
            value = declaration.value
            modules = value["modules"]
            on = sum(1 for v in modules.values() if v is True)
            teams = value["teams"]
            active = sum(1 for t in teams if t.get("active"))
            off = [k for k, v in modules.items() if v is False]
            head = ("<div class='grid'>"
                    + stat("모듈", f"{on}/{len(modules)}", "꺼짐: " + (", ".join(off) or "없음"))
                    + stat("Agent Team", f"{active}/{len(teams)}", "라우팅됨/등록됨")
                    + stat("team_executor", value["ports"].get("team_executor") or "모름")
                    + "</div>")
            assembly = table(
                ["team_id", "active", "implementation_ref"],
                [f"<tr><td class='mono'>{esc(t.get('team_id'))}</td>"
                 f"<td>{pill('active', 'ok') if t.get('active') else pill('inactive', 'idle')}</td>"
                 f"<td class='mono dim'>{esc(t.get('implementation_ref'))}</td></tr>" for t in teams])

        # ── 막힌 것 ───────────────────────────────────────────────────────
        items = judgements.value or []
        if judgements.error and not items:
            blocked = note(f"판정을 읽지 못했습니다 — {judgements.error}", "warn")
        else:
            counts = judgement_counts(items)
            stuck = [i for i in items if i.judgement != "통과"]
            rows = [f"<tr><td class='mono'>{esc(i.id)}</td>"
                    f"<td>{pill(i.judgement, JUDGEMENT_KIND.get(i.judgement, 'bad'))}</td>"
                    f"<td>{esc(i.title)}</td>"
                    f"<td class='dim'>{'재현' if i.has_reproduction else '재현 없음'} · "
                    f"{'실측' if i.has_actual_output else '실측 없음'}</td></tr>" for i in stuck]
            # ★점수 하나로 뭉치지 않는다 — 부분통과와 미착수는 다른 일이다
            distribution = " ".join(
                pill(f"{k} {v}", JUDGEMENT_KIND.get(k, "bad")) for k, v in sorted(counts.items()))
            blocked = (f"<p>{distribution}</p>"
                       + (table(["DoD", "판정", "항목", "근거"], rows) if stuck
                          else note("통과가 아닌 항목이 없습니다.", "info")))

        # ── 평가 ─────────────────────────────────────────────────────────
        data = evaluation.value or {"runs": [], "total": 0, "shown": 0}
        if evaluation.error and not data["runs"]:
            evaluated = note(f"평가를 읽지 못했습니다 — {evaluation.error}", "warn")
        elif not data["runs"]:
            evaluated = "<div class='empty'><p>평가 리포트가 없습니다.</p></div>"
        else:
            rows = []
            for run in data["runs"]:
                marks = [pill("mock — 실제 성능 아님", "bad")] if run.is_mock else []
                marks += [pill(a, "warn") for a in run.ablations]
                rows.append(
                    f"<tr><td class='mono'>{esc(run.file)}</td>"
                    f"<td class='mono'>{esc(run.rows)}</td>"
                    f"<td>{esc(run.arm or '미표기')}</td>"
                    f"<td>{esc(run.provider or '미표기')}</td>"
                    # ★실측과 추정을 나란히 둔다. 하나로 뭉치면 거짓이 된다.
                    f"<td class='mono'>{'모름' if run.observed_cost_usd is None else f'${run.observed_cost_usd}'}</td>"
                    f"<td class='mono dim'>{'모름' if run.estimated_cost_usd is None else f'${run.estimated_cost_usd}'}</td>"
                    f"<td>{''.join(marks) or '<span class=dim>—</span>'}</td></tr>")
            # ★말없이 자르지 않는다
            cut = (note(f"최근 {data['shown']}개만 표시했습니다. 전체 {data['total']}개 중 "
                        f"{data['total'] - data['shown']}개는 화면에 없습니다.", "warn")
                   if data["total"] > data["shown"] else "")
            evaluated = (note("run 단위로만 비교합니다. arm·dataset·실행 방식이 다르면 "
                              "평균을 견줄 수 없습니다.", "info") + cut
                         + table(["리포트", "행", "arm", "provider", "실측 비용", "추정 비용", "표시"], rows))

        live = read_introspection(profile.introspection_url, profile.contract_versions,
                                   profile.introspection_token)
        runs = read_agent_runs(profile.database_url)
        state_rows = []
        if runs.state_counts:
            for table_name, counts in runs.state_counts.items():
                for status, count in counts.items():
                    state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                     f"<td>{esc(status)}</td><td>{esc(count)}</td></tr>")
        # ★상태 분포. `outbox` 의 `unknown`·`dead_letter` 는 **사람이 봐야 하는 상태**다.
        #   `unknown` 은 돈이 나갔는지 모르는 상태이므로 가장 세게 칠한다.
        state_rows = []
        for table_name, counts in (runs.state_counts or {}).items():
            if "__error__" in counts:
                # ★읽지 못한 것을 0 으로 채우지 않는다
                state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                  f"<td colspan='2' class='dim'>읽지 못했다 — "
                                  f"{esc(counts['__error__'])}</td></tr>")
                continue
            if not counts:
                state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                  f"<td colspan='2' class='dim'>행 없음</td></tr>")
                continue
            for status, count in sorted(counts.items(), key=lambda x: -x[1]):
                kind = "bad" if status in ("unknown", "dead_letter", "escalated") else (
                    "warn" if status in ("waiting_approval", "waiting_input", "pending") else "idle")
                state_rows.append(f"<tr><td class='dim'>{esc(table_name)}</td>"
                                  f"<td>{pill(status, kind)}</td>"
                                  f"<td class='mono'>{esc(count)}</td></tr>")

        state_card = "<div class='card'><h2>상태 분포</h2>" + table(
            ["테이블", "status", "건수"], state_rows,
            # ★연결이 없으면 "0" 이 아니라 그 이유를 적는다
            empty=runs.detail or "연결 안 함") + "</div>"
        run_rows = []
        for run in runs.rows:
            run_id = run.get("run_id")
            href = f"/run?path={qs(str(target))}&run_id={qs(run_id)}"
            run_rows.append(
                f"<tr><td class='mono'><a href='{href}'>{esc(run_id)}</a></td>"
                f"<td>{esc(run.get('status'))}</td>"
                f"<td class='mono'>{esc(run.get('case_id'))}</td>"
                f"<td class='dim'>{esc(run.get('started_at'))}</td></tr>")
        run_history = table(
            ["run_id", "status", "case_id", "started_at"], run_rows,
            empty=runs.detail or "실행 이력이 없습니다.")

        connections = table(
            ["출처", "상태", "세부"],
            [f"<tr><td>{esc(label)}</td><td>{pill(result.status, 'ok' if result.status == '읽음' else 'idle')}</td>"
             f"<td class='dim'>{esc(result.detail)}</td></tr>"
             for label, result in (
                 ("선언", type("R", (), {"status": "읽음" if declaration.ok else "모름", "detail": declaration.source or ""})()),
                 ("판정", type("R", (), {"status": "읽음" if judgements.ok else "모름", "detail": judgements.source or ""})()),
                 ("평가", type("R", (), {"status": "읽음" if evaluation.ok else "모름", "detail": evaluation.source or ""})()),
                 ("조립 실측", live),
                 ("실행 이력", runs),
             )],
            empty="연결 정보가 없습니다.")

        guardrail_value = "missing"
        if guardrails.ok:
            context = guardrails.value.get("context", {})
            guardrail_value = context.get("token_budget", "missing")
        guardrail_card = (
            "<div class='card'><h2>guardrails</h2>" +
            table(["context.token_budget"], [f"<tr><td class='mono'>{esc(guardrail_value)}</td></tr>"],
                  empty=guardrails.error or "missing") + "</div>")

        body = (head
                + guardrail_card
                + f"<div class='card'><h2>조립</h2>{assembly}</div>"
                + f"<div class='card'><h2>무엇이 막혀 있나</h2>{blocked}</div>"
                + f"<div class='card'><h2>평가 실행</h2>{evaluated}</div>"
                # ★state_card 를 만들어 놓고 body 에 안 넣고 있었다 —
                #   섹션이 통째로 화면에서 사라졌고, 테스트가 없어 아무도 몰랐다.
                + state_card
                + "<div class='card'><h2>실행 이력</h2>" + run_history + "</div>"
                + f"<div class='card'><h2>연결</h2>{connections}</div>"
                + f"<p><a href='/composer?path={qs(str(target))}'>구성 조립(Composer) →</a>"
                + f" &nbsp;·&nbsp; <a href='/'>← 프로젝트 목록</a></p>")
        return page(found.name, body, lede=str(target), path=str(target), current="/project")

    @app.get("/run", response_class=HTMLResponse)
    def run(path: str = Query(default=""), run_id: str | None = Query(default=None)) -> HTMLResponse:
        if not run_id:
            return page("실행 추적", note("run_id가 없습니다.", "warn"), lede=path, path=path)

        target = Path(path) if path else Path(DEFAULT_ROOT)
        profile = profile_for(target)
        result = read_trace(profile.database_url, run_id)
        if not result.ok:
            kind = "warn" if result.status in ("연결 안 함", "그 실행이 없다") else "bad"
            return page("실행 추적", note(result.detail or result.status, kind), lede=str(target), path=path)

        sections = []
        for item in result.trace:
            stage = item.get("stage", "")
            if "error" in item:
                content = note(f"읽지 못했습니다: {item['error']}", "warn")
            else:
                rows = item.get("rows", [])
                if not rows:
                    content = note("이 단계의 기록이 없습니다.", "info")
                else:
                    headers = list(rows[0].keys())
                    rendered = [
                        "<tr>" + "".join(f"<td>{esc(row.get(header))}</td>" for header in headers) + "</tr>"
                        for row in rows
                    ]
                    content = table(headers, rendered)
            sections.append(f"<div class='card'><h2>{esc(stage)}</h2>{content}</div>")

        back = f"<p><a href='/project?path={qs(str(target))}'>실행 이력으로 돌아가기</a></p>"
        return page("실행 추적", "".join(sections) + back, lede=f"{target} · {run_id}", path=path)

    def _composer_page(target: Path, current: "composer_client.ComposerResult", live: Any, *,
                       config: dict[str, Any] | None = None, prefix: str = "",
                       catalog: "composer_client.ComposerResult | None" = None) -> HTMLResponse:
        """토글 카드 + 인스턴스 CRUD 카드 + v2 편집 폼을 한 화면으로 합친다.

        모든 `/composer*` 라우트가 이 한 곳을 거치게 해서, 화면을 새로 그릴
        때마다 세 계약을 같이 빠뜨리지 않게 한다. ★각 카드는 대상이 그 기능을
        갖고 있을 때만 뜬다 — 없으면 조용히 빠지고 나머지는 그대로 동작한다.
        """
        catalog_card = _catalog_card(catalog, current, target) if catalog is not None else ""
        # ★어느 방식으로 붙어 있는지 맨 위에 밝힌다 — 이 화면의 [적용] 이
        #   누구 설정을 바꾸는지가 보여야 한다.
        badge = _composer_mode_badge(profile_for(target))
        # ★저장된 선언과 **실행 중인 조립**이 어긋났으면 맨 위에서 말한다.
        #   이 화면에서 [적용] 을 눌러도 대상이 반영하기 전까지는 옛 조립이
        #   돌고 있다 — 그걸 안 보여주면 운영자는 이미 바뀐 줄 안다.
        reload_note = _reload_state_note(live.value if getattr(live, "value", None) else None)
        return page("구성 조립(Composer)",
                    prefix + badge + reload_note + _toggle_card(live, target) + catalog_card
                    + _composer_body(target, current, config=config),
                    lede=str(target), path=str(target), current="/composer")

    def _read_catalog(profile: Any) -> "composer_client.ComposerResult":
        return composer_client.read_catalog(profile.composer_url, profile.composer_issuer_secret,
                                           deployment_id=profile.composer_deployment_id)

    @app.get("/composer", response_class=HTMLResponse)
    def composer_form(path: str = Query(default="")) -> HTMLResponse:
        target = Path(path) if path else Path(DEFAULT_ROOT)
        profile = profile_for(target)
        current = composer_client.read_current(profile.composer_url, profile.composer_issuer_secret,
                                            deployment_id=profile.composer_deployment_id)
        live = read_introspection(profile.introspection_url, profile.contract_versions,
                                  profile.introspection_token)
        return _composer_page(target, current, live, catalog=_read_catalog(profile))

    @app.post("/composer", response_class=HTMLResponse)
    async def composer_submit(request: Request) -> HTMLResponse:
        form = await request.form()

        # ★CSRF — 대상에 **아무것도 보내기 전에** 막는다.
        #   토큰은 우리가 그린 폼에만 있고, 공격자 페이지는 동일출처 정책 때문에
        #   못 읽는다. `Origin` 은 보조다(브라우저는 cross-origin POST 에 항상 보낸다).
        refusal = _csrf_refusal(request, form)
        if refusal is not None:
            return refusal

        target = Path(str(form.get("path", "")))
        profile = profile_for(target)
        # ★blocking `urlopen()` 을 이벤트 루프에서 직접 부르면, 대상이 느릴 때
        #   이 프로세스의 **다른 화면까지** 멈춘다. worker thread 로 뺀다.
        current = await run_in_threadpool(
            composer_client.read_current, profile.composer_url, profile.composer_issuer_secret,
                deployment_id=profile.composer_deployment_id)
        live = await run_in_threadpool(read_introspection, profile.introspection_url,
                                       profile.contract_versions, profile.introspection_token)
        if not current.ok:
            return _composer_page(target, current, live)

        base_config = current.value.get("config", {})
        # ★대상이 이상한 것을 줘도 콘솔은 떠야 한다 — `_composer_body` 와 같은 이유다.
        if not isinstance(base_config, dict):
            return _composer_page(target, current, live)
        module_names = list(base_config.get("modules") or {})
        port_names = list(base_config.get("ports") or {})
        indexes = [int(key.removeprefix("team_id_")) for key in form
                  if key.startswith("team_id_") and key.removeprefix("team_id_").isdigit()]
        team_count = max(indexes, default=len(base_config.get("teams") or []) - 1) + 1
        candidate = _config_from_form(form, module_names, port_names, team_count)

        # ★행 추가/제거는 대상에 보내지 않는다 — 화면만 다시 그린다(원본 화면과 같은 패턴)
        if form.get("remove_team") is not None:
            # ★`int()` 를 그냥 부르면 조작된 POST(`remove_team=abc`)가 **500** 이 된다.
            #   실측으로 확인했다(2026-08-19 인수인계 점검). 숫자가 아니면 아무 행도
            #   지우지 않고 화면만 다시 그린다 — 범위 밖 인덱스와 같은 취급이다.
            raw_index = str(form["remove_team"])
            index = int(raw_index) if raw_index.lstrip("-").isdigit() else -1
            if 0 <= index < len(candidate["teams"]):
                candidate["teams"].pop(index)
            return _composer_page(target, current, live, config=candidate)
        if form.get("add_team") is not None:
            candidate["teams"].append({"team_id": "new_team", "active": False, "implementation_ref": ""})
            return _composer_page(target, current, live, config=candidate,
                                  prefix=note("새 Team을 추가했습니다. 검증 전에는 저장되지 않습니다.", "info"))

        action = str(form.get("action", ""))
        reason = str(form.get("reason", ""))
        if action == "validate":
            outcome = await run_in_threadpool(
                composer_client.validate_candidate,
                profile.composer_url, profile.composer_issuer_secret, candidate,
                deployment_id=profile.composer_deployment_id)
        elif action == "apply":
            if not reason.strip():
                # ★reason 없이 적용하지 않는다 — 대상 계약(§ audit)이 요구하는 최소한의 근거다
                return _composer_page(target, current, live, config=candidate,
                                      prefix=note("적용하려면 사유(reason)를 적어야 합니다.", "bad"))
            outcome = await run_in_threadpool(
                composer_client.apply_candidate,
                profile.composer_url, profile.composer_issuer_secret, candidate,
                base_revision=str(form.get("base_revision", "")), reason=reason.strip(),
                deployment_id=profile.composer_deployment_id)
        else:
            return _composer_page(target, current, live, config=candidate,
                                  prefix=note(f"알 수 없는 동작: {action}", "bad"))

        kind = "ok" if outcome.ok else ("warn" if outcome.status in ("연결 안 함", "충돌") else "bad")
        detail = outcome.detail or outcome.status
        if outcome.status == "적용됨":
            detail = f"적용됨 — 새 revision {outcome.value.get('revision')}"
        elif outcome.status == "검증됨":
            detail = f"검증 통과 — revision {outcome.value.get('revision')}"
        elif outcome.status == "검증 실패":
            detail = "검증 실패: " + "; ".join(outcome.errors) if outcome.errors else "검증 실패"
        result_note = note(detail, kind)

        # ★적용 성공 후에는 대상의 최신 상태(새 revision)를 다시 읽어 보여준다
        refreshed = current
        if outcome.status == "적용됨":
            refreshed = await run_in_threadpool(
                composer_client.read_current, profile.composer_url, profile.composer_issuer_secret,
                deployment_id=profile.composer_deployment_id)
        return _composer_page(target, refreshed, live, config=candidate, prefix=result_note)

    @app.post("/composer/toggle", response_class=HTMLResponse)
    async def composer_toggle_submit(request: Request) -> HTMLResponse:
        """v3 제안(`POST /composer/toggle`) — 등록된 항목 하나의 활성 상태만 바꾼다.

        ★v2(`/composer`)와 같은 CSRF 방어를 그대로 쓴다 — 부작용을 내는 폼 POST 라는
        점은 v2 apply 와 같다. `console/composer.py`의 `toggle_target()` docstring이
        말하듯 계약은 아직 잠정이라, 대상이 없거나 필드가 안 맞으면 그저 "대상이
        응답하지 않음"·"검증 실패"로 뜬다 — 화면이 깨지지는 않는다.
        """
        form = await request.form()
        refusal = _csrf_refusal(request, form)
        if refusal is not None:
            return refusal

        target = Path(str(form.get("path", "")))
        profile = profile_for(target)
        reason = str(form.get("reason", "")).strip()

        async def _redraw(prefix: str = "") -> HTMLResponse:
            current = await run_in_threadpool(
                composer_client.read_current, profile.composer_url, profile.composer_issuer_secret,
                deployment_id=profile.composer_deployment_id)
            live = await run_in_threadpool(read_introspection, profile.introspection_url,
                                           profile.contract_versions, profile.introspection_token)
            return _composer_page(target, current, live, prefix=prefix)

        if not reason:
            # ★v2 apply 와 같은 규칙 — 사유 없이 상태를 바꾸지 않는다
            return await _redraw(note("토글하려면 사유(reason)를 적어야 합니다.", "bad"))

        outcome = await run_in_threadpool(
            composer_client.toggle_target, profile.composer_url, profile.composer_issuer_secret,
            deployment_id=profile.composer_deployment_id,
            target_type=str(form.get("target_type", "")), target_id=str(form.get("target_id", "")),
            active=str(form.get("active", "")) == "true",
            base_revision=str(form.get("base_revision", "")), reason=reason)

        kind = "ok" if outcome.ok else ("warn" if outcome.status in ("연결 안 함", "충돌") else "bad")
        detail = outcome.detail or outcome.status
        if outcome.status == "토글됨" and isinstance(outcome.value, dict):
            new_state = "켜짐" if outcome.value.get("active") else "꺼짐"
            detail = (f"토글됨 — {outcome.value.get('target_id')} → {new_state} "
                     f"(revision {outcome.value.get('config_revision')})")
            detail += _activation_hint(outcome.value)
        return await _redraw(note(detail, kind))

    @app.post("/composer/instance", response_class=HTMLResponse)
    async def composer_instance_submit(request: Request) -> HTMLResponse:
        """카탈로그 기반 인스턴스 생성·삭제 (`POST /composer/changes`).

        ★이 화면은 **판정하지 않는다.** 설정 JSON 이 대상의 스키마에 맞는지,
        구현이 등록돼 있는지, 권한이 되는지는 전부 대상이 본다. 여기서 미리
        검사하면 그 순간 대상의 검증 모델을 복제하는 것이다(`CLAUDE.md` §0.2).
        다만 **JSON 문법**은 여기서 본다 — 그건 대상 스키마가 아니라 이 폼의
        입력 형식이고, 깨진 문자열을 그대로 보내면 오류 메시지가 엉뚱해진다.
        """
        form = await request.form()
        refusal = _csrf_refusal(request, form)
        if refusal is not None:
            return refusal

        target = Path(str(form.get("path", "")))
        profile = profile_for(target)
        reason = str(form.get("reason", "")).strip()

        async def _redraw(prefix: str = "") -> HTMLResponse:
            current = await run_in_threadpool(
                composer_client.read_current, profile.composer_url, profile.composer_issuer_secret,
                deployment_id=profile.composer_deployment_id)
            live = await run_in_threadpool(read_introspection, profile.introspection_url,
                                           profile.contract_versions, profile.introspection_token)
            catalog = await run_in_threadpool(_read_catalog, profile)
            return _composer_page(target, current, live, prefix=prefix, catalog=catalog)

        if not reason:
            # ★v2 apply·토글과 같은 규칙 — 사유 없이 구성을 바꾸지 않는다.
            return await _redraw(note("변경하려면 사유(reason)를 적어야 합니다.", "bad"))

        raw_parameters = str(form.get("parameters", "")).strip()
        parameters: dict[str, Any] | None = None
        if raw_parameters:
            try:
                decoded = json.loads(raw_parameters)
            except json.JSONDecodeError as exc:
                return await _redraw(note(f"설정 JSON 을 읽지 못했습니다 — {exc}", "bad"))
            if not isinstance(decoded, dict):
                return await _redraw(note("설정 JSON 은 객체여야 합니다.", "bad"))
            parameters = decoded

        outcome = await run_in_threadpool(
            composer_client.submit_change, profile.composer_url, profile.composer_issuer_secret,
            deployment_id=profile.composer_deployment_id,
            operation=str(form.get("operation", "")),
            resource_type=str(form.get("resource_type", "team")),
            instance_id=str(form.get("instance_id", "")).strip(),
            base_revision=str(form.get("base_revision", "")),
            reason=reason,
            implementation_id=str(form.get("implementation_id", "")) or None,
            parameters=parameters,
            dry_run=str(form.get("dry_run", "")) == "true")

        kind = "ok" if outcome.ok else ("warn" if outcome.status in ("연결 안 함", "충돌") else "bad")
        detail = outcome.detail or outcome.status
        if outcome.ok and isinstance(outcome.value, dict):
            if outcome.value.get("dry_run"):
                detail = "검증만 했습니다 — 저장하지 않았습니다."
            else:
                detail = (f"{form.get('operation')} 적용됨 — {form.get('instance_id')} "
                          f"(revision {outcome.value.get('desired_revision')})")
                detail += _activation_hint(outcome.value)
        return await _redraw(note(detail, kind))

    return app


app = create_app()


def main() -> None:
    """★포트를 하드코딩하지 않는다. 호스트가 `PORT` 로 지정한다 —
    다른 채팅이 띄운 서버와 포트가 부딪히면 아예 뜨지 못한다."""
    import uvicorn
    uvicorn.run("console.web:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", "8060")), reload=True)


if __name__ == "__main__":
    main()
