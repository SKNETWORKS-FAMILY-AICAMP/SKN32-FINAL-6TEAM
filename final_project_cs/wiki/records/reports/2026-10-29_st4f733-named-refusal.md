---
type: report
title: ST4F-733 뒤 일정 미루기 거절 일정 이름 누락 수정 후보
status: draft
domain: travel
---

# ST4F-733 거절 일정 이름 누락

2026-10-29 KST. 루트·CS 지침, RULE, 양쪽 wiki 목차·역할·코드 경로·현재 접수 계약, 732 최근 보고/인계와 실제 coord NOTICE를 확인했습니다. 변경 담당·시험 작성·자체 검토는 이 Codex 세션입니다. 독립 검토 승인은 없습니다.

TeamFlow page=1/2&limit=100은 같은 100건을 반환했습니다. 페이지 번호가 무시되어 상태4×유형4의 16분할 GET(limit500, 각 응답500 미만)로 중복0·전체688건을 확인했습니다. 미완료102/688 = **14.8%**입니다. 미담당 high/review ST4F-733의 남은 D4 「거절 문장에 걸린 일정 이름」을 골랐습니다. 724(T 후보)·589 지정담당·S3·EKS 및 731/729 보류는 유지했습니다.

## 재현과 수정

보존된 role-manager 커밋 fab3da50ab970a7d8c79ed65c1df2e666abc1cd0을 archive한 새 격리 사본 scratch/teamflow-codefix-20261029/repo에서 작업했습니다. 현재 원격 최신 tip이나 운영 전체와 같다고 주장하지 않습니다. 원본 제품 코드·Git 색인/설정과 다른 작업자 사본은 변경하지 않았습니다.

direct_schedule.fit(forward_only=True)가 운영시간·자정 경계·잠금·예약 여부·예약번호 때문에 거절할 때 일정 이름 없이 일반 문장만 생성합니다. 새 독립 단위 시험5/5 = **100%**가 제목 누락으로 실패했습니다. 초기 설정 누락 오류5건은 별도 보존하며 재현에 세지 않습니다. 새 실DB API 시험도 수정 전1/1 = **100%** 누락 감지: N서울타워 뒤의 광장시장 운영시간에 걸려도 광장시장 이름이 안내에 없습니다.

격리 wiki 계약에 D4 후보를 먼저 적고 실제로 막힌 일정 제목을 거절 문장에 붙였습니다. 마지막 운영시간 검사도 forward_only일 때 해당 이름을 붙입니다. 응답 필드·코드·시각 계산·고정/예약 보호·저장 여부는 그대로입니다. 제품 수정은 direct_schedule.py 한 파일입니다. 시험2개·계약 후보를 포함한 [패치](../evidence/2026-10-29_st4f733-named-refusal/ST4F-733.patch)를 보존했습니다.

## 실행 증거

- 새 단위 + 기존 재배치 시험39/39 = **100%**. 명령: python -m pytest tests/unit/travel/test_push_refusal_stop.py tests/unit/travel/test_intake_direct_schedule.py -q --tb=short.
- 실DB 확장회귀15/16 = **93.8%**. 호텔조식 시험에서 비동기 dining_judge 대기→model_error가 두 조회 사이에 바뀌어 전체 응답 비교 실패. 수정 전 코드로 해당 시험만 재실행해 같은 실패1/1 = **100%** 재현했습니다. 기대값을 바꾸거나 실패를 제외하지 않았습니다.
- 새 API + 기존 push_later 집중회귀6/6 = **100%**. 실제 fit을 실행하고 운영시간 자료만 대역으로 줍니다. 뒤에서 막힌 일정 이름·요청 일정과 구별·같은 revision·저장 건수 불변을 검사합니다.
- ruff F/E9 수정 제품/시험3파일 통과. Starlette deprecated 경고는 원로그에 보존했습니다.

PostgreSQL16.15 새 pgdata/port55536/DB st4f733를 생성하고 current_database·port·data_directory 일치 확인 후 migration·여행 seed·프롬프트 등록을 실행했습니다. 첫 실행은 ACOP_DATABASE_URL 별칭이 이전 격리55532를 가리켜 연결에서 대기했습니다. 이 세션의 해당 시험 자식만 종료하고 별칭 모두 이번 DB로 맞췄습니다. 최초 실행은 migration/시험에 도달하지 않았습니다. 실교통·실모델·운영 화면 수락이 아닙니다.

## 보존과 인계

원시 응답·로그·스크립트·archive·pgdata·초기 실패는 git 밖 scratch/teamflow-codefix-20261029에 보존합니다. 실행 순서: snapshot.py → complete.py → prepare.py → reproduce.py/red.py → fix.py/green.py → create_db_runner.py → db_run.py(별칭 오류) → db_retry.py → verify.py. 같은 출력 이름으로 재실행하지 않습니다.

스캐너·기존 XML 등 보호대상18/18 = **100%** 기존 해시 일치. 증거 수정·추적해제·예외·검사 약화·삭제는 하지 않았습니다. 원본 제품·고객/운영 DB 변경·push·배포는 없습니다.

## 필수 관문과 보류

DoD26/26·계약367/367 = **100%** 통과. 보안은 처음 archive에서 추적 파일0으로 실패했으며 이 결과를 통과나 기존 XML 실패로 세지 않았습니다. 이번 사본에만 전용 Git 저장소·색인을 만들고 추적 경로10,890개(기준 archive와 사본 생성물 포함, 기존 XML 있음)를 확인한 뒤 **동일 스캐너**로 재실행했습니다. 최종 보안124/125 = **99.2%**, 실패는 기존728 security-ready.xml 하나입니다. 필수 관문2/3 = **66.7% HOLD**. 기존 보류를 우회하지 않았으며 통합·커밋·push·배포·이슈 종결0입니다.

호텔조식 기존 실패1건, 보안 XML 실패, 독립 검토·최신 tip 재검증·실제 화면/운영 수락이 남았습니다. 고객 전체 수락 분모는 모릅니다. 전용 PostgreSQL은 정상 종료했고55536 연결 거부를 확인했습니다. pgdata·사본·색인·로그는 보존합니다. [집계](../evidence/2026-10-29_st4f733-named-refusal/summary.json).

최종 TeamFlow 설명만 PUT1회 후 개별 GET·전체688건 재조회:733의 desc/updatedAt만 바뀌었고 review·미담당·나머지687건은 그대로입니다. 종결0·미완료102/688=14.8%. [개별 영수증](../evidence/2026-10-29_st4f733-named-refusal/tracker-receipt.json) · [전체 대조](../evidence/2026-10-29_st4f733-named-refusal/full-readback.json).
