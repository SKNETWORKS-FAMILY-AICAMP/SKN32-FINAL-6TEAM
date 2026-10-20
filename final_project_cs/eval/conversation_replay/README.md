# 실제 여행 대화 재생 시험 도구 (2026-10-19)

「고객이 원한 일이 끝났나 · 엉뚱하게 저장하지 않았나 · 몇 번 되물었나」를 **대화 단위**로 잰다.
정본 계획은 `wiki/quality/conversation-replay-plan.md`(재생 시험 계획) — 칸 · 판정 규칙 · 갈림 처리 · 숫자 고정 순서는 그 문서를 따른다.
대화 원문 · 정답 · 녹화 · 결과는 **git 밖** `datasets/travel/chat_replay_20261019/` 에만 둔다. 이 폴더에는 도구와 합성 예시 3개만 있다.

## 흐름

```
에피소드(시작 상태 · 대본 · 끝 상태 조건 · 금지)
  → 조건 문장을 규칙 언어로 옮기기(compile.py 규칙 → compile_model.py Codex → 못 옮기면 판정 불가)
  → 시작 상태를 시험 DB 에 넣기(seed.py — 주소에 'replay' 가 없으면 멈춤)
  → 웹 채팅 입구에 원래 시각을 실어 대본 재생(runner.py A) — 바깥 조회는 녹화 · 재생(recorder.py)
  → 일찍 끝남 · 갈림 a/b/c 판정 → 갈리면 고객 역할 모델로 잇기(B, 2회 · 다르면 3회 다수결, 턴 상한 4)
  → 칸별 채점(score.py ①~④) → 판정기 규칙 · 짝 비교(stats.py) → 요약(report.py)
```

| 파일 | 하는 일 |
|---|---|
| `episodes.py` | 실제 대화(`episodes_v*.jsonl`) · 표적(`targets_v*.jsonl`)을 한 모양으로 |
| `state.py` | 판 · 항목 · 계보 |
| `conditions.py` | 규칙 언어 — `pass` · `fail` · `unknown`(판정 불가, 통과로 세지 않음) |
| `compile.py` · `compile_model.py` | 조건 문장 → 규칙 언어 |
| `seed.py` | 시작 상태 → 시험 DB |
| `recorder.py` | 바깥 응답 녹화 · 재생(mock 서버 역할), 실조회 수 · 예산 |
| `runner.py` · `run.py` | 재생 실행(이어 돌리기 가능) |
| `score.py` · `stats.py` · `report.py` · `rescore.py` | 채점 · 판정 · 요약 · 정답만 바뀌었을 때 다시 채점 |
| `examples/` | 합성 예시 3개(빼기 · 짧은 답 「2」 · 비 → 실내) |

시험: `python -m pytest eval/tests/test_conversation_replay.py`(DB · 모델 없이).

## 다시 돌리기

```bash
cd final_project_cs
# 1) 조건 옮기기(끝난 묶음은 건너뜀)
python -m eval.conversation_replay.compile_model --episodes <episodes_v7.jsonl> --targets <targets_v1.jsonl> --out <replay/conditions_v1>
# 2) 녹화 실행(실조회 — 예산 상한에서 멈춤) → 3) 녹화 재생으로 기준선 · 재실행
python -m eval.conversation_replay.run --episodes … --targets … --compiled <conditions_v1/compiled.jsonl> --raw-dir <raw/20261019_more> \
  --db <시험 DB 주소(replay)> --ollama <x600 재현 올라마 주소> --keys-file <키 파일> --cassette <replay/cassettes/v1.jsonl> \
  --mode record|replay --out <replay/runs/<이름>> --rep 1
# 4) 요약 · 재실행 일치
python -m eval.conversation_replay.report <run 폴더> --rerun <재실행 폴더> --latency <지연 폴더>
# 사람 검수로 정답만 바뀌었으면 — 모델을 다시 부르지 않는다
python -m eval.conversation_replay.rescore <run 폴더> --episodes <새 판> --targets … --compiled <새 옮김> --name scores_reviewed
```

## 지키는 것

- 제품 코드(`app/`)는 고치지 않는다. 운영과 같은 앱 조립 · x600 서버와 같은 모델 설정(`runner.X600_LIKE`)으로 돈다. 바꾼 것은 웹 사용량 제한 끄기 · 개발 모드 켜기(답에 해석 결과 · 근거가 실린다 — 처리는 같다)뿐이다.
- 시험 DB 에만 쓴다. 비밀 키는 녹화 · 결과 · 화면에 남기지 않는다.
- 결과는 「mock 서버 재생 n/n(녹화로 본 반응)」과 「실서버 확인(실조회로 다시 돌린 에피소드)」을 나눠 적는다.
- 정답이 사람 검수 전이면 결과에 「검수 전 기준선」으로 적는다.
