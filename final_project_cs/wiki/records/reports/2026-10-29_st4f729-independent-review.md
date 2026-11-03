---
type: report
title: ST4F-729 독립 검토·최신 manager 관문과 보안 HOLD
status: draft
domain: travel
impl_scope: cs
---

# ST4F-729 독립 후속 검토

2026-10-29T03:59:55.123942+09:00 실측. 이전 구현 세션과 별도의 이번 세션에서 루트/CS AGENTS·RULE, 양쪽 wiki index, 역할·코드 경로, 관리자 API 계약과 실제 `_coord` 42파일을 읽었습니다. 검토자는 이번 Codex 세션이며 추가 하위 에이전트는 사용하지 않았습니다. 기존 main/EKS·589 담당 예약을 존중했습니다. 이전 보고를 성공 증거로 재사용하지 않았습니다.

## 판정

최신 팀 role-manager `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`를 기존 격리 저장소에서 fetch하고 새 격리 worktree에 후보를 적용했습니다. 적용 전 `git apply --check` 통과, 검증 후 같은 원격 tip 재확인. 제품 변경은 실제/데모 로딩 문구 및 데모 전용 단추 분기에 한정됩니다. 인증·operator 전달·QueryClient·명령·DB 계약 변경은 없습니다. 세션 정리의 기존 회귀도 관리자 단위 전수에 포함했습니다. 코드 검토에서 후보 자체의 추가 결함은 발견하지 못했습니다.

필수 관문 **2/3 = 66.7%**이므로 **통합 HOLD**입니다. 안전 통합 요청의 전제조건을 충족하지 못해 커밋·양원격 push·배포·tracker 수정·종결은 모두0입니다. 개인 원격 최신성/ff 수락은 진행하지 않았으므로 양원격 일치를 주장하지 않습니다. 원본 제품 코드·색인·refs·sparse 설정은 변경하지 않았습니다.

| 이번 실행 | 결과 |
|---|---|
| `python -m scripts.verify_dod_v11 --evidence-dir ...` | 26/26 = 100%, 실제 pytest216 통과·skip0 |
| `python -m pytest tests/contract -q` | 367/367 = 100% |
| `python -m pytest tests/security -q` | 124/125 = 99.2%, 실패1·skip0 |
| 관리자 Vitest | 46/46 = 100% |
| 고객 웹 Vitest | 1227/1227 = 100% |
| 양쪽 eslint·tsc, 관리자 next typegen | exit0; 관리자 기존 unused import 경고1 |
| 기존 후보 Playwright 회귀 | 1/1 = 100%, Vite 합성 화면 |
| 새 독립 시험: 실제 조회 재시도·데모 복귀 | 2/2 = 100%, Vite 합성 화면 |
| Next 프로덕션 실제 모드 로딩·재시도 | 2/2 = 100%, HTTP 요청을 합성 응답으로 대체 |
| 고객 웹 `session.spec.ts` 통합 | 11/11 = 100%, 별도 loopback stub API |
| 기본 Next/Turbopack build | 0/2 = 0%, 외부 node_modules junction 해석 실패 |
| Next `build --webpack` | 4/4 = 100%, admin/web 각각 demo/live |

지원 범위의 기존 공식 Node24.22.1 및 Python3.12 격리 환경을 사용했습니다. 의존성 설치·갱신은 하지 않았습니다. 기본 Git은 WinError5였으며 원본 Git 우회 실행은 하지 않았습니다. 격리 저장소에서만 기존 실행 가능한 Git을 사용했습니다. 긴 경로 조회의 Filename too long 경고도 로그에 보존했습니다.

## 보안 실패와 미해결 항목

실패는 `test_no_infra_in_tracked_files.py::test_no_tracked_text_file_leaks_infrastructure`입니다. 최신 HEAD가 이미 추적하는 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`에 검사 금지 문자열이 들어 있습니다. 이는 검사 표본 형태 문자열이며 실제 인프라 사고로 단정하지 않습니다. HEAD 원문과 작업 파일의 바이트 일치·SHA256 및 독립 검출5건을 확인했습니다. 후보는 그 파일을 수정하지 않습니다. [원문 불변 확인](../evidence/2026-10-29_st4f729-independent-review/baseline-security.json). 과거 증거는 삭제·축소·재작성하지 않았습니다. 증거 보존 원칙에 맞는 담당자 처리 후 최신 branch에서 보안 관문 재실행이 필요합니다. 검사를 건너뛰거나 예외 목록에 넣지 않았습니다.

고객 웹 전체 live 설정은967건을 수집해 일부 실행한 뒤 범위 과대로 자체 실행 트리만 종료했습니다. 전체 결과는 미완료이며 11건 세션 시험으로 대체 성공이라고 주장하지 않습니다. 요청된 변경에 맞는 표적 통합11건을 별도 완주했습니다. 기본 build 실패도 Webpack 성공으로 숨기지 않습니다. 정확한 기본 빌드 관문 수락과 필요시 전체967건은 별도 남습니다.

운영자 실제 교체·고객 세션·공개 배포 수락은 미검증입니다. Cloudflare는 이번 세션에서 재요청·우회·설정변경0이며 이전403/1010 기록은 당시 관측으로만 보존합니다. 고객자료 접근·운영DB 쓰기·외부 유료모델 호출0입니다. 전체 제품 수락 분모는 모릅니다.

## 증거·보존·재개

사본·합성 PostgreSQL55729/review729·원로그·브라우저 결과·실패 모두 `scratch/st4f729-independent-20261029/`에 보존합니다. 해당 DB는 이번 검증 뒤 정식 종료하며 종료 영수증을 추가합니다. 다른 작업자 프로세스는 종료하지 않았습니다. 브라우저 전체 실행을 중단할 때 명령줄로 소유 PID를 검산하고 그 프로세스 트리만 종료했습니다. 삭제0입니다.

Next가 생성한 tsconfig 추가 경로·next-env와 probe/config는 시험 부산물이며 통합 후보가 아닙니다. 원래 [candidate.patch](../evidence/2026-10-29_st4f729-loading-and-public403/candidate.patch)는 보존했습니다. [새 독립 시험](../evidence/2026-10-29_st4f729-independent-review/loading-review.spec.ts), [요약](../evidence/2026-10-29_st4f729-independent-review/summary.json), [로그 SHA256 목록](../evidence/2026-10-29_st4f729-independent-review/manifest.json), [합성 실제 화면](../evidence/2026-10-29_st4f729-independent-review/live.png)을 연결합니다. 원시 XML은 금지문자열 재유입 방지를 위해 wiki에 복제하지 않았습니다.

재개 순서: 보안 증거 담당자 처리 → 최신 양원격 manager와 후보 재대조 → 실패/필요 관문 재실행 → 검토·coord 예약 확인 → 모두 충족할 때만 사용자 승인 범위의 안전 ff 통합. main/develop/EKS는 이번 대상이 아닙니다.

종료 영수증: 자체 PG 정상 종료(exit0), 시험 포트5/5 =100% 연결거부 확인. 데이터·모든증거 보존. [종료확인](../evidence/2026-10-29_st4f729-independent-review/completion.json).
