# DoD-10 — 일일 배치가 count·ratio·임계값 급증 report 를 생성한다

- v5 §20 항목 10 / 검증 방법: scheduled job test
- 최초 판정: 2026-08-12 **부분 통과** (실데이터 급증 alert 미관측)
- 재측정: 2026-08-14 · 실측 원문 `wiki/records/evidence/_raw/DoD-10_v4.md`
- 2026-08-17: 배치가 **VOC/Feedback Analytics Team** 실행 경로로 바뀜(v7 §0 변경 4). 재현 명령 출력 불변 확인
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/unit/voc -v
python -m scripts.run_daily_feedback --date 2026-08-14
python  # 임시 tenant 에 실제 Case 를 임계 이상 생성 후 집계
```

## 실제 출력

```
collected 8 items
8 passed

{"alerts": [], "metrics": {...}}          ← demo tenant (Case 없음 → 0)

별도 임시 tenant 실측:
tenant = raw_voc_cebb7113f41544459dfec276c863ba24
alert_report = {'tenant_id': 'raw_voc_...', 'period_start': '2026-08-07', 'period_end': ...}
teardown = deleted
```

## 판정 근거

| 요구 (v5 §14-3) | 결과 |
|---|---|
| 배치가 실행되고 report 를 남긴다 | **통과** |
| 집계 기간 = 전일 + 직전 7일 | **통과** — `2026-08-07` ~ |
| 지표 4종(intent/issue count·negative·unresolved·totals) | **통과** |
| ★**실데이터에서 급증 alert 이 발생한다** | **통과** — 임시 tenant 에 임계 이상 Case 를 만들어 `alert_report` 관측 (최초 판정 때 미관측이던 부분) |
| 급증식이 v5 §14-3 그대로 | **통과** — `today >= max(5, 1.5×avg7)` AND `today − avg7 >= 3`. 수치는 `config/guardrails.yaml` 의 `5/1.5/3` |
| 경계값 검사 | **통과** — 두 조건을 각각 단독으로 깨는 fixture 포함(8건) |
| z-score·클러스터링·토픽모델링 없음 | **통과** (v5 §3 Out 준수) |
| 데이터 없을 때 0 을 정직하게 낸다 | **통과** — demo tenant 에서 `alerts: []`, 가짜 숫자 없음 |
| 테스트 격리 | **통과** — 임시 tenant 사용 후 `teardown=deleted` |

## 최초 판정에서 무엇이 바뀌었나

2026-08-12 에는 급증 로직이 **단위 테스트 fixture 로만** 검증됐고,
실제 Case 흐름에서 분류 → 집계 → alert 로 이어지는 경로가 관측되지 않았다.
당시 DoD-09(분류기 미연결)가 막혀 있어 API 로 만든 Case 가 전부 `escalated` 였고
`intent`/`issue_code` 가 NULL 이라 집계 대상이 되지 못한 것도 원인이었다.

분류 배선이 수정된 뒤 임시 tenant 에 실제 Case 를 만들어 재측정했다.

## 한계

- 급증을 **인위적으로 만든** 데이터다. 실제 고객 문의 패턴에서의 오탐/미탐률은 측정하지 않았다
- v5 §15-3 의 **VOC alert precision**(실제 검토된 급증 alert 중 유효 비율)은 측정 대상이 아니었다 —
  그건 평가(DoD-15/16) 영역이고, 이번 실행에서도 다루지 않았다
- alert 이 `outbox` 로 발행되어 **실제로 전달되는지**는 이번에 확인하지 않았다

## ★2026-08-17 — VOC 를 Agent Team 으로 (v7 §0 변경 4)

`app/modules/customer_ops/feedback_team.py::FeedbackAnalyticsTeam` 신설.
`scripts/run_daily_feedback.py` 가 `run_daily_feedback()` 을 직접 부르지 않고
**이 Team 을 통해** 실행한다 — v7: *"기존 배치는 이 Team 의 실행 형태다."*

```
python -m scripts.run_daily_feedback --date 2026-08-14
→ {"alerts": [], "metrics": {...}, "period_end": "2026-08-14",
   "period_start": "2026-08-07", "tenant_id": "demo"}
```

★**재현 명령의 출력이 이전과 같다.** 위 §실제 출력 의 `{"alerts": [], "metrics": {...}}` 모양이
그대로 재현된다 — 이 문서가 실측으로 삼은 명령이 계속 유효하다.

### ★한 번 잘못 나왔다가 고쳤다

발주 지시서에 "CLI 동작은 바뀌면 안 된다" 를 명시했는데도,
1차 구현은 `TeamResult` 봉투 전체를 찍었다:

```
{"action_proposals": [], "answer": "No VOC alerts detected", ...,
 "evidence": [{"value": {...}}], "outcome": "completed", ...}
```

**이 문서의 재현 명령이 더 이상 위 §실제 출력 을 내지 않게 되는** 회귀였다.
`FeedbackAnalyticsTeam` 이 `Evidence.value` 에 report 전체를 담고,
스크립트가 `run_daily_feedback()` 을 **다시 부르지 않고** 그 값을 그대로 찍도록 고쳤다 —
Team 을 거치되(v7 요구) CLI 계약은 지킨다(이 문서 요구).

### 새 판단(judgment) — 이 Team 이 하는 것

전에는 배치가 report 를 만들 뿐이었다. 지금은 Team 이 alert 유무로 **판정**한다:
alert 있으면 `outcome=escalated`/`next_action=escalate`, 없으면 `completed`/`respond`.
v7 이 요구한 *"집계·임계값·알림·위임을 판단"* 이 이 판정이다.

### ★이 Team 은 Controller 라우팅 대상이 아니다

`accepted_case_types=[]` — 실제 고객 Case 가 이 Team 으로 라우팅되면 안 된다
(스케줄러가 합성 `TeamTask` 를 만들어 직접 부른다). 테스트로 고정했다:
`tests/unit/test_composition_root.py::test_feedback_team_does_not_claim_case_routing`.

테스트: **320 passed** (319 → +2, feedback_analytics 팀 목록 반영 + 라우팅 격리 테스트).
