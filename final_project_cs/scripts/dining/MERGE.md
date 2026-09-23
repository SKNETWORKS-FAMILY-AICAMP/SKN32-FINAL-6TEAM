# 요식 합류 절차

`role-dining` 을 `develop` 에 합칠 때 필요한 것만 적는다.
요식이 무엇을 하는지는 `README.md` 에 있다.

---

## 먼저 돌린다

```bash
python scripts/dining/preflight.py
```

막는 문제가 0 이면 합쳐도 된다. 합친 뒤에도 한 번 더 돌린다.

이 점검이 있는 이유는 **합치고 나서 조용히 안 되는 것들** 때문이다.
도구가 등록되지 않아도 Team 은 죽지 않고 「모름」으로 답하고, 마이그레이션
번호가 겹쳐도 파일은 둘 다 존재하며, 링크가 비어도 판정은 그냥 NULL 이 된다.
전부 터지지 않고 틀리는 것이라 눈으로는 안 보인다.

---

## 1. 코어에 부탁하는 것 — 두 곳

### `app/tools/read_tools.py`

`read.place` 는 시각을 받지 않아 `open_at_slot` 이 어느 예약이든 같은 값이다.
시각을 받는 도구를 하나 더 둔다.

```python
from app.modules.travel_ops.dining.ledger import dining_state as _dining_state
```

`_travel_tools()` 의 표에 한 줄:

```python
"read.dining_state": self.dining_state,
```

그리고 메서드 하나:

```python
def dining_state(self, scope: ToolContext, *, place_id: str | None = None,
                 at: Any = None, until: Any = None, **_: Any) -> dict[str, Any] | None:
    """그 시각 그 장소의 요식 판정. 없으면 `None`(모름).

    ★`read.place` 와 달리 시각을 받는다. 「그 시각에 여는가」는 시각이
      있어야 답할 수 있고, 칸 하나에 미리 채워 두면 12시 예약과 22시 예약이
      같은 값을 보게 된다.
    ★코어 표를 읽지도 쓰지도 않는다. 코어 place_id 를 요식 원장 장소로
      바꾸는 것은 `dining.dn_core_place_link` 이고 그것도 요식 표다.
    """
    with self.connection_factory() as conn:
        return _dining_state(conn, scope.tenant_id, place_id, at, until)
```

**요식 쪽은 이미 끝나 있다.** `dining/team.py` 가 이 도구를 선언했고,
등록되기 전에는 `ToolNotAllowed` 를 잡아 예전처럼 답한다. 그래서 이 패치가
늦어도 아무것도 깨지지 않는다 — 다만 요식 판정이 원장에 닿지 않는다.

### 마이그레이션 번호

요식은 `020~032` 를 쓴다. 코어가 `001~019` 를 쓰고 도메인마다 열 개씩
나눠 쓰자는 제안이며 **아직 합의 전이다.**

**요식이 제안한 열 칸을 넘었다.** `029` 다음으로 `030~032` 가 붙었다. 다른
도메인이 `030` 대를 받으면 겹친다. 합류 전에 둘 중 하나로 정해야 한다.

- 요식에 `020~039` 스무 칸을 준다. 파일은 그대로 둔다
- 요식을 열 칸 안으로 다시 번호 매긴다. `migrate.py` 가 이름 순으로 한
  트랜잭션에 붙이므로 번호를 바꿔도 적용 결과는 같다. 요식 파일끼리의
  순서만 지키면 된다 (`021` 의 `distance_m` 을 `027` 이 쓴다 등)

지금 `role-activity` 가 `014` 와 `016` 을 다른 파일로 쓰고 있다.

| 번호 | develop · 이동 · 코어 · 요식 | 액티비티 |
|---|---|---|
| 014 | `014_itinerary.sql` | `014_activity_tour_disaster.sql` |
| 016 | `016_trip_request_key.sql` | `016_activities_disaster_to_watch.sql` |

`migrate.py` 는 `migrations/*.sql` 을 **한 트랜잭션에 이름 순으로** 붙인다.
같은 번호가 둘이면 붙는 순서가 의도와 달라질 수 있다. 요식 구간과는 겹치지
않지만 합류 전에 정리하는 편이 낫다. `preflight.py` 가 이것을 본다.

---

## 2. 합친 뒤에 돌리는 것

### 스키마

`migrate.py` 가 `020~028` 을 함께 올린다. 따로 할 일이 없다.

**다만 마이그레이션은 다시 돌려도 깨지지 않아야 한다.** `migrate.py` 는 버전
표가 없어서 매번 전부 다시 돌린다. 요식 것은 전부 `IF NOT EXISTS` 와
`CREATE OR REPLACE` 이고, 출처 등록은 `ON CONFLICT DO UPDATE` 다.

### 자료

```bash
python scripts/dining/parse_hours.py
python scripts/dining/make_load_sql.py
psql ... -f data/dining/_build/load_200.sql

python scripts/dining/make_holiday_sql.py
psql ... -f data/dining/_build/holidays.sql

python scripts/dining/make_attribute_sql.py
psql ... -f data/dining/_build/attributes.sql

python scripts/dining/make_truth_sql.py
psql ... -f data/dining/_build/truth.sql

python scripts/dining/make_operator_sql.py --dry    # 먼저 눈으로 본다
python scripts/dining/make_operator_sql.py
psql ... -f data/dining/_build/operator.sql
```

빈 DB 라면 `python scripts/dining/rebuild.py --db <DB> --keep` 한 줄이면 된다.

### 매칭

코어 `places` 와 요식 원장을 잇는다. **이것을 안 하면 판정이 코어에 닿지 않는다.**

```sql
-- 먼저 시험 실행. 아무것도 쓰지 않는다.
SELECT * FROM dining.link_core_places('<tenant_id>');

-- 결과가 맞으면
SELECT * FROM dining.link_core_places('<tenant_id>', 0.75, 'matcher', false);

-- 못 이은 것과 사유
SELECT reason, count(*) FROM dining.v_link_gap GROUP BY reason;
```

후보가 둘 이상인 장소는 잇지 않고 `ambiguous` 로 남긴다. 잘못 이으면 다른
식당의 영업시간으로 판정하게 되고, 그것은 틀린 답을 자신 있게 말하는 것이다.

### 확인

```bash
python scripts/dining/preflight.py
python scripts/dining/run_quality.py
```

---

## 3. 부딪힐 만한 파일

| 파일 | 왜 | 누구와 |
|---|---|---|
| `app/tools/read_tools.py` | 위 패치 두 줄 | 코어 |
| `app/modules/travel_ops/dining/` | `dining.py` 를 폴더로 바꿨다 | 코어 |
| `app/modules/travel_ops/replan.py` | 후보 고르는 방식이 다르다 | **전원** |
| `migrations/` | 번호 구간 | 전원 |

`dining.py` → `dining/` 은 등록 문자열
`app.modules.travel_ops.dining:DiningTeam` 이 그대로 풀리도록
`__init__.py` 가 재수출한다. 네 곳에서 이 이름을 쓰고 있고 전부 안 고쳤다.

---

## 4. 아직 정하지 못한 것

합류를 막지는 않지만 정해야 한다.

**후보 고르는 방식.** `replan.py` 는 탈락 뒤 사전식 비교로 **하나**를 고른다.
요식 `suggest_alternatives` 는 **세 축에서 하나씩** 준다(설계보완 2026-09-18 의 1번).
둘은 다른 그림이다. 요식 쪽을 코어에 제안할지, 요식은 후보만 주고 고르기는
코어에 맡길지 정해야 한다.

**라스트오더 여유.** `replan.py` 의 `ORDER_MARGIN_MIN` 은 20분이고 주석에
「우리가 고른 값(측정 아님)」이라고 적혀 있다. 요식 P-02 의 경고 임계는
60분이며 실측에서 나왔다 — 값을 표기한 77곳에서 중앙값 50분, 60분이 85.7% 를
덮었다. 근거가 있는 쪽으로 맞추자고 제안한다.

**코어 표 쓰기.** 지금은 읽기만 한다. `places.open_at_slot` 에 직접 쓰게 되면
`attributes` 는 통째로 대입하지 말고 `||` 로 합쳐야 한다. 액티비티가 같은 칸에
`indoor` 같은 값을 넣기 때문에 덮어쓰면 상대 값이 사라진다.

**식사 항목의 감시.** `watch.py` 주석에 「식사 항목의 시스템 감지는 소스가
없다 — 요식-P3·P7」이라고 적혀 있다. 그 소스가 이 원장이다.

깨울 때 할 일은 요식에 만들어 두었다. **깨우는 쪽은 코어가 정한다** — `watch.py`
든 크론이든 버튼이든 상관없고, 무엇으로 바뀌어도 요식은 고치지 않는다.

```python
from app.modules.travel_ops.dining.tick import tick_once

items = [(place_uid, starts_at), ...]    # 일정의 식사 항목. 코어가 꺼내 준다
for r in tick_once(conn, now, items, fetch=읽는쪽, trial=False):
    if r["notice"]:
        보낸다(r["notice"]["body"])        # 보내는 것도 코어
```

| 요식이 지키는 것 | 어떻게 |
|---|---|
| 몇 번 불러도 같다 | 1분마다 불러도 한 번만 묻고 한 번만 말한다 |
| 물을 때만 묻는다 | 방문 60분·20분 전의 5분 창 (`watch_window`) |
| 시계를 보지 않는다 | `now` 를 받는다 |
| 일정 표를 읽지 않는다 | `items` 를 받는다. 코어 표가 바뀌어도 깨지지 않는다 |
| 보내지 않는다 | 보낼 말을 돌려줄 뿐이다 |

`fetch` 는 읽는 쪽이다. 요식은 캐치테이블을 모른다. `trial=False` 면 캐치테이블
값으로는 말하지 않는다 — 본 갈래 판정이 시험 출처를 보지 않기 때문이다.

정해야 할 것 하나. 말하기로 정하면 그 자리에서 `dn_notice` 에 적는다. 그래서
같은 말은 두 번 나가지 않지만, 코어가 보내다 실패하면 그 말은 다시 오지 않는다.
반대가 낫다면 `record_notice` 를 코어가 보낸 뒤 부르면 된다.
