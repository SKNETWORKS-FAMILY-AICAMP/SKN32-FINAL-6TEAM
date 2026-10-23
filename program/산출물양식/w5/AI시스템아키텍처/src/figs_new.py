# -*- coding: utf-8 -*-
"""AI 시스템 아키텍처 산출물 — 새로 그리는 그림 셋 (2026-10-06)

- fig_context  시스템 전체 관계도(C4 의 시스템 컨텍스트 수준): 누가 쓰고, 무엇과 연결되나
- fig_states   케이스 상태 전이도: 상태 12종과 전이(app/core/case_lifecycle/events.py TRANSITIONS)
- fig_failures 장애 대응 지도: 양식 4절의 네 칸 — 실패 상황 → 막는 장치 → 결과

사실 근거(final_project_cs, 2026-10-06):
- 외부 정보 6종: ports/data_sources/disruptions.py(forecast · weather_warning · disaster_msg · traffic_control · air_quality · earthquake 동시 조회)
  · weather_chain.py(Open-Meteo → 기상청 대체) · traffic_chain.py(ITS + UTIC 합침) · air_quality.py(에어코리아) · kma_earthquake.py · kma_warning.py · disaster_msg.py
- 장소: tour_api.py(관광공사) · kakao_local.py · google_places.py · 이동 판정기(instances/mobility, 시간표 + GraphHopper)
- 언어 모델: app/core/settings.py ollama_model gemma4:12b · 임베딩 ollama_embedding_model bge-m3 / guardrails embedding_model text-embedding-3-small(설정으로 선택)
- 규정 검색 문턱: config/guardrails.yaml min_policy_score 0.55 · 도구 12번 · 마감 90초 · 재시도 3번(5분) · 알림 3번(1분)
"""
from dd import Fig

I, T, O = "입력", "도구", "출력"


def fig_context():
    W, H = 1600, 704
    f = Fig("ctx", W, H, "guguroute 시스템 전체 관계도 — 누가 쓰고 무엇과 연결되나",
            "고객은 웹으로, 고객의 개인 AI 는 MCP 로 guguroute 에 붙는다. guguroute 은 외부 정보 6종 · 장소 정보 · 언어 모델을 읽어 일정을 검증하고 지키며, 바뀐 것은 디스코드로 알린다.")
    f.max_nodes, f.max_arrows, f.max_accents = 9, 12, 2
    f.box("U1", 40, 120, 320, 104, kind="input", title="고객 (여행자)",
          io=[(I, "계획 올리기 · 채팅 · 고르기"), (O, "확인 화면 · 계획서 링크")])
    f.box("U2", 40, 392, 320, 104, kind="input", title="고객의 개인 AI",
          io=[(I, "MCP 도구 14 호출(본인 여행만)"), (O, "일정 · 위험 점검 · 이동 판정")])
    f.box("S", 560, 192, 480, 248, kind="focal", title="guguroute — cs 프로젝트 서버",
          io=[("입구", "웹 · API(FastAPI) · MCP"), ("두뇌", "오케스트레이터(코드) · 에이전트 2"),
              ("도구", "읽기 도구 · 이동 판정기(공용)"), ("감시", "일정 위험 모니터링(3분 주기)"),
              ("저장", "PostgreSQL + pgvector(케이스 · 일정 · 규정)"), ("알림", "아웃박스 워커(1분 간격 3번)")])
    f.box("X1", 1240, 40, 320, 112, kind="external", title="외부 정보 6종",
          io=[("", "Open-Meteo → 기상청 · 기상 특보"), ("", "재난문자 · ITS + UTIC 교통"), ("", "에어코리아 대기질 · 기상청 지진")])
    f.box("X2", 1240, 200, 320, 96, kind="external", title="장소 · 이동 정보",
          io=[("", "관광공사 TourAPI · 카카오 로컬"), ("", "지하철 · 버스 시간표 · 길찾기")])
    f.box("X3", 1240, 344, 320, 96, kind="external", title="언어 모델 (로컬)",
          io=[("", "gemma4:12b(Ollama) · 없으면 OpenAI"), ("", "임베딩(bge-m3 등 · 설정)")])
    f.box("X4", 1240, 488, 320, 96, kind="external", title="디스코드",
          io=[("", "알림 · 계획서 링크 받기"), ("", "웹훅 하나")])
    f.path("a1", [(360, 172), (560, 172), (560, 232)], "U1", "S") if False else None
    f.path("a1", [(360, 172), (460, 172), (460, 248), (560, 248)], "U1", "S")
    f.label("a1", 460, 148, "웹 · 휴대폰")
    f.path("a2", [(360, 444), (460, 444), (460, 384), (560, 384)], "U2", "S")
    f.label("a2", 410, 452, "MCP")
    f.path("b1", [(1040, 232), (1140, 232), (1140, 96), (1240, 96)], "S", "X1")
    f.label("b1", 1140, 72, "3분마다 조회")
    f.path("b2", [(1040, 268), (1240, 268)], "S", "X2")
    f.label("b2", 1140, 244, "장소 · 경로")
    f.path("b3", [(1040, 392), (1240, 392)], "S", "X3")
    f.label("b3", 1140, 368, "보기 고르기 · 번역")
    f.path("b4", [(1040, 420), (1140, 420), (1140, 536), (1240, 536)], "S", "X4")
    f.label("b4", 1190, 544, "알림 보냄")
    f.legend(H - 56, [("input", "사람 · 사람의 AI"), ("focal", "우리 시스템"), ("external", "바깥 시스템")])
    return f


def fig_states():
    W, H = 1600, 712
    f = Fig("states", W, H, "케이스 상태 전이도 — 상태 12종",
            "케이스는 접수 → 분류 → 라우팅 → 실행을 거쳐 해결되거나, 입력 · 승인 · 외부 응답을 기다렸다가 재개된다. 분류 · 라우팅 실패, 규칙 위반, 대기 만료, 재개 실패는 모두 에스컬레이션으로 간다.")
    f.max_nodes, f.max_arrows, f.max_accents = 14, 26, 2
    y1 = 80
    for name, x, title, sub in [("N", 40, "new", "접수"), ("C", 280, "classifying", "분류 중"), ("R", 520, "routing", "담당 고르기"),
                                ("U", 760, "running", "에이전트 실행"), ("D", 1240, "resolved", "해결")]:
        f.box(name, x, y1, 200, 64, kind="focal" if name == "U" else "backend", title=title, lines=[sub])
    f.path("t1", [(240, 112), (280, 112)], "N", "C")
    f.path("t2", [(480, 112), (520, 112)], "C", "R")
    f.path("t3", [(720, 112), (760, 112)], "R", "U")
    f.path("t4", [(960, 112), (1240, 112)], "U", "D")
    f.label("t4", 1100, 88, "completed")
    # 기다림 셋 → 재개
    for name, x, title, sub in [("WI", 600, "waiting_input", "입력 기다림"), ("WA", 840, "waiting_approval", "승인 기다림"),
                                ("WE", 1080, "waiting_external", "외부 응답 기다림")]:
        f.box(name, x, 264, 200, 64, kind="input", title=title, lines=[sub])
    f.box("RS", 1320, 264, 200, 64, title="resuming", lines=["재개"])
    f.path("w1", [(780, 144), (780, 200), (700, 200), (700, 264)], "U", "WI")
    f.path("w2", [(900, 144), (900, 264)], "U", "WA")
    f.path("w3", [(940, 144), (940, 184), (1180, 184), (1180, 264)], "U", "WE")
    f.label("w1", 692, 232, "입력 부족", anchor="right")
    f.label("w2", 908, 232, "승인 필요", anchor="left")
    f.label("w3", 1188, 216, "외부 대기", anchor="left")
    f.path("r1", [(1280, 296), (1320, 296)], "WE", "RS")
    f.path("r2", [(1520, 296), (1552, 296), (1552, 48), (880, 48), (880, 80)], "RS", "U", color="accent")
    f.label("r2", 1216, 24, "resumed → 다시 실행")
    f.label("r1", 1300, 352, "valid_input · approved · callback → 재개", anchor="center") if False else None
    # 끝 상태들
    f.box("F", 760, 424, 200, 64, kind="stop", title="failed", lines=["재시도 소진"])
    f.box("E", 40, 552, 1480, 64, kind="stop", title="escalated — 오류 리포트(사람 대기 없음)",
          lines=["분류 실패 · 라우팅 실패 · 규칙 위반 · 대기 만료 · 거부 · 재개 실패 · failed"])
    f.box("X", 40, 424, 200, 64, kind="optional", title="cancelled", lines=["고객 취소"])
    f.path("x1", [(140, 144), (140, 424)], "N", "X")
    f.path("e1", [(380, 144), (380, 552)], "C", "E")
    f.label("e1", 388, 352, "분류 실패", anchor="left")
    f.path("e2", [(620, 144), (620, 200), (560, 200), (560, 552)], "R", "E")
    f.label("e2", 552, 400, "담당 없음", anchor="right")
    f.path("f1", [(780, 144), (780, 184), (740, 184), (740, 456), (760, 456)], "U", "F") if False else None
    f.path("e3", [(700, 328), (700, 552)], "WI", "E")
    f.path("e4", [(940, 328), (940, 376), (1000, 376), (1000, 552)], "WA", "E")
    f.label("e4", 1008, 400, "만료 · 거부", anchor="left")
    f.path("e5", [(1180, 328), (1180, 552)], "WE", "E")
    f.label("e5", 1188, 440, "만료", anchor="left")
    f.path("e6", [(1420, 328), (1420, 552)], "RS", "E")
    f.label("e6", 1428, 440, "재개 실패", anchor="left")
    f.path("e7", [(860, 488), (860, 552)], "F", "E")
    f.path("uf", [(820, 144), (820, 424)], "U", "F")
    f.label("uf", 812, 392, "재시도 소진", anchor="right")
    f.path("uf", [(820, 144), (820, 168), (660, 168), (660, 400), (840, 400), (840, 424)], "U", "F") if False else None
    f.legend(H - 56, [("backend", "처리 중"), ("focal", "에이전트가 일하는 상태"), ("input", "기다림"), ("stop", "끝(오류)"),
                      ("optional", "끝(취소)"), ("line:accent", "재개")])
    return f


def fig_failures():
    W, H = 1600, 616
    f = Fig("fail", W, H, "장애 대응 지도 — 실패 상황 → 막는 장치 → 결과",
            "규정 검색 실패, 판단 오류와 무한 반복, 외부 API 장애, 출력 검수 네 가지 실패마다 막는 장치와 그 결과. 값을 모를 때 지어내지 않고, 일정을 바꾸지 않은 채 알리거나 다시 본다.")
    f.max_nodes, f.max_arrows, f.max_accents = 12, 12, 1
    cols = [
        ("4.1 규정 검색 실패", "비슷한 규정 조각 점수가 낮다",
         ["점수 0.55 미만 조각은 버림", "문턱 넘는 최대 3조각만 답에"], ["규정을 지어내지 않음", "못 찾았다고 말하고 일정 사실로 답"]),
        ("4.2 판단 오류 · 무한 반복", "모델이 보기 밖을 고르거나 도구를 계속 부름",
         ["보기 밖 값 · 없는 일정 번호 → 실패", "도구 12번 · 같은 질문 반복 금지 · 90초"], ["일정은 그대로 · 오류 기록", "케이스 오류는 5분 뒤 다시(3번)"]),
        ("4.3 외부 API 장애", "기상 · 교통 소스가 답하지 않는다",
         ["대체 소스로 바꿈(Open-Meteo → 기상청)", "대체도 안 되면 「확인 불가」"], ["일정을 바꾸지 않음", "3분 뒤 회차에서 다시 확인"]),
        ("4.4 출력 검수", "초안 · 알림이 사실과 다르거나 개인정보가 섞임",
         ["근거 대조 · 체크리스트 · 밀도", "번역 숫자 검사 · 개인정보 가림"], ["어긋나면 반영 안 함 · 다음 순위", "번역 실패면 한국어 원문"]),
    ]
    for k, (title, situation, guards, results) in enumerate(cols):
        x = 40 + k * 384
        f.box(f"S{k}", x, 40, 352, 112, kind="input", title=title, lines=[situation])
        f.box(f"G{k}", x, 216, 352, 120, title="막는 장치", lines=guards)
        f.box(f"R{k}", x, 400, 352, 120, kind="external", title="결과", lines=results)
        f.path(f"p{k}a", [(x + 176, 152), (x + 176, 216)], f"S{k}", f"G{k}")
        f.path(f"p{k}b", [(x + 176, 336), (x + 176, 400)], f"G{k}", f"R{k}")
    f.legend(H - 56, [("input", "실패 상황"), ("backend", "막는 장치"), ("external", "결과")])
    return f
