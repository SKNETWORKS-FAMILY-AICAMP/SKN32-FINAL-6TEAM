# 2026-10-18 AWS 서비스 도메인 연결·HTTPS 준비

## 확인·적용 범위

- 사용자 지정 서비스 도메인은 Cloudflare 프록시 DNS 응답을 반환한다. 로컬 HTTP 실제 응답은 200이며 HTTPS는 522였다. AWS 내 Python 조회는 Cloudflare 403으로 별도 관측했다. HTTP 성공만으로 HTTPS 성공을 선언하지 않는다.
- 서울 리전 ACM 인증서 요청 1건을 생성했다. 현재 DNS 검증 대기다. AWS 계정의 Route53 호스팅 영역 조회 결과는 빈 목록이며 Cloudflare 관리 화면은 로그인 화면이다.
- 현재 EKS 런타임 설정을 비공개 작업 경로에 백업하고 사용자 도메인의 HTTP·HTTPS 출처를 허용 목록에 추가했다. API·작업 처리 Deployment 두 개 모두 rollout 완료를 확인했다.
- HTTPS 미준비 상태에서 보안 쿠키·공개 링크를 강제 전환하지 않았다. 인증서 발급 후 실행하도록 개인 적용기에 상태 검사를 넣었다. 자동 예약·x600 자동 전환은 수행하지 않았다.

## 남은 일

- Cloudflare에 ACM이 제공한 인증서 검증 CNAME 1건을 DNS only로 등록해야 한다. 구체 값과 인증서 식별자는 Git 제외 개인 적용기에만 보관한다.
- 인증서 ISSUED 이후 기존 NLB의 TLS 진입·앱 공개 주소·HTTP 리디렉션을 적용하고 외부 HTTPS·API 응답을 확인한다. 적용기는 준비됐으나 최종 단계는 실행하지 않았다.
- 기존 고객 경로·알림 실제 수신·도메인 인증 이후 로그인 성공은 이번 확인 범위가 아니다. x600 자동 전환은 사용자 지시로 나중에 진행한다.


## 2026-10-18_085035_https HTTPS 실제 적용

- 사용자가 추가한 검증 CNAME이 Cloudflare 권한 DNS에서 정확한 대상과 일치했다. ACM 인증서 ISSUED를 확인한 뒤 최종 적용기를 실행했다.
- 기존 NLB에 TLS 443 리스너와 TLS 1.2/1.3 정책을 연결했다. HTTP 진입은 지정 도메인의 HTTPS로 308 이동한다.
- 프록시는 TLS용 내부 진입 포트를 따로 사용하고 전달 프로토콜을 HTTPS로 지정한다. 앱 허용 출처·로그인 복귀 주소·공개 링크 주소를 HTTPS로 전환했다.
- 내부 프록시를 통한 API health 200 및 앱 6개 모두 가용 1/1을 확인했다. 새 TLS 대상 그룹은 최초 등록 중이며 외부 HTTPS 최종 성공 확인은 이어서 진행한다.
- 변경 전 런타임·프록시 설정·Service·Deployment는 개인 작업 경로에 백업했다.


## 2026-10-18_085142_https-complete 외부 HTTPS 완료

- 공개 도메인 HTTPS 웹 화면 HTTP 200, 공개 API health HTTP 200 및 status=ok, HTTP 308 이후 HTTPS 최종 HTTP 200을 각각 확인했다. curl TLS 인증서 검증 결과는 0(정상)이며 검증 우회 옵션을 사용하지 않았다. 확인 3/3=100%.
- NLB TLS 대상 그룹 healthy 및 앱 Deployment 6개 각각 가용 1/1을 확인했다. 최초 등록 중 522·525와 AWS 내부 동일 노드의 원본 NLB 접근 ConnectionReset 관측은 보존하며 공개 경로 최종 확인과 구분한다.
- TLS 정책은 ELBSecurityPolicy-TLS13-1-2-2021-06이다. 인증서 DNS 검증 CNAME은 갱신을 위해 유지한다.
- 계정 로그인·개인 여행 변경·실제 알림 수신을 이번 HTTPS 확인으로 대신 검증했다고 주장하지 않는다.
