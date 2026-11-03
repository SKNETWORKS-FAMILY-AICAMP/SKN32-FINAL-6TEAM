---
type: contract
title: 알림 이후 읽기 전용 변경 설명
status: draft
domain: travel
---

# 변경 설명 읽기 계약

2026-10-24. conversation 변경 설명 child 소유. 공통 응대 작성기·공개 API·감시/실행기는 변경하지 않습니다. 독립 검토·운영 승인은 별도입니다.

- 기존 의미 해석기의 `answer_fact`에 `change_explanation` 사실 종류를 추가합니다. 단어 목록으로 분류하지 않습니다. `reads`의 `target_change`는 서버가 제시한 변경 별칭 또는 none이며, `reference`는 기존 explicit/selection/previous/none입니다. 모델은 저장된 변경을 고를 뿐 새 쓰기 권한을 받지 않습니다.
- 명시한 변경판과 일정, 화면에서 고른 일정, 유효한 구조화 직전 대상만 사용합니다. 모델이 최근 변경을 추측했거나 변경이 여러 개면 먼저 재질문합니다. 자동 최신 변경 선택은 하지 않습니다. 직전 대상은 기존 설정 TTL·현재 여행 포함·현재 판을 검증하며 만료/판변경 뒤 다른 대상으로 바꾸지 않습니다.
- 기존 `itinerary_versions`의 원인·생성 시각과 전후 `itinerary_items`, 연결된 `customer_cases.state_json.applied_actions`만 읽습니다. 새 표·LLM 호출·업체 승인·업무 재실행·새 outbox는 없습니다. 문의 Case 자체의 기존 생성·분류·종결 기록은 유지합니다.
- tenant/trip/customer 범위를 현재 TripStore 결과와 대조합니다. 연결 Case는 저장된 버전의 case_id로만 읽고 tenant/customer를 SQL과 반환값에서 확인합니다. applied result_ref가 정확히 그 trip/판일 때만 적용 근거로 인정합니다. 타고객/타trip 기록은 답변에 쓰지 않습니다.
- 답은 전후 이름·시각·기준판·저장 이유·원인에 기록된 source 및 checked_at/confirmed_at를 표시합니다. 버전 생성 시각과 원인 자료 확인 시각은 구분합니다. 출처나 시각이 없으면 근거 부재를 명시하고 모델 상식으로 보충하지 않습니다.
- 공통 응대에 원래 질문/근거/판/읽기 전용 execution을 공급합니다. 미지정·복수·만료·판변경은 needs_input, 원인 출처/시각 부재는 failed로 partial입니다. 이미 저장된 설명의 재전송은 기존 duplicate 결과를 사용하고 변경 업무를 다시 실행하지 않습니다.
- 신규 읽기는 현재 정상 `handle_trip_message` 경로의 격리 unit으로 RED→GREEN 검증합니다. 실DB·외부 LLM/HTTP·앱/서비스 시작·배포·커밋/푸시는 범위 밖입니다. 기존 302 문의·기상 회귀 목록을 재사용합니다.

구현·실제 시험 결과: [cs 고유 보고서](../records/reports/2026-10-24_change-explanation.md). 계약 먼저 작성했으며 결과 보고서는 검증 뒤 추가합니다.
