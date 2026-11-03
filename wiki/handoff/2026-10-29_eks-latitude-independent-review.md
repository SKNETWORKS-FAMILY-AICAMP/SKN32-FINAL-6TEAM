---
type: handoff
title: EKS 위도 가지치기 독립 검토 인계
status: draft
domain: travel
---

# EKS 위도 가지치기 독립 검토 인계

2026-10-29 05:30 KST. **로컬 실익 확인, 운영 배포 HOLD입니다.** [보고서](../records/reports/2026-10-29_eks-latitude-independent-review.md)와 [정확한 근거](../records/evidence/2026-10-29_eks-latitude-independent-review/review-summary.json)를 먼저 읽습니다.

한 일 목록:

- 루트·CS 지침, 현재 wiki/Mobility 계약, 원 후보·인계 및 실제 scratch `_coord` notice를 확인했습니다. 원 후보 작성 세션과 별도 검토입니다.
- 원격 main `57f3d2f004d0600f781599a6a92e8691b49bef82` 재조회, 새 독립 clone에 원 패치 적용, 기존 원본 코드·Git 설정·다른 작업 보존했습니다.
- 위도 하한 증명·포함 경계·동일 거리 객체 순서·유한 극단 입력78/78 및 실제 정류장240/240 = 100% 동등성을 확인했습니다. 새 pytest 회귀2/2 = 100%입니다.
- 실제 자료25/25 = 100% 해시 재검산, 작성자 프로토콜을 독립 재실행했습니다. 경로12/12 = 100% 일치, 로컬 중앙값0.499→0.416초(16.63% 감소)입니다. EKS 전체시간 개선으로 일반화하지 않습니다.
- 밀도 합성에서 넓은 반경은 31.24% 느려졌습니다. 전 입력 성능 보장이 아니며 새 임계값을 추가하지 않았습니다.
- 기본 이동1,486/1,612 = 92.18%(skip126·별도 제외222), 아키텍처170/170 = 100%를 실행했습니다. canonical 전체층은 8/216 = 3.70% 실행(통과7·실패1·미실행208), 해당 실패는 HEAD에서도 재현했습니다.
- 초기 격리 DB 준비 실패를 보존하고 전용 PostgreSQL16.15에 main CI와 같은 migrate/register_prompts/seed_travel 후 필수3/3 = 100%(DoD26·계약368·보안125)를 통과시켰습니다. 이 DB 서버는 정상 종료했고 자료는 남겼습니다.
- 보고·증거·이 인계만 원본 wiki에 추가했습니다. 고객/provider 조회·유료 호출·push·배포·원본 자료 삭제는 0입니다.

이어 할 일:

1. canonical 전체층 `ntower_namdae` 실패를 별도 결함으로 검토하고 non-live 나머지208건을 실행합니다. 전역 `ACOP_MOBILITY_DATA_DIR`를 켠 진단 실패는 원인 미확정이며 통과로 취급하지 않습니다. live6은 사용자의 별도 실호출 범위가 없으므로 실행하지 않았습니다.
2. Linux/amd64·배포 NumPy에서 거리/순서 동등성, 입력 밀도·cold/warm·메모리를 확인합니다. 기존의 평면 거리 근사 정확도를 이번 변경의 성과로 주장하지 않습니다.
3. 동일 업무·자료·부하 전후 EKS stage/prefill, CPU/throttling, RDS 대기/timeout을 측정한 뒤 출시를 판단합니다. 현재 운영 측정0이며 운영 검증 전체 분모는 모릅니다.

작업 사본은 `C:/_proj/ekslat-review1029/localrepo`입니다. 중단한 최초 clone `C:/_proj/ekslat-review1029/repo`, 비정규 실행 로그·실패 XML·PG 자료·모든 스크립트도 보존했습니다. 삭제 승인이 없으므로 정리하지 않습니다. 원 후보 사본 `C:/_proj/eksdeep1029/repo`는 수정하지 않았습니다. 이 검토는 통합 예약·배포 승인·원격 변경을 만들지 않았습니다.
