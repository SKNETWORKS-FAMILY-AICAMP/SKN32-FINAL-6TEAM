# 이동 모듈 평가 지표

자동 생성 — `scripts/mobility_metrics.py` · 케이스 85건

## 1. 근거 보존율 — 코어에 남는가

| | 단위 | 보존율 |
|---|---|---|
| 판정이 만든 정보 단위 | 738 | — |
| **접기 전** — `evidence`(소스 근거)만 남는다 | 247 | **33.5%** |
| **접기 후** — 판정 상세를 `Evidence.value` 로 올린다 | 738 | **100.0%** |

버려지던 것 **491단위** — 판정·등급·사유·완화조건·도착시각·경고·대안·구간판정.

## 2. 근거 충실도

- 판정 1건당 소스 근거 **2.91건**
- 근거 등급 분포 — 확정 145건(58.7%) · 추정 101건(40.9%) · 근거없음 1건(0.4%)
- 판정 등급 분포 — 확정 27건(31.8%) · 추정 55건(64.7%) · 근거없음 3건(3.5%)

## 3. 판정 분포

성립 52건 · 불가 29건 · 탈락 2건 · 근거없음 2건

- **모르는 것을 모른다고 낸 비율 2.4%** — 다른 팀이 낼 수 없는 축이다.
  단순 LLM 호출은 이 값을 0 으로 만든다(모른다고 하지 않는다).

## 4. 경고 코드별 발생

| 코드 | 건수 |
|---|---|
| `MOB_W_SPEED_NO_PEAK` | 19 |
| `MOB_W_ORIGIN_TERMINAL_DEST` | 6 |
| `MOB_W_SINJEONG_SAT` | 6 |
| `MOB_W_BUS_SPEED_PROXY_AIRPORT` | 5 |
| `MOB_W_AIRPORT_FARE` | 5 |
| `MOB_W_BUS_SPEED_PROXY_NIGHT` | 3 |
| `MOB_W_BUS_NO_DAYTYPE` | 2 |
| `MOB_W_BUS_DETOUR` | 1 |
| `MOB_W_BUS_ROUTE_NOT_COLLECTED` | 1 |
| `MOB_W_BUS_SPEED_BLOCKED_ROUTE` | 1 |
| `MOB_W_STATION_NOT_IN_TIMETABLE` | 1 |

## 세는 방법

- **정보 단위** = 판정 1 + 근거등급 1 + 사유 + 완화조건 + 도착시각 + 여유분 + 경고 n + 대안 n + 구간판정 n + 소스근거 n
- **접기 전 보존율** = 소스근거 ÷ 정보 단위. 코어가 `evidence` 만 저장하고 `decisions` 를 버리기 때문이다
- 이 파일은 회귀를 돌려 만든다. **숫자마다 재현 명령이 있다** — `python scripts/mobility_metrics.py`
