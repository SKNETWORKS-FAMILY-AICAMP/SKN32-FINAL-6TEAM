---
type: handoff
title: ST4F-719 late id mutation 독립 검토 — 미리보기 P1·보안 HOLD
status: draft
domain: travel
---

**후보 수락 보류**입니다. `useServerReview.previewRecommendAll`의 await 뒤 소유권 검사가 없어 계정 전환 뒤 A의 늦은 응답이 마운트된 preview state에 들어갑니다. 실제 PG 인증·Edge **0/1 = 0% 통과**, 검사 한 줄 임시 추가 대조 **1/1 = 100%**, 이후 후보 복구했습니다. [상세 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-late-id-independent.md).

기존 네 경합/정상 대조 **8/8 = 100%**, 개인정보 **10/10 = 100%**, 웹 **1304/1304 = 100%**, PG 테넌트 경계 **3/3 = 100%**, 계약 **367/367**, DoD **26/26**, 쿠키 **38/38 = 100%**입니다. 서명된 기존 Git helper를 시험 전용 경로로 재사용해 PermissionError를 해소했으나 보안은 보호 XML 검출로 **124/125 = 99.2%**, 필수 **2/3 = 66.7% HOLD**입니다. 실제 여행 응답은 합성 stub이며 운영 쓰기 종단 검증은 아닙니다.

기존 `scratch/st4f719-blocker-independent-20261029/repo`와 PG/Next 캐시를 재사용했습니다. 새 clone·DB 전체 복사·프로필 변경·원본 제품 반영·커밋·push·배포·삭제는 0건입니다. `setup.json`은 시험 후 복구했고 scanner/XML도 유지합니다. 현재 coord 디렉터리는 없어서 기존 snapshot만 읽었습니다. 최신 조정 상태 확인은 남아 있습니다.

재현은 기존 작업 폴더에서 실행합니다. fixture/쿠키 파일은 공개 복사하지 않습니다. 기존 러너의 종료 0만 보고 성공으로 판단하지 말고 Playwright JSON·pytest XML을 확인합니다.

실제 PG 인증·Edge 가드 제거 변이는 목표 **4/4 = 100% 검출**했습니다(등록 8건 중 4실패·4선택 제외). 후보 소스 **12/12 = 100%**, scanner/XML **2/2 = 100%** 복구 해시 일치입니다. 모든 실행 후 전용 PG 정지와 포트 연결 거부를 확인했습니다.

```powershell
$env:BROWSER_SPECS='independent-late-preview'
$env:API_PROBES='0'
$env:INDEP_PROBES='0'
$env:LATE_REAL='1'
python scratch/st4f719-blocker-independent-20261029/run_late_gates.py browser-independent-preview-original
```

위 이름은 이미 사용했으므로 재실행 시 새 결과 이름을 쓰십시오. 독립 probe와 변이/진단 driver는 [공개 evidence](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-late-id-independent/)에 있습니다. mutation runner는 후보를 잠시 바꾸므로 다른 검증과 동시에 실행하지 않습니다.

다음 담당은 미리보기의 늦은 응답·실패 후 재요청·결과 반환과 취소를 포함한 소유권 수정 후 재검토해야 합니다. 기존 ST4F-745 검토 대상에 대한 로컬 인계이며 이 세션은 이슈나 외부 담당자에게 메시지를 보내지 않았습니다. XML/scanner 보안 HOLD가 풀리기 전에는 병합·push하지 않습니다.

디스크 inventory: entries 0·unregistered_dirs 0, 여유 182,893,592,576바이트, 최소 32,212,254,720바이트·목표 400,000,000,000바이트입니다. 공개 evidence는 집계 시 20,180바이트입니다. Next 캐시 순증은 작업 전 실측이 없어 모릅니다. 모든 원본·사본·실패 로그를 보존했습니다.

이번 실행 이름의 로그·JSON·XML·브라우저 출력·독립검토 폴더·재현 스크립트 89파일은 집계 시 1,012,223바이트입니다(기존 PG·Next 캐시·공개 evidence·추가 probe 소스·wiki 문서는 별도).
