# A11 ready 올림 독립 보안 검토 재개

2026-10-29 KST. 검토자 Codex. 구현 담당 Hermes의 중단 로그 `deleg_8ce43783/task-0.log`와 `2026-10-29_routing-a11-reopen-kind-question-ready.md`를 이어 읽었습니다. 후보 `C:/_proj/routingresume1029`와 기존 PostgreSQL 16.15 loopback `:63941/a11_readyreview`를 재사용했습니다. 새 clone, 설치, 운영 변경, 삭제, 커밋, push는 없습니다.

## 판정

검토한 A11 ready 올림에서 권한·등록 필수 차단·판 충돌을 우회하는 새 결함은 발견하지 못했습니다. **릴리스 승인은 아닙니다. 보호 XML 보안 HOLD로 통합·push 보류를 유지합니다.**

- `pipeline.view`는 tenant·customer가 일치한 현재 접수를 조회하고 같은 revision의 검사를 읽습니다. `review.ready_now`는 현재 조립 성공·일정 있음·검사 완료·needs.total=0일 때 응답 복사본의 ready만 올립니다. 저장된 intake_reviews는 바꾸지 않습니다.
- 등록은 응답 ready를 받거나 신뢰하지 않습니다. 실제 조립 문제(`kind_unanswered` 포함), 미룬 검사, revision, 고객 소유권, 식당 필수 조건을 따로 검사합니다. 미답 직접 confirm=422, 다른 고객 조회·답·등록·SSE=404, 오래된 답·등록=409, 미검사 등록=409를 실 DB 시험으로 확인했습니다.
- 확인 필요가 남은 판은 ready가 false입니다. 다만 **needs는 등록 필수 차단이 아닙니다.** 기존 계약 `web-intakes.md`의 ready 설명대로 확인 필요를 남긴 직접 등록은 200일 수 있습니다. 이를 권한 우회라고 판정하거나 이번 작업에서 계약을 바꾸지 않았습니다.
- 앞 독립 검토가 찾은 SSE done.ready 불일치는 후보의 `review.ready_now` 공용 함수로 수정되어 있습니다. GET과 재연결 SSE가 같은 ready를 내는 것을 재확인했습니다. 수정 전 RED 및 수정 후 15건 실행은 기존 증거에 보존되어 있습니다. 이번 Codex 세션은 제품 코드를 변경하지 않았습니다.
- 웹 held 질문은 서버의 kind_unanswered·source·item을 대응하며 서버 선택지를 기존 interpretations API로 보냅니다. UI를 건너뛰는 직접 등록도 서버에서 거부됩니다.

## 증거와 실행 범위

기존 증거 `C:/_proj/routinga11readyreview1029_evidence`를 유지했습니다. 코드·계약·독립 시험 5/5 = 100%가 중단 당시 `after-sha256.txt`와 같고, 보호 XML 336/336 = 100%가 최초 manifest와 같습니다(`codex-preservation.json`).

| 실행 | 결과 | 구분 |
|---|---|---|
| 독립 API·실DB 시험 | 9/9 = 100%, 134.89초 | 이번 재실행 |
| 웹 from-review·model | 69/69 = 100% | 이번 재실행 |
| 접수 E2E 전체 | 442/442 = 100% | 중단 후 완료된 XML·로그 확인 |
| 회귀 | 1526/1526 = 100%, live 245 제외 | 기존 실행 증거 |
| 추가 | 749/751 = 99.73%, 2건 건너뜀 | git 밖 자료 없음, 기존 실행 |
| 계약 | 367/367 = 100% | 기존 실행 증거 |
| 보안 | 124/125 = 99.2%, 실패 1 | 보호 XML 기존 HOLD |
| DoD | 26/26 = 100% | gate_dod/evidence/summary.json |

브라우저는 새로 실행하지 않았습니다. 실제 FastAPI·실 DB·Edge로 만든 `shots/20-reopen-day3.png`, `22-reopen-press.png`, `24-reopen-register.png`와 본문·실행 로그를 검토했습니다. 22번 화면은 미답 종류를 골라 달라는 안내이고, 24번은 전송 중 화면이므로 **그 그림만으로 등록 완료를 주장하지 않습니다.** 등록 200·DB confirmed는 기존 로그 및 이번 실DB API 시험으로 확인합니다. 외부 모델·공공데이터·카카오는 대역이고 지도 타일은 차단되어 있습니다.

## 유지할 한계

보호 XML을 수정·삭제·검사 예외 처리하지 않았습니다. 알려진 보안 실패는 `tests/security/test_no_infra_in_tracked_files.py`의 기존 보호 XML 1건입니다. XML의 발견 문자열은 보고서에 복제하지 않습니다.

짝 없는 체크아웃의 숙박 선택 effect 문구 부정확성, 질문 없는 체크아웃 UI, 호텔 좌표·이름 중복, 실제 모델·운영 환경 검증은 앞 인계대로 남깁니다. 등록 여행 reopen의 기본 경로에는 종류 질문이 남지 않는 시험이 있으나 모든 수정 모드 조합의 화면 검증은 아닙니다.

`GET은 쓰지 않는다`는 앞 문구는 **ready 올림이 저장 검사에 쓰지 않는다**는 범위로 읽어야 합니다. view에는 기존 stalled 처리·설문 계산 경로도 있으므로 GET 전체의 무부수효과를 보증하지 않습니다.

디스크 inventory: 등록 entries 0, unregistered_dirs 0, C: 여유 183,113,699,328 bytes(최소 32,212,254,720 초과·목표 400,000,000,000 미달). 기존 evidence 약 4.0 MB, PG는 기존 것을 재사용했고 새 DB 전체 사본은 없습니다. PG는 재개 시 이미 실행 중이어서 다른 세션 소유일 수 있으므로 중지하지 않았습니다. 이번 세션이 띄운 서버·웹은 없습니다. 가드가 모든 파일 쓰기를 막는다는 뜻은 아닙니다.

실행 명령: `A11KP_DB=a11_readyreview python C:/_proj/routinga11readyreview1029_evidence/run.py codex_resume tests/e2e/test_intake_kind_ready_independent_review.py -q -s` (PowerShell에서는 `$env:A11KP_DB`로 지정). 웹은 기존 Node 실행기로 `node_modules/vitest/vitest.mjs run --config a11-reopen.vitest.config.mts src/features/plan-check/from-review.test.ts src/features/plan-check/model.test.ts`를 실행했습니다.
