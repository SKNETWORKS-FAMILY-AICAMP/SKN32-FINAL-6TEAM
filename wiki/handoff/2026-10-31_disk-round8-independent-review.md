# 인계: C: 8차 하드링크 독립 검토 — 2026-10-31

보고서: [2026-10-31_disk-round8-independent-review](../records/reports/2026-10-31_disk-round8-independent-review.md)

## 한 일
- 8차 하드링크 116개, 실패 1개, ETL 210개를 읽기 전용으로 다시 확인했다.
  - 매니페스트, inode, nlink, 크기를 대조했다.
  - inode 24개의 sha256을 전부 다시 계산했다. 24/24가 기록과 같았다.
  - 합계 7,315,361,792 B가 보고서와 일치했다.
- 실행 중 여부를 확인했다. 관련 트리를 참조하는 프로세스는 0/209개였고, 24시간 안의 쓰기는 0개였다.
- 프로젝트 보호를 확인했다. final_workspace를 대상으로 한 항목은 0개였다.
- 수정·복원·삭제·속성 변경·설정 변경은 하지 않았다.

## 남은 결정 (사용자/소유자)
1. 보존 경로가 작업 사본과 inode를 공유한다. inode 18개, 938,329,044 B다.
   - `_preserved/finalspace_20261028/finalspace_full_20261028.bundle` ⇄ scratch `finalspace_preservation`
   - backups `scratch-candidates-20261029d/files` 8개 ⇄ scratch 도구 사본
   - `_archive_20261027` 8개와 `place-quality-20261027` 7개 ⇄ 14-링크 활성 체크아웃 묶음
2. 선택지는 보고서 「복원·승인 경계」 A~E에 있다. 링크를 분리하면 최대 1.03GB를 다시 쓴다. 비용 없는 대안은 읽기 전용 속성 지정이다.
3. 이 링크 경로들에 제자리 덮어쓰기를 하지 않는다. 대상 명령은 `Set-Content`/`>`/`open('wb')`/`Expand-Archive -Force`/`copy /Y`다. 덮어쓰기가 필요하면 먼저 그 경로를 복사한 뒤 이름 변경으로 분리한다.
4. 8차와 무관한 사실을 하나 발견했다. `latest-serving-6c345-20261025/source-v2`의 Git alternates가 없어진 저장소를 가리키고 있어 `bad object HEAD`가 난다.

## 디스크
- 이 세션이 쓴 양: scratch `disk-r8-review-20261031`에 1,035,997 B, wiki 증거·보고서에 약 0.3MB.
- 정리한 양: 0 B.
- 측정 시점 C: 여유: 207,942,475,776 B.
