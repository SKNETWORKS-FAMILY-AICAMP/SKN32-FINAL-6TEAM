# 검토 문서 용어 정정 · 2026-10-11

이 기록은 HTML·Markdown·JSON 검토 문서를 고친 결과입니다. 제품 wiki 본문·앱 코드·배포는 변경하지 않았습니다.

- 팀은 에이전트 팀으로 명시했습니다.
- Controller(흐름)·TeamRegistry(담당 선택)·TeamExecutorPort와 LocalTeamExecutor(실행)를 구분했습니다.
- 같은 여행의 여러 일정 문제를 함께 처리하는 WatchBatch와 여행 상태 점검, 개발자·QA 모니터링 도구를 구분했습니다.
- 10월 3일 D-017 결정에 더해 10월 6일 D-CS-013과 현재 watch_planners 등록 구조를 반영했습니다. 세 팀 execute를 연쇄 호출한다고 쓰지 않습니다.
- 이번 용어 정정은 로컬 결정·코드 대조입니다. 앞선 Claude Sonnet 5.5 두 차례 검토 뒤에 수행했으며 이번 문장을 Claude가 다시 검토했다고 주장하지 않습니다.

검사: 화면·선택·근거 링크 13/13 = 100%; 용어·정적 근거 8/8 = 100%; 추출한 그림 자기 검사 2/2 = 100%. 앱 기능 시험·실제 외부 조회·원격 배포 확인은 수행하지 않았습니다.

관련 파일: [검토 HTML](wiki-review-v2.html) · [용어 검사](terminology-validation-v2.json) · [화면 검사](render-validation-v2.json) · [백업](_backup/)
