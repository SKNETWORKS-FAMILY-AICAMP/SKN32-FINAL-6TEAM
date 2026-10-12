---
type: report
title: 최초 분류·라우팅 실패의 운영 진단 연결
status: draft
domain: travel
---

# 최초 분류·라우팅 실패의 운영 진단 연결

고객 접수·분류 재시도·여행 대화의 분류 실패와 담당 라우팅 실패를 운영 진단 콜백에 연결했습니다. 관련 선택 시험 268/268 = 100% 통과이며 최신 제품 전체 인수 결과는 아닙니다.

새 고객 접수는 생성 커밋을 먼저 끝내 독립 진단 연결에서도 Case를 찾을 수 있게 합니다. 기존 Case의 분류 되잡기·사실 질문 후속 처리도 같은 분류 함수의 주입 경계를 사용합니다. 고객 번호가 생략된 내부 호출은 조립에서 tenant와 Case로 확인한 고객만 연결합니다. 재배분 성공은 실패로 세지 않고 최종 담당 미확정과 비활성 팀은 각각 고정 코드로 기록합니다.

콜백에는 tenant·고객·Case UUID와 고정 코드만 전달합니다. 고객 문장·예외 본문은 전달하지 않습니다. 수집 오류가 원래 분류 결과나 라우팅 예외를 가리지 않으며 `collection_degraded`로 드러납니다. 기존 분류 로깅의 본문 보존 정책 전체를 바꾼 작업은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 분류·Controller·진단·구조 선택 시험 | 통과 | 268/268 = 100% |
| 실행 중 소스 일치 | 확인 | 1/1 = 100% |
| 전용 PostgreSQL 종료 | 확인 | 1/1 = 100% |

- [JUnit 원본](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_055733_173846_isolated_integration/junit.xml)
- [실행·해시·외부 연결 차단 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_055733_173846_isolated_integration/result.json)
- [전용 DB 종료](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_055733_173846_isolated_integration/cleanup.json)
- [변경 전 백업](../../../_backup/2026-10-12_0558_initial_diagnostics/)

최초 선택은 존재하지 않는 시험 파일 경로 때문에 수집0개로 종료했습니다. 해당 실패 원본은 별도 실행 폴더에 보존했고 통과 수에 넣지 않았습니다. 최신 전체 공통·여행 및 외부 개인 AI 종단 연결·운영 볼륨 인수·업무 DB 적용은 별도입니다.

mock 서버 시험(화면 반응): 이번 실행은 화면 시험이 아닙니다.

실서버 확인(서버 응답): 외부 제공처·운영 cs 프로젝트 서버는 확인하지 않았습니다. 격리 PostgreSQL만 실행했습니다.
