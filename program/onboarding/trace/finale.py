# -*- coding: utf-8 -*-
"""마무리 세 장. 상태 생명주기, 계약 문서가 이어지는 모양, 다른 길로 빠지는 경우."""
from draw import (AMBER, BLUE, DIM, FAINT, GREEN, GREY, INK, LINE, PURPLE, RED,
                  arrow, box, canvas, save)


# ══════════════════════════════════════════════ 13. 상태 생명주기
def sheet_lifecycle():
    fig, ax = canvas(7.2)
    ax.text(0.03, 0.950, "작은 구조에서 본 같은 흐름  ·  상태 12개", fontsize=20,
            color=INK, fontweight="bold", va="center")
    ax.text(0.03, 0.906, "앞의 열두 단계는 코드가 지나는 순서지 상태가 아니다. "
            "둘 다 열둘이라 헷갈리지만 겹치지 않는다.",
            fontsize=11, color=DIM, va="center")

    main = [("new", "행을 만든 찰나", 0.030), ("classifying", "분류 중", 0.215),
            ("routing", "팀 찾는 중", 0.400), ("running", "팀이 도는 중", 0.585),
            ("resolved", "종결", 0.795)]
    for name, sub, x in main:
        color = GREEN if name == "resolved" else BLUE
        w = 0.155 if name != "resolved" else 0.175
        box(ax, x, 0.660, w, 0.105, fc="white", ec=color, lw=2.0)
        ax.text(x + w / 2, 0.727, name, ha="center", va="center", fontsize=11.5,
                color=color, fontweight="bold")
        ax.text(x + w / 2, 0.692, sub, ha="center", va="center", fontsize=8.8, color=DIM)
    for a, b in zip(main, main[1:]):
        arrow(ax, (a[2] + 0.155, 0.712), (b[2], 0.712), color=BLUE, lw=1.8)
    ax.text(0.5825, 0.640, "이 환불 건은 이 길로만 갔다", ha="center", va="center",
            fontsize=9.4, color=GREEN)

    waits = [("waiting_input", "고객 답을 기다림", 0.030),
             ("waiting_approval", "사람 결재를 기다림", 0.215),
             ("waiting_external", "외부 콜백을 기다림", 0.400),
             ("resuming", "다시 이어서 실행", 0.585)]
    for name, sub, x in waits:
        box(ax, x, 0.420, 0.155, 0.105, fc="#fffaf0", ec=AMBER, lw=1.6)
        ax.text(x + 0.0775, 0.487, name, ha="center", va="center", fontsize=10.5,
                color=AMBER, fontweight="bold")
        ax.text(x + 0.0775, 0.452, sub, ha="center", va="center", fontsize=8.6, color=DIM)
    arrow(ax, (0.6625, 0.660), (0.6625, 0.525), color=AMBER, lw=1.6)
    arrow(ax, (0.740, 0.472), (0.795, 0.660), color=AMBER, lw=1.6)
    ax.text(0.800, 0.487, "멈췄다가\n조건이 갖춰지면\n다시 이어서 돈다",
            ha="left", va="center", fontsize=9.2, color=AMBER, linespacing=1.7)

    ends = [("escalated", "사람에게 넘김", 0.030, RED),
            ("failed", "실패로 끝남", 0.215, RED),
            ("cancelled", "취소됨", 0.400, GREY)]
    for name, sub, x, color in ends:
        box(ax, x, 0.230, 0.155, 0.095, fc="white", ec=color, lw=1.4)
        ax.text(x + 0.0775, 0.291, name, ha="center", va="center", fontsize=10.5,
                color=color, fontweight="bold")
        ax.text(x + 0.0775, 0.258, sub, ha="center", va="center", fontsize=8.6, color=DIM)

    ax.text(0.585, 0.300, "이 세 상태와 대기 세 상태는\n이 환불 건에서 안 나왔다.\n"
            "나오는 경우는 다음 장에 있다.",
            ha="left", va="center", fontsize=9.6, color=DIM, linespacing=1.8)

    box(ax, 0.03, 0.045, 0.94, 0.130, fc="#f7f8fb", ec=LINE)
    ax.text(0.048, 0.140, "왜 헷갈리나", fontsize=10, color=INK, fontweight="bold",
            va="center")
    ax.text(0.048, 0.104, "단계도 열둘이고 상태도 열둘이다. 그런데 1번 신원 확인과 "
            "2번 중복 확인은 Case 가 생기기 전이라 상태가 아예 없고,",
            fontsize=9.8, color=DIM, va="center")
    ax.text(0.048, 0.072, "반대로 waiting_external 과 cancelled 는 코드 흐름 열두 단계에 "
            "안 나온다. 한쪽을 다른 쪽으로 번역하려 하면 안 맞는다.",
            fontsize=9.8, color=DIM, va="center")
    save(fig, "13_상태생명주기.png")


# ══════════════════════════════════════════════ 14. 계약 문서가 이어지는 모양
def sheet_contracts():
    fig, ax = canvas(7.4)
    ax.text(0.03, 0.952, "전달 문서가 바뀌어 가는 모양", fontsize=20, color=INK,
            fontweight="bold", va="center")
    ax.text(0.03, 0.910, "같은 문의 하나가 다섯 번 모습을 바꾼다. 각 계약은 "
            "extra 필드를 금지해서 조용히 늘어나지 않는다.",
            fontsize=11, color=DIM, va="center")

    docs = [
        ("HTTP 요청", RED, 1, 0.030, [
            "request_id", "customer_id", "message", "channel"]),
        ("Principal", RED, 1, 0.222, [
            "tenant_id", "scopes", "key_id", "", "여기서 tenant 가 붙는다"]),
        ("ContextPack", PURPLE, 7, 0.414, [
            "sections", "evidence[]", "degraded", "omissions[]", "", "근거가 붙는다"]),
        ("TeamTask", GREEN, 8, 0.606, [
            "case_id", "capability", "context_pack", "run_id", "", "팀에게 넘어간다"]),
        ("TeamResult", GREEN, 8, 0.798, [
            "next_action", "answer", "evidence[]", "proposals[]", "", "판단이 붙는다"]),
    ]
    for name, color, at_step, x, fields in docs:
        box(ax, x, 0.470, 0.172, 0.330, fc="white", ec=color, lw=1.8)
        ax.text(x + 0.086, 0.762, name, ha="center", va="center", fontsize=12,
                color=color, fontweight="bold")
        ax.text(x + 0.086, 0.729, "%d번 단계" % at_step, ha="center", va="center",
                fontsize=8.4, color=FAINT)
        for i, f in enumerate(fields):
            ax.text(x + 0.014, 0.690 - i * 0.034, f, ha="left", va="center",
                    fontsize=9.2, color=DIM if f.startswith("근거") or f.startswith("여기")
                    or f.startswith("팀에") or f.startswith("판단") else INK)
    for a, b in zip(docs, docs[1:]):
        arrow(ax, (a[3] + 0.172, 0.635), (b[3], 0.635), color=GREY, lw=1.8)

    box(ax, 0.030, 0.245, 0.940, 0.185, fc="#fbfcfe", ec=BLUE)
    ax.text(0.048, 0.398, "그리고 이것들이 표로 내려앉는다", fontsize=11.5,
            color=BLUE, fontweight="bold", va="center")
    tables = [("customer_cases", "지금 상태 1행. 이벤트를 적용한 결과", 0.048),
              ("case_events", "무슨 일이 있었나 4행. 추가만 한다", 0.290),
              ("action_requests", "멱등성 기록 1행", 0.532),
              ("agent_runs · llm_calls", "실행과 프롬프트 기록", 0.740)]
    for name, sub, x in tables:
        ax.text(x, 0.348, name, fontsize=10, color=INK, fontweight="bold", va="center")
        ax.text(x, 0.316, sub, fontsize=9, color=DIM, va="center")
    ax.text(0.048, 0.272, "customer_cases 는 case_events 를 순서대로 적용한 결과일 뿐이다. "
            "그래서 이벤트만 있으면 언제든 다시 만들 수 있다.",
            fontsize=9.6, color=DIM, va="center")

    box(ax, 0.030, 0.045, 0.940, 0.165, fc="#fffdf6", ec=AMBER)
    ax.text(0.048, 0.176, "계약이 왜 중요한가", fontsize=10.5, color=INK,
            fontweight="bold", va="center")
    for i, line in enumerate([
            "Core 는 Team 안을 들여다보지 않는다. TeamManifest 와 execute() 두 가지만 쓴다. "
            "그래서 팀을 늘려도 Core 코드가 안 바뀐다.",
            "모든 계약은 정의되지 않은 필드를 거부한다. 오타로 만든 필드가 조용히 흘러 다니지 않는다.",
            "이 경계는 문서가 아니라 테스트가 지킨다. Core 가 Team 을 import 하면 "
            "tests/contract 가 붉어진다."]):
        ax.text(0.048, 0.140 - i * 0.032, line, fontsize=9.6, color=DIM, va="center")
    save(fig, "14_계약문서.png")


# ══════════════════════════════════════════════ 15. 다른 길로 빠지는 경우
def sheet_branches():
    fig, ax = canvas(7.0)
    ax.text(0.03, 0.950, "다른 길로 빠지는 경우", fontsize=20, color=INK,
            fontweight="bold", va="center")
    ax.text(0.03, 0.906, "앞의 열두 장은 전부 통과한 길이다. 실제로는 아래에서 갈린다. "
            "어느 쪽이든 조용히 넘어가지 않는다.",
            fontsize=11, color=DIM, va="center")

    rows = [
        (4, "분류가 목록 밖 라벨을 냈다", "classification_failed 를 남기고 escalated",
         "값을 비워 둔다. 추정으로 채우면 그 오류가 답변까지 간다", RED),
        (5, "받는 팀이 둘이거나 없다", "routing_failed 를 남기고 escalated",
         "조용히 아무 팀이나 고르지 않는다", RED),
        (7, "정책 검색이 실패했다", "degraded=true 와 omissions 를 붙여서 계속",
         "빈 결과를 조용히 쓰지 않는다. 팀이 그 신호를 보고 판단한다", AMBER),
        (8, "근거가 잘렸다 (degraded)", "degraded_context 로 escalated",
         "근거가 모자란 채로 확답을 만들지 않는다", RED),
        (8, "반품 사유나 수량을 모른다", "waiting_input 으로 멈춤",
         "고객에게 물어보고 답이 오면 이어서 돈다", AMBER),
        (8, "이미 진행 중인 반품이 있다", "return_already_in_history 로 escalated",
         "중복 처리를 사람이 판단하게 넘긴다", RED),
        (8, "반품 기간이 지났다 (기본 7일)", "return_period_expired 로 escalated",
         "예외를 코드가 정하지 않는다", RED),
        (0, "돈이 나가는 제안이 나왔다", "waiting_approval 로 멈춤",
         "고위험 Action 은 사람이 승인해야 실행된다", AMBER),
        (0, "결제사 응답이 안 온다", "unknown 으로 남기고 자동 재실행 안 함",
         "돈이 나갔는지 모르는 상태를 모른다 고 적는다", GREY),
    ]
    y = 0.830
    ax.text(0.048, y + 0.030, "단계", fontsize=8.6, color=FAINT, va="center")
    ax.text(0.105, y + 0.030, "무슨 일이 생기면", fontsize=8.6, color=FAINT, va="center")
    ax.text(0.395, y + 0.030, "어떻게 되나", fontsize=8.6, color=FAINT, va="center")
    ax.text(0.660, y + 0.030, "왜 그렇게 하나", fontsize=8.6, color=FAINT, va="center")
    for at, when, then, why, color in rows:
        box(ax, 0.030, y - 0.028, 0.940, 0.001, fc=LINE, ec="none", r=0)
        ax.text(0.048, y, ("%d" % at) if at else "공통", fontsize=9.4,
                color=color, fontweight="bold", va="center")
        ax.text(0.105, y, when, fontsize=9.6, color=INK, va="center")
        ax.text(0.395, y, then, fontsize=9.6, color=color, va="center")
        ax.text(0.660, y, why, fontsize=9.2, color=DIM, va="center")
        y -= 0.070

    box(ax, 0.030, 0.045, 0.940, 0.095, fc="#fffdf6", ec=AMBER)
    ax.text(0.5, 0.092, "공통 원칙 하나다. 모르면 비워 두고 신호를 남긴다. "
            "채워 넣거나 조용히 넘어가면 그 오류가 고객 답변까지 그대로 간다.",
            ha="center", va="center", fontsize=10.6, color=INK)
    save(fig, "15_분기.png")
