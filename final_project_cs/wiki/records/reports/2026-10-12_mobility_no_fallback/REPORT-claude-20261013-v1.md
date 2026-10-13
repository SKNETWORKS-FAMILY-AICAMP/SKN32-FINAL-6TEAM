# 서울시 도보 네트워크로 만든 보행 그래프 — 카카오 웹 대조 (Claude, 2026-10-13 새벽)

[앞 보고서](REPORT-claude-20261012-v1.md)의 남은 일 1번(보행 자료 원천)을 이어서 했습니다. 제품 코드(`app/`)는 바꾸지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 서울시 도보 네트워크 전체 받기 | 끝 | 491,082행 = 100% · API 493회 |
| 보행 그래프로 변환 | 끝 | 간선 275,353 · 버린 링크 3,663(1.3%) |
| 같은 4쌍 카카오 대조 ±10% 안 | 개선 | 2/4 = 50% (OSM 그래프는 1/4 = 25%) |
| 제품 연결 | 안 함 — 표본 확대 뒤 판단 | 0/1 |

## 결과(같은 출발·도착 좌표 · 카카오 최단 기준)

| ID | 카카오 | OSM 그래프(v2) | 서울시 도보 그래프 | 비고 |
|---|---|---|---|---|
| W01 | 672 m | 742.65 m (+10.51%) | 775.08 m (+15.34%) | 출발이 서울광장 안 — 54.2 m 떨어진 길에 붙음(낙관 표시) |
| W02 | 432 m | 592.23 m (+37.09%) | 478.38 m (+10.74%) | 카카오와 거의 같은 길. 출발 쪽 한 블록만 돌아감 |
| W03 | 516 m | 590.19 m (+14.38%) | 503.53 m (−2.42%) | 도착 접근 38.9 m(탑골공원 안 · 낙관 표시) |
| W04 | 580 m | 628.22 m (+8.31%) | 550.15 m (−5.15%) | 카카오는 역사 안 출발 — 조건 다름 |

- 분석: [walk-web-analysis-seoulwalk.json](claude-walk-web-v1/walk-web-analysis-seoulwalk.json) · 그림 [kakao-vs-product-seoulwalk.png](claude-walk-web-v1/kakao-vs-product-seoulwalk.png) · 같은 형식의 OSM 그림 [kakao-vs-product-v2graph-fixed.png](claude-walk-web-v1/kakao-vs-product-v2graph-fixed.png)(출처 문구를 고쳐 다시 그림).
- W01·W03 은 접근 거리 30 m 초과(낙관 표시)라 지금 제품 규칙이면 직접 도보 후보에서 빠집니다. 거리 비교에는 넣었지만 「제공 가능한 안내」로 세면 안 됩니다.
- 원자료·변환 기록: [datasets/mobility/raw/seoul_walk_network_20261012_v1/REPORT.md](../../../../../datasets/mobility/raw/seoul_walk_network_20261012_v1/REPORT.md).

## 판단과 다음 일

- 4쌍 중 3쌍이 좋아졌지만 표본이 작고, W01 은 나빠졌습니다. 4쌍 중 W01 은 개발에 이미 쓴 좌표라 독립 표본이 아닙니다. 그래서 바로 제품에 연결하지 않습니다.
- 다음: 제품 결과를 보기 전에 서울 안 새 좌표 쌍을 고정합니다. 그다음 카카오 웹으로 관측하고, OSM 그래프와 서울시 도보 그래프를 같은 표로 비교합니다. 그 결과로 제품 걸음 경로에 쓸지 정합니다.
- 제품에 연결하려면 라우터가 걸음만 다른 그래프를 읽도록 바꿔야 합니다. 자동차·자전거는 지금처럼 OSM 그래프를 씁니다.

| 파일 | SHA-256 |
|---|---|
| datasets/mobility/scripts/fetch_seoul_walk_network_v1.py | bcdf63daac35fd4f65c369b6a2966f856212bdd86a496d7224299b31d523fb9f |
| datasets/mobility/scripts/build_seoul_walk_graph_v1.py | 220e495e08a10dc2cc804941f81228a097bc4dce0c3f3339e8b4a820b0180eee |
| walk_graph_seoul_v1/edges.jsonl.gz | md5 be2084cf995de1655b303c89a32ace81 |

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음.
