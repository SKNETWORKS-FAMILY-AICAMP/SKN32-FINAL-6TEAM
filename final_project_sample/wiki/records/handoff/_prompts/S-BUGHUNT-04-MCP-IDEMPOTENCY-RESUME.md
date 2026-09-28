# S-BUGHUNT-04-MCP-IDEMPOTENCY-RESUME — MCP·idempotency·resume 버그 사냥 (리포트만, 수정 금지)

## 배경

라운드 1~3 이력:
- `wiki/records/reports/debugs/2026-08-17_버그사냥_01_5건_발견_3건_수정.md`
- `wiki/records/reports/debugs/2026-08-17_버그사냥_02_3건_발견_2건_수정_1건_해소.md`
- `wiki/records/reports/debugs/2026-08-17_버그사냥_03_환불제안이_매번_거부됐다.md`
  (★가장 심각했던 것 — Team 단독 테스트와 검증 단독 테스트가 서로 다른
  손으로 만든 입력만 봐서, 실제 Team 출력이 검증을 매번 통과 못 하는 걸
  아무도 못 잡았다. **이런 "두 테스트가 서로 다른 입력만 보는" 유형을
  이번에도 우선 찾는다.**)

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3).

## 스캔 범위

1. `app/presentation/api/mcp.py` — MCP tool 3개(`get_my_cases`, `get_case_detail`,
   `open_support_case`). 전부 `mcp:read` 여야 하고 payments/subscriptions 를
   건드리면 안 된다
2. `app/core/idempotency.py` — idempotency key 계산
3. `app/presentation/api/cases.py` 의 **resume/messages 엔드포인트**
   (approve 엔드포인트는 라운드 1 에서 이미 봤다 — 이번엔 `POST
   /v1/cases/{case_id}/messages` 와 resume token 검증 쪽)
4. `app/application/case_service.py` (있다면 — resume token 발급·검증,
   중복 실행 방지)

## 찾을 것

라운드 1~3 과 같은 기준. 특히 이번엔:

- **MCP tool 이 실수로 쓰기 경로를 타는 곳** — `open_support_case` 가 Case
  생성 이상의 일을 하는지(v7 §0 변경 4 — MCP 는 Case 생성·분류 시작까지만)
- **idempotency key 가 실제로 같은 논리적 요청에 항상 같은 값을 내는지** —
  입력 순서·타입 변환(str vs UUID)에 따라 같은 요청인데 다른 key 가 나올
  수 있는 곳
- **resume token 이 재사용되거나, 만료 후에도 통과하는 경로** — CLAUDE.md
  가 "24h TTL·일회성"이라고 못박은 것이 실제로 강제되는지
- **"두 테스트가 서로 다른 입력만 보는" 유형** — 예: idempotency key 를
  만드는 함수의 단위 테스트와, 실제 REST 핸들러가 그 함수에 넘기는 인자가
  서로 다른 형태(대소문자·공백·타입)를 가정하고 있지 않은지

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다 —
못 찾으면 못 찾았다고 적는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_04_MCP_idempotency_resume.md` 하나만. 형식은
이전 라운드와 같다:

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
