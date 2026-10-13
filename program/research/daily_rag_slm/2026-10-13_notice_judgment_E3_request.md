# 의뢰 — 공지 판정 두 과제를 E3 데이터셋과 모델 학습에 넣어 주세요 (2026-10-13)

보낸 쪽: 「종료 표현 다양성 검토」 세션(Claude). 받는 쪽: 「큐 등록 완료」 세션(모델 작업 큐).
사용자 지시(2026-10-13): 「추가 테스트셋과 모델학습이 필요한 부분을 '큐 등록 완료' 세션에 전달해서 앞으로 작업에 반영된 E3 데이터셋을 구축하고 모델학습들에 반영할 수 있게 해」.

## 한 줄 요약

재난 문자를 읽는 판정 두 가지에 쓸 자료가 생겼습니다.
- 정답 세트: 전국 700건, 서울 398건.
- 학습 자료: 452건.

이 두 과제를 E3 의 새 과제 묶음(family)으로 넣어 주시고, 학습 대상 모델(Winnow · Saluki · 가르친 E4B 등)의 다음 학습 자료에 넣을지 검토해 주세요.

## 두 과제

| 과제 | 입력 | 출력 JSON | 위험한 실수 | 제품에서 쓰는 곳 |
|---|---|---|---|---|
| **notice_end** — 끝났나 | 재난 문자 본문 1통 | `{"state": ended·partial·scheduled·unsettled·no_end_signal, "ended": bool, "evidence": 본문 조각}` | 잘못 「끝남」(경고가 조용히 사라짐) | `app/domains/travel_ops/ports/data_sources/notice_end_model.py`<br>규칙이 끝남이라 한 것만 모델이 다시 보고, **둘 다 끝남일 때만 끝남** |
| **notice_impact** — 여행 영향 | 재난 문자 본문 1통(주로 재해구분 「기타」) | `{"impact": road·bus·rail·utility·crowd·hazard·outdoor·none, "relevant": bool, "ended": bool, "place": 본문 그대로, "evidence": 본문 조각}` | 놓침(감시에 안 감) | 규칙 `notice_impact.py` 는 있음<br>모델 연결 · 감시 경로 연결은 사용자 결정 대기<br>합치는 방식은 **규칙 또는 모델** |

- 지시문(기준서)은 정답을 붙인 쪽과 모델이 같은 글을 썼습니다.
  - notice_end: `datasets/safety/disaster_msg_korea_2023_2026/eval/end_label_guide.md`. 제품 지시문은 `notice_end_model.py` 의 `SYSTEM`(버전 `notice_end.v1-2026-10-13`)이고 같은 글입니다.
  - notice_impact: `datasets/safety/disaster_msg_korea_2023_2026/eval/gita_label_guide.md`
- 모델 호출 조건: Ollama `/api/chat`, `think: false`, 온도 0, `format: json`. 사용자 메시지는 `"재난 문자:\n" + 본문`.

## 자료 위치와 나눔 (전부 git 밖 `datasets/`)

| 파일 | 건수 | 쓰임 |
|---|---|---|
| `datasets/safety/disaster_msg_korea_2023_2026/train/notice_train.jsonl` | 452 (end 251 · impact 201) | **학습 가능**. 전국 세트의 dev 몫만 담았습니다 |
| `datasets/safety/disaster_msg_korea_2023_2026/train/notice_eval.jsonl` | 646 (end 339 · impact 307) | **평가 전용 — 학습 금지**. 전국 holdout 몫 + 서울 세트 |
| `datasets/safety/disaster_msg_korea_2023_2026/eval/end_set.json` · `gita_set.json` | 400 · 300 | 각 문자의 split(dev/holdout) · 묶음(stratum) · 규칙 결과 |
| `datasets/safety/disaster_msg_korea_2023_2026/eval/*_claude_labels_part*.json` | 400 · 300 | 정답(Claude) |
| `datasets/safety/disaster_msg_korea_2023_2026/eval/*_model_labels.jsonl` | 400 · 300 | x600 `tripilot-pointer:e4b-ft` 의 원래 답 |
| `datasets/safety/disaster_msg_seoul_2026/eval/` | 190 · 208 | 서울 세트. 규칙을 만들 때 **안 본 시험장**이라 학습에 넣지 말아 주세요 |
| `datasets/safety/disaster_msg_korea_2023_2026/processed/disaster_msg_korea.csv` | 63,276행(고유 본문 50,223) | 전국 원자료 정리본. 정답 없음. 추가 정답 세트를 뽑을 때 쓰는 모집단 |

- 한 줄 모양: `{"messages":[system, user, assistant], "task", "id", "split", "source", "confidence"}`.
- 확신 낮음(`confidence: low`) 표시: 학습 91/452 · 평가 124/646. 가르칠 때 뺄지 정해 주세요.
- 다시 만드는 법: `scripts/build_label_sets.py`(세트 고르기) · `export_training.py`(학습 파일) · `score_all.py`(채점) · `run_model.py`(모델 돌리기).

## 지금 기준선 (holdout 몫, 규칙을 만들 때 안 봄)

| 과제 | 규칙(고친 뒤) | x600 가르친 E4B | 합친 방식 |
|---|---|---|---|
| notice_end (149건 · 정답 끝남 47) | 잘못 끝남 8 · 놓침 2 | 잘못 끝남 0 · 놓침 3 | AND: 0 · 5 |
| notice_impact (99건 · 영향 있음 71) | 놓침 2 · 잘못 보냄 9 | 놓침 0 · 잘못 보냄 10 | OR: 0 · 13 |

- 비교한 모델: x600 서버 Ollama 의 `tripilot-pointer:e4b-ft`. 우리 데이터로 가르친 E4B 이고, 원래는 일정 항목 짚기용으로 2026-10-07 에 올라갔습니다. 이 과제로는 가르친 적이 없습니다.
- 자세한 표: `final_project_cs/wiki/records/reports/2026-10-13_0430_전국재난문자_규칙보강.md`

## 부탁드리는 것

1. **E3 에 두 과제 묶음을 넣어 주세요.**
   - 평가 몫은 `notice_eval.jsonl`(646)입니다. 서울 세트는 따로 「외부 시험장」 표시를 해 주세요.
   - 채점은 과제마다 위험한 실수를 따로 세 주세요: notice_end 는 잘못 끝남, notice_impact 는 놓침. 정확도 하나로 합치지 말아 주세요.
2. **학습 대상 모델의 다음 회차에 `notice_train.jsonl`(452)을 넣을지 검토해 주세요.**
   - E2 와 같은 원칙으로, 평가 몫(646)은 어떤 모델의 학습에도 넣지 않습니다.
   - 학습 전후를 같은 646 으로 재 주세요. 시드가 다르면 점수가 흔들리므로(같은 레시피로 750↔760 사례), 시드 여럿으로 재 주세요.
3. **필요하면 정답 세트를 더 뽑아 주세요.** 모집단은 전국 CSV 입니다.
   - 이미 정답을 붙인 본문은 빼 주세요(세트 json 의 `text` 로 거르면 됩니다).
   - 정답은 출제자가 Claude 입니다. Claude 계열을 평가할 때는 공정성 표시를 붙여 주세요(기존 규칙과 같음).

## 지켜 주실 것

- **재난 문자 API 를 더 부르지 말아 주세요.** 2026-10-13 에 이 세션이 315번 썼습니다. x600 서버의 cs 프로젝트 서버와 같은 키라 하루 한도 1,000 을 함께 씁니다. 사용자 지시 상한은 80% 입니다. 원자료는 이미 전부 받아 두었습니다.
- **시험 부하는 GPU 서버(RunPod)에서 돌려 주세요.** x600 서버는 서비스 기계입니다. 이번 평가는 사용자가 「x600 에서 도는 모델로」라고 해서 x600 에서 돌렸습니다(700 호출).
- **정답의 한계:** 정답은 Claude 하위 작업 넷이 본문과 기준서만 보고 붙였습니다. 사람이 붙인 정답은 없습니다. 넷이 애매한 경우를 다르게 정한 곳이 있습니다.
  - 예: 「해제 시까지」를 예정으로 볼지, 끝 낱말 없음으로 볼지.
  - 「끝남 참 · 거짓」에는 영향이 없지만, 다섯 상태 칸 일치율은 그만큼 흔들립니다.
- 사용자에게 보고할 때는 「Jev」라고만 쓰지 말고 정확한 모델 이름과 학습 여부를 적어 주세요(전역 규칙).
