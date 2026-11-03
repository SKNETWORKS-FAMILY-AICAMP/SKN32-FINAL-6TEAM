---
type: report
title: ST4F-729 보안 오탐 독립 재현·검증된 분류 제안·보존 결정 대기
status: draft
domain: travel
impl_scope: cs
---

# ST4F-729 보안 후속

2026-10-29T04:35:59.223271+09:00. 루트·CS AGENTS/RULE, 양쪽 wiki, 역할·코드 경로·시험 지도와 기존 인계를 읽었습니다. 담당은 이번 Codex 세션이며, 별도 사람/에이전트의 독립 검토 승인을 주장하지 않습니다. 실제 coord를 보존·공지했고 다른 담당 트리에는 쓰지 않았습니다. 원본 제품 코드/Git·기존 XML 변경0, 삭제0, 커밋/푸시/배포0, 고객/운영/트래커 쓰기0입니다.

**기존 결정 아래 필수 관문 2/3 = 66.7%, 통합 HOLD입니다.** 정책 변경 제안은 기술 관문 3/3 = 100%이지만 승인·통합 완료가 아닙니다. [기존 인계](2026-10-29_st4f729-source-followup.md)의 「승인 없이 XML을 재작성하거나 바이너리로 감추거나 예외에 넣지 않았습니다」를 유지했습니다. 새 예외는 격리 검토안에만 존재합니다.

## 이번 직접 실행 결과

기준선은 양원격 role-manager `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`입니다. 원본이 아닌 기존 격리 seed에서 새 독립 clone을 만들었습니다. Git optional locks는0입니다. 새 PG16.15 DB55749를 초기화·migration·prompt 등록한 뒤 기준선과 기존 combined candidate를 각각 실행했습니다. 시험 대상 변경은 순차 적용했고 로그/XML은 별개입니다.

| 대상·실행 | 이번 결과 |
|---|---|
| 기준선 보안 |124/125 = 99.2%, 같은 XML 실패1·오류0·skip0 |
| 기존 후보 보안 |124/125 = 99.2%, 같은 XML 실패1·오류0·skip0 |
| 기존 후보 계약 |367/367 = 100%, 오류/skip0 |
| 기존 후보 DoD |26/26 = 100%, 실제 pytest216/216 = 100%, 오류/skip0 |
| 오탐 분류 제안 보안 |143/143 = 100%, 오류/skip0; 새 회귀18/18 = 100% |
| 오탐 분류 제안 계약 |367/367 = 100%, 오류/skip0 |
| 오탐 분류 제안 DoD |26/26 = 100%, 실제 pytest216/216 = 100%, 오류/skip0 |

이번 명령은 `ready2.py`·`finish.py`·`proposal.py`·`proposal-gates.py`에 있습니다. RULE의 pytest security/contract 및 verify_dod_v11 명령을 분모/표본/범위 축소 없이 실행했습니다. XML 집계는 [summary](../evidence/2026-10-29_st4f729-security-resolution/summary.json)를 따릅니다. 이전 웹/빌드/브라우저 결과를 이번 결과로 재사용하지 않습니다. 이번에는 화면·운영 수락을 다시 실행하지 않았고 전체 제품 수락 분모는 모릅니다.

## 정확한 오탐과 보존 경계

원본·새 기준선·후보의 기존 `security-ready.xml` SHA256은 모두 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`입니다. 검출5건은 네 detector 합성 표본의 testcase name 속성에만 있고, 다른 속성/본문 검출0입니다. 첫 표본은 pytest unicode escape를 거친 이름입니다. 실제 접속 정보 유출로 확정하지 않습니다. [위치별 결과](../evidence/2026-10-29_st4f729-security-resolution/results.json).

기존 후보는 안정적인 표본 ID만 추가했습니다. 실제 기준선과 AST 비교에서 그 decorator 외 코드가 동일하며, 기준선에 이미 있던 허용 항목도 보존합니다. 빈 허용 목록이라고 가정한 초기 집계 필드는 실제 기준선 AST 비교로 바로잡았습니다. [동일성](../evidence/2026-10-29_st4f729-security-resolution/source-proof.json).

바이트가 같은 XML을 같은 raw detector로 검사하면 같은 다섯 검출이 발생합니다. 따라서 원본 불변·판정 불변·즉시 GREEN을 동시에 달성할 수 없습니다. 경로/확장자 제외, IP/웹훅 값의 전역 허용, 보고서 본문 가리기, 바이너리 포장, 추적 증거 삭제는 하지 않았습니다.

검토안은 **정확한 기존 blob SHA256이 맞을 때만 네 합성 testcase 이름을 명시적으로 오탐 분류**합니다. 나머지 내용은 원래 detector로 검사합니다. 모든 추적 텍스트 파일을 계속 읽으며 파일 경로를 제외하지 않습니다. 바이트가 하나라도 바뀌면 분류를 적용하지 않고 원래 검사로 돌아갑니다. 향후 성공 보고서는 안정적 ID로 재발을 막지만 실패의 원시 검출 내용은 숨기지 않습니다.

새 회귀18건은 정확한 원본 분류1, 네 표본×추가 위치3(끝/이름/본문)12, 비밀과 무관한 한 바이트 변경1, raw detector 동등4입니다. 별도 외부 검산14건도 통과했습니다. 이 검산은 보존된 원문을 수정하지 않고 메모리에서 수행합니다. [검토 패치](../evidence/2026-10-29_st4f729-security-resolution/proposed-classification.patch), [729 포함 전체 제안](../evidence/2026-10-29_st4f729-security-resolution/complete-proposal.patch).

이 방식은 검사 파일 범위를 줄이지 않지만 **명시적인 오탐 예외 결정**입니다. 기존 인계의 예외 금지를 스스로 해제하지 않았습니다. 이 정확한 blob의 합성 이름 분류 승인 전에는 원격 통합·증거 판정 변경을 하지 않습니다. 승인 후에는 담당 검토, coord/양원격 tip 재확인과 그 시점의 최종 관문 뒤에만 통합을 검토합니다. main/develop/EKS·589 범위는 유지합니다.

## Git credential helper

기존에 보존된 gh2.97.0 실행 파일은 설치된 WindowsApps gh와 SHA256 `e92564e62dcb4525f0decfd8a87d9e2656391f78a342de07cf65dc940f2cdf28`로 동일하고 Authenticode `Valid`입니다. [설치본 대조](../evidence/2026-10-29_st4f729-security-resolution/helper-provenance.json).

처음에는 명령별 helper를 사용했고, 이후 새 격리 clone의 local config에만 빈 helper 재설정 및 그 실행 파일의 `auth git-credential`을 설정했습니다. 명령별 override 없이 실제 양원격 조회2/2 = 100% 성공, 양쪽 tip은 위 해시입니다. 전역·원본 Git 설정 변경0, 토큰/credential 출력0입니다. helper가 OS 저장소를 정상 사용했으며 비밀을 추출·복사하지 않았습니다. [기본 명령 재조회](../evidence/2026-10-29_st4f729-security-resolution/local-helper-readback.json). 다른 작업 폴더의 깨진 전역 helper까지 수정했다고 주장하지 않습니다.

## 실패·인계

첫 보안 실행은 종료된 이전 DB를 지정해 미완료 상태로 중단했고 원시 부분 로그를 남겼습니다. 새 DB 기동 때 subprocess capture pipe가 백그라운드 서버에 상속돼 래퍼가 대기했고, 그 래퍼만 종료한 뒤 파일 출력으로 고쳤습니다. PG는 계속 정상 기동했고 새 DB/migration을 확인했습니다. 첫 집계는 시스템 Python의 pytest 부재로 실패했으며 시험에 사용한 준비된 Python으로 집계를 완료했습니다. 세 실패를 최종 성공 로그로 덮지 않았습니다.

새 DB는 이번 세션의 pg_ctl fast stop exit0으로 정상 종료했으며 데이터는 보존합니다. 원시 로그/XML·모든 스크립트·전체 clone·PG 데이터·초기 실패는 [작업 폴더](../../../../scratch/st4f729-resolution-20261029/)에 남았습니다. 새 wiki에는 원시 금지 표본을 복제하지 않고 요약/패치/해시를 넣었습니다. [보존 manifest](../evidence/2026-10-29_st4f729-security-resolution/manifest.json).

한 일 목록: 실제 coord/지침 확인 → 서명된 설치본 동일 helper 복구/양원격 조회 → 새 clone/새 PG 준비 → 기준선·기존 후보 독립 재실행 → XML 속성별 오탐/AST 동일성 확인 → 해시 고정 분류안 및 변조 회귀18건 검증 → 제안 필수3관문 실행 → 원본 XML 불변 검산 → 자체 PG 정상 종료/증거 보존 → wiki/coord HOLD 인계.

남음: 정확한 blob의 합성 이름을 오탐으로 분류할 명시적 결정과 담당 검토입니다. 전체 제품 수락 분모는 모릅니다. 정책 승인이 오더라도 그 자체가 푸시/운영 수락 완료는 아닙니다.

최종 패치 저장의 첫 Git diff는 긴 경로 경고3건을 냈습니다. 처음 패치도 별도 이름으로 보존하고 `-c core.longpaths=true` 및 CS 경로 한정으로 다시 저장했습니다. 전체 변경 경로는 CS 내부2개뿐이고 diff --check exit0, 자체 PG55749 연결 거부를 확인했습니다.
