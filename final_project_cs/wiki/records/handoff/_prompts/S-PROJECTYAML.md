# 구현 지시 — `config/project.yaml` 을 조립의 단일 입력으로 (Composer 선행 작업)

## 0. 목적

지금 `app/composition.py` 는 Team 두 개를 **하드코딩 import** 한다:
```python
from app.modules.customer_ops import BillingSubscriptionTeam, TechnicalEntitlementTeam
```

★**선언 파일을 만들어도 그것이 실제 조립을 지배하지 못한다.**
이 상태에서 GUI 를 붙이면 **화면에서 바꿔도 배포에 반영되지 않는 껍데기**가 된다.

이번 작업은 GUI 가 아니라 **그 밑바닥**이다: 선언이 조립의 **단일 입력**이 되게 한다.

## 1. 계약

★**`wiki/records/handoff/08_모듈_컴포넌트_목록.md` 를 먼저 읽어라. 그것이 이 작업의 계약이다.**
- §1 컴포넌트(선택 불가) / §2 모듈(선택 가능) / §3 Port / §4 인스턴스
- §6 에 선언 초안과 **빌드 시 실패시켜야 할 4가지**가 있다

참고: `wiki/records/reports/2026-08-14_모듈구성기_설계검토.md` (권고안 근거)

현재 기준선: **130 passed, 0 failed, skipped 0**. 이걸 깨면 실패다.

## 2. 소유 범위

```
config/project.yaml           ← 신설
app/composition.py            ← 선언을 읽어 조립
app/core/project_config.py    ← 신설: 선언 로드·검증 (Core 격리 유지)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/contracts.py`, `app/domain/**`, `app/modules/**`,
`app/presentation/**`, `app/infrastructure/**`, `eval/**`, `knowledge/**`,
`config/guardrails.yaml`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 3. 만들 것

### 3-1. `config/project.yaml` — `08` §6 초안대로

```yaml
modules:
  vector_rag:    { enabled: true }
  graph_store:   { enabled: true }
  a2a_executor:  { enabled: false }
  mcp:           { enabled: true }
  voc:           { enabled: true }
  ops_ui:        { enabled: true }
  composer_ui:   { enabled: false }
ports:
  team_executor:  local        # local | a2a
  message_broker: outbox       # outbox | redis_streams(Phase 2, 미구현)
  graph_store:    sql          # sql | age | neo4j(Phase 2, 미구현)
teams:
  - { team_id: billing_subscription,  active: true,
      implementation_ref: "app.modules.customer_ops:BillingSubscriptionTeam" }
  - { team_id: technical_entitlement, active: true,
      implementation_ref: "app.modules.customer_ops:TechnicalEntitlementTeam" }
```

★**현재 동작과 같은 구성**으로 시작한다. 이번 작업에서 기능이 바뀌면 안 된다.

### 3-2. `app/core/project_config.py` — 로드 + 검증

- 선언을 읽어 타입이 있는 객체로 준다 (`app.core.settings` 방식 참고)
- ★**Core 격리 유지**: `app.modules`·`app.presentation`·`app.infrastructure` 를
  **import 하지 마라**. `implementation_ref` 는 **문자열로 들고만 있고**,
  실제 import 는 `composition.py` 가 한다
  (`tests/contract/test_core_isolation.py` 가 검사한다)
- ★파일이 없거나 스키마가 틀리면 **명시적 예외**. 기본값으로 조용히 넘어가지 마라(`RULE.md` §3.2)

### 3-3. ★검증기 — 빌드 시 실패시킬 4가지 (`08` §6)

1. `enabled: true` 인데 **구현이 없다**
2. `active: true` 인데 `implementation_ref` 가 **import 되지 않는다**
3. **중복 `team_id`**, 또는 같은 capability 를 두 Team 이 주장
4. **꺼진 모듈을 부르는 경로가 남아 있다**
   (최소한 "꺼진 Port 를 조립하려 하면 실패" 까지)

★검증 실패는 **기동 시점에 명확한 메시지**로 죽어야 한다. 무엇이 왜 틀렸는지 담아라.

### 3-4. `composition.py` 가 선언을 읽는다

- `build_registry()` 가 `teams` 선언을 순회하며 `implementation_ref` 로 **동적 import** 해 등록
- ★`active: false` 인 Team 은 **등록하되 라우팅되지 않게** 한다
  (`TeamManifest.active` 를 그대로 쓴다). 미구현 Team 이 Case 를 죽이면 안 된다
- `ports.team_executor` 가 `local`/`a2a` 를 고른다
- 꺼진 모듈(`enabled: false`)의 어댑터는 **조립하지 않는다**
- ★**주입 가능성 유지**: 기존 `build_*(...)` 시그니처의 인자 주입이 계속 동작해야 한다
  (테스트가 fake 를 넣는다)

## 4. 테스트

1. ★**선언을 바꾸면 조립이 바뀐다** — 임시 선언으로 Team 하나만 active 로 두면
   Registry 에 그 하나만 라우팅 대상이 된다
2. ★`active: false` Team 은 등록되지만 **라우팅되지 않는다**
3. ★검증 실패 4종이 **각각 명확한 예외**를 던진다
   (없는 `implementation_ref`, 중복 `team_id`, 꺼진 Port 조립 시도, 미지원 Port 값)
4. `graph_store: {enabled: false}` 면 GraphStore 어댑터가 조립되지 않는다
5. 기존 130건이 그대로 통과한다 (기본 선언 = 현재 동작)
6. `app/core/**` 가 `app.modules` 를 import 하지 않는다 (기존 격리 테스트 유지)

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지(fake 주입).
테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 5. 완료 조건

```powershell
python -m pytest tests -q
python -c "import sys;sys.path.insert(0,'.');from app.composition import build_registry;r=build_registry();print('registered:',sorted(m.team_id for m in r.manifests()))"
```
기대: **130건 이상, 0 failed, skipped 0**, Registry 에 두 Team.
(`manifests()` 가 없으면 Registry 의 실제 조회 API 를 쓰라)

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 6. 리포트

`wiki/records/reports/2026-08-14_S-PROJECTYAML_리포트.md` — 선언 스키마,
`composition.py` 변경 전후, 검증 4종이 각각 어떤 메시지로 죽는지, §5 출력 원문.

## 7. 하지 말 것
- ❌ 이번 작업에서 **기능 변경** (기본 선언 = 현재 동작)
- ❌ `app/core/` 가 `app.modules` 를 import (동적 import 는 composition 몫)
- ❌ 선언 부재·스키마 오류를 기본값으로 폴백
- ❌ `active:false` Team 이 라우팅되게 두기
- ❌ 주입 가능성 제거
- ❌ 소유 범위 밖 수정
- ❌ 돌려보지 않고 "완료"
