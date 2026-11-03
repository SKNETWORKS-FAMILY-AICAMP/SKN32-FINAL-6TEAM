---
type: report
title: TeamFlow 미완료 117건 전수 조회 · 분류 · 완료 증거 기록 · 상태 갱신
description: 프로젝트 84 전체 688건을 유형×상태로 나눠 받아 미완료 117건을 빠짐없이 분류하고, 증거가 확인된 12건 완료 · 6건 검토로 바꾸고, 수정 후보 1커밋(574 · 714)을 격리 사본에 만들었다
status: done
domain: travel
impl_scope: cs
---

# TeamFlow 미완료 117건 전수 점검 (2026-10-28)

사용자가 승인한 범위: 미완료를 모두 확인하고 처리하며, 완료 기록과 상태를 바꾼다. 완료 증거가 없는 이슈는 완료로 바꾸지 않는다. 운영 데이터는 바꾸지 않는다. 코드 수정은 격리 사본에서 하고, 라우팅·EKS 담당과 겹치지 않게 인계한다.

## 1. 조회와 분모 검증

- 경로: `C:/_proj/test_workspace/jira_for_me/mcp-server` stdio MCP(`list_issues` · `get_issue`). 키는 `.env.teamflow` 에서 읽었고 출력하지 않았다.
- `list_issues` 는 한 번에 최대 500건만 주고 offset을 무시한다. 그래서 상태 4 × 유형 4 = 16묶음으로 나눠 받았다. 모든 묶음이 500건 미만(최대 248건)이라 잘린 묶음은 없다.
- 고유 id 합집합은 688건이다. 필터 없이 받으면 500건(상한)이고 `status=done` 만 받아도 500건이라, 나눠 받지 않으면 빠진다.
- 갱신 전: done 571 · review 49 · todo 48 · inprogress 20 = 688. **미완료 117건**(117/688 = 17.0%).
- 갱신 후 다시 받음: done 583 · review 51 · todo 39 · inprogress 15 = 688. **미완료 105건**(105/688 = 15.3%).
- 대상 22건은 상태 · 원래 본문 앞부분 · 제목 · 담당이 모두 기대대로다(22/22). 나머지 666건은 상태 · 본문 · 제목 변화가 0건이다.

## 2. 코드 반영 대조

- 기준: 팀 원격 `role-manager efc6fca47` · `develop 36ba4c2fc` · `main e88e01925` · `role-eval-ui 3626bce33`(`git ls-remote` 로 확인).
- 미완료 이슈 본문과 댓글에서 커밋처럼 보이는 문자열 263개를 뽑아 대조했다.
  - 202개는 네 가지에 모두 들어 있다.
  - 6개는 main 에만 있다(main 병합 커밋).
  - 1개(`206f151f`)는 어디에도 조상이 아니다. 체리픽된 `ede8d85a9` 로 들어갔다.
  - 54개는 커밋이 아니다(날짜 · CI 실행 번호 · 접수 id).
- 6833b1153(ST4F-631)은 role-manager 에만 있다.
- main `e88e01925` 의 CI 결과:
  - CI (main) 40486738166 success.
  - CI (web) 40486738151 success. 브라우저 live 4묶음은 236+229+239+239 = 943 통과, 실패 0, 건너뜀 20.
  - CD (AWS) 40488146501 success.
- develop `36ba4c2fc` 의 CI (develop) 40484477127 · CI (web) 40484477303 은 success 다.

## 3. 분류(117건 = 100%)

| 분류 | 건수 | 키 |
|---|---|---|
| A 완료 처리(증거 확인) | 12/117 = 10.3% | 536 · 573 · 577 · 653 · 678 · 685 · 694 · 709 · 715 · 716 · 717 · 726 |
| B 검토로 이동(코드 반영 확인, 실서버 · 사람 확인 남음) | 6/117 = 5.1% | 351 · 631 · 674 · 692 · 718 · 719 |
| C 검토 유지(코드는 role-manager · develop · main 에 반영, 실서버 · 실기기 · 사용자 확인 남음) | 45/117 = 38.5% | 549 · 572 · 583 · 592 · 620 · 621 · 622 · 632 · 633 · 634 · 636 · 638 · 643 · 646 · 649 · 651 · 666 · 670 · 671 · 672 · 675 · 676 · 684 · 698 · 699 · 704 · 705 · 706 · 707 · 708 · 721 · 722 · 723 · 727 · 728 · 729 · 731 · 732 · 733 · 734 · 735 · 736 · 737 · 738 · 739 |
| D 수정 후보 있음(격리 커밋, 푸시 전) | 3/117 = 2.6% | 574 · 710 · 714 |
| E 영역 에픽(하위 진행 중, 닫을 근거 없음) | 9/117 = 7.7% | 209 · 210 · 211 · 212 · 213 · 214 · 215 · 216 · 217 |
| F 최종발표 · 제출(발표 완료 증거를 wiki 에서 못 찾음) | 2/117 = 1.7% | 15 · 123 |
| G 쇼핑몰 시절 잔여(D-023 이후 범위 밖) | 4/117 = 3.4% | 14 · 109 · 119 · 120 |
| H 결정 대기(사용자 · 팀) | 9/117 = 7.7% | 523 · 545 · 552 · 595 · 602 · 619 · 626 · 691 · 700 |
| I 운영 · 실서버 작업(x600 · Oracle · 운영 DB 쓰기 필요) | 13/117 = 11.1% | 348 · 516 · 520 · 529 · 554 · 555 · 556 · 565 · 587 · 588 · 589 · 644 · 697 |
| J 사람 검토 · 평가 후속 | 3/117 = 2.6% | 540 · 550 · 585 |
| K 시험 불안정 · 시험 기반 | 3/117 = 2.6% | 504 · 521 · 547 |
| L 미해결 코드 · 자료 작업(담당 필요) | 8/117 = 6.8% | 188 · 409 · 502 · 531 · 581 · 597 · 711 · 724 |

## 4. 완료로 바꾼 12건의 증거

각 이슈 본문 끝에 `[2026-10-28 TeamFlow 전수 점검]` 문단으로 같은 증거를 덧붙였다. 원래 본문은 그대로 두었다. 이 토큰으로는 댓글을 쓸 수 없다.

| 키 | 증거 |
|---|---|
| 536 · 573 | 읽는 쪽 892fd567 과 싣는 쪽 d03ed80c6 이 role-manager · develop · main 에 들어 있다. role-activity-b 끝 11e46bde1 이 셋의 조상이다 |
| 577 | role-activity-b 가 develop 에 합쳐졌다. develop CI 는 success 다 |
| 653 | main CI (web) live 2/4 에서 `login-consent-flow-20261016.spec.ts:152` 가 통과했다 |
| 678 | 275c63ee3(고침)과 a5348ab39(x600 실서버 확인 기록)가 네 가지 모두에 있다 |
| 685 | b8c191b6a 가 반영됐다. 오늘 efc6fca47 에서 `test_closure_modal_su.py` 8/8 통과 |
| 694 | main 브라우저 live 4묶음 943 통과 · 실패 0 |
| 709 | ede8d85a9 와 c91289b16 이 반영됐다. 오늘 `test_choose_price_limit.py` 5/5 통과 |
| 715 | 2a993fa7 의 develop push CI 2건이 success 다. hwansj 의도 확인은 692 로 넘겼다 |
| 716 | x600 적용은 사용자가 확인했다(10-22 기록). main CI (main) success. 오늘 `test_journey_progress.py` 22/22 통과 |
| 717 | x600 적용은 사용자가 확인했다. main live 2/4 에서 `menu.spec.ts` 5건 통과 |
| 726 | main 트리에 `.render-temp` 파일 0개. `apps/web/.gitignore` 16행에 제외 규칙이 있다 |

오늘 실행한 시험(격리 Py 3.12, 소켓 차단 runner, efc6fca47 압축 해제본): 36 통과 · 1 건너뜀 / 37.

- 건너뛴 1건은 DB 가 필요한 `test_dining_agent_judge` 다.
- 이 시험의 libpq 가 로컬 5433 포트에 연결을 시도했고 인증 실패로 끝났다. 데이터 쓰기는 0이다.

## 5. 상태를 바꾸지 않았지만 새로 확인한 것

- **724 진행 중 유지.**
  - main 의 세 앱은 next 16.4.2 이고 Next 권고는 사라졌다.
  - 오늘 `npm audit --omit=dev --package-lock-only` 를 돌리니 세 앱 모두 high 1건이 남았다: zod <4.6.6 GHSA-mrhx-c7xc-m3w5(새 권고).
  - 그래서 완료 기준 「audit 0건」을 아직 못 채웠다. 고치려면 package.json 을 바꿔야 해서 웹 담당에게 넘긴다.
- **574 · 714.** 격리 후보 `010f9deeb` 를 만들었다(efc6fca47 위 1커밋, 푸시 전).
  - 574: `refresh_places_tick` 이 `Settings.public_data_key()` 로 키를 고른다(서비스별 키가 먼저, 없으면 공통 `ACOP_DATA_GO_KR_KEY`).
  - 714: dining 블록만이 아니라 activity · booking_handoff · mobility 블록도 required · capabilities · hooks 가 두 번 적혀 있었다. 넷 모두 한 벌만 남겼다. `yaml.safe_load` 결과는 고치기 전과 같다(True).
  - 새 시험 2건은 RED → GREEN 이다. core · composition · activity · architecture · contract 묶음 1,973 통과 · 실패 0. ruff 통과.
  - patch 파일은 scratch 의 `ev/0001-…ST4F-714.patch` 다.
- **710.** 기존 격리 후보 `e6e754f27` 이 있다(푸시 전). [보고서](2026-10-28_st4f710-same-day-checkout-stay-fix.md)
- **573 · 577 · 536.** 이전 우선순위표(10-28 ST4F-631 보고서)에는 없던 항목이다. 활동 브랜치가 이미 셋 모두에 합쳐져 있어 「끝났는데 열린」 상태였다.
- **502 · 531.** 재발 방지 안내나 검사가 role-manager 의 AGENTS · CLAUDE · scripts 에서 검색되지 않는다. 미해결이다.

## 6. 하지 않은 것과 그 이유

- **푸시 · 배포는 하지 않았다(0건).** role-manager 에 푸시하면 x600 자동 배포가 시작되고, 라우팅 에이전트 구현 세션이 지금 그 가지에 푸시하고 있다. 후보 `010f9deeb` · `e6e754f27` 은 그 세션이 반영하도록 넘긴다.
- **운영 실서버 확인은 하지 않았다.** C · I 분류는 고객 여행을 만들거나 지우는 등 운영 데이터를 써야 확인할 수 있다.
- **에픽 · 발표 · 쇼핑몰 잔여 · 결정 대기는 닫지 않았다.** 완료 근거가 없거나 사용자 결정이 필요한 항목이다.

## 증거(저장소 밖)

Hermes scratch `teamflow-open-sweep-20261028/` 에 있다.

- `tf_pull.mjs` · `tf_get.mjs`: 읽기 전용 도구
- `tf_update.mjs`: `update_issue_fields` 만 부른다
- `ev/tf_all.json`(전) · `ev/tf_all_after.json`(후)
- `ev/ancestry.tsv`
- `ev/classification.csv`
- `ev/updates.json`
- `ev/updates*.result.json`
- `ev/red_574_714.log` · `ev/red2.log` · `ev/green2.{log,xml}` · `ev/verify_685_709_692_716.{log,xml}`
- `audit724/`
- 격리 worktree `wt/`(detached `010f9deeb`)
