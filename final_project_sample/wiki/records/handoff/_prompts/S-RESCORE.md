# 구현 지시 — `next_action` 어휘 정렬 + 재채점 (540런 재실행 없이)

## 0. 결함

`wiki/records/reports/debugs/2026-08-13_1800_next_action_지표가_어휘일치를_잰다.md`

```
golden 기대 : investigate_and_propose_refund / explain_policy / compare_events_and_escalate
Proposed    : respond / respond / respond              ← 계약 어휘(NextAction Enum)
B           : investigate_and_propose_refund ...       ← golden 문자열을 복창
```

judge 평균:
| 항목 | A | B | Proposed |
|---|---:|---:|---:|
| policy_grounding | 0.00 | 2.67 | **3.99** |
| next_action | — | **3.98** | **0.94** |

★**Proposed 는 계약을 지켰기 때문에 벌점을 받았다.**
`TeamResult.next_action` 은 v5 §7 의 `NextAction` Enum 7종
(`continue`·`wait_for_input`·`wait_for_approval`·`call_tool`·`handoff`·`respond`·`escalate`)
이고, `extra='forbid'` + Enum 제약 때문에 golden 라벨을 **낼 수도 없다.**

**설계를 지킨 쪽이 지표에서 지는 구조다.**

## 1. 소유 범위

```
eval/datasets/golden.jsonl
eval/datasets/holdout.jsonl
eval/judge/**
eval/stats/**
eval/runners/common.py        (재채점 진입점이 필요하면)
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/**`, `tests/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.
★`eval/reports/raw_*.jsonl` 의 **`prediction` 을 수정하지 마라** — 원본 응답이다.

## 2. 할 일

### 2-1. golden/holdout 의 `expected_next_action` 을 계약 어휘로 바꾼다

시스템의 계약이 기준이어야 한다. 매핑 예:

| 기존 golden 라벨 | `NextAction` |
|---|---|
| `investigate_and_propose_refund` | `wait_for_approval` (환불 제안은 승인 대기다) |
| `explain_policy` | `respond` |
| `compare_events_and_escalate` | `escalate` |
| (그 밖) | 뜻에 맞는 Enum 값 |

★**전체 80건(golden 60 + holdout 20)을 훑어** 매핑하라.
★매핑표를 리포트에 **전부** 싣고, 애매한 항목은 판단 근거를 적어라.
★`NextAction` 7종 밖의 값을 쓰지 마라.

### 2-2. ★재채점 — 540런을 다시 돌리지 마라

`eval/reports/raw_*.jsonl` 에 각 군의 **원본 `prediction` 이 남아 있다.**
그것을 읽어 **judge 만 다시** 돌리는 경로를 만든다:

```powershell
python -m eval.rescore --input eval/reports/raw_baseline_a.jsonl --output eval/reports/rescored_a.jsonl
```

- ★**A·B·Proposed 세 군 모두 같은 기준으로** 재채점한다. 한 군만 고치면 비교가 깨진다
- 원본 파일은 **보존**하고 `rescored_*.jsonl` 로 따로 쓴다
- ★judge 호출은 LLM 이 필요하다 — **당신 환경에서는 실패한다**(외부 네트워크 차단).
  **코드만 만들고 실행은 검수 담당이 한다**

### 2-3. 통계 입력 준비

`eval/stats/bootstrap.py` · `mcnemar.py` 가 `rescored_*.jsonl` 을 받을 수 있게 한다
(paired 비교용 `pairs.jsonl` 생성 포함).

## 3. 완료 조건

```powershell
python -c "import json;print(len([json.loads(l) for l in open('eval/datasets/golden.jsonl',encoding='utf-8')]))"
python -c "
import json
g=[json.loads(l) for l in open('eval/datasets/golden.jsonl',encoding='utf-8')]
vals=set(x.get('expected_next_action') for x in g)
allowed={'continue','wait_for_input','wait_for_approval','call_tool','handoff','respond','escalate'}
print('고유 라벨:',sorted(vals))
print('계약 밖 값:',sorted(vals-allowed))
"
python -m eval.rescore --help
python -m pytest eval/tests -q
```

기대: golden **60건**, **계약 밖 값 0개**, `rescore` 진입점 존재, eval 테스트 통과.

★**judge 실행은 하지 마라.** 네트워크가 막혀 있다. 실패하면 그 사실을 적어라.

## 4. 리포트

`wiki/records/reports/2026-08-13_S-RESCORE_리포트.md` —
★**80건 전체 매핑표**(기존 라벨 → NextAction, 애매한 건 근거),
`rescore` 사용법, §3 출력 원문.

## 5. 하지 말 것
- ❌ `raw_*.jsonl` 의 `prediction` 수정
- ❌ 한 군만 재채점
- ❌ `NextAction` 밖의 라벨
- ❌ 540런 재실행
- ❌ judge 를 mock 으로 돌려 "재채점 완료" 라고 쓰기
- ❌ 소유 범위 밖 수정
