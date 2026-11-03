---
type: report
title: EKS Linux 37건 기준선 대조와 checking DB·네트워크 중복
status: draft
domain: travel
---

# EKS Linux 37건 기준선 대조와 checking 중복

2026-10-29 KST. **기존37건 전부를 깨끗한 main에서 대조했습니다. 자료 부재1건은 같은 단언으로 통과했고36건은 기준선에서도 실패합니다. checking SQL 절감 후보는 격리 검증만 완료했으며 통합·push·배포0입니다.** 기각된 반경/해독 후보는 가져오지 않았고 시험·골든·가드레일을 줄이지 않았습니다. [최종 집계](../evidence/2026-10-29_eks-linux37-and-checking-duplication/final-summary.json)·[37개별 판정](../evidence/2026-10-29_eks-linux37-and-checking-duplication/classification.json)·[재현 안내](../evidence/2026-10-29_eks-linux37-and-checking-duplication/README.md).

담당은 이 Codex 세션입니다. 독립 검토자 미지정이며 자체 검증을 독립 승인으로 부르지 않습니다. root/subproject AGENTS·CLAUDE·RULE, wiki 목차/개발 책임/Mobility·web-intakes 계약, 데이터 README/REPORT와 실제 `_coord` notice를 확인했습니다. 자체 경계는 `C:/_proj/ekscheck1029`와 새 보고/증거/인계 및 백업 후 목차 링크입니다. 기존 작업자 사본·서비스·원본 제품 코드/색인/설정은 변경하지 않았습니다. 원본 Git 조회는 safe_git.py를 사용했습니다. 새 no-hardlinks clone 및 최종 팀 main 조회는 모두 `57f3d2f004d0600f781599a6a92e8691b49bef82`입니다.

## 37건 대조와 분류

새 사본은 반경 변경이 없는 원래 코드입니다. 기존 node id·단언을 그대로37/37 = 100% 실행해 **통과1/37 = 2.70%, 실패36/37 = 97.30%, skip0**입니다. [기준 XML](../evidence/2026-10-29_eks-linux37-and-checking-duplication/baseline37.xml). 원래216 전체층의179통과37실패 기록을 소급 수정하지 않았고 이번에216 전체층을 재실행했다고 하지 않습니다. 기존 mobility 시험/픽스처162/162 = 100%, 원본 공개 입력61/61 = 100% 해시 불변입니다.

| 분류 | 건수 / 37 | 근거·남은 판정 |
|---|---:|---|
| 환경: 사본 공개 graph 입력 누락 | 1/37 = 2.70% | 기존에 있던 공개61파일을 해시 검증해 새 사본에만 공급. passenger-car 예외 시험 통과. 새 규칙/데이터 생성 아님 |
| 기준선: 정밀 시간표와 옛 기대값 불일치 | 18/37 = 48.65% | 공식 열차 도착초 보강만 끈 진단에서18/18 = 100% 통과. precision 제품 기능은 보존. 단순 Linux 오차나 반경 회귀로 분류하지 않음 |
| 기준선: 택시 산식·계획 예산 기대 불일치, 수락 남음 | 7/37 = 18.92% | 실제 같은7건 재생. CAR-05/11의 옛 기대는 현재 meter와 같으나 fare는 예산 여유 포함. 나머지5건은 meter도 다름. 전부 여유 금액 하나로 설명하지 않음 |
| 기준선: 동시성 시험의 기록 시각 비결정성 | 2/37 = 5.41% | captured_at만 고정해 끼어들기/8스레드 총80건 시험2/2 = 100% 통과. 기존 음성 대조·순차 기준·싱글턴 보존 단언 그대로. canonical 실패는 그대로 보존 |
| 기준선: plan golden 불일치, 원인/수락 남음 | 2/37 = 5.41% | 시각/경로 및 추가 departure context 차이. 새 golden 생성·덮어쓰기 안 함 |
| 기준선: 경로/스키마 기대 불일치, 수락 남음 | 7/37 = 18.92% | ntower의 현재 성립 경로, 첫차/버스→버스 선택, left_out 추가 칸 등. 현재 경로 기대의 도메인 판정이 필요하며 자동 면제하지 않음 |

[정밀표 진단](../evidence/2026-10-29_eks-linux37-and-checking-duplication/precision-ablation.xml)·[시각 진단](../evidence/2026-10-29_eks-linux37-and-checking-duplication/clock-diagnostic.xml)·[80건 진단](../evidence/2026-10-29_eks-linux37-and-checking-duplication/clock-threads.xml)·[택시 실제 분해](../evidence/2026-10-29_eks-linux37-and-checking-duplication/taxi-diagnostic-v3.json). 시각 진단의 earliest plan 시험은 경로가 실제 성립하여 여전히 실패했습니다(동시성 끼어들기와 구분). 전체37건의 baseline 대조를 끝낸 것이지36건을 수정·종결한 것이 아닙니다. 택시7·golden2·경로/스키마7인16/37 = 43.24%는 계약/도메인 수락 또는 추가 원인 검토를 남깁니다. 정밀표·시계 진단의 통과를 운영 기능 수정이나 canonical 통과율로 합산하지 않습니다.

## checking의 실제 호출과 가장 큰 관측 중복

main의 `pipeline.process`에서 checking→review는 최초 `review.ensure(force=True)`와 위험 decorate, 날짜/질문 조회, prefill, 해석 답 반영을 포함합니다. 기존 위험 병렬화와 ITS operation snapshot은 이미 있습니다. 기존6회 SSE 구간의181.60/319.43초 = 56.85%는 그 구간 합계이며 DB/CPU/provider별 기여율이 아닙니다. 이번에도 운영 로그/접수를 새로 만들지 않았습니다.

전용 PostgreSQL16·loopback55773·합성 여행 DB에 실제 조립된 `review.build`를 연결했습니다. 7일·하루6개, 총42활동·35이동을 만들었습니다. SQL은 실제 execute에서 세며 bind 값은 기록하지 않습니다. 이동 엔진은 이 SQL 분리 시험에서 명시적으로 끄고 위험 callable은 합성이므로 시간표/API/prefill/answers 전체 경로 검증으로 읽지 않습니다.

| 실측 범위 | 실제 SQL |
|---|---:|
| 최초 build 운영시간·고정 이웃 조회 | 127 |
| 그 안 관광공사 hours 조회 | 42 |
| 그 안 다른 여행의 최근 hours 재사용 조회 | 42 |
| 그 안 활동 원장 조회(방문 시각별 판정) | 42 |
| 그 안 reopen 조회 | 1 |
| 같은 실제 build 출력의 위험 점검, 기준 → 후보 | 42 → 6 |

[실제 SQL 집계](../evidence/2026-10-29_eks-linux37-and-checking-duplication/build-inventory-v3.json). 따라서 이 표본에서 가장 큰 반복 원자료 조회는 **시간 정보 두 조회84회**입니다. 같은6개 content_id를7일에 반복하며 최대72회의 재조회 후보가 있지만, 이를 제거했다고 하지 않습니다. 날짜별 원장 판정42회는 같은 SQL 모양이어도 인자가 달라 그대로 중복이라고 보지 않습니다. 시간 facts 전체를 캐시하면 방문 시각·휴무·원장 판정·동시 갱신 의미가 바뀔 수 있어 통째로 캐시하지 않았습니다. 그 다음 위험 단계의 상한 밖 조회는 의미를 바꾸지 않고 제거 가능한 것으로 검증했습니다. 전체 관측 SQL169→133은36/169 = 21.30% 감소이며 **실제 EKS 시간 개선율이 아닙니다**.

네트워크는 실제 `risks.decorate → DisruptionCheck → DisasterMsgApi → DbResponseCache → PostgreSQL`을 연결하고 HTTP transport만 성공/timeout 합성으로 바꿨습니다. 8개 일정, 실제 점검 상한6을 유지한4/4 = 100% 시나리오에서 같은 원문 성공은 전송1회·DB cache read1회, 실패는 전송6회·cache miss read6회·예산/실패 각6회였습니다. 모름과 item_limit을 그대로 보존했습니다. [계수와 결과](../evidence/2026-10-29_eks-linux37-and-checking-duplication/offline-checking.json). 이는 **실패 재조회 증폭이 가능한 경로**라는 증거이며 실제 EKS에서 그 소스가6번 timeout했다는 증거는 아닙니다. 공통 캐시는 성공만 저장하는 계약이므로 실패를 전역 캐시에 넣거나 오류를 clear로 바꾸지 않았습니다. ITS에 이미 있는 요청 범위 재사용을 새 기능처럼 다시 제안하지 않습니다.

## 격리 SQL 후보와 검증

`decorate`는 시각을 파싱한 뒤 과거·점검 상한·재사용 여부를 먼저 정하고, 실제 judge 대상만 `_sensitivity`로 보강합니다. `to_item` 직접 호출의 기본 동작은 유지합니다. DB 읽기는 기존 단일 준비 스레드에 남으며 외부 점검만 기존 병렬 정책을 씁니다. 공개 응답·위험 한도·순서·오류·알림·동의 경계는 바꾸지 않습니다. [후보+새 시험 패치](../evidence/2026-10-29_eks-linux37-and-checking-duplication/candidate-complete-v2.patch)·[AST 감사](../evidence/2026-10-29_eks-linux37-and-checking-duplication/candidate-audit.json). 10함수 중2개만 변경, 나머지8개 및 `_sensitivity` SQL/오류 동작은 불변입니다.

직접42행을 넣는 별도 시험은84→12 SQL, 실제 build 출력은42→6 SQL로 줄었습니다. 차이는 build가 낸 place 칸 모양 때문이며84를 실제 build의 분모로 사용하지 않습니다. 원시8조건·실내/야외/모름 DB 자료8조건·실제 build1조건 각각 전체 출력/진행 이벤트가 동일했습니다. [원시 비교](../evidence/2026-10-29_eks-linux37-and-checking-duplication/query-equivalence.json)·[DB 분류를 결과에 반영한 비교](../evidence/2026-10-29_eks-linux37-and-checking-duplication/query-equivalence-sensitive.json).

| 검증 | 실제 결과 |
|---|---:|
| 같은 새 회귀 바이트 기준 → 후보 | 1실패1통과 → 2/2 = 100% |
| Windows 후보 관련 | 59/59 = 100%, skip0 |
| Linux ARM64 후보 관련 | 51/51 = 100%, skip0 |
| 별도 최초 관련/정밀 시간표 시험 | 76/76 = 100% |
| 필수 관문 | 3/3 = 100%: DoD26/26·계약368/368·보안125/125 |
| 아키텍처 | 170/170 = 100% |
| ruff F/E9·diff --check·최종 패치 reverse --check | 모두 exit0 |

첫 whole-build 스크립트는 composition을 안 묶어 실패했고 실제 조립 후 재실행했습니다. 택시 진단은 첫 경로 준비 실패와 dataclass를 안 펼친 빈 추출을 보존하고 v3에서7건의 실제 값을 얻었습니다. 첫 통합 패치는 줄바꿈 처리 때문에 reverse-check 실패했으며 바이트를 보존한v2는 exit0입니다. 준비 오류를 제품 결함이나 통과로 세지 않습니다. 원문/자체 PG/모든 시도는 `C:/_proj/ekscheck1029`에 남겼습니다. 원본/다른 작업자/기존 보고서 덮어쓰기·파일 삭제0, 자체PG55773 정상 종료입니다.

## 남은 경계와 인계

운영 통합 HOLD입니다. 독립 검토 승인은 없으며 EKS pod throttling/RDS wait·실제 provider 빈도·배포 AMD64 이미지·cold/warm/RSS·같은 업무의 EKS 속도는 측정하지 않았습니다. 전체 운영 검증 분모는 모릅니다. 가장 큰 raw-hours 중복의 안전한 요청 범위 재사용/일괄 조회와 실패 provider 요청의 계약을 별도 검토하고,16건의 남은 기대값 수락을 진행해야 합니다. 그 뒤에 최신 main·배포 이미지·동일 업무 검증을 통과하기 전에는 이 작은 SQL 후보도 배포하지 않습니다. [인계](../../handoff/2026-10-29_eks-linux37-and-checking-duplication.md)·[manifest](../evidence/2026-10-29_eks-linux37-and-checking-duplication/manifest.json).
