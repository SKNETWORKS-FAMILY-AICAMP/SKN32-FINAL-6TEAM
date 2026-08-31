# -*- coding: utf-8 -*-
"""이 흐름이 실제로 만드는 것의 목록. 두 장이다.

★제일 중요한 사실부터 적는다. **이 흐름은 파일을 만들지 않는다.**
  그림에 JSON 조각을 보여 줬더니 "그럼 이게 무슨 파일로 저장되나" 를 묻게 되는데,
  답은 "파일이 아니라 DB 행" 이다. HTTP 로 오가는 JSON 은 몸통(body)이지 파일이 아니다.
  이걸 안 적으면 어딘가에 send.json 같은 것이 생긴다고 오해한다.

★컬럼 이름은 `app/infrastructure/db/migrations/001_schema.sql` 에서 그대로 옮겼다.
  파일 이름도 실제로 있는 것만 적었다. 지어낸 이름은 없다.
"""
from draw import AMBER, BLUE, DIM, FAINT, GREEN, GREY, INK, LINE, PURPLE, RED, box, canvas, save


#: 한 줄 높이. ★0.030 으로 잡았더니 좌열 두 상자가 캔버스 아래로 넘쳤다.
#   칼럼이 열둘인 표가 있어서 상자 하나가 화면의 절반에 가깝다.
ROW = 0.0235


def _table(ax, x, y, w, title, sub, color, cols, note=""):
    h = 0.050 + ROW * len(cols) + (ROW if note else 0.010)
    box(ax, x, y - h, w, h, fc="white", ec=color, lw=1.5)
    ax.text(x + 0.014, y - 0.022, title, fontsize=10.6, color=color,
            fontweight="bold", va="center")
    ax.text(x + w - 0.014, y - 0.022, sub, fontsize=8.4, color=DIM,
            va="center", ha="right")
    for i, c in enumerate(cols):
        ax.text(x + 0.020, y - 0.046 - i * ROW, c, fontsize=8.4, color=INK, va="center")
    if note:
        ax.text(x + 0.020, y - 0.046 - len(cols) * ROW, note, fontsize=8.3,
                color=color, va="center")
    return y - h


# ══════════════════════════════════════════ 16. 실제로 남는 것
def sheet_artifacts():
    fig, ax = canvas(8.4)
    ax.text(0.03, 0.962, "이 흐름이 실제로 만드는 것", fontsize=20, color=INK,
            fontweight="bold", va="center")
    ax.text(0.03, 0.924, "앞 장들이 보여 준 JSON 은 HTTP 로 오가는 몸통이거나 메모리 위의 객체다. "
            "디스크에 파일로 떨어지지 않는다.", fontsize=11, color=DIM, va="center")

    box(ax, 0.03, 0.840, 0.940, 0.062, fc="#fffdf6", ec=AMBER)
    ax.text(0.048, 0.871, "이 흐름에서 새로 생기는 파일은 없다. 전부 데이터베이스 행이다. "
            "파일이 생기는 곳은 따로 있고 다음 장에 적었다.",
            fontsize=11, color=INK, va="center", fontweight="bold")

    y = 0.800
    y = _table(ax, 0.03, y, 0.455, "customer_cases", "1행 · 지금 상태", BLUE, [
        "case_id       uuid",
        "tenant_id     text",
        "customer_id   uuid",
        "status        case_status   resolved",
        "subject       text          고객 메시지",
        "state_json    jsonb         answer 가 여기 들어간다",
        "intent        text          return",
        "issue_code    text          return_fee_or_period",
        "sentiment     text          negative",
        "owner_team_id text          return_refund",
        "version       int           4",
        "created_at / updated_at     timestamptz",
    ], "이 표는 case_events 를 순서대로 적용한 결과다")

    y = _table(ax, 0.03, y - 0.026, 0.455, "case_events", "4행 · 추가만 한다", BLUE, [
        "event_id           uuid",
        "case_id            uuid",
        "aggregate_version  int    1 2 3 4",
        "event_type         text   created",
        "                          classified",
        "                          routed",
        "                          completed",
        "payload_json       jsonb",
        "actor_type         text   api",
        "actor_id           text   키 식별자",
        "UNIQUE(case_id, aggregate_version)",
    ], "UPDATE 도 DELETE 도 하지 않는다")

    y2 = 0.800
    y2 = _table(ax, 0.515, y2, 0.455, "action_requests", "1행 · 멱등성 기록", RED, [
        "action_id        uuid",
        "case_id          uuid",
        "action_type      text   case.create",
        "arguments_json   jsonb",
        "idempotency_key  text   sha256 문자열",
        "status           action_status",
        "provider_ref     text",
        "UNIQUE(tenant_id, idempotency_key)",
    ], "이 UNIQUE 하나가 중복 처리를 막는다")

    y2 = _table(ax, 0.515, y2 - 0.026, 0.455, "agent_runs", "1행 · 실행 기록", GREEN, [
        "run_id          uuid",
        "case_id         uuid",
        "graph_revision  text",
        "status          text",
        "attempt         int",
        "started_at / finished_at   timestamptz",
    ])

    y2 = _table(ax, 0.515, y2 - 0.026, 0.455, "llm_calls", "분류에 쓴 호출", GREEN, [
        "call_id        uuid",
        "run_id         uuid",
        "prompt_id      uuid   prompts 표를 가리킨다",
        "provider / model      text",
        "input_tokens / output_tokens   int",
        "latency_ms / cost_microusd",
        "response_json  jsonb",
    ], "어느 프롬프트가 만든 답인지 되짚을 수 있다")

    ax.text(0.03, 0.028, "team_tasks 와 outbox 와 action_approvals 는 이 케이스에서 안 쓴다. "
            "승인이 필요한 제안이 없었고 발행할 메시지도 없었기 때문이다.",
            fontsize=10, color=DIM, va="center")
    save(fig, "16_실제로_남는_것.png")


# ══════════════════════════════════════════ 17. 진짜 파일 이름
def sheet_filenames():
    fig, ax = canvas(8.6)
    ax.text(0.03, 0.962, "그럼 파일은 어디서 생기나", fontsize=20, color=INK,
            fontweight="bold", va="center")
    ax.text(0.03, 0.926, "실제로 있는 이름만 적었다. 이 케이스가 읽는 것과, 다른 경로에서 "
            "쓰는 것을 나눴다.", fontsize=11, color=DIM, va="center")

    groups = [
        ("이 케이스가 읽는 파일", BLUE, 0.880, [
            ("config/project.yaml", "무슨 모듈과 Team 을 쓸지의 선언. 기동할 때 읽는다"),
            ("config/guardrails.yaml", "12,000 토큰 예산과 scope 10종. 수치의 단일 출처"),
            ("prompts/response/generate.v2.md", "응답 생성 프롬프트. DB prompts 표에 등록해 쓴다"),
            ("prompts/response/review_tone.v1.md", "톤 검토 프롬프트. 9번 단계가 꺼져 있어 이번엔 안 썼다"),
        ]),
        ("Composer 가 설정을 바꿀 때 쓰는 파일", PURPLE, 0.618, [
            ("config/project.yaml", "최종 기록 자리. 통째로 다시 쓴다"),
            (".project.validate.<uuid>.yaml", "검증용 임시 파일. 검사 끝나면 지운다"),
            (".project.write.<uuid>.yaml", "쓰기용 임시 파일. 원자적 교체에 쓴다"),
            ("composer_events.jsonl", "누가 언제 무엇을 바꿨는지 한 줄에 하나"),
        ]),
        ("평가가 만드는 파일", GREEN, 0.356, [
            ("eval/datasets/golden.jsonl", "문제집 60건. 보면서 고쳐도 된다"),
            ("eval/datasets/holdout.jsonl", "문제집 20건. 보고 고치면 안 된다"),
            ("eval/reports/2026-08-31_stage3_v6_review_comparison.jsonl",
             "실행 결과. 날짜와 조건이 이름에 박힌다"),
            ("docs/evidence/DoD-21_Graph_관계질의.md", "통과했다고 주장하는 근거"),
        ]),
    ]
    for head, color, y0, rows in groups:
        h = 0.052 + 0.048 * len(rows)
        box(ax, 0.03, y0 - h, 0.940, h, fc="white", ec=color, lw=1.5)
        ax.text(0.048, y0 - 0.026, head, fontsize=12, color=color,
                fontweight="bold", va="center")
        for i, (name, why) in enumerate(rows):
            yy = y0 - 0.062 - i * 0.048
            ax.text(0.055, yy, name, fontsize=10.2, color=INK, va="center")
            ax.text(0.500, yy, why, fontsize=9.4, color=DIM, va="center")

    box(ax, 0.03, 0.040, 0.940, 0.088, fc="#fffdf6", ec=AMBER)
    ax.text(0.5, 0.084, "고객 문의 한 건을 처리하는 동안 새로 생기는 파일은 하나도 없다. "
            "파일은 설정을 바꿀 때와 평가를 돌릴 때 생긴다.",
            ha="center", va="center", fontsize=10.6, color=INK)
    save(fig, "17_파일_이름.png")
