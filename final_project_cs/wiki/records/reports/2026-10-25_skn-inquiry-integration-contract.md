---
type: report
title: SKN pin 문의 의미 통합 계약
status: documented
domain: travel
---

# 문의 통합 계약 (구현 전)

기준은 develop `325ba25d88c91ce97da61f2bda635e5888fe3b40`입니다. 최신 `_desk.weather → read_requests → weather_read`, 시간 anchor/clock, 고객 선택 장소, focus/TTL, card/pick, 승인·tenant·privacy 경계를 유지합니다. D-018 실패 격리와 D-020 승인 규칙은 변경하지 않습니다.

- 질문별 원래 request 사본과 q 순서, 확인 시각, 검증된 target 및 answered/needs_input/failed 종결을 기존 순수 response writer에 연결합니다.
- 실패한 날씨 대상이 하나라도 있으면 그 질문을 answered로 표시하지 않습니다. 다른 질문의 성공·기존 일정은 보존합니다.
- Case basis.response는 내부 근거입니다. 공개 결과와 저장 chat_reply/duplicate/_web_view에는 response_status/question_status enum만 추가합니다. 기존 pick/focus/edit_goal 필드를 보존합니다. developer basis에서는 신규 scope/request 중복을 제거합니다.
- 변경 이유 읽기는 최신 저장판·현재 scoped trip/customer·실제 연결 Case 적용 기록을 재조회합니다. 모호한 대상·과거판·미확인 원인은 확인 요청/실패로 끝내고 변경 실행은 하지 않습니다.
- 파이프라인/계획/감시/프런트/공급자/composition 및 공유 response 코드는 소유하지 않습니다. 공유 계약 수정이 필요하면 부모에게 전달합니다.

RED→GREEN 로그와 현재 고유 nodeid 단일 실행 범위는 프로필 scratch `skn-develop-step1-20261025-014848/evidence/inquiry/`에 남깁니다. DB·외부 네트워크·모델·앱 서비스·배포·커밋·푸시는 실행하지 않습니다. 원본 소스는 수정하지 않고 보고서 추가만 허용합니다.

선행 근거: 원본 root/cs `2026-10-25_skn-pinned-writing-branding-independent.md`, 상위 evidence `report.md`/classification/conflicts, 후보 현재 wiki D-018/D-020. 과거 시험 총합은 현재 결과로 가져오지 않습니다.
