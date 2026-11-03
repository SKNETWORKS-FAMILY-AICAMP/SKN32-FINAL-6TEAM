---
type: report
title: GuguRoute LAN 방화벽·실브라우저 확인과 API 연결 결함
status: draft
domain: travel
---

## LAN 공유·병렬 시험 실진행

사용자요청으로동일개인LAN접속및유휴스레드병렬시험을시작했습니다. 실제Wi-Fi주소192.168.0.15/24를조회했고사용자가승인폼에서현재Wi-Fi Private전환과LAN3100/8042허용을명시선택했습니다. UAC실행exit0후정확firewallrule {cca3ee85-728e-4894-977e-1e82ed6144e7}를재조회해EnabledTrue/Allow/Private,Local192.168.0.15,Remote192.168.0.0/24,Wi-Fi,TCP3100·8042를확인했습니다. VPN/다른인터페이스/외부전체허용아닙니다. profile-before/result/rollbackrule은profile scratch guguroute-lan-firewall-result보존입니다. 실제다른기기접속은아직미확인입니다.

새child둘에LAN전용compiledAPI192.168.0.15:8042로fresh웹build·명시LANbind와실자원측정911exactnode병렬분할검증을나눠넘겼습니다. 별도API기동child에LANbind/CORS정확origin연결을전달했습니다.

부모가설치된Playwright로새격리Edgeheadless를실행해실화면4route/desktopmobile스크린샷을얻었습니다. 홈구구루트로고·서울일정안내·최근여행서버연결오류를직접확인했습니다. APIauth/me/legalretention에credentialsCORS오류및500이실제로있어기동child에정확콘솔증거를전달했습니다. 진짜API연결/e2e수락아닙니다. 브라우저증거guguroute-browser-local-final/browser-readback.json및png,private사용자브라우저세션/폼submit없습니다.

