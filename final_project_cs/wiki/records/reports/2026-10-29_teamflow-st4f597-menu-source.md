---
type: report
title: TeamFlow 재조회와 ST4F-597 메뉴 원문 선택 결함 격리 수정
status: draft
domain: travel
impl_scope: cs
---

# ST4F-597 메뉴 원문 선택 결함 — 격리 후보

확인 시각: 2026-10-29T02:39:42.764647+09:00. 담당·검증: Codex root. 독립 검증은 pytest 픽스처와 별개의 직접 SQL 실행이며, 다른 사람·에이전트의 독립 리뷰를 받았다는 뜻은 아닙니다.

## 실제 열린 이슈와 선정

TeamFlow 프로젝트84를 상태4×유형4 묶음으로 처음·마지막 두 번 읽었습니다. 각 묶음 최대248건으로 limit500보다 작습니다. 전체 목록 한 번은500에서 잘리므로 그 값으로 분모를 만들지 않았습니다. 두 조회의688개 이슈 객체는 동일했습니다.

- 전체688, done584, todo38, inprogress15, review51. 미완료104/688 = **15.1%**.
- 미완료 버그31/104 = **29.8%**: todo9, review22. 기존 review를 미해결 코드 결함으로 단정하지 않았습니다.
- high todo504: 직전 새PG 반복30/30 통과로 현재 미재현, 역사적 원인 미확정. high554·555·556·589: x600/Oracle의 모델·자료·호출량 실측이 필요한 운영 항목입니다. 이번 합성 DB 결과로 종결할 수 없습니다.
- 711은217da9ad0 후속 수정·배포 기록이 있으나 LB-09 역사적 원인·운영 복귀 인수가 남습니다. 521에는 기존 후보와 담당T가 있습니다. 547은 전체 단위 묶음의 역사적 정지 조사입니다.
- medium597은 기존 SQL의 `LIMIT 1` 때문에 **메뉴가 이미 있어도** 근거를 못 읽는 재현 가능한 코드 결함을 확인해 선정했습니다. 원장에 메뉴가 아예 없는 문제 전부를 해결한 것은 아닙니다.

## 경계와 현재 계약

원본 및 격리본 AGENTS·CLAUDE·RULE, wiki indices·이전117/105 sweep·최신711/504 handoff, T·S3·R·V·711·배포 후속 `_coord` 공지를 읽었습니다. 새 공지 `Codex-ST4F597-20261029-NOTICE.md`로 SQL·요식 시험만 맡는다고 게시했습니다. intake·conversation·웹·다른 작업 트리를 수정하지 않았습니다.

기준은 읽기 전용 팀 원격 확인 `3dd9bd70c9d1c598f70faad69cf755141cc4a041`입니다. 새 격리 worktree `C:\_proj\final_workspace\scratch\teamflow-next-20261029\repo2`에서 구현했습니다. 원본 Git 명령은 safe_git 진입점만 사용했으며 시스템git 실행 거부를 기록했습니다. 이후 Git은 기존 **격리** 허브와 자체 worktree에만 portable git을 사용했고 `GIT_OPTIONAL_LOCKS=0`을 강제했습니다. 원본 Git 설정·색인·코드·비밀값을 바꾸지 않았습니다.

`review_alternatives.rank → dining.suggest_alternatives → alternative_pool → cuisine_similarity → cuisine_tags` 실제 호출을 확인했습니다. 기존214의 `classify_category`,231의 `classify_style`과 같은 원문 선택 기준으로 맞췄습니다. 새 API·스키마 필드·판정 어휘·공유 계약 변경은 없습니다.

## 구현과 재현

새 `908_dining_cuisine_source.sql`만 추가했습니다. 기존207 마이그레이션은 보존합니다. 메뉴 필드가 있는 원문을 적재 확인시각 내림차순·record_id 순으로 골라, 주소만 있는 행이 메뉴를 가리지 않게 합니다. 최신 원문이 메뉴를 명시적으로 비우면 과거 메뉴를 되살리지 않고 NULL을 유지합니다. 메뉴가 전혀 없을 때도 NULL입니다. 음식 태그 어휘와 유사도 공식은 그대로입니다.

새 PostgreSQL16, loopback55495, 전용 DB `st4f597`만 사용했습니다. 공개 자료·고객 자료 대신 합성 식당을 넣었습니다. 외부 API·유료 모델 호출은 하지 않았습니다.

| 검증 | 결과 |
|---|---|
| 새 회귀6개 기준 | 2/6 =33.3% 통과,4개 예상 실패 |
| 새 회귀6개 후보 | **6/6 =100%** |
| 동일 요식 통합255개 기준 |250/255 =98.0%,5실패 |
| 동일 요식 통합255개 후보 |**254/255 =99.6%**,1실패,건너뜀0 |
| JUnit 개별 결과 비교 |4개만 실패→통과,새 실패0; 공통 실패1 |
| 독립 직접SQL |원본NULL→후보['면']; 두 번 적용 동일,트랜잭션 롤백 |
| 계약 |**367/367 =100%**,건너뜀0 |
| 보안 |**125/125 =100%**,건너뜀0 |
| DoD |**26/26 =100%**,미측정0·시험없음0 |
| ruff F/E9·staged diff --check |둘 다 exit0 |

공통 실패는 `test_judge_records_agreement_and_disagreement_in_the_dining_table`입니다. 임의 intake_id의 접수 행이 없어 `_stale` 기록이 추가되는데 시험은3행만 기대합니다. 기준과 후보에서 모두 실패했고 이번 범위에서 고치지 않았습니다. 메뉴 선택 변경으로 이 실패가 생기지 않았음을 `comparison.json`으로 확인했습니다.

초기 환경 실패도 보존했습니다: dummy 설정 누락으로6 setup errors(`red.log`), dining-only DB에서 접수 표 누락, full migration 뒤 공통 `_stale` 실패, 프롬프트 미등록·시스템git 거부로 계약12/보안1 실패. portable git PATH·정식 prompts 등록 후 계약·보안은 전부 통과했습니다. 불필요하게 시도한 `seed_travel`은 현재 places의 제거된 `hours_confirmed_at` 열을 참조해 실패했습니다. 이 실패를 은폐하거나 현재 데이터 스키마를 임의로 바꾸지 않았으며, broad seed 성공으로 보고하지 않습니다. 첫 worktree 생성은 긴 파일명으로 실패해 별도 `core.longpaths=true` 호출의 repo2를 사용했습니다.

## 재실행과 보존

원본 workspace의 `scratch/teamflow-next-20261029/`에 다음을 보존했습니다.

- `tf_all.json`, `final-pull/tf_all.json`: 두 실제 조회.
- `run_checks.py`, `baseline_plugin.py`: 자체DB 실행·동일시험 기준/후보 대조. baseline plugin은 새908만 적용에서 제외하며 원문 파일을 바꾸지 않습니다.
- `red-v2.xml`, `baseline-dining.xml`, `final-dining-v2.xml`, `comparison.json`.
- `contract-ready.xml`, `security-ready.xml`, `dod.log`, ruff·diff-check 로그.
- `independent_sql.py`, `independent-sql.json`: pytest와 별개 SQL 검증.
- `ST4F-597.patch`: 두 파일 패치 SHA256 `37c9610c88bfb9b6d342b96cad244de8df6cc7f9da64705ec917fbe0e3cd8841`.
- `pgdata`, PostgreSQL 로그·종료 로그, 최초 실패 로그·문서 백업.

대표 명령은 `python run_checks.py red`, `baseline`, `final-dining`, `contract-ready`, `security-ready`, `dod`입니다. 직접SQL은 setup.json의 Python으로 `independent_sql.py`를 실행했습니다. DB는 종료되어 재실행 전 자체 pgdata를55495에서 시작해야 합니다. 문서·SQL 증거는 삭제하지 않았습니다.

## 인계·남은 일

**push·병합·이슈 상태 변경·이슈 종결은0**입니다. 운영DB에 메뉴가 실제 존재하는 비율이나 이 SQL 결함에 해당하는 건수를 확인하지 않아 ST4F-597은 계속todo입니다. 모든 메뉴가 없는 원장 데이터까지 고쳤다고 보고하지 않습니다. 외부 리뷰와 기존 공통 요식 시험 정리는 다음 담당 몫이며, 반영하려면 최신 양 원격과 `_coord`를 다시 읽고 새 tip 위에서 검증한 뒤 양쪽 role-manager에만 비강제 반영합니다. develop·main은 이번 대상이 아닙니다.

자체PG는 `pg_ctl stop` exit0으로 종료했습니다. node_modules 설치·공용 캐시 정리·다른 세션 자원 변경은0입니다. 파일·worktree·캐시는 상위 지침의 대상별 명시 승인 없이 지우지 않고 보존했습니다. 전체 잔여 작업의 완료율은 분모 모름입니다.
