# S-BASEMENT-03-TENANT-DEDUPE 결과 보고서

## 변경 내용

- outbox dedupe conflict target을 `tenant_id, topic, dedupe_key`로 통일했다.
  `outbox.py`, `transition.py`뿐 아니라 새 제약과 충돌하는 `feedback_job.py`의
  outbox insert도 함께 갱신했다.
- `003_outbox_tenant_scoped_dedupe.sql`을 추가해 기존
  `UNIQUE(topic, dedupe_key)`를 제거하고
  `UNIQUE(tenant_id, topic, dedupe_key)`를 추가했다. 반복 적용 시에도
  이미 새 제약이 있으면 재생성하지 않도록 작성했다.
- outbox publisher에서 payload tenant와 case tenant가 다르면 거부하도록
  샘플의 tenant 경계 검증도 복원했다.
- idempotency key 생성 시 네 필드를 각각 SHA-256으로 해싱한 뒤 결합해
  필드 경계 충돌을 제거했다.
- `subgraph()`의 edge type을 `neighbors()`와 같은 9종으로 확장했다:
  `owns`, `has_event`, `proposed`, `approved`, `contains`, `in_document`,
  `has_issue`, `governed_by`, `handled_by`.

## 추가 검증

- 서로 다른 두 tenant가 동일한 `topic + dedupe_key`로 실제 publish:
  두 publish 모두 성공하고 두 outbox row 및 서로 다른 message id를 확인했다.
- `("ab", "c")`와 `("a", "bc")` 입력이 서로 다른 idempotency key를 만드는지 확인했다.
- `subgraph()`가 최신 9종 edge type을 `neighbors()`에 전달하는지 확인했다.

## 테스트 결과

- 신규/관련 집중 테스트: **3 passed**.
- `tests/security -q`: **3 passed**.
- 요청한 `python -m pytest -q -m "not live"`: **355 passed, 6 failed, 12 errors, 3 deselected**.

전체 실행의 실패·오류는 이번 변경과 직접 관련 없는 환경 문제로 확인됐다. 12개 오류는
pytest 임시 디렉터리(`C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2`)
접근 권한 거부였고, RAG 관련 실패는 OpenAI API 네트워크 차단이었다. 전체 결과 기준은
기존 359 passed이며, 이번 작업으로 재현 테스트 3개가 추가됐다. 보안 테스트와 이번
작업의 DB/단위 검증은 모두 통과했다.
