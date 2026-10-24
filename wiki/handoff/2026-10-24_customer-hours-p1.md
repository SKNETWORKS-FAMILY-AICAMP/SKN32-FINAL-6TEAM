---
type: handoff
title: 고객 운영시간 P1 후속 수정 인계
description: 독립 재현 두 건 수정과 재검증 증거
status: draft
domain: travel
---

# 한 일·범위

- 원본 및 `customer_hours_integration_01`, `customer_hours_delivery_01`, 독립리뷰 원본을 보존했습니다. 새 사본 `customer_hours_integration_02`, 전달물 `customer_hours_delivery_02`만 씁니다.
- 기존 독립 probe를 그대로 재실행하여 2 assertion RED를 확인하고, 프로젝트 정식 `test_intake_customer_hours_p1.py`에 편입했습니다. SQL은 메모리 SQLite뿐이며 실DB 접속을 하지 않습니다.
- 제품 변경은 `intake/stream.py` 완료 item 두 필드 보존과 `watch/dawn_check.py` 공용 휴무 조회의 고객 출처 제외 두 곳입니다. 고객 판정의 해당 항목 처리·기록은 유지합니다.
- 최초완료·confirmed·진행 보관소 없는 재연결, 실제 review.build→Feed.poll, activity/dining 각각 다른고객·같은고객 다른여행·동일여행 다른항목, 공식휴무 공유/tenant·day 경계를 시험합니다.
- `changes.patch`는 **이전 고객시간 결과 tree 위의 P1 후속 차분**입니다. `combined-from-date.patch`는 날짜위험 tree 위 고객시간+P1 차분입니다. 둘을 연속 적용하지 않습니다. manifest의 기준/결과 tree 및 SHA256을 대조하십시오.
- 최종 명령/자식 exit/XML은 delivery `final-results.json`, 원본 probe RED/GREEN 및 정식 RED/중간/GREEN 로그에 있습니다. [후속 보고](../../final_project_cs/wiki/records/reports/2026-10-24_customer-hours-p1.md)에 결과를 추가합니다.

# 남은 일

별도 독립 재검토가 필요합니다. 전체 `scripts.verify_dod_v11`은 이전 startup guard 승인 만료 때문에 실행하지 않으며 재시도/우회하지 않았습니다. 실 PostgreSQL·인증 E2E·운영 브라우저·외부 제공처 확인과 배포/push는 미실행입니다. 선택 관문과 메모리 SQL·웹 단위/build를 이 경계의 통과로 확대하지 않습니다.
