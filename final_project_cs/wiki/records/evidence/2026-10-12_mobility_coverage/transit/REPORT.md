# 대중교통 웹 검증과 현장 시험 준비 — 2026-10-12

공식 웹으로 확인할 수 있는 예정 시각·출구 번호·통계의 뜻을 대조했고, 현장 기록을 받아 같은 이동 사건의 오차를 계산하는 도구를 추가했습니다. 실제 운행 관측 없이 가능한 범위와 현장에서 측정할 범위를 나눴습니다.

| 할 일 | 결과 | 진행 |
|---|---|---|
| 담당 기능의 근거·경로·실행명령·남는 한계 연결 | 9개 항목 목록 완성 | 9/9 = 100% |
| 공식 홍대입구 첫차·막차 경계 | 평일·휴일 양방향 일치 | 8/8 = 100% |
| 공식 홍대입구 출구 번호 존재 | 보유 OSM 자료에 존재 | 9/9 = 100% |
| 보유 공표 승차 시각 대응 | 12그룹 전체 대응 | 2,044/2,044 = 100% |
| 관련 고유 개발 시험 | 실행 결과 중복 제거 | 259/259 = 100% |
| 새 현장 탑승 관측 | 이번 작업에서 측정하지 않음 | 0건 |

첫 행은 문서·시험 연결 목록의 완료율입니다. 21개 기능의 실사용 완료율이 아닙니다. 공표 시각 2,044개는 보유 2026-10-09 웹 표본의 무결성 재검증이고, 오늘 새로 웹과 비교한 시간 값은 첫차·막차 8개입니다. 출구 9개는 번호의 존재만 확인했으며 좌표 정확도·출구까지 보행 시간·실제 승차 칸은 이 분모가 아닙니다.

## 새로 가능해진 일

[현장 관측 비교 도구](C:/Users/playdata2/Documents/final_workspace/final_project_cs/scripts/mobility/compare_transit_observations_v1.py)는 예측과 참조가 같은 여행·구간·노선·방향·역·일반/급행·승차/하차/환승 사건인지 확인합니다. 특정 열차 번호를 예측에 넣었으면 참조에도 같은 번호가 있어야 합니다. 시간대가 없는 시각, 사건 뒤에 작성한 예측, 누락된 허용오차, 식별자 불일치, 중복 기록은 평가하지 않고 이유를 남깁니다. 허용오차는 입력값이며 전체 제품 기준을 새로 지어내지 않았습니다.

실제 이용 기록, 공식 예정 시간표, 승강장 표시, 개발 재생은 각각 따로 집계합니다. 잘못 정렬된 행도 전체 입력 분모에 남깁니다. 비어 있는 [현장 기록 서식](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/field-record-template-v1.json)은 평가 0/1·종료코드 1이며, [개발 재생 예시](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/synthetic-replay-example-v1.json)는 개발 재생 1/1·종료코드 0입니다. 두 경우 모두 실제 관측 측정은 0건입니다.

이 도구는 비교 준비·사후 평가용이며 운영 서비스에 연결하지 않았습니다. 참조 종류와 증거 위치는 기록자가 제공하는 값입니다. 증거 파일·웹 원문의 존재와 진위를 외부에서 자동 확인하거나 기록 시각을 공증하지는 않습니다. 현장에서는 예측 원본을 사건 전에 보존해야 합니다. 실제 서비스 전체 오차를 말하려면 표본 설계·수집과 허용오차 확정이 별도로 필요합니다.

## 공식 웹에서 확인한 범위

- [공항철도 홍대입구역](https://www.airportrailroad.com/train/normal/info/030/0): 평일·휴일 서울역 방향 첫차 05:34·막차 24:31, 공항 방향 첫차 05:28·막차 24:08을 보유 공표분과 비교했습니다. 안내도의 출구 1~9번도 보유 자료와 맞췄습니다. 임시 연장·운휴의 모든 날짜를 검증하지 않았습니다.
- [서울 실시간 지하철 도착정보](https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do), [역별 시간표](https://data.seoul.go.kr/dataList/OA-101/A/1/datasetView.do), [버스 도착정보](https://www.data.go.kr/data/15000314/openapi.do): 생성 시각 이후 보정, 예정 시간표와 실도착 차이, 정확한 노선·정류소 식별을 확인했습니다. 제품의 현재 승차 적용·미래 환승 모델·조회 실패 시 명시적 모델 재검증 시험을 실행했습니다.
- [9호선 혼잡 통계](https://data.seoul.go.kr/dataList/OA-22197/F/1/datasetView.do): 30분간 역을 통과한 열차 평균이라는 자료의 성격을 확인했습니다. 보유 일반 5,776행·급행 2,432행의 구분 적용을 시험했습니다. 현재 특정 열차 혼잡과의 일치율은 측정하지 않았습니다.
- [서울교통공사 공지 명세](https://www.data.go.kr/data/15144070/openapi.do): 지연·사고·무정차·시간표 변경 공지의 범위를 확인했습니다. 공지 시작/종료·다역 표기와 도로 대체 조회·사건 후 재경로를 오프라인 개발 입력으로 재생했습니다. 새 실제 사건의 탐지율과 지연을 측정하지 않았습니다.

## 실행과 수정

선택 회귀는 257/257 통과·건너뜀 0건(86.81초), 최신 비교 도구는 41/41 통과·건너뜀 0건(3.70초)입니다. JUnit의 `classname+name`으로 중복을 제거하고 같은 비교 도구 시험은 최신 실행을 사용하면 고유 259/259입니다. 둘을 단순히 더한 298개로 보고하지 않습니다. 앞선 전체 657개와도 중복되므로 합산하지 않습니다.

초기 회귀 210/211에서 실패한 사건 후 재경로 시험은 옛 연결 지점에 시험 대역을 붙였습니다. 현재 제품이 부르는 `team_hooks.legs.leg_planner`로 기존 두 시험의 연결 지점만 바꿨고 사건 조건 변환·앞 일정 종료 뒤 출발·새 경로 및 소요 보존 검사는 유지했습니다. 제품 동작을 약화하지 않았습니다. 기존 시험 백업은 [재경로 시험 원본](C:/Users/playdata2/Documents/final_workspace/final_project_cs/tests/unit/travel/_backup/2026-10-12_reroute_binding/test_route_reroute_engine.py)입니다.

최초 자료 감사는 제품이 선택하지 않는 비압축 시간표를 지정해 공표 자료의 원본 해시 검사에서 실패했습니다. 실제 제품의 `timetable_file`이 선택하는 압축 시간표로 바로잡았습니다. 현재 로더가 읽은 시간표는 453,356행·노선/역 798쌍이며, 대조하는 12개 그룹 안에서 공표분에 없는 원자료 312행은 기존 정책에 따라 제외합니다. 이 수치를 전체 시간표 최신성이나 빠진 열차가 없다는 증거로 사용하지 않습니다. 최초 단독 비교 도구 시험의 임시폴더 권한 오류 2건도 기록을 보존한 뒤 작업 폴더 안 임시폴더에서 모두 다시 실행했습니다.

작업 폴더 루트에서 재현하는 명령은 다음과 같습니다. 개발자 API·DB·알림 전송을 실행하지 않습니다.

```powershell
C:/Users/playdata2/anaconda3/python.exe .tmp/mobility_coverage_20261012/transit/audit_public_inputs.py
C:/Users/playdata2/anaconda3/python.exe .tmp/mobility_coverage_20261012/transit/run_helper_checks.py
C:/Users/playdata2/anaconda3/python.exe .tmp/mobility_coverage_20261012/transit/run_transit_checks.py
C:/Users/playdata2/anaconda3/python.exe final_project_cs/scripts/mobility/compare_transit_observations_v1.py --input .tmp/mobility_coverage_20261012/transit/synthetic-replay-example-v1.json --output .tmp/mobility_coverage_20261012/transit/new-replay-report.json
```

보고서 생성기와 비교 도구는 기존 출력이 있으면 백업합니다. 시험 실행을 반복할 때 기존 XML·로그는 먼저 보존하고 새 실행 이름을 사용해야 합니다.

기계 근거는 [9개 항목 구조화 근거](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/coverage-evidence-v1.json), [공개 자료·새 웹 대조](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/public-input-audit-v2.json), [선택 회귀 JUnit](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/transit-regression-v2.xml), [최신 비교 도구 JUnit](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_coverage_20261012/transit/helper-final-v2.xml)입니다. 수정 파일 해시와 최초 실패 기록도 함께 남겼습니다.

개발자 API 호출·새 다운로드·개인자료 접근·외부 메시지 전송·커밋·푸시·배포는 모두 0건입니다. API 일일 예비량 20%를 소비하지 않았습니다. 공유 누적 사용량은 조회하지 않았고, 불명확한 API를 호출하지 않았습니다.
