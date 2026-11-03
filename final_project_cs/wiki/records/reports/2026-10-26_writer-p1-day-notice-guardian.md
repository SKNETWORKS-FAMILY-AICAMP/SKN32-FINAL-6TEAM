---
type: report
title: writer 감사 P1 두 건 — 하루 시작 안내 D-020 정합(후보 staged) · 채팅 변경 결과 writer 연결(보류)
status: candidate
domain: travel
---

# writer 감사 P1 — role-manager 후보

- 작성: 2026-10-26 KST · Hermes subagent(Opus) · 근거 감사: [2026-10-26_customer-response-writer-audit](2026-10-26_customer-response-writer-audit.md) W12·W5
- 기준: role-manager `c34bd376fce473ac8b42bb101974f7f374e4e10b`(ls-remote 확인). 작업 트리 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/writer-p1-20261026-051647/rm`(detached worktree)
- 지킨 것: push 0 · 모델 호출 0 · 원본 코드 수정 0 · DB·네트워크 차단 runner(`WRP1_SOURCE_ROOT`)

## 결론

1. **(1) 하루 시작 안내 — 고침, staged.** 항로 지킴이 켜짐일 때만 「먼저 조정하고 알려드릴게요」, 꺼짐·미응답·운영자 끔은 「바꾸기 전에 먼저 여쭤볼게요」. 빠른 관문 실패 0.
2. **(2) 채팅 변경 결과 → 공통 writer — 하지 않음.** role-manager(`c34bd376`)와 develop(`30e9f0a0`) 어디에도 공통 writer(`travel_ops/components/response/writing.py`)와 `question_status`·`response_status`가 없습니다(app·wiki·final_project_ui grep 0건). 감사가 본 writer는 로컬 live v7a(git 밖 source)에만 있습니다. role-manager에서 변경 답에 상태를 붙이려면 writer 이식과 `chat_reply`의 새 공개 필드가 필요해서, 지시대로 보고만 합니다.

## (1) 변경

| | 전 | 후 |
|---|---|---|
| 항로 지킴이 켜짐(`survey.auto_on_disruption` True) | 일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요. | 같음 |
| 꺼짐(`ask_first`) · 미응답(기본 `replace`만 저장) · 설문 없음 · 운영자 끔(`travel.guardian.enabled`) | 일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요. | 일정에 영향을 주는 변동이 확인되면 **바꾸기 전에 먼저 여쭤볼게요.** |

- `trip_reminders.day_phrase(..., auto_adjust=False)` — 기본값은 먼저 확인(D-020 「설정·설문 미응답 = 꺼짐」).
- `TripReminders._payload`가 `survey.auto_on_disruption(trip["constraints"])`를 넘깁니다. `pending.decide`·`guardian.is_on`과 같은 판정 함수입니다.
- 알림 payload 키(`type`·`kind`·`version`·`text`·`template`·`values`)는 그대로입니다. 문구틀이 하나 늘어 언어마다 번역 1회가 추가됩니다(`notify/phrase.py` 캐시).
- wiki: `wiki/architecture/notifications.md` 「구현 상태」 표에 「하루 시작 끝 문장」 행 추가.

## 시험

- RED(`red.log`): 새 시험 7건 중 6 실패, 1 통과(켜짐 문구 보존 시험 — 원래 동작).
- GREEN(`green.log`): 새 시험 + `test_notice_phrase_cache` 22/22 = 100%.
- 빠른 관문 `tests/architecture tests/contract tests/unit tests/security -m 'not live and not db and not slow'`(venv `date_risk_env_312`, `-p pytest_asyncio.plugin`): **9377 passed / 9550 collected, 실패 0 · 오류 0 · skip 173** — 실행 9377/9377 = 100%(`gate.xml`).
- ruff `--select F,E9`: 통과.

## 산출물

- staged: `final_project_cs/app/domains/travel_ops/components/watch/trip_reminders.py`, `final_project_cs/tests/unit/travel/test_day_notice_guardian_wording.py`, `wiki/architecture/notifications.md`
- tree `3e7561b51dcee735a716f359389844c6758d594a`, patch `writer-p1.patch` sha256 `f1ae394e4d86e1c90eb18bf31d2272d367dc86363d69af2ee8f479de763d0b9a`, `COMMIT_MSG.txt`
- 증거 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/writer-p1-20261026-051647/`

## 겹침

- `trip_messages.py`·`decision_unit.py`·`edit_intent.py` 수정 0 — 다른 워커와 겹침 없음.

## 남은 일

- (2)를 하려면 먼저 결정: v7a의 `response/writing.py`·`public.py`를 role-manager로 이식하고 `chat_reply`에 `response_status`(question_status 포함)를 공개 투영으로 추가할지. 웹 소비 쪽(final_project_ui) 계약도 함께 바뀝니다.
- 감사 모순 2의 「최고 안을 먼저 적용」 서술은 role-manager의 `wiki/architecture/notifications.md`에서 찾지 못했습니다(grep 0건). v7a source 쪽 문서만 해당될 수 있습니다.
