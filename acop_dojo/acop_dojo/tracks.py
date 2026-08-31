"""파트별 학습 트랙.

전체 1개 + 파트 6개다. 경계는 사람이 아니라 **디렉터리로** 긋는다 —
`docs/handoff/05_분업_규칙.md` 가 같은 이유로 그렇게 한다. 두 사람이 같은 파일을
쓰면 마지막에 끝난 쪽이 조용히 이기기 때문이다.

★팀 모듈 3분할은 추정이다. 저장소에 사람 배정 문서가 없어 모듈 성격으로 나눴다.
   담당이 다르면 아래 `owns` 만 고치면 된다 — 결함·지도·시나리오가 따라온다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    track_id: str
    title: str
    owner_hint: str
    #: 이 트랙이 책임지는 경로 접두사. 빈 튜플이면 전체다.
    owns: tuple[str, ...]
    #: 이 파트가 다루는 시나리오들. 첫 번째가 기본값이다.
    scenarios: tuple[str, ...]
    #: 이 파트에서 반드시 설명할 수 있어야 하는 것
    focus: str

    @property
    def scenario(self) -> str:
        return self.scenarios[0]


TRACKS: dict[str, Track] = {
    "all": Track(
        track_id="all",
        title="전체 — 요청 하나가 끝까지 가는 길",
        owner_hint="전원",
        owns=(),
        scenarios=("shipping-status-resolved-v1",),
        focus="Case 가 만들어지고 라우팅되고 Team 이 처리한 뒤 상태가 닫히는 전 구간",
    ),
    "core1": Track(
        track_id="core1",
        title="Core 1 — Case 실행 런타임",
        owner_hint="코어 1",
        owns=("app/core/transition.py", "app/core/contracts.py", "app/core/registry.py",
              "app/core/context.py", "app/core/idempotency.py", "app/core/remote_team/",
              "app/domain/", "app/application/controller.py", "app/application/case_service.py",
              "app/infrastructure/messaging/"),
        scenarios=("shipping-status-resolved-v1", "case-reducer-versions-v1"),
        focus="상태는 이벤트를 접은 결과다. transition_case 만이 상태를 바꾼다",
    ),
    "core2": Track(
        track_id="core2",
        title="Core 2 — 외부 접근과 Action 실행",
        owner_hint="코어 2",
        owns=("app/presentation/api/", "app/presentation/security.py", "app/presentation/a2a/",
              "app/core/verification.py", "app/application/proposal_guard.py", "app/tools/",
              "app/infrastructure/a2a/"),
        scenarios=("api-idempotent-create-v1",),
        focus="같은 요청을 열 번 보내도 side effect 는 한 번. scope 없는 호출은 거부",
    ),
    "team-voc": Track(
        track_id="team-voc",
        title="Team — VOC & Store Manager",
        owner_hint="팀 모듈 담당 1",
        owns=("app/modules/customer_ops/voc_store_manager.py",
              "app/modules/customer_ops/feedback.py", "app/application/feedback_job.py"),
        scenarios=("voc-batch-tenant-scoped-v1", "voc-degraded-escalates-v1"),
        focus="분류 실패를 조용히 넘기지 않는다. 배치는 tenant 안에서 멱등이다",
    ),
    "team-review": Track(
        track_id="team-review",
        title="Team — Response Generation & Review",
        owner_hint="팀 모듈 담당 2",
        owns=("app/modules/customer_ops/response_review.py",
              "app/modules/customer_ops/response_review_policy.py"),
        scenarios=("review-pii-escalates-v1",),
        focus="근거 없는 답변을 만들지 않는다. PII 가 보이면 재시도하지 않고 넘긴다",
    ),
    "team-commerce": Track(
        track_id="team-commerce",
        title="Team — 커머스 연계 (조달·주문·배송·반품·카탈로그)",
        owner_hint="팀 모듈 담당 3",
        owns=("app/modules/customer_ops/procurement_order_payment.py",
              "app/modules/customer_ops/fulfillment_logistics.py",
              "app/modules/customer_ops/return_refund.py",
              "app/modules/customer_ops/catalog_verification.py",
              "app/modules/customer_ops/verification_policy.py"),
        scenarios=("procurement-policy-evidence-v1", "return-refund-no-side-effect-v1",
                   "fulfillment-lost-shipment-approval-v1", "catalog-compliance-escalates-v1"),
        focus="Team 은 side effect 를 실행하지 않는다. 정책 값을 자기 판단으로 바꾸지 않는다",
    ),
    "front": Track(
        track_id="front",
        title="프론트 — 운영 화면",
        owner_hint="프론트",
        owns=("app/presentation/ui/",),
        scenarios=("ui-evidence-free-proposal-v1",),
        focus="근거 없는 제안은 화면에서 결정할 수 없어야 한다 — 규칙이 UI 까지 내려온다",
    ),
}


def get(track_id: str) -> Track:
    try:
        return TRACKS[track_id]
    except KeyError:
        known = ", ".join(TRACKS)
        raise SystemExit(f"모르는 트랙이다: {track_id}\n아는 것: {known}") from None


def owns(track: Track, path: str) -> bool:
    """전체 트랙은 모두 자기 것이다."""
    if not track.owns:
        return True
    return any(path.startswith(prefix) for prefix in track.owns)
