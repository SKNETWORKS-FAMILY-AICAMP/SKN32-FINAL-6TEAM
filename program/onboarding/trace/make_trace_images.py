# -*- coding: utf-8 -*-
"""취소·환불 한 건이 지나는 길을 그림 열여섯 장으로 만든다.

    python program/onboarding/trace/make_trace_images.py

그림 그리는 도구는 `draw.py` 에 있고 여기는 내용만 있다.

근거는 셋이다. 지어낸 값은 없다.
  - 흐름과 코드 경로: `program/onboarding/trace_refund_case.html`
  - 구조 분류(컴포넌트·모듈·인스턴스·Port): `final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md`
  - 담당: `program/plan/A-COP_스프린트_에픽_설계.md`

★큰 구조와 작은 구조를 한 장 안에 같이 둔다. 왼쪽 세로 띠가 큰 구조(이 단계가
  컴포넌트인지 모듈인지, 어느 런타임인지, 누가 맡는지, 무슨 계약인지)이고,
  가운데가 작은 구조(들어온 문서와 나간 문서의 실제 모양)다.
"""
import sys

from draw import (AMBER, BLUE, DIM, FAINT, GREEN, GREY, INK, LINE, OUT, PURPLE,
                  RED, STEPS, arrow, box, canvas, save)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ══════════════════════════════════════════════ 00. 전체 지도
def sheet_map():
    fig, ax = canvas(7.0)
    ax.text(0.03, 0.945, "취소·환불 한 건이 지나는 길", fontsize=21, color=INK,
            fontweight="bold", va="center")
    ax.text(0.03, 0.900, '고객이 "어제 주문한 거 취소하고 환불받고 싶어요" 를 보낸 순간부터 '
            "답이 돌아갈 때까지의 열두 단계", fontsize=11, color=DIM, va="center")

    lanes = [("코어 2   진입과 실행", RED, [1, 2, 11], 0.740),
             ("코어 1   Case 조정", BLUE, [3, 5, 6, 10], 0.590),
             ("모델     Agent Team", GREEN, [4, 8, 9], 0.440),
             ("근거 조합", PURPLE, [7], 0.290),
             ("기록", GREY, [12], 0.140)]
    n = len(STEPS)
    left, gap = 0.215, 0.005
    w = (1 - left - 0.03 - gap * (n - 1)) / n
    for label, color, owns, y in lanes:
        box(ax, 0.03, y, 0.170, 0.100, fc="white", ec=color)
        ax.text(0.115, y + 0.050, label, ha="center", va="center", fontsize=9.6,
                color=color, fontweight="bold")
        for i, (name, _c) in enumerate(STEPS):
            x = left + i * (w + gap)
            if i + 1 in owns:
                box(ax, x, y, w, 0.100, fc=color, ec="none")
                ax.text(x + w / 2, y + 0.068, "%d" % (i + 1), ha="center", va="center",
                        fontsize=11, color="white", fontweight="bold")
                ax.text(x + w / 2, y + 0.030, name, ha="center", va="center",
                        fontsize=8.2, color="white")
            else:
                box(ax, x, y + 0.046, w, 0.008, fc="#eef0f5", ec="none", r=0.004)
    ax.text(0.5, 0.060, "가로가 시간이다. 왼쪽 이름표가 그 단계를 누가 맡는지다. "
            "같은 담당이 흐름 중간에 다시 나온다.",
            ha="center", va="center", fontsize=10.2, color=DIM)
    save(fig, "00_전체지도.png")


# ══════════════════════════════════════════════ 01. 구조 좌표 전체
def sheet_structure():
    fig, ax = canvas(7.6)
    ax.text(0.03, 0.955, "큰 구조에서 이 케이스가 건드리는 것", fontsize=20,
            color=INK, fontweight="bold", va="center")
    ax.text(0.03, 0.912, "네 가지를 다르게 부른다. 무엇을 뺄 수 있고 무엇을 못 빼는지가 "
            "여기서 갈린다.", fontsize=11, color=DIM, va="center")

    groups = [
        ("컴포넌트  9", "빼면 시스템이 아니다. 선택 불가", BLUE, 0.700, [
            ("Case lifecycle · transition_case()", True, "3 10"),
            ("계약 모델 (TeamTask · TeamResult · ContextPack)", True, "전 단계"),
            ("Team Registry", True, "5 6"),
            ("Context Broker", True, "7"),
            ("DB repository · session", True, "3 8 12"),
            ("Outbox 원자성", False, ""),
            ("Case service (run · resume)", True, "8"),
            ("Controller", True, "5~10"),
            ("설정 · 가드레일", True, "7"),
        ]),
        ("모듈  6", "켜고 끌 수 있다. 끄면 그 표면도 사라진다", GREEN, 0.395, [
            ("vector_rag", True, "7"),
            ("voc  (분류 · 일일 배치)", True, "4"),
            ("mcp", False, "이 건은 REST 로 들어왔다"),
            ("graph_store", False, ""),
            ("a2a_executor", False, "지금 꺼져 있다"),
            ("ops_ui", False, "운영자 화면"),
        ]),
    ]
    for head, sub, color, y0, items in groups:
        box(ax, 0.03, y0 - 0.030 * len(items) - 0.045, 0.44,
            0.030 * len(items) + 0.100, fc="white", ec=color)
        ax.text(0.048, y0 + 0.030, head, fontsize=12.5, color=color,
                fontweight="bold", va="center")
        ax.text(0.048, y0 - 0.002, sub, fontsize=9.2, color=DIM, va="center")
        for i, (name, used, note) in enumerate(items):
            yy = y0 - 0.040 - i * 0.030
            ax.text(0.055, yy, "●" if used else "○", fontsize=8,
                    color=color if used else "#c9cfdb", va="center")
            ax.text(0.075, yy, name, fontsize=9.2,
                    color=INK if used else FAINT, va="center")
            if note:
                ax.text(0.455, yy, note, fontsize=8.6, color=color if used else FAINT,
                        va="center", ha="right")

    right = [
        ("인스턴스  Agent Team 6", "개수가 늘고 주는 것은 이것뿐이다", GREEN, 0.700, [
            ("return_refund", True, "8  이 건을 맡는다"),
            ("response_generation_review", False, "9  지금 꺼짐"),
            ("voc_store_manager", False, ""),
            ("procurement_order_payment", False, ""),
            ("fulfillment_logistics", False, ""),
            ("catalog_verification", False, ""),
        ]),
        ("Port  6", "구현을 갈아 끼우는 자리", PURPLE, 0.435, [
            ("TeamExecutorPort → LocalTeamExecutor", True, "8"),
            ("정책 검색 함수 → search_policy", True, "7"),
            ("분류기 → feedback.classify", True, "4"),
            ("LLM → OpenAITeamLLM", True, "4 9"),
            ("MessageBrokerPort → Outbox", False, ""),
            ("GraphStorePort → SqlGraphAdapter", False, ""),
        ]),
    ]
    for head, sub, color, y0, items in right:
        box(ax, 0.515, y0 - 0.030 * len(items) - 0.045, 0.455,
            0.030 * len(items) + 0.100, fc="white", ec=color)
        ax.text(0.533, y0 + 0.030, head, fontsize=12.5, color=color,
                fontweight="bold", va="center")
        ax.text(0.533, y0 - 0.002, sub, fontsize=9.2, color=DIM, va="center")
        for i, (name, used, note) in enumerate(items):
            yy = y0 - 0.040 - i * 0.030
            ax.text(0.540, yy, "●" if used else "○", fontsize=8,
                    color=color if used else "#c9cfdb", va="center")
            ax.text(0.560, yy, name, fontsize=9.2,
                    color=INK if used else FAINT, va="center")
            if note:
                ax.text(0.955, yy, note, fontsize=8.6, color=color if used else FAINT,
                        va="center", ha="right")

    box(ax, 0.03, 0.045, 0.94, 0.085, fc="#fffdf6", ec=AMBER)
    ax.text(0.5, 0.088, "채운 동그라미가 이 환불 한 건이 실제로 지나는 것이다. "
            "오른쪽 숫자는 몇 번 단계에서 쓰이는지다.",
            ha="center", va="center", fontsize=10.4, color=INK)
    save(fig, "01_구조좌표.png")


if __name__ == "__main__":
    from finale import sheet_branches, sheet_contracts, sheet_lifecycle
    from steps import build_steps

    print("그림을 만든다:")
    sheet_map()
    sheet_structure()
    build_steps()
    sheet_lifecycle()
    sheet_contracts()
    sheet_branches()
    import os
    n = len([f for f in os.listdir(OUT) if f.endswith(".png")]) if "OUT" in dir() else 0
    print("완료:", os.path.abspath("images"))
