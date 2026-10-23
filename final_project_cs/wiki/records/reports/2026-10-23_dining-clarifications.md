# Dining 3단계 — 모호한 조건 질문·답 저장·재검증

2026-10-23, Asia/Seoul. 사용자가 요청한 3번을 로컬에 구현했다. 세 보완의 로컬 구현 진행은 3/3 = 100%다. 운영 배포 완료나 전체 제품 검증 통과를 뜻하지 않는다.

## 고객 흐름과 변경

1. 모델이 고객 원문에서 읽은 조건의 적용 식사가 모호하면, 원문 인용·속성·필수 여부가 검증된 `request_scope_unclear`만 질문으로 만든다. 현재 접수의 식사만 날짜·시각·이름으로 선택지에 넣는다. 날짜별로 반복된 같은 질문은 합친다.
2. 확인 화면 목록 안에서 고객이 여러 식사를 선택하거나 「이 조건 취소」를 누른다. 고정 로딩 설문과 구분한다. 미응답을 임의로 전체 식사에 적용하지 않는다.
3. `POST /v1/web/trip-intakes/{id}/dining-answers`가 소유권을 포함해 접수 행을 잠그고 revision·run_id·상태·현재 원문 서명을 대조한다. 클라이언트는 질문 id와 선택만 보내며 원문·속성·필수 여부를 바꾸지 못한다.
4. 답을 기존 `intake_reviews.payload.dining_questions`에 원문과 함께 저장하고, 같은 판에 새 검사 토큰을 준비한다. 동적 답을 검사 서명에 포함한다. 실제 모델 대기 중에는 DB 잠금을 유지하지 않는다.
5. 에이전트는 `customer_clarifications`로 답을 받는다. 코드도 모델의 해당 원문 목록에 고객의 선택·취소를 우선 적용한다. 모델이 목록 항목을 빠뜨려도 저장된 조건은 검사 대상으로 남는다. 다른 날짜의 식사에는 그 날짜에서만 검사한다.
6. 재검사 중에는 질문의 재제출과 등록을 기다리게 하고 최신 결과를 주기 조회한다. 답 저장 응답이 늦게 와도 더 최신 판·토큰·등록 상태의 화면을 덮지 않는다.

질문·답은 해당 접수 판의 검사 자료다. 일정 편집으로 판이 바뀌거나 전체 재검증이 저장된 검사를 새로 만들면 자동 승계하지 않으며, 오래된 답변은 거절한다. 새 DB 표·영구 캐시·업체 거래 자동 승인은 추가하지 않았다. 1단계 검사 누락과 2단계 실행 내 재사용은 유지한다.

### 조건 정정과 독립 판정 보호

조건의 적용 식사를 바꾸거나 취소하면 해당 원문·속성의 식사 조건 행만 제거한다. 영업·휴무·폐업 등 독립적인 확정 불가 행은 남는다. 비조건 검사에는 고객 조건의 request_id가 붙어 와도 customer_request를 연결하지 않는다.

에이전트가 상태를 낮추기 전의 ready·항목 상태·잠금 가능 여부를 `before_dining_judge`에 보존한다. 정정한 조건의 이전 bad를 제거한 뒤에는 그 기준 상태를 복원하되 다른 bad·기존 확인 필요·이동 문제를 무시하지 않는다. 정정 직후 새 검사 토큰은 pending으로 등록을 기다리게 한다. 미확인 자체로 등록을 막지 않는 기존 정책은 유지한다.

## 검증 결과

| 범위 | 결과 |
|---|---|
| 새 서버 질문·답변·API 시험 | 29/29 = 100% |
| 관련 Python 단위 회귀 14파일 | 212/214 = 99.1%, 기존 접수 잠금 가짜 저장소 시험 실패 2건 포함 |
| 관련 웹 시험 5파일 | 79/79 = 100% |
| 실제 브라우저 부품·모형 API 동작 | 6/6 = 100% 확인: 초기 선택 없음, 실제 식사 선택, 답변 본문, 재검사 대기, 취소 본문, 화면 오류 없음 |
| 선택한 구조·웹 계약·도구 경계·인증/scope 시험 | 304/305 = 99.7%. 실패 1건은 설치되지 않은 acop_composer 의존성 |
| 변경 Python ruff F·E9 | 종료 코드 0, 위반 없음 |
| 웹 타입 검사 | `npm run typecheck` 종료 코드 0 |
| 변경 웹 파일 ESLint | 종료 코드 0 |

모델 응답·DB 저장·고객 인증은 시험용 모형으로 대체했다. API 시험은 실제 FastAPI 경로를 호출하고, 별도 시험은 저장한 답으로 실제 Dining 판정 루프·근거 검증·완료 저장까지 실행했다. 원문의 모호한 모델 결과에서 실제 질문 저장까지도 시험했다. 실제 DB·유료 모델·외부 지도·운영 API는 호출하지 않았다. 전체 접수 페이지를 실서버에 연결한 시험은 하지 않았다.

실패를 먼저 확인한 주요 사례: 질문 부품 부재, 조건 취소 뒤 ready가 돌아오지 않음, 잘못 붙은 request_id로 영업시간 bad까지 삭제됨, 늦은 답변의 캐시 교체 방어 부재. 각각 수정 뒤 관련 회귀가 통과했다.

### 별도 검토

검토자가 조건 취소의 독립 영업 판정 삭제(P1)와 늦은 답변 응답의 화면 역행(P2)을 재현했다. 식사 조건 행 제한·비조건 source 연결 차단과 현재 판/토큰 기반 응답 적용으로 수정했다. 두 지적 2/2 = 100% 해결을 재검토했고 새 고·중위험 결함은 발견하지 못했다. 검토자는 Python 관련 18/18 = 100%를 별도로 실행했으며 웹 시험은 직접 실행하지 않았다.

### 기존 실패·환경 한계

- `test_force_review_prepares_the_new_token_before_returning`, `test_loading_an_old_cached_review_does_not_create_a_new_gate`: 1단계에서 수정 전에도 재현한 가짜 저장소의 잠금 assertion 실패다. 이번에 관계없는 제품 잠금을 약화하지 않았다.
- 전체 구조·계약·보안 묶음은 `test_declared_refs_are_savable.py` 수집 중 `acop_composer` 미설치로 중단됐다. 이 전체 묶음의 실행 완료 분모는 모름이다. 이후 선택 묶음의 305개는 위 표에 별도 집계했다.
- DB를 요구하는 query_scope를 포함한 선택 묶음은 DB 연결 대기로 중단했고, 이를 제외한 선택 묶음으로 다시 확인했다. DB 보안 통합 통과로 보고하지 않는다.
- `npm run lint` 전체는 기존 `.next-hongdae-check` 생성물과 수정하지 않은 `use-intake-registration.ts`의 기존 effect 규칙 등으로 오류 365·경고 5,924를 보고했다. 생성물을 삭제하거나 무관한 파일을 바꾸지 않았다. 수정한 웹 소스만 지정한 ESLint는 통과했다.
- 기존 웹 타입 오류는 동적 질문의 판정 상태·등록 경계 연결에 필요한 IntakeDiningJudge·Review.dining_judge·CheckLine와 이미 반환되는 식사 조건 행의 선언을 보완해 이번 타입 검사에서는 해소됐다.

## 실행 명령

cs 폴더:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_dining_clarifications.py tests/unit/travel/test_dining_clarification_api.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_dining_clarifications.py tests/unit/travel/test_dining_clarification_api.py tests/unit/travel/test_dining_tool_reuse.py tests/unit/travel/test_dining_required_checks.py tests/unit/travel/test_dining_agent.py tests/unit/travel/test_dining_agent_scope.py tests/unit/travel/test_dining_agent_turns.py tests/unit/travel/test_dining_customer_requests.py tests/unit/travel/test_dining_judge_merge.py tests/unit/travel/test_dining_judge_evidence.py tests/unit/travel/test_dining_judge_stale.py tests/unit/travel/test_intake_dining_completion.py tests/unit/travel/test_intake_dining_gate_policy.py tests/unit/travel/test_dining_agent_eval_metrics.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/architecture tests/contract/test_web_client_contract.py tests/contract/test_team_layout.py tests/contract/test_team_tool_discipline.py tests/security/test_auth_and_scope_guards.py tests/security/test_scope_contract.py -q --tb=short
```

웹 폴더:

```powershell
npm run test -- src/features/intake-review/dining-questions.test.ts src/features/plan-check/dining-status.test.ts src/features/plan-check/from-review.test.ts src/features/intake-review/use-intake-registration.test.ts src/lib/live/intake-review.test.ts
npm run typecheck
npx eslint src/features/intake-review/dining-questions.tsx src/features/intake-review/dining-questions.test.ts src/features/intake-review/intake-review.tsx src/features/plan-check/plan-check.tsx src/features/plan-check/model.ts src/features/plan-check/parts.tsx src/lib/live/intake-review.ts
node ..\..\..\..\_backup\2026-10-23_dining-clarifications\browser-check.mjs
```

로컬 TestClient 시험은 샌드박스에서 진행이 멈춰 중단 후 정상 권한으로 실행했다. 브라우저 확인용 임시 실행기는 JSX 변환 설정을 조정한 뒤 성공했다. 이 임시 실행기의 실패를 제품 UI의 실패로 합산하지 않으며, 최종 성공 범위는 위의 모형 부품 시험이다.

## 화면·보존·인계

- [질문 — 휴대폰](../../../../_backup/2026-10-23_dining-clarifications/questions-mobile.png)
- [답 저장 후 재검사 대기 — 휴대폰](../../../../_backup/2026-10-23_dining-clarifications/answered-pending-mobile.png)
- [조건 취소 후 — 데스크톱](../../../../_backup/2026-10-23_dining-clarifications/cancelled-desktop.png)

수정 전 13파일과 실행기·모형 요청 기록은 루트 `_backup/2026-10-23_dining-clarifications/`에 있다. 현재 role-dining의 기존 미커밋 작업을 보존했다. 커밋·푸시·운영 배포는 하지 않았다. 실제 환경 검증은 DB·Composer 의존성·운영 모델 연결이 준비된 환경에서 별도로 해야 한다.
