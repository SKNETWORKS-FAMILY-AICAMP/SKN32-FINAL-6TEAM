# 접수 에이전트의 식사 시간 단서 귀속 수정 — 2026-10-22

## 문제와 범위

고객 입력 `10/23일 홍대가서 쇼핑 후에 근처에서 돈가스 먹고 그 다음엔 저녁으로 라멘`에서 돈가스와 라멘을 모두 18:00으로 배치했다. 고객 의도는 앞 식사가 저녁 라멘보다 먼저라는 것이며, 앞 식사를 점심으로 명시한 것이 아니다.

담당: 이번 작업의 Codex(공통 접수 코드 구현·자체 검증). 매니저·Dining 영향을 확인했으나 독립 검토 완료로 표시하지 않는다. 공유 API·DB 스키마·모델 프롬프트·입출력 필드는 바꾸지 않는 내부 결함 수정이다. 전체 개선 중 1순위 시간 단서 분리만 이번에 수정했다.

## 수정

`pipeline._agent_rows`가 항목 원문을 '장소명부터 다음 장소명 직전까지'로 잘라 저장하던 로직을 기존 `span_segments.split_segments` 사용으로 교체했다. 이 함수는 다른 접수 경로와 조립에서도 이미 쓰며, 연결어 뒤의 다음 일정 시각·끼니 단서를 다음 장소 구간에 둔다. 원문 인용 좌표와 실제 부분 문자열을 보존한다.

점심을 강제하는 규칙을 추가하지 않았다. 시각을 명시하지 않은 앞 식사는 기존 기본 배치 정책에 따른다. 이번 입력에서는 돈가스가 12:00~13:00, 저녁 라멘은 18:00~19:00이 된다. 이 12시는 원문에서 추출한 사실이 아니다.

## 검증

- 신규 회귀 4건: 수정 전 1/4 = 25% 통과(3건 실패), 수정 후 4/4 = 100% 통과. 원문 및 연결어·점심 명시 변형, 직접 적은 11:00·13:00·19:00 보존을 확인한다.
- 로컬 role-dining 작업 폴더: 관련 7개 파일 79/79 = 100% 통과.
- 최신 origin/develop `95949d3ef`, origin/role-manager `52873e768`의 app·config 및 관련 시험을 각각 git archive 사본으로 추출. 신규 시험이 두 브랜치 모두 수정 전 3건 실패·1건 통과함을 확인한 뒤 같은 코드 수정 적용. 각 브랜치 관련 7개 파일 85/85 = 100% 통과.
- 최신 브랜치 사본 시험은 `--noconftest`로 실행하고 필수 설정은 테스트용 가짜 값으로 지정했다. 실제 DB·모델·외부 API 호출 없는 코드 경로 검증이다. 모델 출력은 원문에서 정확히 인용한 3개 항목으로 고정했다.
- 로컬 변경 파일 ruff F·E9 통과.
- 대상 시험: test_intake_agent_meal_order, test_intake_agent_read, test_intake_agent_booking, test_intake_span_segments, test_intake_span_pipeline, test_intake_span_ownership, test_intake_direct_schedule.

## 산출물과 남은 작업

- 최신 매니저 적용용 패치: 루트 `output/hongdae_branch_audit_20261022/meal-order-fix-role-manager.patch`.
- 최신 브랜치별 증거: 같은 폴더 develop·role-manager의 meal-order-red.txt, meal-order-green.txt, meal-order-related.txt.
- 기존 pipeline 백업: 루트 `_backup/2026-10-22_intake-meal-order/pipeline.py`.
- 로컬 작업 파일만 수정했다. 브랜치 전환·커밋·푸시·배포하지 않았다. 따라서 실서비스에서는 여전히 재현될 수 있다.
- 나머지 우선순위인 대체 추천의 메뉴 조건 계약·유지, 조회 차단 원인, 선택 후 경고 안내는 이번 수정으로 해결되지 않았다. 앞선 Dining 메뉴 표기 로컬 수정도 보존했다.
