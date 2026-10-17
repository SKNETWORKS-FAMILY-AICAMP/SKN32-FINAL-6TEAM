# SNS 맛집 링크 일정 반영 기능 검토 — 2026-10-15

현재 작업 폴더의 구현을 검토했다. 제품 코드는 수정하지 않았다. 우선 수정할 P1 2건과 P2 3건을 확인했다.

## 실행 검증

| 범위 | 실제 실행 결과 |
|---|---|
| SNS 링크·배치·초안 생성·API 관련 백엔드 단위 시험 6개 파일 | 127/127 = **100%** 통과, Starlette 기존 deprecation 경고 1건 |
| social-dining·live API·plan-check·intake-review·trip-registration 화면 시험 | 291/291 = **100%** 통과, 시험 파일 35개 |
| TypeScript `npx tsc --noEmit --incremental false` | 종료 코드 0 |
| 아래 결함의 부품 실행 재현 | 5/5 = **100%** 재현 |

시험 통과율은 해당 시험 범위의 결과이며 기능 전체 완성도를 뜻하지 않는다. 이번 검토에서 실제 SNS·모델 호출, 브라우저 조작, 운영 DB·배포 검증은 하지 않았다. 앞선 브라우저 검증 보고서와 이번 실행을 구분한다.

## 확인한 결함

### [P1] 최초 초안의 식이 조건이 링크 반영 검사에 전달되지 않는다

- 위치: `app/domains/travel_ops/components/intake/social_dining_plan.py:144`, `app/domains/travel_ops/entry/trip_api.py:1887`, `app/domains/travel_ops/components/intake/social_dining.py:185`.
- 빈 접수의 `review_only` 초안 생성은 요청 설문을 생성기에 넘긴다. 그러나 `stage_generated`의 `build_rows`는 `body.constraints`와 설문을 보존하지 않는다. `_intake_survey`도 요청 설문을 읽어 합칠 뿐 저장하지 않는다.
- 후속 preview/apply의 `_dietary_requirements`는 원래 여행과 DB에 저장된 접수 설문만 읽는다. 아직 여행이 없는 빈 접수에서 화면이 직접 보낸 채식·할랄 조건은 여기서 빠져, 식이 근거가 없는 식당도 통과할 수 있다.
- 재현: `constraints.dietary=[vegetarian]`, `constraints.survey.priority_details.food=[halal]` 초안을 stage한 결과 관련 claim 0개, 저장 설문 빈 객체. 해당 초기 접수의 요구 조건은 빈 tuple이고 `_dietary_verdict`는 검증되지 않은 장소도 허용했다.
- 조치: 생성 시 확정한 요청 조건을 접수에 보존하고 preview/apply와 최종 확정까지 같은 조건으로 검사한다.

### [P1] 별관 선택을 본점으로 조용히 바꾼다

- 위치: `app/domains/travel_ops/components/intake/social_dining.py:304-307`.
- `_same_place`가 도로명·건물번호와 이름 포함 여부로 먼저 `True`를 반환해 지점 표시 충돌과 좌표 거리 검사를 우회한다.
- 재현: 같은 주소의 `가상식당 본점(place:main)`과 `가상식당 별관(kakao:annex)`을 후보로 주고 별관을 선택해 저장했다. 실제 preview가 둘을 중복으로 병합한 뒤 `selected_ref`를 `place:main`으로 바꾸고 본점 변경안 1건을 만들었다.
- 조치: 서로 다른 지점 표시는 병합하지 않고, 주소 일치 판단에도 위치 검증을 적용한다. 제공자 별칭 치환이 고객의 실제 지점 선택을 바꾸지 않도록 한다.

### [P2] 지역·지점 정보를 붙인 검색어로 기존 DB 식당을 놓친다

- 위치: `app/domains/travel_ops/components/intake/social_dining.py:363`.
- `name + branch + area` 전체를 `candidates.search`로 보낸다. 관광 목록과 요식 원장 검색은 이 문자열 전체를 가게 이름의 `ILIKE` 조건에 넣는다. `우래옥 서울`, `명동교자 본점 명동`은 해당 이름의 행과 일치하지 않는다. 외부 검색만 남으면 운영시간 근거가 없어 배치가 보류될 수 있다.
- 재현: 이름이 `우래옥`인 목록 어댑터로 preview하면 `area=서울`일 때 변경 0건·`place_not_found`, 같은 후보에서 지역만 비우면 변경 1건이다.
- 조치: DB 이름 검색과 지역·지점 필터를 분리하고 이름에 이미 포함된 지점을 중복 연결하지 않는다.

### [P2] head 뒤 본문이 추출 모델 입력에 섞인다

- 위치: `app/domains/travel_ops/components/intake/social_links.py:235-239`.
- `</head>`를 발견해도 해당 수신 chunk 전체를 저장한다. `_MetadataReader`도 head 범위를 추적하지 않고 일반 표시 텍스트를 수집한다. head와 body 일부가 같은 chunk로 오면 본문이 모델 입력·근거 인용의 대상이 된다.
- 재현: 한 번의 read에 `<head><title>Travel clip</title></head><body>BODY_ONLY_RESTAURANT</body>`를 주면 `_request` 반환과 모델 입력용 `reader.text()` 양쪽에 본문 표지가 남는다.
- 이는 [D-024](../../../../wiki/decisions/D-024-study-only-social-post-text.md)의 head 안 제목·설명 메타 한정 결정과 다르다.
- 조치: 수신 데이터를 정확히 head 끝에서 자르고 파서도 head 안의 허용된 메타·title만 수집한다.

### [P2] 저장된 반영안을 새로고침·재접속으로 복구할 수 없다

- 위치: `app/domains/travel_ops/components/intake/social_dining.py:103-106`, `frontend/apps/web/src/features/social-dining/model.ts:64`.
- preview는 proposal을 DB에 저장하지만 GET은 revision과 links만 반환한다. 화면 load도 links만 복원한다. preview 응답이 끊기거나 새로고침하면 저장된 proposal_id와 변경안을 회수할 수 없어서 다시 생성해야 한다.
- 재현: proposal이 존재하는 저장 상태에서 `list_links`를 호출해도 proposal이 반환되지 않는다. [API 계약](../../external/social-dining-links.md)은 GET으로 현재 저장 제안도 반환하도록 정한다.
- 조치: 현재 revision에 유효한 제안을 GET에 포함하고 화면이 복원하도록 한다. 만료된 제안은 명시적으로 무효화한다.

## 재현 자료

- 실행 스크립트: 저장소 루트 `tmp/social-dining-review/reproduce_findings.py`.
- 실행 결과: 저장소 루트 `tmp/social-dining-review/results.json`.
- 실행 명령: `final_project_cs`에서 `.\.venv\Scripts\python.exe ..\tmp\social-dining-review\reproduce_findings.py`.
- 저장소의 기존 시험 fixture로 DB 저장·후보 검색·네트워크 어댑터만 대체한다. 서비스의 preview·중복 병합·stage·메타 읽기 코드를 실행하며, 실제 외부 서비스나 고객 DB를 호출하지 않는다.

백엔드 시험 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/test_social_links.py tests/unit/travel/test_social_dining_rank.py tests/unit/travel/test_social_dining.py tests/unit/travel/test_social_dining_plan.py tests/unit/travel/test_social_dining_api.py tests/unit/travel/test_social_dining_initial_plan_api.py -q --tb=short
```

프런트엔드 시험 명령(`frontend/apps/web`, TEMP/TMP는 저장소 안 임시 폴더로 지정):

```powershell
npm run test -- src/features/social-dining src/lib/live/social-dining.test.ts src/features/plan-check src/features/intake-review src/features/trip-registration
npx tsc --noEmit --incremental false
```
