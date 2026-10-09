---
type: decision
title: develop 판 활동 팀에 판정 LLM 을 섀도로 붙인다 — 기본은 규칙, 켜는 환경만 섀도
description: D-CS-008(role-activity-test 한정 실험)을 develop 판 활동 팀(team.py) 위로 옮긴다. 기본 모드는 rule, 섀도 기록을 모을 환경만 .env 로 shadow. 정기휴무 · 실내외 · 재난문자 · 실시간 운영 상태 넷만, 운영시간은 붙이지 않는다
status: draft
tags: [architecture, llm, travel, activity]
owners: [human:미배정]
domain: travel
---

# D-CS-015 develop 판 활동 팀에 판정 LLM 을 섀도로 붙인다

`[결정 2026-10-09]` 사용자 결정(설계 제안 그대로).
- 결정 범위: D-CS-008 은 테스트 브랜치 실험 기록으로 두고, develop 판은 **이 결정**으로 받는다.
- 기본 모드: **`rule`**. 섀도 기록을 모을 환경만 `.env` 의 `ACOP_ACTIVITY_JUDGE_MODE=shadow` 로 켠다.
- 붙일 판정: ① 정기휴무 · ③ 실내외 · ④ 재난문자 · ⑤ 실시간 운영 상태 — 모두 **섀도**. ② 운영시간은 붙이지 않는다.
- 설계와 진행 기록: [액티비티 LLM 연동 계획서 §9](../teams/액티비티%20LLM%20연동%20계획서.md)

## 왜 새 결정인가

[D-CS-008](D-CS-008-activity-llm-judgment-experiment.md) 은 「`role-activity-test` 브랜치 안에서만, `develop` · `main` 에 합치려면
평가 결과를 붙여 결정을 새로 받는다」였다. 2026-10-09 통합으로 이 브랜치의 등록된 활동 팀이 develop 판(`team.py`)이 됐다 —
여기에 붙이는 순간 develop 으로 가는 코드가 된다. D-CS-008 의 실험(role-activity 판 `team_a.py` + `feasibility.py`)은 기록으로 남는다.

★`D-CS-008` 번호는 운영 콘솔 결정([D-CS-008-ops-console-separate-app](D-CS-008-ops-console-separate-app.md))도 쓴다 — 그래서 새 번호다.

## 무엇을 하나

| 판정 | develop 판의 지금 판정 | 붙이는 자리 · 조건 |
|---|---|---|
| ① 정기휴무 | `closure_rules.read_closure`(휴무 원문) | `team._hours_check` — 휴무 원문이 있을 때 |
| ③ 실내외 | 장소 값 → 관광공사 분류(`read.place_class`) → 모르면 먼저 묻기 | `team._indoor_outdoor` — 분류까지 모를 때만 |
| ④ 재난문자 | 공유 점검 유형 목록 + 재난 정지 기준(`safety.classify`) | 공유 점검이 이상으로 세지 않고 정지 대상도 아닌 문자가 있을 때 |
| ⑤ 실시간 운영 | 없음 | 성립 직전 — 실외이거나 시작까지 `live_status_within_hours` 안 |

- **② 운영시간은 붙이지 않는다.** develop 은 새벽 작업(`catalog_hours` — `place_hours.read_hours`)이 원문을 규칙 → 안 되면
  모델로 읽어 요일표로 둔다. 요청마다 다시 해석할 것이 거의 없다.
- 판정 계층(`instances/activity/judge/`) · 어댑터 · 프롬프트 · 섀도 표(031) · 조립 배선은 D-CS-008 때 만든 것을 그대로 쓴다.
  role-activity 판의 `feasibility.py` 믹스인은 쓰지 않는다.

## 지키는 것

- **섀도에서 고객 결과는 규칙 모드와 같다** — 답변 · `decisions` · 근거 · 경고 · 실패 코드 · 제안 전부. LLM 이 모든 판정에서
  반대로 답해도 같아야 한다(시험으로 센다).
- **섀도의 비교 기준은 develop 판의 지금 판정이다.** role-activity 판 규칙(장소명 짐작 · 등급만 보는 재난)과 비교하지 않는다.
- D-CS-008 의 「지키는 것」(계산 판정은 코드에 · 모름은 모름 · 확정 불가를 뒤집지 않음 · 웹 본문 저장 안 함)을 그대로 지킨다.
- 위급재난 · 재난 정지 대상 문자는 판정 계층에 보내지 않는다.

## 이 결정이 **말하지 않는 것**

- **`llm` 모드 전환.** 계획서 §8 기준을 develop 판 섀도 수치로 다시 잰 뒤 따로 정한다. ③ · ④ 는 감시 경로
  (`disruptions.py` · `pending.needs_consent`)가 같은 값을 쓰도록 바꾸는 설계까지 함께여야 한다 — 성립 판정만 바꾸면 둘이 어긋난다.
- 대체 장소 후보의 판정 LLM, 다른 팀의 판정.
- `team_a.py` 보존본 정리(판정 LLM 이 develop 판에서 돌기 시작한 뒤에 정한다).

## 되돌리는 조건

D-CS-008 과 같다. 하나라도 해당하면 모든 환경을 `rule` 로 두고 이 결정을 `superseded` 로 닫는다.
- 섀도 수치에서 LLM 이 develop 판 규칙보다 정확도가 낮다
- 인용 · 출처 검증 탈락으로 대부분 「모름」이 된다
- 섀도 비용 · 백그라운드 부하를 감당할 수 없다

## 관계

- 앞선 실험 — [D-CS-008 활동 판정 LLM 실험](D-CS-008-activity-llm-judgment-experiment.md)
- 계획 · 진행 기록 — [액티비티 LLM 연동 계획서 §9](../teams/액티비티%20LLM%20연동%20계획서.md)
