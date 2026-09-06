---
type: concept
title: Composer의 단일 쓰기 경로
description: 설정 변경을 한 경로로 모으는 이유와 그 경로가 적용 전에 검사하는 조건을 설명한다.
status: draft
tags: [architecture, state, api, testing]
---

# Composer의 단일 쓰기 경로

Composer의 HTTP 명령은 `/composer/apply`, `/composer/changes`, `/composer/toggle`로 나뉘지만, 실제 저장 판정은 `apply_candidate()` 하나로 모인다. `[실측]` `/changes`와 `/toggle`은 `_perform_change()`를 공유하고, `_perform_change()`와 `/apply`는 모두 `apply_candidate()`를 호출한다. `acop_composer/api.py:202-215`, `acop_composer/api.py:317-332`, `acop_composer/api.py:362-364`, `acop_composer/api.py:415-424`

이 경로를 하나로 유지하는 이유는 검증, revision 충돌 판정, 저장소의 조건부 쓰기를 모든 변경 방식에 동일하게 적용하기 위해서다. `[실측]` `/toggle`도 별도 저장 구현을 갖지 않고 `/changes`와 같은 경로를 사용한다. `acop_composer/api.py:164-171`

## 변경이 저장되기까지

1. `[실측]` `/composer/current`가 현재 선언과 `revision`을 반환한다. 쓰기 요청은 이 값을 `base_revision`으로 제출한다. `acop_composer/api.py:392-396`
2. `[실측]` `/changes`는 현재 선언을 깊은 복사한 뒤 요청 대상 하나만 변경한 후보 선언을 만든다. 모듈과 Team의 존재 여부, 생성 중복, Team 생성 시 `implementation_id` 필요 여부도 이 단계에서 판정한다. `acop_composer/api.py:259-314`
3. `[실측]` `/toggle`은 `enable` 또는 `disable` 변경 명령으로 변환되어 `_perform_change()`에 들어간다. `acop_composer/api.py:202-215`
4. `[실측]` `apply_candidate()`는 쓰기 잠금을 잡은 뒤 저장소에서 현재 선언을 다시 읽고, 현재 revision과 요청의 `base_revision`을 비교한다. 다르면 `RevisionConflict`를 발생시킨다. `acop_composer/service.py:137-147`
5. `[실측]` 후보는 `config_from_declaration()`으로 다시 검증된다. 검증 실패는 저장소의 `write()` 호출 전에 발생한다. `acop_composer/service.py:149-153`
6. `[실측]` 저장소에는 `base_revision`과 새 revision을 함께 전달한다. 저장소가 `RevisionMismatch`를 반환하면 API 계층에서 409 `revision_conflict`로 변환되는 `RevisionConflict`가 발생한다. `acop_composer/service.py:151-156`, `acop_composer/api.py:365-370`
7. `[실측]` 저장 성공 후 변경 주체, 대상, 시각, 이전·새 revision, 변경 필드, 사유와 상관관계를 감사 저장소에 기록한다. `/changes`와 `/toggle`은 작업 종류와 인스턴스 정보도 기록한다. `acop_composer/api.py:372-388`, `acop_composer/api.py:432-442`

## 적용 전에 검사하는 것

- `[실측]` 요청 모델은 선언되지 않은 추가 필드를 거부하며, `reason`과 대상 ID에는 최소 한 글자를 요구한다. 작업과 자원 종류도 허용된 문자열로 제한한다. `acop_composer/api.py:131-160`, `acop_composer/api.py:174-179`
- `[실측]` 모든 변경 엔드포인트는 `composer:write` scope를 요구한다. 검증 전용 엔드포인트는 `composer:validate`, 현재 선언과 카탈로그 조회는 `composer:read`를 요구한다. `acop_composer/api.py:202-204`, `acop_composer/api.py:228-230`, `acop_composer/api.py:317-319`, `acop_composer/api.py:392-401`, `acop_composer/api.py:415-417`
- `[실측]` 중앙 설정 서비스에서는 `X-Deployment-Id` 헤더가 비어 있으면 400 `deployment_required`로 거부한다. 파일 방식과 중앙 방식의 저장소 선택도 요청 처리 전에 이루어진다. `acop_composer/api.py:62-96`
- `[실측]` HTTP 쓰기 경로는 `enforce_registry=True`로 적용한다. 별도 registry 검사는 활성 Team의 `implementation_ref`가 `KNOWN_IMPLEMENTATION_REFS`에 들어 있는지 확인한다. `acop_composer/service.py:62-76`, `acop_composer/api.py:363-364`, `acop_composer/api.py:423-424`
- `[실측]` 후보 전체는 별도 UI 검증기가 아니라 서버의 `config_from_declaration()`에 전달된다. `/validate`와 실제 적용이 같은 정규 검증 진입점을 사용한다. `acop_composer/service.py:99-121`, `acop_composer/service.py:149-150`
- `[미확보]` `config_from_declaration()` 내부의 세부 스키마·호환성 규칙은 허용된 파일 범위 밖이므로 이 문서에서 독립적으로 확인하지 않았다.
- `[실측]` 동일한 `base_revision`으로 동시에 보낸 두 `/apply` 요청 중 하나는 200, 다른 하나는 409가 되어야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_write_channel.py:187-234`
- `[실측]` 알 수 없는 구현 참조는 422로 거부되고 선언 파일은 그대로 남아야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_write_channel.py:171-184`

## 쓰지 않는 경로

`[실측]` `/composer/validate`는 후보를 검증하고 결과와 계산된 revision만 반환한다. 저장소에 쓰지 않는다. `acop_composer/api.py:399-412`

`[실측]` `/changes`의 `dry_run`도 후보를 검증하지만 `apply_candidate()`를 호출하지 않는다. 응답의 `desired_revision`은 기존 revision이며 파일 내용과 수정 시각이 유지되어야 한다는 검사가 있다. `acop_composer/api.py:352-360`, `tests/e2e/test_composer_catalog_changes.py:100-112`

## 확인된 한계

`[실측]` `_WRITE_LOCK`은 단일 프로세스 안의 동시 쓰기만 직렬화한다. 여러 워커나 여러 인스턴스 사이의 최종 충돌 판정은 저장소의 조건부 쓰기에 맡긴다. `acop_composer/service.py:41-44`, `acop_composer/service.py:142-156`

`[미확보]` 파일 저장소와 PostgreSQL 저장소가 물리적으로 어떤 원자적 연산을 사용하는지는 허용된 파일 범위에서 확인하지 않았다.

`[실측]` 감사 기록은 설정 저장 뒤에 실행된다. 감사 저장이 실패하면 API는 500 `audit_failure`를 반환하지만 오류 메시지는 변경 자체가 이미 적용되었음을 명시한다. 이 코드에는 설정을 되돌리는 처리가 없다. `acop_composer/api.py:385-388`, `acop_composer/api.py:439-442`

`[미확보]` 허용된 테스트 파일의 현재 실행 성공 여부는 확인하지 않았다.

## ★ [2026-09-06] 이력이 남고, 되돌리기는 이력에서 한다

`[실측]` [D-011](../../../wiki/decisions/D-011-composer-v3-gap.md) 구현. `project_configs`는 대상당 현재 행 하나뿐이라 되돌릴 수 없었다. 이제 **쓰기 경로 하나(`apply_candidate()`)가 쓴 직후 같은 잠금 아래에서 이력을 한 줄 남긴다** — `/apply`·`/changes`·`/toggle`·`/restore` 전부.

| 무엇 | 어디 |
|---|---|
| 이력 저장소 | `acop_basement/core/revision_store.py` — `FileRevisionStore`(선언 파일 곁 JSONL, 기본 `var/audit/composer_revisions.jsonl`) · `PostgresRevisionStore`(`project_config_revisions`, 마이그레이션 009). 감사 저장소와 같은 선택 규칙 — 중앙이면 중앙 |
| 첫 기록 | 직전 상태를 **`baseline`** 으로 먼저 남긴다. 그래야 첫 변경 직후에도 되돌릴 수 있다 |
| `GET /composer/revisions` | 최신부터. **선언 전문은 안 내보낸다** — UI 가 전문을 받으면 다시 통째 교체로 돌아간다 |
| `POST /composer/restore` | `{revision, base_revision, reason}`. 서버가 이력에서 선언을 꺼내 **새 revision 으로 다시 적용**한다. 이력을 되감지 않고 앞으로 한 줄 더 간다. 없는 revision 404 · 낡은 base 409 · 지금이 그 revision 이면 422 |
| 실패 | 저장은 됐는데 이력을 못 남기면 500 `history_failure` — 감사 실패와 같은 모양으로 "이미 적용됐다"를 숨기지 않는다 |

revision 은 내용 해시라 되돌리면 **같은 revision 이 다시 나온다.** 그래서 이력에서 revision 은 고유 키가 아니고, 조회는 최신 한 줄을 고른다(`tests/integration/test_revision_store.py`).

`[실측]` e2e — `test_every_write_leaves_history_and_restore_returns_the_previous_content`(파일 모드, `/changes` → 이력 2줄 → 복원 → 파일 내용·revision 원복, 감사에 `restored_from`) · `test_restore_unknown_revision_is_404_and_stale_base_is_409` · `tests/e2e/test_config_service.py::test_restore_is_scoped_to_the_deployment`(중앙 모드, 대상 격리).

UI 클라이언트(`acop_composer_ui/client.py`)에 `revisions()`·`restore()`가 생겼고 `apply()`는 `composer:admin`을 요구한다.

## 관계

- 인증 주체와 scope 판정은 [auth-scope.md](auth-scope.md)를 참조한다.
- UI가 이 쓰기 경로 밖으로 나가지 못하게 하는 경계는 [ui-boundary.md](ui-boundary.md)를 참조한다.
