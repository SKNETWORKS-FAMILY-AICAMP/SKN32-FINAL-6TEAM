# 구현 지시 — order_shipping/return_exchange Team 을 legacy 로 완전 격리 (2단계)

## 0. 전제 조건 — ★반드시 먼저 확인 (2026-08-19 정정)

확인할 것은 딱 하나: **`voc_store_manager` 가 `config/project.yaml` 의
`teams:` 에 이미 등록돼 있는가**(`grep voc_store_manager config/project.yaml`).
등록 안 돼 있으면 즉시 중단하고 보고해라 — `teams:` 목록이
`Field(min_length=1)` 이라 두 팀을 다 빼면 `config/project.yaml` 로딩
자체가 깨진다(`app/core/project_config.py:50`).

★**`pytest -q` 가 0 실패일 필요는 없다 — 그렇게 요구했던 건 이 계약
자체의 실수였다.** 실제로 지금(2026-08-19) `pytest -q` 를 돌리면 다음이
나오는데 전부 **이 작업과 무관하거나, 이 작업이 고칠 대상**이다:

- `tests/unit/test_composition_root.py`·`test_project_composition.py`
  실패 2건 — "팀이 정확히 2개"를 하드코딩한 테스트다. **이게 바로 이
  계약 §4 가 고칠 대상이다.** 실패 상태인 게 정상이다.
- `tests/integration/rag/test_rag_integration.py` 실패 3건 — 실행 환경의
  외부망 차단(OpenAI 임베딩 API 접근 불가)이다. 이 작업과 무관하다.
- `tests/e2e/test_composer_write_channel.py` 에러 다수(있다면) — 실행
  샌드박스 환경(비밀키·시크릿 미주입)의 문제다. Claude 가 실 환경에서
  10건 전부 통과함을 이미 확인했다. 이 작업과 무관하다.

**시작 조건은 "위 목록 밖의 새로운 실패가 없다"이다.** 위 목록에 없는
실패나 에러가 나오면 그건 진짜 문제이니 중단하고 보고해라.

## 1. 배경

`order_shipping`/`return_exchange` 는 실제 기획서(`program/plan/
A-COP_구현계획서_v8.md` §8-B)에 있는 이름이 아니다 — 도메인 마이그레이션
과정에서 임의로 만든 팀이다. 실제 CS Pack 확정 Team 은 VOC & Store
Manager 와 Response Generation & Review 뿐이다. **삭제하지 않는다** —
`RULE.md` §4.2 `legacy/<원본프로젝트명>/<원본경로>` 관례대로 보존하고,
실행 경로에서만 완전히 뺀다.

## 2. 소유 범위

```
쓰기 대상:
  legacy/final_project_cs/team_modules_v1/**        (신규 — 이동 대상)
  app/modules/customer_ops/order_shipping.py         (삭제 — legacy 로 이동)
  app/modules/customer_ops/return_exchange.py        (삭제 — legacy 로 이동)
  app/modules/customer_ops/__init__.py               (export 제거)
  app/tools/read_tools.py                            (ALLOWED_PROMPT_KEYS 비움)
  config/project.yaml                                (teams 목록에서 두 항목 제거)
  prompts/order_shipping/**                          (삭제 — legacy 로 이동)
  prompts/return_exchange/**                          (삭제 — legacy 로 이동)
  tests/unit/teams/test_team_scenarios.py            (legacy 로 이동)
  tests/unit/tools/test_prompt_registration.py       (재작성 — 아래 §4 참고)
  tests/contract/test_team_contract.py               (재작성 — voc_store_manager 대상으로)
  tests/e2e/test_operations_ui.py                     (문자열 교체만)
  tests/unit/test_composition_root.py                 (문자열 교체만)
  tests/unit/test_project_composition.py              (fixture 교체만)
  tests/unit/voc/test_feedback_intent_alignment.py    (대상 Team 교체만)

★건드리지 않는다(확인만 하고 그대로 둔다 — 실제로는 placeholder 문자열이라
  real Team 존재를 검증하지 않는다):
  tests/contract/test_contracts.py
  tests/unit/core/test_case_reducer.py
  tests/unit/infrastructure/test_graph_v7_axes.py
  tests/integration/llm/test_llm_call_audit_wiring.py

★절대 금지: `verification_policy.py`, `app/core/**`, `app/application/**`,
  `app/presentation/**`, `eval/**`, `scripts/**`, `voc_store_manager.py`
```

## 3. 이동 (삭제 아님)

```
git mv app/modules/customer_ops/order_shipping.py  legacy/final_project_cs/team_modules_v1/customer_ops/order_shipping.py
git mv app/modules/customer_ops/return_exchange.py legacy/final_project_cs/team_modules_v1/customer_ops/return_exchange.py
git mv prompts/order_shipping   legacy/final_project_cs/team_modules_v1/prompts/order_shipping
git mv prompts/return_exchange  legacy/final_project_cs/team_modules_v1/prompts/return_exchange
git mv tests/unit/teams/test_team_scenarios.py legacy/final_project_cs/team_modules_v1/tests/test_team_scenarios.py
```
(디렉터리가 없으면 만든다. `git mv` 를 못 쓰는 상황이면 일반 파일
이동 후 `git add`/`git rm` 으로 같은 결과를 낸다.)

`legacy/final_project_cs/team_modules_v1/README.md` 를 새로 써서 왜
여기 있는지 한 문단으로 남긴다 — "v8 §8-B 확정 계획과 이름·경계가
달랐던 1차 커머스 팀 구현. 삭제하지 않고 보존. 대체: voc_store_manager,
(예정) response_generation_review." 같은 내용.

## 4. 각 파일별 정확한 처리

### `app/modules/customer_ops/__init__.py`
`OrderShippingTeam`/`ReturnExchangeTeam` import·export 제거. `VocStoreManagerTeam`
(1단계에서 이미 추가돼 있어야 함)만 남긴다.

### `app/tools/read_tools.py`
`ALLOWED_PROMPT_KEYS = frozenset()` (빈 집합)으로 바꾼다. 이 상수를 쓰는
`register_prompt_files()` 로직 자체는 안 건드린다 — 빈 허용 목록이면
글롭으로 찾은 파일이 있어도 전부 건너뛰기 목록에 잡히는 게 맞는 동작이다
(현재 `prompts/` 에 유효 콘텐츠 파일이 안 남으므로 결과적으로 등록 0건).

### `config/project.yaml`
`teams:` 에서 `order_shipping`/`return_exchange` 두 항목을 지운다.
`voc_store_manager` 항목(1단계에서 추가됨)만 남는다. **1개 이상**인지
반드시 확인한다.

### `tests/unit/tools/test_prompt_registration.py`
4개 실제 파일을 전제로 한 테스트라 지금 상황과 안 맞는다. 다음으로
재작성한다: `ALLOWED_PROMPT_KEYS == frozenset()` 확인, `register_prompt_files()`
를 빈 `prompts/` fixture 디렉터리로 호출하면 `([], [])` 를 돌려주는지
확인. 기존 "같은 버전 다른 내용이면 에러" 테스트는 임시 디렉터리에
아무 임의의 두 글자 키(예: `foo/bar.v1.md`)로 재현하되, 허용 목록 밖이라
애초에 등록 안 되고 skipped 로만 잡힌다는 사실도 함께 확인한다(이
동작 자체가 바뀌었으므로 테스트 의미도 바뀐다 — 억지로 이전 동작을
재현하려 하지 않는다).

### `tests/contract/test_team_contract.py`
`OrderShippingTeam`/`ReturnExchangeTeam` import 를 `VocStoreManagerTeam`
으로 교체하고, manifest·Protocol 준수 단언을 그 Team 기준으로 다시 쓴다
(`voc_store_manager.py` 의 실제 `manifest.allowed_tools` 값 — `["read.policy"]`
— 을 그대로 대조).

### `tests/e2e/test_operations_ui.py`
`"order_shipping"`/`"return_exchange"` 문자열을 `"voc_store_manager"` 로
교체(단, 두 팀 이름이 동시에 필요한 구조면 하나만 남기고 나머지 검사는
제거 — 실제 코드를 읽고 맥락에 맞게 고친다).

### `tests/unit/test_composition_root.py`, `test_project_composition.py`
하드코딩된 `order_shipping`/`return_exchange`/`OrderShippingTeam`/
`ReturnExchangeTeam` fixture 값을 `voc_store_manager`/`VocStoreManagerTeam`
으로 교체한다. 두 팀을 동시에 쓰는 검증 로직(예: 여러 팀 존재 확인)이
있으면 그 의도를 유지하되 실제 남은 팀 구성에 맞게 고친다.

### `tests/unit/voc/test_feedback_intent_alignment.py`
`from app.modules.customer_ops import OrderShippingTeam, ReturnExchangeTeam`
를 `VocStoreManagerTeam` 으로 교체하고, 불변조건을
`INTENTS ⊇ VocStoreManagerTeam.manifest.accepted_case_types` 로 좁힌다.

## 5. 검증

```powershell
python -m pytest -q
```
★기대: `test_composition_root.py`·`test_project_composition.py` 실패가
**사라진다**(이 계약이 고쳤으므로). RAG 3건과(샌드박스라면) composer
write channel 에러는 여전히 나올 수 있다(§0 참고, 이 작업과 무관).
**§0 목록 밖의 새 실패·에러가 있으면 완료가 아니다.** 테스트 총량은
줄 수 있다(레거시로 옮긴 16건이 빠지고 재작성된 만큼만 남으므로) —
그건 정상이다.

```powershell
python -c "from app import composition; composition.build_controller(); print('OK')"
```
★이 명령이 예외 없이 `OK` 를 출력해야 한다 — config 로딩과 Team 조립이
실제로 되는지의 최종 증거다.

## 6. 완료 조건

- [ ] `order_shipping`/`return_exchange` 소스·프롬프트·전용 테스트가
      `legacy/final_project_cs/team_modules_v1/` 에 보존됨(삭제 아님)
- [ ] `config/project.yaml` 의 `teams:` 에 `voc_store_manager` 만 남음
- [ ] `python -m pytest -q` 실패 0
- [ ] `composition.build_controller()` 예외 없이 성공
- [ ] `docs/reports/2026-08-19_S-LEGACY-ISOLATE-ORDER-RETURN-TEAMS_리포트.md`
      제출 — 이동한 파일 전체 목록, 각 테스트 파일별로 무엇을 했는지,
      §5 두 명령의 실제 출력
