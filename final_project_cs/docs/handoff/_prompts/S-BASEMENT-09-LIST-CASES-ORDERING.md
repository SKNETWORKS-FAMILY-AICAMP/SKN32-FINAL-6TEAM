# S-BASEMENT-09-LIST-CASES-ORDERING — `list_cases` 동률 정렬 비결정성 수정

## 0. 배경

`final_project_sample/acop_basement/infrastructure/db/repository.py`
(참고용, **절대 수정 금지**)와 `app/infrastructure/db/repository.py`
대조에서 발견됨. sample은 이미 이 버그를 고쳤다:

```python
# ★버그사냥 2026-08-17 — created_at 만으로 정렬하면 동률(같은 timestamptz)일 때
#   순서가 안정적이지 않다. case_id 를 2차 정렬키로 더해 결정적으로 만든다.
query += " ORDER BY created_at DESC, case_id DESC LIMIT %s"; params.append(limit)
```

cs의 `list_cases()`(`app/infrastructure/db/repository.py` line 30)는
여전히:

```python
query += " ORDER BY created_at DESC LIMIT %s"; params.append(limit)
```

PostgreSQL은 동일한 정렬키를 가진 행들의 상대 순서를 보장하지 않는다.
같은 배치로 seed된 Case들, 또는 짧은 시간 안에 연속 생성된 Case들처럼
`created_at`이 같은 timestamptz 값을 가지는 행이 둘 이상이면, 반복
호출마다 `list_cases()`가 그 동률 행들을 다른 상대 순서로 돌려줄 수
있다 — UI 목록/페이지네이션이 흔들리거나 "가장 최근 Case" 판정이
호출마다 달라질 수 있다.

## 1. 할 일

`app/infrastructure/db/repository.py`의 `list_cases()` 함수에서
`ORDER BY created_at DESC LIMIT %s`를 `ORDER BY created_at DESC,
case_id DESC LIMIT %s`로 고쳐라 — `case_id`를 2차 정렬키로 추가해
동률을 결정적으로 깨라. 이 파일의 다른 함수(`get_case`,
`get_case_events` 등)는 건드리지 마라 — 이미 결정적 정렬 키를 쓰고
있거나 단일 행만 반환한다.

## 2. 검증

- 재현 테스트를 추가해라(`tests/integration/db/test_db_integration.py`
  옆이 적합해 보인다 — 기존 파일 구조를 보고 맞는 위치를 골라라):
  같은 tenant에 `created_at`이 동일한(같은 timestamptz로 강제 삽입한)
  Case를 2개 이상 만든 뒤, `list_cases()`를 여러 번 호출해서 매번
  **같은 순서**로 나오는지 확인해라. 수정 전 코드로는 이 테스트가
  비결정적으로 실패할 수 있다는 걸 확인(또는 최소한 순서 보장이 코드
  상 없다는 것을 논리적으로 확인)한 뒤, 수정 후에는 항상 통과하는지
  봐라.
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (378 passed 기준 변화 명시).

## 3. 쓰기 대상

- `app/infrastructure/db/repository.py`
- 관련 테스트 파일(신규 또는 기존 파일에 추가)
- `docs/reports/2026-08-24_S-BASEMENT-09-LIST-CASES-ORDERING_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `repository.py`의 `list_cases()` 외 다른 함수 수정 금지
