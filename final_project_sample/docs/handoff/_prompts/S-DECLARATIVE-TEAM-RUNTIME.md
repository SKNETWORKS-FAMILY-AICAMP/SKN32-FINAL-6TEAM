# S-DECLARATIVE-TEAM-RUNTIME — 선언형 Team 범용 실행기 (스트림 A)

## 배경

계획서는 `docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md`다. 이 계약은
그 계획서 §2·§3의 스트림 A를 구현 지시로 옮긴 것이다. 계획서와 어긋나면
계획서가 정본이다.

지금은 새 Agent Team을 하나 추가하려면 Python 코드를 새로 써서 배포해야
한다. 이 스트림은 **범용 실행기를 한 번 만들어서, 이후로는 선언(데이터)만으로
새 Team을 만들 수 있게** 한다.

★핵심 제약: `acop_basement`는 도메인을 몰라야 한다
(`docs/handoff/10_도메인_교체_가이드.md` §0,
`tests/architecture/test_basement_is_domain_free.py`가 강제). 선언형 실행기는
"프롬프트와 도구 목록을 받아 실행한다"는 **메커니즘**만 갖고, 어떤 도메인
어휘(order·refund·subscription 등)도 코드에 넣지 않는다.

## 만들 것

### 1. `TeamConfig.parameters` 필드 추가

`acop_basement/core/project_config.py`의 `TeamConfig`에 계획서 §2.1 그대로
`parameters: dict[str, Any] | None = None`을 추가한다.

★**하위호환이 양보 불가 조건이다.** 기존 `config/project.yaml`은
`parameters` 없이 그대로 로드돼야 한다. 이걸 검증하는 테스트를 반드시
넣어라.

### 2. 선언형 파라미터 검증 모델

같은 파일 또는 `acop_basement/teams/` 아래에 선언형 Team의 `parameters`를
검증하는 Pydantic 모델을 만든다. 필드는 계획서 §2.2 그대로다
(`display_name`, `capabilities`, `accepted_case_types`, `required_context`,
`allowed_tools`, `knowledge_scope`, `max_steps`, `prompt_key`).
`extra="forbid"`를 쓴다.

`implementation_ref`가 선언형 실행기를 가리킬 때만 이 검증을 적용한다.
코드형 Team의 `parameters`는 `None`이어야 하고, 값이 들어 있으면 거부해라
(조용히 무시하지 마라 — 무시하면 사용자는 설정이 먹은 줄 안다).

### 3. ★grant ceiling (보안, 양보 불가)

계획서 §2.3을 그대로 구현한다.

`acop_basement`에 읽기 전용 tool 이름의 allowlist 상수를 둔다. 선언형
Team의 `allowed_tools`가 그 집합의 부분집합이 아니면 **`load_project_config`
단계에서 `ProjectConfigError`로 거부**한다. 런타임 검사로 미루지 마라.

상수에 넣을 이름은 이 저장소에 실제로 존재하는 읽기 tool 이름을 코드에서
확인해서 채워라(`acop_basement/tools/read_tools.py`와
`app/modules/customer_ops/read_tools.py`의 `build_read_tool_functions()`가
실제로 등록하는 이름들). 도메인 어휘가 tool 이름에 섞여 있다면, 그 목록을
basement 상수로 하드코딩하지 말고 **"read." 로 시작하는 것만 허용" 같은
접두사 규칙**으로 표현해서 basement 순수성 검사를 통과시켜라. 어느 쪽을
골랐는지 리포트에 근거와 함께 적어라.

★왜 필요한가: `composer:write` 권한을 가진 사람이 `allowed_tools`를 임의로
넓힐 수 있으면, 그게 사실상 "도구 권한을 스스로 부여하는" 권한 상승이
된다. 프롬프트 인젝션이 곧 데이터 유출로 이어질 수 있다.

### 4. `DeclarativeTeamRuntime`

`acop_basement/teams/declarative.py`(신규 디렉터리·파일). `TeamModule`
Protocol을 만족해야 한다 — `manifest` 속성과 `async execute(task)` 메서드
(`acop_basement/core/contracts.py`의 `TeamModule`·`TeamManifest`·
`TeamTask`·`TeamResult`를 실제로 읽고 맞춰라).

- 생성자에서 선언 파라미터를 받아 `TeamManifest`를 만든다.
  `contract_name`·`supported_contract_versions`·`implementation_revision`
  같이 선언에 없는 필수 필드는 실행기가 채운다.
- `execute()`는 `allowed_tools` 안의 tool만 호출하고, 결과를 evidence로
  묶어 `TeamResult`를 만든다. LLM이 주입돼 있으면 `prompt_key`로 초안을
  만들고, 없으면 결정론 경로로 동작해야 한다(테스트가 실 LLM 없이 돌아야
  한다).
- ★**1차에서는 `ActionProposal`을 만들지 않는다**(계획서 §2.3). 조회·분류·
  초안까지다. `next_action`은 `respond` 또는 `escalate` 계열만 쓴다 —
  실제 enum 값은 `contracts.py`에서 확인해라.
- 근거를 못 찾으면 지어내지 말고 escalate 한다(`CLAUDE.md` §0.1).

### 5. composition이 파라미터를 주입하게 한다

`app/composition.py`의 `_instantiate_team()`은 지금 생성자 인자 개수만 보고
`(tools)` 또는 `(tools, llm)`을 넘긴다. 선언형 실행기는 파라미터도 받아야
한다.

기존 두 경로(인자 없음 / tools / tools+llm)의 동작을 **깨지 않으면서**
파라미터를 넘길 방법을 골라라. 판단 근거를 리포트에 적어라. 기존 Team
구현들과 테스트용 소형 구현들이 지금처럼 계속 조립돼야 한다.

## 검증

계획서 §4의 완료 기준을 전부 테스트로 증명해라. 특히:

- 기존 `config/project.yaml`(parameters 없음)이 그대로 로드된다.
- ★선언형 Team **2개를 서로 다른 capability로** 선언하면 둘 다 조립된다.
  같은 `implementation_ref`를 두 번 쓰는데도 capability 충돌이 안 난다는
  게 이 스트림의 핵심 증명이다(`app/composition.py`의 duplicate capability
  검사를 실제로 통과해야 한다).
- `allowed_tools`에 읽기 전용 밖의 이름을 넣으면 **로드가 실패**한다.
- 코드형 Team에 `parameters`를 넣으면 거부된다.

```powershell
python -m pytest tests/architecture -q
python -m pytest -q --ignore=tests/integration/rag
```

## 하지 말 것

- `acop_composer/**`를 건드리지 마라 — 스트림 B가 동시에 작업 중이다.
- `config/project.yaml`(저장소 루트, 개발 서버가 쓰는 파일)을 바꾸지 마라.
  선언형 Team 예시는 테스트 안의 임시 파일로만 만들어라.
- 선언형 Team이 side effect(`ActionProposal`)를 만들게 하지 마라.
- 도메인 어휘를 `acop_basement/**`에 넣지 마라.

## 만들 것 (리포트)

`docs/reports/2026-08-28_S-DECLARATIVE-TEAM-RUNTIME_리포트.md` — 만든/고친
파일, grant ceiling을 어떤 방식으로 표현했는지와 그 근거, `_instantiate_team`
확장 방식과 기존 경로를 어떻게 보존했는지, 테스트 결과.
