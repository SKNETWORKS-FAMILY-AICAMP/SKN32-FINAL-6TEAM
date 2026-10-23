# DB 적재 정리 (개인용)

CSV를 고쳐도 서비스에 안 보이는 이유와, DB가 어디 있는지·언제 다시 적재해야 하는지 정리한 메모.

## 한 줄 요약

**서비스는 CSV를 읽지 않는다. DB만 읽는다.** CSV는 DB에 올리기 전의 원본일 뿐이라, CSV를 바꾸면 적재 스크립트를 다시 돌려야 반영된다.

```
CSV  ──(load_places.py)──▶  DB(activity.ac_place …)  ──▶  서버가 읽어 서비스
```

## DB는 어디 있나

| 항목 | 내용 |
|---|---|
| 실체 | 프로젝트 루트 `pgdata/` — PostgreSQL 데이터 폴더. 안의 파일은 엔진 전용 바이너리라 눈으로 못 읽는다 |
| 접속 주소 | `.env` 의 `ACOP_DATABASE_URL` (예: `postgresql+psycopg://postgres@127.0.0.1:5433/acop_cs`) |
| 보는 법 | DBeaver 또는 docker psql 로 위 주소에 접속 → `activity` 스키마 아래 표 |
| 주의 | `pgdata/` 는 git 에 올리지 않는다(지금 `??` 로 떠 있음) |

DB는 **각자 컴퓨터에 따로** 있다. 푸시해도 DB 내용은 안 넘어간다.

## 활동 팀 표 (스키마 `activity`)

| 표 | 역할 | 만든 마이그레이션 | 채우는 법 |
|---|---|---|---|
| `activity.ac_place` | 활동 장소 원장(운영시간·휴무 원문 등) | 300 | `load_places.py` (CSV → DB) |
| `activity.ac_indoor` | 실내·야외 판정 저장 | 301 | `decide_indoor.py` · `fill_indoor_outdoor.py` |
| `activity.ac_load_meta` | 적재 기록(언제 몇 행) | 300 | 적재 때 같이 기록됨 |
| `activity.ac_live_status` | 웹으로 확인한 임시휴무·폐업 | 304 | `check_live_status.py` (배치) |

- 이름이 `acop_…` 가 아니라 **`ac_…`** 다(`load` meta 는 `ac_load_meta`).
- `place_catalog` 에서 쪼갠 것이 아니다. `place_catalog`(마이그레이션 011)는 코어의 장소 표로 따로 있고, 장소 이름 조회에 쓴다. `ac_*` 는 활동 전용 표.

## 팀원이 풀 받은 뒤 해야 할 일

1. `git pull`
2. 마이그레이션(표 구조 생성·갱신) — 코드는 `app/infrastructure/db/migrate.py`, 재실행해도 안전
3. `python scripts/activity/load_places.py --dry-run` 으로 행 수 확인
4. `python scripts/activity/load_places.py` 로 적재
5. 필요하면 `read_hours.py` → `decide_indoor.py` 순서로 파생 값 채움

## 언제 다시 적재하나

| 상황 | 해야 할 것 |
|---|---|
| CSV 를 바꿨다 | `load_places.py` 다시 (같은 CSV 를 또 돌려도 결과 같음) |
| 마이그레이션 파일이 새로 생겼다(pull 후) | 마이그레이션 다시 |
| 운영시간 원문이 바뀌었다 | `read_hours.py` 로 요일표 다시 펴기 |
| 장소가 새로 들어왔다 | `decide_indoor.py` 로 실내외 채우기 |

## 자동인가 수동인가

**기본은 전부 수동**이다. 정기 실행으로 등록된 활동 스크립트는 아직 없다.
예외로 웹 확인 배치(`check_live_status.py`)만 코어의 03:00~08:00 정기 점검에 등록하기로 협의 중(코어 몫).

## 헷갈릴 때 점검

- 화면에 옛 값이 나온다 → CSV 가 아니라 **DB 적재가 구버전**인지 먼저 본다.
- 내 DB 와 팀원 DB 값이 다르다 → 각자 적재 시점이 다른 것. 같은 CSV 로 다시 적재하면 같아진다.
