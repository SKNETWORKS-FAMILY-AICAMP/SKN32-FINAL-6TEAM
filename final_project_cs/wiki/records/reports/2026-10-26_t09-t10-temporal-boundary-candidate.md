---
type: report
title: full49 T09·T10 시간 경계 실패 원인과 독립 후보
domain: travel
---

# full49 T09·T10 시간 경계 실패 — 원인 확정·독립 후보 수정

작성 2026-10-26 KST · 후보 폴더 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/t09t10-temporal-20261026-012405-b39137b6/` · 코드 기준 `f02-origin-20261025-201456-5daacb/source` 사본(app 517파일 해시 동일 확인 후 수정)

## 결론
T09·T10 모두 실제 E4B 정상 API 재실행에서 **2/2 = 100% pass**(둘 다 `clarify`, DB 버전 변화 0)입니다. 격리 회귀 **1396/1396 = 100%**(기존 f02 union 1389 + 신규 7). 배포·live 반영·push 없음.

| 항목 | 결과 |
|---|---|
| 신규 시험 RED (수정 전) | 5 fail / 2 pass (`red.xml`, `red.log`) |
| 신규 시험 GREEN | 7/7 = 100% (`green.xml`) |
| 격리 회귀 union | 1396/1396 = 100% (`union.xml`, snapshot_stable True) |
| 실모델 T09·T10 | 2/2 = 100% pass, 모델 호출 2/4 (`real-runs/improved-1792946858917199100`) |

## 건별 원인 (원자료: temporal-f02-final real-runs/improved-1792926228694056000)
- **T09** 「1월 2일 오후 3시 이후 일정만 한 시간 미뤄줘」. 기대 `clarify`+경계 질문(build_matrix.py:43, 사용자 명시 합성 행). 모델 출력은 정상 구조(shift/range, anchor_time 15:00, after, +60)였습니다. 실행기 `edit_intent.time_ops`가 after를 `>=`(포함), before를 `<`(제외)로 비대칭 결정해 15:00 정각 시작 N서울타워를 묻지 않고 16:00으로 옮겼습니다. wiki(`trip-chat-context.md` 시간 수정 절)에는 경계 포함 여부 계약이 없고, 모호한 값으로 정하지 않는다는 원칙과 기대가 맞습니다.
- **T10** 「N서울타워를 오후 11시 30분으로 미뤄줘」. 기대 `edit_refused/clarify/needs_check`, 다음 날 무음 이동 금지(followup_rows T10 정정). 모델은 절대 시각을 shift/item, minutes=2340으로 냈습니다. 서버 `decision_unit.spoken_minutes`가 시각의 분 부분 「11시 30분」의 30분을 이동 크기로 세어 +30분(15:30~17:00)으로 저장했습니다. 이 함수 자체의 기존 계약(`"오후 3시로"→None`)과 어긋나는 결함입니다. 과거 bounded run은 crosses_midnight 거절로 pass였습니다.

## 수정 hunk (2파일, 각 1 hunk)
1. `decision_unit.py` `spoken_minutes`: `N시 M분`(시간 아님) 시각 표기를 분 계산 전에 제외. `1시간 30분`=90, `3시 30분 이후 … 1시간`=60, `11시30분 … 20분`=20 보존.
2. `edit_intent.py` `time_ops` range/time: 조회 범위 안에 기준 시각 **정각 시작** 일정이 있으면 `EditRefused("need_time_boundary", "15:00에 시작하는 「N서울타워」도 함께 옮길까요? …")`. 기존 `need_` → `clarify` 매핑(trip_desk.edit)을 그대로 씁니다. 경계 일치 없는 T03/T04는 그대로 이동합니다.

출력 후보정·원문 재파싱으로 새 의미를 만들지 않았습니다. 상대/절대/범위 schema(generation_variants)는 바꾸지 않았습니다. 1은 기존 서버 크기 판독기의 오판을 줄이는 것이고, 2는 검증된 구조 필드(anchor_time, relation)만 사용합니다.

## 해시
- product.patch SHA256 `e81751632921181dd9281c3f10d98a9bb70a3e8ae7804a760de677c447e98a52`, tests.patch `f2d0b70b41f6019dec3dd174479a7cee8e02675b6c26f19f79c2e3709fdab0a8`. `git -c core.autocrlf=false apply` roundtrip 결과가 postimages와 같습니다(`patch-roundtrip/`).
- pre/post: decision_unit `040a8a5a…e2d` → `d27965ee…a99`, edit_intent `3d928ee7…a35` → `b3238572…c06`.

## 실모델
`tripilot-pointer:e4b-ft` digest `ef0a580a…1025`, ctx 8192, concurrency 1, temperature 0, seed 미지정, num_predict 1200. 호출 2회: prompt 6503/output 257, 6503/228, done stop. 모델 출력은 이전 실패 run과 같은 구조였고, 바뀐 것은 서버 처리입니다. lease 획득→실행→즉시 release, live v7a counters admitted 5 / completed 5 전후 동일, 승인 비교 DB improved의 새 tenant `acceptance_matrix_20261025_11b901320e35`만 썼습니다.

## 남은 한계
- T10 답은 「몇 시로(또는 몇 분) 옮길지」를 다시 묻습니다. 고객이 이미 23:30을 말했으므로 이상적인 응답은 start 23:30 → 자정 넘음 거절입니다. 모델이 절대 시각을 shift로 고르는 생성 문제는 남아 있고, 이를 고치려면 schema/프롬프트를 바꾸고 모델로 재측정해야 합니다(이번 범위 밖).
- T09 확인 질문 뒤 「포함/제외」 후속 답을 처리하는 continuation(edit_goal)은 없습니다. 같은 기준 시각으로 다시 말하면 다시 묻습니다. 품목 이름 기준 표현(「N서울타워 뒤 일정만」)은 기존 following 경로로 처리됩니다.
- 격리 시도 실패 보존: `red-plugin-registration-failure.log`(autoload 미차단), `harness-path-failure-union.*`(external-dining 사본의 옛 f02 경로 1곳 → 내 사본만 경로 교체), `product-sed-crlf-failed.patch`.

## 충돌 예상 파일
`app/domains/travel_ops/components/conversation/decision_unit.py`(spoken_minutes, 1261행 부근)와 `edit_intent.py`(time_ops range/time, 261행 부근). C02/U01 작업자가 같은 파일을 고칠 수 있으나 hunk가 떨어져 있어 textual 충돌 가능성은 낮습니다. 통합은 부모가 3-way로 확인해야 합니다.

live API·프런트·x600·push·고객DB·알림·유료 호출·클라우드 고객 원문 전송: 모두 0.

상태: 격리 후보만 있습니다. 원본 코드에는 적용하지 않았고, 통합·배포는 부모 몫입니다.
