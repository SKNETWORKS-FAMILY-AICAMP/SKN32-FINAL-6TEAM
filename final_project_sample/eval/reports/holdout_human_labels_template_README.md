# Holdout 사람 라벨 워크시트

`holdout_human_labels_template.jsonl`은 frozen holdout 20건을 사람이 직접
검토해 채우는 입력 파일이다. 템플릿 생성 명령은 다음과 같다.

```powershell
python -m eval.label_holdout_template
```

각 행의 필드는 다음처럼 작성한다.

- `case_id`, `message`: 원본 holdout 값. 수정하지 않는다.
- `human_intent`: 사람이 판단한 의도 분류값.
- `human_issue_code`: 사람이 판단한 세부 이슈 코드.
- `human_sentiment`: 사람이 판단한 감정값.
- `human_pass`: 사람 기준으로 전체 응답이 통과인지 `true` 또는 `false`.
- `human_notes`: 판단 근거, 애매한 점, adjudication 메모. 사람 라벨을 다
  채우기 전에는 위 네 라벨을 `null`로 둔다.

완료 후 judge 결과와 대조한다. 기존 raw report 형식(`prediction.*`,
`judge.pass`)도 지원한다.

```powershell
python -m eval.stats.agreement `
  --human eval/reports/holdout_human_labels_template.jsonl `
  --predictions eval/reports/raw_proposed.jsonl
```

출력의 `agreement`는 exact-match 비율이고, `kappa`는 우연 일치를 보정한
Cohen's kappa다. `case_id` 누락·추가·중복은 오류로 중단된다.
