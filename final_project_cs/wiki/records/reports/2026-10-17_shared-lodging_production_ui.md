---
type: record
title: 여행 공통 숙소·호텔 조식 연결의 운영 화면 검증
description: UI팀 숙소 표시를 재사용해 반복 호텔 조식을 한 숙소에 연결하고 실제 예시 두 건을 확인한 기록
status: verified
domain: travel
date: 2026-10-17
---

# 여행 공통 숙소·호텔 조식 연결

새 예시와 기존 예시 모두, 첫 호텔에서 추천을 한 번 실행하면 이틀의 호텔 조식이 **트레블로지 명동을지로호텔 하나**로 연결된다. 공개 서비스의 실제 화면과 저장된 값을 확인했다.

| 확인 항목 | 상태 | 진행 |
|---|---|---|
| 새 예시의 양일 숙소 | 같은 곳 | 2/2 날짜 = 100% |
| 서로 다른 숙소였던 기존 예시 | 같은 곳으로 수정 | 2/2 날짜 = 100% |
| 숙박 아이콘·공통 숙소 표시 | 확인 | 2/2 기능 = 100% |
| 좁은·넓은 화면 가로 넘침 | 없음 | 2/2 크기 = 100% |

## 원인과 변경

앞선 수정은 호텔 후보 공급과 항목별 추천을 복구했지만, 날짜별 호텔을 같은 숙소로 묶지 않았다. 호텔 조식이 각각 그날의 이웃 장소를 기준으로 추천돼 서로 다른 숙소가 저장됐다. 이 기록은 이전 날짜별 호텔 검증 기록을 보완한다.

이름 없는 호텔·호텔 조식은 여행 공통 숙소로 묶는다. 후보를 모을 중심은 전체 방문지의 평균 좌표이고, 순서는 방문지까지의 평균 직선거리다. 각 날짜의 식사 시간·앞뒤 이동을 검증해 **모든 연결 항목에 맞는 호텔 하나**를 같은 판에서 저장한다. 지역 지정은 우선하며, 여러 체크인·체크아웃 구간은 각각 유지한다. 고정·예약·업체 예약 숙소와 충돌하면 저장을 거부한다.

직접 장소 선택과 항목 되돌리기도 같은 연결 범위를 사용한다. 관련 없는 관광·식사 항목은 항목별 추천에 포함하지 않는다. 과거 판의 서로 다른 호텔은 확인 필요로 표시하고 다시 고를 수 있다. 숙박 기간이 없는 조식으로 체크인·박 수를 만들지 않는다.

실제 화면에서 식사 짝이 앞의 세 호텔에만 붙어 뒤쪽 후보가 누락되는 추가 결함을 발견했다. 전체 후보에 같은 숙소의 식사 짝을 붙이고, 네 번째 호텔만 양일에 맞는 회귀 시험을 추가했다. 기존의 서로 다른 호텔도 전체 동선으로 다시 비교한다.

## UI팀 코드의 출처와 재사용

팀 저장소 `SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM`의 `feat/web-stay-check-20261015`, 커밋 `a85441531`이다. `c51583fc6` → PR #56 → `507d929f6` 경로로 병합됐으며 확인한 develop `6fc4a2d5cf61365289ad05c9f38f1e41f20d66e1`에 포함돼 있었다.

기존 UI팀의 숙소 출발 줄·숙박 아이콘·숙소 보기 동작을 사용했다. 공통 숙소 연결 자료를 공급해 호텔 조식에서도 같은 표시가 나오도록 확장했다. 조식 종류는 식사로 유지하고 장소 아이콘은 숙박으로 표시한다. 숙소 보기 버튼은 Enter로 해당 카드를 열며, 최소 높이 44px와 긴 이름 줄바꿈을 적용했다.

## 검증

| 범위 | 결과 | 조건 |
|---|---|---|
| 숙소 단위 시험 | 36/36 통과 | 마지막 후보 범위 수정 포함 |
| HTTP·계약·보안 회귀 | 고유 491/491 통과 | 첫 실행 490/491, 지정 숙소 위치 보존 수정 후 관련 13/13 재검증. 고유 시험 수로 집계 |
| 마지막 후보 범위 HTTP 회귀 | 12/12 통과 | 격리 DB·외부 API mock 자료 |
| 최신 매니저 통합 | 97/97 통과 | 숙소 HTTP·게스트 시험 목록·재난 시험 |
| 최종 배포 API 이미지 숙소 시험 | 30/30 통과 | 이미지의 실제 코드·순수 계산/자료 대역 |
| 최종 배포 웹 이미지 | 795/795 통과 | lint·typecheck·전체 단위 시험·build 성공 |
| 완료 관문 | 26/26 통과 | 최종 통합 판, MVP 18/18 |
| Python 정적 검사 | 통과 | 변경 Python의 ruff F·E9 |

주요 실행 범위:

```text
pytest tests/unit/travel/test_intake_shared_lodging.py tests/unit/travel/test_intake_lodging_candidates.py tests/unit/travel/test_intake_lodging_registered.py tests/unit/travel/test_intake_stays.py tests/unit/travel/test_intake_stay_morning.py -q
pytest tests/e2e/test_intake_lodging_recommendation.py tests/e2e/test_intake_stay_lines.py tests/e2e/test_intake_item_restore.py tests/e2e/test_intake_restore.py tests/e2e/test_intake_candidate_kinds.py tests/contract tests/security -q
pytest tests/e2e/test_intake_lodging_recommendation.py tests/integration/test_simulation_guest_catalogue.py tests/integration/test_watch_simulation.py -q
python -m scripts.verify_dod_v11
npm run lint && npm run typecheck && npm run test && npm run build
```

로컬 검증은 작업 전용 PostgreSQL과 선언된 설정만 읽는 개인 러너를 사용했다. Composer 라이브러리는 CI와 같은 참고 구현의 공통 라이브러리 경로를 사용했으며, 참고 구현의 도메인 시험·자료는 가져오지 않았다. Windows 웹 시험은 임시 파일 접근 오류로 67개 파일이 실행되지 않아 전체 성공으로 집계하지 않았다. 최종 Linux 웹 이미지에서 전체 795건과 빌드를 확인했다.

mock 서버 시험(화면 반응): 별도 브라우저 mock 서버 시험은 미실행. 격리 DB HTTP 시험과 구분한다.

실서버 확인(서버 응답): 했음. 공개 서비스에서 예시를 다시 불러 접수하고 첫날 호텔 자동 추천을 실행했다. 새 접수와 기존 접수의 양일 이름·좌표 동일, 식사 종류 유지, 수정된 시각·이동을 읽기 전용으로 재확인했다. 업체 예약·결제·여행 등록은 실행하지 않았다.

## 실제 저장 결과와 화면

두 시험 접수 모두 다음 결과다. 새 예시는 revision 3, 기존 예시는 revision 5다. 접수·고객 식별자는 공개 증거에서 제외했다.

| 날짜 | 호텔 | 조식 | 다음 방문 | 표시 이동 |
|---|---|---|---|---|
| 10월 24일 | 트레블로지 명동을지로호텔 | 09:00–09:35 | 경복궁 10:00 | 09:36 출발, 지하철 11분, 09:47 도착 |
| 10월 25일 | 트레블로지 명동을지로호텔 | 09:00–09:30 | 북촌한옥마을 10:00 | 09:30 출발, 지하철 17분, 09:47 도착 |

- [저장된 응답의 검증 결과](../evidence/2026-10-17_shared-lodging/saved-service-results.json)
- [새 예시 첫날 숙박 아이콘·공통 숙소](../evidence/2026-10-17_shared-lodging/fresh-day1-bed.jpg)
- [새 예시 둘째 날 같은 호텔](../evidence/2026-10-17_shared-lodging/fresh-day2-hotel.jpg)
- [둘째 날 호텔 뒤 이동](../evidence/2026-10-17_shared-lodging/fresh-day2-route.jpg)
- [375px 화면](../evidence/2026-10-17_shared-lodging/fresh-day2-375.jpg)
- [1280px 화면](../evidence/2026-10-17_shared-lodging/fresh-day2-1280.jpg)
- [기존 예시 수정 완료](../evidence/2026-10-17_shared-lodging/existing-day2-fixed.jpg)

375px·1280px에서 문서 가로 넘침이 없었으며, 공통 숙소 버튼의 실측 높이는 약 76px였다. 기존 UI팀의 카드·색·글꼴 체계는 유지했다. 변경한 숙소 표시·동작의 확인이며 제품 전체 UX·접근성 인증은 아니다.

## 반영·보존·검토

기능 커밋 `a2f2cd85`와 최신 매니저 통합 `29106b7f`의 숙소 소스를 운영 이미지에 적용했다. 릴리스 `shared-lodging-20261017-v3`의 API/worker는 `dc8aa12b6ad9`, 웹은 `32d1572b1117`이다. 변경 소스 11개의 실행 이미지 해시를 대조했고 기동 뒤 30초 안정성을 확인했다. 실제 실행 구성과 직전 이미지의 복구 사본을 보존했으며 SQL은 실행하지 않았다. DB와 관리자 앱의 컨테이너는 유지했다.

최신 매니저의 게스트 시험 작업을 보존해 병합했으며, 추가된 통합 시험 파일도 여행 시험 목록에 등록했다. develop에는 푸시하지 않는다.

원본 사본은 로컬 작업 폴더의 `_backup/2026-10-17_shared-lodging/`에 보존했다. 백업과 개인 실행 스크립트·접속 구성은 커밋하지 않는다. 과거 보고서는 덮어쓰지 않는다. 변경 담당·검토는 이 작업의 에이전트가 겸임했으며 독립 검토로 표시하지 않는다.

호텔 식당·조식 제공 여부나 영업시간을 새로 확인한 것은 아니다. 해당 정보는 화면에 미확인으로 유지한다. 후보 순위는 평균 직선거리이며 최저 가격·최소 총 이동시간의 전역 최적해를 주장하지 않는다. 광장시장의 기존 장소 확인 필요는 이 숙소 수정에 포함하지 않았다.
