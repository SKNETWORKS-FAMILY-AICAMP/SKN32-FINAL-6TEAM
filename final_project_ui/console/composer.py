"""대상의 인증된 Composer 쓰기 채널 어댑터.

★2026-08-29 — **전송·토큰 발급을 직접 구현하지 않는다.** `acop_composer_ui`
  패키지(`final_project_sample` 이 만들어 배포한다)를 pip 로 설치해 쓴다.
  같은 계약을 두 곳에서 구현하면 한쪽만 고쳐지는 날이 온다
  (`program/plan/A-COP_Composer_소유권_정정.md`,
  `program/research/_컴포저_UI배포구조_점검_2026-08-29.md`).

  이 모듈에 남는 것은 **화면이 쓰는 표현**뿐이다 — 한글 상태 라벨과
  `ComposerResult`. 어떤 요청을 어떻게 보낼지는 패키지가, 그 결과를 화면에서
  어떻게 부를지는 여기가 정한다.

★§0.3 위반이 아니다. 여기서 import 하는 것은 **대상(final_project_cs)의
  Python 이 아니라** sample 이 배포한 라이브러리다. 그 패키지는 대상의 Core
  모델(`ProjectConfig` 등)을 담지 않는다 — sample 쪽 아키텍처 테스트가
  강제한다(`tests/architecture/test_composer_ui_package_boundary.py`).

설치:
    pip install -e ../final_project_sample/packages/acop_composer_ui
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from acop_composer_ui import ComposerClient, ComposerResponse

TOKEN_SUBJECT = "final_project_ui.console"

#: 성공으로 취급하는 상태 라벨.
_SUCCESS = ("읽음", "검증됨", "적용됨", "토글됨", "조회됨", "변경됨")


@dataclass(frozen=True)
class ComposerResult:
    """Composer 호출 결과를 화면에서 구분하기 위한 값."""

    status: str
    value: dict[str, Any] | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in _SUCCESS


def _root_of(url: str | None) -> str | None:
    """프로필의 `composer_url` 을 대상 **루트** 주소로 정규화한다.

    ★프로필에는 `http://host:port/composer` 처럼 `/composer` 접두사까지 넣는
      관례가 있다(테스트 픽스처도 그 형태다). 반면 `acop_composer_ui` 는 루트를
      받아 경로를 스스로 붙인다 — `/auth/token` 은 `/composer` 아래가 아니라
      루트에 있기 때문이다. 그대로 넘기면 토큰 발급이
      `/composer/auth/token` 으로 나가 전부 실패한다(2026-08-29 실측).
    """
    if not url:
        return url
    trimmed = url.rstrip("/")
    if trimmed.endswith("/composer"):
        return trimmed[: -len("/composer")]
    return trimmed


def _client(url: str | None, issuer_secret: str | None, *,
            deployment_id: str | None = None) -> ComposerClient:
    """★`deployment_id` 가 두 운영 방식을 가른다(2026-08-30).

    없으면 **직접 방식** — 대상에 Composer 가 함께 설치돼 있고 그 대상을
    직접 부른다. 있으면 **중앙 방식** — 설정 서비스 한 곳을 부르고 헤더로
    대상을 지정한다. 어느 쪽인지는 프로필이 정한다(`Profile.composer_mode`).
    """
    return ComposerClient(_root_of(url), issuer_secret, subject=TOKEN_SUBJECT,
                          deployment_id=deployment_id)


def _to_result(response: ComposerResponse, success_status: str) -> ComposerResult:
    """패키지의 결과를 화면이 쓰는 한글 상태로 옮긴다.

    ★단계(`phase`)를 먼저 본다. 토큰 발급 실패와 호출 인증 실패는 둘 다
      401 이지만 운영자가 봐야 할 것이 다르다 — 전자는 발급자 비밀키 설정,
      후자는 scope 다.
    """
    if response.ok:
        return ComposerResult(success_status, value=response.payload)

    detail = response.error or ""
    # ★안내 문구는 여기(UI)가 소유한다. 패키지의 일반 메시지("대상 주소가
    #   설정되지 않았다")를 그대로 쓰면 운영자가 **어느 프로필 필드**를 채워야
    #   하는지 알 수 없다 — 화면은 그걸 짚어줘야 한다.
    if response.phase == "config":
        return ComposerResult("연결 안 함", detail="composer_url 이 프로필에 없음")
    if response.phase == "token":
        if not response.status:
            return ComposerResult("토큰 발급 실패",
                                  detail="composer_issuer_secret 이 프로필에 없음"
                                  if "비밀키" in detail else detail)
        return ComposerResult("토큰 발급 실패", detail=f"HTTP {response.status}: {detail}")

    error = response.payload.get("error")
    error = error if isinstance(error, dict) else {}
    if response.status in (401, 403):
        return ComposerResult("인증 실패", detail=f"HTTP {response.status}: {detail}")
    if response.status == 409:
        return ComposerResult("충돌", value=error, detail=detail)
    if response.status == 422:
        return ComposerResult("검증 실패", value=error, detail=detail)
    if response.status:
        return ComposerResult("대상이 응답하지 않음", detail=f"HTTP {response.status}")
    return ComposerResult("대상이 응답하지 않음", detail=detail)


# ── v2 (호환·bulk 경로) ──────────────────────────────────────────────
def read_current(url: str | None, issuer_secret: str | None = None, *,
                 deployment_id: str | None = None) -> ComposerResult:
    """현재 revision과 config를 읽는다."""
    return _to_result(_client(url, issuer_secret, deployment_id=deployment_id).read_current(), "읽음")


def validate_candidate(url: str | None, issuer_secret: str | None,
                       config: dict[str, Any], *,
                       deployment_id: str | None = None) -> ComposerResult:
    """후보 config를 검증한다."""
    result = _to_result(_client(url, issuer_secret, deployment_id=deployment_id).validate(config), "검증됨")
    if result.status == "검증됨" and result.value is not None and result.value.get("valid") is False:
        return ComposerResult("검증 실패", value=result.value,
                              errors=tuple(result.value.get("errors", ())))
    return result


def apply_candidate(url: str | None, issuer_secret: str | None, config: dict[str, Any],
                    *, base_revision: str, reason: str,
                    deployment_id: str | None = None) -> ComposerResult:
    """검증된 후보를 base revision이 일치할 때 적용한다.

    ★`reason`은 선택이 아니다. 대상의 `ApplyPayload`가 `min_length=1`로 요구하고,
    audit 기록의 근거가 된다. 한때 이 함수가 `config`와 `base_revision`만 보내서
    화면의 [적용]이 항상 422로 거부됐다 — 화면은 사유를 입력받고 비었는지 검사까지
    했는데 그 값이 요청에 실리지 않았다(2026-08-28 결함 점검에서 실측).
    그래서 keyword-only 필수 인자로 두었다. 빠뜨리면 호출이 TypeError로 깨진다.
    """
    return _to_result(
        _client(url, issuer_secret, deployment_id=deployment_id).apply(config, base_revision=base_revision, reason=reason),
        "적용됨")


# ── v3 토글 ─────────────────────────────────────────────────────────
def toggle_target(url: str | None, issuer_secret: str | None, *, target_type: str, target_id: str,
                  active: bool, base_revision: str, reason: str,
                  deployment_id: str | None = None) -> ComposerResult:
    """등록된 모듈·Team 하나의 활성 상태만 바꾼다 (`POST /composer/toggle`).

    ★응답의 `activation_state` 는 보통 `pending_restart` 다 — 저장된 것이지
      이미 떠 있는 런타임에 반영된 것이 아니다. 화면은 이 값을 감추지 말고
      그대로 보여줘야 한다.
    """
    return _to_result(
        _client(url, issuer_secret, deployment_id=deployment_id).toggle(target_type=target_type, target_id=target_id,
                                           active=active, base_revision=base_revision,
                                           reason=reason),
        "토글됨")


# ── 카탈로그 기반 인스턴스 CRUD (정본 관리 계약) ─────────────────────
def read_catalog(url: str | None, issuer_secret: str | None = None, *,
                 deployment_id: str | None = None) -> ComposerResult:
    """고를 수 있는 구현 종류와 입력 스키마를 읽는다 (`GET /composer/catalog`).

    ★화면의 생성 폼은 여기서 받은 `parameters_schema` 로 만든다. UI 가 대상의
      스키마를 자기 코드에 복제하지 않기 위해서다.
    """
    return _to_result(_client(url, issuer_secret, deployment_id=deployment_id).catalog(), "조회됨")


def submit_change(url: str | None, issuer_secret: str | None, *, operation: str,
                  resource_type: str, instance_id: str, base_revision: str, reason: str,
                  implementation_id: str | None = None,
                  parameters: dict[str, Any] | None = None,
                  active: bool | None = None, dry_run: bool = False,
                  idempotency_key: str | None = None,
                  deployment_id: str | None = None) -> ComposerResult:
    """인스턴스 하나를 만들거나 고치거나 지운다 (`POST /composer/changes`).

    `operation` 은 `create`·`update`·`delete`·`enable`·`disable`.
    ★유효성은 대상이 판정한다 — 여기서 미리 검사하지 않는다(§0.2).
    """
    return _to_result(
        _client(url, issuer_secret, deployment_id=deployment_id).change(
            operation=operation, resource_type=resource_type, instance_id=instance_id,
            base_revision=base_revision, reason=reason,
            implementation_id=implementation_id, parameters=parameters,
            active=active, dry_run=dry_run, idempotency_key=idempotency_key),
        "변경됨")
