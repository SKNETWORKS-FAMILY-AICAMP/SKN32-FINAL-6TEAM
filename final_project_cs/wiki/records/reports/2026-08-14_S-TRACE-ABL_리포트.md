# S-TRACE-ABL 리포트

## A. trace

`app/presentation/ui/routes.py`의 trace 조회가 Case의 `subject`를 함께 읽고, trace 이벤트 payload에 `case_id`, `subject`, 현재 `status`, `version`을 노출하도록 수정했다. aggregate version 정렬과 append-only 안내는 유지했다. 수정·삭제 UI는 추가하지 않았다. 관련 E2E는 7건 실행했다.

## B. ablation

기존 구현에서 실제 실행 경로에 반영되던 것은 `no_rag`뿐이었다. 나머지 네 flag는 결과 config에 기록되지만 기능을 끄지 않았다.

수정 사항:

- `no_context_broker`: ContextBroker 조립 대신 원문 입력과 최소 raw ContextPack을 사용한다.
- `no_team_split`: Billing team 하나로 처리한다.
- `no_approval`: `wait_for_approval` 결과를 `respond`로 변환하고 approval proposal을 제거한다.
- `no_rag`: policy 검색을 호출하지 않고 degraded 및 빈 evidence 경로를 사용한다.
- `no_feedback_inline`: inline feedback 입력을 생략하고 control 상태를 결과 record에 남긴다.

모든 flag는 `config.ablations`에 기록되며, dry-run은 다음과 같이 확인했다.

```text
provider=openai, cases=2, ablations=["no_rag"], estimated_llm_calls=4
```

전량 실행은 하지 않았다.

## C. 원문 수집

`wiki/records/evidence/_raw/DoD-05_v4.md`와 `DoD-10_v4.md`를 추가했다. DoD-10은 `demo`를 변경하지 않고 임시 tenant에 6건의 당일 Case와 2건의 이전 Case를 만들었으며, alert 출력 후 tenant 연결 데이터를 삭제했다.

## 검증 관측

- trace E2E: 7 passed
- Context budget: 3 passed
- VOC: 8 passed
- ablation dry-run: exit code 0
- DB tenant 목록: `demo`와 기존 `test_cc2a968516f546adb1e436512feaedef`가 조회되어 `tenants=2`였다. 후자는 작업 전부터 존재한 데이터로 확인되어 삭제하지 않았다.
