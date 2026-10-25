---
type: report
title: 날짜 읽기를 모델(E4B) 판단으로 — date_form · year_quote, 정규식 연도 판정 제거
status: draft
domain: travel
---

# 2026-10-26 날짜 읽기 LLM 판단 전환

작업 위치: 격리 worktree `scratch/mgr-merge-20261026-0045`, 브랜치 `feat/past-date-guard-ext-20261026`(앞 커밋 `337bcbd68` 위). 원본 `C:/_proj/final_workspace` 는 건드리지 않았다. 커밋까지만 — push · 배포 · 로컬 서빙 교체 없음. 실DB 쓰기 0 · 유료 API 0 · 실모델은 로컬 Ollama E4B 만.

## 문제

앞 커밋의 `agent_read._year_written` 은 「모델 연도 숫자가 날짜 인용이나 **본문 아무 줄**에 있으면 연도를 적은 것」으로 봤다. 규칙이라 다음이 틀렸다(실측 before):

- 본문에 「입장료 2026원」 · 전화번호 `010-2026-…` · 예약번호 `2026-1105` → 연도 없는 「3/5」를 2026-03-05(지난 날)로 → 전부 과거 거절 위험. 소음 표본 4/4 실패.
- 「'26.3.5」 → 「2026」 글자가 없어 연도 없는 날(2027)로.
- 숫자 없는 인용만 상대 날짜로 봐서 「다음 달 5일」은 상대 날짜가 아니었다.

사용자 지시: 날짜는 규칙 · 정규식이 아니라 LLM 판단으로 어떤 형식이든. 확정 정책: 연도 없는 날짜 = 오늘 이후 처음 오는 그 날(오늘 포함) · 연도를 적은 과거만 과거 · 상대 표현은 오늘 기준.

## 바꾼 것

| 곳 | 변경 |
|---|---|
| `agent_read.SCHEMA` items | `year_quote`(고객이 적은 연도 조각, 머리줄 가능) · `date_form`(`explicit_year` · `relative` · `yearless` · null) 추가(필수). 출력 순서 `date_quote → year_quote → date_form → date`(인용 → 판단 → 값, Codex 권고) |
| `agent_read.SYSTEM` | 날짜 절을 새로 씀: 세 형식 정의 + 한국어 · 영어 · 숫자형 · 한글 숫자 · 기념일 예, 「가격 · 전화 · 예약번호 · 시각 숫자는 year_quote 가 아니다」, 연도가 date_quote 안에 있어도 year_quote 로 복사, 상대 날짜 값 예(어제 · 이번 주/다음 주/지난주 수요일 · 다음 달 10일)와 연도 없는 날 예(8/15 · 5일 전 월일 → 다음 해 · 오늘 월일 = 오늘). **예시 값은 `system_for` 가 오늘에서 계산**한다(고정 날짜가 시간이 지나 틀려지지 않게). 「Today」 줄에 어제 · 그제 · 글피 · 「이번 주 X = 월~일 주의 X」 추가 |
| `agent_read._grounded_date`(새, `_year_written` 과 `\d` 상대 판정 제거) | 코드는 원문을 다시 읽지 않고 인용 존재 · 필드 일치 · 달력 유효만 본다. explicit_year: `year_quote` 가 원문에 있으면 모델 날짜 그대로 / 없으면 연도 없는 날로 두고 `dropped.date_year` + `year_unverified` · relative: 모델 날짜(지난 날 포함, `agent_relative` 확인 필요) · yearless: `--MM-DD` · 형식 칸 없음/모르는 값: 날짜 버림 `dropped.date_form`(날짜가 비어도 칸이 없으면 센다) · relative/yearless 인데 연도 인용이 원문에 있음: 모델 형식 따르고 `dropped.date_mismatch` · 달력에 없는 날: 버림 `dropped.date` |
| `dates.next_month_day` / `_fill_year` | 연도 없는 「2/29」는 다음 윤년(전에는 다음 해 2월 28일로 조용히 바꿈). 어느 해에도 없는 월 · 일(「2/30」)은 `ValueError` → `resolve_dates` 가 `unknown`(확인 필요, 「없는 날짜예요」) |
| `dates.resolve_dates` 메모 | `year_unverified` 항목은 「연도를 원문에서 확인하지 못해 … 다가오는 날로 두었다 — 다르면 고쳐 주세요」(how 는 그대로 `year_filled` — 웹의 「해를 ○○년으로 두었어요」 표시가 그대로 붙는다) |
| `pipeline._agent_rows` | 항목 dict 에 `year_unverified` 전달 |
| 채팅 넣기 `chat_edit._read_adds` | 코드 변경 없음 — 같은 `ground` 를 거쳐 같은 계약(본문 「2026원」이 있어도 다가오는 3/5 로 넣는다, 시험 추가) |
| 계약 | [`web-intakes.md`](../../external/rest-endpoints/web-intakes.md) 「읽는 순서 → 날짜」에 모델 판단 계약 한 단락 |

하드코딩 점검(추가된 비시험 줄): 고객 원문 키워드 · 정규식 매칭 0. 남은 리터럴은 스키마 enum(`DATE_FORMS`), 프롬프트 예시 문장, 달력 검사용 윤년 상수(`LEAP_YEAR=2000`, 값이 아니라 「있는 날인가」만 본다).

## Codex 논의(codex-cli 0.163.0, `codex exec -s read-only`, 로그인 확인 `Logged in using ChatGPT`)

1. 1차(`codex_run_v1.log`): 샌드박스가 파일 읽기 명령을 막아 설계 파일을 못 읽음 → 일반론만. 2차(`codex_review_v2.md`): 설계서 · 코드 발췌를 stdin 으로 보냄. 3차(`codex_review_v3.md`): 구현 diff · 실측 요약 검토.
2. **반영**: enum 이름 `explicit_year/relative/yearless` · `year_quote` 분리(머리줄 연도) · 출력 순서 · 인용 안 연도 숫자 검사 넣지 않음 · 형식 칸 누락 = 계약 오류(날짜 버림, 연도 없는 날로 바꾸지 않음) · 2/29 윤년 · 불가능 날짜 28일 보정 제거 · 프롬프트에 대조 예시 · 기존 예시 JSON 에 새 칸 · 날짜 비어도 형식 칸 누락 집계 · relative/yearless + 연도 인용 어긋남 집계 · 오염된 holdout1 을 독립 근거로 쓰지 않음.
3. **반영하지 않음(이유 · 되돌릴 수 있음)**: 「explicit_year 인데 연도 인용이 원문에 없으면 날짜 미확정으로」(3차 필수 권고). 실측에서 이 경로를 탄 7건 = 연도 없는 날을 모델이 explicit_year 로 잘못 낸 4건(그대로 믿으면 2건이 지난 날 → 전부 과거 거절: 「10월 25일」 · 「1월 1일」) + 상대 1건(「내년 3월 5일」, 값 맞음) + 강등으로 틀어진 2건(「'26.3.5」 → 2027, 「작년 6월 10일」 → 2027). 미확정으로 바꾸면 맞던 5건도 날짜를 잃고 틀린 2건은 고쳐지지 않는다. 강등은 `year_filled`(확인 필요) + 별도 메모로 보이고, 틀어지는 방향이 「다가오는 날」이라 거절이 아니라 고칠 수 있는 확인으로 남는다. 정책 문장 「연도를 **명시**한 과거만 과거」에서 원문 근거 없는 연도는 명시가 아니라고 읽었다.
4. **범위 밖(남김)**: 모델이 날짜를 비웠을 때 `dates._relative_for_item` 이 원문에서 「오늘/내일/모레…」 6낱말을 정규식으로 찾는 규칙 경로(규칙 읽기와 공용, 이번 변경이 진입을 늘리는 경우는 형식 칸 누락 · 달력 없는 날뿐). 합성 인용(머리줄 + 줄을 합친 date_quote)으로 날짜를 잃는 경로의 재시도 · 확인. 모델 재시도 루프.

## 실측(로컬 E4B)

모델 `tripilot-pointer:e4b-ft`(Ollama `http://127.0.0.1:11434`, num_ctx 8192) — 주소 · 모델 · num_ctx 는 지금 로컬 서빙의 `launch-serving.py` 가 넣는 `ACOP_OLLAMA_*` 값을 읽어 제품과 같은 `ollama_chat._build(settings, "local")` 로 만들었다(넘김 장치 꺼짐 = 유료 경로 없음). 온도 0 · think false · 스트리밍 읽기(가드레일 `travel.intake_reading` 기본값) · `pipeline.read_source(agent_mode="on")` 전체 흐름 · today=2026-10-26(월). 러너는 그 Ollama 포트 외 socket · psycopg 차단, 행마다 서빙 카운터 유휴 확인, E4B 임대(`_coord/e4b_lease.py`) 안에서만 호출. 채점 = 최종 `items[i].date` 값 목록이 기대값과 같음(항목 수가 다르면 실패 — g16 · h19 는 날짜는 맞고 항목이 2개로 읽혀 실패). 표본은 모두 합성(고객 원문 아님). before = HEAD `337bcbd68` 의 `git archive` 사본.

| 표본 | before | after |
|---|---|---|
| 개발 41(한/영/숫자/한글숫자/기념일/상대/2자리 연도/머리줄 연도/「2026원」 · 전화 · 예약번호 소음/혼합) — 프롬프트를 고칠 때 봄 | 28/41 = 68.3% | A 34/41 = 82.9% → B 38/41 = 92.7% → **C 39/41 = 95.1%** |
| 보류 1 · 20 — C 를 고칠 때 실패 3건(다음 주 수요일 · next Wednesday · 글피)을 봤다 → **독립 근거 아님** | 14/20 = 70.0% | B 15/20 = 75.0% → C 17/20 = 85.0% |
| 보류 2 · 20 — C 이후 새로 만든 깨끗한 표본 | 12/20 = 60.0% | **C 15/20 = 75.0%** |

- 가장 해로운 오류 「다가오는 날을 지난 날로(전부 과거 거절 위험)」: before 5 · 2 · 3 = 10건 → after 0 · 1 · 0 = 1건(보류1 「작년 이맘때 … 1월 10일」이 「작년 이맘때」를 날짜로 읽음).
- 개발 묶음 갈래별 before → after C: 소음 0/4 → 4/4, 연도 없음 9/12 → 12/12, 상대 8/12 → 11/12, 연도 명시 9/10 → 9/10, 혼합 2/3 → 3/3.
- 남은 실패(after C): 「'26.3.5」(year_quote 를 비움 → 다가오는 날로) · 「11월 둘째 토요일」(날짜 비움) · 「이번 주 일요일」(하루 앞 토요일로 계산) · 「어린이날」(relative 로 보고 날짜 비움) · 「작년 6월 10일」(explicit_year + 원문에 없는 「2025」 → 다가오는 날로) · 「2026년 가족여행 / 11월 3일」(원문에 없는 합성 인용 → 날짜 버림) · 항목 중복 2건.
- 지연 중앙값(같은 시각대 비교 가능한 보류1): before 4.14초 → after 4.53초(+약 0.4초, 프롬프트 길이 · 새 칸). 개발 before 는 19.2초로 다른 GPU 부하 시간대라 비교에서 뺀다.
- 표본 크기가 작다(81문장). 서비스 전체 성능으로 일반화하지 않는다. 학습(LoRA)은 하지 않았다 — 새 칸은 프롬프트로만 가르쳤다.

증거(합성 표본 · 러너 · 결과 · Codex 기록): [`records/evidence/2026-10-26_llm_date_read/`](../evidence/2026-10-26_llm_date_read/).

## 시험(TDD)

격리 runner(`scratch/llm-date-read-20261026/run_isolated.py`, socket · psycopg 차단, 고유 root 변수 `LLMDATE_SOURCE_ROOT`) · Python 3.12 venv(`date_risk_env_312`, 비동기 시험은 `-p pytest_asyncio.plugin` 명시).

- RED: `red-llm-date-form.log`(새 파일 첫 판 9 실패/11 — 채팅 넣기 1건은 대역 시각 인용 오류였음) → 대역 고친 뒤 기준 모듈로 다시: `red2-chat-add-baseline.log`(채팅 넣기가 「2026원」 때문에 「혹시 오타 아닌가요?」로 거절 — 기능 RED 확인), `red3-baseline-full-newfile.log`(HEAD `agent_read` · `dates` 로 새 파일 10 실패/12). 마지막 2건(별도 메모 · 계약 집계)은 구현 뒤 작성 — RED 없음.
- 새 계약으로 옮긴 시험 대역(단언은 그대로): `test_yearless_agent_dates` · `test_intake_agent_read` · `test_intake_interpretations` · `test_intake_move_lines` · `test_intake_schedule_cards` · `test_intake_transport_scope` · `test_intake_agent_meal_order` · `test_chat_edit_reader` · `test_chat_past_date_typo` · e2e 2개(`test_intake_interpretations_api` · `test_intake_reading_prefs`, DB 필요 — 못 돌림).
- GREEN: 새 파일 14/14, 관련 묶음 결과는 아래 「최종 실행」.

## 최종 실행

(커밋 직전 안정 트리 · 실행 전후 해시 대조)

- 관련 묶음(새 파일 + 대역을 옮긴 9파일 + 날짜 · 과거 가드 · 읽기 흐름 4파일): **150/150 = 100%**(`focused-final.xml`).
- `tests/unit/travel` 전체: 7397 passed / 128 skipped / 464 deselected, 실패 2 · 오류 6 — 8건 모두 runner 의 DB 차단(7건 `network/database denied`, 1건은 공유 DB 캐시 시험이 DB 없이 제공처를 다시 부른 것). 앞 커밋 세션의 비통과 nodeid 와 같다(`diff` 0). 차단 외 실패 0.
- `tests/architecture` · `contract` · `security`: 617 passed, 실패 13 · 오류 6 — 19건 모두 DB 차단, 앞 세션 비통과 목록과 같다. 증거 폴더를 넣은 뒤 `tests/architecture` 다시 168/168 = 100%.
- 실행 전후 변경 Python 15파일 sha256 같음. ruff F·E9 통과, `git diff --check` 통과.
- 실DB e2e(대역을 옮긴 e2e 2개 포함) · 웹 시험은 실행하지 않음(웹 코드 변경 없음).

## 남은 것

- 위 「범위 밖」 3가지, 그리고 남은 실패 유형(2자리 연도 year_quote 비움 · 「N째 주 X요일」 · 「이번 주 일요일」 계산 · 기념일 상대 분류 · 합성 인용)은 프롬프트만으로 더 줄이기 어렵다 — 새 칸을 넣은 학습 자료로 LoRA 재학습을 검토(별도 승인 필요).
- 실DB e2e · 실화면 · x600 서빙 확인 안 함. 로컬 서빙 교체 안 함(지금 로컬 서빙은 옛 프롬프트).
