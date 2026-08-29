# S-COMPOSER-CATALOG-CHANGES 리포트 (스트림 B)

실행일: 2026-08-28. 계획서: `docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md`.

★스트림 A 와 같은 이유로 **Codex 가 아니라 Claude 가 직접 구현했다** — Codex
워크스페이스 쓰기 권한 거부. 진단은 스트림 A 리포트에 있다.

## 만든 것

| 파일 | 내용 |
|---|---|
| `acop_composer/catalog.py` | implementation_id ↔ 경로 매핑, 카탈로그 항목 |
| `acop_composer/api.py` | `GET /composer/catalog`, `POST /composer/changes` |
| `tests/e2e/test_composer_catalog_changes.py` | 12건(통합 2건 포함) |

v2(`/current`·`/validate`·`/apply`)는 **한 줄도 바꾸지 않았다.** 기존 8건이
그대로 통과하는 것으로 확인했다.

## ID↔경로 매핑을 어디에 뒀나

`acop_composer/catalog.py` 의 `IMPLEMENTATION_IDS` 에 **명시 선언**으로 뒀다.
UI 응답에는 `implementation_id` 만 나가고 Python 경로는 서버 안에만 있다.

경로를 노출하지 않는 이유는 두 가지다. UI 가 대상의 내부 모듈 구조에 묶이는
것을 막고, 원격 요청 문자열이 곧 import 경로가 되는 통로를 열지 않기 위해서다
(`docs/handoff/13` v2 가 registry allowlist 를 둔 것과 같은 이유).

★`_assert_complete()` 가 `KNOWN_IMPLEMENTATION_REFS` 에는 있는데 카탈로그에
ID 가 없는 구현을 찾아 **500 으로 터뜨린다.** 조용히 빠뜨리면 그 구현은 UI 에서
영원히 못 고르는데도 아무도 모른다 — 이 저장소가 금지하는 조용한 누락이다.

## 모듈 목록을 현재 선언에서 읽은 이유

모듈 구현 목록은 product 의 조립 루트(`app/composition.py` 의
`_MODULE_IMPLEMENTATIONS`)가 갖는다. `acop_composer` 가 그걸 import 하면 선택
패키지가 product 조립부에 묶여서, `acop_composer` 를 설치한 다른 제품에서
깨진다. 그래서 import 하지 않고 **현재 선언의 `modules` 키**를 낸다. UI 에는
이쪽이 더 정확하기도 하다 — "이 프로젝트가 실제로 켜고 끌 수 있는 것"이다.

## idempotency 를 감사 로그로 구현한 이유

새 저장소를 만들지 않고 `var/audit/composer_events.jsonl` 에 기록된
`idempotency_key` 를 근거로 삼는다. 요청이 오면 그 키의 이벤트를 찾아, 있으면
기록된 `result` 를 그대로 돌려준다.

메모리 dict 로 하면 프로세스가 재시작하는 순간 사라져서 "재시도했더니 두 번
적용" 이 그대로 살아난다. 감사 로그는 이미 append-only 로 영속되고 있으므로
새 인프라 없이 durable 한 보장을 얻는다. 손상된 줄은 건너뛰되 그 때문에
재시도가 막히지는 않게 했다.

비용은 선형 스캔이다. Composer 는 단일 writer 전제이고 감사 파일이 작아서
현재 규모에서는 문제가 없다. 파일이 커지면 append-only DB 테이블로 옮기라는
`docs/handoff/13` 의 기존 지침이 그대로 적용된다.

★재시도 시 `base_revision` 이 이미 낡았어도 409 가 아니라 첫 결과를 돌려준다.
그래야 네트워크 실패 후 재시도가 안전하다(`test_same_idempotency_key_applies_once`).

## v2 원자적 쓰기를 어떻게 재사용했나

복제하지 않았다. `/changes` 는 현재 선언을 읽어 **해당 인스턴스 하나만** 바꾼
새 선언을 만든 뒤, v2 와 **같은** `apply_candidate()` 에 넘긴다. 그래서
`_WRITE_LOCK` → 임시파일 → `os.replace()` → 백업 → revision 검사가 전부 그대로
적용된다. 검증도 별도 검증기를 만들지 않고 canonical loader 를 쓰는 기존
`validate_candidate()` 를 그대로 부른다.

★`validate_candidate()` 는 예외가 아니라 `ValidationResult` 를 돌려준다는 것을
구현 중에 확인해 dry_run 분기를 그에 맞게 고쳤다.

## `pending_restart` 를 정직하게 반환한다

저장에 성공해도 **이미 떠 있는 프로세스는 그 설정으로 돌지 않는다.** 조립은
기동 시 한 번만 일어난다(`app/composition.py`). 그래서 성공 응답의
`activation_state` 는 항상 `pending_restart` 다. "적용 완료" 처럼 응답하면
그건 조용한 성공 위장이다(`CLAUDE.md` §0.1). 자동 재시작은 계획서 §1 이 Phase 2
로 미뤘다 — supervisor·worker 구성이 미확정이라 지금 만들면 추측이 된다.

## 검증

```powershell
python -m pytest tests/e2e/test_composer_catalog_changes.py -q   # 12 passed
python -m pytest tests/e2e/test_composer_write_channel.py -q     # 8 passed (v2 무손상)
python -m pytest tests/architecture -q                            # 74 passed
python -m pytest -q --ignore=tests/integration/rag        # 383 passed
```

계획서 §4 완료 기준 대조:

| 기준 | 결과 |
|---|---|
| catalog 가 등록 구현체 + 선언형 타입 반환 | 통과 |
| Python 경로가 응답에 안 샌다 | 통과 |
| `dry_run: true` 가 파일을 안 건드린다 | 통과 (내용·mtime 양쪽 확인) |
| `base_revision` 불일치 → 409 | 통과 |
| 카탈로그 밖 ID → 422 | 통과 |
| 같은 idempotency_key 2회 → 1번만 쓴다 | 통과 |
| `activation_state` = `pending_restart` | 통과 |
| v2 기존 테스트 무손상 | 통과 (8건) |

## ★스트림 A+B 통합 증명

`test_declarative_team_created_through_the_api_loads_and_assembles` —
**코드 배포 없이 HTTP 명령만으로 새 Team 이 생긴다.** 카탈로그에서
`team.declarative.v1` 을 고르고 이름·capability·프롬프트·도구 목록을 보내면,
저장된 선언이 실제 `load_project_config()` 를 통과하고 `build_registry()` 로
조립까지 된다.

`test_declarative_team_with_write_tool_is_rejected_by_the_api` — grant ceiling
이 **HTTP 경로에서도** 걸린다. `allowed_tools` 에 `payments.refund` 를 넣어
보내면 422 로 거부된다. 권한 상승을 API 로 우회할 수 없다.

## 남은 것 (Phase 2)

- 자동 재시작(`POST /composer/activations`) — supervisor·단일/다중 worker
  구성이 정해진 뒤.
- 삭제 안전장치 고도화(drain/tombstone) — 1차는 `disable` 후 `delete` 2단계.
- 서명 플러그인 배포·SBOM·artifact installer.
