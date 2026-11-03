# v6 intake 동일 owned fixture 차이 확정 인계

**authentry PASS / intake core match=true / full parity=false.** 승인 추가 GET localhost/LAN 2/2=100% HTTP200·CORS 일치. 유일한 차이는 `/review/items/0/risk/checked_at`, `/review/items/1/risk/checked_at`, `/review/risk_checked_at`입니다. cached review의 요청별 risk 관측시각 장식이 원인입니다. 위3 pointer 외 전체 JSON 일치, 업무11표 변경0, 승인 session last_used_at 1행만 touch, v6 PID24140·모델 counters0 유지. 추가 GET 재실행하지 않습니다. 기존 FAIL 미수정, 과거 shared-live body 부재의 소급 확정 한계 유지.

[상세 보충 report](../../../wiki/records/reports/2026-10-25_v6-intake-diff-closeout-child.md)

실 diff 및 최종 분류: 프로필 scratch `action-v6-20261025-172901-05e642d6/runtime-v6-serving/intake-diff-closeout-20261025/{difference,closeout}.json`. 원문 응답 저장0. 코드/sharedschema/고객state 변경0, 모델/paid/kill/restart0.
