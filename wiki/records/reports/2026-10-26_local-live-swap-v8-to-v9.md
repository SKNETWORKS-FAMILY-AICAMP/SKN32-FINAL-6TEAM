# 2026-10-26 로컬 live API v8 → v9 교체

- 04:18 idle 확인(`runtime-v9/pre_swap_idle_check.py 28392` RC0 IDLE, 8042 연결 0, 15분 내 활성 접수 0) → v8 `proc_221a60572e48` 종료 → v9 기동 `proc_56306ecfe547`(health 200까지 80초).
- 후보: `cache/scratch/integ-v9-20261026-025943/` = v8 + QA 야외·고른 일정(+근처기준 guard 53c3c273분) + C02 + T09·T10 + Dining seeded lookups + 라우팅 P2. 합집합 2848/2848(DB 필요 168 미실행, 통과로 세지 않음), 실E4B 6/6, shadow GET 7/7.
- 교체 후 검증: `runtime-v9/post_swap_verify.py` RC0 `{"status":"PASS","identity":true,"core_get":"14/14","provenance":true,"all_past_guard":"PASS"}`.
- 롤백: workdir `integ-v8-20261026-011529-adebc095/runtime-v8-serving`에서 같은 venv python `-B launch-serving.py`.
- 미포함: role-manager da4ccd97(실내·야외 되묻기 후보), T16 고정 일정 보호, 전부과거 계획담기 가드, U01 미지원 안내.
- 프런트 3100(v5) 불변.
