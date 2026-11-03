---
type: report
title: 2026-10-25 Comment9 구역별 방문 제한시간 vs 날짜 휴무 (후보 수정)
status: candidate-only
domain: travel
---

# Comment9 — 방문 제한시간을 휴무로 오표시하는 문제

결론: 후보(scratch)에서 `intake/hours.py::_settle_stored_conditions` 한 곳을 고쳐 정확 사례 RED→GREEN. 신규+기존 35/35 = 100%. 부모 live 미반영, 본 고객 저장판 재검토 미실행, 넓은 회귀 n/m 미측정.

- 원인: "쉬는 날: 연중무휴"(라벨)과 "방문 제한시간 … 17:00~익일 10:00"(시간대 제한)을 휴무 규칙이 모름으로 읽어 조건이 남고, `review._hours_and_closed` 가 closed ok 를 warn 으로 덮음.
- 수정: 라벨 제거 후 같은 규칙 재질의 + 방문 시각과 안 겹침이 확정된 제한시간만 조건에서 빼고 원문은 `tips` 안내로 보존. 겹침·모호는 기존처럼 남김. 하드코딩 0, 폴백 신설 0.
- 등록 차단: closed warn 은 item status/needs/ready 에 불참(코드 읽기). 대체 후보 `fits` 에만 영향.
- 한계: 겹침 시 문구에 "휴무" 표현 잔존(review.py 몫), 회귀 미완료.
- 증거·패치·SHA·시험 기록: `%LOCALAPPDATA%/hermes/profiles/guguroute/cache/scratch/claude55-support/comment9-sonnet/` (REPORT_KO.md, product.patch, SHA256.txt, junit_*.xml, run_pytest.sh).
- 다음 구간(새 child 세션 인계): ① hours/closure 관련 회귀 전체를 DB 없는 파일만 골라 n/m 측정 ② 겹침 시 문구 분리 검토 ③ 부모 승인 하에 배포·고객 건 재계산.
