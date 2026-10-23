# 담당 Team의 다시 적용 안내 문구가 되돌림으로 표시됨

## 미해결

다시 적용 요청에서 변경 제안은 생성되지만 안내 문구가 '되돌렸어요'로 나온다. 기존 경로와 현재 Team 경로의 기능 승계를 대조하다가 발견했다. 제품 코드는 수정하지 않았다.

위치: app/domains/travel_ops/instances/_shared/itinerary_team.py:212. plan_rollback 호출에서 redo 인자를 전달하지 않는다. conversation_work.py:168은 rollback과 redo 모두 이 메서드로 연결한다. 기존 TripDesk.rollback은 이력을 보고 redo 인자를 전달한다.

재현:

```powershell
$env:PYTHONPATH='.tmp/conversation-python;.'
$env:PYTHONIOENCODING='utf-8'
python wiki/records/evidence/2026-10-11_team_calculation_audit/reproduce_redo.py
```

실측: Team.execute 재현 1/1건에서 변경 제안 1개, 안내 문구 차이 1건. 기존 계산 함수의 redo=True 결과는 '요청하신 변경을 다시 적용했어요'이고 Team 결과는 '되돌렸어요'다. [실제 출력](../../evidence/2026-10-11_team_calculation_audit/redo.log).

위험: 고객이 다시 적용과 되돌림을 반대로 이해할 수 있다. 이번 재현은 제안 단계까지이며 실제 DB 적용 내용 오류를 입증한 것은 아니다. 기존 90건 시험 통과는 이 문구 차이를 검출하지 못한다.

수치 정정: 핵심 계산 재사용·기존 시험 통과를 근거로 모든 부가 동작이 동일하거나 더 낫다고 말할 수 없다. [대조 보고서](../2026-10-11_0442_team_calculation_reuse_audit.md).
