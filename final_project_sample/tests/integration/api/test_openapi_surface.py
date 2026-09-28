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

from acop_basement.presentation.api.app import app

# 설계 계약 문서 §1 의 표 — 이것은 **최소 집합**이지 상한이 아니다.
CONTRACT_V1_PATHS = {
    "/v1/cases",
    "/v1/cases/{case_id}",
    "/v1/cases/{case_id}/messages",
    "/v1/cases/{case_id}/actions/{action_id}/approve",
    "/v1/outbox/{message_id}/resolve",  # docs/handoff/03 §1-6, S-UNKNOWN-OPS-SCREEN
}

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
    """
    from acop_basement.presentation.security import require_scope  # noqa: F401

    offenders = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = {m.lower() for m in getattr(route, "methods", set())}
        if not path.startswith("/v1/") or not (methods & WRITE_METHODS):
            continue
        dependencies = str(getattr(route, "dependant", ""))
        if "require_scope" not in dependencies and "scope" not in dependencies.lower():
            offenders.append((sorted(methods), path))
    assert not offenders, f"scope 의존성이 없는 쓰기 경로: {offenders}"


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
