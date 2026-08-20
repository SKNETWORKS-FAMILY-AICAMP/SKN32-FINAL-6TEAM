# S-TEAM-RETURN-REFUND — Return & Refund Team (Mock 전용)

## 0. 배경 (읽기만)

- `program/plan/A-COP_예제Team모듈_확충설계.md` — 이 Team 의 확정 설계 문서.
  이미 결정된 스펙을 그대로 구현해라, 새로 설계하지 마라.
- `program/plan/A-COP_구현계획서_v8.md` §8-B — 이 Team 은 **Registry 계약 +
  Mock 으로 유지한다.** 실제 스마트스토어 반품·교환 데이터로 반품사유
  코드체계·상태전이가 검증되기 전까지는 LOCAL(실제 DB 연동)로 승격하지
  않는다. **이번 작업은 승격이 아니라 Mock 단계 구현이다.**
- `legacy/final_project_cs/team_modules_v1/customer_ops/return_exchange.py`
  — 옛 구현(다른 팀 경계였지만 evidence 구성·승인게이트 ActionProposal·
  기간만료 검사 패턴은 참고할 가치가 있다). **그대로 복사하지 마라** —
  case_type·capability 이름이 v8 스펙과 다르다. 패턴만 참고해라.
- `app/modules/customer_ops/voc_store_manager.py`,
  `app/modules/customer_ops/response_review.py` — 현재 이 저장소에서
  실제로 동작하는 Team 구현 예시. `TeamManifest`/`TeamTask`/`TeamResult`
  계약을 어떻게 지키는지 이 둘을 먼저 읽고 형식을 맞춰라.

## 1. 확정 스펙 (설계 문서에서 그대로 가져옴 — 바꾸지 마라)

```
team_id: return_refund
capabilities: [return.check_eligibility, return.request, refund.calculate]
accepted_case_types: [return, refund, exchange]
allowed_tools: [read.order, read.return, read.policy]
knowledge_scope: [order, return, refund, exchange, policy]
```

## 2. Mock 원칙 (가장 중요 — 어겨서는 안 됨)

- **"Mock 은 fake side effect 를 성공 처리하지 않는다."** 실행 가능한 것처럼
  보이는 요청도 `ActionProposal` 에서 멈춘다 — 절대 `outcome="completed"`
  로 환불이 실제로 처리된 것처럼 응답하지 않는다. 반품 접수·환불 계산
  결과는 전부 `approval_required=True` 인 제안으로 끝난다.
- 계산(예: `refund.calculate` 의 환불 금액 산정)은 실제로 계산해서 근거와
  함께 제시하되, 이 계산이 **제안**이지 **확정된 처리**가 아니라는 걸
  `next_action`/`outcome` 으로 명확히 구분해라.
- Evidence 없이 반품사유·수량·기한을 판단하지 마라 — `CLAUDE.md` §0.1
  원칙 그대로: 근거 없으면 `waiting_input`/`escalated`.

## 3. 할 일

1. `app/modules/customer_ops/return_refund.py` 작성 — `TeamManifest` 는
   §1 스펙 그대로, `execute()` 는 다음을 다룬다:
   - `return.check_eligibility`: 주문/반품 정책 대조해서 반품 가능 여부
     판정(기간 만료, 이미 반품 이력 등 — 근거 기반)
   - `return.request`: 반품 접수 **제안**(승인 필요)
   - `refund.calculate`: 환불 금액 산정 **제안**(승인 필요, 계산 근거 명시)
2. `app/modules/customer_ops/__init__.py` 에 export 추가(다른 export 는
   건드리지 마라).
3. `tests/unit/teams/test_return_refund.py` 작성 — 최소: 정상 반품접수
   제안, 기간만료로 반려, evidence 없을 때 escalate, Mock 원칙 위반 안
   하는지(즉 outcome 이 completed 로 실제 환불을 자처하지 않는지) 검증.

## 4. 쓰기 대상

- `app/modules/customer_ops/return_refund.py` (신규)
- `app/modules/customer_ops/__init__.py` (export 추가만)
- `tests/unit/teams/test_return_refund.py` (신규)
- `docs/reports/2026-08-20_S-TEAM-RETURN-REFUND_리포트.md` (신규)

## 5. 하지 말 것

- `config/project.yaml` 수정 금지 — **등록은 Claude 가 한다**(동시에 여러
  Codex 세션이 같은 설정 파일을 건드리면 충돌한다).
- `legacy/` 아래 파일 수정 금지
- 다른 Team 파일(`voc_store_manager.py`, `response_review.py` 등) 수정 금지
- LOCAL 승격(실제 DB write 경로) 시도 금지 — Mock 단계까지만

## 6. 검증

- `python -m pytest -q -m "not live"` 실행 결과를 리포트에 실제 출력
  그대로 붙여라. 실행 전후 pass 수 변화를 명시해라(현재 338 passed).
