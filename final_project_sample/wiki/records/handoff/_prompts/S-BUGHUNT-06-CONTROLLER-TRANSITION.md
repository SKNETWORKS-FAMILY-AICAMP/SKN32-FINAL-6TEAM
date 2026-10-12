# S-BUGHUNT-06-CONTROLLER-TRANSITION — Controller WAIT/RESUME·전이표 버그 사냥 (리포트만, 수정 금지)

## 배경

라운드 1~5 이력(전부 `wiki/records/reports/debugs/2026-08-17_버그사냥_*.md`):
- 01: 안전 핵심부 5건→3건 수정
- 02: Context/RAG/A2A/Registry 3건→2건 수정+1건 버그 아님
- 03: **환불 제안이 검증에서 매번 거부되고 있었다**(최고 위험도)
- 04: MCP idempotency 2건 수정, **resume token 미검증 1건 보류**(가장 중요한
  미해결 항목 — `POST /v1/cases/{id}/messages` 가 진짜 토큰을 검증하는
  `Controller.resume()`/`CaseService.validate_resume()` 를 아예 안 거친다.
  이 라운드가 그 주변을 더 파고든다)
- 05: subgraph() DoD-21 축 누락, Case 목록 정렬 결정성 2건 수정

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3).

## 스캔 범위

1. `app/application/controller.py` 전체 — 특히 `run_case()`, `resume()`,
   guardrail 타임아웃 처리(`case_wall_clock_seconds`, `team_timeout_seconds`)
2. `app/core/transition.py` — 순수 상태 전이 리듀서·전이표. 라운드 1 은
   outbox INSERT 부분만 봤다 — 이번엔 전이표 자체(어떤 상태에서 어떤
   이벤트가 허용되는지)
3. `app/domain/events.py` — `EventType` 정의와 전이표가 실제로 일치하는지

## 찾을 것

라운드 1~5 와 같은 기준. 특히:

- **resume 관련 — 라운드 4 의 연장선**: `Controller.resume()` 와
  `POST /v1/cases/{id}/messages` 가 정말 완전히 분리돼 있는지, 아니면
  어딘가 연결점이 있는지 다시 한번 정밀하게 확인한다. `resume()` 을 실제로
  호출하는 경로가 REST/MCP/스케줄러 어디에도 없다면 그 사실 자체와, 그게
  왜 위험한지(진짜 토큰 검증 로직이 죽은 코드로 남아 있다는 것)를 다시 명확히 적는다
- **guardrail 타임아웃이 실제로 강제되는지** — `case_wall_clock_seconds`·
  `team_timeout_seconds` 를 넘긴 실행이 계속 진행되는 경로가 있는지
- **전이표에 없는 이벤트가 조용히 통과하는 경로** — `transition.py` 가
  선언 안 된 `(status, event_type)` 조합을 막는지, 막는다면 어떻게 뚫릴 수
  있는지
- **`replay_case()`(있다면)가 실제로 case_events 를 순서대로 재생하는지,
  아니면 중간에 빠뜨리는 이벤트가 있는지**
- **동시에 두 요청이 같은 Case 를 resume/run 하려 할 때 `max_active_runs_per_case`
  가드레일이 실제로 막는지, 아니면 문서에만 있는지**

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다 —
못 찾으면 못 찾았다고 적는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_06_Controller_전이표.md` 하나만. 형식은
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
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 346 passed 여야 한다
```
