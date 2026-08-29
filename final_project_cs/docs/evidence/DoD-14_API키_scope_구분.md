# DoD-14 — API key scope 가 read/write/MCP 를 구분한다

- v5 §20 항목 14 / 검증 방법: unauthorized matrix
- 실행: 2026-08-12 23:20 · 실측 원문 `docs/evidence/_raw/DoD-14.md`
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/integration/api/test_api_runtime.py -q
python -m pytest tests/security -q
```

## 실제 출력

```
14 passed, 1 warning in 5.08s
2 passed, 1 warning in 0.74s
```

## 판정 근거

- `test_unauthorized_matrix_for_each_scope_and_rest_endpoint` 가 scope **6종**
  (`case:read`, `case:write`, `subscription:read`, `technical:read`, `action:approve`, `mcp:read`)
  에 대해 parametrize 되어 REST endpoint 를 전수 호출하고 기대 status 를 단언한다.
- `test_mcp_read_scope_tools_execute_only_with_mcp_principal` 이 MCP tool 3종을
  각각 parametrize 하여 `mcp:read` principal 로만 실행됨을 확인한다.
- scope 목록은 `config/guardrails.yaml` 의 `security.scopes` 에서 읽는다
  (`test_six_scopes_are_guardrail_owned` 가 하드코딩이 아님을 단언).
- ★`test_case_from_other_customer_is_not_found` — 남의 Case 는 **404** 다.
  403 이면 존재 사실을 알리는 것이라 실패로 판정한다(`docs/handoff/03` §2).

## ★이 항목은 한 번 전면 실패했었다

1차 산출물은 `security.py` 가 `os.getenv` 로 설정을 읽어 **인증이 필요한 모든 요청이 500** 이었다.
그때 테스트는 정적 단언 3건뿐이라 초록이었다.
→ `docs/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md`

★**route 가 등록됐다는 사실과 scope 가 강제된다는 사실은 다르다.**
지금 통과는 실제 HTTP 호출 14건에 근거한다.

## 한계

- 표 형태의 scope × endpoint 전수 매트릭스 **출력물**은 생성하지 않았다
  (테스트 parametrize 안에만 있다). 발표용으로 뽑으려면 별도 작업이 필요하다.
- API key **회전·만료** 정책은 구현·검증 범위 밖이다(v5 MVP 경계).
- OAuth2/OIDC 는 v5 §3 Phase 2 로 **의도적으로 구현하지 않았다.**

## ★2026-08-24 갱신 — Composer 쓰기채널 인증이 사실상 무력화돼 있던 결함 2건

`final_project_sample/acop_basement/` 대조로 cs 고유(basement 이식 누락이
아니라 cs가 직접 만든 결함)의 인증 우회 체인이 발견됐다. 둘 다 이
DoD가 검증하는 "scope 가 실제로 강제되는가"의 정신을 정면으로 어겼다.

1. **`composer_jwt_secret`/`composer_issuer_secret` fail-open**
   (`app/core/settings.py`). 두 필드에 `= ""` 기본값이 있어 환경변수 없이도
   앱이 정상 기동됐고, 실제로 cs `.env`엔 이 값이 없었다 — **빈 문자열을
   HMAC 키로 서명한 JWT가 `authenticate_composer()`의 서명 검증을 그대로
   통과**했다(알려진 JWT 위조 기법). `composer:validate`/`composer:write`
   scope 검사 자체가 무의미해지는 결함이었다. sample처럼 두 필드를 필수로
   되돌려 값이 없으면 기동을 거부하게 고쳤고, 실제 `.env`에 랜덤 시크릿을
   채웠다. `tests/unit/core/test_settings_composer_secrets.py` 신규.
2. **Composer 쓰기채널에 구현체 allowlist 없음** (`app/core/project_config.py`).
   `composer:write` scope만 있으면 `implementation_ref`에 임의 문자열을
   넣어 `importlib.import_module()`이 **공격자가 지정한 모듈을 그대로
   import**하게 만들 수 있었다 — ①과 결합하면 인증 우회 후 임의 모듈
   import까지 이어지는 체인이었다. sample의 `KNOWN_IMPLEMENTATION_REFS`
   allowlist를 이식(cs의 실제 활성 Team 5개로 채움), `/composer/validate`·
   `/composer/apply`가 `enforce_registry=True`로 항상 검사하도록 고쳤다.
   `tests/e2e/test_composer_write_channel.py`에 임의 모듈 거부·정상 통과·
   비활성 무시 3종 재현 테스트 추가.

`tests/security/test_scope_contract.py`의 scope 개수 단언도 9→10으로
갱신됐다(`ops:introspect` 신설, 아래 참고). 상세:
`docs/reports/2026-08-24_S-BASEMENT-07-COMPOSER-SECRET-FAILOPEN_리포트.md`,
`docs/reports/2026-08-24_S-BASEMENT-08-COMPOSER-IMPL-ALLOWLIST_리포트.md`

## ★2026-08-24 — 이 DoD에 안 걸리는 나머지 2건 (별도 기록만)

같은 조사에서 함께 발견·수정된 2건은 이 DoD의 범위(scope 강제)에 들지
않아 다른 곳에 남긴다:
- `list_cases()` 동률(같은 `created_at`) 정렬 비결정성 —
  `docs/evidence/DoD-03_동시성_appendonly_replay.md`에도 안 맞고(동시성이
  아니라 정렬 안정성 문제), v8 §27 의 1~29 항목 어디에도 명시적으로
  안 걸린다. `docs/reports/2026-08-24_S-BASEMENT-09-LIST-CASES-ORDERING_리포트.md`만
  근거로 남긴다.
- `GET /introspection`(외부 콘솔용 read-only 조립 스냅샷) — v8 계획서에
  아예 없는 항목이다(basement 완성도 문제이지 v8 DoD 요구사항이 아니다).
  `docs/reports/2026-08-24_S-BASEMENT-10-INTROSPECTION-ENDPOINT_리포트.md`만
  근거로 남긴다.
