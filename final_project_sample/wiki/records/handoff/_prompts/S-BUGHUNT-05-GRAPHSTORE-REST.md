# S-BUGHUNT-05-GRAPHSTORE-REST — SqlGraphAdapter·나머지 REST 버그 사냥 (리포트만, 수정 금지)

## 배경

라운드 1~4 이력(전부 `wiki/records/reports/debugs/2026-08-17_버그사냥_*.md`):
- 01: 안전 핵심부 5건→3건 수정
- 02: Context/RAG/A2A/Registry 3건→2건 수정+1건 버그 아님
- 03: **환불 제안이 검증에서 매번 거부되고 있었다**(최고 위험도 — Team 출력과
  검증기를 실제로 연결해 보는 테스트가 없어서 아무도 못 잡았다)
- 04: MCP idempotency 중복생성·idempotency key 충돌 2건 수정, resume token
  미검증 1건 보류(REST 계약 변경 필요), event_id 조기반환 1건은 버그 아님으로 확인

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3).

## 스캔 범위

1. `app/infrastructure/graphstore/sql_adapter.py` — `SqlGraphAdapter`.
   Case→Issue→Policy, Issue→Team, Case→Action 관계 질의 3종(DoD-21)
2. `app/presentation/api/cases.py` 의 `GET /v1/cases`(목록), `GET /v1/cases/{id}`
   (상세) — 라운드 1 은 approve, 라운드 4 는 messages 를 봤다. 이번엔 이 둘
3. `app/infrastructure/db/repository.py` — REST/MCP 가 공통으로 쓰는 조회 함수들

## 찾을 것

라운드 1~4 와 같은 기준 — 특히 라운드 3·4 에서 반복된 패턴을 우선 찾는다:
**"이 함수를 테스트하는 쪽"과 "실제로 이 함수를 호출하는 쪽"이 서로 다른
가정을 하고 있어서, 실제 호출 경로는 한 번도 검증된 적이 없는 경우.**

- **`SqlGraphAdapter` 의 SQL 이 tenant_id 조건을 빠뜨린 곳** — 관계 질의
  3종 전부 확인
- **관계 깊이 제한(`depth`)이 실제로 SQL 에 반영되는지, 아니면 파이썬에서만
  잘라서 DB 는 무제한으로 긁는지** — 후자면 대량 데이터에서 성능·정보 노출
  문제가 될 수 있다
- **`GET /v1/cases` 페이지네이션이 `limit` 만 있고 정렬 기준이 없어서, 같은
  요청을 반복해도 결과 순서가 안정적이지 않은 경우** — 클라이언트가 "새 항목"
  을 놓치거나 중복으로 볼 수 있다
- **`repository.py` 의 조회 함수 중 tenant_id 조건이 빠졌거나, 문자열 결합으로
  SQL 을 만드는 곳**(injection 위험)

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다 —
못 찾으면 못 찾았다고 적는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_05_GraphStore_REST.md` 하나만. 형식은
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
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 345 passed 여야 한다
```
