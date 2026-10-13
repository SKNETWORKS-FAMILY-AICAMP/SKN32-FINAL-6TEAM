# W18 적용 근거와 검토 범위

2026-10-11 공식 원문4개를 직접 열어 확인하고 HTML 원문·URL·회수 시각·SHA256을 [sources.json](references/w18/sources.json)에 저장했습니다. 공식 자료가 보장하는 성질과 프로젝트에 적용한 판단을 구분합니다.

| 적용 판단 | 공식 근거 | 프로젝트 코드로 확인한 사실 |
|---|---|---|
| 기존 단일 기계 Compose 운영을 바탕으로 절차를 정리 | [Docker production](https://docs.docker.com/compose/how-tos/production/) | `deploy/docker-compose.yml`의 공개 배포 서비스4개. 현재 원격 가동은 이번에 확인 안 함 |
| 기동과 준비를 구분 | [Docker startup order](https://docs.docker.com/compose/how-tos/startup-order/) | DB healthcheck, API 이미지의 `/health`, worker의 API healthy 의존. API `/health`는 정적 응답 |
| 종료 복구와 기능 정상 여부를 구분 | [Docker restart](https://docs.docker.com/engine/containers/start-containers-automatically/) | 공개4개 서비스 `unless-stopped`, worker healthcheck 비활성. unhealthy 자체의 자동 재시작을 추정하지 않음 |
| 고객 증상과 내부 원인을 함께 기록 | [Google SRE monitoring](https://sre.google/sre-book/monitoring-distributed-systems/) | 공개worker는 직접 호출 후60초 대기. 로컬tick의 heartbeat·경보 경로를 통과하지 않음 |

**프로젝트 적용 판단:** 기존 Compose를 유지하는 A안은 문서·절차 정리에 대한 추천입니다. 새 상시 계측·준비 검사·자동 복구를 구현·배포했다는 뜻이 아닙니다. 특정 클라우드·Kubernetes·새 모니터링 제품 도입을 공식 필수 요건으로 만들지 않았습니다. 주기·시간 임계값은 우리 제품의 측정과 위험으로 정해야 합니다.

Claude Sonnet5.5는 [비밀값 없는 요약](claude-review/commerce-w18-request-v6.txt)만 읽고 [설계 검토](claude-review/commerce-w18-response-v6.md)를 했습니다. 실제 저장소·코드·고객 데이터·원격 프로세스를 읽은 검토가 아닙니다. 현재 관측과 문서 개선, worker 계측 공백, 결과unknown의 후속 책임을 구분하라는 지적은 반영했습니다. 다만 ‘529개 전부 새 임시DB 시험’이라는 추정과 ‘현재 자동 감지가 전혀 없다’는 확대 해석은 채택하지 않았습니다. 실제529개는 구조·계약·보안·단위 시험 묶음이며, 임시 새DB 생성 검사는 통합98개 중 해당 DB 시험입니다. 기존 적체 점검 도구의 존재와 공개worker 회차 heartbeat 부재도 구분했습니다.

기존 업무DB 잔존 표를 이번에 삭제·조사 완료로 표시하지 않습니다. 현재 runner의 새 설치 생성 차단과 기존 업무DB 현황은 별도입니다. 과거 SQL 바이트는 보존하며 모든 SQL을 매번 재실행하는 runner의 이력 장부 개선은 별도 검토 대상입니다.
