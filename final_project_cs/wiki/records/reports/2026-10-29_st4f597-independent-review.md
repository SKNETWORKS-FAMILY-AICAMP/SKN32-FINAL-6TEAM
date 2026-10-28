---
type: report
title: ST4F-597 후보 독립 검토와 dining 감사행 회귀 진단
status: draft
domain: travel
impl_scope: cs
---

# ST4F-597 독립 검토

2026-10-29. 기존 후보 작성 세션의 결과를 그대로 승인하지 않고 새 격리 worktree와 PostgreSQL16.15(127.0.0.1:55617/review597)에서 재실행했습니다. 원본 제품 코드·활성 DB·다른 작업 트리는 수정하지 않았습니다. 루트/하위 AGENTS·CLAUDE·RULE, wiki indices, 개발 역할, Dining·SQL 계약과 _coord를 읽었습니다. 현재 사용자의 독립 검토·안전 통합 요청 범위에서 합성 DB와 mock 검증을 수행했습니다.

## 결론과 보안

후보 908은 메뉴가 있어도 주소 원문을 먼저 잡아 유사도를 NULL로 만드는 결함을 고칩니다. 메뉴 키가 있는 행만 선택하고 적재 확인시각 내림차순·record_id 오름차순으로 고릅니다. 214 category와231 style의 기준과 같습니다. 명시적으로 빈 최신 메뉴와 분류 불가 최신 메뉴는 NULL이며 이전 메뉴를 되살리지 않습니다. 태그 정규식·유사도 공식·API 계약은 바꾸지 않았습니다.

입력은 uuid이고 정적인 schema-qualified SQL입니다. 동적 SQL·외부 부수효과·SECURITY DEFINER·권한 확대·고객 데이터 쓰기를 추가하지 않습니다. 직접 SQL에서 invoker, STABLE, 기존 ACL이 적용 전후 동일함을 확인했습니다. 메뉴의 SQL 문자는 데이터로만 처리됩니다. 동률 record_id 선택은 category와 같은 기존 정책이며, 운영 데이터 분포·대량 조회 성능은 이번 합성 검증으로 확정하지 않습니다.

## 254/255 실패의 원인

`test_judge_records_agreement_and_disagreement_in_the_dining_table`은 review.load=None을 만들면서 _run/found/open_at 세 행만 기대했습니다. 제품 judge.run의 tokenless 경로는 intake_state를 잠금 조회하고 접수/현재 검사가 없으면 stale=1, changed=0과 `_stale / intake_moved_on` 감사행을 남깁니다. 메뉴 함수와 독립적인 정상 보호 동작입니다. 제품 코드를 완화하지 않았습니다.

격리 시험만 intake_state=None 경계를 명시하고 네 행 전체·stale=1·changed=0·실패코드를 검증하도록 보완했습니다. 실제 접수 경로는 별도 판정 e2e/늦은 판정 회귀로 검사합니다. 후보 원본 6개에 동률 시각·SQL 문자·분류 불가 최신 메뉴 3개를 추가했습니다.

## 독립 실행 증거

| 검사 | 결과 |
|---|---|
| 동일 원본255개 기준(908만 제외) |250/255 =98.0%,5실패 |
| 동일 원본255개 원후보 |254/255 =99.6%,공통실패1;새실패0 |
| 감사행 기대 보완+독립 edge3 |258/258 =100%,건너뜀0 |
| 계약 |367/367 =100%,건너뜀0 |
| 보안 |125/125 =100%,건너뜀0 |
| DoD |26/26 =100%,미측정0·시험없음0 |
| 마이그레이션·추천 unit |92/92 =100%,건너뜀0 |
| 직접SQL |기준NULL→후보면,2회적용동일,권한보존,rollback확인 |
| 전체 migration 재실행 |2/2 =100%,합성 메뉴와 태그 보존;검증행 보존 |
| ruff F/E9·staged diff check |exit0 |

실패/환경 기록도 보존했습니다. 처음55497은 사용 중이라 건드리지 않고55617을 새로 확보했습니다. pg_ctl capture pipe 대기가 있어 후속 명령은 파일 로그를 사용했습니다. replay 첫 시도는 스크립트 sys.path에서 sample app이 앞서 ModuleNotFoundError였고, CS import 위치를 명시한 v2가 통과했습니다. 추가 판정 e2e 첫 시도는 provider 미지정(openai 기본)인데 mock 실행기 비활성 시험을 돌려38/39 =97.4%였습니다. 시험 계약대로 provider=mock을 명시한 후속 결과는 해당 JUnit에 남깁니다. 이 환경 설정 수정으로 제품 코드를 바꾸지 않았습니다. 기존 실패 로그를 덮거나 지우지 않았습니다.

## 최신 원격·협업·통합

초기 양쪽 role-manager는3dd9bd70c9d1c598f70faad69cf755141cc4a041로 동일하며 원후보 적용이 깨끗했습니다. 버스 세션의02:47 통합 예약을 확인해 동시 push를 보류했습니다. 최신 tip을 다시 받아 변경 경계와 최종 관문을 확인한 뒤에만 반영합니다. develop/main·수동 배포·이슈 상태 변경은 대상이 아닙니다. role-manager가 x600 자동 배포 대상임을 알고 있으며 운영 데이터 메뉴 비율·운영 개선·배포 완료는 별도 증거 없이는 주장하지 않습니다.

SQL inventory는 생성기의 render 결과 중 해당 문서만 갱신했습니다. 기존107개 표시는 이미 누락4개였고,이번908까지 포함한 실제 실행 파일은112개입니다. 기존 SQL 원문은 수정하지 않았습니다.

## 보존·재실행·남은 일

전체 증거: `C:/_proj/final_workspace/scratch/st4f597-review-20261029/`. review.py의 baseline/dining/final-dining/contract/security/dod/migration-tests/probe/replay/judge-tests-ready로 조건을 확인할 수 있습니다. 기준·원후보 JUnit,각 로그,직접SQL JSON,재적용JSON,시험전 파일·문서 백업을 보존했습니다. 원후보 패치 SHA256은37c9610c88bfb9b6d342b96cad244de8df6cc7f9da64705ec917fbe0e3cd8841입니다.

메뉴가 아예 없는 원장까지 해결한 것은 아닙니다. ST4F-597을 닫지 않습니다. 운영 메뉴 보유율·후보 해당 건수·운영 수락은 미확인입니다. 전체 잔여 업무의 분모는 모름입니다. 활성 자료·기존 DB·로그·사본 삭제0입니다.
