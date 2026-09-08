# capability 선택의 정확도를 처음으로 **측정**했다

## 왜 쟀나

`select_capability` 훅을 넣을 때(2026-09-01, `4c76966`) "지금보다 낫다"는
근거가 **없었다.** 고친 사례 몇 개를 눈으로 확인했을 뿐이다. Codex 교차검증이
"golden 라벨 60건 중 37건이 마커 결과와 다르다"고 지적해, 그렇다면 이 훅이
**개선인지 개악인지**부터 재기로 했다.

## 무엇을 기준으로 재나

`eval/datasets/golden.jsonl` 의 72건 중 **60건이 `expected_capability` 라벨을
가진다**(사람이 붙인 정답). 그것을 기준으로 두 경로를 대조한다.

```
기존   TeamRegistry.capability_for(entry, intent)                    # 이름 매칭만
훅     TeamRegistry.capability_for(entry, intent, input_text=문장)   # select_capability 포함
```

## 결과

| | 라벨과 일치 |
|---|---|
| 기존(이름 매칭만) | **19/60 = 31.7%** |
| 훅 적용 | **25/60 = 41.7%** |

바뀐 8건 중 **개선 7 · 악화 1**.

```
개선  g-order-08  g-order-09  g-shipping-06
      g-return-11 g-return-15 g-exchange-03 g-exchange-05
악화  g-return-08
```

## 악화 1건은 키워드로 못 잡는 종류다

```
g-return-08  "주문제작 상품인데 단순히 마음에 들지 않아서 반품하고 싶습니다."
             라벨: return.check_eligibility   훅: return.request
```

문장만 보면 명백한 반품 **요청**이다. 라벨이 `check_eligibility` 인 이유는
**주문제작 상품이라 반품 대상이 아닐 수 있어서** 자격부터 확인해야 하기
때문이다 — 이건 문장 형태가 아니라 **상품 속성에 대한 도메인 지식**이다.
키워드로는 원리상 잡을 수 없다. 남는 오차로 정직하게 둔다.

## 측정하면서 좁힌 것

라벨과 대조하니 마커가 넓게 잡는 자리가 드러났다. 셋 다 **"내 상황이
문제다"와 "규칙이 뭐냐"를 못 가른 것**이었다.

| 문장 | 잘못 잡던 것 | 넣은 억제 |
|---|---|---|
| "출고 마감 시간이 지나면 배송 지연으로 보는 **건가요**?" | shipment.exception | `건가요` |
| "지연 여부를 **확인해 주세요**" | shipment.exception | `확인해 주` |
| "배송 지연 사유를 안내한 **답변**에…" | shipment.exception | `답변`·`응답` |
| "교환하고 싶습니다. 신청 기한을 **알려 주세요**" | return.request | return_refund 에도 문의 억제 신설 |
| "주문 전체를 **취소해야** 하나요?" | order.cancel | `취소해` → `취소해 주` |

★**애매하면 기본값(정보성 응답)으로 둔다.** 정보성 응답은 되돌릴 수 있지만
잘못 만든 신청은 승인 큐를 오염시킨다.

## 이 수치를 어떻게 읽어야 하나

★**41.7% 는 좋은 값이 아니다.** 이 리포트의 요점은 "훅이 낫다"가 아니라
**"이제 얼마나 나쁜지 안다"** 는 것이다. 전에는 그 수치조차 없었다.

★그리고 이 수치는 **eval 결과에 영향을 주지 않는다.** 러너는 라벨이 있으면
라벨을 우선하므로(`eval/runners/common.py`), 라벨 보유 60건에서는 훅이 아니라
라벨대로 실행된다. 이 41.7% 가 말하는 것은 **운영 경로**의 정확도다 — 실제
고객 문의에는 라벨이 없다.

★키워드 방식의 한계가 이 수치로 드러난 셈이다. 근본 해결은
`wiki/records/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md`
가 적은 대로 **intent→capability 매핑의 재설계**이고, 그때 이 41.7% 가
비교 기준선이 된다.

## 재현

```powershell
python -m pytest -q tests/unit/teams          # 97 passed (문의/요청 구분 회귀 테스트 포함)
```

측정 자체는 `eval/datasets/golden.jsonl` 의 `expected_capability` 와
`TeamRegistry.capability_for()` 를 input_text 유무로 두 번 불러 세면 재현된다.
