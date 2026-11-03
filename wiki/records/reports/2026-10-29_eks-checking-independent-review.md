---
type: report
title: EKS checking 최적화 독립 검토 — 정책·실PG·Linux16·운영 HOLD
status: draft
domain: travel
---

# EKS checking 최적화 독립 검토

2026-10-29 KST. **격리 후보에서 새 의미 회귀는 발견하지 않았으나 통합·push·배포는 HOLD입니다.** 실제 PostgreSQL 전체 출력/진행 이벤트 14/14 = 100% 일치, Windows/Linux 관련 각각51/51 = 100%, 필수 관문3/3 = 100%(DoD26/26·계약368/368·보안125/125), 아키텍처170/170 = 100%입니다. 잔여 Linux 실패는16/16 = 100% 재현했고 수락·해결0/16 = 0%입니다. 후보 AMD64 이미지·동일 업무 EKS 전후·pod/RDS 지표 검증은 미완료이며 전체 운영 검증 분모는 모릅니다.

대상은 [기존 보고서](2026-10-29_eks-linux37-and-checking-duplication.md)와 [인계](../../handoff/2026-10-29_eks-linux37-and-checking-duplication.md)의 SQL 후보입니다. 이번 세션은 구현자와 별개인 독립 검토입니다. 제품 전체/운영 승인을 뜻하지 않습니다. root와 cs AGENTS/RULE, wiki 목차·개발 역할·Mobility·web-intakes, 실제 coord notice를 읽었습니다. 소유는 새 no-hardlinks 사본 `C:/_proj/ekscheckreview1029`, 새 전용 PG16.15(loopback63905), 새 보고·증거·인계와 백업 후 목차 링크뿐입니다. 기존 담당의 사본/PG/프로세스는 변경하지 않았고 main/CD 예약을 잡지 않았습니다. 최신 main과 사본 기준은 모두 `57f3d2f004d0600f781599a6a92e8691b49bef82`입니다. 기존 후보 패치만 새 사본에 적용했습니다.

## 정책·오류·상한·순서 판정

`risks.decorate`의 두 단계(단일 준비 스레드의 DB 읽기 → 첫 위험 점검 후 나머지 기존 병렬 실행)는 그대로입니다. 후보는 과거 일정과 점검 상한 밖 일정의 `_sensitivity` SELECT만 생략합니다. `Item.place`는 같은 dict를 보유하므로 선택된 일정의 민감도 보강은 실제 judge 전에 반영됩니다. 직접 `to_item()` 호출은 기본 `resolve_sensitivity=True`로 유지됩니다. cap은 공통 guardrail의6이며 값·세는 순서·재사용 결과의 cap 소비·입력 순서·이벤트 순서를 바꾸지 않았습니다. 입력 객체도 불변입니다. `mobility`, 날짜 없음, 끝 시각이 now와 같은 일정, 장소 없음, 고정/예약 표시도 비교했습니다.

원래 `_sensitivity` SQL과 savepoint/예외 처리, `risk_report`·공유 캐시·알림·동의·저장 경로는 바뀌지 않습니다. 실제 PG SELECT에 division-by-zero를 발생시킨 비교에서도 savepoint가 회복되고 민감도는 None으로 남습니다. None은 실내로 간주하지 않으며 실제 점검기가 필요한 날씨 검사를 하게 하는 값입니다. 주입한 위험 timeout은 fresh/cached 모두 `unknown/check_error`로 남았고 상한 밖은 `unknown/item_limit`, 과거는 `not_applicable/past`입니다. 실패를 clear로 바꾸거나 전역 실패 캐시를 추가하지 않았습니다. [전체 출력·이벤트/실SQL 증거](../evidence/2026-10-29_eks-checking-independent-review/pg-review.json).

fresh 호출 사이 DB 분류를 야외→실내→야외로 갱신했을 때 양쪽 모두 새 값을 반영했습니다. 새 교차요청 캐시는 없습니다. 다만 **기존 정책상 앞 판 fresh 위험은 서명 일치·600초 이내면 DB가 바뀌어도 재사용**하며, 그 결과와 원래 checked_at을 보존합니다. 601초 지난 판은 재점검합니다. 명시된 boolean 민감도도 기존처럼 DB보다 우선합니다. 이번 후보가 이 기존 자료 노후화 조건을 해결했다는 주장은 하지 않습니다. 원자료 hours 전체 캐시는 도입하지 않았습니다. 방문 시각·원장 판정·14일 재사용·DB 갱신 우선순위를 별도 설계 없이 합치면 의미가 달라질 수 있습니다.

## 실제 PG 재현과 전후 측정

전용 DB에 migration, 표준 register_prompts/seed_travel을 실행했습니다. 원시42행 위험 단계는84→12 SELECT로72/84 = 85.71% 감소합니다. 실제 조립 `review.build`의42활동·35이동은 build127 SELECT, 위험42→6 SELECT, 합계169→133으로36/169 = 21.30% 감소를 재현했습니다. build 출력 전체도 같습니다. 이 조립 시험은 이동 엔진을 명시적으로 끄고 위험 callable을 합성으로 사용합니다. API/prefill/answers/LLM/실제 provider 전체 경로가 아닙니다.

순서 편향을 줄이기 위해 같은 연결·동일42행에 baseline→candidate와 candidate→baseline을 번갈아 실행했습니다. 2쌍 warm-up을 제외한20/20 = 100% 쌍의 전체 출력/이벤트 해시가 같습니다. 로컬 위험 단계 중앙값은 **15.57815→5.09840ms**입니다. SQL·입력 생성·합성 judge를 포함한 이 한 프로세스의 측정이며, cold/RSS/네트워크·운영 부하를 통제한 EKS 개선율이 아닙니다. 원시20쌍과 양쪽 시간/SELECT/해시를 보존했습니다.

실제 `risks → DisruptionCheck → DisasterMsgApi → DbResponseCache → PostgreSQL`도 다시 실행했습니다. 합성 transport 성공/timeout × 명시 민감도 유무4/4 = 100%에서 성공 전송1회, 실패 전송6회, 상한6·뒤2개 item_limit·DB cache error0을 재현했습니다. 실패 재조회 증폭이 가능한 코드 경로이며 **실제 EKS에서6번 timeout했다는 증거는 아닙니다**. 공통 캐시는 성공만 저장합니다. 기존 ITS operation snapshot은 이미 있으므로 새 최적화로 세지 않았습니다.

## Linux16과 회귀

| 독립 실행 | 결과 |
|---|---:|
| 같은 추가 회귀의 원래 decorate → 후보 | 1실패1통과 → 2/2 = 100% 통과 |
| Windows 관련 | 51/51 = 100%, skip0 |
| Linux ARM64 관련 | 51/51 = 100%, skip0 |
| DoD · 계약 · 보안 | 26/26 · 368/368 · 125/125 = 각각100% |
| 아키텍처 | 170/170 = 100% |
| ruff F/E9 · diff --check · 패치 reverse --check | 모두 exit0 |
| 잔여 Linux16 | 통과0/16 = 0%, 실패16/16 = 100%, skip0 |

잔여16건은 택시7·plan golden2·경로/스키마7입니다. 택시는 현재 meter와 planning reserve를 구분해야 하며,7건 모두 reserve 하나로 설명되지 않습니다. N타워 경로와 첫차·혼합/버스 대안 선택은 실제 도메인 수락이 남습니다. `left_out` 추가 칸은 이유 dict의 정확한 키 집합을 요구하는 옛 단언과 충돌합니다. golden은 경로/시각/출발 context 차이를 포함하므로 기록시각만 제거해 통과시키지 않았습니다. 기존 단언·golden을 수정하거나 자동 면제하지 않았습니다. [16건 실제 실패 메시지](../evidence/2026-10-29_eks-checking-independent-review/remaining16-results.json)·[Linux XML](../evidence/2026-10-29_eks-checking-independent-review/linux-remaining16.xml).

Mobility 시험/픽스처 파일은 163/163 = 100%, 제품 mobility Python 52/52 = 100%가 기존 사본과 바이트 일치합니다. 공개 입력61/61 = 100% 해시 확인했습니다. 따라서 이 후보에 의해16건이 새로 생겼다고 보지 않습니다. 다만 전체 Linux mobility216층이나 제품 전체 테스트를 이번에 다시 통과시켰다는 뜻은 아닙니다. Linux는 Python3.12.16·aarch64 WSL이며 AMD64 배포 이미지와 다릅니다.

준비 실패도 보존했습니다. 첫 PG55783은 Windows bind permission denied로 시작하지 못했고63905로 바꿨습니다. 첫 계약은 빈 DB의 활성 프롬프트10개 누락으로358/368 = 97.28% 통과·10실패였습니다. 표준 등록/여행 seed 후 같은 전체 계약은368/368 = 100%입니다. 첫 PG 비교 스크립트는 응답의 advisories가 cautions로 변환되는 것을 잘못 읽어 freshness 단언이 실패했습니다. 올바른 공개 필드로 고친 재실행만14조건/20쌍 통과로 셌습니다. 원문 실패를 제품 회귀나 통과로 바꾸지 않았습니다.

## 실제 EKS 근거와 배포 위험

읽기 전용 GitHub API/새 CD artifact 다운로드로 현재 main SHA와 CD40754585676 성공을 다시 확인했습니다. artifact의4/4 = 100% 앱 ready, API/worker digest 일치, SHA 일치이며, 공개 `/health`·`/` GET2/2 = 100% HTTP200(health ok)입니다. artifact 생성 시각은2026-10-28T19:38:07Z, 독립 조회는2026-10-28T21:32:00Z입니다. [읽기 검증](../evidence/2026-10-29_eks-checking-independent-review/eks-readonly-summary.json)·[실제 CD 실행](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40754585676).

이는 **기존 배포의 CD/readiness와 공개 가용성 근거**입니다. checking 후보를 EKS에 반영한 근거는 없습니다. 현재 배포 코드는 linux/amd64를 빌드하지만 이번 후보의 동일 이미지 실행은 안 했습니다. native aws/kubectl은 PATH에서 찾지 못했으며 권한이 없다고 단정하거나 권한을 확장하지 않았습니다. 직접 pod throttling·CPU/RSS·RDS waits·provider 횟수·cold/warm·동일 업무의 후보 전후는 미확보입니다. 로컬 SQL 감소와 별개로 실서비스 병목·인과 개선·전체 응답/진행 의미는 승인하지 않습니다.

**최종 HOLD 조건:** 잔여16건의 도메인/계약 판정, 최신 main 위 후보 AMD64/배포 이미지 검증, 동시 담당과 통합/CD 예약, 동일 업무·조건을 기록한 EKS 전후와 운영 실패 경계 검증이 남습니다. 후보는 읽기만 줄이는 내부 변경이고 DB migration/캐시정책 변경은 없지만, 그 사실만으로 운영 관문을 면제하지 않습니다. 이번 제품 통합·push·배포·운영 데이터 쓰기·실모델/provider 호출은0입니다. 자체 PG63905는 종료 후 연결거부를 확인했고 기존 서비스는 정지하지 않았습니다. 모든 사본/PG자료/준비 실패는 보존하며 수동 삭제하지 않았습니다.

[독립 최종 집계](../evidence/2026-10-29_eks-checking-independent-review/summary.json)·[증거 manifest](../evidence/2026-10-29_eks-checking-independent-review/manifest.json)·[인계](../../handoff/2026-10-29_eks-checking-independent-review.md).
