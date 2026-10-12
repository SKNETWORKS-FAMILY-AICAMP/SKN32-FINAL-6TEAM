# 통합 뒤 재측정 — v3-domains (2026-10-08)

develop 통합(0bf4331 · 새 폴더 구조 `app/domains/travel_ops`)을 `role-dining` 에 합친 뒤 장소 찾기 · 대체 식당을 다시 쟀다.
앞 기록: [장소 찾기 v0~v2](2026-10-07_place_lookup_v0.md) · [대체 식당 v0~v2](2026-10-07_dining_alternatives_v0.md).

## 판

- 코드 `role-dining` **d76ecad · 작업 트리 깨끗**(`env.git_dirty=false`). ★처음 잰 결과는 커밋 전(5a32c83 + 미커밋 수정)이라 같은 날 d76ecad 에서 다시 쟀다 — **케이스마다 결과가 같았다.**
- DB `dining_rebuild`(원장 영업 중 1,888곳) · 카카오 실호출 · 모델 꺼짐 · 관광공사 **꺼짐**(`--tour off`, 아래 「관광공사」).

## 다시 재는 법

```powershell
cd final_project_cs
$env:ACOP_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5433/dining_rebuild"; $env:PYTHONPATH="..\final_project_sample"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m eval.runners.place_lookup --label v3-domains --kakao live --out eval\reports\2026-10-08_place_lookup_v3-domains.json
.\.venv\Scripts\python.exe -m eval.runners.place_lookup --label holdout_v3-domains --kakao live --dataset eval\datasets\place_lookup_holdout_v1.jsonl --out eval\reports\2026-10-08_place_lookup_holdout_v3-domains.json
.\.venv\Scripts\python.exe -m eval.runners.place_lookup --label v3-domains-kakao-off --kakao off --out eval\reports\2026-10-08_place_lookup_v3-domains-kakao-off.json
.\.venv\Scripts\python.exe -m eval.runners.dining_alternatives --label v3-domains --seeds 5 --mobility ..\datasets\mobility\processed --out eval\reports\2026-10-08_dining_alternatives_v3-domains.json
.\.venv\Scripts\python.exe -m eval.runners.dining_alternatives --label holdout_v3-domains --seeds 5 --mobility ..\datasets\mobility\processed --dataset eval\datasets\dining_alternatives_holdout_v1.jsonl --out eval\reports\2026-10-08_dining_alternatives_holdout_v3-domains.json
```

## 결과

| | v2-chain (10-07, 통합 전) | **v3-domains (10-08, 통합 뒤)** |
|---|---|---|
| 장소 찾기 개발 세트 정답 | 30/34 | **31/34** |
| 장소 찾기 개발 세트 ★틀린 곳을 확정 | 1 | **0** |
| 장소 찾기 확인 세트 정답 | 10/12 | **9/12** |
| 장소 찾기 확인 세트 ★틀린 곳을 확정 | 0 | **0** |
| 장소 찾기 카카오 끔(참고) | — | 14/34 |
| 대체 식당 개발 세트(5판 · 이동 계산기 켬) | 19/19 · 동선 위반 0 | **19/19 · 동선 위반 0** |
| 대체 식당 확인 세트 | 8/8 | **8/8** |

★표본이 작다(34 · 12 · 19 · 8건) — 한두 건 차이는 방향만 말한다.

## 통합 전과 달라진 케이스

| 케이스 | v2 → v3 | 왜 |
|---|---|---|
| PL-024 점심 한식 | 틀린 곳 확정 → **맞음(찾지 않음)** | develop 의 「이름이 아닌 말」 판정(`line_parts`)이 들어왔다 |
| PL-008 을지로 노가리골목 만선호프 | 틀림(골목) → **맞음** | 원문 전체로 카카오를 찾아 「원조만선호프」 |
| PL-029 Gwangjang Market | 맞음 → **못 찾음** | 전에는 카카오로 찾은 「광장시장」을 관광지 CSV 대체로 확인했다. 통합 뒤 CSV 대체가 빠졌고 이 평가는 관광공사를 끄고 쟀다 — 관광공사를 켠 운영 조립에서는 확인될 수 있다 `[미확인 — 이 PC 에 관광공사 키가 없다]` |
| PL-023 근처 국밥집 | 확인 필요(광화문국밥 1.1km) → **못 찾음** | ★아래 「근처 ○○집」 |
| PLH-10 근처 칼국수집(확인 세트) | 맞음 → **못 찾음** | ★아래 「근처 ○○집」 |

### ★「근처 ○○집」이 통합 뒤 못 찾는다 — 운영에도 해당

원장 이름 찾기(`LedgerPlaceLookup`)는 근처 기준을 `trip_api._PlaceCtx` 에서만 받는다. 통합 전에는 관광지 CSV 대체 · 카카오 근처 힌트 감싸개가
앞 일정(경복궁 등)의 좌표를 이 `ctx` 에 넣었다. 통합 뒤 두 감싸개가 빠져 `ctx` 에는 **원장에서 찾은 식당 좌표만** 들어간다.
접수는 앞 일정 좌표를 `places.resolve(near=…)` 로 넘기지만(`pipeline._near_hint`), resolve 는 그 `near` 를 원장 찾기에 넘기지 않는다.
→ 앞 일정이 관광지 · 카카오에서 찾힌 곳이면 「근처 국밥집」의 기준점이 없다. 평가 실행기는 운영(`trip_api.web_intake_start`)과 같은 조립이라 **운영도 같다.**
고칠 자리: `places.resolve` 가 원장 찾기에 `near` 를 넘기고, `LedgerPlaceLookup.find` 가 그 값을 `ctx` 보다 먼저 쓴다(별도 작업).

## 관광공사

- 이 평가는 `--tour off` 다(호출 한도 · 같은 결과). 운영은 관광공사를 실제로 부른다 — 관광지 확인이 필요한 케이스(PL-029)는 운영보다 낮게 나올 수 있다.
- `--tour live` 로 재려면 관광공사 키가 있어야 한다(이 PC 에서는 「관광공사 키가 없다」로 멈췄다).

## 남은 것

- 개발: 근처 국밥집(위) · Gwangjang Market(관광공사) · 소문난성수감자탕 별관(시험지 거리 20m 초과 — 시험지를 고치지 않는다).
- 확인(고치지 않는다 — 같은 유형을 개발 세트에 넣어 고친다): 이디야 홍대입구역 · 근처 칼국수집 · 남산돈까스.
- 카카오 호출 — 체인점은 이제 관련도 결과가 1km 안이어도 근처를 한 번 더 찾는다(d76ecad, 체인 1건당 +1~2회). 일일 예산 `travel.kakao_budget`(하루 1,000 · 달 31,000).
