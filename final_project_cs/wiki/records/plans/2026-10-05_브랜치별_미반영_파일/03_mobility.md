# 로컬이 본 적 없는 내용 — 이동(Mobility) 담당 세션

작성: commit 세션 · 2026-10-05 · role-mobility 의 이동 자료·시험 등

**무엇인가.** 팀 저장소의 다른 브랜치(머리 해시는 [00_안내.md](00_안내.md))에 있는 파일 중, 우리 로컬이 **그 내용을 한 번도 가진 적이 없는** 것의 목록이다. 내용이 다르다는 뜻일 뿐 기능이 없다는 뜻은 아니다 — 우리가 다른 모양으로 이미 구현했을 수 있다.

**할 일(담당 세션).** 줄마다 상대 내용을 **읽어서** 우리 쪽보다 **더 잘 만든 것만** 로컬에 반영한다(우리 설계가 기준이다 · 2026-10-05 사용자 정정). 반영한 줄에는 「반영」, 일부만 가져왔으면 「일부 반영」, 우리 쪽이 더 낫거나 같은 일을 이미 하면 「제외」, 아직 못 읽었으면 비워 두고 이유를 적는다. **판정 · 이유 칸을 이 표에 직접 적는다.** develop 은 읽기만 한다(푸시 · 머지 · 리베이스 금지).

| 파일 | 종류 | 이 내용을 가진 브랜치 | 마지막으로 바꾼 커밋(브랜치 · 작성자 · 날짜 · 제목) | 판정 | 이유 |
|---|---|---|---|---|---|
| `datasets/mobility/DATA_IN_GIT.md` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-30 · datasets(mobility): 차도 그래프 추가 · 시간표 gz · 출발없음·9호선 급행 행 제외 |  |  |
| `datasets/mobility/processed/mobility/MANIFEST_git_v1.json` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-30 · datasets(mobility): 차도 그래프 추가 · 시간표 gz · 출발없음·9호선 급행 행 제외 |  |  |
| `datasets/mobility/processed/mobility/line_station_order_v1.json` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-29 · data(mobility): 판정기 입력 18파일을 datasets/mobility/processed/ 에  |  |  |
| `datasets/mobility/processed/mobility/line_station_order_v1_report.md` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-29 · data(mobility): 판정기 입력 18파일을 datasets/mobility/processed/ 에  |  |  |
| `datasets/mobility/processed/mobility/timetable_v1.jsonl.gz` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-30 · datasets(mobility): 차도 그래프 추가 · 시간표 gz · 출발없음·9호선 급행 행 제외 |  |  |
| `datasets/mobility/processed/mobility/timetable_v1_coverage.md` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-29 · data(mobility): 판정기 입력 18파일을 datasets/mobility/processed/ 에  |  |  |
| `datasets/mobility/processed/mobility/timetable_v1_destfill_report.md` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-29 · data(mobility): 판정기 입력 18파일을 datasets/mobility/processed/ 에  |  |  |
| `datasets/mobility/processed/mobility/timetable_v1_meta.json` | 고친 파일 | role-eval-ui, role-mobility | role-eval-ui · cls15rn · 09-29 · data(mobility): 판정기 입력 18파일을 datasets/mobility/processed/ 에  |  |  |
| `final_project_cs/app/modules/travel_ops/mobility/engine/paths.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · cls15rn · 09-30 · chore(mobility): 갱신용 수집·전처리 스크립트를 datasets/mobility/scripts/ |  |  |
| `final_project_cs/app/modules/travel_ops/mobility/engine/plan.py` | 고친 파일 | develop, role-activity, role-dining | develop · cls15rn · 10-01 · feat(mobility): 지하철+버스 혼합 후보(환승 1회) · 사고 때 역+버스 대안 · 87 |  |  |
| `final_project_cs/app/modules/travel_ops/mobility/engine/runtime.py` | 고친 파일 | develop, role-activity, role-dining | develop · cls15rn · 10-01 · data(mobility): 지하철 시간표 재수집(10/1) · 오래됨 기준을 수집일로 · 89 |  |  |
| `final_project_cs/app/modules/travel_ops/mobility/engine/timeutil.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · cls15rn · 09-29 · fix(mobility): 73 후속 — 팀장 판 위에서 우리 엔진 수정 · 규칙 v0.9.2 · 시험·회귀 |  |  |
| `final_project_cs/app/modules/travel_ops/mobility/engine/verify_time.py` | 고친 파일 | develop, role-activity, role-dining | develop · cls15rn · 10-01 · feat(mobility): 지하철+버스 혼합 후보(환승 1회) · 사고 때 역+버스 대안 · 87 |  |  |
| `final_project_cs/requirements-mobility.txt` | 새 파일 | develop, role-activity, role-dining, role-eval-ui, role-mobility | develop · cls15rn · 09-30 · chore(mobility): 갱신용 수집·전처리 스크립트를 datasets/mobility/scripts/ |  |  |
| `final_project_cs/tests/unit/travel/mobility/README.md` | 고친 파일 | role-mobility | role-mobility · cls15rn · 09-30 · datasets(mobility): 차도 그래프 추가 · 시간표 gz · 출발없음·9호선 급행 행 제외 |  |  |
| `final_project_cs/tests/unit/travel/mobility/test_review_fixes_plan.py` | 고친 파일 | develop, role-activity, role-dining, role-eval-ui | develop · cls15rn · 10-01 · fix(mobility): 사고 대안 역 — 장소마다 도보 상한 안 역 여럿(막힌 역 제외) · 83 E1 |  |  |
| `final_project_cs/tests/unit/travel/mobility/test_review_fixes_runtime.py` | 고친 파일 | develop, role-activity, role-dining | develop · cls15rn · 10-01 · data(mobility): 지하철 시간표 재수집(10/1) · 오래됨 기준을 수집일로 · 89 |  |  |
