# S-BUGHUNT-03-TEAMS-VOC — Team 비즈니스 로직·VOC 배치 버그 사냥 (리포트만, 수정 금지)

## 배경

라운드 1(`wiki/records/reports/debugs/2026-08-17_버그사냥_01_5건_발견_3건_수정.md`, 안전
핵심부 5건→3건 수정)과 라운드 2(`wiki/records/reports/debugs/2026-08-17_버그사냥_02_3건_발견_2건_수정_1건_해소.md`,
Context/RAG/A2A/Registry 3건→2건 수정+1건 버그 아님 확인)에 이어 세 번째 라운드다.

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3). 아무 파일도 수정하지 않는다.

## 스캔 범위 (이번 라운드는 이 파일들만)

1. `app/modules/customer_ops/billing.py` — Billing/Subscription Team. 결제·환불
   제안을 만드는 로직
2. `app/modules/customer_ops/technical.py` — Technical/Entitlement Team
3. `app/modules/customer_ops/feedback_team.py` — VOC 를 감싼 Team wrapper
4. `app/application/feedback_job.py` — 일일 배치. `outbox` 에 **직접 SQL** 로
   쓰는 유일한 프로덕션 경로 중 하나(다른 하나는 `OutboxBrokerAdapter`)
5. `app/modules/customer_ops/verification_policy.py` — 도메인이 선언하는
   대조 규칙(무엇을 사실과 맞춰볼지)

## 찾을 것

라운드 1·2 와 같은 기준 — 구체적 시나리오 없는 지적은 적지 않는다. 특히:

- **금액·식별자를 다루면서 `verification_policy.py` 선언과 실제로 제안하는
  필드가 어긋나는 곳** — 정책은 A 필드를 대조 대상으로 선언했는데 코드는
  B 필드로 제안을 만드는 식의 어긋남
- **`feedback_job.py` 의 outbox 직접 INSERT** — tenant_id 파라미터 바인딩이
  맞는지, dedupe_key 가 batch 재실행 시 중복을 정말 막는지(예: 같은 날 배치를
  두 번 돌리면 같은 dedupe_key 가 나오는지, 아니면 매번 새로 나와 중복
  발행되는지)
- **Team 이 `next_action=ESCALATE` 를 내면서 `failure_code` 도 `warnings` 도
  없는 경로** — 계약(`app/core/contracts.py`)이 이 경우를 막는지, 막는다면
  어떻게 뚫릴 수 있는지
- **billing.py/technical.py 가 `task.context` 의 `degraded=true` 를 무시하고
  그냥 진행하는 경로** — DoD-25("degraded Context 자동 실행 금지")가 실제로
  이 두 Team 안에서도 지켜지는지, 아니면 Controller 레벨에서만 막고 Team
  자체는 무방비인지

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_03_Teams_VOC.md` 하나만. 형식은 라운드 1·2 와 같다:

```
### <파일:줄번호> — <한 줄 요약>
- 시나리오: <구체적 입력/상태 → 무엇이 잘못되는지>
- 왜 기존 테스트가 못 잡는가: <이유>
- 재현 시도: <실제로 재현을 시도했다면 그 결과. 못 했으면 "재현 안 해봄, 코드 읽기로만 판단">
- 위험도: 높음 | 보통 | 낮음
```

## 완료 기준

```powershell
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 341 passed 여야 한다
```
