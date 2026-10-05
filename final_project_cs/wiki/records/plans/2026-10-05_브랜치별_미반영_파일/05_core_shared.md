# 로컬이 본 적 없는 내용 — 코어·공통 담당 세션(cs 프로젝트)

작성: commit 세션 · 2026-10-05 · 여러 영역에 걸친 서버 코드 · DB 마이그레이션 · CI · 설정 · 시험 · 기록 문서

**무엇인가.** 팀 저장소의 다른 브랜치(머리 해시는 [00_안내.md](00_안내.md))에 있는 파일 중, 우리 로컬이 **그 내용을 한 번도 가진 적이 없는** 것의 목록이다. 내용이 다르다는 뜻일 뿐 기능이 없다는 뜻은 아니다 — 우리가 다른 모양으로 이미 구현했을 수 있다.

**할 일(담당 세션).** 줄마다 상대 내용을 **읽어서** 우리 쪽보다 **더 잘 만든 것만** 로컬에 반영한다(우리 설계가 기준이다 · 2026-10-05 사용자 정정). 반영한 줄에는 「반영」, 일부만 가져왔으면 「일부 반영」, 우리 쪽이 더 낫거나 같은 일을 이미 하면 「제외」, 아직 못 읽었으면 비워 두고 이유를 적는다. **판정 · 이유 칸을 이 표에 직접 적는다.** develop 은 읽기만 한다(푸시 · 머지 · 리베이스 금지).

| 파일 | 종류 | 이 내용을 가진 브랜치 | 마지막으로 바꾼 커밋(브랜치 · 작성자 · 날짜 · 제목) | 판정 | 이유 |
|---|---|---|---|---|---|
| `.github/workflows/ci-develop.yml` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-30 · chore(deps): requirements 를 final_project_cs 의 파일 하나로 되돌리고,  |  |  |
| `.github/workflows/ci-web.yml` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-28 · feat(ci): 웹 시험을 CI에 올린다 — ci-web.yml(check·e2e·live)과 웹↔서버 계 |  |  |
| `.gitignore` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · changlike · 10-01 · chore: TourAPI 상세 이어받기 캐시(tourapi_details_cache.jsonl)를 giti |  |  |
| `README.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-30 · chore(deps): requirements 를 final_project_cs 의 파일 하나로 되돌리고,  |  |  |
| `final_project_cs/.env.apikeys.example` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/.gitignore` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 10-01 · chore: gitignore에 docker/ 및 dev.log 추가 |  |  |
| `final_project_cs/RULE.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/app/application/classification.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/app/composition.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · changlike · 10-02 · feat(activity): 장소 이름 조회·카카오 존재 확인 추가, 성립 판정의 정보 부족 확장 |  |  |
| `final_project_cs/app/core/settings.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/infrastructure/notify/ops_alert.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 대체 식당을 구글 가격(1인당 범위 · 가격대)으로 세운다 — 가격을 몰라도 떨어뜨리지 않고,  |  |  |
| `final_project_cs/app/infrastructure/travel/base.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-28 · feat(travel): 고객 계획 읽기 1~3주차 · 버스 노선 표기 · 사용자 웹 전환(role-eval |  |  |
| `final_project_cs/app/infrastructure/travel/call_budget.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 대체 식당을 구글 가격(1인당 범위 · 가격대)으로 세운다 — 가격을 몰라도 떨어뜨리지 않고,  |  |  |
| `final_project_cs/app/infrastructure/travel/catalog_sync.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-28 · feat(travel): 고객 계획 읽기 1~3주차 · 버스 노선 표기 · 사용자 웹 전환(role-eval |  |  |
| `final_project_cs/app/infrastructure/travel/disaster_msg.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-30 · fix(disaster): 재난문자 near() 좌표로 자치구 특정 |  |  |
| `final_project_cs/app/infrastructure/travel/google_places.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 대체 식당을 구글 가격(1인당 범위 · 가격대)으로 세운다 — 가격을 몰라도 떨어뜨리지 않고,  |  |  |
| `final_project_cs/app/infrastructure/travel/tour_api.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-28 · feat(frontend): 사용자 웹 — 내 여행 목록·마이페이지·키 재발급·실서버 연결 · 채팅 답·영업 |  |  |
| `final_project_cs/app/modules/travel_ops/dawn_check.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/intake/assemble.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/app/modules/travel_ops/intake/pipeline.py` | 고친 파일 | develop, role-activity, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/app/modules/travel_ops/intake/places.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 일정 접수 — 식당은 요식 원장에서 먼저 찾는다 · 분류 실패 원인을 로그로 남긴다 |  |  |
| `final_project_cs/app/modules/travel_ops/itinerary.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/itinerary_changes.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/itinerary_checks.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/app/modules/travel_ops/itinerary_team.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/modules/travel_ops/pending.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/modules/travel_ops/planner.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/app/modules/travel_ops/replan.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/trip_api.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 10-03 · fix(ci): 접수 시험을 활동팀의 장소 확인 변경에 맞추고, 오류 함수의 status 이름 겹침을 고친다 |  |  |
| `final_project_cs/app/modules/travel_ops/trip_desk.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 대체 식당 후보를 원장에서 들여놓는다 · 카드 가능 여부는 참고로만 보여 준다 |  |  |
| `final_project_cs/app/modules/travel_ops/trip_messages.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/modules/travel_ops/trip_replies.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/app/tools/read_tools.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · kimji9663 · 10-03 · feat(activity): 대체 장소 근처를 시군구 대신 반경(km)으로 재고, 노출 3곳 + 더보기 10 |  |  |
| `final_project_cs/bash.exe.stackdump` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-21 · feat: add role-activity initial project structure |  |  |
| `final_project_cs/config/guardrails.yaml` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-29 · feat(web): 모델 미리 깨우기(POST /v1/web/warmup) — develop CI 실패 해소 |  |  |
| `final_project_cs/frontend/README.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/frontend/UI_EVAL_WORKSPACE.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/pytest.ini` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-21 · feat: add role-activity initial project structure |  |  |
| `final_project_cs/requirements.txt` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-30 · chore(deps): requirements 를 final_project_cs 의 파일 하나로 되돌리고,  |  |  |
| `final_project_cs/scripts/fetch_tourapi_list.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · changlike · 09-29 · feat(activity): TourAPI 서울 전체 목록 수집·추가 스크립트 |  |  |
| `final_project_cs/scripts/geocode_vworld.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · changlike · 09-29 · feat(activity): V-World 지오코더로 빈 좌표를 채우는 스크립트 추가 |  |  |
| `final_project_cs/scripts/merge_tourapi_new.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · changlike · 09-29 · data(activity): 쓰지 않는 열 6개 삭제 (data_source·event_period·tel· |  |  |
| `final_project_cs/scripts/run_sweepers.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · changlike · 10-02 · feat(activity): 활동 재난문자 감시를 sweepers 에서 돌리는 러너 추가 |  |  |
| `final_project_cs/scripts/run_tests_local.ps1` | 새 파일 | develop, role-dining | develop · hwansj · 10-01 · [feat] 대체 식당도 원장으로 판정한다 — 방문 시간대 영업 · 확인 필요 경고 · 판정 때 장소 잇기 |  |  |
| `final_project_cs/scripts/verify_disaster_api.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-28 · fix(lint): F401 미사용 import 제거 — ruff clean |  |  |
| `final_project_cs/tests/contract/test_api_key_file.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-04 · [fix] API 키 템플릿 시험 — _CLIENT_ID · _SECRET 도 비밀로 본다 (네이버 검색 키 |  |  |
| `final_project_cs/tests/contract/test_web_client_contract.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-28 · feat(ci): 웹 시험을 CI에 올린다 — ci-web.yml(check·e2e·live)과 웹↔서버 계 |  |  |
| `final_project_cs/tests/e2e/test_trip_intake_api.py` | 고친 파일 | develop, role-activity, role-dining | develop · Your Name · 10-03 · fix(ci): 접수 시험을 활동팀의 장소 확인 변경에 맞추고, 오류 함수의 status 이름 겹침을 고친다 |  |  |
| `final_project_cs/tests/e2e/test_trip_planner.py` | 고친 파일 | develop, role-dining | develop · hwansj · 10-02 · [feat] 식당은 요식 원장으로 — 생성기 후보·판정과 등록 판정을 원장 하나로 맞춘다 |  |  |
| `final_project_cs/tests/integration/api/test_openapi_surface.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · fix(test): 웹 예열 API를 계약 검사 목록에 반영 |  |  |
| `final_project_cs/tests/integration/db/test_place_by_name_db.py` | 새 파일 | develop, role-activity, role-dining | develop · changlike · 10-02 · feat(activity): 장소 이름 조회·카카오 존재 확인 추가, 성립 판정의 정보 부족 확장 |  |  |
| `final_project_cs/tests/integration/db/test_place_candidates_db.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · kimji9663 · 10-03 · feat(activity): 대체 장소 근처를 시군구 대신 반경(km)으로 재고, 노출 3곳 + 더보기 10 |  |  |
| `final_project_cs/tests/scenario/test_dawn_check.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · hwansj · 09-30 · [feat] 대체 식당을 구글 가격(1인당 범위 · 가격대)으로 세운다 — 가격을 몰라도 떨어뜨리지 않고,  |  |  |
| `final_project_cs/tests/unit/travel/customer_travel.json` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-21 · feat(activity): 고객일정 검증 테스트 + 데모 러너 추가, 신분류체계 place_catalog  |  |  |
| `final_project_cs/tests/unit/travel/test_csv_place_lookup.py` | 새 파일 | develop, role-activity, role-dining | develop · Jihye · 10-01 · fix(test): remove unused pytest import to pass ruff F401 lin |  |  |
| `final_project_cs/tests/unit/travel/test_db_search_place_candidates.py` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · kimji9663 · 10-03 · feat(activity): 대체 장소 근처를 시군구 대신 반경(km)으로 재고, 노출 3곳 + 더보기 10 |  |  |
| `final_project_cs/tests/unit/travel/test_evidence_accumulates.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-28 · feat(activity): _check_feasible 구 아키텍처 복원 + submit_itinerary |  |  |
| `final_project_cs/tests/unit/travel/test_fill_tourapi_details.py` | 새 파일 | develop, role-activity, role-dining | develop · changlike · 10-01 · feat(activity): TourAPI 상세 수집에 인원·예약 확인용 컬럼 6개 추가 |  |  |
| `final_project_cs/tests/unit/travel/test_weather_warning_and_advisory.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Jihye · 09-29 · feat(activity): CSV 로컬 장소 조회 추가 + 재난문자 필드명 수정 |  |  |
| `final_project_cs/wiki/external/admin-screen-api.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/external/auth-boundary.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/external/index.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/external/rest-api.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/external/rest-endpoints.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/external/web-screen-api.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · fix(web): 리뷰 결함 수정과 알림·채팅 합의 반영 |  |  |
| `final_project_cs/wiki/index.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 10-01 · docs: 웹 develop 통합 검증과 기존 실패 근거 기록 |  |  |
| `final_project_cs/wiki/log.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_0909_role-eval-ui_develop_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(git): role-eval-ui 최신화 검증 기록 보존 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_1014_웹목업_분리.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(frontend): 목업 정리 CI 결과와 기존 계약 실패를 기록한다 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_1228_UI웹_원본문서_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_1436_웹API_협업문서_정리.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_2114_role-eval-ui_develop_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_2313_admin_프론트와_HTML_시나리오.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-29_2352_admin_공유와_API협의_진입점.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-30_0017_admin_CI와_develop_공유.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · ci(admin): 병합 보안 검사와 공유 검증 근거 추가 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-30_0044_warmup_API_계약시험_누락.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · fix(test): 웹 예열 API를 계약 검사 목록에 반영 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-30_1032_웹리뷰_검증.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · Choi-Sangwook · 09-30 · fix(web): 리뷰 결함 수정과 알림·채팅 합의 반영 |  |  |
| `final_project_cs/wiki/records/evidence/2026-09-30_1231_알림폴링_채팅안내_검증.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · Choi-Sangwook · 09-30 · fix(web): 리뷰 결함 수정과 알림·채팅 합의 반영 |  |  |
| `final_project_cs/wiki/records/evidence/2026-10-03_0030_온보딩_알림복구카드_이식_검증.md` | 고친 파일 | feat/web-manager-integration | feat/web-manager-integration · Choi-Sangwook · 10-03 · feat(web): 온보딩 알림·복구 카드를 옮기고 웹훅 입력·검사 추가 |  |  |
| `final_project_cs/wiki/records/evidence/2026-10-03_0405_웹_SSE진행_웹훅_연결_검증.md` | 고친 파일 | feat/web-manager-integration | feat/web-manager-integration · Choi-Sangwook · 10-03 · feat(web): 실시간 진행(SSE)·디스코드 웹훅 연결과 계획 확인 화면 목업 전체 구현 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_0909_role-eval-ui_develop_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(git): role-eval-ui 최신화 검증 기록 보존 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_1014_웹목업_분리.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(frontend): 목업 정리 CI 결과와 기존 계약 실패를 기록한다 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_1228_UI웹_원본문서_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_1436_웹API_협업문서_정리.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): 문서 통합 전 검증 결과를 기록한다 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_2114_role-eval-ui_develop_최신화.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_2313_admin_프론트와_HTML_시나리오.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_2340_role-manager_운영백엔드_admin_연동확인.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-29_2352_admin_공유와_API협의_진입점.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · feat(admin): 운영 콘솔 데모와 API 협의 자료 공유 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-30_0017_admin_CI와_develop_공유.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · ci(admin): 병합 보안 검사와 공유 검증 근거 추가 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-30_1032_웹리뷰_프론트독립수정.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · Choi-Sangwook · 09-30 · fix(web): 리뷰 결함 수정과 알림·채팅 합의 반영 |  |  |
| `final_project_cs/wiki/records/reports/2026-09-30_1231_알림폴링_채팅안내_합의반영.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · Choi-Sangwook · 09-30 · fix(web): 리뷰 결함 수정과 알림·채팅 합의 반영 |  |  |
| `final_project_cs/wiki/records/reports/2026-10-01_0957_role_eval_ui_develop_merge.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui | develop · Choi-Sangwook · 10-01 · docs: 웹 develop 통합 검증과 기존 실패 근거 기록 |  |  |
| `final_project_cs/wiki/records/reports/debugs/2026-09-29_1436_예열API_검사목록_누락.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-29 · docs(web): API 명세와 화면별 협업 문서를 최신화 |  |  |
| `final_project_cs/wiki/records/reports/debugs/2026-09-30_0044_warmup_API_계약시험_누락.md` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · fix(test): 웹 예열 API를 계약 검사 목록에 반영 |  |  |
| `final_project_cs/wiki/records/vision/TODO_VISION.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-29 · docs(mobility): 지하철·버스 사고 출처를 조사해 적고, 이동 계산기 구조 정리를 보류 목록에 올 |  |  |
| `final_project_sample/requirements.txt` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Your Name · 09-30 · chore(deps): 의존성 목록을 저장소 맨 위 requirements/ 로 정리한다 — 서버·시험·선택 |  |  |
| `final_project_ui/requirements.txt` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · kimji9663 · 10-03 · fix(ui): psycopg 를 binary 판으로 설치해 libpq 없는 환경에서도 뜨게 한다 |  |  |
| `wiki/log.md` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · Choi-Sangwook · 09-30 · fix(test): 웹 예열 API를 계약 검사 목록에 반영 |  |  |
