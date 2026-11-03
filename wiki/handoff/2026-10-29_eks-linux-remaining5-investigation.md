---
type: handoff
title: EKS Linux 잔여5 원본 재현·개별 진단·HOLD 유지
status: draft
domain: travel
---

# EKS Linux 잔여5 후속 인계

**추가 해소0/5 = 0%·새 재현 실패5/5 = 100%·skip0, PR110 draft/HOLD 유지.** 이전218/223 = 97.76%는 이번 전체 재실행 결과가 아닙니다. [보고서](../records/reports/2026-10-29_eks-linux-remaining5-investigation.md)·[실행/해시 요약](../records/evidence/2026-10-29_eks-linux-remaining5-investigation/summary.json).

한 일 목록:

- 루트/cs 규칙·wiki·coord EKS 알림·main/PR을 읽었습니다. main57f3d2f004d0·PR110 open/draft3fda4eee/HOLD 확인, 운영 쓰기/모델/push/merge/배포0입니다.
- 이전 tip ee8ca880(소스7484a180)을 `/root/eksremaining5_1029/candidate`에 새 no-hardlinks 복제했습니다. 원본113/113 = 100% SHA256 검증, 시험5/golden3/입력·픽스처2 보존10/10 = 100%, tracked diff0입니다. 이전 사본·DB·자료·임시 폴더는 그대로입니다.
- Linux ARM64/Python3.12에서 원래5개를 그대로 실행해 실패5개·오류0·skip0을 재현했습니다. 제품/시험/golden 변경0, 허용오차/precision/마커/비교 범위 변경0입니다.
- 새벽710→301의 기점 첫차와 중간 승차 정류장을 원문으로 분리했습니다.710은03:50 기점→경복궁12,048m인데 실제 trace는04:00 정류장 판정입니다. 독립 profile p90과 p10/p50 결측을 기록했으며 실제 첫차/최소통과시각으로 둔갑시키지 않았습니다. 정류장 첫차 근거와 미확인 처리 계약 없이 임의 보정하지 않았습니다.
- 혼합 A0/B13을 직접 열거해7/13 = 53.85%가 원래11:30 목표에 성립함을 확인했습니다(모두10:45 이전 출발). 잠실8→천호5→왕십리→2016은10:45 장소 출발·12:05 목표에도 명시 재검증 성립합니다. 원래 사고에서 rail+bus 없음은 아닙니다. 실제 bus+bus 선택과 bounded search/동률 문제를 구별하고 원래 prefix 단언을 보존했습니다.
- bike golden4개 비교항목/default golden42개 비교항목 차이를 값별로 남겼습니다. 무근거 직접도보 복구·v2 조건 혼합·golden 재생성0입니다. 지정 인계/보고2/2 = 100% strict UTF-8 정상·물음표 연속/U+FFFD0, 원문 수정0입니다.

로컬 도구/모든 raw: `C:/_proj/eksremaining5_1029`; Linux 새 사본: `/root/eksremaining5_1029/candidate`; XML/명령·원문해시·독립 산술·선택 trace는 위 보고서 링크입니다. 코드 수정/커밋0, 독립 검토자 승인이나 담당 통합 예약 없음입니다. 새DB/리스너0·삭제0입니다.

다음: 새벽은 정류장별 첫차 근거·결측 처리 계약, 혼합은 후보 제한/선택 요구, golden은 입력/라우터 조건별 권위 기대를 개별 확인합니다. 남은5개 모두 미해결이며 실패를 green으로 바꾸지 않았습니다. 이전 전체 RAG16 미준비도 이번에 재실행하지 않았습니다. 실제 reader fatal은 별도이며 기존 허용된 운영 이유 로그/운영 수락 전까지 PR110 HOLD입니다. 모든 run·temp는 새 이름을 사용하고 이전 증거는 재사용/삭제하지 않습니다.
