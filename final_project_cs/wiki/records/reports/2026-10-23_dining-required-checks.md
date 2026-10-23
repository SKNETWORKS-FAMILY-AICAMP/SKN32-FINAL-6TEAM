# Dining 1단계 — 필수 검사 누락 확인·고객 안내

2026-10-23, Asia/Seoul. 사용자가 승인한 세 보완 중 1번만 구현했다. 전체 진행 1/3 = 33.3%. 결과 재사용과 모호한 조건 질문·답변은 아직 구현하지 않았다.

## 문제와 수정

- `agent.py`는 근거 검증 실패한 체크의 이름도 완료 집합에 넣고 있었다. 실패 체크를 제외했다. 정직한 unknown은 완료 응답으로 남긴다. 검사 항목 자체가 없는 empty_result와 검증 실패를 구분한다.
- `judge.py`는 누락을 DB 감사 기록에만 남겼다. 현재 식사에 `dining_check` unknown 안내를 합치도록 `completion.py`를 추가했다. 조건 속성·요청 식별자는 구분해 보존한다. 실제로 검증된 기존 ok·bad 행은 덮지 않는다.
- 수명주기에서는 반환된 missing 목록이 비어 있어도 found·시각이 있는 open_at과 원문 조건 목록의 대상 식사·속성 검사를 독립적으로 대조한다. empty_result의 누락도 처리한다. 오래된 revision·run_id 결과는 기존 저장 경계를 통과하지 못한다.
- 웹의 행 타입·표시 이름에 dining_check를 추가했다. 안내 자체는 unknown이며 별도의 등록 차단·필수 수정 표시로 승격하지 않는다.
- 모델이 조건 원문 목록 자체에서 빠뜨린 의미까지 코드가 완벽히 알아낸다는 보장은 추가하지 않았다. 코드로 고객 문장을 재분류하지 않는다.

## 검증 증거

모델·실제 DB·운영 API는 호출하지 않았다. 저장 경계 시험은 가짜 연결을 사용했다.

| 실행 | 결과 |
|---|---|
| 새 회귀 시험 `test_dining_required_checks.py` | 최종 11/11 = 100%. 최초 6개 실패 재현 후 수정, 추가한 수명주기 방어 시험 2개도 실패를 먼저 확인했다 |
| 관련 Python 시험 10파일 | 143/145 = 98.6%. 아래의 기존 실패 2개 포함 |
| 웹 회귀 시험 3파일 | 57/57 = 100% |
| 변경 Python의 ruff F·E9 | 종료 코드 0, 위반 없음 |
| 웹 `npm run typecheck` | 오류 15건. 수정 전 파일을 메모리에서 대체하고 새 시험을 제외한 TypeScript 진단에서도 같은 기존 오류 15건 재현. 이번 변경의 추가 진단 없음 |
| 변경분 별도 검토 | 검토자가 백업 대비 지정 파일 7/7 = 100% 검토, 구체적인 고·중위험 회귀 미발견. 추가 시험은 실행하지 않음 |

### 실행 명령

cs 폴더에서:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_dining_required_checks.py tests/unit/travel/test_dining_agent.py tests/unit/travel/test_dining_agent_scope.py tests/unit/travel/test_dining_agent_turns.py tests/unit/travel/test_dining_customer_requests.py tests/unit/travel/test_dining_judge_merge.py tests/unit/travel/test_dining_judge_evidence.py tests/unit/travel/test_dining_judge_stale.py tests/unit/travel/test_intake_dining_completion.py tests/unit/travel/test_intake_dining_gate_policy.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check --select F,E9 app/domains/travel_ops/instances/dining/agent.py app/domains/travel_ops/instances/dining/judge.py app/domains/travel_ops/instances/dining/completion.py tests/unit/travel/test_dining_required_checks.py
```

웹 폴더에서:

```powershell
npm run test -- src/features/plan-check/dining-completion.test.ts src/features/plan-check/from-review.test.ts src/features/plan-check/dining-status.test.ts
npm run typecheck
```

웹 시험 최초 시도는 샌드박스 임시 파일 ENOENT로 2개 묶음이 로드되지 않았다. 동일 명령을 정상 권한에서 실행해 3개 묶음 57개 시험을 모두 통과했다.

### 기존 실패 분리

`test_intake_dining_completion.py`의 아래 2개는 접수 review의 읽기 경로에서도 가짜 연결의 locked=True를 요구해 실패한다. 수정 전 agent·judge를 백업에서 메모리로 로드해 같은 두 시험을 실행했고 2/2 = 100% 동일 실패를 재현했다. 제품의 잠금 정책을 약화하거나 관계없는 시험을 이번 범위에 섞어 수정하지 않았다.

- `test_force_review_prepares_the_new_token_before_returning`
- `test_loading_an_old_cached_review_does_not_create_a_new_gate`

웹 기존 오류는 IntakeDiningJudge·Review.dining_judge·blocks_registration 선언 누락과 기존 dietary·kids·payment·business 행 타입 누락이다. 이번에는 새 dining_check 타입만 추가했다. 타입 검사·전체 빌드 통과로 보고하지 않는다.

## 화면 확인 범위

실제 `Checks` React 부품과 현재 CSS를 브라우저에서 390px·900px 너비로 렌더링했다. 기존 영업 ok와 별도 누락 unknown 안내가 함께 보이는 것을 이미지로 확인했다. 전체 접수 페이지·실서버·실제 고객 흐름 시험은 하지 않았다.

- [휴대폰 크기 캡처](../../../../_backup/2026-10-23_dining-required-checks/component-preview-mobile.png)
- [데스크톱 크기 캡처](../../../../_backup/2026-10-23_dining-required-checks/component-preview-desktop.png)
- 동일 폴더 `component-preview.html`은 부품 확인용 파일이며 제품 화면·배포물이 아니다.

## 보존·인계

수정 전 사본: 루트 `_backup/2026-10-23_dining-required-checks/manifest.json`에 8개 파일을 기록했다. 기존 미커밋 작업을 보존하고 현재 role-dining에서 수정했다. 새 파일은 completion.py·Python 회귀 시험·웹 회귀 시험·계획 및 이 보고서다.

로컬 구현만 반영했다. 커밋·푸시·배포는 하지 않았다. 다음 단계는 2번, 같은 판정 실행의 동일 조회 결과 재사용이다. 기존 잠금 시험 2건·웹 타입 오류 15건은 별도 정합성 작업으로 남는다.
