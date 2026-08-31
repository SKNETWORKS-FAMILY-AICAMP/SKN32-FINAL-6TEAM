"""추가 결함 2 — 권한·Team 계약·outbox.

여기 있는 것 중 권한과 outbox 계열은 실측에서 테스트가 잡지 못했다. 카탈로그에는
남겨 두되 게이트가 자동으로 걸러 낸다. 걸러진 목록 자체가 테스트 사각지대 기록이다.

INV-CONFIG-002(구현 없는 모듈 검사 뒤집기)는 뺐다. 조립이 통째로 깨져 수집 오류가
17건 났다. 구조를 배우는 문제가 아니라 그냥 고장이라 학습 문제로 쓸 수 없다.
"""
from __future__ import annotations

from .defects import Defect

MORE2: list[Defect] = [
    Defect(
        defect_id="INV-SCOPE-002",
        title="scope 가 하나도 없는 주체는 검사를 통과한다",
        invariant="scope 없는 호출은 거부한다",
        path="app/presentation/security.py",
        old="        if scope not in principal.scopes:",
        new="        if scope not in principal.scopes and principal.scopes:",
        lesson=(
            "권한 목록이 빈 주체가 오히려 모든 문을 지난다. 빈 값을 '검사할 게 없다'로 읽으면 "
            "가장 권한 없는 쪽이 가장 자유로워진다."
        ),
        counterfactuals=["scope 가 없으면 아무것도 못 하니 안전하다", "인증을 통과했으면 믿어도 된다"],
        difficulty=3,
    ),
    Defect(
        defect_id="INV-AUTH-001",
        title="Bearer 형식 검사가 사라졌다",
        invariant="인증 헤더는 형식부터 검사한다",
        path="app/presentation/security.py",
        old='    if not authorization or not authorization.startswith("Bearer "):',
        new="    if not authorization:",
        lesson=(
            "형식 검사를 빼면 헤더 문자열이 통째로 토큰으로 취급된다. 예상 못 한 입력이 "
            "인증 경로 깊숙이 들어온다."
        ),
        counterfactuals=["어차피 토큰이 안 맞으면 실패한다"],
    ),
    Defect(
        defect_id="INV-TEAM-001",
        title="반품 가능 기간이 정책보다 길어졌다",
        invariant="Team 은 정책 값을 그대로 쓴다 — 자기 판단으로 늘리지 않는다",
        path="app/modules/customer_ops/return_refund.py",
        old="                    return value[key]",
        new="                    return value[key] + 30",
        lesson=(
            "정책 값을 Team 이 손대면 근거와 답이 어긋난다. 고객에게는 '가능하다'고 말하고 "
            "정책 문서에는 불가능하다고 적혀 있는 상태가 된다."
        ),
        counterfactuals=["고객에게 유리한 방향이면 괜찮다", "여유를 두는 게 안전하다"],
    ),
    Defect(
        defect_id="INV-TEAM-002",
        title="답변 검토에서 사실 대조 결과를 버린다",
        invariant="생성된 답변은 사실과 대조한 뒤 내보낸다",
        path="app/modules/customer_ops/response_review.py",
        old='            problems.extend(f"fact_mismatch:{m.field}" for m in mismatches)',
        new="            problems.extend([])",
        lesson=(
            "대조는 하지만 결과를 버리면 검토가 형식만 남는다. 사실과 다른 문장이 "
            "검토를 통과한 것처럼 고객에게 나간다."
        ),
        counterfactuals=["대조를 돌렸으면 그것으로 충분하다", "LLM 이 알아서 맞게 쓴다"],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-OUTBOX-001",
        title="outbox 발행에서 tenant 불일치 검사가 꺼졌다",
        invariant="다른 tenant 의 Case 로 메시지를 발행할 수 없다",
        path="app/infrastructure/messaging/outbox.py",
        old='                    if case_tenant_id is not None and payload.get("tenant_id") not in (None, case_tenant_id):',
        new='                    if False and case_tenant_id is not None and payload.get("tenant_id") not in (None, case_tenant_id):',
        lesson=(
            "발행 경계에서 tenant 를 확인하지 않으면, 한 tenant 의 Case 사건이 다른 tenant 의 "
            "이름을 달고 나간다. 메시지는 되돌릴 수 없다."
        ),
        counterfactuals=["Case 를 만들 때 이미 확인했다", "consumer 쪽에서 거르면 된다"],
    ),
    Defect(
        defect_id="INV-OUTBOX-002",
        title="tenant 를 모를 때 임시값으로 채운다",
        invariant="값을 모르면 비워 둔다 — 추정으로 채우지 않는다",
        path="app/infrastructure/messaging/outbox.py",
        old='                    tenant_id = payload.get("tenant_id") or case_tenant_id',
        new='                    tenant_id = payload.get("tenant_id") or case_tenant_id or "unknown"',
        lesson=(
            "모르는 값을 그럴듯한 문자열로 채우면 오류가 데이터가 된다. 나중에 이 메시지를 "
            "누가 보냈는지 되짚을 방법이 사라진다."
        ),
        counterfactuals=["빈 값보다는 뭐라도 넣는 게 낫다", "unknown 은 명시적이니 괜찮다"],
        difficulty=2,
    ),
]
