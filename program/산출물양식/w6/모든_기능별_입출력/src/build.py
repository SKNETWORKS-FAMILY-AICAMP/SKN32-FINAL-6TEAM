# -*- coding: utf-8 -*-
"""w6 모든 기능별 입출력 — 목차(00) + 기능 페이지(01~15) 생성.

    python build.py

출력은 이 폴더의 한 단계 위(w6/모든_기능별_입출력/)에 HTML 로 쓴다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE.parent

from lib import CSS, LEGEND, NAV, esc  # noqa: E402
import p01_06  # noqa: E402
import p07_11  # noqa: E402
import p10  # noqa: E402
import p12_15  # noqa: E402

FEATURES = [
    ("01", "일정 문제 감시", "시계(3분 주기) · 모니터링", "3분마다 · 90분 안 시작하는 항목"),
    ("02", "처리 건 열기 · 담당 고르기", "접수기 · 담당 등록 목록", "감시 사건 또는 고객 문장이 들어올 때"),
    ("03", "작업 지시서 (TeamTask)", "코어 → 담당 에이전트 (공통)", "처리 건을 실행할 때마다"),
    ("04", "처리 결과지 (TeamResult)", "담당 에이전트 → 코어 (공통)", "담당의 실행이 끝났을 때"),
    ("05", "일정 관리 공통 순서", "요식 · 액티비티 공통 흐름", "담당이 지시서를 받은 뒤"),
    ("06", "외부 정보 6종 점검", "조회 도구(공용) · 판정", "감시 · 에이전트가 장소를 점검할 때"),
    ("07", "요식 에이전트 (AG-DINING)", "규칙 코드 (언어 모델 없음)", "식사 일정이 깨졌을 때"),
    ("08", "액티비티 에이전트 (AG-ACTIVITY)", "규칙 코드 (언어 모델 없음)", "활동 일정이 깨졌을 때 · 같은 여행 묶음"),
    ("09", "이동 판정 (공용 도구)", "시간표 판정기 · 교통 사건 조회 (에이전트 아님)", "장소를 바꿀 때 · 저장 전 · 이동 사고 · MCP"),
    ("10", "고객 신고 처리", "신고 해석기 · 담당 에이전트", "고객이 늦음 · 휴무 · 품절 등을 신고할 때"),
    ("11", "일정 변경 적용 (itinerary.apply)", "적용기 (승인 없이 적용하는 유일한 적용기)", "담당 제안 · 고객 변경 요청"),
    ("12", "알림 보관과 배달", "보관함 · 배달 작업 · 번역 도우미 [LLM]", "처리 건 상태가 바뀔 때"),
    ("13", "여행 계획 확인 (UC-1)", "계획 읽기 도우미 [LLM] · 등록 검사", "고객이 계획을 올릴 때"),
    ("14", "고객 채팅 (결정 모델)", "결정 모델 [LLM] · 코드의 다섯 길", "고객이 채팅 문장을 보낼 때"),
    ("15", "개인 AI 입구 (MCP)", "개인 AI(외부) · 도구 목록", "고객이 연결한 개인 AI가 도구를 부를 때"),
]

OPEN_ISSUES = [
    "<b>이동의 자리</b>: 설계는 이동을 에이전트가 아닌 공용 도구로 정했지만(2026-10-02 팀 결정), 코드에는 아직 mobility 담당으로 등록돼 있습니다 — 09 · 05 참조.",
    "<b>MCP 도구 개수</b>: 계획 v26 는 14개(읽기 7 · 쓰기 7), 루트 CLAUDE.md 사실표는 「읽기 5 · 쓰기 7」, 코드 등록은 15개(읽기 8 · 쓰기 7)입니다 — 15 참조.",
    "<b>외부 정보 6종</b>: 발표 자료의 6종(날씨 · 특보 · 단기예보 · 재난문자 · ITS · UTIC)과 코드의 6종(예보 · 특보 · 재난문자 · 교통 통제 · 대기질 · 지진)이 다릅니다 — 06 참조.",
    "<b>미연결 판정</b>: 계획 v26 는 「미연결 → 문제 없음」이라고 적지만 결정 15 는 「확인하지 못한 것을 문제 없음으로 읽지 않는다」고 적습니다 — 06 참조.",
    "<b>알림 세 시점</b>: 결정 ②·③(여행 시작 · 항목 출발 시각)이 코드에 있는지 확인하지 못했습니다 — 12 참조.",
    "<b>채팅과 에이전트</b>: 채팅에서 요식 · 액티비티 에이전트로 가는 길은 아직 없습니다 — 14 참조.",
    "<b>숙박 · 항공 · 예약 인계</b>: 등록만 돼 있고 이번 묶음에서 일하지 않습니다(계획 v26 부록 C 「그대로 둠」). 이 묶음에서 뺐습니다.",
]

PDF_MAP = [
    ("1. 범위와 액터 (Cockburn 1 · 2)", "각 장의 「1. 명세 머리」 — 범위 · 수준 · 주 액터 · 보조 액터"),
    ("2. 사용자 목표 · 사전조건 · 트리거 · 보장 (Cockburn 7)", "각 장의 「1. 명세 머리」 — 사전조건 · 트리거 · 최소 · 성공 보장"),
    ("3. 주 성공 시나리오 (Cockburn 8 · G1~G7)", "각 장의 「2. 주 성공 시나리오」 — 주어 + 동사 + 목적어, 3~9단계"),
    ("4. 확장 조건 · 확장 처리 (Cockburn 9 · 10 · G11 · G12)", "각 장의 「3. 확장 · 예외」 — 시나리오 번호에 붙여 씀"),
    ("5. 흐름도 — 시작 · 끝 · 노드 종류 · 분기 조건 · 루프 상한 · 사람 개입", "각 장의 「4. 그림」 — 타원 · 상자 · 마름모 · 점선 · ⏸"),
    ("6. 입력 · 출력 (TeamTask · TeamResult 표)", "각 장의 「5. 입력 · 출력」 — 칸마다 밑줄 값에 설명 상자"),
    ("7. 에이전트 명세 카드 (책임 · 하지 않는 일 · 도구 · 실패 · 가드레일 · 관측 · 예산)", "07 · 08 · 15 장의 「6. 에이전트 명세 카드」 — 이 묶음에서는 15항목을 그대로 씀"),
    ("8. 요구사항 · 화면 · 테스트 연결 (추적표)", "[미확보] — 이 묶음에는 없습니다. 정하실 것: 추적표를 따로 만들지"),
]


def index_html():
    o = [
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>guguroute 모든 기능별 입출력 — 목차</title>",
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">',
        f"<style>{CSS}</style></head><body><div class=\"wrap\">",
        '<p class="eyebrow">guguroute · 모든 기능별 입출력 · 2026-10-12</p>',
        "<h1>모든 기능별 입출력 — 목차</h1>",
        '<div class="sub">기능 15장과 공통 계약 두 장 · 밑줄 친 말과 그림의 상자에 마우스를 올리면 설명이 뜹니다 · 누르면 다른 곳을 누를 때까지 남습니다 · 스크립트 없이 동작</div>',
        "<ul class=\"top\">",
        "<li><b>결론</b>: 여행 계획 확인부터 여행 중 일정 고치기, 개인 AI 입구까지 <b>기능 15장</b>과 그 밑에 깔린 <b>공통 계약 두 장</b>(작업 지시서 · 처리 결과지)을 한 장씩 묶었습니다.</li>",
        "<li><b>그래서 달라지는 것</b>: 기능마다 「누가 · 무엇을 이루려고 · 어떤 순서로 · 무엇을 받고 무엇을 내나」를 한 장에서 읽습니다. 설계와 코드가 다른 곳은 「미확정」 칸에 따로 적었습니다.</li>",
        "<li><b>사용자가 정할 것</b>: 아래 「정할 것 · 설계와 코드가 다른 곳」 일곱 가지입니다. 이동의 자리와 MCP 도구 개수가 가장 먼저 필요합니다.</li>",
        "<li><b>근거 범위</b>: 2026-10-12 기준 코드 경로 확인 · w5 코어_에이전트_입출력 v7 오버레이 111개 대조 · 계획 v26(2026-10-06) · 멘토링 PDF 「유스케이스 &amp; 멀티 에이전트 다이어그램」의 정석 순서.</li>",
        "</ul>",
        "<h2>1. 기능 목록</h2>",
        '<table><thead><tr><th style="width:52px">번호</th><th>기능</th><th>누가 일하나</th><th>언제 일하나</th></tr></thead><tbody>',
    ]
    slug_by_num = {}
    for slug, label in NAV:
        if slug != "00_목차":
            slug_by_num[slug[:2]] = (slug, label)
    for num, name, who, when in FEATURES:
        slug, label = slug_by_num[num]
        o.append(f"<tr><td>{num}</td><td><a href=\"{slug}.html\">{esc(name)}</a></td><td>{esc(who)}</td><td>{esc(when)}</td></tr>")
    o.append("</tbody></table>")

    o.append("<h2>2. 한 장의 짜임 — 정석 순서가 어디에 있나</h2>")
    o.append("<table><thead><tr><th>멘토링 PDF 의 단계</th><th>이 묶음에서 자리</th></tr></thead><tbody>")
    for step, where in PDF_MAP:
        o.append(f"<tr><td>{esc(step)}</td><td>{where}</td></tr>")
    o.append("</tbody></table>")

    o.append("<h2>3. 그림 읽는 법</h2>")
    o.append("<table><thead><tr><th>모양</th><th>뜻</th></tr></thead><tbody>")
    rows = [
        ("타원 (짙은 녹색 실선)", "시작 · 끝"),
        ("빨간 점선 타원", "오류로 끝남 (고객 알림 없음 — 운영 기록만)"),
        ("회색 점선 타원 ⏸", "고객이 고르거나 답할 때까지 기다리는 자리"),
        ("흰 상자", "정해진 규칙대로 하는 코드"),
        ("파란 점선 상자 [LLM]", "언어 모델이 돕는 자리 — 정해진 보기 안에서만 고르고, 결과는 코드가 다시 확인"),
        ("굵은 상자", "담당 에이전트 (자기 일감과 허락된 도구만 씀, 언어 모델 없음)"),
        ("갈색 긴 점선 상자", "공용 도구 (에이전트가 아니라 여러 곳이 부르는 함수)"),
        ("노란 마름모", "코드의 판단 — 화살표 옆 글이 조건"),
        ("노란 화살표 (곡선)", "되돌아가는 반복 — 옆에 상한"),
        ("작은 밑줄 칸", "칸 이름 — 마우스를 올리면 설명 상자"),
    ]
    for shape, meaning in rows:
        o.append(f"<tr><td>{esc(shape)}</td><td>{esc(meaning)}</td></tr>")
    o.append("</tbody></table>")
    o.append(f'<p class="legend">{LEGEND}</p>')

    o.append("<h2>4. 정할 것 · 설계와 코드가 다른 곳</h2><ul>")
    o.extend(f"<li>{s}</li>" for s in OPEN_ISSUES)
    o.append("</ul>")

    o.append("<h2>5. 근거 등급</h2>")
    o.append("<p class='note'>각 칸의 근거는 세 등급으로 적었습니다. "
             "<span class='t yes'>근거 있음</span> = 코드 줄이나 실행 기록으로 확인 · "
             "<span class='t gap'>부분 근거</span> = 일부만 확인 · "
             "<span class='t no'>근거 없음</span> = 계약 문서의 값이거나 기록이 없음. "
             "[미확보] = 이 세션에서 확인하지 못함. [확인 필요] = 코드 경로를 다시 봐야 함.</p>")

    o.append(f'<div class="foot">' + " ".join(f'<a href="{s}.html">{esc(l)}</a>' for s, l in NAV) + "</div>")
    o.append("</div></body></html>")
    return "".join(o)


def main():
    pages = []
    pages += p01_06.build()
    pages += p07_11.build()
    pages += p10.build()
    pages += p12_15.build()
    written = []
    (OUT / "00_목차.html").write_text(index_html(), encoding="utf-8")
    written.append("00_목차.html")
    for slug, html in pages:
        (OUT / f"{slug}.html").write_text(html, encoding="utf-8")
        written.append(f"{slug}.html")
    print(f"{len(written)} files → {OUT}")
    for w in written:
        print(" -", w)


if __name__ == "__main__":
    main()
