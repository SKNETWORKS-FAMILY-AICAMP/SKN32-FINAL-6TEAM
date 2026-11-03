---
type: report
title: ST4F-732 진행 이벤트 독립 재생 검증
status: draft
domain: travel
---

# ST4F-732 진행 이벤트 검증

2026-10-29 KST. 요청된 인계, 루트/CS AGENTS·RULE, 양쪽 wiki, 역할·코드 경로·웹 접수 SSE 계약을 확인했습니다. 실제 coord NOTICE 전체와 TeamFlow 상태×유형16분할 GET을 시작/종료에 보존했습니다. 미완료102/688 = **14.8%**, 중복0입니다. ST4F724는 T 통합 후보, S3 라우팅·589/597·EKS 기존 담당 영역을 인수하지 않았습니다. 708/727/733/734의 기존 검증을 반복 작업 대상으로 고르지 않고, 미배정 high/review732를 선정했습니다. 담당·시험 작성은 이 Codex 세션입니다. 독립 작성 시험이며 별도 사람/에이전트 검토 승인으로 주장하지 않습니다.

## 격리 환경과 결과

`scratch/teamflow-next-20261029b/repo`는 기존 격리 Git 객체의 커밋 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`을 archive한 새 사본입니다. 원본 코드·색인·다른 작업자 사본을 수정하지 않았습니다. 보류731 패치는 포함하지 않았습니다. 원본/현재 운영 전체와 같다고 주장하지 않습니다.

Node24.22.1·기존 설치 의존성의 junction 참조·사본 전용 cache로 server-progress/intake-events/stream-model 시험45/45 = **100%** 통과했습니다. 별도로 서울의 북촌한옥마을 위험 점검·빈칸 재검사·답 반영 순서를 SSE JSON → parser → reducer → view adapter → 진행 칸까지 통과시키는 시험1/1 = **100%**를 작성했습니다. risks 이벤트 지원을 사본에서만 제거한 변이1/1 = **100%** 실패 감지 후 원본 바이트 복원·동일시험1/1 재통과를 확인했습니다. 기존 단위 기대값만 재실행한 결과와 구분합니다.

새 PostgreSQL16.15 pgdata/port55532/DB st4f732를 만들고 DB명·port·data_directory를 실제 조회로 확인한 뒤 마이그레이션·여행 seed·프롬프트 등록을 실행했습니다. `python -m pytest tests/e2e/test_intake_progress_events.py tests/unit/travel/test_intake_progress.py -q --tb=short`13/13 = **100%**, `tests/unit/travel/test_intake_risks.py`22/22 = **100%**입니다. 이벤트 순서·느린 이동 전 항목 공개·모델 읽기 줄 수·SSE feed 퇴보 방지·listener 유무 결과 일치와 위험 단계 알림을 검사했습니다. Starlette deprecated 경고1개는 원로그에 보존했습니다. 외부 모델·실교통 결과 수락이 아니라 여행 fixture/double 기반 실DB 시험입니다.

## 판정과 보존

새 제품 결함은 재현되지 않아 제품 패치·통합·커밋·push·배포를 하지 않았습니다. 실운영 전체 화면·8초 표시 렌더링·도움말 이미지 수락은 이번에 실행하지 않았습니다. 따라서732를 종결하거나 필수3관문 통과라고 주장하지 않습니다. 현재 이슈는 review 그대로이며 트래커 쓰기0, 시작/종료 전체 객체 차이0입니다.

731 보안 HOLD 필수2/3 = **66.7%**는 그대로입니다. 이전 보호목록18/18 = **100%** 해시 일치, 스캐너·원시XML·보존증거 변경0입니다. 이번 시험을 보안 실패 대체로 사용하지 않았습니다. 고객/공유 DB·운영 자료 쓰기·삭제0입니다. 사본 PostgreSQL은 정상 종료했고55532 연결 거부를 확인했습니다. archive/pgdata/logs/실패 변이/사본은 모두 보존합니다.

[집계](../evidence/2026-10-29_st4f732-independent-progress/summary.json) · [독립 재생 시험](../evidence/2026-10-29_st4f732-independent-progress/independent732.test.ts). 원시 증거·스크립트는 git 밖 `scratch/teamflow-next-20261029b/`에 있습니다. 실행순서는 snapshot.py → prepare.py → create_runners.py → web_run.py/db_run.py → independent.py → risks_run.py → final_snapshot.py입니다. 기존 이름으로 재실행하지 않습니다.

다음 단계는 허용된 브라우저·비고객 시험 계획으로732의 실제 단계 칸·8초 표시·완료 전환을 수락하는 것입니다. 733/734 화면 수락과731 보안 보류를 분리해 유지합니다. 전체 제품 수락 분모는 모릅니다.
