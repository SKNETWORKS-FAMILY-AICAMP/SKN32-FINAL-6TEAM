# -*- coding: utf-8 -*-
"""v12 산출물 — 그림 A · B · C (diagram-design 스킬 · acop 스킨) + 문서 HTML · PNG · md (2026-10-03)

    python build_v12.py [--no-png]

문장은 v12/플로우_단계정의_v3_합의.md(코덱스 1 · 2차 적대 검토 합의본)만 쓴다.
"""
import re
import sys
from html import escape
from pathlib import Path

import build as base
from fig_ac import fig_a, fig_c
from fig_b import fig_b

OUT = Path(__file__).resolve().parent.parent
base.OUT = OUT
base.VER = VER = "v12"

ALL = [("그림A_전체지도", fig_a), ("그림B_감시처리건", fig_b), ("그림C_응답_채팅_새벽", fig_c)]

TITLE = "triPilot 멀티에이전트 플로우 — 규칙 기반 요식 · 활동 워커와 선택적 개인 AI 연결"

INTRO = ("triPilot 은 <strong>고객이 낸 여행 계획을 확인해 등록하고, 여행이 끝날 때까지 지키는</strong> 서비스입니다. "
         "이 플로우에는 <strong>네 종류의 참여자</strong>가 있고 그림의 색과 모양으로 가릅니다 — "
         "<strong>LLM 에이전트</strong>(고객이 연결한 개인 AI · 선택, 파란 실선), "
         "<strong>워커 에이전트 둘</strong>(요식 · 액티비티 — 역할 · 허용 툴 · 할 일 계약을 받지만 <strong>판단은 규칙 코드</strong>, 굵은 테두리), "
         "<strong>AI 모델 호출</strong>(에이전트가 아니라 정해진 자리에서 읽기 · 고르기 · 정리 · 번역만, 파란 점선), "
         "<strong>규칙 코드</strong>(처리 총괄 · 일정 반영 전 확인 · 감시 · 알림). 이동은 에이전트가 아니라 <strong>공용 이동 계산</strong>입니다. "
         "<strong>범위</strong> — 팀이 정한 범위는 요식 · 액티비티 워커 둘과 공용 이동 계산입니다. 지금 코드 설정에는 이동 · 예약 인계 · 숙박 · 항공 담당도 남아 있고, "
         "감시는 이동 문제 건도 엽니다. 그림 A 는 정한 범위를 보여 주고, 실제 연결과 다른 곳은 따로 표시합니다.")

HONEST = ("정직하게 말하면 — 안쪽 워커는 다음 행동을 스스로 고르는 LLM 루프가 아니라 허용 툴을 부르는 규칙 코드입니다. "
          "일정을 실제로 바꾸는 시스템이라 판단을 코드에 두었습니다. AI 모델은 고르기 · 옮기기만 하고 값을 만들지 않으며, 결과는 허용 목록 · 원문과 대조합니다"
          "(해석 오류 자체는 남을 수 있습니다). AI 보조가 들어가는 자리는 계획 읽기(사진 받아쓰기 · 원문 조각), 채팅 할 일 고르기, "
          "영업시간 원문 정리(새로 들어온 장소), 알림 번역입니다.")

SECTIONS = {
    "그림A_전체지도": ("그림 A — 전체 지도: 시작점이 둘",
        "줄 세운 순서표가 아니라 <strong>시작점이 여럿인 지도</strong>입니다. 왼쪽은 고객 쪽(계획 제출 · 채팅 · 선택 요청에 답하기), "
        "오른쪽은 시간 쪽(타이머가 감시와 새벽 확인을 돌림)입니다. 모든 길은 아래의 같은 기록(일정 판 · 선택 요청 · 알림)에 쓰지만 "
        "<strong>쓰는 길은 서로 다릅니다</strong> — 감시는 결과 대조와 일정 반영 전 확인을, 새벽은 공통 묻기 판정을, 채팅과 고객 선택은 각자의 확인 · 저장을 거칩니다.",
        "굵은 황토색 선이 반복입니다 — 계획 확인 · 거절 뒤 다시 등록, 타이머의 감시 반복. 워커 안의 후보 반복은 그림 B, "
        "「동의 → 다시 묻기」 · 새벽 재시도는 그림 C 에 있습니다. 개인 AI 는 고객이 연결한 경우에만 같은 입구로 들어오고(일정 제출 때는 원문 읽기를 건너뜀), 쓰기는 설정을 켤 때만 됩니다. 타이머 작업은 감시 → 새벽 확인 → 정기 안내(하루 시작 · 다음 장소 · 출발, 대기 중이면 대기 안내, 경로 확인 실패 · 사건이면 출발 안내 보류) 순서로 돕니다."),
    "그림B_감시처리건": ("그림 B — 감시가 새로 연 문제 한 건",
        "타이머가 감시를 다시 돌리고, 감시가 90분 안에 시작할 항목에서 새 문제를 찾으면 문제 처리 건을 엽니다. 처리 총괄(규칙)이 "
        "식사는 요식 워커, 활동은 액티비티 워커에 <strong>할 일 묶음</strong>(할 일 · 근거 · 허용 툴 · 마감 설정 90초)을 넘기고, "
        "워커는 <strong>후보를 하나씩 다시 점검</strong>(굵은 선)한 뒤 결과를 돌려줍니다 — 요식은 앞 순위부터 모두 합쳐 최대 3곳, 후보 표가 전부 탈락하면 장소 목록에서 한 번 더 찾고(남은 점검 횟수 안에서), 액티비티는 조건을 통과한 후보를 모두 점검한 뒤 순위를 매깁니다. 결과는 나뉘고 대조된 뒤 일정 반영 전 확인을 거치고, "
        "물어볼 조건이면 선택 요청을, 아니면 새 일정 판을 저장해 알림을 쌓습니다.",
        "예 — 저녁 식당 근처에 재난문자가 걸리면: 감시가 식사 문제 건을 열고 → 요식 워커가 그 식당을 다시 점검(문제 지속) → 후보 표에서 그 시각에 "
        "여는 곳을 순위대로 만들고 앞 순위 최대 3곳을 다시 점검 → 남은 후보 중 최선 1 + 다른 안 최대 2 → 대조 · 반영 전 확인 → 「먼저 물어봐」를 고른 고객이면 "
        "선택 요청, 아니면 새 판 저장 + 되돌리기 버튼과 함께 알림. 중단이면 일정은 그대로이고 <strong>이 중단에 대한 고객 알림은 없습니다</strong>."),
    "그림C_응답_채팅_새벽": ("그림 C — 고객 응답 · 채팅 · 새벽 확인 (나란히)",
        "세 길은 <strong>따로 시작</strong>합니다(차례로 이어지는 것이 아닙니다). 선택 요청에 대한 응답은 그대로 · 안 번호 · 동의(바꿔 줘)로 나뉩니다. 후보가 없으면 요청을 닫고 일정을 그대로 둡니다. "
        "<strong>후보 없는 「바꿀까요?」에 동의</strong>하면 후보를 계산해 같은 요청에 <strong>최대 3개 안을 저장하고 알림으로 다시 묻습니다</strong>(굵은 선). 채팅은 AI 모델이 할 일과 대상을 목록 안에서 고르고, "
        "목록 · 대상을 확인 · 기록한 뒤 요청 종류별로 <strong>워커 없이 직접</strong> 처리합니다. 새벽 확인은 같은 점검 작업 안에서 03~08시에 Google 로 영업을 보고, 닫혔으면 대체안과 공통 묻기 판정을 거치며, 조회 실패는 다음 점검에서 재시도합니다(굵은 선).",
        "고객이 고른 안은 고른 순간 열린 요청 · 최신 판 · 항목 · 선택지 · 장소 · 다음 일정을 확인합니다. 활동은 점검기가 연결돼 있으면 외부 사건을 다시 점검하고, 식사는 영업 · 외부 사건을 다시 조회하지 않습니다. "
        "답하지 않으면 자동으로 바꾸지 않지만, 끝난 일정의 제안을 만료로 닫는 처리는 지금 기본 경로에 연결돼 있지 않습니다."),
}

TABLE = [
    ("고객", "사람", "알림 · 계획서 링크, 선택 요청", "계획 원문, 채팅 문장, 안 고르기 · 바꿔 줘", "시작점"),
    ("개인 AI (선택)", "LLM 에이전트", "고객의 지시 · 우리 조회 결과", "같은 입구로 조회 · 신고 · 고르기 (쓰기는 설정 시)", "고객이 연결했을 때만"),
    ("계획 읽기 · 등록", "규칙 코드 + AI 보조", "글 · 사진 · 파일", "등록 + 첫 판 / 거절 + 고칠 방법", "AI 는 사진 받아쓰기 · 원문 조각 가리키기"),
    ("타이머 · 감시", "규칙 코드", "90분 안에 시작할 항목 · 외부 6범주", "새 문제마다 문제 처리 건 1개", "지금 1분 · 팀 결정 3분"),
    ("처리 총괄", "규칙 코드", "문제 처리 건", "담당 하나 + 할 일 묶음 / 결과 대조 · 일정 반영 전 확인 · 묻기 판정", "LLM 이 아니라 규칙"),
    ("요식 워커", "워커 에이전트(규칙)", "식사 항목 · 할 일 묶음", "그대로 / 변경안(최선 1 + 다른 안 최대 2) / 중단", "read.itinerary · read.disruptions · read.dining_alternatives · read.dining_state"),
    ("액티비티 워커", "워커 에이전트(규칙)", "활동 항목 · 설문 · 할 일 묶음", "그대로 / 변경안 / 바꿀까요? / 중단", "read.itinerary · read.disruptions · read.place_catalog"),
    ("공용 이동 계산", "규칙 코드", "두 장소 · 시각", "앞뒤 이동 · 소요", "에이전트 아님 · 지금 코드엔 이동 담당으로도 등록"),
    ("채팅 할 일 고르기", "AI 모델 호출", "문장 + 일정 · 변경 이력 · 화면 선택", "목록 안의 할 일 · 대상", "값은 안 만듦 · 목록 · 대상 확인"),
    ("영업시간 원문 정리 · 알림 번역", "AI 모델 호출", "관광공사 운영시간 원문 · 한국어 문구", "구조화한 영업시간 · 고객 언어 문구", "판정은 코드가 함"),
    ("새벽 영업 확인", "규칙 코드", "그날 식사 · 활동 · Google 영업", "대체안 → 공통 묻기 판정 → 선택 요청 / 변경", "03~08시 · 조회 실패는 다음 점검에서 재시도"),
    ("알림 배달", "규칙 코드", "변경 · 선택 요청 · 안전 · 정기 안내 기록", "Discord 발송 시도 + 계획서 링크", "따로 도는 1분 작업(도착 시간 보장 아님) · 일반 오류 첫 시도 포함 최대 3번 · 시간 초과 · 연결 오류는 수신 불명으로 기록하고 재시도 안 함"),
]

DEFECTS = [
    "감시 주기 — 팀 결정은 3분인데 코드는 1분이고, 응답 재사용이 실행 1회 안에서만 살아 매분 다시 조회할 수 있습니다(대기질 하루 500회 한도를 넘길 위험 — 계산값, 측정 아님).",
    "무응답 만료 — 끝난 일정의 선택 요청을 닫는 처리가 기본 감시 경로에 연결돼 있지 않습니다.",
    "중단 알림 — 워커가 변경을 중단하면 고객 알림이 없고, 같은 원인의 실패 건은 다음 감시가 다시 실행하지 않습니다.",
    "고정 항목 — 고객이 고정한 항목은 감시에서 건너뜁니다(결정 D-020 은 고정 항목도 감지 · 안전 알림).",
    "묶음 처리 — 결정은 여행별 묶음 처리 · 소스별 공유 수집, 코드는 항목별 처리 건입니다. 적용 단계에 전체 일정 재검증도 없습니다.",
    "팀 등록 — 이동 · 예약 인계 · 숙박 · 항공 팀이 아직 활성 등록돼 있습니다(팀 결정은 워커 둘 + 공용 이동).",
]


def doc_html(figs):
    parts = [f'<p class="eyebrow">triPilot · Multi-Agent Flow · {VER} · 2026-10-03</p>',
             f"<h1>{escape(TITLE)}</h1>",
             f'<p class="lead">{INTRO}</p>',
             f"<p>{HONEST}</p>"]
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        parts.append(f'<h2>{escape(h)}</h2><p>{body}</p><figure class="fig-wide">{f.svg()}<figcaption>{cap}</figcaption></figure>')
    parts.append("<h2>참여자별 받는 것 · 내보내는 것</h2>")
    parts.append("<table><thead><tr><th>참여자</th><th>종류</th><th>받는 것 (I)</th><th>내보내는 것 (O)</th><th>메모</th></tr></thead><tbody>"
                 + "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in TABLE) + "</tbody></table>")
    parts.append("<h2>이번 검토로 드러난 것 — 결정과 구현이 다른 곳</h2>")
    parts.append('<div class="status"><ul>' + "".join(f"<li>{escape(d)}</li>" for d in DEFECTS) + "</ul></div>")
    parts.append(f"<footer>triPilot · A-COPilot · 그림: diagram-design 스킬(acop 스킨) · 단계 정의: 플로우_단계정의_v3_합의.md "
                 f"(Claude 작성 → 코덱스 1 · 2차 적대 검토 → 합의 → 코덱스 3차 그림 검토 → 반영) · {VER}</footer>")
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>triPilot 멀티에이전트 플로우 {VER}</title>{base.FONT_LINK}<style>{base.CSS} .status ul{{padding-left:1.1rem}}</style></head>'
            f'<body><div class="frame">' + "\n".join(parts) + "</div></body></html>")


def strip(s):
    return re.sub(r"<[^>]+>", "", s)


def md_text(figs):
    md = [f"# {TITLE}", "", strip(INTRO), "", strip(HONEST), ""]
    for name, f in figs:
        h, body, cap = SECTIONS[name]
        md += [f"## {h}", "", strip(body), "", f"![{f.title}]({name}_{VER}.png)", "", f"> {strip(cap)}", ""]
    md += ["## 참여자별 받는 것 · 내보내는 것", "", "| 참여자 | 종류 | 받는 것 (I) | 내보내는 것 (O) | 메모 |", "|---|---|---|---|---|"]
    md += ["| **" + r[0] + "** | " + " | ".join(r[1:]) + " |" for r in TABLE]
    md += ["", "## 이번 검토로 드러난 것 — 결정과 구현이 다른 곳", ""] + [f"- {d}" for d in DEFECTS] + [""]
    return "\n".join(md)


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
        (OUT / f"{n}_{VER}.html").write_text(base.fig_html(n, f), encoding="utf-8")
        (OUT / f"{n}_{VER}.svg").write_text(base.svg_file(f), encoding="utf-8")
    doc = OUT / f"triPilot_멀티에이전트플로우_{VER}.html"
    doc.write_text(doc_html(figs), encoding="utf-8")
    (OUT / f"triPilot_멀티에이전트플로우_{VER}.md").write_text(md_text(figs), encoding="utf-8")
    if "--no-png" not in sys.argv:
        base.export(figs, doc)


if __name__ == "__main__":
    main()
