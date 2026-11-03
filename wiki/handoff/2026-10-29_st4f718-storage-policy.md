---
type: handoff
title: ST4F-718 저장 자원·quota·로그아웃 후속
status: draft
domain: travel
---

# ST4F-718 저장 자원·quota·로그아웃 후속

**필수 2/3 = 66.7% HOLD**입니다. [이유·실행·실패·정책·보존 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f718-storage-policy.md). 구현/검증 담당은 이번 Codex 세션이며 독립 검토·개인정보 승인·통합·운영 수락 완료가 아닙니다.

한 일 목록:

1. 독립검토와 루트/CS 규칙·wiki·역할·경로·coord NOTICE 61개를 읽고 새 no-hardlinks clone `scratch/st4f718-storage-20261029/r`에서 진행했습니다. 기존 사본·다른 세션·원본 제품은 보존했습니다.
2. D3의 기기별 여행 한 번 계약을 확인했습니다. 임의 50 cap/TTL·로그아웃 이력 초기화는 기존 계약과 충돌합니다. 영속 집합의 저장량 자체는 늘 수밖에 있어 브라우저 quota와 명시적 자동 재생 보류를 자원/실패 정책으로 제안했습니다. 장기 보존과 고객 안내는 미승인입니다.
3. IndexedDB 고정 크기 keyed 표식·원자적 claim·commit 뒤 허용·지속 오류/수동 안내를 구현했습니다. raw ID v1은 사용/SignOut 때 이관 후 제거하며 실패 시 원문 보존과 식별자 잔존 경고를 표시합니다. 로그아웃 계정 캐시/동의 정리는 이관 실패와 무관하게 완료합니다. 비동기 결과의 세션/화면 변경 뒤 재생도 막았습니다.
4. 웹1,241/1,241·Edge22/22·변이4/4·실제Toast3/3·types/lint2/2 = 100%입니다. >50 여행(256개), 10,000개 이관, 탭 경합, 실제 logout/SignOut, privacy를 검증했습니다. 실제 localStorage quota와 주입한 IDB commit quota를 구분했습니다. CDP로 native IDB quota를 재현하려던 시도는 실패로 남겼습니다.
5. 새 전용 PG 계약367/367·DoD26/26 = 100%, 보안124/125 = 99.2%입니다. 기존 XML 탐지 실패를 고치거나 제외하지 않았습니다. XML/scanner2/2·기존 공개증거11/11 = 100% 해시 유지, 최종 신규파일7/7 scanner 무탐지입니다. PG56318은 최종 신원 확인 뒤 정지/연결 거절, 자료는 보존했습니다.

다음 담당자는 [7파일 후보 patch](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f718-storage-policy/candidate.patch)와 [계약 후보](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f718-storage-policy/credits-device-history.md)를 실제 최신 통합 tip에서 검토해야 합니다. baseline cf8d9760 및 그 740 부모를 가진 bundle 전체를 통합하지 마세요. 이전 cap으로 유실된 ID는 복구하지 않습니다. 같은 origin 스크립트가 표식을 대조할 수 있으므로 익명화/무기한 보존 승인으로 읽지 마세요.

보안 HOLD 정식 처리, 정책 공동 검토, 전체 TripScreen·실서버·실제 휴대폰 수락, native IDB quota/축출·구버전 탭 검증이 남습니다. 운영 잔여 분모 모름입니다. 실제 Toast 합성 화면과 추출 callback을 전체 제품 수락으로 대체하지 않았습니다. 원본 제품·운영·tracker 쓰기, commit, push, 배포, 종결은 각각 0건입니다.

최종 스캐너 정정: 원본의 빈 허용 목록과 선행 clone의 기존 허용 항목은 서로 다릅니다. 양쪽 파일을 수정하지 않고 원본 scanner 함수를 그대로 실행하며 REPO만 격리 경로로 지정해 보안을 재검증했습니다. 원본2/2와 clone 자체 baseline2/2 보존이며, 두 스캐너 정책이 같다는 뜻이 아닙니다. 이 차이도 통합 검토 대상입니다.
