# 2026-08-12 S-RAG 검색 수정 이력

- 검색 질의 임베딩의 `tuple` 변환을 제거하고 `list[float]`로 pgvector psycopg adapter에 바인딩하도록 수정.
- tenant/scope 후보가 없을 때 외부 임베딩 호출 없이 빈 결과를 반환하도록 수정.
- RAG 통합 테스트의 데이터 부재 `pytest.skip` 제거; corpus count 불일치는 실패하도록 변경.
- manifest와 `doc_06`·`doc_14` 원문을 확인했으며 코퍼스는 변경하지 않음.
- DB 실측: `documents=25`, `chunks=300`, `tenants=1`.
- 이 실행 환경의 `api.openai.com:443` 차단으로 최종 테스트는 `75 passed, 3 failed, 0 skipped`; 실패는 질의 임베딩 생성 단계에서 발생.
