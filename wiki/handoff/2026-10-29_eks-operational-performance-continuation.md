# EKS 성능 후속 인계 — 2026-10-29

한 일: x600 장부·API 버전·버스 소스 hash 읽기 확인(최종006268853c, scalar 보존), EKS 공개 GET8/8=100%와 최신 성공 CD artifact 확인, 최신 main/role-manager 전용34/15커밋 비교, main20c296e77 격리 사본에 scalar1표현식 통합, CD 실패시간·복구시간 및 network reason 유형 기록 후보 구현, 격리 PG55739 회귀·종료·증거 보존. NOTICE로 ST4F597 예약·완료와 파일 경계를 확인했습니다. 다른 작업자의 회신은 없습니다.

결과: main scalar 전후34/34, 의미32,939/32,939, ride_estimator·cache 각각1,152/1,152, 배포79/79, contract368/368, security125/125, DoD26/26(필수3/3=100%). Mobility1,481/1,607=92.16%(자료skip126,제외222). 초기 PATH WinError5 및 실패·보류 후보를 보존했습니다. 추가 계산 후보2개는 개선 미확인/경고 차이로 채택하지 않았습니다.

변경 묶음: `C:/_proj/eksperf1029/repo`의 bus_profile.py scalar1표현식·deploy/aws_cd.py 진단·tests/unit/deploy/test_aws_cd.py 새회귀3개. 보고서 evidence의 main-scalar.patch와 cd-diagnostics.patch는 분리했습니다. 원본 제품 변경·커밋·push·배포0, 자체PG55739 종료·연결거부 확인. 파일·PGdata·실패로그·fixture·사본은 보존합니다.

남은 일: 최신 main 재대조, Linux/amd64 기존 런타임·자료hash 비교, 승인된 읽기 EKS/CloudWatch 접근으로 단계 로그·RDS 연결비용·CPU 관측, 동일 조건 격리 접수 전후 성능, 실제 릴리스 관문. EKS 전체 접수속도 개선·새 독립 리뷰·운영 인수는 미완료(분모 모름). 진단133→3+130초는 가짜 시계로 기록 귀속 오류를 고친 결과이며 운영 단축이 아닙니다.

재확인: GitHub CD run40699378486 artifact는 역사적 배포 증거입니다. 공개 도메인 EKS `guguroute.devroro.click`과 x600 `tripilot.devroro.click`을 구분하고 식별 User-Agent로 GET만 수행합니다. live imageID는 읽기 EKS 권한을 얻은 뒤 확인합니다. 기존 `aws_cd.py deploy`/workflow_dispatch는 배포를 실행하므로 증거 조회용으로 호출하지 않습니다.

[보고서·명령·전제조건·보안·보존 위치](../records/reports/2026-10-29_eks-operational-performance-continuation.md).
