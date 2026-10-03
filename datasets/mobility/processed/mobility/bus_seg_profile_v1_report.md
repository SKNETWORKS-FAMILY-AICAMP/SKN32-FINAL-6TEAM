# bus_seg_profile_v1 — 41 산출 보고

```json
{
 "source_id": "seoul_OA-21217",
 "source_url": "https://data.seoul.go.kr/dataList/OA-21217/F/1/datasetView.do",
 "checked_at": "2026-09-24T23:25+09:00",
 "files": 9,
 "dates": [
  20260601,
  20260913
 ],
 "n_dates": 100,
 "missing_dates_in_span": [
  20260615,
  20260628,
  20260701,
  20260704,
  20260705
 ],
 "days_by_day_type": {
  "weekday": 70,
  "holiday": 30
 },
 "raw_rows": 8743191,
 "dup_date_rows": 566136,
 "repeat_pair_rows_kept": 70698,
 "repeat_pair_rows_dropped": 75386,
 "seq_mismatch_unique_pair": 57196,
 "nonfinite_cells": 0,
 "neg_cells": 0,
 "dup_sec_date_identical": 87,
 "dup_sec_date_conflict_dropped": 0,
 "our_sections": 41103,
 "sections_covered": 40776,
 "routes_total": 717,
 "routes_any": 713,
 "routes_chain_full_any_obs": 442,
 "routes_chain_excl_last_any_obs": 693,
 "coverage_meaning": "구간이 어느 요일형·시간이든 5일 미만 포함 한 번이라도 관측되면 covered — 요청 시간대 가용성 아님",
 "routes_none": [
  "8002",
  "TOUR02",
  "TOUR04",
  "TOUR12"
 ],
 "by_type": {
  "간선": [
   13048,
   13054
  ],
  "공항": [
   1927,
   1946
  ],
  "광역": [
   558,
   562
  ],
  "마을": [
   7083,
   7331
  ],
  "순환": [
   53,
   56
  ],
  "심야": [
   2127,
   2129
  ],
  "지선": [
   15952,
   15967
  ],
  "투어": [
   28,
   58
  ]
 },
 "night_route_cells_23_04_with_ge5_days": 0.775403162674182,
 "p90_over_p50_median": 1.1875,
 "cells_n_ge5": 1457091,
 "cells_n_1_4": 18130
}
```
