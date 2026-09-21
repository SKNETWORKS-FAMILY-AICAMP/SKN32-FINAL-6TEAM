# DoD-02 — Case 상태가 상태표와 transition 규약으로만 변경된다

- v5 §20 항목 2 / 검증 방법: transition integration test
- 실행: 2026-08-12 22:50 · 커밋 `cbb75e6`
- 판정: **통과**

## ★2026-09-06 갱신 — 판정은 유효하고, 낡은 이름·수치·경로만 현행으로 고쳤다


| 낡았던 것 | 지금 (실측 2026-09-06) |
|---|---|
| `transition_case()` 사용 **7회** | **12회** — `controller.py` 7 · `api/cases.py` 4 · `classification.py` 1 |
| 재현 출력 `107 passed` | 아래 「실제 출력」 참조. 명령이 둘인데 출력이 하나뿐이라 어느 것인지 모호했다 |

★**대조 기록은 이 수치를 「14회」라 했는데 12회다.** `grep` 줄 수(15)에는
정의부·주석이 섞이고, 14 는 그중 일부만 뺀 값이다. AST 로 **호출 노드만**
세어 12 를 얻었다. 남이 센 숫자를 그대로 옮기지 않는다.

★**호출이 는 것은 규약이 느슨해진 것이 아니다.** 이 DoD 가 요구하는 것은
"호출이 적은 것"이 아니라 **"상태를 바꾸는 문이 이것 하나인 것"**이다.
우회 경로를 다시 검사했고 여전히 **0건**이다.

```
UPDATE customer_cases | DELETE FROM case_events | UPDATE case_events
  → app/ 전체에서 transition.py 밖 0건
상태 12개 (tests/contract/test_case_state_table.py 가 v5 §5-1 과 1:1 대조)
전이표 25 전이 / 이벤트 20종
```


## 재현

```powershell
python -m pytest tests/contract/test_case_state_table.py tests/integration/controller -q
python -m pytest tests -q
```

## 실제 출력

```
107 passed in 25.14s      (skipped 0, failed 0)
```

## 근거 1 — 전이표가 v5 §5-1 과 1:1 대조된다

`tests/contract/test_case_state_table.py` 는 v5 §5-1 "허용 다음 상태" 열을
**계획서를 보고 손으로 옮긴 상수**(`V5_ALLOWED_NEXT`)와 코드 전이표를 12개 상태 전부 대조한다.
코드에서 값을 가져오지 않으므로 대조가 성립한다.

추가로 검사하는 것: 상태 12개 · `cancelled` 종결성 · 모든 이벤트에 payload schema 존재 ·
전이표에 쓰이지 않는 이벤트 없음 · **분류 실패는 escalated** · **TTL 만료는 escalated** ·
**승인 거절은 resuming 으로 가지 않음**.

## 근거 2 — 우회 경로가 없다 (정적 검사)

```
Select-String -Pattern "UPDATE\s+customer_cases|DELETE\s+FROM\s+case_events|UPDATE\s+case_events"
  app/application/*.py, app/infrastructure/messaging/*.py, app/core/registry.py, app/infrastructure/db/**
→ 0건
```

`transition_case()` 사용 7회. 상태 변경 경로가 이 함수 하나뿐이다.

## 근거 3 — ★상태기계가 실제로 잘못된 전이를 막았다

2026-08-12, Controller 가 승인 후 `resuming` 에서 곧장 `completed` 를 적용하려 했고
**런타임에 거부**됐다:

```
InvalidTransition: 허용되지 않은 전이: resuming --completed--> ?
  (이 상태에서 가능한 이벤트: ['resumed', 'resume_failed'])
```

★직접 `UPDATE` 하는 구현이었다면 `resolved` 로 조용히 넘어가고 이벤트 이력이 깨진 채
통과했을 것이다. 이 규약이 **장식이 아니라 실제로 막는다**는 관측 근거다.
→ `wiki/records/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md`

수정 후 관측된 전이 순서:

```
시나리오1: classifying(1) → routing(2) → running(3) → waiting_approval(4)
           → resuming(5) → running(6) → resolved(7)
시나리오2: classifying(1) → routing(2) → running(3) → resolved(4)
```

수정 범위는 `app/application/controller.py` **단일 파일**이고,
`app/domain/events.py`(전이표)와 테스트 단언은 **변경 0건**이다 —
전이표를 늘려 통과시키는 우회를 하지 않았음을 `git diff` 로 확인했다.
