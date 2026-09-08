# capability 선택을 LLM 에게 시키면 나은가 — 재봤다

## 왜 쟀나

재설계 선택지가 셋이었다(`2026-09-03_S-CAPABILITY-SELECTION-측정_리포트.md`).

```
A 분류 라벨 세분화     intent 어휘를 늘린다 — 분류기·계약까지 건드린다
B 매니페스트 선언 확장  default_capability 같은 선언을 더 정교하게
C 짧은 LLM 판단        ← 이 리포트
```

C 를 먼저 잰 이유는 **사람 감사 없이 지금 잴 수 있는 유일한 선택지**여서다.
A·B 는 "라벨이 맞나 휴리스틱이 맞나" 가 정해져야 방향이 나온다.

## 결과

golden 라벨 60건, 같은 조건(`temperature=0`·`seed=7`), 팀이 실제로 가진
capability 목록만 제시.

| | 라벨과 일치 |
|---|---|
| 키워드(지금 방식) | 25/60 = **41.7%** |
| LLM (첫 시도) | 30/60 = 50.0% |
| **LLM (편향 제거)** | 36/60 = **60.0%** |

## ★첫 시도는 내 프롬프트가 결과를 만들었다

첫 실행에서 둘 다 틀린 21건 중 **13건이 "라벨=request/calculate,
LLM=check_eligibility" 로 한 방향**이었다. 원인은 내가 프롬프트에 넣은 이 줄이다.

```
- 애매하면 되돌릴 수 있는 쪽(조회·확인)을 고릅니다.
```

이 저장소의 안전 원칙을 프롬프트에 그대로 옮긴 것이었는데, **측정에서는
그것이 편향이 된다.** 빼고 다시 재니 50.0% → **60.0%** 로 올랐다. 즉 그 한
줄이 10%p 를 깎고 있었다.

★**실험 설계가 결과를 만들면 그건 측정이 아니다.** 두 조건을 옵션으로 남겨
(`--no-safe-tiebreak`) 둘 다 재현되게 했다.

## 남은 오답이 말하는 것 — 경계가 문장으로 안 정해진다

편향을 뺀 뒤 LLM 오답 24건의 혼동 방향:

```
8건  라벨=return.request           LLM=return.check_eligibility
4건  라벨=return.check_eligibility LLM=return.request        ← 반대 방향
3건  라벨=refund.calculate         LLM=return.check_eligibility
2건  라벨=shipment.status          LLM=shipment.exception
2건  라벨=fulfillment.track        LLM=shipment.status
```

★**혼동이 양방향이다.** 한쪽으로 쏠렸으면 규칙을 고쳐 잡을 수 있지만,
같은 두 capability 사이를 양쪽으로 틀린다는 것은 **문장만으로는 경계가
정해지지 않는다**는 뜻이다. 키워드도, 능력 있는 LLM 도 같은 자리에서 틀린다.

## 그래서 무엇을 아나

1. **LLM 이 키워드보다 낫다** — 41.7% → 60.0%. 다만 **채택 결정은 아니다.**
   Case 마다 호출이 하나 늘고(비용·지연), 결과가 비결정적이 된다.
2. **60% 도 낮다.** 남은 40% 는 모델을 바꿔서 좁혀질 종류로 보이지 않는다 —
   `return.request` 와 `return.check_eligibility` 의 경계가 애초에
   문장에 없기 때문이다.
3. 따라서 **다음은 C 를 더 밀어붙이는 것이 아니라, 라벨과 경계를 사람이
   확인하는 것**이다. 그 도구가 `wiki/records/labeling/capability_audit.html` 이다
   (불일치 35건을 먼저 보여준다).
   - 라벨이 틀린 것으로 판명되면 → 라벨을 고치고 A·B 로 간다
   - 라벨이 맞는 것으로 판명되면 → capability 정의 자체를 나눠야 한다
     (지금 `return.request` 와 `check_eligibility` 를 가르는 것은 문장이
     아니라 **고객이 이미 결정했는지** 인데, 그건 대화 이력에 있지 한 문장에 없다)

## 재현

```powershell
python -m eval.capability_selection_experiment --limit 5              # 소량 확인
python -m eval.capability_selection_experiment                        # 편향 있는 조건
python -m eval.capability_selection_experiment --no-safe-tiebreak     # 편향 제거
```

산출물: `eval/reports/2026-09-03_capability_selection_llm_vs_keyword.json`,
`eval/reports/2026-09-03_capability_selection_llm_no_tiebreak.json`
