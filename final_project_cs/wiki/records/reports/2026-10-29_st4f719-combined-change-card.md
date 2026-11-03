---
type: report
title: ST4F-719 시각·장소 동시 변경 카드의 정보 누락 격리 수정
status: draft
domain: travel
---

# ST4F-719 변경 카드

2026-10-29 KST. **같은 일정의 시각과 장소가 함께 바뀔 때 변경 카드가 시각만 보여 주는 결함을 격리 수정했습니다. 통합은 HOLD입니다.** 이전 장소가 사라지고, 제목이 일반적인 「점심」이면 새 장소도 카드에서 보이지 않았습니다. 제목을 새 장소로 바꾼 경우에도 이전 장소가 빠집니다. 원본 제품·운영 데이터 쓰기, push·배포·삭제·이슈 종결은 0건입니다.

## 선택·책임·작업 경계

루트 AGENTS·CLAUDE(루트 RULE 없음), CS AGENTS·RULE·CLAUDE, 양쪽 wiki 입구·handoff 목차, 개발 역할·여행 채팅 계약, 지정된 732 독립 검토 인계와 보고서를 읽었습니다. 조정 NOTICE 62개를 비공개 사본으로 읽고 보존했습니다. 최신 TeamFlow 전체 689건 중 미완료 103/689 = **14.9%**를 16개 상태×유형 묶음으로 다시 조회했습니다. 각 묶음은 500건 미만이며 고유 id 중복 0입니다.

ST4F-719는 high·review·assignee 빈 값입니다. 동급 high 항목들 가운데 기존 724·728·729·731·732·733·734·740 후보와 HOLD를 침범하지 않고 재현한 별도 제품 결함으로 선택했습니다. 현재 조정 기록에 이 파일을 예약한 담당은 없었습니다. 변경 담당·자체 검증은 이번 Codex 세션이며 **독립 검토자는 미배정**입니다. 아래 별도 경로 증거를 다른 사람의 독립 승인으로 표시하지 않습니다. 조정 메시지를 보내거나 다른 작업자의 사본을 변경하지 않았습니다.

732 좁은 시계 후보는 계속 HOLD입니다. 동일 입력의 새 실행 경계를 추정하지 않았고 run_id·withAnswers 계약을 변경하지 않았습니다. 718·731 HOLD도 유지합니다.

새 no-hardlinks 사본: `scratch/teamflow-product-next-20261029/repo`. 원격 role-manager `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`를 fetch 후 자체 가지에서 작업했고 마지막 ls-remote도 같은 tip입니다. 로컬 후보 `656579fe37d613a64caeb96cdb344958890a1c4d`는 그 위의 1커밋·2파일입니다. 원본 전체 복사·통합은 하지 않았습니다. 의존성 junction은 기존 설치본을 읽으며 설치본을 수정하지 않았습니다.

## 원인과 수정

`diffStops`가 같은 ID의 시각 변경을 먼저 검사하고 장소 변경은 `else if`로 검사해 하나만 기록했습니다. `Answer`는 그 행으로 변경 카드를 그리고 카드가 담당하는 서버 줄을 `coveredLines`/`shownText`로 생략합니다. 정상 여행 데이터의 `광장시장 12:00~13:00 → 남대문시장 12:30~13:30`에서 기존 행은 시간만 남습니다.

같은 날·같은 ID에서 시각 범위와 장소가 모두 바뀔 때 한 행의 before/after에 양쪽 값을 함께 넣었습니다. 단독 시각·장소 변경의 표시와 저장 형식, 단일 행·key, 서버/API·승인·실행 정책은 그대로입니다. 날짜 이동·신규 ID 교체 의미를 확대하지 않았습니다. 수정 파일은 `chat-diff.ts`, 새 회귀는 `chat-diff-combined.test.ts`뿐입니다.

## 실행 증거

| 실행 | 실측 |
|---|---|
| 최초 새 단위, 수정 전 | 1/3 = 33.3%, 두 결함 사례 실패 |
| 최종 새 회귀 | 4/4 = 100% |
| 기존 카드 포함 집중 시험 | 11/11 = 100% |
| 전체 웹 Vitest | 1231/1231 = 100%, 실패·skip 0 |
| 타입·표적 lint | 2/2 = 100%, 각 exit 0 |
| 별도 Edge 렌더, 기존 → 후보 | 2/5 = 40% → 5/5 = 100%, pageerror 0 |
| 실제 서버 ops_for·done_text 함수 | 2/2 = 100%, 같은 대상의 place+time 요청·새 값 응답 확인 |
| 전용 PG 계약 | 367/367 = 100% |
| DoD | 26/26 = 100% |
| 보안 | 124/125 = 99.2%, 기존 ST4F728 `security-ready.xml` 탐지 |
| 필수 관문 | **2/3 = 66.7%, HOLD** |
| 선정 보호 파일 SHA256 | 격리 185/185·원본 176/176 = 100% 동일 |

Edge는 실제 제품 `Answer`·관련 렌더 함수를 AST로 그대로 추출하고 실제 diff/카드/텍스트 함수를 연결했습니다. 하네스가 독립적으로 두 장소·두 시간의 DOM 존재를 판정했습니다. 시작·끝 시각 동시 변경, 끝만 변경, 제목도 변경, 시간만 변경, 장소만 변경을 비교했습니다. 합성 여행 fixture·간단한 하네스 CSS이며 전체 Next 앱·백엔드 API·DB 저장·실기기 수락이 아닙니다. 전후 screenshot도 직접 확인했습니다.

서버의 별도 실행은 실제 `replace_named` 요청 해석 함수가 같은 item_id의 place와 time 연산을 함께 만드는 것과 실제 응답 문구를 확인했습니다. 모델·네트워크·저장기를 호출하지 않았으며 동일 ID의 복합 변경이 저장부터 화면까지 이어지는 전체 수락은 남습니다. 준비 중 Python 모듈 이름 충돌과 누락된 fixture seq를 수정했으며 실패 로그도 사본에 보존했습니다. 다른 사람의 독립 검토나 운영 재현을 주장하지 않습니다.

명령은 웹 cwd에서 `node node_modules/vitest/vitest.mjs run`, 집중 두 시험 경로, `node node_modules/typescript/bin/tsc --noEmit`, 두 변경 파일의 eslint입니다. 서버는 `run_pg.py`로 `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`, `python -m scripts.verify_dod_v11`을 실제 실행했습니다. `backend_evidence.py`는 `-P`로 실행했습니다. 상세 runner·결과는 [증거 집계](../evidence/2026-10-29_st4f719-combined-change-card/validation-summary.json)와 [manifest](../evidence/2026-10-29_st4f719-combined-change-card/manifest.json)에 있습니다.

## 보존과 인계

scanner/XML 예외·내용 수정·이동·삭제 0입니다. 위 보존 분모는 시작 시 실제 읽어 선정한 경로 수이며 원본 전체 파일 검증 비율이 아닙니다. 보안 실패를 그대로 기록하고 병합·push·배포를 보류합니다. 초기 Git 기본 실행 파일의 접근 거부는 별도 설치 실행 파일로 해결했으며 원본 Git 조회는 safe_git 진입점을 사용했습니다. 최초 커밋 시 로컬 identity 부재를 기록했고 격리 커밋에만 Codex 이름을 지정했습니다. clone의 긴 경로 4개 진단도 로그에 보존했으며 원본 삭제·복원·색인 재구성을 하지 않았습니다.

전용 PostgreSQL `chat_cards_test`/56379의 DB명·포트·data_directory를 확인한 뒤 정상 종료했습니다. 연결 거부를 확인했고 pgdata와 모든 사본·로그·bundle은 보존했습니다. 원본 제품에 후보를 덮어쓰지 않았습니다.

검증 증거를 ST4F-719 본문에만 추가하고 review·미배정을 유지하는 정확 재조회 영수증은 [tracker-receipt.json](../evidence/2026-10-29_st4f719-combined-change-card/tracker-receipt.json)에 별도로 남깁니다. 전체 앱의 실제 저장 후 카드, 독립 검토자, 서버/휴대폰 수락은 미완료이며 운영 수락 분모 모름입니다. 다음 담당자는 좁은 [candidate.patch](../evidence/2026-10-29_st4f719-combined-change-card/candidate.patch)부터 검토하고 최신 tip에서 필수 3관문을 모두 충족해야 합니다.

[한 일·다음 담당 인계](../../../../wiki/handoff/2026-10-29_st4f719-combined-change-card.md).
