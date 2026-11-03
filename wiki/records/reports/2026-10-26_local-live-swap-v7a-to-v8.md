# 2026-10-26 로컬 live API v7a → v8 교체

- 시각: 02:52 idle 확인(`pre_swap_idle_check.py 10756` RC0 IDLE, 15분 내 활성 접수 0, E4B lease 없음) → v7a `proc_49f94fe8cb2d` 종료(8042 비움 확인) → v8 기동 `proc_221a60572e48`(health 200까지 120초).
- 후보: `cache/scratch/integ-v8-20261026-011529-adebc095/` (v7a + temporal·F02 + Comment9 + I06 booked-only + fix8 + 시험 시계 고정). 합집합 2214/2214, 실E4B 4/4, shadow GET 7/7.
- 교체 후 검증: `runtime-v8/post_swap_verify.py` RC0 `{"status":"PASS","identity":true,"core_get":"14/14","provenance":true,"all_past_guard":"PASS"}`.
- 프런트 3100(v5) 불변.
- 롤백: workdir `action-v7a-allpast-20261025-233317-fac130f7/runtime-v7a-serving`에서 같은 venv python `-B launch-serving.py`.
- 미포함(다음 후보): QA 야외/고른 일정(chat-outdoor·chat-subject, decision_unit/edit_intent 충돌 예상), C02, T09·T10, Dining seeded lookups, 라우팅 P2, 웹 all-past 영문 문구.
- Comment9 고객 rev2 화면은 저장된 검사라 자동으로 바뀌지 않는다(고객 재제출 또는 제품 변경 필요).
