# Codex — 배선(wiring) 수정: 분류기가 API 에 연결돼 있지 않다

## 0. 결함

`POST /v1/cases` 가 **항상 분류 실패**한다. 실측:

```
status= 201
body= {"status":"escalated","version":2,"intent":null,"issue_code":null,"sentiment":null}
customer_cases= (None, None, None)
events= [('created',...), ('classification_failed', {'failure_code':'classification_failed'})]
```

원인: `app/modules/customer_ops/feedback.py:classify()` 는 구현돼 있고 단위 테스트 7건이 통과하는데,
**`create_app()` 이 그것을 주입하지 않는다.** 그래서 API 경로에서는 분류기가 항상 `None` 이다.

★S-API 는 주입 지점을 만들었고 S-VOC 는 함수를 만들었다. **둘을 잇는 일을 아무에게도 주지 않은
것이 원인**이다. 양쪽 다 잘못하지 않았다.

v5 §20 **DoD 9** 가 이걸로 막혀 있다.
→ `wiki/records/evidence/DoD-09_인라인분류_전건실행.md`

## 1. 소유 범위

```
app/presentation/api/app.py       ← 분류기 주입 (composition root)
app/presentation/api/cases.py     ← 필요하면 (주입 시그니처 확인용)
tests/integration/api/**
wiki/records/reports/ , wiki/records/history/
```

★그 밖 **전부 금지**. 특히:
- `app/modules/customer_ops/feedback.py` — **고치지 마라.** 이미 통과했다
- `app/core/**`, `app/domain/**`, `eval/**` — ★`eval/` 은 **지금 다른 세션이 실행 중**이다. 절대 열지 마라
- `knowledge/**`, `wiki/records/evidence/**`

## 2. 할 일

1. `create_app()` 의 기본 `classifier` 를 `app.modules.customer_ops.feedback` 의 분류기로 연결한다
   - ★**주입 가능성은 유지**한다. 테스트가 fake 를 넣을 수 있어야 한다
     (`create_app(classifier=fake)` 가 계속 동작해야 한다)
   - ★설정은 `app.core.settings.get_settings()` 로만 읽는다. `os.getenv` 금지
   - ★API 키가 없으면 **예외를 던져라.** 조용히 분류를 건너뛰지 마라

2. **테스트 추가** (`tests/integration/api/`):
   - ★`POST /v1/cases` 후 `customer_cases.intent / issue_code / sentiment` 가 **전부 채워짐**
   - 상태가 `classifying` 을 거쳐 진행됨 (`escalated` 가 아님)
   - `case_events` 에 `classified` 이벤트가 있음
   - ★분류기가 예외를 던지는 fake 를 주입하면 **여전히** `classification_failed` + `escalated`
     (실패 처리 규약이 깨지지 않았음을 지킨다)
   - ★실제 LLM 호출을 테스트에서 하지 마라 — fake 주입으로 결정적으로

3. 기존 테스트가 깨지면 **원인을 리포트에 적어라.** 단언을 약화시켜 통과시키지 마라

## 3. 완료 조건

```powershell
python -m pytest tests -q                 # ★기존 107건 + 신규. skipped 0, failed 0
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

그리고 **실제로 한 건 만들어 확인**하고 출력을 붙여라:

```powershell
python  # TestClient 로 POST /v1/cases (fake 분류기 주입) 후
        # customer_cases 의 intent/issue_code/sentiment 와 status 를 출력
```

기대: 세 값이 **채워지고** status 가 `escalated` 가 아니다. `tenants=1`.

## 4. 리포트

`wiki/records/reports/2026-08-12_S-WIRE_분류기연결_리포트.md` — §3 **실제 출력 원문**,
변경 파일, 추가한 테스트 목록. `wiki/records/history/2026-08-12_S-WIRE.md` 이력.

## 5. 하지 말 것
- ❌ `feedback.py` 수정
- ❌ `eval/` 열기 (다른 세션 실행 중)
- ❌ `os.getenv`
- ❌ 분류 실패를 조용히 넘기도록 바꾸기 (실패 규약은 유지한다)
- ❌ 테스트에서 실제 LLM 호출
- ❌ 기존 단언 약화
- ❌ 돌려보지 않고 "동작함"
