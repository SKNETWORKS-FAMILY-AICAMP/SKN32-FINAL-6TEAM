---
type: handoff
title: A11 후속 — 짝 없는 「체크아웃」 숙박 줄이 끝 없는 가짜 숙박이 되던 결함 수정
status: draft
domain: travel
---

# 결과와 한 일 목록

기록 시각: 2026-10-29 KST. 작업자: Hermes(Claude) 서브에이전트, 자체 검증이며 독립 승인은 없습니다. 이 작업은 [A11 독립 검토](2026-10-29_routing-a11-independent-review.md)의 결함 P1을 고친 것입니다.

**필수 관문은 2/3이고, 통합과 push는 HOLD입니다.** 계약·DoD·회귀는 전부 통과했습니다. 보안은 기존 보호 XML 탐지 1건(`2026-10-29_st4f728-guest-logout/security-ready.xml`) 때문에 124/125이고, 이전과 같은 파일입니다. push·배포·운영 DB 쓰기·원본 저장소 변경·TeamFlow 변경은 모두 0건입니다.

- 루트 AGENTS 규칙, wiki와 handoff 색인, 이전 A11 인계 3건을 읽었습니다. 후보 `C:/_proj/routingresume1029`의 `assemble.py` 해시가 이전 스냅샷(`b8ff39cb…`)과 같은지 확인했습니다. 이 트리를 쓰는 다른 프로세스가 없는지 프로세스 명령줄로 확인한 뒤 재사용했습니다. 새 clone·worktree·pip 설치·데이터셋 복사는 0건입니다.
- **계약상 맞는 처리**: 짝이 없는 체크아웃 줄은 숙박의 시작이 아닙니다(`[2026-10-27]` `leaving`). 숙박 기간을 지어내지 않고, 새 질문 종류도 만들지 않았습니다. `web-intakes.md` 「숙박」 절에 「체크아웃 날을 따로 묻는 칸은 이번에 만들지 않았다」고 적혀 있기 때문입니다. 그래서 고객이 적은 그대로 **그 시각에 그 호텔에 들르는 일정(활동)**으로 둡니다. 체크아웃 줄을 `activity`로 읽었을 때(A11 첫 시험)의 결과와 같고, 2026-10-26 이전에 숙박 읽기가 활동으로 들어가던 동작과도 같습니다. 바꾼 종류는 `provenance.kind = {method: rule, rule: intake.checkout_only}`와 `filled`(「규칙으로 채움」)로 보입니다. 고객이 고른 종류(`customer`)와 등록한 숙소(`trip`)는 덮지 않습니다.
- 제품 코드는 `_stays` 한 곳만 바꿨습니다(`assemble.py` 기준 후보 대비 +18줄). 체크인이 있는 길과 체크인 줄이 하나도 없는 일찍 끝나는 길 모두에 적용합니다. 새 상수나 임계값은 없습니다.
- 새 시험 `tests/unit/travel/test_intake_stay_checkout_only_lodging.py`(5개)는 실제 읽기 에이전트 형태인 체크인·체크아웃 모두 `kind: lodging` 입력을 씁니다. ①P1(다른 호텔 체크아웃) ②호텔을 바꾸는 날 앞 숙박의 체크아웃만 적은 경우 ③체크인 없는 여행 ④두 숙박 모두 lodging인 회귀 ⑤고객 선택 보존입니다.

## 실행 결과(같은 격리 조건 — mock provider, 비loopback 차단, 전용 loopback PG16.15 63942, CI 순서 migrate → register_prompts → seed_travel)

| 실행 | 결과 |
|---|---|
| 새 시험, 수정 전(RED) | 2/5 통과 · 3 실패. 세 실패 모두 「신라호텔 체크아웃」이 `end_date`와 `end`가 없는 lodging으로 남음 |
| 새 시험, 수정 후(GREEN) | 5/5 |
| 접수·숙박·예약·항공·아키텍처 회귀(이전과 같은 선택 규칙, 115개 경로) | **1510/1510**(이전 1505 + 새 시험 5), live 245건은 선택 제외 |
| 계약 | 367/367 |
| 보안 | 124/125(기존 보호 XML 1건 그대로) |
| DoD v11 | 26/26 |

후보의 추적 파일 12189개는 실행 전후 해시 변경이 0건입니다. `git diff --check`도 통과했습니다. 저장소 스캐너 `find_leaks`(스캐너는 고치지 않음)를 바뀐 파일·새 시험·A11 첫 시험에 직접 적용한 결과 0건이고, 이메일·전화·키 패턴도 0건입니다. 시험에는 공개 호텔명과 공개 좌표만 들어 있습니다. 새 시험 두 파일은 untracked라서 저장소 보안 시험이 스스로 검사하지 않습니다.

## 증거와 디스크

- `C:/_proj/routinga11fix1029_evidence`(약 73 MB, 그중 pgdata 70 MB이며 PG는 정지 상태, 데이터는 보존): `red.*`·`green.*`·`regression.*`·`contract.*`·`security.*`·`dod/`·`run.log`·`verify_fix.py`·`candidate-followup.patch`·`new-test.py`·`assemble.before.py`·`before/after.sha256`·`tracked-after-diff.json`·`handoff-index.before.md`가 있습니다. 보안 로그에는 보호 XML 탐지 원문이 들어 있으므로 wiki로 복사하지 않습니다.
- 쓰기 전에 `disk_guard check`(400 MB)를 실행했고 허용됐습니다. `disk_guard inventory`는 entries 0이었습니다. 이 작업의 증가분은 약 73 MB입니다. 이전 증거 `routinga11verify1029`·`routingresume1029_evidence`는 수정하지 않았고, 아무것도 삭제하지 않았습니다.

## 남은 것

1. 보호 XML 보안 HOLD를 정식으로 처리하기 전에는 통합·push하지 않습니다.
2. 이번 수정(+A11)을 독립 검토해야 합니다. 실제 모델·화면 수락은 하지 않았습니다. 활동으로 바뀐 체크아웃 줄이 확인 화면과 일정 화면에서 「규칙으로 채움」으로 어떻게 보이는지는 확인하지 않았습니다.
3. 남은 경계: 고객이 체크아웃 줄을 직접 숙박으로 고르면 그 선택을 유지하므로 끝 없는 숙박이 남을 수 있습니다(시험 ⑤가 이 동작을 고정합니다). 고칠지는 제품 결정 사항입니다. 독립 검토 P2(좌표 167 m 차이가 나는 같은 호텔의 분리)도 그대로 별도 요구로 남아 있습니다.
