# 채팅 일정 옮기기 — 절대 시각·날짜 옮기기·되돌릴 것 없음·장소+시간 충돌 (2026-10-26)

후보 폴더: `cache/scratch/time-date-fix-20261026-051654/` (Hermes 프로필 guguroute). push·배포·live 교체 없음.

## 결론
- role-manager `53dea261` 위 staged 후보(tree `1e2131a2`, patch SHA256 `96e31a0f…deb1c`). 10파일 +477/−23.
- 단위 관문 tests/unit/travel: 후보 7566건 중 실패·오류 47건, 기준 53dea261 7531건 중 47건 — **같은 nodeid**(신규 실패 0, 신규 35건 모두 통과). 47건은 격리 runner의 DB·네트워크 차단 46건 + mobility 버스 공유 DB 1건(기준에도 있음, 이 변경과 무관).
- 실 E4B(v10 serving 사본 + 같은 patch, 비교 DB 새 tenant) 3회 lease, 16 호출: T10·T15·T16·T17·D02·D03 pass, D04는 안전한 되묻기(기대 adjusted 대비 fail), D01·D05는 모델 해석 문제로 fail.

## 기능별
| 기능 | 결과 | 근거 |
|---|---|---|
| 미루기·당기기(크기) | 됨(기존) | 「11시 30분」의 30분을 크기로 세던 결함 수정(`spoken_minutes`) |
| 절대 시각(T10) | 됨 | 실 E4B: start 23:30 → `crosses_midnight` 거절 |
| 되돌릴 것 없음(T15) | 됨 | 실 E4B: `answered`/`nothing_to_undo`, 무변경 |
| 날짜만 옮기기 | 됨(dN일 때) | D03 「하루 뒤로」 adjusted. D01 「다음 날로」는 모델이 tomorrow로 읽음 → rm 경로에서는 `day_outside_trip` 거절(오프라인 재생) |
| 날짜+시각 | 됨 | D02 adjusted 13:00 d2(구형 anchor_time 사용) |
| 날짜+체류(end/duration) | 됨(단위) | 실모델 미측정 |
| T17 겹침 | 됨 | `itinerary_infeasible` + check_itinerary 관측 |
| 장소 행동+시간만(T16/D04) | 되묻기 | 해석 실패·무단 교체 대신 「다른 곳으로 바꿀지, 시각을 옮길지」 |
| 순서 바꾸기 C05 / 추가 C01 / 삭제 C04 | 미실행 | 이번 범위 밖 |
