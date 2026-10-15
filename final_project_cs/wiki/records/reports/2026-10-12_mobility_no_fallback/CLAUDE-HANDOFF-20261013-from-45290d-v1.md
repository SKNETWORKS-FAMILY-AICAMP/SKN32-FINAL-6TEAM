# 인계 — 「이동 이어서」 세션(45290d) → 「이동경로 최적화」 세션, 2026-10-13

앞 인수인계 [CLAUDE-HANDOFF-20261012-v1.md](CLAUDE-HANDOFF-20261012-v1.md)를 이어받아 한 일과 남은 일입니다. 그 문서의 사용자 지시(하드코딩·폴백·정답 맞춤 금지, 수정 전 백업, 커밋·푸시·배포·외부 발송 금지, API 예산)는 그대로 유효합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 기준 소스·입력 해시 대조 | manifest 와 같음 | 13/13 = 100% |
| 첫 회귀(차량 목표 휴리스틱·직접 도보 무폴백) | 통과 | 5/5 = 100% |
| 새 카카오 웹 도보 관측(W02~W04) | 완료 | 3/3 = 100% |
| 제품 도보 거리 카카오 ±10% | W04 만 | 1/4 = 25% |
| 확장 실패 4건(test_plan_v1) | 원인 확인, 해결 안 함 | 0/4 = 0% |
| arrive_late 에서 뺀 후보 이유 소실 결함 | 수정 + 새 시험 | 1/1 = 100% |
| 택시 과소 예측 | 조사 보고서만 읽음 | 0/1 = 0% |

분모: 각각 대조 파일 수·시험 수·관측 OD 수. 21개 기능 전체 완료율은 산출하지 않았습니다.

## 1. 바꾼 코드(1곳)

- [plan.py:1682-1687](../../../../app/domains/travel_ops/instances/mobility/engine/plan.py) — `Planner.leg` 의 `arrive_late` 분기에 `late["left_out"] = self._fold_left(left)` 추가. 후보가 아예 없을 때(1660행)는 이미 싣던 칸입니다. 앞 판은 이 분기에서 버려, 「도보: walk_source_unavailable / unverified_walk_access」가 결과 어디에도 남지 않았습니다(수정 전 같은 입력 결과: skipped 에 left_out 없음, left_out 도 비어 있음).
- 백업: [final_project_cs/_backup/2026-10-12_221534_late_left_out/plan.py](../../../../_backup/2026-10-12_221534_late_left_out/plan.py) (수정 전 SHA-256 fe9542d3…, manifest 값과 같음). 수정 후 SHA-256 52097F61BB5C8C43844FF201AE57656145FB8E2FB8F13FB93CE6B4CF5C6B01FD. 2026-10-13 00:3x 에 다시 확인했을 때 백업과의 차이는 이 3줄뿐이었습니다.
- 새 시험: [test_late_left_out_v1.py](../../../../tests/unit/travel/mobility/test_late_left_out_v1.py) 1/1 통과(실데이터 축, 44초). 로그: `.tmp/mobility_claude_resume_20261012_201012/late-left-out-v1.log`.
- 이 수정 뒤 이동 시험 전체는 다시 돌리지 않았습니다(메모리·디스크 부족). 다음 세션이 돌려야 합니다.

## 2. 도보 거리 — 웹 대조 결과

관측: 카카오맵 공개 웹, 앱 안 브라우저, 2026-10-12 21:27~21:29 KST. 지도 개발자 API 호출 0회.
원자료: [datasets/mobility/raw/mobility_walk_web_20261012_v3_kakao/kakao-walk-observed-claude-v1.json](../../../../../datasets/mobility/raw/mobility_walk_web_20261012_v3_kakao/kakao-walk-observed-claude-v1.json). 같은 날 21:20 에 다른 실행이 [mobility_walk_web_20261012_v3/](../../../../../datasets/mobility/raw/mobility_walk_web_20261012_v3/)에 W01~W04 를 먼저 저장했습니다(덮지 않음).

- **카카오 총거리 정의 확인**: 경로 좌표 길이 + 요청점↔경로 시작·끝 직선. 4쌍 모두 1m 안에서 맞습니다. 제품도 붙임 직선을 더하므로 정의가 같습니다. 이전 「+10.51%」는 같은 정의끼리 비교한 값이 맞습니다.
- **좌표 변환**: 카카오 WCONGNAMUL ÷2.5 = TM(GRS80, lat0 38, lon0 127, x0 200000, y0 500000). 요청점 10개 최대 오차 0.23m. 흔히 쓰는 Bessel+towgs84 정의는 372m 어긋납니다.

| OD | 카카오 최단 | 제품 | 차이 | 제품 붙임(출발/도착) |
|---|---|---|---|---|
| W01 | 672m | 742.65m | +10.51% | 8.5 / 41.0m (낙관 표시) |
| W02 | 432m | 592.23m | +37.09% | 5.1 / 39.3m (낙관 표시) |
| W03 | 516m | 590.19m | +14.38% | 6.9 / 3.9m |
| W04 | 580m | 628.22m | +8.31% | 5.6 / 25.0m |

- 카카오 경로를 5m 간격으로 짚은 결과, 길 위 구간의 97~99%(W01~W03)가 제품 보행망 8m 안에 있습니다. W04 는 80%(서울숲역 역사 안 50m 포함). 즉 **길 자료가 없는 것이 아니라 짧은 연결이 빠져 크게 돌아갑니다.**
- 카카오 꼭짓점 사이를 제품 보행망으로 이어 본 끊김:
  - W01 광통교 남단: 카카오 5m·24m·11m → 제품 38.5·96.8·68.8m. OSM 에서 보행교(way 656122968)는 북단이 횡단보도 way 656122969(crossing 노드 11233115446)로 이어져 있습니다. 하지만 **남쪽 청계천로(way 73541403)를 건너는 횡단보도가 OSM 에 없습니다** → 자료 공백.
  - W03 탑골공원 서문: 카카오 13m → 제품 257m. 공원 보행로(306381853)와 삼일대로 사이에 `barrier=wall`(1554513241)만 있고 문이 없습니다 → OSM 공백.
  - W03 공원 안: 카카오 25m → 제품 104m. 경로가 `highway=pedestrian`+`area=yes`(way 1554513242) 광장 면으로 이어지는데, v2 빌드 규칙이 「area=yes 는 싣지 않는다」입니다 → **우리 규칙 문제, OSM 자료로 고칠 수 있음.**
- 그림: `.tmp/mobility_claude_resume_20261012_201012/web/walk-overlay-W01-W02.png`, `walk-overlay-W03-W04.png`. 표: `walk-compare-v1.json`, `walk-coverage-v1.json`, `walk-legs-v1.txt`, `osm-at-gaps-v1.txt`, `osm-at-gaps-v2.txt`.

## 3. 확장 실패 4건 원인

1. **경복궁→성수(test_golden · test_golden_all_modes · test_reasons_axis)** — 결함이 아닙니다. 제품이 이제 한 대 뒤 열차를 찾습니다. 경복궁 12:52 3호선 오금행 → 을지로3가 12:57 → 환승 4분 → 13:01 2호선 → 성수 13:16. 골든은 12:45 → 12:55 → 13:09 였습니다. 카카오 공식 시간표(평일)에 경복궁 안국 방면 12:45·12:52, 을지로3가 을지로4가 방면 12:55·13:01 이 모두 있습니다(2026-10-12 22:1x 관측). 출발이 12:41 로 늦어지면서 subway_2(44분)는 「더 이른 출발 필요」로 left_out 에 빠지고, 후보가 하나라 「가장 짧음」 문구가 없어져 test_reasons_axis 가 실패합니다.
2. **저녁 식당→롯데마트(test_golden 2건 · test_walk_m_and_fare)** — 매장 좌표(37.5559, 126.9707)가 OSM 관계 7307085(building=train_station, 서울역) 안에 있습니다. 가장 가까운 보행 간선과 84.6m 떨어져 있습니다. 건물 외곽 출입구 10128702879·10128702880 은 외곽선 way 331969674 에만 있고 **어떤 보행로와도 노드를 공유하지 않습니다.** 카카오도 이 점까지 길로 잇지 못하고 111.3m 직선을 긋습니다(경로 끝이 요청점에서 111m). 카카오 장소 자료의 「롯데마트 입구」는 37.55587158, 126.96919053 이고 OSM 출입구와 약 23m 떨어져 있습니다(제품 입력으로 쓰지 않음).
   - Codex(gpt-6-sol, 본계정)와 1회차 합의: 출입구가 실제 보행로와 노드를 공유할 때만 출입구까지 경로를 복구합니다. **출입구 도착을 매장 도착으로 써서 일정 성립을 판정하지 않습니다.** 건물 안 직선은 시간에 더하지 않습니다. 이 예시는 연결 근거가 없으므로 「보행 접근 미검증」 유지가 맞습니다. 기록: `.tmp/mobility_claude_resume_20261012_201012/claude-scratch-45290d/consensus/20261012_2230_building_access/decision.md`.

정답 JSON 은 고치지 않았습니다. 사용자에게 물어 둔 것: 원본은 두고 새 이름의 골든 v2 를 만들지. 내용은 경복궁→성수를 12:52 로, 롯데마트 구간을 「보행 접근 미검증」 skipped 로 바꾸고, test_walk_m_and_fare 는 검증 가능한 다른 도보 쌍으로 바꾸는 것입니다. 추천은 「예」입니다. **답은 아직 받지 않았습니다.**

## 4. 남은 일(우선순위)

1. 이동 시험 전체 재실행 — plan.py 수정 뒤 아직 안 했습니다. 다른 실행의 baseline(21:27)은 1498 통과·18 실패·4 오류였습니다(`baseline-full-mobility.log`). 자전거·route_shape·earliest 실패는 다른 실행이 `fix4.log`·`precheck` 로 다루던 중이었습니다.
2. 광장 면(`area=yes` + pedestrian/footway) 외곽을 보행 간선으로 넣는 빌드 변형 → W01~W04 재비교. 상자 단위 작은 그래프 실험 스크립트는 디스크 부족(ENOSPC)으로 저장하지 못했습니다. 다른 실행이 만든 `datasets/mobility/scripts/build_road_graph_v3.py` 와 `.tmp/.../build-v3*.log` · `fetch-walknet*.log` · `product_walk_check.py`, 백업 `final_project_cs/_backup/2026-10-13_seoul_walk_router/` 가 같은 방향의 작업으로 보입니다. **먼저 대조해 겹치지 않게 하십시오.**
3. 횡단보도 공백 — 행정안전부 「전국횡단보도표준데이터」(공공데이터포털 표준데이터, 수정일 2026-10-08). **내려받기는 사용자 허락이 필요합니다(아직 받지 않음).** 파일 크기는 확인하지 않았습니다.
4. 역 접근 `_eff` 에 남은 대체 계산 4가지([plan.py:346-378](../../../../app/domains/travel_ops/instances/mobility/engine/plan.py) · [plan.py:452-472](../../../../app/domains/travel_ops/instances/mobility/engine/plan.py)) — 라우터 없음·실패 시 직선, 낙관 시 직선×계수, `WALK_ROUTED_CAP_PROPOSED` 2배 상한, 연결통로 직선×1.2. 따릉이 도보 [verify_time.py:1104-1125](../../../../app/domains/travel_ops/instances/mobility/engine/verify_time.py) 도 직선×계수입니다. 제거하지 않았습니다.
5. 택시 과소 예측 — [taxi-research/REPORT.md](taxi-research/REPORT.md)만 읽었습니다. 개인 영수증은 열지 않았습니다.

## 5. 환경 주의

- 2026-10-12 22:2x 에 C 드라이브 남은 용량이 0 바이트였고, 다른 실행의 OSM 그래프 빌드가 「Could not resize file」로 실패했습니다. 10-13 00:3x 에는 3.6GB 로 회복됐습니다. 그래프 빌드 전 용량을 확인하십시오.
- 메모리 16GB 에 다른 세션의 전체 pytest 가 3GB 넘게 쓰는 일이 잦습니다. 보행 그래프를 올리는 시험은 MemoryError 가 날 수 있으니 다시 시도하십시오(다른 세션 프로세스는 죽이지 않음).
- osmium 은 `PYTHONPATH=.tmp/mobility_complete_20261008/deps` 로 anaconda 파이썬에서 쓸 수 있습니다(shapely 없음).
- 진단 스크립트·OSM 상자 추출: `.tmp/mobility_claude_resume_20261012_201012/claude-scratch-45290d/`.

mock 서버 시험(화면 반응): 안 했습니다.
실서버 확인(서버 응답): 안 했습니다. x600 서버의 cs 프로젝트 서버 HTTP·DB 와 휴대폰 지도 SDK 를 보지 않았습니다.
커밋·푸시·배포·외부 메시지 전송: 0건.
