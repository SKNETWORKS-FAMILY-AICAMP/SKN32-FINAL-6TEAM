---
type: report
title: 화면에서 고른 일정에 묻는 채팅이 「어느 일정」 되묻기 · 옆 일정 답으로 끝나는 결함 — 격리 후보
status: draft
domain: travel
---

# 2026-10-25 화면에서 고른 일정에 묻는 채팅 (QA 「국립중앙박물관에 대해 궁금한 점」)

결론: 고른 일정(`item_id`)이 있는 이름 없는 이어 묻기가 ① 「가리키는 일정을 … 확인하지 못했어요」 되묻기, ② 고른 일정 **바로 앞 일정**의 답으로 끝나던 두 갈래를 서버 두 파일에서 고쳤습니다. 로컬 격리 후보까지입니다 — push · x600 배포 · 로컬 서빙 반영 전입니다.

## 문제 (QA 2026-10-25, 영상은 확인하지 못해 문장만 근거)

「국립중앙박물관에 대해 궁금한 점을 물어보세요 → 어느 일정에 대해 묻는지 다시 물어 봄」. 그 문구는 웹 채팅 막대의 입력 안내 `${subject}에 대해 궁금한 점을 입력하세요`(`frontend/apps/web/src/features/trip/trip-chat.tsx`, `subject` = 고른 일정의 장소 이름)입니다. 그 안내가 보일 때 웹은 고른 일정을 `item_id` 로 이미 보냅니다(`useTripChat.ask` 기본값 `pickedId` → `lib/live/gateway.ts` `item_id`). **웹은 바꿀 것이 없습니다.**

## 원인 (코드 · 실제 E4B 원출력으로 확정)

학습 E4B(`tripilot-pointer:e4b-ft`)는 고른 일정에 묻는 이름 없는 질문을 `reference=previous` 로 적고, 같은 4문장 중 3문장에서 기준 칸 `anchor_item` = 고른 일정 · `relation=before` 를 덧붙였습니다(답 대상 `target_item` 도 고른 일정).

1. `relation=before` + 기준 = 고른 일정 → `time_anchor.clean` 이 기준을 item 으로 올리고 `time_anchor.resolve` 가 **고른 일정 바로 앞 일정**을 계산 → 국립중앙박물관 대신 앞 식당을 답함(실측 3/4). 고른 일정이 여행 첫 일정이면 범위 밖(out_of_range) → 아래 2로 이어짐.
2. `fact_context.resolve` 는 `reference=previous` 이면 화면 선택을 쓰지 않고 직전 답 대상만 찾음 → 직전 답이 없으면 짧은 이어 묻기(`bare`) · 가리키는 말(「거기」)은 「가리키는 일정을 현재 여행에서 하나로 확인하지 못했어요. 일정 이름이나 날짜를 알려 주세요.」로 되물음 — QA 문장과 같은 증상.
3. 같은 이름 일정이 여럿이면 고객이 그중 하나를 골라도 되물음.

## 수정 (최소 · D-025 범위)

- `fact_context.resolve`: 유효한 직전 답 대상이 없을 때만 고른 일정을 이어 묻기의 대상으로 씀(`source=selection`). 조건: 날 · 시각 · 끼니를 말하지 않았고, 문장에 대상 말이 전혀 없거나(`bare`) 「거기 · 그거」로 가리켰고 모델 답 대상도 고른 일정. 같은 이름 여럿 중 고른 일정이 그 이름이면 그 일정.
- `read_requests.reply`: 한 일정 성질 사실(detail · address · hours · phone · description · price · entry_booking · food)에서 답 대상 = 고른 일정 = 기준(또는 기준 없음)이고 앞뒤만 채워졌으면 그 칸만 떼고 `relation_dropped` 로 근거에 남김(`near_dropped: anchor_is_target` 와 같은 규칙).
- 계약: [trip-chat-context](../../external/trip-chat-context.md) 2026-10-25 절. 2026-10-18 weather/outdoor previous 계약은 바꾸지 않았습니다.
- 바꾸지 않은 것: 프롬프트 · 스키마 · validator · 모델 · 웹 · DB · 권한. 모델 해석을 문장 낱말 규칙으로 다시 고치지 않았습니다(기존 `bare` · `pointing` · `scoped` 판정만 재사용).

## 검증

| 항목 | 결과 |
|---|---|
| 새 시험(develop d2ab93a6 원본에서) | RED 13 실패 / 11 통과(통과 11 = 보존해야 할 경계) |
| 새 시험 + 관련 기존 6파일(후보) | GREEN 155/155 = 100% |
| 실제 E4B 정상 웹 API, 비교 DB 새 tenant | 4/4 호출 사용. 원본 P1 박물관 · P3 앞 식당. 1차 후보(①만) P5 · P6 앞 식당 → ② 추가 |
| 같은 4개 실제 원출력 오프라인 재생(실모델 아님) | 원본 1/4 · 최종 후보 4/4 = 100% |
| 최종 해시 실제 E4B | **0회 — 호출 상한 4회 소진, 미검증** |

전체 관문(tests/architecture · contract · unit · security, `not live and not db and not slow`)과 ruff F/E9 결과, role-manager 기준 적용 결과는 후보 폴더 `cache/scratch/chat-subject-20261025-235618-22862/REPORT_KO.md` 에 적습니다.

## 남은 한계 · 결정 필요

- 고른 일정이 없을 때 E4B 가 같은 before 를 붙이면 여전히 앞 일정을 답할 수 있습니다(이번 범위 밖, 프롬프트 · 학습 쪽).
- 「거기 날씨 어때?」(weather/outdoor + previous)는 2026-10-18 계약대로 되묻습니다. 고른 일정으로 답하게 할지 사용자 결정이 필요합니다.
- 고른 일정 상태에서 「그 전 일정 …」을 E4B 가 답 대상 = 고른 일정으로 적으면 고른 일정으로 답합니다(모델 칸이 서로 어긋난 경우의 선택).

## 2026-10-26 추가 실 E4B 확인

- 최종 수정본(develop 후보 트리, 정상 웹 API·비교 DB 새 tenant `chat_subject_20261025_e8bdb5ff11ef`)으로 실 E4B 2회. 박물관(i3)을 고른 상태, `item_id` 전송.

| 문장 | 저장 답 | 모델 원칸 |
|---|---|---|
| 거기 운영시간 알려줘 | 국립중앙박물관의 운영시간은 모르겠어요 — 관광공사 조회가 연결돼 있지 않음. | hours, target=i3, previous, relation=before |
| 운영시간 알려줘 | 국립중앙박물관의 운영시간은 모르겠어요 — 관광공사 조회가 연결돼 있지 않음. | hours, target=i3, previous, relation=before |

- 2/2 = 100% 박물관으로 답했고 되묻지 않았다. `GET …/chat` 재조회의 마지막 assistant 문장이 POST 답과 같다. 모델은 여전히 before 를 붙였고 이번 수정(relation_dropped)이 앞 일정 계산을 막았다.
- 운영시간 값 자체는 이 시험 환경에 관광공사 조회가 없어 「모르겠어요」로 끝난다(대상 확인 시험이지 사실 값 시험이 아니다).
