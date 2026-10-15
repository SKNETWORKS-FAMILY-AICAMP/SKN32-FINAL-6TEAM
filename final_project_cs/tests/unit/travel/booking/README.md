# 숙소 · 항공 확장 에이전트 시험 (`tests/unit/travel/booking/`)

2026-10-12 정리. 숙소(`instances/lodging`) · 항공(`instances/flight`) 팀, 공용 날짜 검증, booking 모듈, 바깥 소스 어댑터(마이리얼트립 · Ignav · SerpApi 구글 항공 · 호텔)의 시험이다.
모델 · 네트워크 · DB 없이 돈다(전부 가짜). 이동 모듈 시험 폴더와 같은 방식으로 **두 층**으로 나눈다 — 잠그는 것은 줄이지 않고 층만 나눴다.

## 두 층

| 층 | 명령 | 무엇 |
|---|---|---|
| **병합 게이트(기본)** | `python -m pytest tests/unit/travel/booking -q` | 주요 기능마다 시험 하나 — 「이게 깨지면 그 기능이 죽은 것」. 목록은 `conftest.py` 의 `GATE`(시험 이름 → 깨지면). develop CI(`tests/unit` 전체)도 이 층만 돈다 |
| **우리 전체** | `python -m pytest tests/unit/travel/booking -m "booking_full or not booking_full" -q` | 게이트 + 측정에서 나온 문장 모양 회귀 · 소스별 세부(쉬는 중 · 링크 모양 · 판매처 합치기 · 시간대 …). 고친 뒤와 방을 닫을 때 우리가 돌린다 |

- 게이트 밖 시험은 skip 이 아니라 deselect — 요약 줄에 「N deselected」로 보인다.
- 한 건만: `-m booking_full -k <이름>` (`-k` 만 주면 게이트 밖 시험은 「no tests ran」).
- `test_booking_gate.py` 가 게이트 목록의 이름이 실제 시험을 가리키는지, 새 시험 파일에 게이트가 있는지 본다.

## develop 병합 전에 돌릴 것

develop CI(`.github/workflows/ci-develop.yml`)와 같은 것을 로컬에서 먼저 돌린다.

```powershell
# 1) 린트 — 저장소 맨 위에서(규칙은 ruff.toml: F · E9). CI 와 같은 판
cd C:\final_project\SKN32-FINAL-6TEAM_check
pip install ruff==0.16.8
ruff check .

# 2) 우리 시험 — 두 층
cd final_project_cs
python -m pytest tests/unit/travel/booking -q
python -m pytest tests/unit/travel/booking -m "booking_full or not booking_full" -q

# 3) 우리가 고친 공용 자리 — 조립 등록 · migration · 키 템플릿
python -m pytest tests -q -k "wire_domain or composition or migration or team_hooks" --ignore=tests/contract/test_declared_refs_are_savable.py --ignore=tests/e2e
python -m pytest tests/contract/test_api_key_file.py -q

# 4) CI 와 같은 묶음 — 로컬 DB(5433)를 켠 뒤
python -m pytest tests/architecture tests/contract tests/unit -q --ignore=tests/contract/test_declared_refs_are_savable.py
python -m pytest tests/security -q
```

- 4) 는 DB 가 꺼져 있으면 `test_active_prompts_are_the_deployed_set` · `test_consumer_idempotency_contract` · `test_mcp_opens_a_classified_case` 가 연결 시간 초과로 붉다. `acop_composer` 가 없으면 `test_declared_refs_are_savable` · `test_the_registry_and_the_catalog_agree` · e2e `test_composer_write_channel` 이 붉다(CI 는 `PYTHONPATH` 에 `final_project_sample` 을 둬서 돈다). 둘 다 우리 변경과 무관.
- 실제 소스 · 모델은 pytest 가 부르지 않는다. 손으로: `python -m scripts.try_itinerary_item …`(일정 항목 「바꿔 줘」), 해석 평가(`scripts/interpret_cases.json`).

## 파일별 — 무엇을 보나 (게이트 수 / 전체)

| 파일 | 대상 | 게이트 | 전체 |
|---|---|---|---|
| `test_lodging_team.py` | 숙소 팀 — 해석은 모델, 검증 · 조회 · 답은 서버. 검색 · 되묻기 · 「내 숙소」 · 거리 · 일정 항목(후보 3 · 고르기 · 예약 불변) | 10 | 38 |
| `test_flight_team.py` | 항공 팀 — 검색 · 소스 합치기 · 시간대 · 직항/경유 · 1인 가격 상한 · 왕복 · 일정 항목(새 편 · 원래 시각 근처 먼저 · 고르기 · 예약 불변) | 12 | 39 |
| `test_lodging_ledger.py` | 우리 원장(보여 준 후보 · 고른 숙소 → 여행 전용 장소)과 조립 끼움 자리 | 3 | 5 |
| `test_interpret_dates.py` | 숙소 · 항공 공용 날짜 검증 — 문장 근거 · 연도 · N박 · 뒤집힌 날짜 + 측정 문장 모양 회귀 | 3 | 18 |
| `test_booking_module.py` | booking 모듈 — 소스 부르기(동시) · 합치기 · 쉬는/없는 소스 · 링크 | 4 | 8 |
| `test_myrealtrip_source.py` | 마이리얼트립 MCP 어댑터 — 응답 읽기 · 실패 세기 · 429 쉬기 | 4 | 17 |
| `test_ignav_source.py` | Ignav MCP 어댑터 — 응답 → 공용 모양 · 실패 세기 | 2 | 6 |
| `test_serpapi_flights_source.py` | SerpApi 구글 항공 — 응답 → 공용 모양 · 실패 세기 | 2 | 5 |
| `test_serpapi_hotels_source.py` | SerpApi 구글 호텔 — 응답 → 숙소 모양 · 없음 세기 | 2 | 4 |
| `test_booking_gate.py` | 게이트 목록 자체 | 2 | 2 |

함수 단위 「깨지면 무엇이 죽었나」는 `conftest.py` 의 `GATE` 에 한 줄씩 있다.
