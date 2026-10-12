# 구현 지시 — P7 trace 화면 연결

## 0. 작업 대상

★**`C:\Users\playdata2\Documents\final_workspace\final_project_ui` 안에서만 작업한다.**
다른 폴더는 열지 마라. 이번 작업은 이 저장소 안의 파일만으로 끝난다.

## 1. ★먼저 읽을 파일 (이것만)

```
console/db.py
console/web.py
console/readers.py
tests/test_connections.py
tests/test_web.py
```

## 2. 왜 이걸 하나 — 만들어 놓고 안 쓴다

`console/db.py` 에 `read_trace(database_url, run_id)` 가 있다.
`agent_runs → team_tasks/llm_calls → case_events` 를 따라가는 함수다.

★**`web.py` 가 이걸 호출하지 않는다.** `read_trace` 검색 결과 0건이다.
"실행 이력" 표에 run 목록만 나오고, 그 run 하나를 눌러 따라가는 화면이 없다.

현재 **44 passed**.

## 3. 만들 것

### 3-1. `console/web.py` — `/run` 화면

```
/run?path=<프로젝트>&run_id=<uuid>
```

`read_trace()` 를 불러 단계별로 보여준다:

```
agent_runs   1행
team_tasks   N행
llm_calls    N행
case_events  N행
```

★각 단계에 **행이 없는 것**과 **읽지 못한 것**을 구분해서 보여준다.
`stage["error"]` 가 있으면 그 사실을 적는다. 빈 목록으로 뭉개지 마라.

### 3-2. "실행 이력" 표에서 각 run 을 클릭할 수 있게

지금 `read_agent_runs`(= `read_runs`) 로 만든 표의 각 행에
`/run?path=...&run_id=...` 링크를 단다.

### 3-3. ★대상이 없을 때도 화면이 죽지 않아야 한다

- `run_id` 가 없는 경로로 접근 → 안내 문구 ("run_id 가 없습니다" 류), 500 아님
- `database_url` 이 없음 → "연결 안 함"
- 그 run 이 없음(`read_trace` 가 `"그 실행이 없다"`) → 그대로 보여준다

## 4. ★지킬 것

| 규칙 | 이유 |
|---|---|
| **SELECT 만 한다** | `db.py` 는 이미 그렇다. 새로 쓰지 마라 |
| **없는 값을 0 으로 채우지 마라** | `모름`·`연결 안 함`·`읽지 못했다` |
| **대상 코드 복사 금지** | 이건 UI 만이다 |
| **항상 참인 단언 금지** | 실제로 실패시켜서 검사해라 |
| **주석 문구로 검사하지 마라** | import 줄·실제 동작만 본다 |

## 5. 완료 조건 — ★출력으로 증명하라

```powershell
cd C:\Users\playdata2\Documents\final_workspace\final_project_ui
python -m pytest tests -q
```
★기대: **44 → 늘어난다.** 늘어난 숫자를 리포트에 적어라.

★그리고 **실제 DB 로 확인하라** (이 저장소 밖 DB 접속이지만 파일은 안 건드린다):
```powershell
$env:PORT="8066"
$env:CONSOLE_DATABASE_URL="postgresql://postgres@127.0.0.1:5433/acop"
python -m console.web
```
`agent_runs` 가 비어 있을 수 있다 — 그래도 좋다. **"run 이 없다"** 가 정직하게 뜨는지,
`/run` 에 run_id 없이 접근했을 때 500 이 아니라 안내가 뜨는지 확인하고 원문을 붙여라.
확인 후 서버를 종료하라.

## 6. 리포트

`docs/reports/2026-08-17_P7_trace_연결.md`
— 테스트 증가 수, §5 출력 원문, 발견한 결함.

## 7. 하지 말 것
- ❌ 테스트 수가 그대로인 채 "완료"
- ❌ `db.py` 의 쿼리를 바꾸기 (이미 검증됐다 — 화면만 잇는다)
- ❌ 대상 DB 에 쓰기
- ❌ 다른 폴더 열기
- ❌ 띄워보지 않고 "완료"
