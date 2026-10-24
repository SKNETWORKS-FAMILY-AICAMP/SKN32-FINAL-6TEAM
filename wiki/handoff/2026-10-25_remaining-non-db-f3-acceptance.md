---
type: guide
title: F3 독립 설계·회귀 수락 인계
description: 새 격리 후보와 원문 보존·시험 모순 분리·외부 실행 금지 경계
status: draft
tags: [release, documentation]
domain: neutral
---

# 한 일과 남은 일

- 새 `remaining_non_db_f3_acceptance/repo`에서 old/new 실제 코드와 원문·타임라인을 독립 비교했습니다. 제품 코드는 이전 진단 tree와 동일하며, 원문 probe는 고치지 않았습니다.
- `test_llm_f3_acceptance.py`를 추가하여 동일 schedule에서 old의 paid 호출 RED와 new의 paid 0 GREEN을 실제 확인했습니다. worker 완료 장벽은 유료 호출을 요구하지 않습니다.
- publication/claim·최초 provider 진입·winner 보존·예외·permit/inflight 회수·bool 예산 한계를 검토했습니다. 원문의 3건 실패를 제품 미해결과 구분하며 실패 로그를 보존합니다.
- [정본 검증 보고서](../../final_project_cs/wiki/records/reports/2026-10-25_remaining-non-db-f3-acceptance.md)와 [루트 연결 기록](../records/reports/2026-10-25_remaining-non-db-f3-acceptance.md)에 최종 단일 실행 분모를 기록합니다.
- 새 patch만 scoped 승인 검토 대상입니다. 이전 `diagnostic-not-accepted.patch`는 계속 미수락 원본입니다. 원본 적용·commit/push/배포·DB·실모델·외부 API·서비스 시작 승인이 아닙니다.
- 남은 일: 기존 4개 bind 차단의 실제 전송 검증, 실 provider/DB accounting 및 물리 취소는 미확인입니다. DB는 다른 라이팅 세션 소유입니다. `paid_called.wait`와 paid-zero를 동시에 만족시키는 것은 제품 수정 목표가 아닙니다. 원문을 GREEN으로 위장하지 않습니다.
