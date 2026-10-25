# Dining 2단계 — 같은 실행의 확인 결과 재사용

2026-10-23, Asia/Seoul. 사용자가 요청한 2번을 로컬에 구현했다. 전체 진행 2/3 = 66.7%. 1단계 변경은 보존했고 3단계 질문·답변 연결은 이번에 수정하지 않았다.

## 동작

- 같은 `DiningTools` 인스턴스에서 도구 이름·인자 값이 같으면 확인된 이전 결과와 원래 `call_id`를 반환한다. 인자 객체의 키 순서는 무시한다. 다른 식당·시간·날짜·속성·실행은 별도 조회다.
- 실제 도구 호출 기록(`calls`)과 새 조회 예산은 늘리지 않는다. 호출 상한에 도달해도 기존 확인 결과를 반환하며 새로운 조회는 거절한다. `allowed`·`off_scope`는 재사용 전에 검사한다.
- `bad`·`closed`처럼 확인된 부정 판정도 재사용한다. unknown·찾지 못함·빈 검색 목록·빈 속성·속성 미확인·명시적 오류·거절·예외는 재사용하지 않는다. 미확인 재조회는 새 호출로 세고 기존 상한을 적용한다.
- 입력·실행 인자·반환 결과·`result_of()`를 깊게 복사해 외부에서 배열이나 중첩 객체를 수정해도 저장된 조회 조건·근거가 바뀌지 않게 했다.
- 재사용 응답에 `reused=true`를 붙이고 `DiningTools.reused`에는 도구와 원 call_id만 기록한다. `AgentResult.stats.cache_hits`로 재사용 횟수를 남기며 기존 접수 `_run` 감사 기록에도 stats를 통해 포함된다.
- 영구·프로세스 공용 캐시나 시간 기반 TTL은 추가하지 않았다. 인스턴스를 만드는 실행 단위가 재사용 범위다. 에이전트의 기존 좌표·이름 기반 재검색 방지는 별도 기존 동작으로 유지하며, 새 `cache_hits`는 이번 동일 인자 계층의 적중만 센다.
- `max_turns`·deadline은 그대로다. 같은 결과를 반복 요청해도 모델의 실행 한도가 풀리지 않는다.

## 수정 위치

- `instances/dining/agent_tools.py`: 확인 결과 재사용, 실제 호출 예산 순서, 사본 반환, 재사용 기록.
- `instances/dining/agent.py`: `cache_hits` 통계 추가. 1단계 검사 누락 집계 변경은 보존.
- `tests/unit/travel/test_dining_tool_reuse.py`: 새 회귀 시험 24개.
- `tests/integration/dining/test_dining_agent_tools.py`: 같은 결과를 반복 거절하던 기대를 원 call_id 재사용 기대에 맞춤.

## 검증

| 실행 | 결과 |
|---|---|
| 최초 새 시험 | 13개 중 6개 실패를 먼저 재현. 반복 거절·상한에서 재사용 불가·입력/반환 객체 공유·집계 누락 확인 |
| 새 재사용 회귀 시험 | 24/24 = 100% 통과 |
| 1단계 회귀 포함 최종 확인 | 35/35 = 100% 통과 |
| 관련 Python 단위·통합 시험 13파일 | 183/192 = 95.3% 통과, 기존 실패 2개, DB 통합 7개 건너뜀. 실패·건너뜀을 분모에서 제외하지 않음 |
| 변경 Python ruff F·E9 | 종료 코드 0, 위반 없음 |

실행에서 새 실제 조회 2회와 반복 요청 1회를 가진 합성 에이전트 흐름은 `tool_calls=2`, `cache_hits=1`, `refused=0`이며, 원 call_id 근거로 기존 판정 검증을 통과했다. 실제 서비스의 비용·응답시간 절감률은 측정하지 않았다.

### 명령

cs 폴더에서:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_dining_tool_reuse.py tests/unit/travel/test_dining_required_checks.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_dining_tool_reuse.py tests/unit/travel/test_dining_required_checks.py tests/unit/travel/test_dining_agent.py tests/unit/travel/test_dining_agent_scope.py tests/unit/travel/test_dining_agent_turns.py tests/unit/travel/test_dining_customer_requests.py tests/unit/travel/test_dining_judge_merge.py tests/unit/travel/test_dining_judge_evidence.py tests/unit/travel/test_dining_judge_stale.py tests/unit/travel/test_intake_dining_completion.py tests/unit/travel/test_intake_dining_gate_policy.py tests/unit/travel/test_dining_agent_eval_metrics.py tests/integration/dining/test_dining_agent_tools.py -q --tb=short -rs
.\.venv\Scripts\python.exe -m pytest tests/integration/dining/test_dining_agent_tools.py -q --tb=short -rs
.\.venv\Scripts\python.exe -m ruff check --select F,E9 app/domains/travel_ops/instances/dining/agent_tools.py app/domains/travel_ops/instances/dining/agent.py tests/unit/travel/test_dining_tool_reuse.py tests/integration/dining/test_dining_agent_tools.py
```

기존 실패 2개는 1단계에서 수정 전에도 재현한 접수 시험의 가짜 연결 잠금 검사다:

- `test_force_review_prepares_the_new_token_before_returning`
- `test_loading_an_old_cached_review_does_not_create_a_new_gate`

DB 시험은 처음 localhost:5433 접근 권한 오류로 건너뛰었고, 정상 권한으로 같은 7개를 재시도해도 연결 시간 초과로 모두 건너뛰었다. DB 생성·스키마 적용 단계에는 진입하지 못했다. 실제 DB 통합 통과로 보고하지 않는다. 모델·지도·구글 등 외부 서비스는 호출하지 않았다. 웹은 수정하지 않아 이번 단계에서 재시험하지 않았다.

## 보존·남은 작업

별도 변경 검토에서 정상 반환한 빈 검색 결과도 재사용되는 점을 지적받았다. hits=[]·places=[]로 2개 실패 시험을 먼저 재현한 뒤 빈 hits·places·attributes를 제외하도록 수정했다. 재검토자는 빈 자료 제외 3건과 양성 자료 유지 3건을 함수로 독립 확인해 6/6 = 100% 통과했고, 새 중요 지적은 없었다. 재검토자가 전체 pytest를 실행한 것은 아니다.

수정 전 5개 파일은 루트 `_backup/2026-10-23_dining-result-reuse/manifest.json`과 같은 폴더의 사본에 보존했다. 커밋·푸시·운영 배포는 하지 않았다. 다음은 3번, 모호한 고객 조건의 질문·답변과 현재 접수 재검증 연결이다.
