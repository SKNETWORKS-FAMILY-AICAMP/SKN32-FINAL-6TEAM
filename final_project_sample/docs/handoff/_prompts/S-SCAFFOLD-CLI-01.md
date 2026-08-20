# S-SCAFFOLD-CLI-01 — 예제 카탈로그 + 스캐폴딩 CLI (VISION-10 1층)

## 배경

`docs/vision/VISION-10_예제_카탈로그_스캐폴딩_CLI.md`의 1층(카탈로그+CLI)을
실행한다. 실행계획서는 `docs/plans/2026-08-19_예제_카탈로그_스캐폴딩_CLI_1층_계획.md`
다 — 이 계약은 그 계획서 §2~5를 그대로 구현 지시로 옮긴 것이다. 계획서와
이 파일이 어긋나면 계획서가 정본이다.

지금 `examples/customer_ops/`에 예시 Team 모듈이 2개 있다(`billing.py`,
`technical.py`) — Team 플러그인 구조가 실제 동작한다는 증거로 보존된
코드다. 이 예시들을 새 프로젝트를 시작할 때 골라서 복사 + `config/project.yaml`
초안까지 자동 생성해주는 CLI가 없다 — 전부 수작업이다. `acop_basement`는
이제 `pip install -e .`로 설치되는 패키지다(v0.3.0) — 이 CLI는 그 위에
얹는 순수 부가 도구이며, `acop_basement`/`acop_composer` 패키지 코드는
건드리지 않는다.

## 만들 것

1. **`examples/catalog.py`**(신규) — 카탈로그를 **선언**하는 모듈.
   `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS`가 채택한
   "명시 선언, 디렉터리 크롤링 아님" 원칙을 그대로 따른다.

   ```python
   from dataclasses import dataclass


   @dataclass(frozen=True)
   class ExampleEntry:
       example_id: str
       case_type: str
       summary: str
       module_path: str            # 저장소 루트 상대 경로, 예: "examples/customer_ops/billing.py"
       implementation_ref: str     # 예: "app.modules.customer_ops.billing:BillingSubscriptionTeam"
       required_modules: tuple[str, ...]
       required_ports: dict[str, str]
       knowledge_scope: str | None = None


   CATALOG: tuple[ExampleEntry, ...] = (
       ExampleEntry(
           example_id="billing_subscription",
           case_type="구독/결제",
           summary="...",  # examples/customer_ops/billing.py 를 실제로 읽고 채워라
           module_path="examples/customer_ops/billing.py",
           implementation_ref="app.modules.customer_ops.billing:BillingSubscriptionTeam",
           required_modules=(...),   # config/project.yaml 의 modules: 키와 맞춰라
           required_ports={...},     # config/project.yaml 의 ports: 키와 맞춰라
       ),
       # technical.py 도 같은 형식으로 등록
   )
   ```

   ★`required_modules`/`required_ports`/`implementation_ref` 값은 지어내지
   말고 `examples/customer_ops/billing.py`·`technical.py`·기존
   `config/project.yaml`의 `teams:` 항목·`app/modules/customer_ops/`의
   기존 등록 사례를 실제로 읽고 그대로 반영해라. 이 프로젝트는 근거 없는
   확정을 금지한다(`CLAUDE.md` §0.1과 동일한 원칙 — 카탈로그도 데이터다).

2. **`scripts/scaffold_project.py`**(신규) — `python -m
   scripts.scaffold_project <subcommand>`로 실행하는 CLI. `argparse` 사용.

   - `list` — `CATALOG`를 표로 출력(`example_id`·`case_type`·`summary`
     컬럼). 최소 폭 맞춤 정도만, 외부 라이브러리 의존 없이 표준 라이브러리로.
   - `show <example_id>` — 해당 항목의 전체 필드를 출력. 존재하지 않는
     `example_id`면 0이 아닌 종료 코드 + stderr 에러 메시지(카탈로그에
     없는 걸 조용히 통과시키지 않는다).
   - `new <example_id> --target <경로> [--team-id <id>]`:
     1. `example_id`가 카탈로그에 없으면 에러로 멈춘다.
     2. `<target>/config/project.yaml`이 **이미 존재하면 에러로 멈추고
        아무 파일도 쓰지 않는다.** 조용한 덮어쓰기 금지 — 이건 이
        저장소가 반복해서 강조하는 원칙이다(`RULE.md` "조용한 스킵을
        만들지 않는다"와 같은 계열: 조용한 덮어쓰기도 실패를 숨긴다).
     3. `examples/<module_path>`를
        `<target>/app/modules/customer_ops/<파일명>`으로 복사한다(내용
        변경 없이 그대로 복사 — import 경로 재작성은 하지 않는다. 대상이
        `app.modules.customer_ops`라는 이 저장소 관례를 그대로 쓴다는
        전제다).
     4. `<target>/config/project.yaml`을 새로 만든다 — 카탈로그 항목의
        `required_modules`/`required_ports`를 채우고, `teams:` 리스트에
        `team_id`(옵션 `--team-id`, 기본값은 `example_id`)와
        `implementation_ref`를 넣은 최소 YAML을 생성한다. **PyYAML에
        의존하지 않는다** — 이 저장소가 이미 `config/project.yaml`을
        어떻게 파싱하는지(`acop_basement/core/project_config.py` 또는
        해당 로더 실제 파일)를 먼저 읽고, 그 로더가 실제로 기대하는
        스키마·타입에 맞는 텍스트를 생성해라(간단한 f-string/템플릿으로
        충분하면 그걸로, 이미 PyYAML이 프로젝트 의존성에 있으면 그걸
        써도 된다 — `requirements.txt`를 먼저 확인해라).
     5. 생성 완료 후, 사람이 다음에 손으로 해야 할 명령(예: `pip install
        -e <acop_basement 경로>`, DB 마이그레이션, `tests/architecture`
        실행)을 안내 메시지로 stdout에 출력한다. **CLI가 이 명령들을
        대신 실행하지 않는다.**

3. **테스트**(신규, `tests/unit/scripts/test_scaffold_project.py`):
   - `list`가 카탈로그 2건을 정확히 반환/출력하는지.
   - `show`가 알 수 없는 `example_id`에 0이 아닌 종료 코드로 실패하는지.
   - `new`가 임시 디렉터리(`tmp_path` fixture)에 파일을 만들고, 생성된
     `project.yaml`이 이 저장소의 **실제 config 로더**
     (`acop_basement.core.project_config`의 로드 함수 — 정확한 이름은
     실제 코드를 읽고 확인해라)를 통과하는지 검증한다. 이게 이 테스트
     스위트의 핵심이다 — 스캐폴딩 산출물이 계약을 어기면 이 테스트가
     잡아야 한다.
   - 이미 `project.yaml`이 있는 대상에 `new`를 실행하면 에러로 멈추고
     기존 파일 내용이 그대로인지 검증.

4. **`docs/handoff/10_도메인_교체_가이드.md`** §3("새 프로젝트 준비 —
   첫 검증") — 기존 수동 절차 앞에, `python -m scripts.scaffold_project
   list`/`new` 경로를 대안으로 안내하는 문단 1~2개 추가. 기존 절차를
   지우지 않는다(수동 경로도 여전히 유효해야 한다 — 이 CLI는 편의
   도구이지 유일한 경로가 아니다).

5. **`docs/vision/TODO_VISION.md`** — VISION-10 행의 상태를 "보류" →
   "보류(1층 완료, 2층 보류)"로 갱신. `VISION-10_예제_카탈로그_스캐폴딩_CLI.md`
   상단 상태 줄과 개정 이력에도 완료 사실과 날짜(2026-08-19)를 추가.

## 하지 않을 것

- `acop_basement/**`, `acop_composer/**` 코드를 건드리지 않는다 — 이
  CLI는 그 위에 얹는 부가 도구다.
- `pip install`을 CLI가 대신 실행하지 않는다(§2-5).
- `examples/customer_ops/billing.py`·`technical.py`의 내용을 수정하지
  않는다 — 카탈로그는 이 파일들을 있는 그대로 가리키기만 한다.
- 2층(데이터 기반 자동 개선) 관련 코드·설계를 만들지 않는다 —
  `VISION-10` §1의 2층은 이번 스트림 범위 밖이다.
- `config/project.yaml`(저장소 루트, 실제 개발 서버가 쓰는 파일)을
  건드리지 않는다 — 이 스트림은 `new` 명령이 **새 대상 디렉터리**에
  만드는 산출물만 다룬다.

## 검증

```powershell
python -m scripts.scaffold_project list
python -m scripts.scaffold_project show billing_subscription
python -m pytest tests/unit/scripts/test_scaffold_project.py -q
python -m pytest tests/architecture -q
python -m pytest -q --ignore=tests/integration/rag
```

새 파일만 추가하므로(§2-4 문서 갱신 제외) 기존 테스트 결과는 이 스트림
시작 전과 동일해야 한다.

## 만들 것 (리포트)

`docs/reports/2026-08-19_S-SCAFFOLD-CLI-01_리포트.md` — 실행 명령과 실제
출력(`list`/`show`/`new` 각각의 출력 예시 포함), 만든/고친 파일 목록,
`new`가 만든 `project.yaml` 예시 전문.
