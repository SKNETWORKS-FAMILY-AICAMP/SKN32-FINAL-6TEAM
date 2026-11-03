---
type: report
title: EKS checking AMD64 검증 완료·실데이터 비회귀·운영 기준 fatal로 배포 HOLD
status: draft
domain: travel
---

# EKS checking AMD64 검증과 운영 기준 실패

2026-10-29 KST. **후보 배포는 하지 않았습니다.** AMD64 실행 환경 검증과 Linux16 원인 판정은 진행했지만, 7일·42항목 합성 일정의 기존 EKS 기준 측정이 review2/3 = **66.67%**, fatal1/3 = **33.33%**였습니다. 원인 미확인 실패를 통과로 바꾸거나 재시도로 지우지 않고 HOLD를 유지합니다. [최종 판정](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/final-verdict.json). 전체 운영 검증의 분모는 모릅니다.

## 수행 범위와 배포 상태

사용자는 엄격히 검증된 배포·실제 EKS 전후를 명시적으로 요청했습니다. root와 cs AGENTS/CLAUDE, cs RULE, wiki 목차·개발 역할·코드 경로·Mobility·web-intakes 계약, 이전 인계와 실제 coordination notice를 대조했습니다. 앞선 scalar/진단 릴리스 예약 해제와 ST4F733의 배포 예약 없음을 확인했습니다. 담당은 이 세션이며 자체 검증을 별도 독립 승인으로 부르지 않습니다.

새 no-hardlinks 격리 사본 `C:/_proj/ekscheckingcontinue1029/repo`에서만 제품·CI를 편집했습니다. main 기준은 `57f3d2f004d0600f781599a6a92e8691b49bef82`, 후보는 `3fda4eee2613d89d56a6d146989de8f96c229852`입니다. [초안 PR #110](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/pull/110)은 draft/open이며 병합0·후보 CD0·후보 EKS 후측정0입니다. 팀 main·role-manager·develop 직접 push와 개인 원격 push는 하지 않았습니다. 원본 제품 코드·색인·Git 설정 변경0이며 새 보고/증거/인계와 백업 후 목차 링크만 남겼습니다.

제품 변경은 `risks.py` 한 파일입니다. 기존 cap 밖·과거 일정의 민감도 SELECT만 생략합니다. 직접 `to_item()` 호출의 기본 조회, 기존 savepoint/예외, DB 분류 변경 반영, fresh600초 재사용/601초 만료, 결과/진행 순서, cap6, provider 재시도·캐시 정책은 유지합니다. DB migration·hours 원자료 캐시·동의·저장/통지 정책은 바꾸지 않았습니다.

## AMD64와 실DB 관문

로컬 WSL은 aarch64이며 Docker/QEMU 실행 파일을 찾지 못했습니다. 기존 GitHub ubuntu CI를 이용해 실제 배포 Dockerfile로 **linux/amd64 이미지**를 만들고, `platform.machine()==x86_64` 확인 후 네트워크를 끈 컨테이너 안에서 관련51건을 실행했습니다. 새 pytest 의존성을 이미지에 덧붙이지 않았고 기존 requirements를 썼습니다. 기존 main 필수 job 이름·전체 시험·role-manager 비실행 정책을 유지하고 이미지 실행 검사를 더했습니다.

첫 시도40774330754는 제가 추가한 명령의 필수 dummy 설정 누락으로 수집 오류1건이 났습니다. 원문 로그를 보존하고 가짜 설정만 보완했습니다. 수정된 [수동 CI40774763719](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40774763719)와 [PR CI40775273306](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40775273306)은 각각 필수3/3 = **100%** 통과했습니다. 둘 다 아키텍처170통과, 전체13,324통과·466건너뜀·실패0이며 기존 전체층/실데이터 제외를 새로 늘리지 않았습니다. 이미지 회귀는 각각51/51 = **100%**, skip0입니다. CI 전체 통과를 실데이터 전체 통과로 부르지 않습니다.

새 loopback PostgreSQL16.15·63915에 표준 migration/register_prompts/seed_travel을 적용했습니다. 전체 출력·이벤트14/14 = **100%** 동등, 번갈아20쌍의 출력/이벤트 일치, 관련51/51·계약368/368·보안125/125·아키텍처170/170 = 각각 **100%**, DoD26/26 = **100%**입니다. 실제 DB 오류와 savepoint 회복·분류 갱신·timeout의 unknown/check_error·과거/item_limit·fresh 재사용 경계를 포함합니다. 로컬 위험 단계 중앙값56.40085→14.82410ms는 합성 judge와 전용 PG의 한 프로세스 측정이며 EKS 개선율이 아닙니다. 과거 실제 조립169→133 SELECT 측정은 [이전 독립 검토](2026-10-29_eks-checking-independent-review.md)의 범위로 구분합니다. 자체 PG는 종료 후 연결 거부를 확인했고 데이터는 보존했습니다.

## Linux16 원인 판정과 전체층

원래16개 단언은 **0/16 = 0% 통과·16실패·skip0**로 보존했습니다. 원인 설명16/16 = **100%**와 시험 수정/전체 Mobility 수락을 구분합니다. 단언·golden·허용오차·마커·precision 제품 기능을 수정하지 않았습니다.

1. `test_full_earliest_on_late_gives_earliest_arrival[ntower_namdae]` — 현재 01A 승하차/접근 모형은 22분이다. 12:13 목표가 이미 성립하므로 예전 29분 경로의 불가 전제가 낡았다. 실제 earliest는11:30→11:52, 목표12:07이다.
2. `test_full_earliest_is_minimal_and_matches_latest_mode[ntower_namdae]` — 현재 latest 역산은12:14목표에서11:37→11:59이다. 옛29분 모형의11:30 출발을22분 모형에 요구했다. earliest와latest를 구분해야 한다.
3. `test_full_default_leg_unchanged_without_flag` — 현재 이유 봉투는 code/reason 외 left_out을 보존한다. 빈약한 정확 키집합 단언이 후속 진단 계약과 충돌한다. code=arrive_late, earliest없음과 실제 left_out을 별도로 검증했다.
4. `test_full_plan_puts_earliest_in_skipped` — 이 시나리오는 현재 이미 성립하여 skipped가 없다. on/off 비교에 captured_at도 달랐다. 출발문맥 시계를 고정한 전체출력 on/off 동등을 별도로 검증했다. 제품 시계/출력 제거는 하지 않았다.
5. `test_full_earliest_waits_for_first_train[after_last_holiday]` — 기본 수단에 버스→버스가 추가되어710→301이03:49출발,05:16도착/05:36목표로 첫 지하철보다 먼저 간다. subway만 명시한 원래 첫차 조건은05:23출발/06:24목표로 별도 통과했다.
6. `test_full_earliest_uses_mixed_when_stations_blocked` — 기본 후보는 이제303→2412 버스→버스다. 지하철+버스만 허용하는 옛 단언이 현재 버스 대안을 거부한다. 금지 호선 사용없음·앞 일정 후 출발·목표 전 도착을 별도 검증했다.
7. `test_golden_bike` — 자전거 golden에는 후속 Item.detail.departure_context 계약이 없고, 마지막 구간은 현재 검증된 직접도보 응답이 없어 mode_unavailable이다. 옛 직선도보를 복원하거나 새 실제보행 근거를 지어내지 않는다. golden은 보존한다.
8. `test_bike_not_called_by_default` — 기본 golden42경로 차이는 departure_context 추가, 현재 출입구 접근/탑승시간 및 혼합 후보, 미검증 직접도보 대신 지하철 선택이다. captured_at만 제거하면 해결되지 않는다. 코드/자료 동일성으로 checking 비회귀와 분리하며 전체 Mobility 정확도 승인은 하지 않는다.
9. `test_full[car-CAR-02]` — CAR-02: 옛미터8000 대 현재미터8100(신고 심야기본금액5800+추가거리2280 반올림), 예산여유3000 →11100. 여유만의 차이가 아니다.
10. `test_full[car-CAR-03]` — CAR-03: 중형은 전체거리1900+저속225초800+기본4800=미터7500; 여유2800→10300. 옛시간/거리 상호병산6800은 현재 중형 동시병산 계약과 다르다.
11. `test_full[car-CAR-03b]` — CAR-03b: 전체거리1900+저속391초1400+기본4800=8100; 여유3000→11100. 휴일과 토요일 구분도 유지된다.
12. `test_full[car-CAR-04]` — CAR-04: 신고 심야기본6700+(거리1900+저속229초800)*1.4=10480→10500; 여유3900→14400. 옛9500은 중형 동시병산/신고기본값 전 기대다.
13. `test_full[car-CAR-05]` — CAR-05: 미터6700은 그대로; 여유2500→9200. class100%/grade추정/저속0은 원단언과 같다.
14. `test_full[car-CAR-07]` — CAR-07: 현재 중점 조각 배정의 저속924초, 전체거리1900+시간3100+기본4800=9800; 여유3700→13500. 옛미터7900은 조각배정/병산 전 기대다. default25.8%/grade추정은 유지된다.
15. `test_full[car-CAR-11]` — CAR-11: 택시 대안 안쪽 car 객체 미터6700/여유2500/합9200, 저속0. 옛대안 fare_won6700은 예산여유 전 미터 기대다.
16. `test_full_only_blocked_stations_is_no_service` — 역이 막혀도 현재320→2412 버스 대안이 성립한다. subway_bus 접두만 허용하는 옛 단언이 버스→버스를 거부한다. 실제 uses두개와 금지 호선 부재를 별도 검증했다.

추가 probe는 택시6건의 독립 금액 산식, 현재 N타워 earliest, 지하철만의 첫차 조건8건과 시계 고정 전체 출력/현재 버스 대안/이유 봉투4건을 확인했습니다. CAR-11은 응답의 taxi.car 안쪽 meter6700/reserve2500/fare9200을 확인했습니다. Mobility 제품 Python52/52, 시험/픽스처163/163, 공개 입력61/61 = 각각 **100%** 기존 검토 사본과 바이트가 같습니다.

이번에는 전체층도 실제로 두 번 실행했습니다. `pytest tests/unit/travel/mobility -m "mobility_full and not live"`: 기준180/216 = **83.33%** 통과·36실패, 후보180/216 = **83.33%** 통과·36실패, 양쪽 error/skip0입니다. node id별 결과216/216 = **100%** 일치·새 실패0이며 기준 실패36개는 이전 분류와 정확히 같습니다(정밀 시간표18·벽시계2·이번16). 이는 query 후보의 비회귀 근거이며 기존 Mobility 정확도·golden 수락의 완료 선언이 아닙니다. [전체층 대조](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/mobility-baseline-candidate.json)·[16건 원인](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/linux16-assessment.json).

## 실제 EKS 기준 측정과 실패

기존 main/CD40754585676 artifact의 SHA와 앱4/4 = **100%** ready/digest, 공개 GET2/2 = **100%** HTTP200을 새로 확인했습니다. API/worker digest도 같습니다. 이는 **기존 운영판**의 근거이며 후보가 배포됐다는 뜻이 아닙니다.

처음 동일6항목 대조3/3 = **100%**가 review까지 도달했습니다(86.47·58.93·27.31초). 그러나 cap6 밖의 조회 생략을 다루지 못하므로 최적화 대표 측정으로 사용하지 않았습니다. 그 결과도 보존했습니다. 이어 같은 날짜/문자열의 7일42항목 합성 입력을3회 순차 실행했습니다. 원문/스크립트 해시는 [프로토콜](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/eks42-protocol.json)에 있고, 실제 model/provider/cache/부하는 통제하지 않았습니다.

| 회차 | 최종 상태 | 접수→GET 초 | 관측 checking→review 초 | 최대 SSE 간격 초 |
|---|---|---:|---:|---:|
| 1 | review | 143.16 | 103.16 | 3.03 |
| 2 | review | 162.79 | 84.92 | 3.13 |
| 3 | fatal | 140.30 | 미관측 | 3.49 |

3회차는 checking 시작·일정 이벤트를 관측하지 못하고 fatal로 끝났습니다. 원 측정기는 `fatal.code`를 수집하지 않아 그 건의 세부 코드·원인을 확인할 수 없습니다. checking SQL이나 모델을 원인으로 확정하지 않습니다. 최종 HTTP200/result 이벤트 자체를 업무 성공으로 세지 않았습니다. 주기 신호는 유지됐으며7초 초과 간격은3회 모두0입니다.

추가1회는 성공률 분모3에서 빼거나 실패를 덮는 재시도가 아니라 별도 진단입니다. 같은 합성 입력에 대해 오류 코드·항목 수·위험 상태 개수만 추가 수집했습니다. 결과: `{"first_at": {"accepted": 14.57, "progress": 17.35, "beat": 17.66, "stage:fatal": 138.2, "result": 139.24}, "total_to_get_s": 142.86, "status": "fatal", "fatal_code": "reading_model_failed", "fatal_detail_class": "model_unavailable", "assembled_items_n": null, "review_items_n": 0, "risk_status_counts": {}, "risk_code_counts": {}}`. 이 결과로 원래 실패의 원인이 소급 확정되지는 않습니다. [원래3회](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/eks42-before.json)·[별도 진단](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/eks42-diagnostic.json).

측정기 기존 `items_n=0`은 없는 최상위 items 칸을 센 계측 오류이며 빈 일정 증거가 아닙니다. 실제 계약은 check.items(정수)와 review.items입니다. 추가 진단에서 이 칸을 올바르게 수집했고 원 자료를 덮지 않았습니다. 시간·SSE 상태 측정과 이 계측 한계를 구분합니다.

## HOLD와 보존

운영 기준 실패의 원인/영향 판정과 수락을 확보하기 전에는 현재 초안을 병합하지 않습니다. **AMD64 검증 부족은 해소됐지만 운영 실패 경계와 후보 EKS 후측정은 미완료**입니다. 로컬 SQL 절감·CI 성공으로 이를 대신하지 않습니다. 직접 pod CPU/RSS/throttling·RDS waits/provider 호출 수와 cold/warm 통제는 미확보입니다. 후보 전후 성능·인과 개선을 주장하지 않습니다.

생성한 운영 자료는 별도 합성 guest 접수7건(6항목 대조3+42항목 기준3+진단1)입니다. 등록/confirm·여행 변경·알림/업체 거래·삭제·실패 주입0입니다. 쿠키·CSRF·키·고객 본문·업무 DB 덤프를 저장하지 않았고 공유 증거에는 해시 접수 핸들도 제외했습니다. 모델/provider 비용과 실제 호출 횟수는 확인하지 못했습니다. 합성 접수는 기존 보존 정책에 남기고 지우지 않았습니다.

모든 사본·PG자료·초기 실패·원본 XML/CI 로그·진단 스크립트는 `C:/_proj/ekscheckingcontinue1029`에 보존합니다. 공유 증거는 허용한 집계 JSON만 복사하고 manifest를 만들었습니다. 기존 보고서는 수정하지 않았습니다. 현재 main/CD 배포 예약은 HOLD로 해제하며 다른 작업자의 사본·PG·서비스를 변경하지 않았습니다. [다음 작업 인계](../../handoff/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal.md).

최종 문서 검증: 새 보고서의 상대 링크/JSON 검사와 기존 추적 텍스트 보안검사12/12 = **100%**를 확인했습니다. 마지막 기존 운영 HTTP2/2 = **100%**는200이지만 모델 읽기 성공을 뜻하지 않습니다. 공유 증거에서 해시 접수 핸들도 제외했습니다. [최종 검사](../evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/final-checks.json).
