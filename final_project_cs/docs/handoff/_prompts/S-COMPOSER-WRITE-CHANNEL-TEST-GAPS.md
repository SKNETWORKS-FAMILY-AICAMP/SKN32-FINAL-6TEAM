# 구현 지시 — Composer 쓰기채널 테스트 커버리지 갭 메우기

## 0. 배경

`app/application/composer_service.py`·`app/presentation/composer_auth.py`·
`app/presentation/api/composer.py`를 `final_project_sample`에서 이식했다
(`docs/reports/2026-08-18_S-COMPOSER-WRITE-CHANNEL-PORT_리포트.md`).
계약(`final_project_sample/docs/handoff/13_Composer_쓰기채널_계약.md` "테스트 계약" 절)이
요구하는 9개 항목 중 이식된 `tests/e2e/test_composer_write_channel.py`엔 **4개만** 있다.
5개가 빠졌다:

- 인증 없으면 401
- 잘못된 scope면 403
- (이 저장소엔 `composer_ui` 모듈 자체가 없다 — "HTML 폼 꺼져도 API는 산다"는
  대신 "ops_ui 꺼져도 API는 산다"로 검사한다, sample의 같은 케이스와 동일 패턴)
- validate는 파일을 안 건드린다
- 구현 안 된 `implementation_ref`는 422로 거부
- apply 성공 시 audit event(`var/audit/composer_events.jsonl`)에 actor·revision·changed_fields 기록

## 1. ★먼저 읽을 파일

이 저장소:
```
tests/e2e/test_composer_write_channel.py
app/presentation/api/composer.py
app/application/composer_service.py
```

참고(읽기만, 수정 금지):
```
C:\Users\playdata2\Documents\final_workspace\final_project_sample\tests\e2e\test_composer_write_channel.py
```

## 2. 만들 것 — `tests/e2e/test_composer_write_channel.py`에 테스트 추가

sample의 파일에 있는 다음 5개 패턴을 이 저장소 구조(`aud="final_project_cs"`,
이 저장소의 fixture·teams 데이터)에 맞춰 추가한다:

1. `test_requires_authentication` — 토큰 없이 `/composer/current` → 401
2. `test_wrong_scope_is_rejected` — `ops:introspect` 같은 다른 scope로 `/composer/current` → 403
3. `test_write_channel_survives_ops_ui_being_disabled` — `ops_ui: false`로 선언해도
   `/composer/current`는 살아있다(이 저장소엔 `composer_ui`가 없으므로 `ops_ui`로 검사)
4. `test_validate_does_not_write_the_file` — validate 호출 전후 파일 바이트가 동일함을 확인
5. `test_apply_rejects_unimplementable_reference` — 존재하지 않는 `implementation_ref`로
   apply → 422 `invalid_declaration`, 파일 불변
6. `test_apply_writes_an_audit_event_with_actor_and_revision` — apply 성공 후
   `var/audit/composer_events.jsonl`(또는 이 저장소의 실제 audit 경로 — 코드에서 확인해라)에
   한 줄이 append됐는지, 그 줄의 JSON에 `actor`·`previous_revision`·`revision`·`changed_fields`가
   있는지 확인

## 3. ★지킬 것

| 규칙 | 이유 |
|---|---|
| **`final_project_sample` 파일은 읽기만** | 수정 금지 |
| **항상 참인 단언 금지** | 실제로 401/403/422가 나는 것을 검사해라, 모킹으로 우회하지 마라 |
| **audit 경로는 코드에서 실제로 확인** | 추측해서 하드코딩하지 마라 — `composer.py`·`composer_service.py`가 어디에 쓰는지 읽어라 |

## 4. 완료 조건

```powershell
cd C:\Users\playdata2\Documents\final_workspace\final_project_cs
python -m pytest tests -q
```
★기대: **300 → 306(+6)**. 0 failed. 원문을 리포트에 붙여라.

## 5. 리포트

`docs/reports/2026-08-18_S-COMPOSER-WRITE-CHANNEL-TEST-GAPS_리포트.md`

## 6. 하지 말 것
- ❌ `final_project_sample` 수정
- ❌ 테스트 수 그대로인 채 "완료"
- ❌ `app/**` 프로덕션 코드 수정 (이번엔 테스트만 추가한다 — 커버리지 갭이 코드 결함을
  드러내면 리포트에 적고 별도로 알려라, 직접 고치지 마라)
