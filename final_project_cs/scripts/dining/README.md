# 요식 에이전트 데이터와 판정

식당이 그 일정 시각에 문을 여는지 판정한다. 관광공사 영업시간 원문을 구조로 바꿔 쌓고,
코어가 읽는 `places.open_at_slot` 에 넣을 값을 계산한다.

코어가 이 자리를 비워두고 있다. `modules/travel_ops/dining.py` 는 `open_at_slot` 한 칸만 읽어
답을 만들고, `infrastructure/travel/tour_api.py` 는 `answers_open_at_slot=False` 로 원문만 넘긴다.
그 사이를 채우는 것이 이 저장소다.

상태는 초안이다. 팀 합의와 코어 협의가 끝나지 않았다.

---

## 폴더 구성

```
final_project_cs/
  app/infrastructure/db/migrations/
    020_dining_schema.sql      테이블 7개와 인덱스, 출처 등록
    021_dining_core_link.sql   코어 연결 표, 판정 뷰, 판정 함수
    022_dining_matcher.sql     코어 장소와 원장 장소를 잇는 매칭기
    023_dining_holiday.sql     명절과 공휴일 경고, 공휴일 달력 표
    024_dining_links.sql       지도 링크와 전화번호
    025_dining_attribute.sql   매장 속성. 조건별 판정
    026_dining_live_check.sql  현장 확인 기록과 물음 만들기
  app/modules/travel_ops/dining/
    __init__.py                DiningTeam. 액티비티와 같은 모양이다
  scripts/dining/
    README.md                  이 문서
    parse_hours.py             영업시간과 휴무 원문을 구조로
    make_load_sql.py           구조를 적재 SQL 로
    make_holiday_sql.py        공휴일 달력을 적재 SQL 로
    make_attribute_sql.py      매장 속성을 적재 SQL 로
    make_audit_sheet.py        오추출률 측정용 대조표
    make_truth_sql.py          검수한 대조표를 정답셋으로
    make_operator_sql.py       검수자가 확인한 실제 값을 원장으로
    run_quality.py             정답셋에 대고 채점하고 실행끼리 비교
    report_quality.py          품질 결과를 문서로
    run_check.py               현장 확인 한 번을 돌린다
    inspect_app.py             원장 확인기. 판정을 눈으로 따라가는 화면
    dev_up.py                  DB 와 확인기를 한 번에 띄운다
  data/dining/
    tourapi_음식점_소개정보.json     영업시간 원문 200건
    tourapi_서울_음식점_목록.json    좌표와 주소 990건
    holidays_2026_2027.json          공휴일 달력 46일
    truth/                           사람이 검수한 결과. 정답셋의 원본이다
    _build/                          생성물. 저장소에 넣지 않는다
```

마이그레이션 번호 020 번대는 요식 구간이다. 코어가 001 부터 019 까지 쓰고
도메인마다 열 개씩 나눠 쓰자는 제안이며 아직 팀 합의 전이다.

## 전제

| | |
|---|---|
| PostgreSQL | 16 |
| 확장 | pgcrypto, btree_gist, fuzzystrmatch |
| 파이썬 | 3.11 이상. 표준 라이브러리만 쓴다 |

PostGIS 는 쓰지 않는다. 코어 확장 목록에 없기 때문이며, 좌표는 위경도 칸으로 두고
거리는 함수에서 직접 계산한다.

`btree_gist` 가 없으면 테이블 생성이 실패한다. 영업 구간이 겹치지 않게 막는 제약이 이 확장을 쓴다.

개발 중에는 코어 팀과 같은 방식으로 띄웠다. 윈도우 서비스가 아니라 conda 환경의 프로세스다.

```
conda create -y -n pgv -c conda-forge postgresql=16
initdb -D <데이터 디렉터리> -U postgres -E UTF8 --locale=C
pg_ctl -D <데이터 디렉터리> -o "-p 5433" -l <데이터 디렉터리>/server.log start
```

포트를 `-o "-p 5433"` 으로 명시해야 한다. 빠뜨리면 5432 로 뜬다.

---

## 실행 순서

### 1. 스키마

```
psql -h 127.0.0.1 -p 5433 -U postgres -d <DB> -v ON_ERROR_STOP=1 -f app/infrastructure/db/migrations/020_dining_schema.sql
psql -h 127.0.0.1 -p 5433 -U postgres -d <DB> -v ON_ERROR_STOP=1 -f app/infrastructure/db/migrations/021_dining_core_link.sql
```

```
psql ... -f app/infrastructure/db/migrations/023_dining_holiday.sql
psql ... -f app/infrastructure/db/migrations/024_dining_links.sql
```

`04` 는 달력 표를 만들기만 하고 값은 넣지 않는다. 값은 아래 4번에서 넣는다.

`022_dining_matcher.sql` 은 코어 `places` 표가 있어야 올라간다. 코어 DB 에 얹는 경우에만 돌린다.
나머지는 순서대로 돌리면 되고, `024` 는 `023` 의 함수를 고쳐 쓰므로 뒤에 와야 한다.

### 2. 원문을 구조로

```
python scripts/dining/parse_hours.py
```

`data/dining/tourapi_음식점_소개정보.json` 을 읽어 `data/dining/_build/parsed_hours.json` 을 만든다.
표본 200건 기준으로 이런 값이 나온다.

| 항목 | 값 |
|---|---|
| 영업 구간 생성 | 92.5% |
| 요일마다 다름 | 31.0% |
| 브레이크 | 32.5% |
| 라스트오더 | 47.0% |
| 휴무 규칙 | 37.0% |

### 3. 적재

```
python scripts/dining/make_load_sql.py
psql -h 127.0.0.1 -p 5433 -U postgres -d <DB> -v ON_ERROR_STOP=1 -f data/dining/_build/load_200.sql
```

장소와 레코드의 식별자를 관광공사 `contentid` 에서 만들기 때문에 같은 파일을 다시 돌려도 결과가 같다.

건수 확인.

```sql
SELECT (SELECT count(*) FROM dining.dn_place)          AS place,
       (SELECT count(*) FROM dining.dn_hours_rule)     AS rule,
       (SELECT count(*) FROM dining.dn_hours_interval) AS interval,
       (SELECT count(*) FROM dining.dn_closure_rule)   AS closure;
```

200 / 1265 / 1661 / 124 가 나오면 정상이다.

### 4. 매칭 (코어 DB 에서만)

```sql
-- 먼저 시험 실행. 아무것도 쓰지 않고 결과만 보여준다.
SELECT * FROM dining.link_core_places('<tenant_id>');

-- 결과가 맞으면 실제로 잇는다.
SELECT * FROM dining.link_core_places('<tenant_id>', 0.75, 'matcher', false);

-- 못 이은 것과 사유
SELECT reason, count(*) FROM dining.v_link_gap GROUP BY reason;
```

후보가 둘 이상인 장소는 잇지 않고 `ambiguous` 로 남긴다. 잘못 이으면 다른 식당의
영업시간으로 판정하게 되므로 안 잇는 쪽을 택한다.

---

### 5. 공휴일 달력

```
python scripts/dining/make_holiday_sql.py
psql ... -f data/dining/_build/holidays.sql
```

`data/dining/holidays_2026_2027.json` 을 읽어 `_build/holidays.sql` 을 만든다.
46일이 들어가고 그중 13일이 명절로 잡힌다.

확인.

```sql
SELECT count(*) AS total, count(*) FILTER (WHERE is_major) AS major
FROM dining.v_holiday;
```

46 과 13 이 나오면 정상이다.

이 단계는 4번 매칭과 상관이 없다. 코어 DB 가 아니어도 돌릴 수 있고,
달력이 비어 있으면 그날이 평일로 판정되므로 적재 직후에 해두는 편이 낫다.


## 판정 쓰는 법

코어 일정 항목의 시각을 넣으면 그 자리에서 답이 나온다.

```sql
SELECT * FROM dining.core_place_state(
    '<tenant_id>', '<코어 places.place_id>',
    timestamptz '2026-09-21 12:00+09',
    timestamptz '2026-09-21 13:00+09');
```

| 돌려주는 값 | 뜻 |
|---|---|
| open_at_slot | 그 시각에 여는가. NULL 은 모름이다 |
| needs_check | 종료가 임박해 마지막 주문을 확인해야 하는가 |
| needs_holiday_check | 명절이나 공휴일인데 그 장소의 규칙을 모르는가 |
| holiday_context | 무슨 날인지와 확인할 곳. 경고가 아니면 NULL |
| attributes | 코어 형식으로 바꾼 영업시간 |
| hours_confirmed_at | 공급자 자료를 받은 시각. 현장 확인 시각이 아니다 |

장소 하나만 보려면 `dining.open_at_slot(place_uid, 시작, 끝)` 을 쓴다.

### 판정 규칙

| ID | 내용 |
|---|---|
| P-01 | 브레이크 시작과 식사 종료가 같으면 통과시킨다 |
| P-02 | 라스트오더 값이 없으면 판정에서 뺀다. 대신 종료 60분 이내면 경고한다 |
| P-08 | 현장 확인은 관찰 시각부터 그날 영업 구간 종료까지 유효하다 |

라스트오더의 60분은 실측에서 나왔다. 값을 표기한 77곳에서 영업 종료와 라스트오더의 간격을
재보니 중앙값이 50분이었고 60분이 85.7% 를 덮었다.

추정값으로 경고는 하되 일정을 바꾸지 않는다. 근거가 약하면 위반이 아니라 확인 요청이 된다.

### 명절과 공휴일

관광공사 자료에 명절 영업시간이 없다. 표본 200곳 중 명절 규칙이 있는 곳은 22곳이고
그것도 쉬는지 여부뿐이며, 몇 시까지 하는지 적힌 곳은 없었다.

그러므로 평소 규칙을 명절에 적용하는 것은 추정이다. 판정은 그대로 두고 확인하라는 표시만 얹는다.
판정을 모름으로 내리면 대안 식당까지 전부 모름이 되어 고를 것이 없어진다.

달력은 한국천문연구원 특일 정보이며 이동 쪽이 받아둔 것을 그대로 쓴다. 관보 고시 기준이고
대체공휴일까지 들어 있다. 값을 SQL 에 박지 않고 파일에서 읽으므로 해마다 파일만 갈면 된다.

명절 판정은 명칭으로 한다. 설날과 추석만 앞뒤 날까지 영업에 영향을 주기 때문이고,
대체공휴일(설날)처럼 괄호가 붙은 것도 같은 연휴이므로 포함한다.
노동절은 관공서는 쉬지만 식당은 대체로 열어서 적재는 하되 표시를 달아두었다.
판단을 바꾸려면 make_holiday_sql.py 위쪽의 목록을 고친다.

이 표시는 알림이 아니라 표시다. 공휴일에는 경고 대상이 많아 푸시로 보내면 식당 수만큼 울린다.
일정 카드 옆에 붙는 문구로 둔다. 알림 임계와 억제 규칙은 이것과 별개로 돈다.

확인 수단은 전화번호와 지도 링크다. 표본에서 전화번호는 99% 가 채워져 있었다.
지도 링크는 저장하지 않고 상호명과 주소로 그때그때 만든다. 우리가 만든 검색 주소이지
공급자가 준 데이터가 아니므로 약관을 따질 일이 없다. 다만 특정 가게가 아니라 검색 결과로 가므로
화면에도 그렇게 적는다.

---

## 현장 확인 (제휴 전제 시험 구현)

일정이 틀어져 대체 후보를 고를 때, 그 한 곳만 실제로 확인해 보는 길이다.
200곳을 순회하지 않는다. 필요한 순간에 필요한 곳만 본다. `026` 이 그 자리다.

```
일정 틀어짐  →  DB 로 후보 추림 (공짜)  →  상위 몇 곳만 조회  →  알림
                                          ↑ 여기
```

DB 가 맡는 것은 셋뿐이다. 조회 자체는 밖에서 한다.

| 함수 | 하는 일 |
|---|---|
| `check_prompt()` | 무엇을 물어야 하는지 문장으로 만든다. 물을 것이 없으면 NULL |
| `record_live_check()` | 돌아온 답을 적는다. 실패해도 성공한다 |
| `live_state()` | 아직 믿을 수 있는 답만 읽는다 |

조회 수단을 DB 가 모르게 둔 것은 나중에 공식 API 로 갈아끼울 때 바깥만 바꾸려는 것이다.

**조회는 더해주는 것이지 없으면 못 도는 것이 아니다.** 상한은 8초이고, 넘거나 막히면
`outcome` 을 실패로 적고 값은 모름으로 둔다. 판정은 원래 하던 대로 DB 값으로 내린다.
실패를 값으로 바꾸지 않으려고 표에 제약을 걸어두었다.

```sql
CHECK (outcome = 'ok' OR value_state = 'unknown')
```

유효기간은 주제마다 다르다. 영업시간과 휴무는 하루, 빈자리와 웨이팅은 5분,
실패는 2분이다. 기한이 지나면 `live_state()` 가 NULL 을 돌려주고 다시 묻게 된다.

출처는 둘로 나눠 등록했다.

| 출처 | 운영 판정 | 왜 |
|---|---|---|
| `auto_map_check` | **쓴다** | 사람이 지도를 열어 보던 일을 기계가 대신한 것. 등급은 `operator_check` 아래 |
| `catchtable_trial` | **쓰지 않는다** | 공식 접근 경로가 막혀 있다. 제휴 전에는 판정 근거가 아니다 |

`catchtable_trial` 의 답도 표에는 남지만 `v_live_check_fresh` 에서 빠지므로 판정에 닿지 않는다.
검수 안 된 LLM 추출을 다루는 방식과 같다. 시연에서 보이더라도 화면과 발표에
**제휴 전제 시험 구현**이라고 적는다.

돌리는 것은 `run_check.py` 다. 백엔드를 갈아끼워 조회 수단을 바꾼다.

```bash
set DINING_DSN=postgresql://postgres@localhost:5433/dining_dev

python scripts/dining/run_check.py ask  --place 대돈집 --at "2026-09-25 12:00"
python scripts/dining/run_check.py run  --place 대돈집 --at "2026-09-25 12:00" --backend manual
python scripts/dining/run_check.py show --place 대돈집
```

| 백엔드 | 무엇 |
|---|---|
| `stub` | 정해둔 답. 파이프라인이 도는지 볼 때 |
| `manual` | 사람이 열어 보고 적는다. 네이버 대조 작업을 옮긴 것 |
| `catchtable` | 비어 있다. 브라우저를 몰아야 해서 스크립트에 담기지 않는다 |

캐치테이블은 `ask` 로 물음을 뽑아 사람이 브라우저로 확인하고 `run --backend manual`
로 적는다. 로그인은 사람이 하고 예약 버튼은 누르지 않는다.

---

## 원장 확인기

판정이 왜 그렇게 나왔는지 SQL 없이 따라가는 화면이다. 원문 한 줄이 어떤 규칙이
되었고 그 규칙이 어떤 답을 내는지 한 자리에서 본다.

```bash
python scripts/dining/dev_up.py
```

DB 가 떠 있는지 보고 안 떠 있으면 켜고, 원장이 준비됐는지 보고, 확인기를 띄운 뒤
브라우저를 연다. 어느 폴더에서 실행해도 되므로 파이참에서 파일만 눌러도 된다.
`--check` 를 주면 띄우지 않고 준비 상태만 본다.

손으로 띄우려면 `final_project_cs` 에서 이렇게 한다.

```bash
set DINING_DSN=postgresql://postgres@localhost:5433/dining_dev
python -m uvicorn scripts.dining.inspect_app:app --port 8011 --reload
```

둘 다 `http://127.0.0.1:8011` 로 연다.

보이는 것은 그 시각 판정과 근거, 이번 주 요일별 영업시간, 원문, 여행 조건별 결과,
현장 확인 물음과 기록이다. 영업 규칙과 휴무 규칙은 여기서 고치지 않는다.
그것은 적재기의 일이다. 쓰기는 현장 확인 기록 한 가지뿐이며 그것도 관측이지 규칙이 아니다.

목록의 대부분이 `record_status = unknown` 인데 인허가 자료를 아직 붙이지 않아서이며
오늘 영업 여부와 무관하다. 화면에서는 폐업만 따로 보인다.

---

## 품질을 재는 법

고쳤는데 좋아졌는지 말할 수 없으면 고친 것이 아니다.

**실행 로그만으로는 알 수 없다.** 입력이 매번 달라서 어제 8% 오늘 6% 가
고쳐서인지 쉬운 자료가 들어와서인지 구분되지 않는다. 같은 입력에 버전만
바꿔 돌려야 차이가 개선이 된다. 그래서 고정된 정답셋이 있어야 한다.

### 지표 둘을 섞지 않는다

| 지표 | 묻는 것 | 우리가 고칠 수 있나 | 어디서 재나 |
|---|---|---|---|
| **원장 정확도** | 지금 원장이 실제 가게와 맞는가 | 예. 확인해서 넣으면 된다 | `run_quality.py` |
| **파서 정확도** | 원문을 제대로 읽었는가 | 예. 파서를 고치면 된다 | 회귀 시험 34개 |

섞으면 관광공사가 틀린 것이 우리 오류율로 들어온다. 원장 정확도가 올라가도
파서는 그대로다. 사람이 확인한 값을 넣어 올린 것을 파서가 좋아졌다고 말하면 안 된다.

### 세 표로 나눈다

```
dn_truth           정답. 고정이며 사람이 확인한 것만 들어온다
dn_quality_run     실행 한 번. 버전이 붙는다
dn_quality_result  그 실행의 건별 결과
```

### 모름을 틀림으로 세지 않는다

정확도의 분모는 판정이 난 건수다. 판정이 나지 않은 것을 틀림으로 세면
정답을 늘릴수록 점수가 떨어지는 이상한 일이 생긴다. 버전을 비교할 때도
`모름 → 모름` 을 따로 센다.

### 총량이 아니라 깨진 것을 본다

셋을 고치고 하나가 깨져도 총량은 둘 늘어서, 숫자만 보면 깨진 것이 보이지 않는다.
`--delta` 는 깨진 것을 맨 위에 놓는다.

### 버전은 파서 내용에서 만든다

손으로 적어 두면 안 바뀐다. 파서를 일곱 번 고치는 동안 `v1` 그대로였고,
그래서 어제 결과와 오늘 결과를 구분할 방법이 없었다. 지금은
`parse_hours.py` 의 해시를 쓰므로 내용이 바뀌면 값이 바뀐다.

다만 **파서가 그대로인데 원장만 달라지는 일**이 있다. 사람이 확인한 값을
넣는 경우가 그렇다. 그때는 버전이 같으므로 실행끼리 비교해야 한다.
`--delta` 를 인자 없이 부르면 최근 두 실행을 본다.

### 돌리는 순서

```bash
python scripts/dining/make_truth_sql.py            # 검수 결과를 정답셋으로
psql ... -f data/dining/_build/truth.sql

python scripts/dining/run_quality.py               # 채점하고 기록

python scripts/dining/make_operator_sql.py --dry   # 무엇이 바뀌는지 먼저 본다
python scripts/dining/make_operator_sql.py
psql ... -f data/dining/_build/operator.sql

python scripts/dining/run_quality.py               # 다시 채점
python scripts/dining/run_quality.py --delta       # 무엇이 고쳐지고 깨졌나
python scripts/dining/report_quality.py --save     # 문서로
```

`--dry` 를 먼저 보는 것이 중요하다. 검수자가 적은 칸만 고치고 적지 않은 칸은
관광공사 값을 그대로 두는데, 그 경계가 맞는지는 눈으로 확인해야 한다.

### 관광공사 규칙을 지우지 않는다

사람이 확인한 값을 넣을 때 같은 요일의 관광공사 규칙은 `retired_at` 으로
물러나게 한다. 지우면 무엇이 어떻게 틀렸는지가 사라진다.

물러나게 하지 않으면 안 된다. `day_intervals` 는 출처를 가리지 않고 살아 있는
규칙을 모두 돌려주므로, 그냥 두면 구간이 두 겹으로 겹쳐 판정이 엉킨다.

### 정답셋의 전제

지금 정답셋은 2026-09-21 에 사람이 100곳을 네이버 지도로 대조한 결과다.
**표시가 없는 행은 「안 봤음」이 아니라 「보았고 같았음」이다.** 전수 확인이었기
때문이며, 그 사실을 `dn_truth.evidence` 에 적어 두었다. 이 전제가 바뀌면
숫자가 통째로 달라지므로 다음 사람이 확인할 수 있어야 한다.

원본은 `data/dining/truth/` 에 있다. 저장소 밖에만 두면 다음에 잃어버린다.

---

## 코어와의 경계

코어 표에 외래키를 걸지 않는다. 접점은 `dn_core_place_link` 한 표의 논리 참조뿐이다.
코어 스키마가 바뀌어도 이쪽 표가 깨지지 않게 하려는 것이다.

| 무엇 | 지금 |
|---|---|
| 코어 표 읽기 | 한다 |
| 코어 표 쓰기 | **하지 않는다** |

`open_at_slot` 을 우리가 채워도 되는지 코어에 답을 받지 못했다. 그 전까지는 값을 계산해
보여주기만 하고 쓰지 않는다.

쓰게 될 때 `places.attributes` 는 통째로 대입하면 안 된다. 액티비티가 같은 칸에
`indoor` 같은 값을 넣기 때문에 덮어쓰면 상대 값이 사라진다.

```sql
UPDATE places SET attributes = attributes || '{"hours": [...]}'::jsonb WHERE ...;
```

---

## 시간을 다루는 방식

시각은 자정부터의 분 단위 정수다. 자정을 넘기면 1440 을 넘는 수가 된다.
저녁 6시부터 새벽 2시까지가 1080 에서 1560 까지 하나의 구간이 된다.
시각 타입을 쓰면 18시가 2시보다 커서 비교가 성립하지 않는다.

브레이크타임은 별도 칸이 아니다. 연속한 두 구간 사이의 빈 시간으로 표현한다.
11시부터 15시, 17시부터 21시 두 구간을 넣으면 그 사이가 자동으로 브레이크가 된다.

새벽 시각을 물으면 전날 규칙부터 본다. 새벽 한 시의 방문은 그날 규칙이 아니라
전날 영업의 연장이기 때문이다.

---

## 모른다는 값

없음과 모름을 구분한다. 결측이나 조회 실패를 영업이나 휴무로 바꾸지 않는다.

| 상황 | 값 |
|---|---|
| 영업 구간을 모름 | open_at_slot 이 NULL |
| 브레이크 언급이 없음 | break_state 가 unknown |
| 라스트오더 표기가 없음 | last_order_state 가 unknown |

코어도 같은 원칙이다. `open_during()` 이 영업시간을 모르면 None 을 돌려주고 연다로 읽지 않는다.

---

## 지금의 한계

| 항목 | 내용 |
|---|---|
| 공휴일 달력 | 2026 년과 2027 년만 있다. 2028 년이 되면 오류 없이 그날이 평일로 판정된다 |
| 달력 갱신 담당 | 정해지지 않았다. 해마다 채워야 하며 안 채우면 조용히 틀린다 |
| 제헌절과 노동절 | 달력에 들어 있다. 어느 오퍼레이션으로 받았는지 이동 쪽에 확인이 필요하다 |
| 네이버 지도 링크 | 검색 주소다. 특정 가게를 가리키는 링크는 사람이 확인해야 한다 |
| 자정 넘는 영업 | 코어 형식으로 내보낼 수 없어 빈 값을 준다. 판정 함수는 정확하다 |
| 1인 가격 | 원장에 없다. 코어가 후보를 고를 때 쓴다 |
| 오추출률 | 측정하지 않았다. 위의 비율은 모두 뽑았는지를 센 것이지 맞게 뽑았는지가 아니다 |
| 이름 유사도 기준 | 0.75 는 파이썬으로 잰 값이다. 여기서는 편집거리로 재므로 계산 방식이 다르다 |

오추출률은 `scripts/dining/make_audit_sheet.py` 로 대조표를 만들어 사람이 확인한다.
파서를 고친 뒤에 재야 의미가 있다.

---

## 저장소에 넣으면 안 되는 것

`.env` 에 관광공사 서비스 키가 들어 있다. 반드시 `.gitignore` 에 넣는다.

```
.env
parsed_hours.json
load_200.sql
holidays.sql
오추출_대조표_*.csv
오추출_대조표_*.html
```

수집 스크립트는 키를 코드에 넣지 않고 `.env` 에서 읽는다. 생성물도 넣지 않는다.
원본 데이터와 스크립트가 있으면 언제든 다시 만들 수 있다.
