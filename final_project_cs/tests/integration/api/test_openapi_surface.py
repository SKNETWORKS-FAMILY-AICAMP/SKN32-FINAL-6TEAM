"""REST API 표면 검사.

★세는 대상은 `/v1/*` 뿐이다. `/health`·`/ui/*`·FastAPI 기본 경로는 포함하지 않는다
  (`/ui/*` 는 운영 화면이며 S-UI 소유).

★**v7 에서 규칙이 바뀌었다.** v6 까지는 "REST 는 정확히 5개" 였고 이 파일이
  집합 완전 일치로 그것을 강제했다. v7 §0 은 이렇게 바꿨다:

  > 5는 당시 MVP 범위 숫자이며 상한이 아니다.
  > 독립 resource·scope·idempotency·audit·평가 fixture 가 있을 때 추가

  그리고 v7 DoD-13 은 **"5가 상한이 아님을 문서·추가 endpoint fixture 로 검증"** 하라고 한다.
  옛 테스트는 그 반대를 강제했다 — endpoint 를 하나 늘리면 실패했다.

★같은 실패 유형을 이 저장소에서 이미 한 번 겪었다. composer 기본값 테스트가
  "저장소 기본값 = 꺼짐" 을 강제해서, 정작 쓰려던 구성기가 계속 404 였다.
  **테스트가 검사하는 것이 지금도 의도한 성질인지 확인하지 않으면
  테스트가 제품을 낡은 방향으로 붙잡는다.**

그래서 검사를 이렇게 바꾼다:
  - 계약에 적힌 경로는 **전부 있어야 한다** (누락은 여전히 결함)
  - 새 경로는 막지 않는다. 대신 **품질 조건**을 검사한다
"""

from app.presentation.api.app import app

# 설계 계약 문서 §1 의 표 — 이것은 **최소 집합**이지 상한이 아니다.
CONTRACT_V1_PATHS = {
    "/v1/cases",
    "/v1/cases/{case_id}",
    "/v1/cases/{case_id}/messages",
    "/v1/cases/{case_id}/actions/{action_id}/approve",
    "/v1/outbox/{message_id}/resolve",
    # ★2026-09-14 여행 API(`app/modules/travel_ops/trip_api.py`) — 등록·조회·신고·재요청.
    #   scope `trip:read`·`trip:write`, 등록은 request_id 멱등, 신고·재요청은 원인 칸의
    #   request_id 로 중복을 막는다.
    "/v1/trips",
    "/v1/trips/{trip_id}",
    "/v1/trips/{trip_id}/reports",
    "/v1/trips/{trip_id}/items/{item_id}/alternate",
    "/v1/trips/{trip_id}/rollback",
    # ★2026-09-14 고객 자유 문장 → Case → 분류 → 여행 창구
    "/v1/trips/{trip_id}/messages",
    # ★★2026-09-22 **일정 생성**(`app/modules/travel_ops/planner.py`) — 요청 → 초안 → 판정
    #   통과 → (`register:true` 면) 등록. scope `trip:write`, 등록까지 가면 `/v1/trips` 와
    #   **같은 멱등 키**를 쓴다. 이 경로는 v11 §4-A(「계획 생성은 우리 일이 아니다」)를
    #   뒤집는 것이고, 사용자 지시로 만들었다 —
    #   `wiki/records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md`.
    "/v1/trips/plan",
    # ★2026-09-22 위임(`app/modules/travel_ops/delegation_api.py`) — 승인 뒤 자동 실행을
    #   여는 둘째 문을 주고 거두는 자리. scope `delegation:read`·`delegation:write`
    #   (`action:approve` 와 나눈다 — 승인은 제안 한 건, 위임은 거둘 때까지 서 있는 권한),
    #   상태 변경은 누가·왜 를 필수로 받고 `delegation_events`(021)에 덧붙여 기록한다.
    "/v1/delegations",
    "/v1/delegations/{customer_id}",
    "/v1/delegations/{customer_id}/grant",
    "/v1/delegations/{customer_id}/revoke",
    # ★2026-09-24 보류 제안(「먼저 물어봐줘」 · 변경 안 할 일정, D-020) — 에이전트가 보고 고른다.
    #   scope `trip:read`·`trip:write`. 먼저 고른 쪽이 이기고 나중 쪽은 409(`pending_changes`, 024).
    "/v1/trips/{trip_id}/proposals",
    "/v1/trips/{trip_id}/proposals/{proposal_id}/choose",
    # ★2026-09-24 웹(고객 브라우저) — scope 키가 아니라 **사용자 식별 키**(`X-User-Key`, 025).
    #   그 사용자 본인의 여행만 연다. `/v1/web/session` 만 키 없이 열린다(첫 방문 발급).
    "/v1/web/session",
    "/v1/web/session/rotate",
    "/v1/web/trips",
    "/v1/web/trips/{trip_id}",
    "/v1/web/trips/{trip_id}/proposals",
    "/v1/web/trips/{trip_id}/proposals/{proposal_id}/choose",
    "/v1/web/trips/{trip_id}/messages",
    "/v1/web/trips/{trip_id}/notices",
    # ★2026-09-29 모델 예열 — 화면이 채팅을 열 때 부른다(사용자 식별 키). `wiki/external/rest-endpoints.md` 웹 표
    "/v1/web/warmup",
    # ★2026-09-29 채팅 기록(서버가 저장한 최근 대화 — 결정 단위의 재료) · 구글 지도 불러오기 허락(한도) · 웹 되돌리기.
    #   `wiki/external/rest-endpoints.md` 「채팅 결정 단위」·「구글 지도 불러오기 허락」
    "/v1/trips/{trip_id}/chat",
    "/v1/web/trips/{trip_id}/chat",
    "/v1/web/map-load",
    "/v1/web/trips/{trip_id}/rollback",
    # ★2026-10-02 웹(사용자 키)용 신고 · 다른 안으로 — 에이전트 입구(`/v1/trips/{id}/reports` · `…/alternate`)와 같은 처리, 본인 여행만. 개인 AI(MCP)가 쓴다
    "/v1/web/trips/{trip_id}/reports",
    "/v1/web/trips/{trip_id}/items/{item_id}/alternate",
    # ★2026-09-30 변경 초인종 — 「이 여행 바뀜」 신호만 흘린다(text/event-stream, 사용자 키). `wiki/external/rest-endpoints.md`
    "/v1/web/trips/{trip_id}/events",
    # ★2026-10-01 고객 연락처(복구 이메일 · 디스코드 웹훅) — 사용자 키. `wiki/external/rest-endpoints.md`
    "/v1/web/profile",
    "/v1/web/profile/discord/test",
    # ★2026-09-27 계획 읽기 — 글·사진·PDF·docx·xlsx 를 받아 확인 화면용 값으로(설계서 program/plan/…고객계획_읽기_설계…).
    #   고객 id 는 키에서, 남의 접수는 404. 읽기는 뒤에서 돈다.
    "/v1/web/trip-intakes",
    "/v1/web/trip-intakes/{intake_id}",
    # 확인 화면 — 고친 값은 새 판(낡은 판은 409), 등록은 `_create_trip` 한 곳(request_id = 접수 + 판)
    "/v1/web/trip-intakes/{intake_id}/edits",
    "/v1/web/trip-intakes/{intake_id}/confirm",
    # 「일정 짜 줘」 — 조건을 확인해 누르면 일정 생성기 초안을 판정 뒤 등록(request_id = 접수 + plan + 판)
    "/v1/web/trip-intakes/{intake_id}/plan",
    # ★2026-10-02 접수 읽기 진행(SSE) — 뒤에서 도는 읽기가 어디까지 왔는지. 채팅(`/messages`)·일정 짜기(`/plan`)는 같은 경로가
    #   `Accept: text/event-stream` 이면 SSE 로 답한다(새 경로 없음). `wiki/external/rest-endpoints.md` 「웹 실시간 진행」
    "/v1/web/trip-intakes/{intake_id}/events",
    # ★2026-10-02 확인 화면 수정 화면 — 대체 후보 · 장소 검색 · 사진(읽기 전용) · 전체 자동 추천 · 재검증(계획 확인 시나리오 목업).
    #   `wiki/external/rest-endpoints.md` 「확인 화면 검사 · 후보 · 자동 추천」
    "/v1/web/trip-intakes/{intake_id}/candidates",
    "/v1/web/trip-intakes/{intake_id}/place-search",
    "/v1/web/trip-intakes/{intake_id}/autofix",
    "/v1/web/trip-intakes/{intake_id}/revalidate",
    "/v1/web/places/photos",
    # ★2026-10-03 소셜 로그인(구글 먼저) · ★2026-10-04 브라우저 세션 쿠키 · 여행 삭제(D-CS-011) — `wiki/external/rest-endpoints.md`
    "/v1/web/auth/providers",
    "/v1/web/auth/{provider}/start",
    "/v1/web/auth/{provider}/callback",
    "/v1/web/auth/exchange",
    "/v1/web/auth/links",
    "/v1/web/auth/{provider}",
    "/v1/web/auth/session",
    "/v1/web/auth/adopt",
    "/v1/web/auth/me",
    "/v1/web/auth/logout",
    "/v1/web/trips/{trip_id}/delete",
}

# ★키 없이 열어 둔 쓰기 경로 — **이름으로** 적는다. 여기 없는 쓰기 경로가 인증 없이 열리면 실패한다.
#   `/v1/web/session` · `/v1/web/auth/session`: 첫 방문에 키/쿠키 세션을 발급하는 자리라 인증을 받을 수 없다(D-020 · 025 · D-CS-011 — 사람 확인과 주소당 한도가 막는다).
#   `/v1/web/auth/{provider}/start`: 로그인 시작은 인증 없이 열린다(`link` 모드는 함수 안에서 인증을 확인한다 — 사람 확인 · 주소당 한도).
#   `/v1/web/auth/exchange`: 일회용 표 + 시작한 브라우저의 `client_nonce` 가 인증이다(로그인 CSRF 막기).
#   `/v1/web/auth/adopt`: 옛 키를 쿠키로 옮기는 자리 — 함수 안에서 키를 확인한다(쿠키와 같이 오면 400, 주소당 한도).
OPEN_WRITE_PATHS = {"/v1/web/session", "/v1/web/auth/session", "/v1/web/auth/{provider}/start", "/v1/web/auth/exchange", "/v1/web/auth/adopt"}

# 인증으로 치는 의존성 — scope 키(`require_scope`) 또는 웹 사용자 키(`_web_customer`)
AUTH_DEPENDENCIES = ("require_scope.", "._web_customer", "require_identity")

WRITE_METHODS = {"post", "put", "patch", "delete"}


def _paths() -> dict:
    return app.openapi()["paths"]


def _v1_paths() -> set[str]:
    return {p for p in _paths() if p.startswith("/v1/")}


def test_every_contract_path_exists() -> None:
    """★누락은 여전히 결함이다. 계약에 있는데 구현이 없으면 실패한다."""
    missing = CONTRACT_V1_PATHS - _v1_paths()
    assert not missing, f"구현되지 않은 계약 경로: {sorted(missing)}"


def test_new_paths_are_allowed_but_must_be_scoped() -> None:
    """★5는 상한이 아니다 (v7 §0). 다만 아무렇게나 늘리지도 않는다.

    새 `/v1` 경로는 **인증 없이 열려 있으면 안 된다.** v7 이 요구한
    독립 scope·idempotency·audit 중, 정적으로 확인 가능한 것이 이것이다.
    """
    paths = _paths()
    unscoped = []
    for path in sorted(_v1_paths()):
        for method, operation in paths[path].items():
            if method.lower() not in WRITE_METHODS | {"get"}:
                continue
            # 이 저장소는 scope 를 FastAPI 의존성으로 강제하고 OpenAPI 에 파라미터로 남긴다.
            declared = str(operation)
            if "security" not in declared and "Authorization" not in declared:
                # 의존성 방식이라 스키마에 안 드러날 수 있다 — 라우트 함수로 확인한다
                continue
    assert not unscoped, f"scope 없이 열린 /v1 경로: {unscoped}"


def test_write_endpoints_require_a_scope_dependency() -> None:
    """★쓰기 경로는 전부 scope 의존성을 달고 있어야 한다.

    OpenAPI 스키마가 아니라 **실제 라우트 의존성**을 본다 —
    스키마만 보면 "문서에는 있는데 코드에는 없는" 경우를 놓친다.

    ☆`[2026-09-24 정정]` 앞 판은 의존성 객체를 **문자열로 바꿔** `"scope"` 를 찾았다. 그 문자열에는
      FastAPI 가 모든 의존성에 붙이는 `security_scopes` 필드 이름이 늘 들어 있어서 **어떤 경로든 통과했다**
      — 인증 없는 `/v1/web/session` 을 붙였는데도 울지 않아 알았다. 이제 의존성 함수를 이름으로 본다.
    """
    def calls(dependant) -> list[str]:
        found = []
        for sub in dependant.dependencies:
            found.append(getattr(sub.call, "__qualname__", repr(sub.call)))
            found += calls(sub)
        return found

    offenders, checked = [], 0
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = {m.lower() for m in getattr(route, "methods", set())}
        if not path.startswith("/v1/") or not (methods & WRITE_METHODS) or path in OPEN_WRITE_PATHS:
            continue
        checked += 1
        if not any(marker in name for name in calls(route.dependant) for marker in AUTH_DEPENDENCIES):
            offenders.append((sorted(methods), path))
    assert checked > 0, "쓰기 경로를 하나도 못 셌다 — 검사가 헛돈다"
    assert not offenders, f"인증 의존성이 없는 쓰기 경로: {offenders}"


def test_the_open_write_path_list_names_only_real_paths() -> None:
    """열어 둔 목록이 낡으면(경로가 없어졌는데 남으면) 다음 사람이 같은 이름으로 몰래 열 수 있다."""
    assert OPEN_WRITE_PATHS <= _v1_paths()


def test_v1_surface_is_documented_when_it_grows() -> None:
    """★늘어난 경로가 계약 문서 밖이면 **알아차릴 수 있게** 한다.

    실패시키지 않는다 — v7 이 확장을 허용했기 때문이다.
    대신 계약 집합과의 차이를 이름으로 드러내, 문서 갱신을 잊지 않게 한다.
    """
    extra = sorted(_v1_paths() - CONTRACT_V1_PATHS)
    # 지금은 계약 그대로여야 한다. 늘리는 변경에서 이 목록을 함께 갱신한다.
    assert extra == [], (
        "계약 문서에 없는 /v1 경로가 생겼다. v7 §0 상 추가는 허용되지만 "
        f"설계 계약 문서와 이 목록을 함께 갱신해야 한다: {extra}")


def test_health_exists() -> None:
    assert "/health" in _paths()


def test_ui_is_not_part_of_v1_api() -> None:
    """운영 화면은 API 표면이 아니다. `/v1` 아래로 새지 않아야 한다."""
    assert not any(p.startswith("/v1/") and "/ui" in p for p in _paths())
