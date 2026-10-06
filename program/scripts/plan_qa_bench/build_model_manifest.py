# 시험한 모델마다 「출처 · 수정판 · 받은 시각 · 형식 · 서빙 엔진/버전 · 설정 · 서버에 남았는지」를 한 표로 만든다.
#  입력: results/export/models.csv(시험한 73개 방식) + 서버에서 수집한 환경 기록(results/_pull/env/env_*.txt, server/collect_env.sh) + 스크립트에서 읽은 설정.
#  원칙: 확인한 값만 적는다. 서버에서 지워져 수정판·받은 날을 알 수 없는 것은 「기록 없음」으로 둔다(지어내지 않는다).
#  출력: results/export/model_manifest.csv (엑셀에서 열리게 utf-8-sig)
# 사용: python build_model_manifest.py     (서버 환경을 다시 수집한 뒤 아래 FACTS 를 고쳐 다시 돌린다)
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, 'results', 'export')
NONE = '기록 없음'

OLLAMA_SET = ('format=JSON 스키마 강제 · think=false · temperature=0 (server/llm_tasks.py 45행 기준, 다른 풀이 스크립트와는 대조하지 않음) · '
              'top_k·top_p 등은 모델 기본값(gemma4: top_k 64 · top_p 0.95) · num_ctx 지정 안 함(올라마 기본값, 값은 확인하지 못함)')
OLLAMA_ENG = '올라마 0.34.4 (2026-10-06 수집 시점 버전 — 측정 당시와 다를 수 있음)'
LLAMA_ENG = 'llama.cpp 0.5.0-dev (build 1, commit 4ebdf2c · 서버 A 수집 시점)'

# 시험 방식 이름(models.csv 의 model 열 앞부분) → 확인한 사실
FACTS = {
    'Gemma 4 26B-A4B Q4_K_M (올라마)': dict(src='올라마 gemma4:26b-a4b-it-q4_K_M', rev='올라마 아이디 5571076f3d70', when='2026-09-30 23:47 UTC (올라마 매니페스트 시각)',
                                           fmt='Q4_K_M · 17GB', eng=OLLAMA_ENG, cfg=OLLAMA_SET, left='서버 A 에 있음'),
    'Gemma 4 12B (올라마)': dict(src='올라마 gemma4:12b', rev='올라마 아이디 4eb23ef187e2', when='2026-09-28 18:49 UTC (올라마 매니페스트 시각)',
                              fmt='Q4_K_M · 7.6GB', eng=OLLAMA_ENG, cfg=OLLAMA_SET, left='서버 A 에 있음'),
    'Gemma 4 E4B QAT (올라마)': dict(src='올라마 gemma4:e4b-it-qat', rev='올라마 아이디 ee6656371218', when='2026-09-30 22:14 UTC (올라마 매니페스트 시각)',
                                  fmt='Q4_0 (QAT) · 6.1GB', eng=OLLAMA_ENG, cfg=OLLAMA_SET, left='서버 A 에 있음'),
    'OpenJev 26B Q4_K_M': dict(src='허깅페이스 ggml-org/OpenJev-GGUF · OpenJev-Q4_K_M.gguf', rev='10840f375658dea7afc5ff4711127bca8218b560',
                             when='2026-10-05 19:20 UTC (다시 받은 시각 — 10-02~03 의 첫 시험에도 받아 쓰고 지웠으나 그때 수정판은 기록 없음)',
                             fmt='Q4_K_M · 18,973,872,288 바이트', eng=LLAMA_ENG,
                             cfg='서버 옵션 --fit on -c 8192 -np 1 · /v1/systemone 에 질문 하나(선택지 = 일정 항목 한 줄 설명 + none)', left='서버 A 에 있음'),
    'Winnow-E4B Q8': dict(src='허깅페이스 EldanRing/Winnow-E4B · gguf/Winnow-E4B-Q8_0.gguf', rev='1b257e8fa80b270a62338362a8b35e37f7890273', when='2026-10-03 19:43 UTC',
                          fmt='Q8_0 · 8,005,437,472 바이트',
                          eng='winnow-inference 커밋 77d14580(2026-09-24 작성) · scripts/serve.py',
                          cfg='--profile 5070ti-64k --text-only --context 8192 · /v1/systemone', left='서버 A 에 있음'),
    'Winnow-12B Q8': dict(src='허깅페이스 EldanRing/Winnow-12B · gguf/Winnow-12B-Q8_0.gguf', rev=NONE, when=NONE, fmt='Q8_0', eng='winnow-inference(커밋 기록 없음)',
                          cfg='--profile 5070ti-64k --text-only --context 8192 (run_night 대기열 기준)', left='지워짐'),
}

# models.csv 에 없는 모델·학습 결과 — 같은 칸으로 따로 적는다
EXTRA = [
    dict(model='가르친 E4B (QLoRA 학습, 서버 B)', src='허깅페이스 google/gemma-4-E4B-it (bf16 원본) + LoRA 어댑터 e4b_r16_e2', rev='원본 ee0ef6023621cff504d758262d4e04895a5af4a2',
         when='원본 2026-10-05 11:49 UTC 받음 · 어댑터 2026-10-05 14:30 UTC 저장(학습 시작 12:01 UTC, 148.7분)', fmt='학습 때 NF4 4비트 적재(계산 bf16) · 어댑터 r16 alpha32 dropout0.05 · 언어 모델 선형층 7종',
         eng='서버 B: torch 2.14.1+cu130 · transformers 5.18.0 · peft 0.21.2 · bitsandbytes 0.50.2 · GPU RTX A4000 16GB(드라이버 595.91, CUDA 13.2)',
         cfg='qlora_train.py --epochs 2 --lr 2e-4(코사인) --rank 16 --accum 8(유효 배치 8) · maxlen 3072 · 시드 기본값 20261005 · 손실은 정답 토큰만 · 평가는 greedy(do_sample=False) max_new_tokens 12',
         left='서버 B 에 있음'),
    dict(model='가르친 E4B — CPU 배포판(Q8 GGUF)', src='위 어댑터를 원본에 텐서 단위로 합침(merge_lora_tensors.py) → GGUF Q8_0', rev='합친 파일 /root/e4bt-Q8_0.gguf 8,005,437,472 바이트',
         when='2026-10-05 21:16 UTC', fmt='Q8_0', eng='서버 B: llama.cpp 0.5.0-dev (build 1, commit bed0a85)',
         cfg='llama-server -t 4 -ngl 0 -c 4096 -np 1 --jinja · 요청 max_tokens 16 · temperature 0 · cache_prompt true · taskset 코어 4개', left='서버 B 에 있음'),
    dict(model='Gemma 4 E2B (학습용, 서버 B)', src='허깅페이스 google/gemma-4-E2B-it', rev='3e22461f65e89153144f8adb70e3b8c2cc9845a7', when='2026-10-05 18:36 UTC', fmt='bf16 원본 → 학습 NF4',
         eng='서버 B 위와 같음', cfg='같은 학습 설정(epochs 2 · lr 2e-4 · rank 16 · accum 8) · 어댑터 e2b r16 alpha32 2026-10-05 23:17 UTC', left='서버 B 에 있음'),
    dict(model='Kanana-2-3B-Instruct (학습용, 서버 B)', src='허깅페이스 kanana-2-3b-instruct (서버 폴더 이름만 확인 — 저장소 전체 이름은 기록 없음 `[미확인]`)', rev='6a5d7889964c4c590299d16e309eabab1f73f8a9', when='2026-10-05 22:18 UTC',
         fmt='bf16 원본 → 학습 NF4', eng='서버 B 위와 같음', cfg='같은 학습 설정 · 스모크 어댑터 2026-10-06 00:48 UTC 에서 본 학습 시작', left='서버 B 에 있음'),
    dict(model='Qwen3.5-4B (서버 B)', src='허깅페이스 Qwen/Qwen3.5-4B', rev='851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a', when='2026-10-05 20:50 UTC', fmt='bf16 원본', eng='서버 B 위와 같음',
         cfg='(시험 대기 — 설정은 시험 때 적는다)', left='서버 B 에 있음'),
    dict(model='Laya 다국어판 (분류 시험, 서버 A)', src='허깅페이스 convaiinnovations/laya-multilingual', rev='1720e3e3357cfe1e281542e223f8273b0890ca34', when='2026-10-06 00:43 UTC',
         fmt='원본(fp32 추정 — 확인 안 함 `[미확인]`)', eng='서버 A 로컬 디스크 환경: laya 0.3.28 · opendecider 0.8.1 · torch 2.8.0+cu128 · GPU RTX 2000 Ada 16GB(드라이버 580.159, CUDA 13.0)',
         cfg='server/jev_cls_run.py: 질문 4개를 한 번에(criteria = 라벨 설명, 한국어·영어 두 판) · device cuda · 학습 없음', left='서버 A 에 있음'),
    dict(model='Qwen3-Embedding-0.6B + LoRA 학습 임베딩(e16c · e16d · e16v2)', src='허깅페이스 Qwen/Qwen3-Embedding-0.6B + 어댑터 3종', rev='원본 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3',
         when='원본 2026-10-01 02:06 UTC · 어댑터 e16c 09-30 14:28 · e16v2 09-30 18:26 · e16d 10-02 14:06 (UTC)', fmt='원본 bf16/fp16(확인 안 함) + LoRA r16 alpha32', eng='서버 A: torch 2.8.0+cu128 · transformers 5.17.0 · peft 0.21.1 · sentence_transformers 6.1.0',
         cfg='학습 자료·문턱은 문서 §20~§39 참고', left='서버 A 에 있음'),
]
ENC = [  # 서버 B 에서 학습한 분류 인코더 — 허깅페이스 캐시의 수정판 해시(받은 시각 2026-10-05 22:45~23:17 UTC)
    ('BAAI/bge-m3', '5617a9f61b02… · 9a0624b896d8…(캐시에 2개 — 어느 쪽인지 기록 없음)'), ('intfloat/multilingual-e5-base', 'd12875059715…'), ('intfloat/multilingual-e5-small', '614241f622f5…'),
    ('FacebookAI/xlm-roberta-base', 'e73636d4f797…'), ('jhu-clsp/mmBERT-base', 'c5955035435e… · ca5b84ba39fb…(2개 — 기록 없음)'), ('jhu-clsp/mmBERT-small', '461475a70b19… · abc32620dd4f…(2개 — 기록 없음)'),
    ('skt/A.X-Encoder-base', '9708f9c404ac…'), ('klue/roberta-base', '02f94ba5e3fc…'), ('klue/roberta-large', '28d911204e90…'), ('klue/roberta-small', 'b6b4c36d827e…'),
    ('beomi/KcELECTRA-base-v2022', '568fe985a10c… · 87285578b468…(2개 — 기록 없음)'), ('monologg/koelectra-base-v3-discriminator', '0e9ddb58c86b… · 68b30cd259f3…(2개 — 기록 없음)'),
    ('monologg/koelectra-small-v3-discriminator', '7488f8db0f20… · 910a9b1513665…(2개 — 기록 없음)'),
]


def main():
    rows = list(csv.DictReader(open(os.path.join(EXPORT, 'models.csv'), encoding='utf-8-sig')))
    out = []
    for r in rows:
        name = r['model']
        f = next((v for k, v in FACTS.items() if name.startswith(k)), None)
        base = dict(kind=r['kind'], model=name, size_storage_active=r['size_storage_active'], serving_from_models_csv=r['serving'])
        if f:
            out.append({**base, '출처': f['src'], '수정판·아이디': f['rev'], '받은·기록 시각': f['when'], '형식': f['fmt'], '서빙 엔진·버전': f['eng'], '설정': f['cfg'], '서버에 남음': f['left']})
        elif r['kind'] == 'combo':
            out.append({**base, '출처': '(조합 — 구성 모델 행을 본다)', '수정판·아이디': '-', '받은·기록 시각': '-', '형식': '-', '서빙 엔진·버전': '-', '설정': '문턱·규칙은 해당 문서 절과 choose_thresholds_*.py 에 있음', '서버에 남음': '-'})
        elif 'API' in r['size_storage_active'] or '클라우드' in r['size_storage_active']:
            out.append({**base, '출처': '외부 서비스(모델 내부 버전은 공급자가 정함)', '수정판·아이디': NONE, '받은·기록 시각': '시험일은 문서 해당 절', '형식': '-', '서빙 엔진·버전': r['serving'], '설정': '문서 해당 절(생각 설정 통제 불가라고 표시)', '서버에 남음': '해당 없음'})
        else:
            out.append({**base, '출처': NONE, '수정판·아이디': NONE, '받은·기록 시각': NONE + '(서버에서 지워져 복구 불가)', '형식': r['size_storage_active'], '서빙 엔진·버전': r['serving'] + '(버전 ' + NONE + ')', '설정': NONE, '서버에 남음': '지워짐'})
    for e in EXTRA:
        out.append(dict(kind='extra', model=e['model'], size_storage_active='', serving_from_models_csv='', **{'출처': e['src'], '수정판·아이디': e['rev'], '받은·기록 시각': e['when'], '형식': e['fmt'], '서빙 엔진·버전': e['eng'], '설정': e['cfg'], '서버에 남음': e['left']}))
    for m, rev in ENC:
        out.append(dict(kind='extra', model=f'분류 인코더 {m}', size_storage_active='', serving_from_models_csv='', **{'출처': '허깅페이스 ' + m, '수정판·아이디': rev, '받은·기록 시각': '2026-10-05 22:45~23:17 UTC (서버 B 캐시)', '형식': '원본 fp32 적재 · 학습은 bf16 자동혼합',
                                                                                       '서빙 엔진·버전': '서버 B: torch 2.14.1+cu130 · transformers 5.18.0', '설정': 'server/train_cls.py: 공유 인코더 + 머리 4개 · lr 3e-5 · 에폭 8 또는 20(개발 점수가 높은 쪽) · 시드 3 · maxlen 96 · 배치 32', '서버에 남음': '서버 B 캐시에 있음'}))
    cols = list(out[0].keys())
    with open(os.path.join(EXPORT, 'model_manifest.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    known = sum(1 for o in out if o['kind'] != 'combo' and o['수정판·아이디'] not in (NONE, '-'))
    gone = sum(1 for o in out if o['kind'] not in ('combo', 'extra') and o['수정판·아이디'] == NONE and o['서버에 남음'] == '지워짐')
    print('행', len(out), '· 수정판을 아는 행', known, '· 지워져 기록 없는 행', gone)


if __name__ == '__main__':
    main()
