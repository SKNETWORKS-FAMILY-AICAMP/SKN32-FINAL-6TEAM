# 여행 분류 어휘와 라우팅 — 실행 명세

`[초안 2026-09-09]` 여행 Case 가 Team 에 도달하지 못하는 것을 푸는 명세다.
**제안한 값이 실제로 라우팅되는지 시뮬레이션으로 확인한 위에 쓴다.**

★**이 문서는 코드를 고치지 않는다.** 결정과 값만 정한다. 적용은 코드 세션 몫이다.

---

## 0. 결론 먼저

**두 축을 다 쓴다(안 A). 계약은 안 바뀐다.**

```
case_type   객체 종류   activity · booking · mobility · dining · lodging · flight
intent      요청 종류   itinerary_submit · incident_report · confirm_request
                       · adjust_reject · other          ← v10 §5-A 의 다섯
```

`case_type` 은 **`issue_code` 의 접두에서 나온다.** 새 칸을 안 만든다.

`[실측 2026-09-09]` 제안 값으로 시뮬레이션한 결과 — **`issue_code` 17개 전부
라우팅 성공, 팀 6개 전부 도달.**

---

## 1. 왜 이 모양인가

### 레지스트리는 이미 두 축을 받는다

```python
resolve(case_type, intent)
    case_type  →  accepted_case_types 와 대조해 Team 을 고른다
    intent     →  capability 네임스페이스로 좁힌다 (선택)
```

그런데 `controller.py:71` 이 이렇다.

```python
entry = self.registry.resolve(case_type=intent or "", intent=intent)
```

**같은 값을 둘 다에 넣는다.** 그래서 `intent` 가 곧 Team 선택 값이 되고,
Team 이 받는 것은 객체 종류이므로 `intent` 도 객체 종류여야만 했다.

### 요청 종류를 intent 에 넣어도 안 깨진다

`[실측 2026-09-09]` 걱정한 것은 "요청 종류는 capability 네임스페이스와 안 맞는데
넣으면 라우팅이 깨지지 않나" 였다. **안 깨진다.** 코드가 이렇게 돼 있다.

```python
if intent:
    intent_matches = [...네임스페이스가 맞는 것...]
    if intent_matches:          # ← 비어 있으면 그냥 안 좁힌다
        matches = intent_matches
```

**못 좁히면 안 좁힐 뿐 실패하지 않는다.** 시뮬레이션으로 확인했다 —
`resolve(case_type='activity', intent='사건 신고')` → `activity` 팀.

| `case_type` | `intent` | 결과 |
|---|---|---|
| activity | 사건 신고 | `activity` |
| booking | 사건 신고 | `booking_handoff` |
| mobility | 사건 신고 | `mobility` |
| dining | 사건 신고 | `dining` |
| lodging | 사건 신고 | `lodging` |
| flight | 사건 신고 | `flight` |

### 그래서 계약을 안 바꿔도 된다

`Classification` 은 지금 넷이다 — `sentiment` · `intent` · `issue_code` · `severity`.
**`issue_code` 가 이미 객체 접두를 달고 있다**(`order_payment_failed`,
`shipping_delayed`). 그 관례를 여행에 그대로 쓰면 `case_type` 을 접두에서 뽑을 수 있다.

```
issue_code = "activity_weather_risk"
                ↑ case_type        ↑ 무엇이 문제인가
```

★**칸을 새로 만들면 계약 변경이고 Registry·A2A·평가 하네스가 다 걸린다.**
접두 규칙이면 그게 없다.

---

## 2. 정할 값

### `INTENTS` — 요청 종류 다섯 (v10 §5-A)

```python
INTENTS = frozenset({
    "itinerary_submit",   # 일정 제출
    "incident_report",    # 사건 신고
    "confirm_request",    # 확인 요청
    "adjust_reject",      # 조정 거부
    "other",              # 그 외
})
```

★**v10 §5-A 의 한국어 라벨을 ASCII 슬러그로 옮겼다.** 뜻은 그대로다.
기존 `INTENTS` 도 ASCII 였고(`order`·`shipping`…), 값이 프롬프트·DB·평가
데이터셋을 오가므로 한국어를 넣으면 인코딩 문제가 붙는다.

`[미확보]` 슬러그 이름은 제안이다. v10 §5-A 는 한국어만 적어 두었으므로
**어느 슬러그를 쓸지는 정해진 바가 없다.**

### `ISSUE_CODES` — 객체 접두 + 문제

```python
ISSUE_CODES = frozenset({
    "activity_weather_risk", "activity_cancel_or_change", "activity_other",
    "booking_change_needed", "booking_cancel_needed",
    "booking_status_unknown", "booking_other",
    "mobility_delay", "mobility_route_broken", "mobility_other",
    "dining_closed", "dining_conditions_unmet", "dining_other",
    "lodging_status", "lodging_other",
    "flight_status", "flight_other",
    "other",
})
```

`[실측 2026-09-09]` 검증한 것 —

```
팀이 받는 case_type    activity · booking · dining · flight · lodging · mobility
issue_code 접두        activity · booking · dining · flight · lodging · mobility
접두 ⊆ case_type       True    못 받는 접두 없음    접두 없는 case_type 없음
라우팅                 17/17 성공
```

★**`"other"` 만 접두가 없다.** 그 하나는 어느 팀에도 안 간다 —
`case_type` 을 못 뽑으므로 `escalated` 로 가야 한다. **그게 맞는 동작이다.**

### 팀별 대응 확인

| 팀 | `accepted_case_types` | 대응하는 `issue_code` | capability |
|---|---|---|---|
| `activity` | `activity` | `activity_*` 3개 | `check_cancelable` · `check_feasible` · `propose_change` |
| `booking_handoff` | `booking` | `booking_*` 4개 | `verify` · `prepare_change` · `prepare_cancel` |
| `mobility` | `mobility` | `mobility_*` 3개 | `check_route` · `status` · `exception` |
| `dining` | `dining` | `dining_*` 3개 | `check_open` · `check_conditions` |
| `lodging` | `lodging` | `lodging_*` 2개 | `status` |
| `flight` | `flight` | `flight_*` 2개 | `status` |

---

## 3. 고칠 자리 셋

### ① 분류 어휘

`app/modules/customer_ops/feedback.py:48,51` — 위 §2 의 두 집합으로 교체.

★**파일 위치도 정리 대상이다.** 여행 어휘를 `customer_ops` 파일이 들고 있게 된다.
`[미확보]` 옮길지, 어휘를 설정으로 뺄지 안 정해졌다 —
**어휘를 설정으로 빼면 도메인이 또 바뀌어도 코드를 안 고친다.**

### ② 컨트롤러가 두 축을 쓰게

`app/application/controller.py:71` 과 `:167`

```python
# 지금
entry = self.registry.resolve(case_type=intent or "", intent=intent)

# 제안 — case_type 은 issue_code 접두에서
case_type = (case.get("issue_code") or "").split("_")[0]
entry = self.registry.resolve(case_type=case_type, intent=intent)
```

★두 자리 다 고쳐야 한다. `:71` 은 capability 선택, `:167` 은 라우팅 재개다.

`[미확보]` `issue_code` 가 `"other"` 이면 접두가 `"other"` 라 어느 팀에도 안 맞고
`RegistryError` 가 난다. **그때 `escalated` 로 보내는 경로가 이미 있는지 확인이
필요하다** — 없으면 예외가 그대로 올라간다.

### ③ 가드 테스트를 등록표 기준으로

`tests/unit/voc/test_feedback_intent_alignment.py`

지금은 `VocStoreManagerTeam` **하나**를 본다. 그 팀은 `config/project.yaml` 에
**등록조차 안 돼 있다.** 그래서 도메인이 바뀌어도 계속 통과한다.

```python
# 제안 — 등록표를 읽는다
from app.core.project_config import load_project_config

def test_every_routable_case_type_is_reachable():
    """★고정된 예시가 아니라 등록표를 본다.
    2026-09-09 에 이 테스트가 등록 안 된 팀 하나만 보느라
    여행 Case 가 전부 라우팅 불가인 상태를 통과시켰다."""
    accepted = {ct for team in _registered_manifests() for ct in team.accepted_case_types}
    prefixes = {c.split("_")[0] for c in ISSUE_CODES if "_" in c}
    assert accepted <= prefixes, f"issue_code 접두가 없는 case_type: {accepted - prefixes}"
```

★**검사 방향이 바뀐다.** 전에는 "Team 이 받는 것을 분류기가 만들 수 있나" 였고,
이제는 "**Team 이 받는 것마다 그리로 가는 `issue_code` 가 있나**" 다.
접두가 없으면 그 팀은 영원히 안 불린다.

---

## 4. 적용 순서와 확인 방법

| # | 무엇 | 끝났는지 어떻게 아나 |
|---|---|---|
| 1 | `INTENTS` · `ISSUE_CODES` 교체 | `classify()` 에 여행 라벨을 넣어 `ClassificationFailed` 가 안 나는 것 |
| 2 | 컨트롤러 두 줄 | `resolve` 가 6팀에 도달하는 것 (§1 표) |
| 3 | 가드 테스트 | 일부러 접두를 지운 `issue_code` 로 **실패하는** 것을 먼저 확인 |
| 4 | 평가 데이터셋 | `golden.jsonl` 의 `expected_intent` 를 새 다섯으로 |

★**3번을 "통과하는지" 로만 확인하면 안 된다.** 지금 테스트가 통과하면서
못 잡고 있었다. **일부러 깨뜨려 빨간 것을 본 뒤에** 고쳐야 가드인지 안다.

---

## 5. 안 정해진 것

| 무엇 | 왜 정해야 하나 |
|---|---|
| 슬러그 이름 다섯 | v10 §5-A 는 한국어만 적었다. 값이 DB·프롬프트·평가셋을 오간다 |
| 분류 어휘의 자리 | `customer_ops` 파일이 여행 어휘를 들게 된다. 설정으로 빼면 다음 도메인에서 안 고쳐도 된다 |
| `issue_code = "other"` 처리 | 접두가 어느 팀에도 안 맞는다. `escalated` 경로가 있는지 확인 |
| `capability_for` 가 안 좁히는 것 | 시뮬레이션에서 `intent` 를 줘도 전부 **기본 capability** 로 떨어졌다. 요청 종류로 capability 를 고르려면 별도 규칙이 필요하다 |

★**마지막 것이 중요하다.** 지금 구조로는 "사건 신고" 가 와도 `activity` 팀의
`check_feasible`(기본)이 불린다. `propose_change` 로 가려면 **`capability_for` 가
요청 종류를 읽어야 한다.** 지금은 `input_text` 만 본다.

---

## 관계

- [`A-COP_구현계획서_v10.md`](A-COP_구현계획서_v10.md) — §5-A 코어 1 분류 라벨
- [`A-COP_여행전환_현황_2026-09-09.md`](A-COP_여행전환_현황_2026-09-09.md) — 층별 현황
- [`A-COP_지속관리루프와_알림_설계.md`](A-COP_지속관리루프와_알림_설계.md) — 라우팅 축 A/B/C
