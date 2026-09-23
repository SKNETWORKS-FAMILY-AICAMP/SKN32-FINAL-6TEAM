# 구현 지시 — composition root 조립 (운영 진입점이 비어 있다)

## 0. 결함 (Basement 재검사 2차)

`wiki/records/reports/2026-08-13_Basement_구조검사_v2.md`:

> ★**가장 먼저 부러질 곳: 실제 운영 진입점의 조립이다.**
> API app 에는 classifier 만 연결되어 있고
> **Controller, Registry, Team executor, Team dependency 가** (조립돼 있지 않다)

그리고 Core Runtime 축:
> `app/application/controller.py:14-19` 에서 **infrastructure 를 참조**

★**구조는 열렸는데 운영 경로가 살아 있지 않다.**
`_capability()` 를 Registry 조회로 열었고 `TeamExecutorPort` 도 만들었지만,
`create_app()` 이 그것들을 조립하지 않아 **REST 요청이 Controller 를 타지 않는다.**

이 프로젝트에서 같은 종류를 여러 번 겪었다 — **"코드가 있다" 와 "그 경로가 실제로 돈다" 는 다르다.**

## 1. 소유 범위

```
app/composition.py              ← 신설 (composition root)
app/presentation/api/app.py     ← 조립 호출
app/application/controller.py   ← infrastructure 참조 정리 (최소 변경)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/contracts.py`, `app/domain/**`, `app/modules/**`(읽기만),
`eval/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 2. 만들 것

### 2-1. `app/composition.py` — 조립 지점 하나

여기서만 구체 구현을 알고, 나머지는 Port/Protocol 로 받는다.

```python
def build_registry() -> TeamRegistry: ...        # 두 Team 을 등록해 반환
def build_team_executor(registry) -> TeamExecutorPort: ...   # LocalTeamExecutor
def build_controller(...) -> Controller: ...     # registry + executor + broker 주입
def build_classifier(): ...                      # 이미 app.py 에 있는 것을 옮긴다
```

- ★Team 인스턴스 생성(`BillingSubscriptionTeam(tools, llm)`)은 **여기서만** 한다
- ★`app/core/**` 는 이 파일을 import 하지 않는다 (격리 유지)
- LLM·DB 연결 등 구체 어댑터도 여기서 조립한다

### 2-2. `create_app()` 이 조립을 쓴다

`app/presentation/api/app.py` 의 `create_app()` 이
`composition.build_controller(...)` 를 호출해 Controller 를 만들고,
**REST 경로가 실제로 그 Controller 를 타게** 한다.

- ★**주입 가능성 유지**: `create_app(controller=..., classifier=...)` 로
  테스트가 fake 를 넣을 수 있어야 한다. 기존 테스트가 깨지면 안 된다
- ★API 키가 없으면 예외를 던진다 (지금 동작 유지). 조용한 폴백 금지

### 2-3. `controller.py` 의 infrastructure 참조 정리

`app/application/controller.py:14-19` 가 `app/infrastructure/**` 를 직접 import 한다.
필요한 것은 **생성자로 주입**받게 바꾼다 (retriever, repository 등).
★어디까지 가능한지 판단해서 옮기고, **못 옮긴 것과 사유를 리포트에 적어라.**

## 3. 테스트

1. ★**REST 로 Case 를 만들면 Controller 가 실제로 호출된다**
   — `POST /v1/cases` 후 Controller 가 관여했음을 관측 (routing 진행·`agent_runs` 행 등)
2. `create_app()` 이 fake controller 주입을 받아들인다 (기존 테스트 유지)
3. ★`composition.build_registry()` 가 두 Team 을 등록하고,
   **새 Team 을 하나 더 등록하면 그것도 라우팅된다**
4. `app/core/**` 가 `app.composition` 을 import 하지 않는다 (격리 테스트에 추가)

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지 (fake 주입).
테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **126건 이상, 0 failed, skipped 0** (live 는 deselected).

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 5. 리포트

`wiki/records/reports/2026-08-13_S-COMPOSITION_리포트.md` — 조립한 것 목록,
`controller.py` 에서 옮긴 참조와 **못 옮긴 것의 사유**, §3 테스트 결과 원문.

## 6. 하지 말 것
- ❌ `app/core/**` 가 `app.composition` 을 import
- ❌ 주입 가능성 제거 (fake 주입이 계속 돼야 한다)
- ❌ 조용한 폴백 (키 없으면 예외)
- ❌ 기존 테스트 단언 약화
- ❌ `eval/**` 열기
- ❌ 돌려보지 않고 "완료"
