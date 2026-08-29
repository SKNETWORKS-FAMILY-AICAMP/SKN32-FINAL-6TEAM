# S-DECLARATIVE-TEAM-RUNTIME 리포트 (스트림 A)

실행일: 2026-08-28. 계획서: `docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md`.

## ★Codex 가 아니라 Claude 가 직접 구현했다

이 스트림은 원래 Codex 에 발주했으나 **워크스페이스 쓰기 권한 거부**로 한
글자도 쓰지 못했다. 재현과 진단은 다음과 같다.

- `codex exec -s workspace-write` 로 두 스트림(A·B)을 발주 → 둘 다 exit 0
  이지만 변경된 코드 파일 0개. 로그에 `Failed to write file`,
  `denied:acop_basement:...\.write_probe 경로에 대한 액세스가 거부되었습니다`.
- Claude 프로세스는 같은 경로에 정상적으로 쓸 수 있었다(직접 확인).
  즉 워크스페이스 권한이 아니라 **Codex 프로세스만** 막힌 것이다.
- `~/.codex/config.toml` 에 `[windows] sandbox = "elevated"` 가 있고
  `~/.codex/.sandbox/` 가 2026-08-28 09:27 에 수정돼 있었다. 세션 초반
  (2026-08-19)에는 같은 명령으로 Codex 가 정상적으로 파일을 썼다.
- 최소 프로브(`docs/reports/.codex_probe.md` 한 줄 쓰기)로 재현 확인.
  `-c windows.sandbox=unelevated` 로 바꿔도 동일하게 거부됐다
  (`none` 은 유효하지 않은 값 — `elevated`/`unelevated` 둘뿐이다).

남은 우회는 `-s danger-full-access`(머신 전체 접근) 뿐이라 **쓰지 않았다.**
사용자 승인 없이 다른 에이전트에게 워크스페이스 밖 전체 접근을 주는 것은
이 작업에 필요한 범위를 넘는다. 그래서 Claude 가 직접 구현했다.

## 만든 것

| 파일 | 내용 |
|---|---|
| `acop_basement/teams/__init__.py` | 신규 패키지 |
| `acop_basement/teams/declarative.py` | `DeclarativeTeamRuntime` |
| `acop_basement/core/project_config.py` | `TeamConfig.parameters`, `DeclarativeTeamParameters`, grant ceiling |
| `app/composition.py` | `_instantiate_team` 이 선언 파라미터를 주입 |
| `tests/unit/teams/test_declarative_team.py` | 9건 |
| `tests/integration/test_declarative_team_composition.py` | 3건 |

## grant ceiling 을 접두사 규칙으로 표현한 이유

계약이 "실제 tool 이름 목록을 확인해서 채우되, 도메인 어휘가 섞이면 접두사
규칙을 쓰라"고 했다. **접두사 규칙(`read.`)을 골랐다.**

근거: 실제 등록되는 tool 이름은 `read.subscription`·`read.payment_history`·
`read.entitlement` 처럼 **도메인 어휘를 그대로 담고 있다**
(`app/modules/customer_ops/read_tools.py` 의 `build_read_tool_functions()`).
이 목록을 `acop_basement` 상수로 하드코딩하면 basement 에 도메인이 새고,
`tests/architecture/test_basement_is_domain_free.py` 가 잡는다. 접두사
규칙은 도메인을 모른 채 "읽기 전용"이라는 성질만 강제한다.

검증은 **로드 시점**이다(`DeclarativeTeamParameters._enforce_grant_ceiling`).
런타임으로 미루면 "저장은 됐는데 언젠가 터지는" 상태가 남는다.

★왜 필요한가: `composer:write` 를 가진 사람이 `allowed_tools` 를 마음대로
넓힐 수 있으면 그것이 곧 도구 권한을 스스로 부여하는 권한 상승이다. 선언
(프롬프트)은 신뢰 경계 밖의 입력으로 다뤄야 한다. 같은 이유로 선언형 Team 은
1차에서 `ActionProposal` 을 만들지 않는다 — 조회·정리·초안까지다.

## `_instantiate_team` 을 확장한 방식과 기존 경로 보존

기존 함수는 생성자 인자 개수를 보고 `()`·`(tools)`·`(tools, llm)` 셋 중
하나로 조립했다. 선언형은 `parameters` 가 있어야 manifest 를 만들 수 있어서
이 추론만으로는 조립되지 않는다(인자가 4개라 `(tools, llm)` 경로를 타고
`parameters=None` 으로 `ValueError`).

**선언에 `parameters` 가 있을 때만** 별도 경로를 타게 했다. 기존 세 경로는
코드를 그대로 뒀다 — 기존 Team 과 테스트용 소형 구현이 계속 같은 방식으로
조립돼야 하기 때문이다. 판별은 `TeamConfig.declarative_parameters()` 가 하고,
선언형이 아니면 `None` 을 돌려주므로 기존 흐름이 그대로 이어진다.

## ★검수 중 발견해 고친 실제 결함 1건

`_validate_active_team_implementations()` 가 활성 Team 의 **클래스**에
`manifest` 속성이 있는지 검사한다. 코드형 Team 은 클래스 속성으로 갖지만,
선언형 실행기는 인스턴스마다 선언에서 manifest 를 만들기 때문에 클래스에는
없다 — 그래서 선언형 Team 이 든 선언은 **로드 자체가 실패**했다
(`does not satisfy TeamModule: missing manifest`).

선언형 ref 에 한해 `execute` 만 요구하도록 고쳤다. 근거: 그 선언의 내용은
`TeamConfig` 가 이미 검증했다. 여기서 `manifest` 까지 요구하면 "클래스에 빈
manifest 를 달아 검사만 통과시키는" 무의미한 회피를 부른다 — 이 저장소가
이미 한 번 겪은 유형이다(`KNOWN_IMPLEMENTATION_REFS` 의 문자열 조각 우회,
2026-08-18 버그사냥).

테스트 픽스처 쪽 오류도 2건 있었다(`ContextPack.current_state.customer_id`
누락, `registry.entries()` 라는 없는 API). 둘 다 코드가 아니라 내가 쓴
테스트의 문제였고, 첫 번째는 **실행기가 실패를 조용히 삼키지 않고 warning
으로 보고해서** 원인이 바로 드러났다.

## 검증

```powershell
python -m pytest tests/unit/teams/test_declarative_team.py -q          # 9 passed
python -m pytest tests/integration/test_declarative_team_composition.py -q  # 3 passed
python -m pytest tests/architecture -q                                  # 74 passed
python -m pytest -q --ignore=tests/integration/rag                   # 371 passed
```

계획서 §4 완료 기준 대조:

| 기준 | 결과 |
|---|---|
| basement 순수성 유지 | 통과 (74 passed — 신규 `acop_basement/teams/**` 포함해 증가) |
| 기존 `config/project.yaml` 이 그대로 로드 | 통과 (`test_existing_repository_declaration_still_loads`) |
| ★선언형 2개를 다른 capability 로 선언하면 둘 다 조립 | **통과** — 같은 `implementation_ref` 를 두 번 쓰는데도 조립된다 |
| 읽기 전용 밖 tool → 로드 실패 | 통과 (모델 검증·파일 로드 양쪽) |
| 코드형 Team 에 parameters → 거부 | 통과 |

중복 capability 는 선언형이어도 여전히 거부된다
(`test_duplicate_capability_across_declarative_instances_is_still_rejected`) —
인스턴스 복제가 된다고 해서 라우팅 모호성까지 허용한 것은 아니다.

## 남은 것

- 스트림 B(`GET /composer/catalog`, `POST /composer/changes`)는 같은 Codex
  권한 문제로 아직 미착수다.
- 두 스트림이 다 끝나면 통합 테스트(선언형 Team 을 `/composer/changes` 로
  만들어 로더 통과 확인)를 붙인다 — 계획서 §3.
