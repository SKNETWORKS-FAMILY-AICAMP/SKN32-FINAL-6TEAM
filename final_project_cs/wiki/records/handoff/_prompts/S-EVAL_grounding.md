# 구현 지시 — judge 가 인용의 실재를 검증해야 한다 (환각 인용 차단)

## 0. 결함 (실측 2026-08-13, 360행)

```
arm A (설계상 RAG 없음):  policy_evidence=['doc_06 §1']  grounding=3  pass=true   성공 35/180
arm B (설계상 RAG 있음):  policy_evidence=[]             grounding=0  pass=false  성공  0/180
```

두 군의 `answer` 는 **문자 그대로 동일**하다. 차이는 인용 문자열의 유무뿐이다.

★**`doc_06 §1` 은 이 시스템이 만들지 않는 형식이다.**
실제 인용 id 는 `app/core/context.py:PolicyChunk.source_id` = `f"{document_id}#c{chunk_no}"`,
즉 **`doc_06#c3`** 형식이다. A 는 RAG 를 쓰지 않으므로 그 값을 **지어냈다.**
그런데 judge 가 실재를 확인하지 않고 `policy_grounding=3` 을 줬다.

**즉 지금 평가는 환각 인용에 점수를 주고, 진짜 검색하는 군에 0 을 준다.**
상세: `wiki/records/reports/debugs/2026-08-13_1200_평가가_환각인용에_점수를_준다.md`

## 1. 소유 범위

```
eval/**
prompts/judge/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**: `app/**`, `tests/**`(★다른 세션 작업 중), `knowledge/**`,
`scripts/**`, `config/**`, `wiki/records/evidence/**`.

## 2. 고칠 것

### 2-1. ★judge 가 인용의 실재를 대조한다 (핵심)

judge 채점 **전에** `policy_evidence` 의 각 항목을 검증한다:

1. 형식이 **`doc_NN#cM`** 인가 (정규식 `^doc_\d+#c\d+$`)
2. 그 `(document_id, chunk_no)` 가 **실제 `knowledge_chunks` 에 존재**하는가 (DB 조회)

검증 결과를 결과 행에 **그대로 기록**한다:
```json
"citations": {"claimed": ["doc_06 §1"], "valid": [], "invalid": ["doc_06 §1"]}
```

채점 규칙:
- ★유효 인용이 **0개면 `policy_grounding = 0`** (LLM 이 몇 점을 주든 덮어쓴다)
- ★**무효 인용이 있으면 그 사실을 `reasons` 에 남긴다** — 환각은 근거가 아니라 감점 사유다
- 유효 인용이 있으면 judge 의 점수를 그대로 쓴다

★**DB 조회가 부담이면 `knowledge_chunks` 의 (document_id, chunk_no) 집합을
한 번만 읽어 메모리에 캐시**하라. 케이스마다 조회하지 마라.

### 2-2. arm B 의 검색 결과를 출력까지 싣는다

B 는 `search_policy()` 를 호출하는 군인데 `policy_evidence` 가 비어 있다.

1. 검색 결과를 **프롬프트에 실제로 넣는다** (근거 문장 + `source_id`)
2. 결과의 `source_id`(`doc_NN#cM`)를 **그대로** `policy_evidence` 에 넣는다
3. 검색이 0건이거나 실패하면 `degraded=true` 로 표시하고 `policy_evidence` 는 빈 채로 둔다
   (조용히 넘기지 마라)

### 2-3. arm A 는 인용을 만들지 않는다

v5 §15-1 상 A 는 **RAG 가 없다.** 프롬프트에서 policy 인용을 **요구하지 마라.**
그래도 LLM 이 뱉으면 §2-1 검증에서 전부 `invalid` 로 걸러져 `grounding=0` 이 된다 — 그게 정상이다.

### 2-4. Proposed 도 같은 형식을 쓴다

`ContextPack.evidence` 의 policy 항목은 `source_id` 가 이미 `doc_NN#cM` 이다.
그대로 `policy_evidence` 에 실어라.

## 3. 자체 검증 — 반드시 통과해야 완료다

```powershell
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 3 --concurrency 3 --output eval/reports/chk_a.jsonl
python -m eval.runners.baseline_b --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 3 --concurrency 3 --output eval/reports/chk_b.jsonl
```

그리고:
```powershell
python -c "import json;[print(f, [ (r['case_id'], r.get('citations'), r['judge']['policy_grounding']) for r in [json.loads(l) for l in open(f,encoding='utf-8')] ]) for f in ('eval/reports/chk_a.jsonl','eval/reports/chk_b.jsonl')]"
```

기대:
- **A**: `citations.valid` 가 **비어 있고** `policy_grounding = 0`
- **B**: `citations.valid` 가 **비어 있지 않고** id 가 `doc_NN#cM` 형식

★A 가 여전히 grounding > 0 이거나 B 가 여전히 빈 인용이면 **완료가 아니다.**

## 4. ★전량 실행은 하지 마라

이 환경은 외부 네트워크가 막혀 있어 **당신 프로세스에서는 OpenAI 호출이 실패한다**
(`APIConnectionError`). §3 검증이 그 이유로 실패하면 **그 사실을 리포트에 적고 멈춰라.**
코드만 고쳐 두면 전량 실행은 다른 환경에서 한다.

★mock 으로 돌려놓고 "완료" 라고 쓰지 마라.

## 5. 리포트

`wiki/records/reports/2026-08-13_평가_인용검증_수정.md` — 변경 파일, §3 출력(또는 실패 출력),
judge 채점 규칙 변경 내용.

## 6. 하지 말 것
- ❌ 인용 실재 확인 없이 grounding 점수 주기
- ❌ arm A 가 인용을 내도록 프롬프트에서 요구
- ❌ 검색 실패를 조용히 빈 배열로
- ❌ 소유 범위 밖 수정 / 전량 실행 / mock 보고
