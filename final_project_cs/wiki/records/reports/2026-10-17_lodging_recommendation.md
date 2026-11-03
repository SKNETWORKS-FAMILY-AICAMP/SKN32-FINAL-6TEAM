---
type: record
title: 예시 계획의 숙소 추천 오류 수정
description: 숙박 후보 제한·선택 후 분류 유지·호텔 조식 자동 추천을 로컬에서 수정하고 검증한 기록
status: draft
domain: travel
---

# 예시 계획의 숙소 추천 오류 수정

숙소 추천에서 숙박 이외의 장소가 섞이고, 호텔 선택 후 숙박 조건이 사라지며, 자동 추천이 호텔 조식을 활동으로 바꾸는 문제를 수정했습니다. **로컬 작업 폴더의 수정·검증 결과**이며 운영 서비스 반영 기록은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최초 결함 재현 | 완료 | 9/9 실행 = 100% · 8건 실패 |
| 관련 단위 시험 | 통과 | 75/75 = 100% |
| 격리 DB HTTP 회귀 시험 | 통과 | 52/52 = 100% |
| 실제 카카오 장소 API 확인 | 응답 정상 | 2/2 = 100% |

확인일: 2026-10-17, 한국 시각. 진행 비율의 분모는 각 행에서 실제 실행한 시험·요청 건수입니다. 최초 9건은 수정 전 재현 시험이며, 최종 단위 시험에는 확장한 숙소 시험 15건과 기존 입력 해석 시험 60건이 포함됩니다. 서로 다른 실행의 건수를 합쳐 전체 제품 성능으로 해석하지 않습니다.

## 원인

1. 위치 기준은 이미 있었습니다. `neighbours()`·`reference()`는 지정 지역을 우선하고, 지역이 없으면 같은 날 앞뒤 일정의 좌표를 사용합니다. 아침 호텔 뒤에 경복궁이 있으면 경복궁이 기준이 됩니다. 이 규칙 자체가 숙소에서 빠진 것은 아니었습니다.
2. 후보의 종류를 활동·식사로만 나눴습니다. 호텔은 활동 쪽으로 표현되므로 공원·생활용품점도 숙소 후보 필터를 통과할 수 있었습니다. 카카오 결과의 숙박 분류 `AD5`를 후보에 보존하지 않았고, 지역 반경도 지도 결과에 적용하지 않았습니다.
3. 고객이 장소를 고르면 이름 없는 줄의 `parts`가 사라집니다. 숙소 여부를 `parts.content_type`만으로 확인해 이후 추천·검색이 일반 활동 또는 식당 경로로 들어갈 수 있었습니다. 자동 추천은 숙소·숙소 안 식사 중 먼저 나온 활동 후보를 선택해 호텔 조식의 종류를 바꿀 수 있었습니다.

등록된 숙소 에이전트 팀은 `config/project.yaml`의 `LodgingTeam`, `lodging.status`입니다. 확인 화면의 후보 추천은 아래 공통 접수 부품이 수행합니다. 팀 등록 여부와 이번 후보 필터 오류는 구분합니다.

## 수정

- [후보·검색](../../../app/domains/travel_ops/components/intake/candidates.py): 숙박 분류·카테고리를 확인하고 지도에서 받은 숙박 분류를 보존합니다. 숙소 후보를 별도로 모으며 지정 지역 또는 앞뒤 일정 기준의 반경을 적용합니다. 고객이 호텔을 고른 뒤에도 저장된 숙박 카테고리로 숙소 조건을 유지합니다.
- [자동 추천](../../../app/domains/travel_ops/components/intake/autofix.py): 숙소와 숙소 안 식사를 함께 보여도 자동 적용은 원래 일정 종류를 유지합니다. 예약한 숙소를 바꾸지 않는 경계도 검사했습니다.
- [신규 단위 시험](../../../tests/unit/travel/test_intake_lodging_candidates.py)·[신규 HTTP 시험](../../../tests/e2e/test_intake_lodging_recommendation.py): 다음 일정 기준, 지정 지역 우선·반경, 숙박 이외의 장소 제외, 선택 이후 재추천·검색, 이틀 호텔 조식의 식사 유지, 예약 보호를 검증합니다. 두 파일을 [여행 시험 목록](../../../tests/test-suites.json)에 등록했습니다.

예: `09:00 호텔 조식 → 10:00 경복궁`이면 경복궁 주변에서 숙박 분류가 확인된 후보를 찾습니다. 자동 적용 후에도 호텔 조식은 식사로 남습니다. 조식 제공 여부·영업시간을 모르는 곳을 확인한 것처럼 표시하지 않습니다.

## 실행과 결과

기존 로컬 개발 DB에 연결되지 않아 작업 폴더 안에 별도의 PostgreSQL 클러스터를 만들고 현재 마이그레이션을 적용했습니다. 시험용 클러스터만 사용하고 실행 후 정상 종료했습니다. 기존 로컬 개발 DB와 운영 서비스 데이터는 변경하지 않았습니다. 로컬 설정 파일에 선언되지 않은 별도 키가 있어, 시험 실행기에서 선언된 설정만 읽도록 분리했습니다. 실제 설정 파일은 수정하지 않았습니다.

아래 파일들을 동일한 최종 실행에서 검사했습니다. 실행 결과 XML은 로컬 작업 폴더의 `.tmp/lodging-fix/final-results.xml`에 있습니다.

```text
tests/unit/travel/test_intake_lodging_candidates.py
tests/unit/travel/test_intake_nameless_read.py
tests/unit/travel/test_line_parts.py
tests/e2e/test_intake_candidate_kinds.py
tests/e2e/test_intake_nameless_lines.py
tests/e2e/test_intake_review.py
tests/e2e/test_intake_lodging_recommendation.py
```

결과: **127/127 = 100%, 177.46초**. XML에서 단위 75건·HTTP 52건, 실패 0건·오류 0건을 다시 집계했습니다. 수정한 Python 파일 4개의 `ruff --select F,E9`와 변경 파일의 `git diff --check`도 통과했습니다.

별도 구조·계약 검사 5개 파일은 **109/110 = 99.09%**입니다. 실패 1건은 `test_team_does_not_import_infrastructure_directly[activity/disaster_impact.py]`이며, [해당 파일 75행](../../../app/domains/travel_ops/instances/activity/disaster_impact.py#L75)의 직접 import 때문입니다. 같은 import가 기존 Git HEAD에도 있음을 확인했습니다. 이번 숙소 변경 파일이 아니며 수정하지 않았습니다. 전체 계약 검사가 통과했다고 해석하지 않습니다.

## 실제 외부 호출과 확인 한계

- mock 서버 시험 (화면 반응): **안 했음**. 이번 HTTP 시험은 실제 접수 앱·격리 PostgreSQL에 외부 장소 소스의 목업을 연결했습니다. 실제 브라우저 화면 시험은 수행하지 않았습니다.
- 실서버 확인 (서버 응답): **했음 — 카카오 장소 API 2/2**. 기존 로컬 키로 경복궁 주변의 `숙소`·`호텔` 검색이 정상 응답했습니다. 실제 `호텔` 검색에도 숙박 이외의 생활용품점이 포함돼 결과 분류 필터가 필요함을 확인했습니다. 이 결과를 공용 장소 DB나 재사용 캐시에 저장하지 않았습니다.
- **미확인**: 운영 cs 프로젝트 서버의 배포 버전·설정·화면에서 사용자가 겪은 정확한 요청 로그. 로컬 외부 API 성공만으로 운영 환경의 키·연결 상태까지 정상이라고 단정하지 않습니다. 커밋·푸시·배포는 하지 않았습니다.

## 덮어쓰기 전 백업

- [후보·자동 추천 원본](../../../app/domains/travel_ops/components/intake/_backup/2026-10-17_012632_lodging_recommendation/) — 작업 시작 시점의 미커밋 변경도 보존합니다.
- [API 문서 원본](../../external/rest-endpoints/_backup/2026-10-17_012632_lodging_recommendation/) — 현재 계약 문서를 고치기 전 사본입니다.
- [시험 목록 원본](../../../tests/_backup/2026-10-17_014043_lodging_suite/) — 기존 시험 등록 내용을 보존합니다.

현재 계약의 한 줄 요약과 이 기록 링크는 [계획 읽기·설문 API](../../external/rest-endpoints/web-intakes.md)에 남겼습니다.
