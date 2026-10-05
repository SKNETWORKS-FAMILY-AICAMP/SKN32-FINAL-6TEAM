# 서울 활동 후보 · 쇼핑 매장 자료 (활동 팀 PR #6 에서 옮김)

## 무엇인가

활동 팀이 만든 서울 활동 후보 자료입니다. 관광공사 장소 805곳과 올리브영 매장 368곳을 합친 후보 1,173건이 중심이고, 무신사·다이소·아트박스 매장 목록이 함께 있습니다. 대체 장소를 고를 때 「비슷한 종류의 쇼핑 장소」를 넓히는 재료로 쓸 수 있습니다.

**아직 DB 에 넣지 않았습니다.** 넣으려면 `scripts/load_place_catalog_csv.py` 를 돌려야 하고, 사용자 확인 뒤에 합니다.

## 어디서 왔나

- 조직 저장소 `develop` 판 `b892cfff` 의 `final_project_cs/app/domains/travel_ops/instances/activity/data_processing/`(앱 코드 폴더 안에 있었음)
- 적재 스크립트는 같은 판의 `final_project_cs/scripts/load_place_catalog_csv.py`
- 옮긴 날: 2026-09-29. 옮긴 이유: 자료는 git 밖 `datasets/` 자리라는 규칙(루트 `CLAUDE.md` 「데이터 폴더」). 검수 기록 — `final_project_cs/wiki/records/reports/2026-09-28_1826_Activity_PR6_전수검수_리포트.md`

## 파일 (CSV 파서로 센 건수 — 칸 안에 줄바꿈이 있어 줄 수로 세면 틀린다)

| 파일 | 건수 | 무엇 |
|---|---:|---|
| `raw/01_oliveyeong_seoul_all_branches.csv` | 368 | 올리브영 서울 매장(파일 이름 오타는 원본 그대로) |
| `raw/02_musinsa_seoul_all_branches.csv` | 53 | 무신사 서울 매장 |
| `raw/03_daiso_seoul_all_branches.csv` | 196 | 다이소 서울 매장 |
| `raw/04_artbox_seoul_all_branches.csv` | 59 | 아트박스 서울 매장 |
| `processed/activities_candidates_seoul_merged.csv` | 1,173 | 관광공사 805 + 올리브영 368 합친 후보 |
| `processed/activity_total_data.csv` | — | 만드는 스크립트·읽는 코드가 없던 파일(출처 다섯). 원본 보존용으로만 둔다 |
| `processed/oliveyoung_*.csv`, `processed/tourapi_*_enriched.csv` | — | 올리브영 짝짓기 검토·관광공사 보강 중간 결과 |
| `scripts/*.py` | — | 관광공사 상세 받기 · 서울 거르기 · 올리브영 짝짓기 · DB 적재 |

원본의 `oliveyoung_seoul.csv` 는 `01_oliveyeong_seoul_all_branches.csv` 와 바이트까지 같아서 옮기지 않았습니다.

## 알아 둘 것

- **휴대전화 형식 번호 3건**이 `processed/activities_candidates_seoul_merged.csv`·`processed/activity_total_data.csv` 의 `tel` 칸에 있습니다(관광공사 행사 연락처로 보임, 확인 안 함). 조직 공개 저장소에도 올라가 있습니다 — 기록에서 지울지는 사용자 결정 대기.
- 관광공사 값은 저장해 써도 됩니다(루트 사실표 「외부 공공데이터 저장」, 2026-09-28 사용자 결정). **사진·소개글(`firstimage`·`overview`)은 저장하지 않는다**는 선이 있으니 DB 에 넣을 때 그 두 칸은 뺍니다.
- 스크립트 기본 경로 중 일부는 저장소에 없는 파일을 가리킵니다(검수 리포트 「그 밖의 정리 사항」). 다시 돌리려면 경로를 이 폴더로 맞춰야 합니다.
