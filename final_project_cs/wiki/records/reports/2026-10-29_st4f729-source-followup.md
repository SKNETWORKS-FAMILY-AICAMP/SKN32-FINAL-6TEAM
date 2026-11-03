---
type: report
title: ST4F-729 보안 보고서 생성 원인 수정·기본 빌드 해소·증거 불변 HOLD
status: draft
domain: travel
impl_scope: cs
---

# ST4F-729 후속 검증

2026-10-29T04:14:31.535765+09:00 실측. 루트·CS AGENTS/RULE, 양쪽 wiki index, 개발 역할·코드 경로·운영 앱 API 계약, 기존 독립 검토 및 실제 coord 파일을 읽었습니다. 이번 세션은 이전 구현/독립 검토의 후속이며 자기 수정에 대한 별도 독립 검토 승인을 주장하지 않습니다. 하위 에이전트0, 고객/운영 쓰기0, tracker 수정0, 커밋/푸시/배포0, 삭제0입니다. main/develop/EKS·589 예약은 유지했습니다.

**필수 관문 2/3 = 66.7%, 통합 HOLD입니다.** 기존 XML 불변 보존과 현재 검사 통과를 동시에 충족하지 못합니다. 보존 형식 변경은 별도 명시적 승인 전까지 하지 않습니다. [이전 독립 검토](2026-10-29_st4f729-independent-review.md)를 오늘 결과로 다시 쓰지 않았습니다.

## 원인과 최소 수정

팀 role-manager 기준선 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`에서 새 격리 worktree `scratch/st4f729-followup-20261029/repo`를 만들었습니다. 원본 Git/제품 코드·색인·refs·sparse 설정은 변경하지 않았습니다. 원격 조회/fetch는 기존 격리 저장소에서만 했으며 Git 자식 시험에는 GIT_OPTIONAL_LOCKS=0을 전달했습니다.

실패 시험은 `tests/security/test_no_infra_in_tracked_files.py::test_no_tracked_text_file_leaks_infrastructure`입니다. 추적된 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`의 JUnit testcase name 속성4개에서 합성 보안 표본5건이 검출됩니다. 속성 외 본문에서 같은 표본이 나온 것은 아닙니다. 실제 인프라 사고로 단정하지 않습니다. 원본·HEAD·후보의 XML SHA256은 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`로 같습니다. [위치별 분석](../evidence/2026-10-29_st4f729-source-followup/baseline-artifact.json).

pytest가 매개변수 값을 기본 test id로 사용해 XML로 내보내는 보고서 생성 경로가 원인입니다. 후보는 합성 표본4개의 id만 고정합니다. AST 비교에서 해당 decorator를 제외한 코드 전체가 같습니다. 검사기·표본 값·assert·추적 파일 범위·허용 목록·건너뜀은 변경하지 않았습니다. 같은 표본4/4 =100% 양쪽 통과, 표본 전용 XML의 검출은5→0입니다. 실패한 검사 결과에서 실제 검출값을 보고하는 동작은 유지합니다. 전체 실패 XML을 깨끗하다고 주장하지 않습니다. [소스 동일성 검증](../evidence/2026-10-29_st4f729-source-followup/source-proof.json), [최소 수정](../evidence/2026-10-29_st4f729-source-followup/source-fix.patch), [729 포함 후보](../evidence/2026-10-29_st4f729-source-followup/combined-candidate.patch).

## 이번 실행 결과

| 실행 | 결과 |
|---|---|
| 기준선 보안 전수 |124/125 =99.2%, 실패1·skip0 |
| 후보 보안 전수 |124/125 =99.2%, 같은 XML 실패1·skip0 |
| 후보 보안 파일 전체 |11/12 =91.7%, 같은 추적 XML 실패1 |
| DoD |26/26 =100%, 실제 pytest216/216 =100%·skip0 |
| 계약 |367/367 =100%·skip0 |
| 관리자·고객 웹 단위 |46/46·1227/1227 =100% |
| 기본 Next/Turbopack 후보 build |admin/web × demo/live 4/4 =100% |
| 기준선 관리자 live 기본 build |1/1 =100% |
| 기준선 Next 로딩 회귀 |0/1 =0%, 운영 로딩 문구 부재로 실패 |
| 후보 Next live 로딩·재시도 |2/2 =100% |
| 후보 Next demo 복귀 |1/1 =100% |
| 고객 session.spec.ts |11/11 =100%, loopback 모방 API |
| 양쪽 eslint·next typegen·tsc |최종 exit0; 관리자 기존 unused import 경고1 |

명령은 `run.py`의 baseline, baseline-build, baseline-browser, candidate, build, gates, candidate-browser, candidate-demo-browser, browser-web, units, web-lint-ready 단계에 있습니다. 필수 명령은 RULE의 DoD/contract/security를 그대로 실행했습니다. 브라우저는 실제 Next 프로덕션 앱과 Edge를 사용하지만 관리자 HTTP는 page.route 합성 응답, 고객 API는 loopback stub입니다. 운영 인증 교체·고객 세션·공개 배포 수락 증거가 아닙니다. 이전 전체 live 967건은 이번에 다시 실행하지 않았으며 표적11건으로 전수 통과를 주장하지 않습니다. 전체 제품 수락 분모는 모릅니다.

기존 기본 build 실패는 외부 node_modules junction이 Turbopack root 밖에 있었던 환경 문제였습니다. 새 사본에 기존 공식 Node24.22.1/Python3.12와 의존성의 실제 사본을 사용했습니다. 설치·의존성 갱신·Next 설정 변경·Webpack 대체0입니다. Next 생성 tsconfig와 시험 config/probe는 후보 패치에 넣지 않았습니다.

## 실패도 보존한 내역

- 첫 setup 감사는 시스템 Python에 pytest가 없어 ModuleNotFoundError로 중단했습니다. 준비된 Python3.12로 바로잡았습니다.
- 첫 migrate 및 보안 수집은 llm_model/embedding_model/tenant_id 세 환경값 누락으로 각각 exit1/exit2, 수집오류2입니다. 처음 로그/XML을 보존하고 격리 mock 설정을 채운 뒤 `*-ready` 이름으로 실행했습니다.
- 고객 eslint 첫 실행은 새 `.next-follow729-*` 생성물 270파일에서 오류692·경고18,632(총19,324)를 냈습니다. 기존 제외 설정 밖의 산출물이었으며 검사 설정은 바꾸지 않았습니다. 같은 `eslint .`를 생성물 보관 후 재실행해 exit0을 확인했습니다.
- 생성물은 같은 격리 작업 폴더의 `build-artifacts/web-demo`, `web-live`로 이동·보존했습니다. 이동 후 파일 수 검산 assert가 실패했습니다. 현재 두 BUILD_ID와 전체 파일 목록은 보존했으나 이동 전후 바이트 일치를 입증했다고 주장하지 않습니다. [보관 목록](../../../../scratch/st4f729-followup-20261029/build-preservation.json). 삭제0, 프로세스 종료 요청은 이미 해당 lint가 끝나 매칭0/종료0입니다.
- 격리 origin은 개인 GitHub가 아닌 로컬 seed 저장소였습니다. 초기 `remote-tips.json`의 personal/null 표기는 개인 원격 확인 결과로 사용하지 않습니다. 이후 실제 양원격을 별도로 조회했습니다. 팀 tip은 기준선과 같고 개인 조회 결과는 영수증을 따릅니다. [실제 조회](../evidence/2026-10-29_st4f729-source-followup/actual-remote-tips.json), [기본 인증 조회](../evidence/2026-10-29_st4f729-source-followup/personal-remote-read.json). 양원격 동기화를 완료했다고 주장하지 않습니다.

## 보존·인계

원시 XML·보안 실패 원문·전체 로그·합성 DB·모든 브라우저 결과·실제 의존성 사본은 [작업 폴더](../../../../scratch/st4f729-followup-20261029/)에 보존했습니다. 금지 표본을 wiki에 다시 복제하지 않도록 새 wiki evidence에는 요약·패치·해시 목록만 추가했습니다. 원시 실패 결과의 검출 내용을 가리거나 삭제하지 않았습니다. [실행 집계](../evidence/2026-10-29_st4f729-source-followup/summary.json), [SHA256 목록](../evidence/2026-10-29_st4f729-source-followup/manifest.json).

한 일 목록: 원인 속성별 확인 → 기준선 보안/Next 화면 RED 재현 → 표본 id 최소 수정/동등성 확인 → 후보 기본 build4건·브라우저14건·단위1273건·필수 관문 재실행 → 기존 XML 불변 확인 → coord HOLD 기록 → 자체 PG 정상 종료(exit0), 시험 포트4/4 =100% 연결거부 확인. 다른 프로세스·DB·서비스는 종료하지 않았습니다.

남은 일은 기존 증거의 불변 원칙과 보안 관문을 함께 충족할 명시적 보존 결정, 담당 검토, 최신 양원격 대조 및 모든 관문 통과 뒤의 통합입니다. 승인 없이 XML을 재작성하거나 바이너리로 감추거나 예외에 넣지 않았습니다. 현재 실패 상태에서는 통합·푸시하지 않습니다.
