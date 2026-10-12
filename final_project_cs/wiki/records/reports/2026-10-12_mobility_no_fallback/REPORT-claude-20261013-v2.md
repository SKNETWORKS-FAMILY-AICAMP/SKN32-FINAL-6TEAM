# 서울 안 걸음에 서울시 도보 자료 연결 · 계단 표시 · x600 서버에 자료 올림 (Claude, 2026-10-13 새벽)

[앞 보고서](REPORT-claude-20261013-v1.md)에 이어, 사용자 지시(「서울에 한해서 쓰고, 제품에 연결할 수준으로 만들어 서버에 데이터셋을 넣고, 계단 정보도 반영」)를 진행했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계단 표시(OSM 계단과 같은 자리·같은 방향 겹침) | 끝 | 서울시 간선 1,186개 · 18.8 km |
| 제품 연결(로컬 작업 폴더) | 끝 · 규칙 개정 | 1/1 |
| 독립 표본 확대(제품 계산 전 고정) | 관측 끝 | 12/12 쌍 |
| 제품 경로 ±10% 안(고정 15쌍) | 측정 | 10/15 = 67% (제공 15/15) |
| 이동 모듈 시험 전체 | 통과(정답 파일 건 4개 제외) | 1,532/1,536 = 99.7% |
| x600 서버에 자료 올림 | 끝 · 해시 5/5 일치 | 1/1 |
| x600 서버 코드 배포 | 안 함 | 0/1 |

## 1. 계단 표시

- 도구: [annotate_seoul_walk_steps_v1.py](../../../../../datasets/mobility/scripts/annotate_seoul_walk_steps_v1.py) → `processed/mobility/walk_graph_seoul_v2/`(v1 은 그대로).
- 규칙: OSM `highway=steps` 선에서 4 m 안 · 방향 차 35° 안 · 2 m 이상 겹치는 서울시 간선 부분만 잘라 계단으로 표시합니다. 추정 계수와 「육교면 계단」 같은 가정은 쓰지 않습니다. 겹친 OSM way id 는 간선마다 `st_src` 에 남깁니다.
- 결과: OSM 계단 909개(way)와 맞춰 서울시 간선 1,186개(18.8 km)를 계단으로 표시했습니다. 이 그래프의 계단 간선은 라우터가 계단 비용·속도로 셉니다(합성 시험으로 확인).
- 확인한 범위: 서울 안 OSM 계단 4,331개 중 21.5%가 맞춰졌습니다. 놓친 3,401개 중 2,680개는 서울시 자료에서 8 m 넘게 떨어져 길이 없는 곳(공원·단지 안·역사 안)이라 붙일 수 없습니다. 4~8 m 의 496개는 나란한 보도일 수도 있어 넣지 않았습니다(보수적 판정). 확인용 계단 3곳(광통교 진출입 계단 2 · 익선동 1)은 모두 맞춰졌습니다.

## 2. 규칙 개정 — 「서울시 자료만」은 독립 표본에서 나빴다

제품 계산 전에 서울 곳곳 12쌍을 고정하고([od-frozen-v1.json](../../../../../datasets/mobility/raw/mobility_walk_web_20261013_v4/od-frozen-v1.json)) 카카오 웹으로 관측했습니다([kakao-walk-observed-v1.json](../../../../../datasets/mobility/raw/mobility_walk_web_20261013_v4/kakao-walk-observed-v1.json) · API 0회).

| 규칙(고정 15쌍 = W02~W04 + S01~S12) | 제공 | ±10% 안 | 오차 절댓값 중앙값(제공분) |
|---|---|---|---|
| OSM 보행망만 | 14/15 | 10/15 | 7.4% |
| 서울시 도보 자료만 | 11/15 | 5/15 | 10.7% |
| **두 자료 중 검증된 짧은 길** | **15/15** | **10/15** | **5.1%** |

- 처음 4쌍(W01~W04)에서 서울시 자료가 좋아 보였던 것은, 그 자리들이 OSM 빈틈 때문에 고른 곳이었기 때문입니다(표본 치우침). 서울시 자료는 남산·명동성당·석촌호수·홍대처럼 보도가 따로 그려지지 않은 길이나 공원 길이 빠진 곳이 많습니다. 예: 남산타워→명동 근처는 카카오 1,744 m · OSM 1,830 m · 서울시 2,249 m 였습니다.
- 그래서 서울 안 걸음은 두 자료로 모두 찾고, 접근이 검증된 경로 중 짧은 것을 고르게 바꿨습니다. 고른 자료와 두 후보(거리 · 접근 미검증 여부 · 실패 이유)는 도보 근거에 남깁니다. 둘 다 실패하면 거리를 만들지 않습니다.
- 서울시 자료만 쓰던 판은 [백업](../../../../_backup/2026-10-13_seoul_walk_router/)에 있습니다(`walk_router_seoul_only_v1.py`).
- 그림: [compare-rules-v1.png](claude-walk-web-v1/compare-rules-v1.png) · 표: [compare-rules-v1.json](claude-walk-web-v1/compare-rules-v1.json).
- 한계: 15쌍은 작은 표본입니다. 새 규칙이 OSM 단독보다 ±10% 안 개수를 늘리지는 않았습니다(10 대 10). 나아진 것은 제공 수(15 대 14)와 오차 중앙값입니다. 두 길 중 짧은 쪽을 고르므로 과소 추정 쪽으로 치우칠 수 있습니다(S08 −12.1% · S11 −13.5%).

## 3. 제품 연결(로컬 작업 폴더 · 커밋 안 함)

| 파일 | 바꾼 것 |
|---|---|
| `engine/walk_router.py`(새 파일) | 서울 경계 판정 · 두 자료 경로 선택 · 근거 기록 |
| `engine/runtime.py` | 서울시 그래프 폴더가 있으면 걸음 라우터를 감싼다. 택시는 기존 라우터 그대로 |
| `engine/bike.py` | 경로마다의 `source_id` · `basis` · `walk_candidates` 를 응답에 옮긴다 |
| `engine/graph_router.py` | `shared()` 추가 · 서울시 그래프 자료 식별자(`seoul_walk_network@2026-10-12+osm_steps@2026-10-03`) |
| `engine/plan.py` | 도보 근거에 `source_id` · `walk_candidates` 두 줄 추가 |
| `tests/unit/travel/mobility/test_seoul_walk_router_v1.py`(새 파일) | 12개 시험 |

- 백업: [final_project_cs/_backup/2026-10-13_seoul_walk_router/](../../../../_backup/2026-10-13_seoul_walk_router/)(plan.py 는 다른 세션 수정이 들어간 판 52097f61… 을 백업).
- 제품 경로 확인(build_verifier → Planner): [product-walk-check-minrule.json](claude-walk-web-v1/product-walk-check-minrule.json). 서울시 자료를 고른 쌍 6 · OSM 을 고른 쌍 9 입니다. W01 은 두 자료 모두 접근 미검증이라 막힙니다(서울광장 안 좌표).
- 시험: 이동 모듈 전체 1,532 통과 · 4 실패([after-minrule-full.xml](claude-walk-web-v1/after-minrule-full.xml)). 실패 4건은 `test_plan_v1` 예시 일정 정답 파일 건입니다. 원인은 다른 세션 인계(CLAUDE-HANDOFF-20261013-from-45290d-v1.md §3)에서 확인됐고, 정답 파일 새 판은 사용자 답을 기다리고 있습니다. 서울시 자료만 쓰던 판에서 새로 깨졌던 2건(남산타워)은 새 규칙에서 통과합니다.

| 파일 | SHA-256 |
|---|---|
| engine/walk_router.py | c947a4bed7d3d732cc3e9c4765b68a6bf872e6ebd919a94582c4b26a566ce078 |
| engine/runtime.py | 1ac8278a6c6748803a6595e854e7d3dfe4560fbbef5b38301bd0c63462c75655 |
| engine/bike.py | 73e4326cdf19b2f9d60c2ea16668023a6ae399a80b1793a5f4aada083f823dee |
| engine/graph_router.py | 9ec465f6210ad14bda2123c19e7ef60e9beaafd13d1bc32430c3a5160196f89f |
| engine/plan.py | 2271ca84908f300c66ff1b59bd3c8e384976aca2374161cc592203dd68d78fc5 |
| tests/…/test_seoul_walk_router_v1.py | ec194cfb2bf44a3a626dad1f2ef6a3343026206e4864b1522a74652836003979 |
| datasets/…/annotate_seoul_walk_steps_v1.py | bbfd8e9459b4f98eb9faf6243b439db748597cd51cdb777f9c368865fc85fd43 |

## 4. x600 서버에 자료 올림

- 위치: x600 서버 `/root/tripilot-docker/datasets/mobility/processed/mobility/walk_graph_seoul_v2/`(새 폴더 · 기존 파일 덮지 않음). cs 프로젝트 서버 컨테이너에는 `/data/mobility/processed/mobility/walk_graph_seoul_v2` 로 읽기 전용으로 보입니다(api · worker 둘 다 확인).
- 압축 파일 해시(645fb069…)와 파일 5개 md5 가 이 PC 와 모두 같습니다.
- **cs 프로젝트 서버 코드는 아직 이 자료를 읽지 않습니다.** 위 코드 변경은 커밋·푸시·배포를 하지 않았습니다. 컨테이너를 다시 띄우지도 않았습니다. 확인할 때 컨테이너들이 2분 전에 다시 떠 있었는데, 이 작업과 무관한 자동 배포로 보입니다.
- 실서버 확인(서버 응답): cs 프로젝트 서버 HTTP 응답으로 새 걸음 경로를 확인하지 않았습니다(코드 배포 전).

mock 서버 시험(화면 반응): 안 했음.
