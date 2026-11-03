# 라우팅 전수검사 미결 재집계 · B10 수정 후보 인계 (2026-10-29 14:30 KST, S4)

## 결론
- 재집계: role-manager `c714eecdb` → `fab3da50a`(11커밋) 사이 앱 변경은 버스 · 식당 메뉴 · 웹 접수/로그아웃뿐 — 미결 28 중 닫힌 것 0. 이번 B10 수정 후보로 **미결 27/70 = 38.6%**(role-manager · x600 반영 전까지 후보).
- **B10 수정(후보, push 0)**: 고객 고정(`detail.customer_pinned`) 숙소 · 항공편 「바꿔 줘」가 후보를 찾고 고르면 적용기에서 `ActionRejected` 나던 것 → 공용 `_protected_refusal` 답. 기준 RED 3/4 → 4/4.
- **B11 확인**: 웹 추가 칸 종류가 `activity|dining` 뿐(`new-stop.ts:6`, `plan-check.tsx:2127`) — 숙소 카드는 종류 없이 열린다. 화면 계약 결정 필요로 남김.
- 같이 고친 기존 실패: `test_lodging_team.py` 숙박 기간 밖 장소 날짜(오늘+10일)가 달 말에 기간 안으로 들어가던 시험 데이터 결함.

## 위치
- worktree `cache/scratch/routing-open-20261029b/wt` = `327d7baaa`(fab3da50a 위: `53ea8134d` 코드·시험, `327d7baaa` 보고서). patch `routing-open-20261029b/patch/000{1,2}-*.patch`. 기준 트리 `.../base`(fab3da50a).
- 보고서(후보 트리): `final_project_cs/wiki/records/reports/2026-10-29_라우팅전수검사_미결재집계_B10수정.md`.

## 검증
- booking 기본 80/80 · 전체 325/325. 빠른 관문 후보 vs 기준 병렬: 10,945 vs 10,941 nodeid, 새 4건 통과, 잃음 0, 상태 변화 0. 실패 3은 양쪽 같은 nodeid(eval HTML 2 환경 + 아래 보안 1).
- ruff · diff --check 통과. Codex 검토 안 함(자기 검토).

## 주의
- **role-manager tip 보안 시험 실패**: `tests/security/test_no_infra_in_tracked_files.py` 가 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`(시험 입력 8.8.8.8 · 가짜 discord 웹훅)을 잡는다. 보호 XML 이라 손대지 않음 — ST4F-728 담당 몫.
- S3(`routing-open-20261028/s3`)의 A09 미커밋 diff(`agent_read.py` 뒤 묶음 `drops` 스키마 · 프롬프트)는 그대로 보존. 모델 스키마 변경이라 실 E4B 같은 시간대 비교 전에는 넣지 않는다.

## 다음
1. 부모: `ls-remote` 가 `fab3da50a` 그대로면 `327d7baaa` 를 팀 · 개인 role-manager 에 ff push → x600 배포 확인 → B10 「고침」 확정. develop · main · EKS 는 사용자 지시로 push 금지. TeamFlow 이슈를 만들 경우 담당은 manager.
2. 결정 대기: A05 · A06 · C14 · C15 · C17 · 웹5 · B11(숙소 추가 칸) · E-D6(DB 쓰기 승인).
3. A09: S3 diff 를 새 tip 위에서 실 E4B 비교(lease) 뒤 판단.
