# 캐치테이블 시험 값 — 등록 여행 식당 카드에 한 줄 보이기 (계획)

- 작성 2026-10-16 · 상태 **구현 — 2026-10-19 (미커밋)**
- 범위 `role-dining`(서버 한 필드) + 고객 웹 카드 한 줄(UI·검증 담당과 함께 확인 — `wiki/delivery/roles.md` 「고객 웹·API 연결」)

## 왜

캐치테이블 다리(`scripts/dining/catchtable.py` · `catchtable_auto.py`)는 웨이팅·빈자리를 읽어
`dining.dn_live_check` 에 `catchtable_trial` 로 적는다. 그러나 **고객 화면 어디에서도 그 값을 읽지 않는다**
(2026-10-16 실측 — 웹·서버에서 `v_live_check_fresh_trial` 을 읽는 곳 0). 시연에서 「읽었다」를 터미널로만 보인다.

## 지키는 것 — 바꾸지 않는다

| 규칙 | 근거 |
|---|---|
| 시험 값은 **판정·재계획·알림에 닿지 않는다** — 화면 표시뿐 | 206 `production_allowed=false` · 211 「본 갈래 판정은 한 글자도 안 바뀐다」 |
| 무인 반복 조회를 만들지 않는다 — 화면을 열어도 **조회하지 않고 DB 에 있는 것만 읽는다** | `catchtable.py` 머리말 4 (robots.txt) |
| 낡은 값·실패한 조회는 안 보인다 | `v_live_check_fresh_trial` 가 `outcome='ok'` · TTL 안만 낸다 |
| 보일 때는 언제나 「제휴 전제 시험」을 함께 적는다 | 206 주석 · `scripts/dining/README.md` 「시연에서 보이더라도 …」 |
| **기본은 꺼짐** — 켜지 않으면 응답 모양이 지금과 같다 | MCP 쓰기 스위치와 같은 방식(`travel.mcp.write_enabled`) |

## 무엇을 만드나

### 1. 스위치 (`config/guardrails.yaml`)

`dining.trial_live_view: false` — 시연 때만 켠다. 파이썬은 `get_guardrails()` 로만 읽는다.

### 2. 서버 — 항목 보기에 한 필드 (`app/domains/travel_ops/entry/trip_api.py` `_item_view`)

스위치가 켜졌고 항목이 `dining` 이며 장소가 원장과 이어져 있을 때만(`place_info._ledger_uid`) 넣는다.
꺼져 있거나 값이 없으면 **필드 자체가 없다.**

```json
"trial_live": [
  {"topic": "waiting", "state": "yes", "num": 41, "detail": "현재 웨이팅 41팀",
   "asked_at": "2026-10-16T12:03:00+09:00", "label": "제휴 전제 시험"}
]
```

- 읽는 곳: `dining.v_live_check_fresh_trial` 중 `source_code='catchtable_trial'` · `topic IN ('waiting','vacancy')`, 주제마다 가장 최근 하나.
- 읽기 함수는 요식 폴더에 둔다(`instances/dining/ledger.py` 옆) — `trip_api` 는 부르기만 한다. 요식이 캐치테이블 이름을 모르는 원칙(`tick.py:34`)은 출처 코드 상수 한 곳으로만 지킨다.
- 한 여행 화면에서 식당 수만큼 묻지 않게 **한 번에 묶어 읽는다**(`place_uid = ANY(%s)`).

### 3. 고객 웹 — 카드 한 줄 (`frontend/apps/web/src`)

| 파일 | 할 일 |
|---|---|
| `lib/live/gateway.ts` | `trial_live` 를 `TripStop.trialLive` 로 옮긴다. 모양이 다른 것은 버린다(`badges` 와 같은 방식) |
| `features/trip/model.ts` | 타입 한 줄 |
| `features/trip/trip-rows.tsx` `StopRow` | 영업시간 · 주소 줄 아래에 사실 한 줄: 「웨이팅 41팀 · 3분 전 확인」 + 작은 표시 「제휴 전제 시험」. 값이 없으면 줄도 없다 |

- 「몇 분 전」은 화면이 `asked_at` 으로 센다. 서버가 낡은 값을 안 보내므로 화면이 기한을 다시 판단하지 않는다.
- 빈자리는 `yes` → 「예약 가능한 시간 있음」, `no` → 「지금 예약 가능한 시간 없음」, `unknown` 은 안 보인다.
- 그 밖의 화면(계획 확인 · 채팅 · 알림)에는 넣지 않는다.

## 시험

| 시험 | 무엇을 본다 |
|---|---|
| 단위 (서버) | 스위치 꺼짐 → 필드 없음 · 켜짐+값 → 필드 · 다른 출처(`auto_map_check`)는 안 실림 · 낡은/실패 값 안 실림 |
| 통합 (`tests/integration/dining`) | 실제 뷰에서 묶어 읽기 — 기존 `record(...)` 도우미 재사용 |
| 아키텍처 | 본 갈래 판정이 시험 출처를 보지 않는다는 기존 시험이 그대로 통과 |
| 웹 (`gateway.test.ts` · 카드) | 필드 없음 → 줄 없음 · 웨이팅 41 → 문구와 「제휴 전제 시험」 표시 |

## 시연 순서

1. `dining.trial_live_view: true` 로 켠다.
2. `catchtable_auto.py --login` 으로 사람이 로그인 → `--place <식당> --i-know --uid <place_uid>` 한 번.
3. 등록 여행 화면에서 그 식당 카드에 「웨이팅 N팀 · 방금 확인 · 제휴 전제 시험」이 보인다.
4. 5분 지나면 줄이 사라진다(낡은 값은 안 보인다)는 것까지 보인다.
5. 시연 뒤 스위치를 끈다.

## 결정 — 2026-10-19

- **곧 갈 식사에만 보인다** — 식사 시작 1시간 전부터 시작 시각 전까지(`ledger.trial_due`). 사람이 1시간 전 · 30분 전에 다리로 한 번씩 읽고, 카드는 최신 값을 보인다. 그 시각에 저절로 읽게 만들지는 않는다(무인 반복 없음).
- 디스코드 · 토스트 알림으로 보내지 않는다 — 낡은 값이 사실처럼 남고, 막힌 출처의 값이 서비스 통지가 된다.

## 정할 것

- 카드 머리(접힌 상태에서도 보임)인가, 상세 보기 안인가 — 이 계획은 **카드 머리**로 적었다(시연에서 눈에 띄어야 한다).
- UI·검증 담당 확인 — 카드 구성은 10-13 목업으로 사용자가 정한 것이라 한 줄 추가도 확인을 받는다.
