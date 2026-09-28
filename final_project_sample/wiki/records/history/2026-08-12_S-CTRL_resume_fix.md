# 2026-08-12 S-CTRL resume fix

- `Controller.run_case()`에서 `resuming` 상태를 감지하면 Team 결과 적용 전에 `RESUMED` 이벤트를 발행하도록 수정했다.
- `RESUME_NODE_FOR_WAIT[wait_reason]`으로 재개 노드를 정하고, 재개 TeamTask에 `resume=True`와 노드를 전달한다.
- `app/core/**`, `app/domain/**`, `tests/**` 및 기타 범위 밖 파일은 수정하지 않았다.
- Controller 통합 테스트: `8 passed`.
- 전체 테스트: `104 passed, 3 failed`; 실패 3건은 OpenAI 임베딩 네트워크 차단으로 발생한 기존 RAG 테스트다.
- outbox worker 1회 실행 exit code: `0`; DB 확인: `tenants=1`.
- 상세 리포트: `wiki/records/reports/2026-08-12_S-CTRL_resume수정_리포트.md`
