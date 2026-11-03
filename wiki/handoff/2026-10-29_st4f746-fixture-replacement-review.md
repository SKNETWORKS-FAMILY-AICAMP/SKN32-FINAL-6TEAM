---
type: report
title: ST4F-746 fixture 치환 검토 인계
status: draft
domain: travel
---

HOLD 유지. 메모리 비교에서 기준114/114·연결 mock 7곳 치환114/114 = 100%, 공인 DNS fixture까지 9곳 치환110/114 = 96.5%였습니다. TEST-NET 세 대역은 실제 제품 공인성 검사에서 모두 거부되므로 DNS 검증용 2곳의 단순 치환은 의미를 손상합니다. 7곳 치환만으로도 원본 detector 2파일/3건이 남습니다. 기존 scanner 선언은 변경 금지 범위입니다.

보존된 제품·시험·scanner·예외·XML 수정0건, push/prod/DB/clone/삭제0건. 기존 보호 증거910/910 = 100% SHA 일치입니다. 최초 Settings 누락 실패와 합성 설정 후 비교 결과를 모두 별도 보존했습니다. 필수 관문은 이전 인정2/3 = 66.7%·HOLD이며 이번 집중 실험을 전체 보안 통과로 세지 않습니다.

다음 담당: 보존본과 분리된 새 작업 버전에서 공인 DNS fixture의 의미 보존 설계와 기존 scanner 선언 처리의 별도 범위 결정을 마련해야 합니다. 이번은 적용 수정 없이 차단 근거를 남긴 검토입니다. 운영 수락·최신 원격 통합 검증은 미수행, 완료율 분모 모름입니다.

[상세 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f746-fixture-replacement-review.md) · [기존 인계](2026-10-29_st4f746-security-gate.md) · [증거](../../scratch/st4f746-fixture-review-20261029/).
