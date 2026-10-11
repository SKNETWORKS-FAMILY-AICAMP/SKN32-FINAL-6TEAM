# S-EXAMPLES-SEPARATION-AUDIT — Billing/Technical → examples/ 분리 검증 (리포트만, 수정 금지)

## 배경

`BillingSubscriptionTeam`·`TechnicalEntitlementTeam` 이 `app/modules/customer_ops/`
에서 `examples/customer_ops/` 로 이동했다(v8 §10 기준 10주 착수 목록 밖 —
`config/project.yaml` 에도 더 이상 등록돼 있지 않다). 이동 자체와, 그 이동이
깨뜨린 죽은 참조(`app/core/project_config.py` 의 `KNOWN_IMPLEMENTATION_REFS`,
`eval/runners/common.py` 의 하드 임포트)는 이미 검수·수정·커밋됐다
(`git log` 의 `refactor(teams): Billing/Technical Team을 examples/로 분리` 커밋).

**이 작업은 그 이후에도 놓친 게 있는지 확인하는 것만이 목적이다. 코드를
고치지 않는다. 리포트만 낸다.**

## 확인할 것

1. **저장소 전체**(테스트·스크립트·eval·docs 코드 예제 포함, 문서 산문 설명은
   제외)에서 `app.modules.customer_ops.billing`, `app.modules.customer_ops.technical`,
   `app.modules.customer_ops:BillingSubscriptionTeam`,
   `app.modules.customer_ops:TechnicalEntitlementTeam` 형태의 참조가 남아
   있는지 grep 으로 찾는다. `examples/**` 안의 참조는 정상이다(예시 자신을
   가리키는 것). 그 밖에서 찾으면 **실제로 import 시점에 깨지는지**
   (`python -c "import ..."` 로 직접 확인)까지 보고한다.
2. `app/modules/customer_ops/__init__.py` 가 더 이상 두 클래스를 export 하지
   않는지, `config/project.yaml` 의 `teams:` 배열에 `billing_subscription`·
   `technical_entitlement` 가 없는지 확인한다.
3. `app/core/project_config.py` 의 `KNOWN_IMPLEMENTATION_REFS` 에 두 클래스가
   더 이상 없는지, 그리고 이 파일을 포함해 `app/core/**`·`app/domain/**`·
   `app/application/**`·`app/infrastructure/**`·`app/presentation/**`
   (basement) 전체에 **문자열을 쪼개서 도메인 검사(`tests/architecture/
   test_basement_is_domain_free.py` 의 `DOMAIN_WORDS`: payment, subscription,
   entitlement, refund, invoice, order_id, line_item, shipment, sku, cart)를
   피해가는 다른 패턴**이 남아 있는지 찾는다(예: 문자열 연결, `getattr` 로
   속성명을 조립, f-string 조각내기, base64/hex 인코딩 등). 하나라도 있으면
   basement 순수성 게이트가 실제로는 우회되고 있다는 뜻이므로 반드시 보고한다.
4. `examples/` 패키지 자체가 온전한지 확인한다 — `examples/__init__.py`,
   `examples/customer_ops/__init__.py`(두 클래스 export), `examples/tests/
   test_team_scenarios.py` 가 실제로 `python -m pytest examples/tests -q`
   로 (그런 실행 경로가 있다면) 또는 `pytest --collect-only` 로 수집되는지.
   수집되지 않는다면(예: pytest.ini 의 testpaths 가 `examples/` 를 빼고
   있어서) 그 사실과 원인을 보고한다 — 문제라고 단정하지 않는다. 프로덕션
   스위트에서 빠지는 것 자체는 의도(examples 는 데모)일 수 있다.
5. `.dockerignore` 가 `examples/` 를 실제로 제외하는지 패턴 문법을 확인한다.
6. `docker/compose.yml`, `Dockerfile`, `infra/aws/` 등 배포 관련 파일이
   옛 경로(`app/modules/customer_ops/billing.py` 등)를 특별 취급하거나
   가정하고 있지 않은지 확인한다(있다면 존재만 보고, 고치지 않는다).
7. `python -m pytest -q --ignore=tests/integration/rag` 를 실제로 돌려서
   실패가 있는지 원문 출력과 함께 보고한다. 실패가 있어도 **고치지 않는다.**

## 하지 않을 것

- **어떤 파일도 수정하지 않는다.** import 경로 고치기, docstring 수정,
  `.gitignore` 추가 등 무엇이든 코드/문서 변경은 하지 않는다. 발견한 것을
  리포트에 적기만 한다.
- 새 파일도 만들지 않는다 — 결과는 이 세션의 최종 응답(stdout)으로만 낸다.

## 출력 형식

각 발견 항목마다: 파일:줄, 무엇을 찾았는지, **실행 시점에 실제로 깨지는지
직접 검증한 결과**(추측 금지 — `python -c "import ..."` 나 `grep` 결과를
그대로 인용), 심각도(치명적 결함 / 경고 / 무해한 문서 언급). 문제가 하나도
없으면 "문제 없음"이라고 명시하고 무엇을 확인했는지 나열한다.
