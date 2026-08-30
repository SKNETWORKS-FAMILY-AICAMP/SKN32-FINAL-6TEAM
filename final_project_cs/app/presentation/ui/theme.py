"""운영 화면의 표현 계층 — 디자인 토큰과 공용 컴포넌트.

★이 화면은 "예쁘게" 가 목적이 아니다. **틀린 정보가 고객 돈을 건드리는 시스템**의
  운영 콘솔이다. 그래서 표현이 지켜야 할 것이 따로 있다:

  1. **사람이 손을 대야 하는 상태가 눈에 띄어야 한다** — `waiting_approval` 은 노랑,
     `unknown`·`escalated` 는 빨강. `unknown` 은 **돈이 나갔는지 모르는 상태**라 가장 세게 칠한다.
  2. **근거 없음이 조용하지 않아야 한다** — 근거 없는 제안은 승인 버튼이 잠기고,
     왜 잠겼는지 화면이 말한다. 잠긴 이유를 안 적으면 운영자는 UI 결함으로 오해한다
     (실제로 2026-08-14 에 그렇게 오해했다).
  3. **degraded 를 숨기지 않는다** — ContextPack 이 축소됐으면 화면에 뜬다.

  색은 장식이 아니라 **분류**다. 아래 STATE_TONE 이 그 분류표다.
"""
from __future__ import annotations

import html
import json
from typing import Any, Iterable

# ── 상태 → 색 분류 ────────────────────────────────────────────────────────────
#: ★critical = 사람이 지금 봐야 한다 / warn = 사람의 결정을 기다린다
#:   active = 시스템이 돌고 있다 / done = 끝났다 / idle = 아직/중단
STATE_TONE: dict[str, str] = {
    # 사람이 지금 봐야 한다
    "escalated": "critical", "failed": "critical", "dead_letter": "critical",
    "unknown": "critical", "rejected": "critical",
    # 사람의 결정을 기다린다
    "waiting_approval": "warn", "waiting_input": "warn", "pending_approval": "warn",
    "proposed": "warn", "waiting_provider": "warn",
    # 돌고 있다
    "classifying": "active", "routing": "active", "running": "active",
    "resuming": "active", "processing": "active", "executing": "active",
    # 끝났다
    "resolved": "done", "delivered": "done", "succeeded": "done", "approved": "done",
    # 아직 / 중단
    "new": "idle", "cancelled": "idle", "pending": "idle",
}


def tone_of(state: Any) -> str:
    return STATE_TONE.get(str(state or "").strip().lower(), "idle")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def as_json(value: Any) -> str:
    return esc(json.dumps(value or {}, ensure_ascii=False, default=str, indent=2))


# ── 컴포넌트 ──────────────────────────────────────────────────────────────────
def pill(state: Any, *, label: str | None = None) -> str:
    """상태 배지. 색이 분류를 말한다."""
    return f"<span class='pill pill--{tone_of(state)}'>{esc(label or state)}</span>"


def stat(label: str, value: Any, *, tone: str = "", hint: str = "") -> str:
    """숫자 하나를 크게 보여주는 카드."""
    hint_html = f"<span class='stat__hint'>{esc(hint)}</span>" if hint else ""
    tone_cls = f" stat--{tone}" if tone else ""
    return (f"<div class='stat{tone_cls}'><span class='stat__label'>{esc(label)}</span>"
            f"<strong class='stat__value'>{esc(value)}</strong>{hint_html}</div>")


def card(title: str | None, body: str, *, subtitle: str = "", tone: str = "") -> str:
    head = ""
    if title:
        sub = f"<p class='card__sub'>{esc(subtitle)}</p>" if subtitle else ""
        head = f"<header class='card__head'><h2>{esc(title)}</h2>{sub}</header>"
    tone_cls = f" card--{tone}" if tone else ""
    return f"<section class='card{tone_cls}'>{head}{body}</section>"


def collapsible_card(title: str, body: str, *, subtitle: str = "", open_: bool = True,
                     tone: str = "") -> str:
    """접을 수 있는 카드.

    ★긴 화면에서 지금 안 보는 덩어리는 접어 둘 수 있어야 한다.
      다만 **기본은 펼침**이다 — 접힌 채로 두면 있는 줄도 모른다.
    """
    tone_cls = f" card--{tone}" if tone else ""
    sub = f"<span class='card__sub'>{esc(subtitle)}</span>" if subtitle else ""
    return (f"<details class='card card--fold{tone_cls}'{' open' if open_ else ''}>"
            f"<summary class='card__head card__head--fold'>"
            f"<h2>{esc(title)}</h2>{sub}</summary>"
            f"<div class='card__body'>{body}</div></details>")


def table(headers: Iterable[str], rows: Iterable[str], *, empty: str = "없음") -> str:
    """★넓은 표는 가로로만 스크롤한다. 페이지 본문이 가로로 밀리면 안 된다."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(rows)
    if not body:
        body = f"<tr><td class='muted' colspan='99'>{esc(empty)}</td></tr>"
    return (f"<div class='scroll-x'><table><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def kv_table(pairs: Iterable[tuple[str, Any]]) -> str:
    """★JSON 덩어리 대신 읽을 수 있는 표로 낸다."""
    rows = "".join(
        f"<tr><th class='kv__key'>{esc(k)}</th><td class='kv__val'>"
        f"{as_json(v) if isinstance(v, (dict, list, tuple)) else esc(v)}</td></tr>"
        for k, v in pairs)
    return f"<div class='scroll-x'><table class='kv'><tbody>{rows}</tbody></table></div>"


def distribution(counts: dict[str, int], *, empty: str = "데이터 없음") -> str:
    """상태 분포를 막대로. ★데이터가 없으면 0 을 지어내지 않고 '없음'을 적는다."""
    if not counts:
        return f"<p class='muted'>{esc(empty)}</p>"
    total = sum(counts.values()) or 1
    bars = "".join(
        f"<li class='dist__row'><span class='dist__name'>{pill(name)}</span>"
        f"<span class='dist__track'><span class='dist__fill dist__fill--{tone_of(name)}'"
        f" style='width:{max(2, round(n / total * 100))}%'></span></span>"
        f"<span class='dist__n'>{esc(n)}</span></li>"
        for name, n in sorted(counts.items(), key=lambda x: -x[1]))
    return f"<ul class='dist'>{bars}</ul>"


def evidence_block(items: Iterable[dict[str, Any]], *, masker=lambda v: v) -> str:
    """근거 목록. ★비면 조용히 넘어가지 않고 경고로 표시한다."""
    rendered = "".join(
        f"<li class='ev'><span class='ev__type'>{esc(e.get('source_type'))}</span>"
        f"<code class='ev__id'>{esc(masker(e.get('source_id')))}</code>"
        f"<p class='ev__claim'>{esc(e.get('claim'))}</p></li>"
        for e in items)
    if not rendered:
        return "<p class='notice notice--warn'>근거 없음 — 확정 답변을 만들 수 없습니다.</p>"
    return f"<ul class='ev-list'>{rendered}</ul>"


def flow(stages: Iterable[dict[str, Any]]) -> str:
    """실행 순서대로 늘어놓은 구조도.

    ★그림이 아니라 **현재 선언의 투영**이다. 꺼진 모듈은 꺼진 채로 그려진다.
      구조도와 실제 조립이 어긋나면 그림이 거짓말을 하게 된다.

    stages: [{"n": "1", "title": ..., "note": ...,
              "nodes": [{"name":..., "kind":"component"|"module"|"instance",
                         "enabled": bool|None, "hint": str}]}]
    """
    rows = []
    for stage in stages:
        chips = "".join(
            "<li class='node node--{kind}{off}'>"
            "<span class='node__name'>{name}</span>"
            # ★배지와 설명 사이에 구분자를 넣는다. 없으면 텍스트로 뽑았을 때
            #   "REST /v1고정쓰기 경로" 처럼 전부 붙어 읽을 수 없다 —
            #   CSS 는 간격을 주지만 **마크업 자체가 읽혀야** 복사·스크린리더가 산다.
            "<span class='node__kind'> — {badge}</span>"
            "{hint}</li>".format(
                kind=esc(node["kind"]),
                off="" if node.get("enabled", True) is not False else " node--off",
                name=esc(node["name"]),
                badge={"component": "고정", "module": "모듈", "instance": "인스턴스"}
                      .get(node["kind"], "") + (
                          "" if node.get("enabled") is None
                          else " · 켜짐" if node.get("enabled") else " · 꺼짐"),
                hint=f"<span class='node__hint'>{esc(node['hint'])}</span>" if node.get("hint") else "")
            for node in stage["nodes"])
        note = f"<p class='stage__note'>{esc(stage['note'])}</p>" if stage.get("note") else ""
        count = len(stage["nodes"])
        off = sum(1 for n in stage["nodes"] if n.get("enabled") is False)
        tally = f"{count}개" + (f" · {off}개 꺼짐" if off else "")
        # ★단계마다 접고 편다. 10단계 × 노드가 한꺼번에 펼쳐져 있으면
        #   보려던 단계를 찾는 데 스크롤을 해야 한다.
        # ★<ul> 이다 — <ol> 이면 브라우저 자동 번호와 stage__n 배지가 겹쳐
        #   "1. 1" 로 두 번 나온다.
        rows.append(
            f"<li class='stage'><span class='stage__n'>{esc(stage['n'])}</span>"
            f"<details class='stage__body' open>"
            f"<summary class='stage__head'>"
            f"<h3 class='stage__title'>{esc(stage['title'])}</h3>"
            f"<span class='stage__tally'>{esc(tally)}</span></summary>"
            f"{note}<ul class='nodes'>{chips}</ul></details></li>")
    return f"<ul class='flow'>{''.join(rows)}</ul>"


def details(summary: str, body: str) -> str:
    """★원문은 지우지 않고 접어 둔다.

    운영자가 판단에 쓰는 것은 evidence 블록이고, raw JSON 은 대조용이다.
    둘을 나란히 펼쳐 두면 중요한 쪽이 묻힌다. 그렇다고 지우면 대조를 못 한다.
    """
    return f"<details class='raw'><summary>{esc(summary)}</summary>{body}</details>"


def notice(text: str, *, tone: str = "info") -> str:
    return f"<p class='notice notice--{tone}'>{esc(text)}</p>"


def empty_state(text: str, *, hint: str = "") -> str:
    hint_html = f"<p class='muted'>{esc(hint)}</p>" if hint else ""
    return f"<div class='empty'><p>{esc(text)}</p>{hint_html}</div>"


# ── 셸 ───────────────────────────────────────────────────────────────────────
NAV = (
    ("/ui/cases", "Cases"),
    ("/ui/approvals", "Approvals"),
    ("/ui/voc", "VOC"),
    ("/ui/admin", "Admin"),
)

#: ★라이트/다크를 모두 정의한다. 색은 토큰으로만 쓰고 컴포넌트에 하드코딩하지 않는다.
CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#f4f6fa; --surface:#fff; --surface-2:#f8fafc; --line:#e2e7f0;
  --text:#111a2c; --text-dim:#5b6779; --accent:#2f5bd8; --accent-strong:#2247ab; --accent-weak:#e8effd;
  --critical:#c0362c; --critical-bg:#fdecea; --warn:#9a6200; --warn-bg:#fff6e2;
  --active:#1d63c7; --active-bg:#e8f1fd; --done:#0d7a4d; --done-bg:#e6f6ee;
  --idle:#5b6779; --idle-bg:#eef1f6;
  --radius:12px; --shadow:0 1px 2px #0f172a0f,0 8px 24px #0f172a0a;
  --mono:ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0d1219; --surface:#151c26; --surface-2:#1b232f; --line:#28323f;
  --text:#e7ecf3; --text-dim:#93a1b4; --accent:#7aa2f7; --accent-strong:#9dbaf9; --accent-weak:#1b2740;
  --critical:#ff8b80; --critical-bg:#3a1c1a; --warn:#f2bd5c; --warn-bg:#3a2c12;
  --active:#7aa2f7; --active-bg:#182742; --done:#5bd6a0; --done-bg:#12332a;
  --idle:#93a1b4; --idle-bg:#212a36;
  --shadow:0 1px 2px #0006,0 8px 24px #0000004d;
}}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:system-ui,-apple-system,"Segoe UI","Noto Sans KR",sans-serif;
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.shell{max-width:1180px;margin:0 auto;padding:0 1.25rem 4rem}
/* ★backdrop-filter 를 뺐다. `position:sticky` + `backdrop-filter` + 반투명 배경은
   새 합성 레이어를 만들고, 그 아래 요소의 hover 하이라이트가 **어긋난 위치에 칠해진다.**
   운영 콘솔에서 마우스가 가리키는 곳과 강조되는 곳이 다르면 오조작으로 이어진다.
   불투명 배경으로 바꿔 그 원인을 없앤다 — 흐림 효과보다 정확도가 먼저다. */
.topbar{position:sticky;top:0;z-index:5;background:var(--bg);
  border-bottom:1px solid var(--line);margin-bottom:1.75rem}
.topbar__in{max-width:1180px;margin:0 auto;padding:.7rem 1.25rem;display:flex;
  align-items:center;gap:1.25rem;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:-.02em;margin-right:.25rem}
.brand span{color:var(--text-dim);font-weight:500;font-size:.82rem;margin-left:.5rem}
nav{display:flex;gap:.25rem;flex-wrap:wrap}
nav a{color:var(--text-dim);text-decoration:none;padding:.35rem .7rem;border-radius:99px;
  font-size:.9rem;font-weight:500}
nav a:hover{background:var(--surface);color:var(--text)}
nav a[aria-current=page]{background:var(--accent-weak);color:var(--accent);font-weight:600}
h1{font-size:1.5rem;letter-spacing:-.02em;margin:.25rem 0 .35rem}
h2{font-size:1.03rem;letter-spacing:-.01em;margin:0}
h3{font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-dim);margin:1.25rem 0 .5rem}
.lede{color:var(--text-dim);margin:0 0 1.5rem}
a{color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:1.1rem 1.25rem;margin:0 0 1rem;box-shadow:var(--shadow)}
.card__head{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;
  flex-wrap:wrap;margin-bottom:.9rem}
.card__sub{margin:0;color:var(--text-dim);font-size:.85rem}
.card--critical{border-left:3px solid var(--critical)}
.card--warn{border-left:3px solid var(--warn)}
.card--fold{padding:0}
.card__head--fold{display:flex;align-items:baseline;gap:.7rem;flex-wrap:wrap;cursor:pointer;
  list-style:none;user-select:none;padding:1rem 1.25rem;margin:0}
.card__head--fold::-webkit-details-marker{display:none}
.card__head--fold::after{content:"▾";color:var(--text-dim);font-size:.85rem;margin-left:auto}
.card--fold:not([open]) .card__head--fold::after{content:"▸"}
.card__head--fold:hover h2{color:var(--accent)}
.card--fold[open] .card__head--fold{border-bottom:1px solid var(--line)}
.card__body{padding:1rem 1.25rem 1.15rem}
.grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));margin-bottom:1rem}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:.9rem 1.05rem;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:.15rem}
.stat__label{font-size:.78rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:.05em}
.stat__value{font-size:1.7rem;font-weight:650;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.stat__hint{font-size:.8rem;color:var(--text-dim)}
.stat--critical{border-left:3px solid var(--critical)} .stat--critical .stat__value{color:var(--critical)}
.stat--warn{border-left:3px solid var(--warn)} .stat--warn .stat__value{color:var(--warn)}
.stat--done .stat__value{color:var(--done)}
.scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:.6rem .7rem;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-size:.73rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim);
  font-weight:600;white-space:nowrap;background:var(--surface-2)}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
td.muted,.muted{color:var(--text-dim)}
.kv .kv__key{width:34%;color:var(--text-dim);font-weight:500;font-size:.85rem}
.kv .kv__val{font-family:var(--mono);font-size:.82rem;white-space:pre-wrap;word-break:break-word}
.mono,code,pre{font-family:var(--mono)}
/* ★UUID 가 표 안에서 4줄로 접히면 한 화면에 보이는 행이 확 준다.
   한 줄로 두고 넘치는 폭은 .scroll-x 가 가로 스크롤로 받는다.
   ID 를 잘라 보여주지 않는 이유 — 운영자가 로그와 대조하려면 전체가 필요하다. */
td.mono,td .mono{white-space:nowrap}
code{background:var(--surface-2);border:1px solid var(--line);border-radius:5px;
  padding:.08rem .35rem;font-size:.82rem;word-break:break-all}
pre{background:var(--surface-2);border:1px solid var(--line);border-radius:8px;padding:.8rem;
  overflow-x:auto;font-size:.82rem;margin:.4rem 0}
.pill{display:inline-flex;align-items:center;gap:.35rem;border-radius:99px;padding:.13rem .6rem;
  font-size:.78rem;font-weight:600;white-space:nowrap;border:1px solid transparent}
.pill::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.pill--critical{background:var(--critical-bg);color:var(--critical)}
.pill--warn{background:var(--warn-bg);color:var(--warn)}
.pill--active{background:var(--active-bg);color:var(--active)}
.pill--done{background:var(--done-bg);color:var(--done)}
.pill--idle{background:var(--idle-bg);color:var(--idle)}
.notice{border-radius:9px;padding:.6rem .85rem;margin:.5rem 0;font-size:.88rem;
  border:1px solid transparent}
.notice--warn{background:var(--warn-bg);color:var(--warn);border-color:currentColor}
.notice--critical{background:var(--critical-bg);color:var(--critical);border-color:currentColor}
.notice--info{background:var(--surface-2);color:var(--text-dim);border-color:var(--line)}
.ev-list{list-style:none;margin:.4rem 0 0;padding:0;display:grid;gap:.5rem}
.ev{border-left:3px solid var(--done);background:var(--surface-2);border-radius:0 8px 8px 0;
  padding:.55rem .8rem}
.ev__type{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim);
  font-weight:600;margin-right:.5rem}
.ev__id{font-size:.78rem}
.ev__claim{margin:.3rem 0 0;font-size:.88rem}
.dist{list-style:none;margin:.3rem 0 0;padding:0;display:grid;gap:.45rem}
.dist__row{display:grid;grid-template-columns:minmax(130px,auto) 1fr auto;align-items:center;gap:.7rem}
.dist__track{background:var(--surface-2);border-radius:99px;height:8px;overflow:hidden}
.dist__fill{display:block;height:100%;border-radius:99px}
.dist__fill--critical{background:var(--critical)} .dist__fill--warn{background:var(--warn)}
.dist__fill--active{background:var(--active)} .dist__fill--done{background:var(--done)}
.dist__fill--idle{background:var(--idle)}
.dist__n{font-variant-numeric:tabular-nums;font-weight:600;font-size:.88rem}
.timeline{list-style:none;margin:0;padding:0 0 0 1.35rem;position:relative}
.timeline::before{content:"";position:absolute;left:5px;top:.5rem;bottom:.5rem;width:2px;
  background:var(--line)}
.tl{position:relative;margin-bottom:.85rem}
.tl::before{content:"";position:absolute;left:-1.35rem;top:.55rem;width:12px;height:12px;
  border-radius:50%;background:var(--surface);border:2px solid var(--accent)}
.tl__head{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.tl__v{font-family:var(--mono);font-size:.78rem;font-weight:700;color:var(--accent);
  background:var(--accent-weak);border-radius:5px;padding:.05rem .4rem}
.tl__meta{color:var(--text-dim);font-size:.8rem;margin:.2rem 0 .35rem}
.actions{display:flex;gap:.6rem;margin-top:1rem;flex-wrap:wrap}
button{font:inherit;font-weight:600;font-size:.88rem;padding:.5rem 1.1rem;border:1px solid transparent;
  border-radius:8px;background:var(--accent);color:#fff;cursor:pointer}
/* ★`filter` 대신 색을 직접 바꾼다. filter 는 hover 동안만 containing block 을 만들어
   자식의 배치 기준을 바꾼다 — 지금은 자식이 없어 안전하지만 같은 부류의 원인이다. */
button:hover:not(:disabled){background:var(--accent-strong)}
button.ghost:hover:not(:disabled){background:var(--critical-bg)}
button.ghost{background:transparent;color:var(--critical);border-color:var(--critical)}
button:disabled{background:var(--idle-bg);color:var(--text-dim);cursor:not-allowed;
  border-color:var(--line)}
.choice .hint,.hint{display:block;width:100%;font-size:.78rem;color:var(--warn);
  font-weight:500;margin-top:.15rem}
/* ── 구조도: 실행 순서 레일 ── */
.flow{list-style:none;margin:0;padding:0 0 0 1.6rem;position:relative;counter-reset:none}
.flow::before{content:"";position:absolute;left:11px;top:.9rem;bottom:.9rem;width:2px;
  background:var(--line)}
.stage{position:relative;margin-bottom:1.15rem}
.stage__head{display:flex;align-items:center;gap:.6rem;cursor:pointer;list-style:none;
  user-select:none;padding:.15rem 0}
.stage__head::-webkit-details-marker{display:none}
.stage__head::after{content:"▾";color:var(--text-dim);font-size:.8rem;margin-left:auto}
.stage__body:not([open]) .stage__head::after{content:"▸"}
.stage__head:hover .stage__title{color:var(--accent)}
.stage__tally{font-size:.76rem;color:var(--text-dim);font-variant-numeric:tabular-nums}
.stage__n{position:absolute;left:-1.6rem;top:.25rem;width:24px;height:24px;border-radius:50%;
  background:var(--accent);color:#fff;font-size:.76rem;font-weight:700;
  display:grid;place-items:center;font-variant-numeric:tabular-nums}
.stage__title{margin:0;font-size:.95rem;text-transform:none;letter-spacing:-.01em;color:var(--text)}
.stage__note{margin:.15rem 0 .4rem;color:var(--text-dim);font-size:.82rem}
.nodes{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.45rem}
.node{display:flex;flex-direction:column;gap:.1rem;border-radius:9px;padding:.45rem .7rem;
  border:1px solid var(--line);background:var(--surface-2);min-width:0}
.node__name{font-weight:600;font-size:.85rem}
.node__kind{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim)}
.node__hint{font-size:.76rem;color:var(--text-dim)}
/* ★컴포넌트는 실선 — 끌 수 없다. 모듈은 점선 — 선택이다. */
.node--component{border-style:solid;border-left:3px solid var(--accent)}
.node--module{border-style:dashed;border-left:3px dashed var(--done)}
.node--instance{border-style:dashed;border-left:3px dashed var(--warn)}
.node--off{opacity:.5}
.node--off .node__name{text-decoration:line-through}
.node--off.node--module{border-left-color:var(--idle)}
@media (max-width:640px){.nodes{flex-direction:column}.node{width:100%}}
.raw{margin:.6rem 0 0;border-top:1px solid var(--line);padding-top:.5rem}
.raw summary{cursor:pointer;color:var(--text-dim);font-size:.82rem;font-weight:600;
  list-style:none;user-select:none}
.raw summary::-webkit-details-marker{display:none}
.raw summary::before{content:"▸ ";color:var(--accent)}
.raw[open] summary::before{content:"▾ "}
.empty{text-align:center;color:var(--text-dim);padding:3rem 1rem;background:var(--surface);
  border:1px dashed var(--line);border-radius:var(--radius)}
.empty p{margin:.2rem 0}
.choice{display:flex;align-items:center;gap:.5rem;padding:.55rem .7rem;border:1px solid var(--line);
  border-radius:8px;background:var(--surface-2);margin:.4rem 0}
.choice input{accent-color:var(--accent)}
.field{display:flex;flex-direction:column;gap:.35rem;margin:.7rem 0;color:var(--text-dim);font-size:.85rem}
input,select{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--line);
  border-radius:7px;padding:.5rem .6rem;max-width:100%}
input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}
.alert-card{border:2px solid var(--critical);background:var(--critical-bg);color:var(--text)}
.alert-card h2{color:var(--critical)}
.success{border-left:3px solid var(--done)}
.error{border-left:3px solid var(--critical)}
@media (max-width:640px){
  .dist__row{grid-template-columns:1fr auto}
  .dist__track{display:none}
  h1{font-size:1.3rem}
}
"""


def page(title: str, body: str, *, current: str = "", lede: str = "",
         nav: tuple[tuple[str, str], ...] | None = None) -> str:
    """Render one operator page.

    ★`nav` 를 받는 이유는 꺼진 모듈의 메뉴를 지우기 위해서다. 없는 화면으로
      가는 링크를 남겨 두면 눌렀을 때 404 가 뜨고, 운영자는 서버가 죽은 줄 안다
      (`docs/handoff/08` §2 — 모듈을 빼면 그 표면도 함께 빠져야 한다).
    """
    links = "".join(
        f"<a href='{href}'{' aria-current=page' if href == current else ''}>{esc(label)}</a>"
        for href, label in (NAV if nav is None else nav))
    lede_html = f"<p class='lede'>{esc(lede)}</p>" if lede else ""
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · A-COP</title><style>{CSS}</style></head><body>"
        f"<div class='topbar'><div class='topbar__in'>"
        f"<span class='brand'>A-COP<span>운영 콘솔</span></span><nav>{links}</nav></div></div>"
        f"<main class='shell'><h1>{esc(title)}</h1>{lede_html}{body}</main></body></html>")
