# S-BUGHUNT-02-CONTEXT-RAG-A2A — 컨텍스트·RAG·A2A·라우팅 버그 사냥 (리포트만, 수정 금지)

## 배경

`S-BUGHUNT-01-CORE-SAFETY` 라운드에서 5건을 찾아 3건을 고쳤다
(`wiki/records/reports/debugs/2026-08-17_버그사냥_01_5건_발견_3건_수정.md`). 사용자가
자리를 비운 동안 Codex 쿼터가 남아 있어 다음 영역으로 라운드를 이어간다.

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 라운드 1과 같다(`RULE.md` §3.6-3) — 아무 파일도 수정하지 않는다.
발견한 것을 근거·재현 명령과 함께 리포트로만 낸다.

## 스캔 범위 (이번 라운드는 이 파일들만)

1. `app/core/context.py` — Context Broker. 12,000 토큰 예산, 결정적 절삭 순서,
   `degraded`/`omissions` 신호
2. `app/infrastructure/rag/retriever.py` — pgvector 검색, tenant/scope 필터
3. `app/core/remote_team/executor.py`, `app/core/remote_team/a2a_executor.py`
   — LOCAL/A2A TeamExecutorPort, Agent Card 발견, 실패·타임아웃·취소·인증
4. `app/core/registry.py` — capability→Team 라우팅, `allowed_tools` 강제

## 찾을 것 — 라운드 1과 같은 기준

구체적인 실패 시나리오(입력/상태 → 무엇이 잘못되는지 → 왜 기존 테스트가 못
잡는지)가 없는 지적은 적지 않는다. 특히 우선 찾을 패턴:

- **토큰 예산 실측 오류** — `tiktoken` 실측이 아니라 추정으로 새는 경로,
  예산 초과인데도 절삭 신호(`degraded`/`omissions`) 없이 그냥 넘어가는 경로
  (RULE.md §3.2 — "신호 없는 축소는 폴백이다")
  - degraded=true 인데 팀 실행을 막지 않는 경로가 있으면 **DoD-25 위반**이니
    최우선으로 본다
- **tenant/scope 필터가 빠지는 RAG 쿼리** — SQL 에 tenant 조건이 없거나,
  파라미터 바인딩이 아니라 문자열 결합으로 들어가는 곳(injection 위험)
- **A2A 실패·타임아웃·취소가 예외를 삼키고 성공처럼 넘어가는 경로** —
  `except Exception: pass`류, 또는 실패 상태를 상위로 전파하지 않는 곳
- **`allowed_tools` 밖의 tool 을 부를 수 있는 경로** — Registry 가 막아야 하는데
  우회 가능한 곳
- **capability 라우팅이 tenant 를 안 가르는 경우** — 남의 tenant 의 Team
  설정/manifest 가 섞일 수 있는 곳

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다 —
못 찾으면 못 찾았다고 적는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_02_컨텍스트_RAG_A2A.md` 하나만. 형식은
라운드 1 리포트(`wiki/records/reports/2026-08-17_버그사냥_01_안전핵심부.md`)와 같다:

```
### <파일:줄번호> — <한 줄 요약>
- 시나리오: <구체적 입력/상태 → 무엇이 잘못되는지>
- 왜 기존 테스트가 못 잡는가: <이유>
- 재현 시도: <실제로 재현을 시도했다면 그 결과. 못 했으면 "재현 안 해봄, 코드 읽기로만 판단">
- 위험도: 높음 | 보통 | 낮음
```

## 완료 기준

```powershell
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 338 passed 여야 한다
```
