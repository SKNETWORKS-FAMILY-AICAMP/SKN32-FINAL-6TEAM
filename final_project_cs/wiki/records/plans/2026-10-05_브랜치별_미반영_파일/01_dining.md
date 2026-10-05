# 로컬이 본 적 없는 내용 — 식당(요식) 담당 세션

작성: commit 세션 · 2026-10-05 · hwansj 의 식당 원장·대체 식당·일정 접수 변경 등

**무엇인가.** 팀 저장소의 다른 브랜치(머리 해시는 [00_안내.md](00_안내.md))에 있는 파일 중, 우리 로컬이 **그 내용을 한 번도 가진 적이 없는** 것의 목록이다. 내용이 다르다는 뜻일 뿐 기능이 없다는 뜻은 아니다 — 우리가 다른 모양으로 이미 구현했을 수 있다.

**할 일(담당 세션).** 줄마다 상대 내용을 **읽어서** 우리 쪽보다 **더 잘 만든 것만** 로컬에 반영한다(우리 설계가 기준이다 · 2026-10-05 사용자 정정). 반영한 줄에는 「반영」, 일부만 가져왔으면 「일부 반영」, 우리 쪽이 더 낫거나 같은 일을 이미 하면 「제외」, 아직 못 읽었으면 비워 두고 이유를 적는다. **판정 · 이유 칸을 이 표에 직접 적는다.** develop 은 읽기만 한다(푸시 · 머지 · 리베이스 금지).

| 파일 | 종류 | 이 내용을 가진 브랜치 | 마지막으로 바꾼 커밋(브랜치 · 작성자 · 날짜 · 제목) | 판정 | 이유 |
|---|---|---|---|---|---|
| `datasets/dining/REPORT.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/infrastructure/db/migrations/201_dining_core_link.sql` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/infrastructure/db/migrations/212_dining_notice.sql` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 09-28 · [chore] 요식 마이그레이션을 200 대로 — develop 020~030 과 겹치지 않게 |  |  |
| `final_project_cs/app/infrastructure/db/migrations/220_dining_runtime_link.sql` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/modules/travel_ops/dining/ledger.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/app/modules/travel_ops/dining/nearby.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/dining/place_lookup.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/app/modules/travel_ops/dining/team.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/modules/travel_ops/dining/tick.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 09-23 · [feat] 깨어났을 때 할 일 — tick_once |  |  |
| `final_project_cs/ml/dining_similarity.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [chore] 요식 데이터를 datasets/dining/processed 로 — git 밖에 두고 경로는  |  |  |
| `final_project_cs/scripts/dining/check_dining.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [chore] 요식 데이터를 datasets/dining/processed 로 — git 밖에 두고 경로는  |  |  |
| `final_project_cs/scripts/dining/rebuild.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 09-30 · [feat] 구글 미연결 시트를 연결 · 폐업 시트로 옮긴다 — cid 가 같을 때만, 사람이 고른 링크는  |  |  |
| `final_project_cs/tests/e2e/test_trip_dining_ledger.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/tests/integration/dining/conftest.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 09-28 · [chore] 요식 마이그레이션을 200 대로 — develop 020~030 과 겹치지 않게 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_alternative_opening.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_closed_place.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_find_by_name.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_nearby.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_runtime_link.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/tests/integration/dining/test_dining_slot_verdicts.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/tests/scenario/test_dining_needs_check.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_alternative_opening.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_ledger.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_nearby_fallback.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_payment_preference.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_price_tier.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 웹 일정 항목에 식당 가격 비교를 싣는다 — 고른 곳과 다른 안마다 같거나 쌈 · 더 비쌈 ·  |  |  |
| `final_project_cs/tests/unit/travel/test_dining_registration_check.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/tests/unit/travel/test_dining_review_fixes.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/tests/unit/travel/test_intake_resolve_dining.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/tests/unit/travel/test_planner_dining_ledger.py` | 새 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/wiki/teams/dining-core-handoff.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 요식 설문 · 폐업/빈칸/구글 연결 SQL 생성기 · 원장 내보내기 스크립트 |  |  |
