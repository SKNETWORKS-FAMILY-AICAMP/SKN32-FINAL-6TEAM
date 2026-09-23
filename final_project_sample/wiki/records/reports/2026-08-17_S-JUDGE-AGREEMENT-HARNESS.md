# S-JUDGE-AGREEMENT-HARNESS 구현 리포트

## 만든 파일

- `eval/label_holdout_template.py`
- `eval/reports/holdout_human_labels_template.jsonl` — holdout 20건의 원본 `case_id`와 `message`만 보존하고 사람 라벨은 비워 둔 템플릿
- `eval/reports/holdout_human_labels_template_README.md`
- `eval/stats/agreement.py` — 필드별 exact-match와 Cohen's kappa, `case_id` 정합성 검사
- `tests/unit/eval/test_agreement.py` — 합성 데이터 단위 테스트

실제 LLM 호출, holdout 원본 수정, 사람 라벨 추정은 하지 않았다. DoD-15와
DoD-17의 판정도 변경하지 않고 도구 준비 상태만 덧붙였다.

## 사람이 다음에 할 일

1. `eval/reports/holdout_human_labels_template.jsonl`의 각 행에
   `human_intent`, `human_issue_code`, `human_sentiment`, `human_pass`,
   `human_notes`를 직접 입력한다.
2. 입력을 마친 뒤 다음 명령으로 agreement를 계산한다.

```powershell
python -m eval.stats.agreement `
  --human eval/reports/holdout_human_labels_template.jsonl `
  --predictions eval/reports/raw_proposed.jsonl
```

`raw_proposed.jsonl` 대신 대조할 judge/system 파일을 지정하면 된다. 결과의
`agreement`는 exact-match 비율이고 `kappa`는 우연 일치를 보정한 Cohen's
kappa다. `case_id` 누락·추가·중복은 오류로 보고된다.

## 테스트 결과

```text
python -m pytest tests/unit/eval/test_agreement.py -v
======================== 4 passed, 1 warning in 0.06s =========================
```

경고는 pytest cache 디렉터리 생성 권한에 관한 환경 경고이며 테스트 실패가
아니다.

```text
python -m pytest -q
3 failed, 323 passed, 1 deselected, 2 warnings in 27.46s
```

실패한 3건은 기존 `tests/integration/rag/test_rag_integration.py`의 검색
테스트이며, `api.openai.com` embeddings 호출이 샌드박스 네트워크 차단
(`WinError 10013`, `openai.APIConnectionError`)으로 실패했다. 새 agreement
단위 테스트의 실패는 없었다.
