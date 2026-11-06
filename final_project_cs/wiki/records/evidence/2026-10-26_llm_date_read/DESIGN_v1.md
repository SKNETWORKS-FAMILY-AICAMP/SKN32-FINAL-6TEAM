# 날짜 읽기 LLM 판단 전환 — 설계안 v1 (Claude, Codex 검토용)

## 배경
- 위치: `final_project_cs/app/domains/travel_ops/components/intake/agent_read.py` (SCHEMA · SYSTEM · ground), `dates.py`(resolve_dates/_fill_year), `pipeline._agent_rows`, `conversation/chat_edit._read_adds`(채팅 넣기 = 같은 이해 에이전트).
- 현재 `ground`:
  - `relative = not re.search(r"\d", date_quote)` — 숫자 없는 인용이면 상대(모델 날짜 그대로, 확인 필요).
  - 그 외 `_year_written(when, quote, lines)` — 모델 연도 숫자(4자리)가 인용 **또는 본문 아무 줄**에 있으면 연도 명시로 본다. 없으면 `--MM-DD` 로 낮춰 `dates._fill_year`(오늘 포함 다가오는 날)가 채운다.
- 한계(규칙 기반): 본문에 「2026원」·전화번호 `010-2026-…`·예약번호가 있으면 연도 없는 「3/5」를 연도 명시로 오판 → 과거 → 전부-과거 가드가 거절. 2자리 연도 「'26.3.5」·「26/3/5」는 「2026」이 없어 연도 없음으로 오판 → 미래로 옮김. 「다음 달 5일」은 숫자가 있어 상대가 아님 처리.
- 사용자 확정 정책: 연도 없는 날짜 = 오늘 이후 처음 오는 그 날(오늘 포함), 연도 명시 과거만 과거, 상대 표현은 오늘 기준. 날짜는 규칙·정규식이 아니라 LLM 판단으로 어떤 형식(3/5, 3월 5일, 지난주 금요일, 작년 크리스마스, Mar 5th, 혼합)도.

## 제안
1. SCHEMA `items[]` 에 `date_form` 추가(required, enum `["year_stated", "relative", "month_day", null]`), 위치는 `date_quote` 바로 뒤(인용 뒤 판단).
   - `year_stated`: 메시지가 연도를 적었다(2026년 3월 5일, 2027-03-05, '26.3.5, Mar 5 2027, 머리줄 「2026년 여행」).
   - `relative`: 오늘에서 센 말(오늘·내일·모레·이번 주 토요일·지난주 금요일·다음 달 5일·작년 크리스마스·내년 3월 5일) — 연도까지 모델이 오늘 기준으로 계산.
   - `month_day`: 월·일만(3/5, 3월 5일, Mar 5th, 크리스마스) — 연도 없음.
   - date 가 null 이면 null.
2. 선택: `year_quote`(연도를 적은 원문 조각, 머리줄 가능, 없으면 null) — 머리줄 연도를 date_quote 와 분리해서 근거로.
3. `ground`(코드 = 사실 검사만):
   - `date_quote` 원문 존재(기존).
   - `year_stated`: 연도 근거 인용(year_quote 또는 date_quote)이 원문에 실제로 있어야 받는다. 없으면 연도를 버리고 month_day 로 취급(`--MM-DD`) + `report.dropped.date_year` 계수. (선택: 인용 안에 모델 연도의 4자리나 끝 2자리가 들어 있는지 — 값-인용 일치 검사)
   - `relative`: 모델 날짜 그대로, `date_guessed=True`(확인 필요, 기존 `agent_relative`).
   - `month_day`: `--MM-DD` → `dates._fill_year`.
   - `date_form` 누락/미지의 값(옛 기록 재생 등): 연도 근거 없음으로 보고 `--MM-DD` + 계수(조용히 연도를 믿지 않는다 — 미래 쪽이 안전: 과거로 오판하면 고객이 거절당함).
   - 정규식 `\d` 상대 판정과 본문 전체 `_year_written` 제거.
4. SYSTEM 프롬프트: 날짜 절을 다시 씀 — 세 형식 정의 + 한국어/영어/숫자형/혼합 예, 「숫자가 있어도 연도가 아닌 것(2026원, 전화번호, 예약번호)은 연도가 아니다」, 연도 없는 날짜의 date 는 여전히 YYYY-MM-DD(오늘 이후 처음 오는 날)로 내되 date_form=month_day. 예시 JSON 에 date_form 추가.
5. 측정: 30+ 합성 문장(연도 명시 과거/미래, 2자리 연도, 연도 없음 숫자형·한글·영문, 상대 과거/미래, 본문에 2026원/전화번호, 머리줄 연도, 혼합) × 실 E4B(로컬 Ollama `tripilot-pointer:e4b-ft`, 온도 0) before(현재 HEAD) / after. 채점 = `read_source` 끝의 `items[i].date` 값 == 기대값.

## Codex 에 묻는 것
- 더 나은 방법이 있나(예: 모델이 날짜 대신 「구성 요소(year/month/day/offset)」를 내고 코드가 계산? year_quote 별도 필드 vs date_quote 하나?).
- year_stated 검증에 「인용 안에 연도 숫자」 검사를 둘지(값-근거 일치 vs 규칙 냄새).
- date_form 누락 시 처리.
- E4B(LoRA 학습된 모델, 기존 스키마로 학습)에서 필드 추가의 위험.
