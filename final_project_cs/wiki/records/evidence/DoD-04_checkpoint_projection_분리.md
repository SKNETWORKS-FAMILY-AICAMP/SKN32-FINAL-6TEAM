# DoD-04 — LangGraph checkpoint 와 업무 projection 이 분리된다

- v5 §20 항목 4 / 검증 방법: graph revision test
- 최초 판정: 2026-08-12 **부분 통과** (`agent_runs` 가 비어 실행 관측 없음)
- 재측정: 2026-08-14 · 실측 원문 `wiki/records/evidence/_raw/DoD-04_v3.md`
- 판정: 통과

## 재현 명령

```powershell
python  # REST 로 Case 생성(fake classifier·fake Team 주입) 후 agent_runs 조회
```

## 실제 출력 (재측정)

```
REST 응답 = 201
agent_runs 행 = 1
graph_revision = 'measurement-v3', distinct 개수 = 1
checkpoint 키 순서 = case_id, run_id, graph_revision, node_name, runtime_state
```

## 판정 근거

| 요구 (v5 §6-3) | 결과 |
|---|---|
| ★**run 이 실제로 기록된다** | **통과** — `agent_runs` 1행 (최초 판정 때 0행이던 부분) |
| ★**graph_revision 이 run 내내 고정** | **통과** — distinct = 1 |
| checkpoint 가 최소 집합만 담는다 | **통과** — `case_id`·`run_id`·`graph_revision`·`node_name`·`runtime_state`. 업무 상태(status/version/intent)를 담지 않는다 |
| checkpoint 로 업무 상태를 되돌리지 않는다 | **통과** — 상태 변경 경로가 `transition_case()` 하나뿐이고 `customer_cases` 직접 UPDATE 가 0건이다(DoD-02). **되돌릴 경로 자체가 없다** |

## 최초 판정에서 무엇이 바뀌었나

2026-08-12 실측은 `graph_revision_rows = []` 였다. 컬럼은 있는데 **값이 없었다.**
당시 판정에 이렇게 적었다:

> ★**컬럼이 있다는 것과 값이 채워진다는 것은 다르다.**

원인은 **composition root 부재**였다 — `create_app()` 이 Controller·Registry·Executor 를
조립하지 않아 REST 요청이 Controller 를 타지 않았다.
`app/composition.py` 를 만들어 조립한 뒤 재측정해 위 결과를 얻었다.

## 한계

- 측정에 **fake classifier·fake Team 을 주입**했다 (이 환경은 외부망이 막혀 있다)
- ★**checkpoint rollback 시 projection 이 영향받지 않는지**를 실제로 되돌려 확인하지는 않았다.
  근거는 "되돌릴 코드 경로가 없다"는 정적 사실이다
- 여러 run 이 동시에 도는 상황에서의 revision 고정은 검증하지 않았다
