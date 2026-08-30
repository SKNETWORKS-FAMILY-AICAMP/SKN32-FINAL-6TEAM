# S-DOD28-FINETUNE-PIPELINE — 파인튜닝 1차·2차·비교평가 결과

DoD-28(v7 §27 항목 28)이 요구하는 마지막 조각인 파인튜닝 1차(공개데이터)·
2차(알파 대체 데이터)·`Proposed` vs `Proposed+FT` golden+holdout 비교평가를
x600 GPU 서버에서 전부 실행했다. **결과: 이번 파인튜닝은 채택하지
않는다.** 원인은 명확하고 설계상 당연한 귀결이지, 버그가 아니다.

## 요약

| 단계 | 결과 |
|---|---|
| 1차 SFT (Qwen2.5-3B-Instruct, LoRA r=16, AI Hub 1,500건) | 376/376 스텝, train_loss 1.37→0.11 |
| 2차 SFT (golden judge-pass 22건 이어붙임) | 12/12 스텝, train_loss 0.57 |
| golden 72건 비교 (Proposed vs Proposed+FT) | Proposed 27.8% pass vs **Proposed+FT 0.0% pass** |
| holdout 24건 비교 (Proposed vs Proposed+FT) | Proposed 16.7% pass vs **Proposed+FT 0.0% pass** — golden과 같은 결론 재확인 |

holdout 24건은 이 프로젝트에서 처음으로 실 LLM 예측을 돌린 것이다
(기존엔 사람 라벨링 템플릿만 있었다). 이 결과를 보고 프롬프트를 고치지
않았으므로 홀드아웃 성격은 유지된다 — 이번이 곧 최초이자 최종 측정이다.

## 왜 0%인가 — 버그 아님

`eval/finetune/predict.py`는 파인튜닝된 모델을 **Team 파이프라인 밖에서
단독 호출**한다. Context Broker가 조합하는 RAG evidence를 프롬프트에
전혀 주입하지 않는다. `prompts/judge/judge_v1.txt`의 채점 규칙은
"citations.valid가 비어있으면 policy_grounding은 무조건 0"이라고
명시한다 — Proposed+FT는 애초에 citations를 생성할 수단이 없으므로
전건이 policy_grounding=0으로 깎이고, judge pass 조건(`safety>=3 and
correctness>=3 and total>=16`)을 넘을 수 없다.

이건 `app/core/verification.py`가 시행하는 "근거 없으면 답하지 않는다"
원칙과 정확히 같은 메커니즘이고, 이미 나온 ablation 결과(RAG 유무에
따라 grounding 3.98→0.00, 구 도메인 기준)를 새 도메인·새 모델에서
재확인한 것뿐이다. 파인튜닝된 3B 모델을 실제로 쓰려면 Team이 조합한
ContextPack을 프롬프트에 주입하는 통합 경로가 별도로 필요하다 —
이번 세션 범위에는 없다.

## 실행 환경과 겪은 결함

### 1. transformers 5.14.1 버그 3종 (모두 우회, 업스트림 수정 아님)

- `AutoTokenizer.from_pretrained()` 가 유효한 tokenizer.json에도
  `ValueError: Couldn't instantiate the backend tokenizer` — `Tokenizer.from_file()` +
  수동 `PreTrainedTokenizerFast(tokenizer_object=...)` 래핑으로 우회
  (`eval/finetune/load_tok.py`).
- `AutoConfig`/`AutoModelForCausalLM.from_pretrained()` 가 유효한
  `"model_type": "qwen2"` config에도 `Unrecognized model` — `Qwen2ForCausalLM`
  직접 import로 우회.
- 체크포인트 샤드 해석이 `model.safetensors.index.json`이 있는데도
  실패 — 이전에 중단된 다운로드의 불완전한 로컬 스냅샷이 원인,
  `huggingface_hub.snapshot_download()` 선행 다운로드 + `local_files_only=True`로 해결.

### 2. Windows 페이징파일 버그로 QLoRA(4-bit) 포기

당초 계획은 4-bit QLoRA(`device_map="auto"` + `BitsAndBytesConfig`)였다.
`OSError: The paging file is too small for this operation to complete.
(os error 1455)` 가 `transformers/modeling_utils.py`의 CUDA 타깃
`safe_open()` 호출에서 **여유 RAM·페이징파일 크기와 무관하게** 반복
재현됐다:

- WSL2(`vmmemWSL`)가 RAM 5.28GB를 점유하고 있어 `wsl --shutdown`으로
  비웠더니 단순 CPU-먼저-로드 경로(`diag_3b.py`)는 해결됐다.
- 하지만 `device_map="auto"` + 4-bit 양자화 경로는 RAM을 비운 뒤에도
  **똑같이 재현**됐다.
- 사용자가 Windows GUI로 페이징파일을 수동 확장 시도(재부팅 포함,
  여러 차례)했으나 `AutomaticManagedPagefile`이 계속 `True`로 되돌아가
  실제로는 거의 늘지 않았다(12068→13463MB).

우회: `device_map="auto"`와 4-bit 양자화를 모두 버리고
```python
model = Qwen2ForCausalLM.from_pretrained(local_base, dtype=torch.bfloat16, local_files_only=True)
model = model.to("cuda")
```
로 CPU에 올린 뒤 통째로 `.to("cuda")`로 옮기는 경로를 썼다 — 이 경로는
문제의 CUDA 타깃 `safe_open()`을 아예 타지 않는다. 3B 모델(~6GB, bf16)은
12GB VRAM에 양자화 없이 들어가서 이 우회가 가능했다. 7B였다면 이
우회 자체가 막혔을 것 — **모델을 7B에서 3B로 낮춘 이유가 이것**이다.
재현 스크립트: `eval/finetune/diag_3b.py`(성공), `diag_loadloop.py`
(문제를 단계별로 격리한 과정).

### 3. CUDA OOM (별개 원인, 진짜 VRAM 예산 문제)

양자화 없이 순수 bf16으로 로드하니 이번엔 진짜 VRAM 예산 초과로
1차 학습이 22스텝(그다음엔 266스텝)에서 CUDA OOM으로 죽었다 — loss는
정상 하락 중이었다(1.37→0.32 등, 학습 자체는 맞게 진행되고 있었음).
`gradient_checkpointing=True` + `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,
garbage_collection_threshold:0.8` + `max_length` 768→512로 activation
메모리를 줄여 해결. 40스텝마다 체크포인트 저장(`save_steps=40`)하도록
바꿔 재발 시 처음부터 다시 돌리지 않고 `--resume`으로 이어 붙일 수
있게 했다 — 실제로 266스텝 지점 OOM 이후 checkpoint-188에서 재개해
완주했다(`train.py`의 `--resume` 인자).

## 재현 명령

```powershell
# x600 GPU 서버, venv312 (Python 3.12.13)
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\train.py --stage 1 --data E:\dod28_ft\sft_stage1.jsonl --base Qwen/Qwen2.5-3B-Instruct --out E:\dod28_ft\ckpt_stage1
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\train.py --stage 2 --data E:\dod28_ft\sft_stage2.jsonl --base E:\dod28_ft\ckpt_stage1 --out E:\dod28_ft\ckpt_stage2
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\predict.py --adapter E:\dod28_ft\ckpt_stage2 --golden E:\dod28_ft\golden.jsonl --out E:\dod28_ft\ft_predictions.jsonl

# 로컬 (채점)
python -m eval.finetune.score_ft --input eval/finetune/ft_predictions.jsonl --output eval/reports/2026-08-30_reeval_ProposedFT.jsonl

# holdout 24건도 같은 방식 — Proposed 는 이 프로젝트 최초의 holdout 실측(사람 라벨 템플릿뿐이었음)
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\predict.py --adapter E:\dod28_ft\ckpt_stage2 --golden E:\dod28_ft\holdout.jsonl --out E:\dod28_ft\ft_predictions_holdout.jsonl
python -m eval.runners.proposed --dataset eval/datasets/holdout.jsonl --repeats 3 --seed 7 --provider openai --output eval/reports/2026-08-30_holdout_proposed.jsonl
python -m eval.finetune.score_ft --input eval/finetune/ft_predictions_holdout.jsonl --output eval/reports/2026-08-30_reeval_ProposedFT_holdout.jsonl
```

## 산출물

- `eval/finetune/build_datasets.py` — 1차/2차 SFT 데이터셋 빌더
- `eval/finetune/load_tok.py`, `train.py`, `predict.py`, `score_ft.py` — 학습/추론/채점 파이프라인
- `eval/finetune/diag_*.py` — 페이징파일·메모리 버그 격리 과정(재현/회귀용으로 보존)
- `eval/reports/2026-08-30_reeval_ProposedFT.jsonl` — golden 72건 채점 결과 원본
- `eval/reports/2026-08-30_holdout_proposed.jsonl` — holdout 24건×3회 Proposed 실측 원본(이 프로젝트 최초)
- `eval/reports/2026-08-30_reeval_ProposedFT_holdout.jsonl` — holdout 24건 Proposed+FT 채점 결과 원본
- `docs/evidence/DoD-28_파인튜닝_방어지표.md` §"2026-08-30 갱신" — DoD-28 판정 반영(golden+holdout)

## 다음 단계 (이번 세션 범위 밖)

파인튜닝된 모델을 실제로 채택하려면 Team의 ContextPack 조합 경로에
파인튜닝 모델을 끼워 넣어(현재는 OpenAI API 호출 지점) RAG evidence를
프롬프트에 실어야 한다. 지금 상태로는 "파인튜닝이 성능을 개선했는가"를
공정하게 비교할 수 없다 — Proposed는 RAG를 쓰고 Proposed+FT는 안 쓰는
비교이기 때문이다. golden·holdout 둘 다 이 한계 안에서 측정됐고 결론은
같다.
