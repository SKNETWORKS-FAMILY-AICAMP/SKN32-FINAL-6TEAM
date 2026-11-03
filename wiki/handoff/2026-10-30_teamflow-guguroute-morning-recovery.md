---
type: handoff
title: TeamFlow·구구루트 현재 잔여와 전날 이동 복구 수정
status: draft
domain: travel
---

2026-10-30 KST. TeamFlow 현재 미완료109/695 = **15.7%**(todo36/진행16/review57/done586), 매니저72/109 = **66.1%**, 미배정25/109 = **22.9%**입니다. 최근741~746 매니저 담당6/6 = **100%**, 기존 담당·상태 변경0입니다. 완료 목록500건 제한을 type별 조회로 해소했습니다.

반환된 기존 격리 사본에서 전날 이동이 다음 날 아침 이동 복구를 막는 결함을2/2 = **100%** 재현·수정했습니다. 날짜를 넘겨 도착한 기존 이동은 보존하며 최종6파일41/41 = **100%**, 보호335/335 = **100%**입니다. 새 clone/DB/모델0, 프로세스 중단·운영·push0입니다.

한 일: 규칙/wiki/coord 대조, API 실제 집계·담당 확인, 재현→최소 수정→회귀 검증, patch·백업·해시와 상세 보고 보존. 새 시험은 기존 checkout의 test_stay_previous_day_recovery.py, 수정은 registered_moves.py뿐입니다. 증거 scratch/teamflow-resume-20261030/, 기존 후보 경로 scratch/teamflow-continue-20261029/repo/final_project_cs입니다.

필수 관문 이번0/3 = **0%**, 독립 검토·최신 원격 통합·실DB/화면 수락은 남습니다. 보안·서비스 HOLD 유지. high 보안/운영 항목의 남은 조건과 ST4F-742 설명·wire schema 수락 한계는 [상세 보고](../records/reports/2026-10-30_teamflow-guguroute-morning-recovery.md)를 따릅니다. 전체 제품 완료율은 분모 모름입니다. 기존 사본을 release/삭제하지 않았고 이번 파일 범위만 반환합니다.
