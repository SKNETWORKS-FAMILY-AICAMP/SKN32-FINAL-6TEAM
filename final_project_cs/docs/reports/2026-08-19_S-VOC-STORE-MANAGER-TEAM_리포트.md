# VOC & Store Manager Team 신설 리포트

## 구현 범위

- `app/modules/customer_ops/voc_store_manager.py`를 신규 추가했다.
- `app/modules/customer_ops/__init__.py`에 `VocStoreManagerTeam` import/export만 추가했다.
- `config/project.yaml`의 `teams` 목록에 `voc_store_manager`를 추가했다.
- `tests/unit/teams/test_voc_store_manager.py`를 신규 추가했다.

기존 `order_shipping` 및 `return_exchange` 구현과, 계약에서 금지한 core/application/presentation/tools/prompts 파일은 수정하지 않았다.

## 설계 결정 검증

§2의 확정 설계를 그대로 반영했다.

- manifest는 `team_id="voc_store_manager"`, 표시명, `a_cop.team_task` 1.0, `voc.aggregate`/`voc.escalate`, `accepted_case_types=["other"]`, 지정 context·tool·knowledge scope, `max_steps=6`, `active=True`, revision `2026-08-19`를 사용한다.
- degraded context는 `degraded_context`로 즉시 escalate한다.
- `read.policy`만 조회하며, 결과가 없으면 `policy_not_found`로 escalate한다.
- `ContextPack.similar_cases` 길이가 2 이상일 때만 `voc.escalate` 승인 제안을 만들며 arguments는 빈 dict다. idempotency key와 evidence ID도 지정된 방식으로 생성한다.
- 그 외에는 LLM을 호출하지 않고 고정 응답으로 완료한다.

## 테스트

신규 테스트: 5개 수집/통과

```text
.....                                                                    [100%]
5 passed, 1 warning in 1.10s
```

전체 수집 결과:

```text
325/327 tests collected (2 deselected) in 2.75s
```

기존 기준선 320개에서 신규 테스트 5개가 증가했다.

요청한 전체 실행 명령의 원문 결과:

```text
> python -m pytest -q --tb=short
.E...................................................................... [ 22%]
.....................................................EEEEEEEEEEEE
command timed out after 300587 milliseconds
```

전체 suite는 현재 통과하지 못했다. 기존 테스트 `test_composition_registers_the_two_builtin_teams_and_allows_extension` 및 `test_load_project_config_accepts_normal_declaration`가 Team 수를 정확히 기존 2개로 하드코딩하고 있어, 설정에 세 번째 Team을 추가한 이번 계약과 충돌한다. 또한 전체 실행은 해당 구간 이후 300초 제한에 도달했다. 이 충돌을 해결하려면 기존 테스트 또는 composition/config 로더를 수정해야 하지만, 이번 계약의 쓰기 대상 및 금지 범위 밖이므로 변경하지 않았다.
