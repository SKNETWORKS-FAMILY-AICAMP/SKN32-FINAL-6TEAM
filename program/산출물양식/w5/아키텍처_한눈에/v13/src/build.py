# -*- coding: utf-8 -*-
"""v11 산출물 만들기 (v10 + 멀티에이전트 플로우 상세) — 그림별 HTML · SVG · PNG + 문서 HTML · PNG · md (2026-10-02)

    python build.py

- 그림: figs.py (diagram-design 스킬 규칙 · acop 스킨). 그리기 전에 dd.Fig.check() 로 규칙 검사 — 하나라도 걸리면 멈춘다
- SVG: 스킬 export.md 절차 — 첫 <svg> 를 꺼내 Google Fonts @import(&amp;) 를 넣고 <?xml 머리를 붙인다
- PNG: 스킬 export.md 절차 — Playwright 로 원본 HTML 을 열어 svg 만 2배로 찍는다(배경 투명)
- 문서 PNG: 문서 HTML 전체를 한 장으로 찍는다
"""
import re
import sys
from html import escape
from pathlib import Path

from figs import fig_arch, fig_layers, fig_loop
from flow import fig_flow

ALL = [("그림1_멀티에이전트_플로우", fig_flow), ("그림2_바깥루프", fig_loop),
       ("그림3_전체구조", fig_arch), ("그림4_툴_데이터층", fig_layers)]

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
VER = "v11"
FONT_LINK = ('<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600'
             '&family=Geist+Mono:wght@400;500;600&family=Noto+Sans+KR:wght@400;500;600&family=Noto+Serif+KR:wght@400&display=swap" rel="stylesheet">')
FONT_IMPORT = ("@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&amp;family=Geist:wght@400;500;600"
               "&amp;family=Geist+Mono:wght@400;500;600&amp;family=Noto+Sans+KR:wght@400;500;600&amp;family=Noto+Serif+KR:wght@400&amp;display=swap');")

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#fbfcfd;--paper-2:#f1f4f8;--ink:#161c28;--muted:#6b7488;--soft:#7a8599;--rule:rgba(22,28,40,.12);
--accent:#a8720c;--accent-tint:rgba(168,114,12,.10);--link:#2f5bd8;
--sans:'Geist','Noto Sans KR','Malgun Gothic',system-ui,sans-serif;--serif:'Instrument Serif','Noto Serif KR',serif;--mono:'Geist Mono',ui-monospace,monospace}
body{font-family:var(--sans);background:var(--paper);color:var(--ink);line-height:1.7;font-size:15px;padding:3rem 2rem}
.frame{max-width:1200px;margin:0 auto}
.eyebrow{font-family:var(--mono);font-size:.66rem;font-weight:500;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:.5rem}
h1{font-family:var(--serif);font-size:2rem;font-weight:400;letter-spacing:-.01em;line-height:1.2;margin-bottom:1rem}
h2{font-family:var(--serif);font-size:1.5rem;font-weight:400;margin:3rem 0 .5rem;padding-top:1.25rem;border-top:1px solid var(--rule)}
p{max-width:860px;margin:0 0 .9rem}
.lead{font-size:16px}
strong{font-weight:600}
code{font-family:var(--mono);font-size:.86em;background:var(--paper-2);padding:.1em .35em;border-radius:4px}
figure{margin:1.25rem 0 0}
figure svg{width:100%;display:block}
figcaption{font-size:13px;color:var(--muted);margin-top:.5rem;max-width:860px}
.fig-wide svg{min-width:900px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:1rem 0;background:#fff}
th,td{border:1px solid var(--rule);padding:8px 12px;text-align:left;vertical-align:top}
th{background:var(--paper-2);font-weight:600}
td:first-child{font-weight:600;white-space:nowrap}
.cards{display:grid;grid-template-columns:1.2fr 1fr .9fr;gap:16px;margin:1.25rem 0}
.card{background:#fff;border:1px solid var(--rule);border-radius:6px;padding:1.25rem}
.card h3{font-size:15px;font-weight:600;margin-bottom:.5rem;display:flex;align-items:center;gap:8px}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--ink)}
.dot.accent{background:var(--accent)}.dot.link{background:var(--link)}.dot.soft{background:var(--soft)}
.card ul{padding-left:1.1rem;font-size:14px}
.status{border-left:3px solid var(--accent);background:var(--accent-tint);padding:.9rem 1.1rem;border-radius:0 6px 6px 0;font-size:14px;max-width:none}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--rule);font-family:var(--mono);font-size:11px;color:var(--muted)}
@media (max-width:760px){.cards{grid-template-columns:1fr}body{padding:2rem 1rem}}
"""

INTRO = ("triPilot 은 <strong>외부 에이전트가 짠 여행 일정을 받아 확인하고, 여행이 끝날 때까지 지키는</strong> 서비스입니다. "
         "에이전트는 <strong>요식 · 액티비티 둘</strong>이고, 이동은 에이전트가 아니라 <strong>모두가 부르는 공용 판정 툴</strong>입니다. "
         "루프는 둘입니다 — <strong>바깥 루프</strong>는 여행 기간 동안 1분마다 감시 → 배정 → 재점검 → 검증 · 반영 → 알림을 돌고, "
         "<strong>안쪽 루프</strong>는 에이전트가 통과하는 곳이 나올 때까지 다음 후보를 다시 점검합니다. "
         "고객 채팅과 새벽 영업 확인은 에이전트를 거치지 않고 <strong>같은 계산과 같은 반영</strong>을 씁니다. "
         "첫 그림이 에이전트 사이의 흐름 전체 — 누가 무엇을 받아 어떤 툴을 부르고 무엇을 넘기는지 — 입니다.")

SECTIONS = {
    "그림1_멀티에이전트_플로우": ("1. 멀티에이전트 플로우 — Case 한 건이 지나가는 길",
        "낮 감시가 깨진 항목을 찾으면 Case(처리할 건 하나)를 엽니다. 오케스트레이터는 문제 코드 앞부분(식사 dining_ · 활동 activity_)으로 "
        "담당 에이전트 <strong>하나</strong>를 고르고, 할 일 묶음 — 할 일 종류 · 지금 상태와 근거 묶음 · 허용 툴 목록 · 마감 90초 — 을 넘깁니다. "
        "에이전트는 허용된 툴로만 읽고, 지금 항목을 다시 점검한 뒤 대체 후보를 <strong>한 곳씩</strong> 다시 점검해(굵은 선) 변경 제안을 냅니다. "
        "제안은 바로 반영되지 않습니다 — 오케스트레이터의 사실 대조와 적용기의 재확인을 거친 뒤, 물어볼 일정이면 묻고 아니면 새 일정 버전으로 저장됩니다.",
        "예 — 저녁 식당 근처에 재난문자가 걸리면: 감시가 식사 Case 를 열고 → 요식 에이전트가 그 식당을 다시 점검(깨짐) → 요식 원장 후보를 순위대로 "
        "최대 3곳 다시 점검 → 최선 1곳 + 다른 안 2곳을 제안 → 대조 · 재확인 통과 → 「먼저 물어봐」를 고른 고객이면 묻고, 아니면 새 버전 저장 + 되돌리기 버튼과 함께 "
        "Discord 알림. 툴은 허용 목록 밖이면 거부, 같은 툴 · 같은 인자는 한 번만, 한 실행에 12회까지입니다. 굵은 선 넷이 루프입니다 — 후보 재점검 둘, "
        "고객 응답 뒤 다시 확인, 다음 1분 감시. 이동은 에이전트가 아니라 반영할 때 앞뒤 이동을 다시 계산하는 공용 툴입니다"
        "(코드에는 아직 경로 사건 Case 를 받는 팀으로도 등록돼 있어 정리가 필요합니다)."),
    "그림2_바깥루프": ("2. 바깥 루프 — 여행 기간 동안 1분마다",
        "등록된 여행은 낮 감시가 1분마다 앞으로 90분 안의 항목을 외부 6범주(기상 · 특보 · 지진 · 재난문자 · 교통 · 대기질)로 점검합니다. "
        "깨진 항목이 있을 때만 Case(처리할 건 하나)를 열고 한 바퀴를 돕니다. 깨진 것이 없으면 감시에서 멈추고 다음 1분을 기다립니다.",
        "점선은 가운데 여행 기록(DB)에 남기는 것 — 감시는 Case, 반영은 새 일정 버전, 알림은 발송 기록. "
        "여행이 끝나면 앞으로 90분 안에 볼 항목이 없어 감시할 것이 없습니다(여행 종료를 상태로 바꾸는 코드는 확인하지 못했습니다)."),
    "그림3_전체구조": ("3. 전체 구조 — 들어오는 길 셋, 반영은 하나",
        "여행자의 요청은 모두 API 서버로 들어옵니다. 들어오는 길은 셋입니다 — <strong>계획 등록</strong>(감시 대상이 됨), "
        "<strong>낮 감시</strong>(오케스트레이터 → 에이전트), <strong>고객 채팅 · 새벽 점검</strong>(에이전트를 거치지 않는 점선). "
        "셋 다 같은 검증 · 반영을 거쳐 알림과 계획서 링크로 여행자에게 돌아갑니다.",
        "상자 안 I = 받는 것, O = 내보내는 것. 오케스트레이터는 규칙으로 담당 에이전트 하나를 고르고(에이전트끼리 직접 부르지 않음), "
        "에이전트 한 번의 시간 제한은 90초입니다. 진행 신호(SSE)와 일정 변경 신호는 웹 화면으로 따로 갑니다."),
    "그림3_에이전트_안쪽루프": ("3. 에이전트 안쪽 루프 — 통과할 때까지 다음 후보",
        "에이전트는 먼저 지금 항목을 같은 외부 점검으로 다시 봅니다. 깨졌으면 후보를 <strong>한 곳씩</strong> 점검하고, "
        "더 볼 후보가 있으면 되돌아갑니다(굵은 선). 다 본 뒤 통과한 곳이 있으면 최선 1곳과 다른 안 최대 2곳을 변경 제안으로 냅니다.",
        "예 — 저녁 식당이 오늘 임시 휴무면, 순위가 높은 대체 식당부터 영업 · 브레이크 · 라스트오더를 다시 보고 통과한 곳을 제안합니다. "
        "툴은 허용 목록 안에서만, 같은 툴 · 같은 인자는 한 번만, 한 실행에 12회까지 부를 수 있습니다."),
    "그림4_검증_묻기루프": ("4. 검증 · 묻기 루프 — 고객이 고르면 다시 검증",
        "변경 제안은 어느 길에서 왔든 같은 검증을 거칩니다. 고객이 고정했거나 예약번호가 있는 <strong>보호 일정</strong>, "
        "「먼저 물어봐」를 고른 고객, 날씨만 걸렸는데 실내인지 모르는 활동이면 바로 바꾸지 않고 묻습니다. "
        "고객이 다른 안을 고르면 그 선택을 <strong>다시 검증</strong>합니다(굵은 선).",
        "새 일정 버전을 저장할 때 이전 판은 지우지 않고 남기고, 앞뒤 이동은 공용 이동 판정 툴로 다시 계산합니다. "
        "알림은 같은 내용이 두 번 쌓이지 않게 막고, 첫 발송 포함 최대 3번 시도합니다. 사람에게 넘기는 단계는 없습니다 — 운영자는 오류 알림만 받습니다."),
    "그림4_툴_데이터층": ("4. 에이전트 · 툴 · 데이터 층",
        "에이전트는 DB 와 외부 API 를 직접 열지 않습니다. <strong>툴 레이어(허용 목록)</strong>가 에이전트가 닿는 유일한 문이고, "
        "판정은 코드가 합니다. 조회가 안 되거나 값이 비면 「모름」, 정상 조회의 빈 결과는 「없음」으로 구분해 돌려줍니다.",
        "그림의 툴 여섯 개는 주요 예시입니다 — 전체 허용 목록은 에이전트 등록 정보(manifest)에 있습니다. "
        "이동 판정 툴은 코드에 아직 팀으로 등록돼 있어 공용 툴로 정리가 필요합니다."),
}

TABLE = [
    ("트리거 — 낮 감시", "앞으로 90분 안 항목, 외부 6범주", "문제 항목 + 원인 → Case 1건", "1분마다 점검 — 깨진 것만 Case 로"),
    ("트리거 — 새벽 영업 확인", "그날 식사 · 활동, Google 영업 정보", "닫힌 곳의 근처 대체 → 묻기 / 반영", "03~08시 · 에이전트를 거치지 않는 직접 계산"),
    ("채팅 처리 (TripDesk)", "고객 문장(바꿔 줘 · 늦어요 · 다른 안 · 되돌리기 · 질문)", "변경 · 제안 · 답변 (질문은 일정 그대로)", "에이전트와 같은 계산 코드를 직접 부른다"),
    ("오케스트레이터", "Case (문제 코드 · 원인)", "담당 에이전트 1개, 할 일 · 허용 툴 · 컨텍스트", "규칙 라우팅 · 에이전트 시간 제한 90초"),
    ("요식 에이전트", "식사 항목 · 원인 · 식이 조건", "그대로 / 대체 식당 1 + 다른 안 최대 2 / 못 함", "read.itinerary · read.disruptions · read.place_catalog · read.dining_alternatives · read.dining_state — 순위순 최대 3곳 재점검"),
    ("액티비티 에이전트", "활동 항목 · 원인 · 실내 여부 · 설문", "그대로 / 대체 활동 + 다른 안 / 바꿀까요? / 못 함", "read.itinerary · read.disruptions · read.place_catalog — 날씨만 + 실내 모름이면 먼저 「바꿀까요?」"),
    ("이동 판정 툴 (공용 · 에이전트 아님)", "두 장소 · 목표 도착 시각 · 앞 일정 종료 시각", "경로 · 소요 · 판정(성립 / 불가 / 모름)", "반영 때 앞뒤 이동 재계산 · 일정 생성 (후보 재점검 연결은 아직)"),
    ("검증 + 반영", "변경 제안", "새 일정 버전 / 사용자에게 묻기 / 거부", "고객 소유 · Case 버전 · 여행 기준 버전 · 항목 · 장소 확인"),
    ("알림 (아웃박스 워커)", "등록 · 변경 · 묻기 알림, 정기 안내", "Discord 웹훅 알림 + 계획서 링크", "중복 방지 키 · 첫 발송 포함 최대 3회"),
    ("계획 읽기 · 일정 생성", "계획 원문 / 「일정 짜 줘」 선호", "일정 항목 + 근거 줄 / 판정을 통과한 초안", "규칙 먼저 · AI 는 줄 위치 · 받아쓰기 · 순서 제안만"),
]

CYCLE = ("대표 순환은 <strong>감시 → Case → 오케스트레이터 → 에이전트(후보 재점검 루프) → 검증 · 묻기 · 반영 → 알림 → 다음 1분 감시</strong>입니다. "
         "이 순환이 triPilot 의 핵심 — 계획을 받아 여행이 끝날 때까지 지킨다 — 을 보여 줍니다. "
         "고객 채팅 · 새벽 영업 확인 · 일정 생성 · 정기 안내(하루 시작 · 다음 일정 · 출발)는 별도 길이며 같은 계산과 버전 저장을 함께 씁니다.")

STATUS = ("지금 상태 — <strong>구현</strong>: 일정 등록 거절(이유 + 고칠 방법) · 고객 채팅 · 다른 안 · 되돌리기 · 일정 생성 · 정기 안내 · 일정 변경 SSE. "
          "<strong>진행 중</strong>: 접수 · 생성 · 채팅 진행 SSE(서버 구현, 웹 연결 중). "
          "<strong>아직 없음</strong>: 실패 항목을 채팅으로 대안 추천 · 후보 재점검의 이동 판정 연결. "
          "알림은 팀 Discord 채널 하나(개인 Discord 는 등록 · 시험 발송까지). 로그인 · AWS 자동 배포는 팀 계획(코드 없음). AI 모델은 로컬 · API 비교 시험 중.")

CARDS = [
    ("accent", "루프 둘", ["바깥: 1분마다 감시 → 반영 → 알림 → 다시 감시", "안쪽: 통과할 때까지 다음 후보 점검", "묻기: 고객이 고르면 다시 검증"]),
    ("", "코드가 정하는 것", ["일정 성립 · 영업 · 시간 판정", "반영 여부와 묻기 조건", "툴 허용 목록 · 12회 상한"]),
    ("soft", "AI 가 하는 것", ["계획서 줄 위치 · 사진 받아쓰기", "문장 해석 · 후보 순서 제안", "영업시간 원문 정리 · 문장 작성"]),
]


def fig_html(name, f):
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{escape(f.title)}</title>{FONT_LINK}<style>{CSS} body{{display:flex;justify-content:center}}</style></head>'
            f'<body><div class="frame"><p class="eyebrow">triPilot · 시스템 아키텍처 {VER}</p><h1>{escape(f.title)}</h1>'
            f'<figure class="fig-wide">{f.svg()}</figure></div></body></html>')


def doc_html(figs):
    parts = [f'<p class="eyebrow">triPilot · Multi-Agent 구조 · {VER} · 2026-10-02</p>',
             "<h1>계획을 받아 여행이 끝날 때까지 지키는 구조</h1>",
             f'<p class="lead">{INTRO}</p>',
             '<div class="cards">' + "".join(
                 f'<div class="card"><h3><span class="dot {c}"></span>{escape(t)}</h3><ul>' + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul></div>"
                 for c, t, items in CARDS) + "</div>"]
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        parts.append(f"<h2>{escape(h)}</h2><p>{body}</p><figure class=\"fig-wide\">{f.svg()}<figcaption>{cap}</figcaption></figure>")
        if name == "그림2_전체구조":
            pass
    parts.append("<h2>구성별 받는 것 · 내보내는 것</h2>")
    parts.append("<table><thead><tr><th>구성</th><th>받는 것 (I)</th><th>내보내는 것 (O)</th><th>하는 일</th></tr></thead><tbody>"
                 + "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in TABLE) + "</tbody></table>")
    parts.append(f"<p>{CYCLE}</p>")
    parts.append(f'<p class="status">{STATUS}</p>')
    parts.append(f"<footer>triPilot · A-COPilot · 그림: diagram-design 스킬(acop 스킨) · 사실 근거: v9 코덱스 검토(../v9/코덱스_검토결과_v8.md) · {VER}</footer>")
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>triPilot 아키텍처 {VER}</title>{FONT_LINK}<style>{CSS}</style></head><body><div class="frame">'
            + "\n".join(parts) + "</div></body></html>")


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).replace("<strong>", "")


def md_text(figs):
    md = [f"{strip_tags(INTRO).replace('— ', '— ')}", ""]
    md[0] = re.sub(r"(외부 에이전트가 짠 여행 일정을 받아 확인하고, 여행이 끝날 때까지 지키는)", r"**\1**", md[0])
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        md += [f"## {h}", "", strip_tags(body), "", f"![{f.title}]({name}_{VER}.png)", "", f"> {strip_tags(cap)}", ""]
    md += ["## 구성별 받는 것 · 내보내는 것", "", "| 구성 | 받는 것 (I) | 내보내는 것 (O) | 하는 일 |", "|---|---|---|---|"]
    md += ["| **" + r[0] + "** | " + " | ".join(r[1:]) + " |" for r in TABLE]
    md += ["", strip_tags(CYCLE), "", "> " + strip_tags(STATUS), ""]
    return "\n".join(md)


def export(figs, doc_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        for name, f in figs:
            src = OUT / f"{name}_{VER}.html"
            page = br.new_page(device_scale_factor=2, viewport={"width": 1280, "height": 900})
            page.goto(src.as_uri(), wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            page.evaluate("document.fonts.ready.then(() => true)")
            ok = page.evaluate("document.fonts.check(\"600 12px 'Noto Sans KR'\") && document.fonts.check(\"12px 'Geist Mono'\")")
            page.locator("svg").first.screenshot(path=str(OUT / f"{name}_{VER}.png"), omit_background=True)
            print("png", name, "fonts", ok)
            page.close()
        page = br.new_page(device_scale_factor=2, viewport={"width": 1280, "height": 900})
        page.goto(doc_path.as_uri(), wait_until="load", timeout=60000)
        page.wait_for_timeout(4000)
        page.evaluate("document.fonts.ready.then(() => true)")
        page.screenshot(path=str(doc_path.with_suffix(".png")), full_page=True)
        print("png doc")
        br.close()


def svg_file(f):
    s = f.svg()
    s = s.replace("<defs>", f"<defs><style>{FONT_IMPORT}</style>", 1)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + s


def main():
    figs = [(n, fn()) for n, fn in ALL]
    bad = False
    for n, f in figs:
        e = f.check()
        if e:
            bad = True
            print(n, *e, sep="\n  - ")
    if bad:
        sys.exit("규칙 검사 실패 — 내보내지 않음")
    for n, f in figs:
        (OUT / f"{n}_{VER}.html").write_text(fig_html(n, f), encoding="utf-8")
        (OUT / f"{n}_{VER}.svg").write_text(svg_file(f), encoding="utf-8")
    doc = OUT / f"triPilot_아키텍처_{VER}.html"
    doc.write_text(doc_html(figs), encoding="utf-8")
    (OUT / f"triPilot_아키텍처_{VER}.md").write_text(md_text(figs), encoding="utf-8")
    if "--no-png" not in sys.argv:
        export(figs, doc)


if __name__ == "__main__":
    main()
