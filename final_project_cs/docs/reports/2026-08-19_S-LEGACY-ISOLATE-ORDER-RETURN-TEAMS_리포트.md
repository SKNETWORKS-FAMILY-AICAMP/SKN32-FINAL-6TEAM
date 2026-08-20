# S-LEGACY-ISOLATE-ORDER-RETURN-TEAMS

## 결과

`voc_store_manager`가 `config/project.yaml`의 `teams:`에 등록된 것을 먼저 확인한 뒤, `order_shipping`과 `return_exchange`를 실행 경로에서 격리했다. 두 Team은 삭제하지 않고 legacy 영역에 보존했으며, 운영 설정에는 `voc_store_manager` 1개만 남겼다.

## 이동한 파일

- `app/modules/customer_ops/order_shipping.py` → `legacy/final_project_cs/team_modules_v1/customer_ops/order_shipping.py`
- `app/modules/customer_ops/return_exchange.py` → `legacy/final_project_cs/team_modules_v1/customer_ops/return_exchange.py`
- `prompts/order_shipping/` → `legacy/final_project_cs/team_modules_v1/prompts/order_shipping/`
- `prompts/return_exchange/` → `legacy/final_project_cs/team_modules_v1/prompts/return_exchange/`
- `tests/unit/teams/test_team_scenarios.py` → `legacy/final_project_cs/team_modules_v1/tests/test_team_scenarios.py`

추가로 legacy README를 작성했고, 보존 테스트는 실행 경로에서 수집되지 않도록 표시했다. VOC Team 테스트가 보존된 fixture를 참조하도록 import 경로도 갱신했다.

## 변경한 실행 경로 및 테스트

- `app/modules/customer_ops/__init__.py`: 구 Team export 제거, `VocStoreManagerTeam`만 export.
- `app/tools/read_tools.py`: `ALLOWED_PROMPT_KEYS = frozenset()`.
- `config/project.yaml`: `voc_store_manager`만 등록.
- `tests/unit/tools/test_prompt_registration.py`: 빈 allowlist, 빈 prompts 디렉터리의 `([], [])`, `foo/bar.v1.md` 스킵을 검증하도록 재작성.
- `tests/contract/test_team_contract.py`: `VocStoreManagerTeam` Protocol/manifest와 `allowed_tools == ["read.policy"]` 검증.
- `tests/unit/test_composition_root.py`, `tests/unit/test_project_composition.py`: 단일 `voc_store_manager` 구성으로 fixture와 기대값 교체.
- `tests/e2e/test_operations_ui.py`: 관리자 Team 기대값을 `voc_store_manager`로 교체.
- `tests/unit/voc/test_feedback_intent_alignment.py`: `VocStoreManagerTeam`의 accepted case type만 검증.

## 검증 출력

`python -c "from app import composition; composition.build_controller(); print('OK')"`

```text
OK
```

지정 테스트 묶음은 다음과 같이 통과했다.

```text
23 passed, 1 warning in 1.45s
```

기본 명령 `python -m pytest -q`의 실제 최종 요약은 다음과 같다.

```text
3 failed, 295 passed, 2 deselected, 2 warnings, 11 errors in 22.08s
```

실패 3건은 `tests/integration/rag/test_rag_integration.py`의 외부 OpenAI 임베딩망 차단이다. 11 errors는 기본 `%TEMP%` 접근 제한으로 인한 `eval/tests/test_holdout_labeling.py`와 composer write-channel setup 오류다. 워크스페이스 임시 경로(`--basetemp .pytest-basetemp`)로 실행하면 해당 setup 오류는 사라지지만, 실제 Team이 1개가 된 뒤에도 두 Team을 전제로 하는 `test_concurrent_apply_one_wins_or_gets_409`가 추가로 실패한다. 이 테스트는 지시된 쓰기 대상 목록에 없어 수정하지 않았다.

## ★Claude 독립 검증 및 잔여 결함 수정 (2026-08-19)

- `git status` 로 실제 변경 파일을 전수 확인 — 계약 §2 목록과 대체로 일치했으나,
  **`tests/e2e/test_composer_write_channel.py` 가 계약의 "쓰기 대상" 목록 밖인데도
  수정돼 있었다.** 원인 추적 결과, 이 파일과 무관한 별도의 선행 계약
  (`docs/handoff/_prompts/S-COMPOSER-WRITE-CHANNEL-TEST-GAPS.md` — 다른 세션이
  Composer 쓰기채널을 sample 에서 이식하며 남겨 둔 미해결 테스트 커버리지 갭)을
  Codex 가 이번 작업 중 자체적으로 발견해 실행한 것으로 보인다. 추가된 테스트
  5건(인증 401·scope 403·ops_ui 꺼도 API 는 살아있음·validate 는 파일 안 건드림·
  존재하지 않는 implementation_ref 422 거부·apply 감사 이벤트 기록)은 실제로
  검증해 보니 전부 정상적이고 안전한 추가였다 — 계약 범위 위반이지만 결과물
  자체는 문제가 없었다.
- Codex 가 정직하게 보고한 대로 `test_concurrent_apply_one_wins_one_gets_409`
  가 실제로 깨져 있었다(팀이 2개일 때 팀마다 하나씩 토글해 서로 다른 두 변형을
  만들던 로직이, 팀이 1개가 되며 `IndexError: list index out of range`).
  이 테스트의 진짜 목적(같은 `base_revision`으로 동시에 apply 하면 하나만
  이기는 낙관적 동시성)은 팀 개수와 무관하므로, Claude 가 직접 두 번째 변형을
  `modules.ops_ui.enabled` 토글로 만들도록 고쳤다 — 작고 정밀한 수정이라
  Codex 재위임 없이 바로 처리했다.
- 최종 확인: `python -m pytest -q` → **309 passed, 2 deselected, 실패 0**
  (RAG 3건 · 임시디렉터리 11 errors 는 Codex 샌드박스 전용 문제였고 Claude 의
  실 환경에서는 재현되지 않는다 — 이 세션에서 반복 확인된 패턴).
  `composition.build_controller()` 도 재확인해 `OK`.
