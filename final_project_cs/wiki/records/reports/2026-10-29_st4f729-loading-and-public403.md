---
type: report
title: ST4F-729 실제 모드 로딩 잔여 결함과 공개403 구분
status: draft
domain: travel
impl_scope: cs
---

# ST4F-729 실제 모드 로딩 잔여 결함

2026-10-29T03:50:41.695570+09:00 실측. 루트·CS AGENTS/RULE·양쪽 wiki 목차·역할/코드 경로·728/729 후속 보고를 읽고 실제 `_coord` 41파일 전체를 확인·비공개 보존했습니다. ST4F-589 지정담당과 EKS/main 예약을 유지했습니다. 작업 담당·검증은 같은 Codex 세션이며 독립 검토는 아닙니다.

## 공개403과 x600

PC 기본 urllib GET /health·/v1/web/auth/providers·/는 **0/3 = 0%** HTTP200, 모두 Cloudflare403·본문 `error code: 1010`입니다. x600 기본 curl로 같은 공개 호스트 /health·providers는 **2/2 = 100%** HTTP200, Caddy 경유·상태ok/google을 확인했습니다. 서로 다른 클라이언트·환경 비교이므로 네트워크/IP 원인만으로 단정하지 않습니다. Cloudflare [공식1010 설명](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)은 클라이언트 브라우저 서명에 따른 거절을 뜻합니다. 기본 요청 외 식별값 위장·IP/Host 우회·터널·보안 설정 변경은 하지 않았습니다. 차단된 클라이언트로 고객 세션 수락은 진행하지 않았습니다.

## 미담당 high ST4F-729 선택·재현·수정

TeamFlow 상태×유형16분할 GET으로688건 중 미완료102/688 = **14.8%**, 완료586/688 = **85.2%**를 확인했습니다.729는 assignee 빈 값·high/review입니다. 최신 팀 role-manager의 AdminApp.tsx를 인증된 GitHub API로 읽어 사본과 LF바이트 일치를 확인했습니다. 별도 admin 사본은 약정한 범위만 복사하고 기존 웹 node_modules를 junction으로 참조했습니다. 원본·다른 작업자 소스는 수정하지 않았습니다.

실제 AdminApp을 Vite로 번들한 loopback 합성 화면에서 session만 합성 운영자 응답, snapshot은 지연시켰습니다. 실제 Edge에서 실제 모드 로딩에 「데모 로딩 상태」와 작동 의미가 없는 「정상 화면 보기」가 노출되는 반례를 확인했습니다. 수정은 이 한 JSX 구간에 실제 모드 「운영 자료를 불러오고 있습니다.」를 표시하고 상태전환 단추를 데모에만 표시합니다. 인증·캐시·명령·DB 계약 변경은0입니다.

동일 브라우저 검사는 수정 전 실제 모드 실패1·데모 통과1 → 수정 후 **2/2 = 100%**입니다. 합성 실제 모드·데모 화면 사진을 직접 확인했습니다. 새 Playwright 회귀 **1/1 = 100%**, 관리자 Vitest **46/46 = 100%**, tsc·수정 파일eslint exit0입니다. Next 프로덕션 서버가 아닌 실제 컴포넌트의 Vite 번들이므로 Next 전체빌드·실API·운영화면 수락과 구분합니다. Node26은 선언22~24 밖이라 지원버전CI 수락으로 주장하지 않습니다.

## 통합·보존·한계

패치는 [candidate.patch](../evidence/2026-10-29_st4f729-loading-and-public403/candidate.patch), 실행 요약은 [summary.json](../evidence/2026-10-29_st4f729-loading-and-public403/summary.json)입니다. 공유 원본의 Git 조회를 지정 safe_git으로 시도했으나 실행파일 WinError5로 실패했습니다. 새 격리 사본에서만 구현했으며 필수 backend DoD/contract/security3관문과 공통 검토를 아직 실행하지 않아 통합은HOLD입니다. 기존 게이트 결과를 이번 패치 검증으로 재사용하지 않습니다. 다음 담당자는 최신 manager와 패치 대조·필수 관문·공유 검토 후 조정NOTICE와 양원격ff 반영을 진행합니다. main/develop/EKS 예약은 유지합니다.

729는 review를 유지하며 전체 이슈 종결0입니다. 고객자료 조회·게스트/여행/문의 생성·유료모델·운영DB쓰기·push·배포·삭제는0입니다. 모든 실패 로그(최초 esbuild 없음, 초기 브라우저 타임아웃, PowerShell 작업경로 오류 포함)와 사본은 git밖 scratch/teamflow-safe-20261029에 보존했습니다. 시작 여유327981117440바이트이며 삭제로 공간을 확보하지 않았습니다. 자기 브라우저·테스트 서버는 종료했습니다. 전체제품 수락 분모는 모릅니다.

트래커 영수증:729 단일 객체를 다시 읽어 이전 snapshot과 전체필드 일치 확인 후 원필드를 모두 보존해 설명만 증거로 보충했습니다. PUT1회·재GET에서 변경필드 desc/updatedAt 두 개만 확인, review·미담당·due 포함 나머지는 동일합니다. [영수증](../evidence/2026-10-29_st4f729-loading-and-public403/tracker-receipt.json).
