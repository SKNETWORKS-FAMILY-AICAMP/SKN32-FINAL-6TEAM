---
type: report
title: I-2 실사용 문서(관리자 사용자 계약·UTIC 20초) — 팀 role-manager 코드 대조 격리 후보
status: draft
domain: travel
---

# I-2 실사용 문서 격리 후보 (2026-10-27)

사용자 지시(2026-10-27): [미확인 66 의미 재분류](2026-10-27_finalspace-unconfirmed66-semantic-review.md)의 **I-2**(#60 관리자 사용자 목록 계약, #62 UTIC 대기 20초 설명)를 최신 팀 role-manager 코드와 대조하고, 정확한 문서 후보와 검증 증거를 격리해서 만든다. 원본 코드·인덱스·브랜치·작업트리 파일은 고치지 않았다. 커밋·push 0건. 후보는 profile scratch 의 별도 bare 저장소(원본 objects 는 alternates 로 읽기만 함)에만 있다.

## 결론

- **pin = 현재 원격과 같다.** `git ls-remote` 결과: 팀 `role-manager` = 개인 origin `role-manager` = `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b`. 앞 감사의 pin 이 그대로 최신이다(팀 develop 은 `36ba4c2f`).
- **관리자 사용자 계약**(`admin-users.md`, 원본 작업트리 미추적): 문장 19개 중 18/19 = 94.7% 가 pin 코드와 일치했다. 1개는 부분 일치다. 대화 정렬은 「시간순」이 아니라 `turn_id`(bigserial) 오름차순, 곧 저장 순서다. 정밀화 3건도 넣었다: 운영 앱 루프백 전용, snapshot 은 생성 시각 기준 최근 500명, 미리보기는 앞 240자. 보강 1건은 제공기 미연결 503 이다.
- **UTIC 설명**(#62 백업 줄): 사실 6개 중 5/6 = 83.3% 가 일치했다(설정 20초, UTIC 조립에만 전달, httpx 단계별 대기, 다른 제공처 기본 8초, 재시도 없음). **「현재는 격리 구현·운영 검증 전」은 낡은 문장이다.** 링크된 10-18 보고서 73행에 따르면 12:20 KST 오라클 운영에 반영했고, 12:21:30 신규 조회는 HTTP 200·129건·7.327초(캐시 미사용)였다. 후보는 이 실측으로 바꿨다. 다만 지금 운영 배포본이 pin 과 같은지는 확인하지 않았다고 명시했다.
- **자동 시험 공백**: pin 에는 사용자 목록·대화 조회 API 시험이 없다. `utic_timeout_seconds` 시험도 0개다. 문서 후보와 별개로 시험 보강 후보로 남긴다.
- **백업 판을 통째로 쓰면 안 된다.** 백업 `external/index.md` 에는 pin 의 색인 5줄(운영 앱 화면 API·표시 이름·개발자 콘솔·Activity 공개 웹·모델 경로)이 없다. 백업 `watch-monitoring.md` 에는 pin 의 10-18 부분 실패 보존 문단이 없다. 그래서 후보는 pin 판에 해당 줄만 더했다.

## 후보

| 묶음 | 파일 | 내용 | 행 |
|---|---|---|---|
| A 문서(권장) | `final_project_cs/wiki/external/index.md` | 백업과 같은 위치에 관리자 사용자 계약 색인 1줄 | +2 |
| A | `final_project_cs/wiki/external/admin-users.md`(신규) | 작업트리 미추적 판에 위 정정·보강을 반영 + `[2026-10-27 대조]` 주석 | +40 |
| A | `final_project_cs/wiki/external/watch-monitoring.md` | UTIC 20초 문단(상태 문장 정정) | +2 |
| B 기록(선택) | `final_project_cs/wiki/records/reports/2026-10-18_admin-users-production.md` | 작업트리 미추적 원문 그대로 | +50 |
| B | `wiki/records/reports/2026-10-18_oracle-rain-traffic-diagnosis.md` | 작업트리 미추적 원문, CRLF→LF 만 바꿈 | +219 |

- 후보 커밋(격리 bare): A `55d36172…`(tree `50a626af…`), A+B `2f1b880b…`(tree `040df7de…`). 부모는 pin.
- A 만 넣으면 새 링크 2개(운영 반영 보고서, 오라클 보고서)가 끊긴다. B 까지 넣으면 A 링크 14/14·1/1 과 새 UTIC 링크가 모두 풀린다. 다만 B 의 두 기록 안에 있는 로컬 링크 8개(`.tmp/…`(gitignore), `_backup/…`(없음), 미추적 handoff)는 저장소에서 끊긴다. 기록 원문은 고치지 않는다는 규칙에 따라 그대로 두었다. B 를 넣을지는 담당자가 정한다.
- `watch-monitoring.md` 의 기존 끊긴 링크 10개(10-09~10-20 보고서)는 pin 에서 이미 끊겨 있던 것이고, 이번 후보와는 관계없다.

## 검증

| 항목 | 결과 |
|---|---|
| `git apply --cached --check` A on pin · A+B on pin · B on A | 3/3 통과, 적용 뒤 tree 가 후보 tree 와 같음 3/3 |
| `git diff --check` pin..A+B | 종료 0, 출력 0줄 |
| 후보 blob = 후보 파일 sha256 | 5/5 |
| 민감정보 | 비밀값·주소·키·사용자 식별값 0. 시각, 이미지 digest, 집계 수(62명·238개)만 있다. 오라클 보고서는 인증값 「있음/없음」만 적는다 |
| 원본 저장소 | 쓰기 0. `GIT_OPTIONAL_LOCKS=0`, ls-remote·읽기 명령만 실행했다 |

정적 대조만 했다. pytest·화면·서버 실행은 0건이다. 근거: [claims.json](../evidence/2026-10-27_finalspace-i2-doc-candidate/claims.json)(문장별 판정과 pin 파일:행, 파일·패치 sha256, 링크 결과), [i2-docs.patch](../evidence/2026-10-27_finalspace-i2-doc-candidate/i2-docs.patch) · [i2-records.patch](../evidence/2026-10-27_finalspace-i2-doc-candidate/i2-records.patch) · [i2-cumulative.patch](../evidence/2026-10-27_finalspace-i2-doc-candidate/i2-cumulative.patch). 작업 스크립트와 bare 저장소는 `cache/scratch/i2-doc-candidate-20261027/`(`build.py`·`mk.sh`·`claims.py`)에 있다. 24시간 동안 쓰지 않으면 정리될 수 있다.

## 남은 일

1. A(필요하면 B 도) 반영 여부를 정한다. 반영은 role-manager 담당이 pin 위에서 `git apply` 로 하고, 팀·개인 role-manager 에 함께 푸시한다. 이 작업에서는 푸시하지 않았다.
2. 시험 보강 후보: `/admin/api/users` 의 정렬·페이지·exact/contains·limit 필터, 대화 404/페이지 범위 초과, UTIC 조립이 설정값을 받는지 확인하는 단위 시험.
3. 운영 배포본이 pin 과 같은지(관리자 이미지, UTIC 20초)는 확인하지 않았다.
