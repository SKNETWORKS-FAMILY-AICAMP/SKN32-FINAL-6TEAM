# 39번 방 GPT 대조 묶음 (규칙 21) — 2026-09-24

아래를 GPT 에 그대로 주고, 첨부로 `_39\verify_time.diff` (1,036줄) · `_39\selfcheck.diff` · `_39\runtime.diff` · `tests\mobility\judgment_legs_v1.json` 을 붙인다.
받은 답은 `## GPT 대조` 절에 채택/기각/보류로 옮긴다(인계 문서 `claude/인수인계/39_코드_판정계약v08_인계_20260924.md`).

---

## 프롬프트

너는 대중교통 구간 판정기(Python)의 변경을 대조하는 검토자다. 결함 후보 · 안 잰 가정 · 빠진 회귀 축만 낸다. 문체·이름은 보지 않는다. 각 항목 ≤4줄, 심각한 순, 최대 15개.

### 설계 의도(v0.8)
- 구간 열을 두 번 통과한다: **best**(종전 계산 · 예정 시각) / **worst**(버스 대기 = 배차 전부 · 환승은 최악 도착에서 다음 편 · 혼잡 매우혼잡+조건이면 같은 경로 다음 편 · 정책 버퍼 10/15분을 @에 더함).
- **판정은 worst, 표시는 best + @**. @ = (최악 도착 − 예정 도착) + 버퍼. slack_min = 도착 목표 − 예정 − @ (음수 → 불가 arrive_late).
- 밖 판 `CaseResult.out`: verdict 둘(feasible/infeasible) + 이유 코드 10종(no_data·before_first·after_last·service_gap·no_service·disruption·transfer_walk·arrive_late·over_limit·mode_unavailable). 내부 4값 verdict·등급은 그대로(접기·자기점검·로그용).
- `last_feasible_depart_min`: 같은 worst 판정기로 출발 시각을 뒤에서부터 역산(지하철 첫 구간 = 편성 목록, 버스 = 막차/도착 목표에서 1분씩 첫차까지, 자동차·자전거 첫 구간 = None). 상한 600회(MOB_W_LFD_CAP).
- 버스 승차·자동차·자전거 스프레드(p90)는 근거 없음 → worst = best + MOB_W_WORST_NO_SPREAD. 값을 지어내지 않는다.
- 회귀 `expect` 는 밖 판정 둘, 옛 4값은 `expect_internal`, `expect_reason`·`expect_slack_min`·`expect_margin_min`(범위)·`expect_last_depart`.

### 이미 대조한 것(자체 대조 1회 · 13건 중 11 채택) — 같은 걸 다시 내지 말 것
1. 혼잡 다음 편이 순환선 반대 방향 편성을 집던 결함(@94) → 같은 방향·같은 경로만.
2. worst 통과가 도착을 못 내면 예정=최악 + 경고.
3. 자동차·자전거 첫 구간 역산 없음 + 케이스 안 구간 캐시(라우터 호출 폭주 방지).
4. 역산 상한 경고. 5. multi 밖 판은 후보 밖 판으로. 6. multi 도착 목표에 이탈 도보 반영, 후보 out 을 출발지 기준으로 되돌림.
7. worst 실패 대안도 worst 로. 8. 경고·근거 중복 제거. 9. 혼잡 warning 액션 구현. 10. 다음 편 없음 경고.
보류: lfd 를 out 에 싣는 것(32 입력이라 싣고, 코어 계약에서는 32 가 뺀다) · 막차 근처 매우혼잡의 「다음 편 없음」은 경고만.

### 특히 의심할 곳
- `_chain` 의 worst 통과에서 구간이 arrive None 을 내는 경우.
- `_last_feasible_depart` 의 단조성 가정(늦게 떠나면 늦게 닿는다)이 깨지는 입력 — 배차 공백·한 바퀴 편성.
- `_congestion_hit` 의 방향·요일 매핑(시간표 dir U/D ↔ 혼잡도 dir U/D · 1~8호선 3종 요일 vs 9호선 2종 · 슬롯 30분 · 24시 넘김).
- `Congestion.load` 가 `cg or None` 을 돌려주는 것(`__bool__` 정의됨).
- verify_multi 의 `nf`(내부) vs `nf_out`(밖) 분리, 등급 계산은 아직 내부 nf.
- 정책 버퍼를 수단 무관하게 @에 더한 결정(41 버스 p90 전까지) — 스펙 v1.3 은 「지하철 포함 경로만 buffer_min」이다. 이 차이가 32 에서 문제가 되는지.

### 회귀 결과(클라우드 · 라우터 없음 · car/bike 픽스처)
- 옛 기대값으로 v0.8 을 돌린 장면: MISS 14건(unknown/rejected_by_limit 어휘 밖 6 · 성립인데 예정 없음 → no_data 2 · multi 5(밖 판 조립 결함, 고침) · 기타 1).
- 재정의 뒤: 10묶음 137건 어긋남 0 (123 + judgment 14). 내부 {feasible 84, infeasible 43, unknown 7, rejected 3} / 밖 {feasible 83, infeasible 54}.
- 자기점검 9,776 탐침: 판정 분포 v0.7 과 동일(3272/6128/376) · 이상 4(INV-UNKNOWN 4) · 새 불변식 INV-WORST·INV-OUT 0건 · 단위시험 13/13.
- check_fold 12 · runtime 26 · adapter 30 · rules_check 통과.
