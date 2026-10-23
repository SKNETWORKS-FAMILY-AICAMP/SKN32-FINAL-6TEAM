## Serving Standard One 8B with this code

This directory is `jev-adapter` (Apache-2.0, see `LICENSE` and `NOTICE`): a small HTTP server that turns the SGLang engine into a
`POST /v1/systemone` decision endpoint. Install it into its own virtual environment and start it in front of a stock SGLang 0.5.20
engine that serves this repository:

```bash
pip install -e './server[native-tokenizer]'

# terminal 1: engine
CUDA_VISIBLE_DEVICES=0 SGLANG_VLM_CACHE_SIZE_MB=0 python -m sglang.launch_server \
  --model-path . --served-model-name standard-one-8b \
  --host 127.0.0.1 --port 30000 --tp-size 1 --model-impl sglang --dtype bfloat16 \
  --context-length 32768 --max-running-requests 32 --mem-fraction-static 0.8 \
  --chunked-prefill-size -1 --disable-radix-cache --mm-preprocess-cache-size-mb 0 \
  --model-config-parser hf --load-format safetensors

# terminal 2: adapter (no system prompt)
jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-8b --alias jev-latest \
  --host 0.0.0.0 --port 30120 --max-concurrency 1 \
  --tokenizer-model mistralai/Ministral-3-8B-Instruct-2512-BF16 \
  --tokenizer-revision f6fae9795746f63c9be8344932f01275f3c63734 \
  --prompt-wording served --label-scheme upper --default-temperature 1.65
```

The adapter supports two prompt wordings (details on the model card):

- `served` (the default, recommended; used for the v2.2 measurements): `--prompt-wording served --label-scheme upper --default-temperature 1.65`; up to 255 options per question
- `native`: `--prompt-wording native --native-system-prompt none --default-temperature 0.85 --temperature-by-type choice=0.85,noul=0.85,score=0.70` (temperatures fitted on v2); at most 26 options per question

`--temperature-by-type` sets one default temperature per answer type (`choice`, `noul`, `score`); a request's own
`options.temperature` still wins. Let only this adapter talk to the engine port. The recommended values and the full
request format are in the model card (`../README.md`).

# Jev adapter

기본 추론 엔진을 별도 프로세스로 실행하고, 그 앞에서 `POST /v1/systemone` 응답을 만드는 독립 Python 서비스입니다. 모델 학습, 엔진 fork, SGLang Python 패키지, CUDA, 모델 가중치가 어댑터에 필요하지 않습니다. 현재 구현한 백엔드는 **SGLang HTTP API**입니다.

```text
클라이언트 → jev-adapter :30120 → 기본 SGLang :30000 → GPU 모델
            질문/응답 변환       템플릿·토큰화·비전 처리·프리필
```

모델은 선택지 라벨의 다음 토큰 logprob를 반환하고, 어댑터가 확률 정규화와 최종 JSON 구성을 담당합니다. 엔진 내부 객체나 비공개 Python 함수를 호출하지 않습니다. 상용 Jev 모델이나 학습 결과를 복제한 것은 아닙니다.

## 실행

엔진 환경에서 모델을 실행합니다. 어댑터와 같은 컴퓨터일 필요는 없습니다. 아래는 모델의 served name을 `decision-model`로 정한 예시입니다. `MODEL_PATH`는 엔진이 지원하는 실제 모델 경로 또는 Hugging Face ID로 설정합니다.

```bash
python -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --served-model-name decision-model \
  --host 127.0.0.1 --port 30000
```

어댑터는 이 레포의 별도 가상 환경에서 실행합니다. 엔진을 다른 호스트에서 실행하면 `--engine-url`만 바꾸면 됩니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/jev-adapter \
  --engine-url http://127.0.0.1:30000 \
  --model decision-model \
  --port 30120
```

`python -m jev_adapter`도 같은 CLI입니다. 기본 listen 주소는 `127.0.0.1`이며, `--host`로 변경합니다. `--max-concurrency` 기본값은 32, 엔진 HTTP timeout은 `--timeout 120`입니다.

`--default-temperature T` (환경 변수 `JEV_DEFAULT_TEMPERATURE`)는 요청이 `options.temperature`를 생략했을 때만 적용되는 서버 기본 온도입니다. 요청이 온도를 명시하면 요청 값이 우선하고, `options.temperature_scaling: false`이면 기본값과 무관하게 스케일링하지 않습니다. 지정하지 않으면 기존과 같이 1.0입니다. 실제 적용된 온도는 응답의 `metadata.temperature`로 확인합니다.

`--label-scheme {upper,served}` (환경 변수 `JEV_LABEL_SCHEME`)는 선택지가 26개를 넘는 질문의 답 라벨 순서입니다. 기본값 `upper`는 v2.2가 학습한 A–Z 다음 AA, AB, … 순서(한 토큰인 라벨만, 최대 255개)이고, `served`는 v2.2 이전의 A–Z, a–z, 0–9, AA, … 순서입니다. 26개 이하에서는 둘 다 A–Z입니다.

`SGLANG_API_KEY`는 엔진에 보낼 키, `JEV_API_KEY`는 클라이언트가 어댑터에 보낼 키입니다. 설정했다면 각각 `Authorization: Bearer ...` 인증을 사용합니다. 키를 설정하지 않은 어댑터는 인증 없이 동작합니다.

시작할 때 엔진 정보를 확인하고, 엔진 토크나이저로 라벨을 검증합니다. 엔진을 먼저 실행해야 합니다. 모델/토크나이저를 교체하면 어댑터도 재시작합니다.

Ministral의 공식 `mistral-common` 토크나이저는 제어 토큰을 문자열로 변환했다가 다시
인코딩하면 토큰 ID가 달라질 수 있습니다. SGLang 0.5.20에서 이 문제가 확인되어,
이 모델의 텍스트 요청은 선택형 공식 토크나이저 경로를 사용합니다.

```bash
.venv/bin/python -m pip install -e '.[native-tokenizer]'
.venv/bin/jev-adapter --model decision-model \
  --tokenizer-model mistralai/Ministral-3-3B-Instruct-2512-BF16 \
  --tokenizer-revision b6d637bef2393152b3da2b2fde72eecdee30557e
```

이 경로는 CPU에서 토크나이저 파일만 로드하고 공식 `apply_chat_template(tokenize=True)`
결과를 엔진에 전달합니다. 각 assistant 라벨의 토큰 경계도 공식 continuation으로
검증합니다. 이미지 입력은 지원하지 않으며 기본 HTTP 경로로 자동 전환하지 않습니다.

### 프롬프트 문구 (`--prompt-wording`)

`--prompt-wording {served,native}` (환경 변수 `JEV_PROMPT_WORDING`)는 어떤 문구로
프롬프트를 렌더링할지 정하는 서버 전역 설정입니다. 기본값 `served`는 기존과 동일하게
어댑터 자체 문구(`Context:/.../Options: A: name: description`)를 사용합니다.

`native`는 jevbench-hard 러너 자신의 오프라인 채점 문구(`run_suites_rotation.py`의
`State:/Question:/Options: A. name: description`)를 그대로 렌더링합니다. 러너 자체
ablation에서 이 문구 차이만으로 jevbench-hard 정확도가 약 +6점 높게 측정되었습니다
(native 61.3 대 served 55.0; 동일 토크나이저 계열, rotation 없는 canonical 순서 기준).
옵션 **순서** 자체는 바꾸지 않습니다 — 요청이 준 순서(`choice`/`score`는 criteria
순서, `noul`은 항상 true 다음 false)를 그대로 쓰고 문구만 바꿉니다. 그래서
`--tokenizer-model`/`--tokenizer-revision`이 가리키는 토크나이저의 앞쪽 라벨이
정확히 대문자 `A`..`Z`(최대 26개 선택지)가 아니면 해당 요청은 거부됩니다 — 대부분의
영문 어휘 토크나이저에서는 자동으로 성립합니다.

`--tokenizer-model`/`--tokenizer-revision`도 함께 주면, 어댑터는 같은 pin을
`fix_mistral_regex=True`로 별도 로드해 HF chat template이 자동 주입하는 모델
기본 시스템 프롬프트 텍스트를 추출하고, 이를 명시적 system 메시지로 앞에 붙입니다.
Ministral처럼 서빙 토크나이저가 `mistral-common` 백엔드로 해석되는 경우
(`native_tokenizer.py` 문서 참고) 이 백엔드는 기본 시스템 프롬프트를 자동으로
주입하지 않기 때문입니다 — 직접 추출한 텍스트가 없으면 시스템 메시지 없이 문구만
`native`로 서빙합니다(시작 시 경고 로그). `SYSTEM_PROMPT.txt` 같은 정적
문서 파일은 실제 chat template이 렌더링하는 기본 텍스트와 다를 수 있어(확인된 사례:
문장 하나가 중복/누락) 신뢰하지 않고, 항상 `apply_chat_template`을 직접 렌더링해서
추출합니다.

이 기본 시스템 프롬프트 자동 추출은 `--native-system-prompt {auto,none}`
(환경 변수 `JEV_NATIVE_SYSTEM_PROMPT`)로 끌 수 있습니다. 기본값 `auto`는 위에서
설명한 기존 동작 그대로이고, `none`은 추출 자체를 건너뛰고 시스템 메시지 없이
`native` 문구만 렌더링하며 누락 경고 로그도 남기지 않습니다. 이 옵션을 둔 이유는
Ministral 기본 시스템 프롬프트가 531토큰으로, 전형적인 요청 하나의 약 80%에 달할
만큼 커서 — 프리필 비용과 지연시간에 영향을 주는데, jevbench-hard 정확도 이득은
문구(`native` vs `served`) 자체에서 오지 시스템 프롬프트 유무에서 오는지는 별도
질문이기 때문입니다. `--prompt-wording served`에는 아무 영향이 없습니다.

```bash
.venv/bin/jev-adapter --model decision-model \
  --tokenizer-model mistralai/Ministral-3-8B-Instruct-2512-BF16 \
  --tokenizer-revision f6fae9795746f63c9be8344932f01275f3c63734 \
  --prompt-wording native --default-temperature 2.4
```

CPU 전용 검증(`jevbench-original` 40개 + `internal-eval-v1` 40개 전체, `jevbench-hard`
5개는 구조만) 결과, 요청 옵션 순서를 고정하면 어댑터가 렌더링한 `native` 문구와
러너의 `format_prompt()` 출력은 **텍스트와 토큰 ID가 모두 완전히 일치**했고
(`mistral-common`이 명시 system 메시지를 렌더링한 토큰 ID와 HF 템플릿의 자동 주입
토큰 ID도 이 표본에서는 차이가 없었습니다), 라벨 토큰 ID도 일치했습니다. 다만
`jevbench-original`의 40개 중 24개, 표본 `jevbench-hard` 5개 중 5개에서
데이터셋이 기록한 "정답 채점 순서"(`expected.labels`)가 어댑터가 실제로 쓰는 옵션
순서(criteria 순서 / noul 고정 순서)와 달랐습니다 — 이는 문구와 무관한, 옵션 **순서**
자체의 사전 존재 차이이며 어댑터가 요청 순서를 그대로 따르는 한 코드로 없앨 수
없습니다. 러너의 native 61.3점 자체도 이 순서로 측정된 값이라, jev-adapter로
`--prompt-wording native`를 서빙했을 때 실제로 회수되는 점수는 이 순서 효과만큼
61.3보다 낮을 수 있습니다 — 문구 효과 자체는 위에서 텍스트/토큰 단위로 확인했습니다.

```bash
.venv/bin/python examples/smoke.py
.venv/bin/python examples/smoke.py --image /path/to/screenshot.png
```

기존 평가 클라이언트에서도 base URL을 `http://127.0.0.1:30120`으로 바꾸면 됩니다. `/v1/models`는 실제 모델명을 반환하고, `/health`는 어댑터 프로세스의 생존 여부만 확인합니다.

## 요청과 응답

전체 예시는 [examples/request.json](examples/request.json)을 참고하세요. 모델에는 실제 served name 또는 기본 별칭 `jev-latest`를 사용할 수 있습니다.

```json
{
  "model": "jev-latest",
  "state": "중복 결제를 환불해 주세요.",
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "담당 부서는?",
      "criteria": {"billing": "결제 및 환불", "technical": "기술 지원"}
    },
    "refund": {"type": "noul", "instructions": "환불 요청인가?"},
    "urgency": {"type": "score", "instructions": "긴급도", "criteria": ["낮음", "보통", "높음"]}
  },
  "options": {"temperature": 1.0, "permutations": 1}
}
```

| 유형 | 결과 |
| --- | --- |
| `choice` | 선택지 확률, 최대 확률의 `choice`, 엔트로피 기반 `confidence` |
| `noul` | 참일 선택지의 확률인 `noul` |
| `score` | 0부터 시작하는 등급 인덱스의 기대값 `score`, 확률, `legend`, `confidence` |

`state`와 설명은 문자열 또는 JSON 객체/배열을 받을 수 있습니다. `images`는 HTTP(S) URL 또는 `data:image/...;base64,...` 목록이며, 이미지 바이트 처리와 비전 인코더 실행은 엔진이 담당합니다.

`options.permutations`는 선택지 순서를 회전한 뒤 원래 순서로 복원하여 확률을 평균합니다. **질문 수 × permutations만큼 프리필 평가**가 발생합니다. `return_logprobs: true`는 각 평가의 원래 vocabulary logprob를 제공합니다. `assistant_prefix`를 설정하면 실제 응답 경계에서 라벨이 단일 토큰인지 다시 검증합니다.

확률은 지정한 라벨 안에서 정규화한 값입니다. `confidence = 1 - entropy / log(선택지 수)`는 실제 정답률의 보정값이 아닙니다. 학습하지 않은 모델의 판단 정확도는 별도로 평가해야 합니다.

## 엔진 API와 지원 범위

사용하는 공개 API는 `/model_info`, `/server_info`, `/v1/tokenize`, `/v1/detokenize`, `/generate`입니다. SGLang upstream [`0024efa0de38794ee309ba10ab00ebb891a3d050`](https://github.com/sgl-project/sglang/tree/0024efa0de38794ee309ba10ab00ebb891a3d050)의 구현을 기준으로 연결 규약을 확인했습니다. 오래된 릴리스에 필요한 API가 없으면 엔진 버전을 올려야 합니다.

일반 텍스트는 템플릿을 적용한 token IDs를 엔진에 전달합니다. 이미지 요청은 Qwen VL/Qwen3.5, Mistral3/Pixtral 계열의 일반적인 텍스트 기반 멀티모달 경로를 대상으로 합니다. 이미지가 포함된 프롬프트의 특수 토큰과 원본 이미지를 함께 전달합니다. 토큰만으로 프롬프트를 표현하는 다른 VLM 계열은 명시적으로 거부합니다. 모델마다 이미지 경로의 GPU 통합 검증이 필요합니다.

`/generate`에는 `max_new_tokens: 0`, `return_logprob: true`, `token_ids_logprob: [...]`를 설정합니다. 모든 라벨의 유한한 logprob와 `completion_tokens == 0`을 확인합니다. 누락된 확률이나 토큰 사용량을 임의로 보완하지 않습니다. speculative decoding/MTP를 사용하지 않는 일반 generation 서버가 필요합니다.

현재의 엄격한 프롬프트 검증은 평가마다 템플릿 토큰화, detokenize, 라벨 경계 일괄 검증, generate의 **HTTP 호출 4회**를 사용합니다. 이 왕복과 CPU 처리 비용은 GPU 프리필 시간에 추가됩니다. `metadata.adapter_elapsed_ms`는 이 작업과 대기 시간을 포함하고, 외부 HTTP 응답 직렬화/전송 시간은 제외합니다. `smoke.py`는 클라이언트에서 전체 왕복 시간을 표시합니다. GPU 간 지연 비교 수치로 대신 사용할 수 없습니다.

선택형 공식 토크나이저 경로는 초기 라벨 검증 이후 평가마다 CPU 토큰화와 엔진
`/generate` 호출 1회를 사용합니다. 두 경로의 HTTP 지연에는 서로 다른 CPU 처리와
왕복 횟수가 포함되므로 순수 모델 연산 성능처럼 비교하면 안 됩니다.

클라이언트 연결이 끊어지면 어댑터의 대기 작업과 엔진 HTTP 요청을 취소합니다. 이후 정리는 기본 엔진의 disconnect 처리에 의존합니다. 이미 실행 중인 GPU 연산을 즉시 중단한다는 보장은 없습니다.

vLLM 백엔드는 아직 구현하지 않았습니다. 추가 시 `ScoringBackend` 인터페이스를 구현하면 질문/응답 규약은 그대로 재사용할 수 있습니다.

## 검증과 코드

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

테스트는 실제 프로토콜/서비스를 사용하고 추론 서버 HTTP 응답만 모의합니다. 확률 정규화, 순서 복원, 혼합 질문, 이미지 전달, 오류, 취소와 동시 실행 제한을 검증합니다. 이 테스트 통과는 NVIDIA GPU에서의 정확도·성능 또는 모델별 이미지 처리 성공을 뜻하지 않습니다.

2026-09-21 검증: 독립 Python 3.12 가상환경에서 **97개 테스트와 74개 하위 케이스 통과**, Ruff 통과. 기본 어댑터 환경에는 SGLang, vLLM, PyTorch, Transformers, MLX가 필요하지 않습니다. H200의 공식 SGLang 0.5.20 wheel로 네 모델 각각 4,006개 요청의 전체 벤치를 완료했으며, Ministral은 선택형 CPU 토크나이저 환경을 사용합니다.

2026-09-23 `--prompt-wording native` 추가 검증: 같은 가상환경에서 **136개 테스트와 80개 하위 케이스 통과**, Ruff 통과. 운영 서버(CPU 전용, GPU 미사용)에서 `jevbench-original`/`internal-eval-v1`/`jevbench-hard` 실제 레코드로 어댑터의 `native` 문구·토큰 ID 렌더링을 jevbench-hard 러너의 `run_suites_rotation.py` 계약과 직접 비교했습니다(위 "프롬프트 문구" 절 참고).

| 파일 | 역할 |
| --- | --- |
| `jev_adapter/protocol.py` | 요청 스키마, 프롬프트, 확률 및 응답 계산 |
| `jev_adapter/service.py` | 질문별 평가 실행, 병렬 수 제한, 결과 조합 |
| `jev_adapter/sglang.py` | 공개 SGLang HTTP API 클라이언트 |
| `jev_adapter/server.py` | 독립 FastAPI 서버 및 인증 |
| `jev_adapter/backend.py` | 다른 추론 엔진을 연결할 최소 인터페이스 |

이 레포는 엔진 소스 트리나 형제 디렉터리를 import하지 않습니다. 기존 `sglang-jev` 실험 레포와 벤치마크 결과는 원래 위치에 남아 있습니다. 초기 프로토콜 코드의 출처는 [NOTICE](NOTICE)를 참고하세요.

## H200 학습 전 벤치마크

[benchmarks/README.md](benchmarks/README.md)에 H200 한 장에서 Ministral 3 3B, Qwen3.5-4B, Qwen3.6-27B, Qwen3.6-35B-A3B를 순서대로 평가하는 절차가 있습니다. 기본 비교는 BF16이며 KEV 공개 개발 세트의 정확도·확률 품질·HTTP 지연시간을 기록합니다. 데이터와 모델 리비전을 고정했고 H200 실측을 완료했습니다. KEV 외 공개 평가셋 조사는 [benchmarks/PUBLIC_DATASETS.md](benchmarks/PUBLIC_DATASETS.md)를 참고하세요.
