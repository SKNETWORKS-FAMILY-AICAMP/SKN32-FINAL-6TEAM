# -*- coding: utf-8 -*-
"""AI 시스템 아키텍처 산출물 — 컨테이너도 · 대표 시나리오 순서도 (2026-10-06)

- fig_containers  컨테이너도(C4 2단계) — deploy/docker-compose.yml: tripilot-web · tripilot-api · tripilot-worker · tripilot-db(pgvector pg17) + 프록시(Caddy).
                  워커는 1분마다 run_sweepers(모니터링 3분 문 · 되잡기) · run_outbox_worker(알림) — deploy/worker.sh. 언어 모델은 설정 주소(ACOP_OLLAMA_BASE_URL).
- fig_sequence    대표 시나리오 순서도(런타임 뷰) — 저녁 식당 근처 재난문자. 단계마다 [코드] / [규칙 + 도구] / [언어 모델] 꼬리표.
"""
from dd import Fig


def fig_containers():
    W, H = 1600, 840
    f = Fig("ctr", W, H, "guguroute 컨테이너도 — 무엇이 따로 뜨고 무엇으로 이어지나",
            "고객의 웹 브라우저와 개인 AI 는 HTTPS 프록시를 거쳐 웹 · API 에 닿는다. API 안에 오케스트레이터 · 에이전트 · 이동 판정기 · MCP 서버가 있고, "
            "백그라운드 워커가 1분마다 모니터링 · 되잡기 · 알림 보내기를 돌린다. 둘 다 같은 PostgreSQL 을 쓴다.")
    f.max_nodes, f.max_arrows, f.max_accents = 11, 12, 2
    f.box("B", 40, 56, 280, 88, kind="input", title="고객 웹 브라우저", lines=["휴대폰 · PC"])
    f.box("A", 40, 216, 280, 88, kind="input", title="고객의 개인 AI", lines=["MCP 클라이언트 · HTTPS"])
    f.box("P", 400, 104, 240, 184, kind="external", title="HTTPS 프록시", lines=["Caddy", "주소 하나로 웹 · API 나눔"])
    f.box("WEB", 720, 40, 320, 96, title="tripilot-web", lines=["Next.js 16 · React 19", "확인 화면 · 계획서 · 채팅"])
    f.box("API", 720, 200, 320, 176, kind="focal", title="tripilot-api (FastAPI)",
          lines=["웹 · 여행 API · MCP 서버(/mcp/)", "오케스트레이터 · 에이전트 2", "이동 판정기 · 결정 모델 호출"])
    f.box("WK", 400, 440, 240, 136, title="tripilot-worker", lines=["1분마다 돎", "모니터링(3분 문) · 되잡기", "아웃박스 워커(알림)"])
    f.box("DB", 720, 440, 320, 112, kind="store", title="tripilot-db",
          lines=["PostgreSQL 17 + pgvector", "케이스 · 일정 버전 · 규정 조각"])
    f.box("X", 1120, 40, 440, 112, kind="external", title="외부 API",
          lines=["외부 정보 6종 · 장소(관광공사 · 카카오)", "지하철 · 버스 시간표 · 길찾기 서버"])
    f.box("L", 1120, 216, 440, 96, kind="external", title="언어 모델 서버", lines=["Ollama gemma4:12b · 임베딩", "주소는 설정 · 없으면 OpenAI"])
    f.box("D", 1120, 584, 440, 88, kind="external", title="디스코드", lines=["웹훅 하나 · 알림 + 계획서 링크"])
    f.path("c1", [(320, 100), (360, 100), (360, 160), (400, 160)], "B", "P")
    f.label("c1", 360, 76, "HTTPS")
    f.path("c2", [(320, 260), (360, 260), (360, 232), (400, 232)], "A", "P")
    f.path("c3", [(640, 128), (680, 128), (680, 88), (720, 88)], "P", "WEB")
    f.path("c4", [(640, 264), (720, 264)], "P", "API")
    f.path("c5", [(880, 136), (880, 200)], "WEB", "API")
    f.label("c5", 888, 168, "JSON · 실시간 진행(SSE)", anchor="left")
    f.path("c6", [(880, 376), (880, 440)], "API", "DB")
    f.label("c6", 888, 408, "SQL", anchor="left")
    f.path("c7", [(640, 496), (720, 496)], "WK", "DB")
    f.label("c7", 680, 472, "SQL")
    f.path("c8", [(1040, 232), (1080, 232), (1080, 96), (1120, 96)], "API", "X")
    f.path("c9", [(1040, 280), (1120, 280)], "API", "L")
    f.label("c9", 1080, 256, "HTTP")
    f.path("c10", [(560, 576), (560, 728), (1584, 728), (1584, 120), (1560, 120)], "WK", "X")
    f.label("c10", 1200, 704, "3분마다 외부 정보 6종 조회")
    f.path("c11", [(600, 576), (600, 632), (1120, 632)], "WK", "D")
    f.label("c11", 880, 608, "HTTPS 웹훅")
    f.legend(H - 56, [("input", "사람 · 사람의 AI"), ("focal", "에이전트가 사는 곳"), ("backend", "우리 컨테이너"),
                      ("store", "저장소"), ("external", "바깥 시스템")])
    return f


def fig_sequence():
    cols = ["① 모니터링", "② 오케스트레이터", "③ 요식업 에이전트", "④ 이동 판정기", "⑤ 검증 · 반영", "⑥ 아웃박스 워커", "⑦ 고객"]
    CW = 216
    W, H = 32 + 7 * 224, 1072
    f = Fig("seq", W, H, "대표 시나리오 순서도 — 저녁 식당 근처에 재난문자가 왔을 때",
            "모니터링이 문제를 찾으면 오케스트레이터가 요식업 에이전트에게 태스크를 맡기고, 에이전트는 후보를 다시 점검해 이동 판정기로 앞뒤 이동을 맞춘 초안 3개를 돌려준다. "
            "오케스트레이터가 검증 · 반영하고 아웃박스 워커가 알린다. 단계마다 누가 판단하는지 꼬리표를 달았다.")
    f.max_nodes, f.max_arrows, f.max_accents = 10, 10, 1
    for k, c in enumerate(cols):
        f.zone(16 + k * 224, 16, CW, 976, c, lx=12)
    steps = [
        (0, "1. 18:00 회차 [코드]", ["6종 동시 조회", "재난문자 → 문제 있음"]),
        (1, "2. 라우팅 · 태스크 [코드]", ["dining 문제 → 요식업", "도구 12번 · 90초"]),
        (2, "3. 다시 점검 [규칙 + 도구]", ["일정 · 사건 재점검", "후보 3곳 순서대로"]),
        (3, "4. 앞뒤 이동 [도구]", ["바뀐 식당 앞뒤 이동", "시간표로 다시 판정"]),
        (1, "5. 초안 받기 [코드]", ["초안 최대 3개", "1순위 + 다른 안 2"]),
        (4, "6. 검증 · 반영 [코드]", ["근거 대조 · 반영 확인", "체크리스트 · 밀도"]),
        (5, "7. 알림 [코드 · 모델]", ["디스코드 + 계획서 링크", "외국어면 번역만 모델"]),
        (6, "8. 받기 · 고르기", ["다른 안 고르기", "되돌리기 · 그대로"]),
    ]
    prev = None
    for i, (c, title, lines) in enumerate(steps):
        x, y = 16 + c * 224 + 8, 72 + i * 112
        kind = "worker" if c == 2 else "tool" if c == 3 else "input" if c == 6 else "focal" if c == 1 and i == 1 else "backend"
        f.box(f"S{i}", x, y, 200, 72, kind=kind, title=title, lines=lines)
        if prev is not None:
            px, py = prev
            sx, ex = px + 100, x + 100
            mid = py + 72 + 20
            if sx == ex:
                f.path(f"q{i}", [(sx, py + 72), (ex, y)], f"S{i-1}", f"S{i}")
            else:
                f.path(f"q{i}", [(sx, py + 72), (sx, mid), (ex, mid), (ex, y)], f"S{i-1}", f"S{i}")
        prev = (x, y)
    f.legend(H - 56, [("backend", "코드"), ("focal", "오케스트레이터"), ("worker", "에이전트(규칙 + 도구)"), ("tool", "공용 도구"), ("input", "고객")])
    return f
