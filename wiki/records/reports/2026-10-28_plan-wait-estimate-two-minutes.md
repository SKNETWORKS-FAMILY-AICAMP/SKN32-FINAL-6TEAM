---
type: report
title: 계획 읽기 · 계획 짜기 화면 예상 시간 안내 1분 → 2분쯤 (2026-10-28)
status: candidate
domain: travel
impl_scope: cs — 고객 웹 화면 문구(final_project_cs/frontend/apps/web). 서버 · 시간 제한 변경 없음
---

# 계획 읽기 · 계획 짜기 화면 예상 시간 안내 1분 → 2분쯤

`[2026-10-28 사용자 결정]` 기존 화면의 「1분쯤 걸려요」 예상 안내를 **「2분쯤 걸릴 수 있어요」**로 바꾼다. 새 안내를 덧붙이지 않고 기존 문구를 교체한다. 시간 제한 · 실제 성능은 바꾸지 않는다. 근거 표본: 여섯 일정 읽기 80.7초 1회(약속한 최대값이 아님).

## 후보

- 기준: 팀 `role-manager` `ffb5fb1b5`(fetch 확인) 위 격리 worktree `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-wait-copy-20261028/tree`
- 커밋 `72c6a718f`(로컬 · detached, **push 0 · 배포 0 · 로컬 serving 미반영**)
- patch `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-wait-copy-20261028/evidence/wait-estimate.patch` sha256 `c238f973eda0da557e4bf47a243536e3d8d41b3f05c610cbf0384025e02e2a0a`

## 바꾼 화면 (4/4 = 100%)

| 화면 | 파일 | 전 | 후 (한 / 영) |
|---|---|---|---|
| 계획 읽기 「계획을 확인하고 있어요」 | `src/features/plan-check/plan-check.tsx` `Reading` | 사진 한 장은 1분쯤 걸려요 / A photo takes about a minute | 사진 한 장은 2분쯤 걸릴 수 있어요 / A photo can take about two minutes |
| 계획 짜기 「일정을 짜는 중이에요」(계획 짜 주기) | `src/features/plan-check/planning-progress.tsx` | 1분쯤 걸려요 / It takes about a minute | 2분쯤 걸릴 수 있어요 / It can take about two minutes |
| 이용 방법 「읽는 중」 설명 | `src/features/help/content.ts` SCREENS `reading.note` | 1분쯤 | 2분쯤 걸릴 수 있어요 / can take about two minutes |
| 이용 방법 FAQ `files` | `src/features/help/content.ts` | 읽는 데 1분쯤 | 읽는 데 2분쯤 걸릴 수 있어요 / can take about two minutes to read |

문구는 기존 번역 구조(`t(ko, en)` · `Pair`)에 그대로 둔다. 숫자 설정값을 새로 만들지 않았다(표시 문구이며, 판정 · 시간 제한 값이 아님).

## 바꾸지 않은 것 (의도)

- 서버 무소식 안내 `intake-review.tsx` 「1분이 넘게 서버 소식이 없어요」(60초 무소식 실측 단계), `server-wait-banner`(8 · 30 · 60초) — 경과 시간 표시이지 예상 안내가 아니다.
- 서버 `travel.intake_reading.*` 시간 제한, 멈춤 판정(180초 `stalled`), 모방 서버 지연, `client.test.ts` 재시도 문구.
- `mockups/*.html`(디자인 기록), README 의 관광공사 한도 「1분쯤 뒤 다시」, `web-intakes.md` 의 실측 기록 「사진 한 장 ~45~60초」.
- 「사진 한 장은」 주어는 글(채팅) 접수에도 보이는 기존 표현 그대로다 — 이번 범위 밖(필요하면 별도 결정).

## 검증

| 시험 | 결과 |
|---|---|
| vitest 전체(`src/**/*.test.ts`) | 1,219/1,219 = 100% (새 시험 1 포함) |
| 새 vitest RED(옛 `content.ts`) | 1 failed → 수정 후 통과 |
| Playwright 모방 서버(`tests/live`, Edge): 새 spec 4 + `flow.spec` + `plan-check-screen.spec` | 첫 실행 50/51(새 en 계획 짜기 시험이 한국어 라벨 도우미를 써 실패 — 시험 수정), 수정 후 새 spec 4/4 |
| 새 Playwright RED(옛 tsx 2개로 별도 빌드) | 4/4 실패 확인 → 복원 |
| `tsc --noEmit` · 바뀐 파일 eslint | 0 / 0 |
| 실제 화면 캡처(모방 서버, 한 · 영) | `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-wait-copy-20261028/evidence/*.png` 4장 — 문구 육안 확인 |

★모방 서버 시험이다. 실제 서버 · x600 · 로컬 serving 확인은 하지 않았다.

## 남은 일

- 부모: 검토 후 role-manager → develop → main push 여부 결정(사용자 승인), x600 배포 확인, 로컬 3100 반영은 별도 승인.
