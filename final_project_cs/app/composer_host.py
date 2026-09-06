"""이 제품이 Composer 패키지에 넘기는 것 — **호스트 어댑터**.

★v9 §8-D: **cs 소스 안에 Composer 구현을 두지 않는다.** 2026-09-06 이전에는
  `app/presentation/api/composer.py`(157줄) · `app/application/composer_service.py`
  (167줄) · `app/presentation/composer_auth.py`(76줄)가 sample 것을 손으로 베낀
  사본이었다. 한쪽만 고쳐지는 날이 반드시 오고, 실제로 그랬다 — sample 이
  `/catalog`·`/changes`·`/revisions`·`/restore` 를 갖는 동안 cs 는 네 개에
  머물러 **콘솔의 카탈로그·변경 카드가 cs 에서는 뜨지 않았다.**

  이제 구현은 패키지(`acop_composer`)에 하나만 있고, 이 파일은 **이 제품의
  것**(스키마·등록표·저장소·인증·경로)만 넘긴다.

★관리용 빌드에만 이 파일이 쓰인다. 릴리즈 빌드는 `acop_composer` 를 설치하지
  않고, `app/presentation/api/app.py` 가 Composer 없이 뜬다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acop_composer.host import AuthPolicy, ComposerHost, ConfigInvalid, Implementation
from acop_composer.stores import RevisionMismatch, StoreError, StoreTarget

from app.core import settings as settings_module
from app.core.composer_stores import (
    FileAuditStore, FileConfigStore, FileRevisionStore,
    RevisionMismatch as HostRevisionMismatch, StoreError as HostStoreError,
)
from app.core.project_config import (
    DEFAULT_PROJECT_CONFIG, ProjectConfigError, config_from_declaration,
    config_revision,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: JWT `aud`. ★sample 과 **다른 값**이어야 한다 — 남의 발급자가 만든 토큰이
#:  이쪽에서 통하면 안 된다.
AUDIENCE = "final_project_cs"

#: direct(pip) 방식이라 이 프로세스가 다루는 대상은 자기 자신 하나다.
#: ★파일 저장소는 이 값을 쓰지 않는다. 중앙 저장소를 도입하면 그때 설정에서 온다.
DEPLOYMENT_ID = "self"


class _Codec:
    """이 제품의 선언 스키마를 패키지가 쓸 수 있는 모양으로 감싼다."""

    def from_declaration(self, raw: dict[str, Any], *, source: str) -> Any:
        try:
            return config_from_declaration(raw, source=source)
        except ProjectConfigError as exc:
            # ★패키지는 이유를 만들지 않는다. 이 제품이 만든 메시지를 그대로 옮긴다.
            raise ConfigInvalid(str(exc)) from exc

    def to_declaration(self, config: Any) -> dict[str, Any]:
        return config.model_dump(mode="json")

    def revision(self, config: Any) -> str:
        """★내용에서 나온다 — 파일 mtime 이나 커밋이 아니다.

        ★sample 은 12자로 자르고 이쪽은 sha256 64자 그대로다. 형식을 맞추면
          **기존에 발급된 base_revision 이 전부 어긋나** 저장이 409 로 튕긴다.
          revision 은 그 대상 안에서만 비교되므로 형식이 달라도 되고, 굳이
          맞출 이유가 없다(2026-09-06 판단).
        """
        # ★코어의 계산을 그대로 쓴다. 두 벌 만들면 `/introspection` 이 말하는
        #   revision 과 Composer 가 말하는 revision 이 갈리는 날이 온다.
        return config_revision(config)


@dataclass(frozen=True)
class _TranslatingStore:
    """저장소 예외를 패키지 예외로 옮긴다.

    ★예외도 계약이다. 이 옮김이 없으면 패키지의 `except RevisionMismatch` 가
      **조용히 빗나가서** revision 충돌이 409 대신 500 으로 나간다
      (sample 에서 실제로 그랬다, 2026-09-06 실측).

    ★`path` 같은 값 속성은 그대로 비쳐 보여야 한다 — 감사의 `subject` 가 읽는다.
    """

    inner: Any

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if not callable(attr):
            return attr

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                return attr(*args, **kwargs)
            except HostRevisionMismatch as exc:
                raise RevisionMismatch(exc.current_revision) from exc
            except HostStoreError as exc:
                raise StoreError(str(exc)) from exc

        return wrapped


class _Stores:
    """선언·이력·감사를 어디에 두는가 — 이 제품은 **파일뿐**이다.

    ★`target.central` 이 참이면 거부한다. 중앙 저장소 구현이 없는데 조용히
      파일로 떨어지면, 설정 서비스로 띄웠을 때 **남의 대상을 자기 파일에
      쓰는** 사고가 소리 없이 일어난다.
    """

    @staticmethod
    def _reject_central(target: StoreTarget) -> None:
        if target.central:
            raise StoreError(
                "이 제품은 중앙 설정 저장소를 구현하지 않았다(direct 방식, v9 §8-D). "
                "설정 서비스로 띄우려면 중앙 저장소 구현을 먼저 넣어야 한다")

    def config_store(self, target: StoreTarget):
        self._reject_central(target)
        return _TranslatingStore(FileConfigStore(target.config_path))

    def revision_store(self, target: StoreTarget):
        self._reject_central(target)
        return _TranslatingStore(FileRevisionStore(target.revisions_path))

    def audit_store(self, target: StoreTarget):
        self._reject_central(target)
        return _TranslatingStore(FileAuditStore(target.audit_path))


#: 이 제품이 등록한 구현. ★`app/core/project_config.py` 의
#:  `KNOWN_IMPLEMENTATION_REFS` 와 **같은 집합**이어야 한다 — 아래 게이트가 센다.
IMPLEMENTATIONS: tuple[Implementation, ...] = (
    Implementation(
        id="team.procurement_order_payment",
        ref="app.modules.customer_ops.procurement_order_payment:ProcurementOrderPaymentTeam",
        display_name="발주·주문·결제 Team",
        description="주문 조회와 결제 사실 확인. 실행은 제안까지다.",
    ),
    Implementation(
        id="team.fulfillment_logistics",
        ref="app.modules.customer_ops.fulfillment_logistics:FulfillmentLogisticsTeam",
        display_name="물류·배송 Team",
        description="배송 상태 조회와 지연 판단.",
    ),
    Implementation(
        id="team.return_refund",
        ref="app.modules.customer_ops.return_refund:ReturnRefundTeam",
        display_name="반품·환불 Team (Mock)",
        description="반품 자격과 환불 금액 산정. 쇼핑몰 연동은 Mock 이다.",
    ),
    Implementation(
        id="team.catalog_verification",
        ref="app.modules.customer_ops.catalog_verification:CatalogVerificationTeam",
        display_name="카탈로그 검증 Team (A2A Remote)",
        description="상품 정보 대조. A2A 원격 실행 경로다.",
    ),
    Implementation(
        id="team.response_review",
        ref="app.modules.customer_ops.response_review:ResponseGenerationReviewTeam",
        display_name="응답 생성·검토 Team",
        description="톤 결정 → 생성 → 결정론 검토 → 톤 검토. PII 는 즉시 escalate.",
    ),
    Implementation(
        id="team.voc_store_manager",
        ref="app.modules.customer_ops:VocStoreManagerTeam",
        display_name="VOC·스토어 매니저 Team (껍데기)",
        description="Registry 등록·계약만 유지한다. 집계·급증 탐지는 코어 1 소유다(v9 §0).",
    ),
)


def _auth_policy() -> AuthPolicy:
    """★비밀을 **값이 아니라 함수**로 넘긴다 — 이 객체를 로깅해도 안 샌다."""
    return AuthPolicy(
        audience=AUDIENCE,
        jwt_secret=lambda: settings_module.get_settings().composer_jwt_secret,
        # ★서명 비밀과 **다른 값**이다(cs 는 둘을 나눠 뒀다).
        issuer_secret=lambda: settings_module.get_settings().composer_issuer_secret,
        configured_scopes=lambda: frozenset(
            settings_module.get_guardrails().get("security.scopes")),
        ttl_minutes=lambda: int(
            settings_module.get_guardrails().get("security.composer_jwt_ttl_minutes")),
    )


def composer_host() -> ComposerHost:
    """이 제품용 `ComposerHost`."""
    return ComposerHost(
        codec=_Codec(),
        implementations=IMPLEMENTATIONS,
        stores=_Stores(),
        auth=_auth_policy(),
        default_config_path=Path(DEFAULT_PROJECT_CONFIG),
        # ★`parents[N]` 을 세지 않는다. 이 파일 기준으로 한 번만 계산한다 —
        #   sample 이 이 숫자를 그대로 베껴 가 감사·이력을 저장소 **밖**에
        #   쌓은 적이 있다(2026-09-06, 감사 9건·이력 62건).
        audit_dir=REPO_ROOT / "var" / "audit",
        default_deployment_id=lambda: DEPLOYMENT_ID,
    )


__all__ = ["AUDIENCE", "DEPLOYMENT_ID", "IMPLEMENTATIONS", "composer_host"]
