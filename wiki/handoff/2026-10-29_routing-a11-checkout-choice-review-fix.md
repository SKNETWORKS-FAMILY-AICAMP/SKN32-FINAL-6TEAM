---
type: handoff
title: A11 독립 검토 잔여 — 고객이 숙박으로 고른 짝 없는 체크아웃 줄(P2) · 바뀐 종류 화면 안내(P3) 수정
status: draft
domain: travel
---

# 결론

기록 2026-10-29 KST, Hermes(Claude) 서브에이전트. 자체 검증이며 독립 승인은 없습니다. 대상은 [A11 후속 독립 검토](2026-10-29_routing-a11-checkout-only-independent-review.md)의 남은 P2 · P3이고, 후보 트리 `C:/_proj/routingresume1029`(HEAD `d1b06357e` + 앞 A11 수정)을 그대로 이어 썼습니다. 새 clone · worktree · pip 설치는 0건입니다.

**통합 · push는 계속 HOLD입니다.** 보호 XML 보안 HOLD(`security-ready.xml`, 124/125)는 이번 작업에서 건드리지 않았고, 스캐너도 고치지 않았습니다. push · 배포 · 운영 DB 쓰기는 0건입니다. 이번에는 DB 관문(회귀 1510 · 계약 · 보안 · DoD)을 다시 돌리지 않았습니다. 저용량 격리 unit만 돌렸습니다.

- **P2(고객이 숙박으로 고른 짝 없는 체크아웃 줄):** 고객 선택(`kind: lodging`, `method: customer`)은 덮지 않습니다. 숙박 기간도 지어내지 않습니다(`end_date` · `ends_at` 없음 그대로). 대신 조립 문제 `stay_without_check_in`(`items[n].kind`)을 내어 **등록을 막습니다**. 문구는 「「…」 — 숙박으로 고르셨지만 짝이 되는 체크인 일정이 없어 숙박 기간을 알 수 없어요 · 체크인 일정을 넣거나 들르는 일정으로 바꿔 주세요」입니다. 확인 화면 시간 줄에도 같은 말을 `bad`로 보입니다. 같은 호텔 체크아웃이면 지금처럼 앞 숙박의 끝으로 짝짓고, 이 문제는 생기지 않습니다.
- **P3(바뀐 종류 안내):** `review._time_line`이 `filled`의 `items[n].kind` 안내를 「규칙으로 채움」으로 보입니다. 예: 「체크인 줄과 짝이 없는 체크아웃 줄이라 숙박이 아니라 그 시각에 들르는 일정으로 두었어요」.
- **P3(시각 없는 짝 없는 체크아웃, 09:00):** 시각은 기존 일정 배치 규칙 결과 그대로 둡니다. 새 시각이나 숙박 기본값 11:00을 넣지 않습니다. 대신 시간 줄을 `warn`으로 바꾸고 「체크아웃 시각이 적혀 있지 않아 일정 배치 규칙으로 HH:MM에 두었어요 · 실제 체크아웃 시각이 다르면 고쳐 주세요」라고 알립니다. `warn` 시간 줄은 기존 규칙대로 등록을 막지 않습니다.
- 새 상수 · 임계값 · 정책 값은 없습니다. 등록을 막는 조립 문제는 기존 계약 방식(`no_date` · `kind_unanswered`처럼 `check.problems`)을 그대로 따릅니다.

# 바꾼 파일(후보 트리, 커밋 안 함)

- `final_project_cs/app/domains/travel_ops/components/intake/assemble.py` `_stays`: `chosen`(고객이 숙박으로 고른 짝 없는 체크아웃 줄) → 짝이 안 되면 `open_stay`(문제 추가 + 행 표시 `open_stay`). 체크인 없는 일찍 끝나는 길과 짝짓기 뒤 길 모두에 적용합니다.
- `.../intake/review.py` `_time_line`: `open_stay`(bad) · 종류 안내(filled) · 규칙 시각 체크아웃 주의(warn)를 넣었습니다. `provenance`가 없는 행도 받습니다(기존 시험이 이 경우를 잡았습니다).
- `final_project_cs/wiki/external/rest-endpoints/web-intakes.md`: 문제 코드 목록과 「숙박」 절에 이 계약을 적었습니다.
- 새 시험 `tests/unit/travel/test_intake_stay_checkout_choice_review.py`(6개)는 **실제 읽기 경로**를 씁니다. `pipeline.read_source`에 읽기 에이전트 대역(`place_quote`는 장소 말만)과 `our_places`를 넣고, `collect` · `assemble` · `review._time_line`을 그대로 부릅니다. 앞 A11 시험 ⑤(`test_intake_stay_checkout_only_lodging.py`, untracked)에는 문제 단언을 더했습니다.
- 모든 파일의 CRLF는 그대로 두었습니다(`git diff --check` 통과).

# 실행 결과(DB · 외부 연결 차단 — 닫힌 포트 DB URL + guard sitecustomize, 3.12 격리 실행기)

| 실행 | 결과 |
|---|---|
| RED1(새 시험, 수정 전) | 1/6 통과. 실패 1건은 시험 기대 오류였습니다(activity 줄의 기존 90분 끝 안내). 기대를 고쳐 따로 보존했습니다 |
| RED2(수정 전) | 2/6 통과, 4 실패. 고객 선택 숙박이 문제 0으로 남음(P2 재현) · 종류 안내 없음 · 09:00 `filled`만 보임 |
| GREEN(숙박 unit 11개 파일) | 72/72 |
| 확대 1회차(travel의 intake·review·lodging·stay 시험 + `tests/unit/intake`, 98개 파일) | 1267/1268. `test_intake_review_units`의 provenance 없는 행에서 KeyError가 났습니다 → 고쳤습니다 |
| 확대 2회차(같은 98개 파일) | **1268/1268**, skip 0 |

실행 전후 대상 소스와 시험의 해시는 같았습니다(`hash_same: true`). 바뀐 파일과 새 시험 5개에 저장소 `find_leaks`를 적용한 결과 0건이고, 이메일 · 전화 · 키 패턴도 0건입니다.

# 증거와 디스크

`C:/_proj/routinga11p2fix1029_evidence`(약 1 MB): `before/`(수정 전 4개 파일), `run_pytest.py`, `red1_fixture_expectation/`, `red2/`, `green/`, `expand1_keyerror/`, `expand2/`(각 폴더에 pytest.xml · log · run.json), `candidate-tracked.patch`, 새 시험 사본이 있습니다. 쓰기 전에 `disk_guard check`(5 MB)를 실행했고 허용됐습니다(below_target 상태). 삭제는 0건입니다.

# 남은 것

1. 보호 XML 보안 HOLD를 정식으로 처리하기 전에는 통합 · push하지 않습니다. 이번 변경으로 DB 관문(회귀 · 계약 · 보안 · DoD)을 다시 돌려야 합니다.
2. 이번 변경은 독립 검토를 받아야 합니다. 실제 모델과 화면 수락은 확인하지 않았습니다.
3. 웹의 접수 기반 대체 화면(`plan-check/from-intake.ts`)은 `filled`를 시간 칸(`date` · `starts_at` · `ends_at`)에서만 읽습니다. 그래서 종류 안내(`items[n].kind`)는 그 화면에 보이지 않습니다. 새 문제는 `.kind` 필드라 그 화면의 장소 줄에 `bad`로 보입니다. 프런트는 고치지 않았습니다.
4. 확인 화면에는 일정 추가 폼(`add-search`, `kind: lodging`)이 있습니다. 하지만 거기서 추가한 체크인 일정이 이 체크아웃 줄과 짝지어져 문제가 풀리는지는 시험하지 않았습니다. 지금 시험으로 확인한 해결 길은 종류를 다시 고르는 것입니다.
5. 독립 검토 P2(좌표 차이 167 m인 같은 호텔)는 별도 요구로 그대로 남아 있습니다.
