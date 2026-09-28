# 여행 밀도 검증 실행 기록

2026-09-22, Windows / Python, 작업 위치 `final_project_cs`.

```text
python -m pytest tests/unit/travel/test_density.py tests/unit/travel/test_itinerary_checks.py tests/e2e/test_trip_api.py -q -p no:cacheprovider
........................................... [100%]
43 passed in 9.17s
```

최초 실행(캐시 옵션 없음)은 `42 passed, 1 failed, 2 warnings in 12.38s`였다.
실패는 `test_the_whole_day_through_the_api`의 기존 outbox INSERT 중 발생했다:

```text
psycopg.errors.OutOfMemory: out of memory
DETAIL: Failed on request of size 1536 in memory context "CacheMemoryContext".
```

코드 수정 없이 위 명령으로 재실행해 43/43(100%) 통과. 캐시 파일 쓰기 경고는 캐시 비활성화로 제외했다. 중간 Tee-Object 로그 저장 시도는 경로 접근 거부로 실패해 이 파일에 실제 도구 출력을 옮겼다. 장기 DB 메모리 안정성은 검증하지 않았다.

`git diff --check` 종료 코드 0. CRLF 변환 안내만 출력됐다.
