# 2026-10-16 임베딩 비교: bge-m3 · arctic-ko · arctic 원본 · EmbeddingGemma 2 를 같은 두 시험에 붙인다.
#  ① 일정 항목 짚기 90문제(판정용): emb_rr.py 와 같은 pairs.json 의 질문↔항목 코사인 → emb_rr_out_20261016.json
#     채점은 로컬에서 eval_models.py 로 한다(문턱은 개발용 묶음에서만 고른다).
#  ② 규정 검색 180문항: rag_gate/server/embed_compare_20261012.py 와 같은 조각 130 · 같은 변형 E · 같은 지표
#     → policy_<tag>.json
#  GPU 대기열과 부딪히지 않게 CPU(fp32)로 돈다. 디스크가 좁아 모델을 한 개씩 받고 재고 나서 지운다.
# 사용: HF_HOME=<임시 폴더> python emb_cmp_20261016.py <모델 키> [<모델 키> ...]
import json, os, shutil, sys, time

import numpy as np
import torch

torch.set_num_threads(int(os.environ.get('EMB_THREADS', '32')))
HERE = os.path.dirname(os.path.abspath(__file__))

MODELS = {
    # 키: (HF id, 질문 쪽 encode 인자, 문서 쪽 encode 인자, 불러오기 인자)
    'bge-m3': ('BAAI/bge-m3', {}, {}, {}),
    'arctic-ko': ('dragonkue/snowflake-arctic-embed-l-v2.0-ko', {'prompt_name': 'query'}, {}, {}),
    'arctic-l-v2': ('Snowflake/snowflake-arctic-embed-l-v2.0', {'prompt_name': 'query'}, {}, {}),
    # 카드 사용법: 질문 SearchQuery · 문서 Document, 글만 쓸 때는 그림·소리 부분을 빼고 불러온다
    'embeddinggemma-2': ('google/embeddinggemma-2', {'prompt_name': 'SearchQuery'}, {'prompt_name': 'Document'},
                         {'config_kwargs': {'vision_config': None, 'audio_config': None}}),
}


SKIP = ('onnx/', 'openvino/', '.onnx', '.h5', '.msgpack', '.ot', 'tf_model', 'flax_model', 'rust_model', '.gguf')
KEEP_FREE = 1.5 * 2 ** 30  # 받은 뒤에도 남아야 하는 여유(다른 작업이 같은 /dev/shm 을 쓴다)


def load(hf_id, extra):
    # 같은 무게를 여러 형식으로 올린 저장소가 있다 — safetensors 가 있으면 .bin 은 받지 않는다
    from huggingface_hub import HfApi, snapshot_download
    from sentence_transformers import SentenceTransformer
    info = HfApi().model_info(hf_id, files_metadata=True)
    files = [(s.rfilename, s.size or 0) for s in info.siblings if not any(k in s.rfilename for k in SKIP)]
    if any(f.endswith('.safetensors') for f, _ in files):
        files = [(f, n) for f, n in files if not f.endswith('.bin')]
    need = sum(n for _, n in files)
    free = shutil.disk_usage(os.environ.get('HF_HOME', '/tmp')).free
    if free - need < KEEP_FREE:
        raise RuntimeError(f'디스크 부족: 받을 {need / 2**30:.2f}GiB, 여유 {free / 2**30:.2f}GiB')
    path = snapshot_download(hf_id, allow_patterns=[f for f, _ in files])
    return SentenceTransformer(path, device='cpu', trust_remote_code=True, **extra)


def enc(m, texts, kw):
    return np.asarray(m.encode(texts, normalize_embeddings=True, batch_size=16, **kw))


def plan_scores(m, qkw, dkw):
    pairs = json.load(open(os.path.join(HERE, 'pairs.json'), encoding='utf-8'))
    docs = sorted({p['doc'] for p in pairs})
    qs = sorted({p['q'] for p in pairs})
    qv, dv = enc(m, qs, qkw), enc(m, docs, dkw)
    qi = {q: i for i, q in enumerate(qs)}
    di = {d: i for i, d in enumerate(docs)}
    return [float(qv[qi[p['q']]] @ dv[di[p['doc']]]) for p in pairs]


def policy_metrics(m, qkw, dkw, hf_id, tag):
    ch = json.load(open(os.path.join(HERE, 'policy_chunks.json'), encoding='utf-8'))
    qs = json.load(open(os.path.join(HERE, 'rag_questions.json'), encoding='utf-8'))['questions']
    th = 0.55
    sims = enc(m, [q['q'] for q in qs], qkw) @ enc(m, [f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}" for c in ch], dkw).T
    line_mask = np.array([bool(c['line']) for c in ch])
    sources = [c['source'] for c in ch]
    ans = [i for i, q in enumerate(qs) if q['type'] == 'answerable']
    neg = [i for i, q in enumerate(qs) if q['type'] in ('uncovered', 'offtopic')]
    hit = {1: 0, 3: 0, 5: 0}
    for i in ans:
        order = [sources[j] for j in np.argsort(-np.where(line_mask, sims[i], -9))]
        for k in hit:
            hit[k] += bool(set(order[:k]) & set(qs[i]['gold']))
    top_ans = [float(np.max(np.where(line_mask, sims[i], -9))) for i in ans]
    top_neg = [float(np.max(np.where(line_mask, sims[i], -9))) for i in neg]
    met = dict(model=hf_id, tag=tag, answerable=len(ans), unanswerable=len(neg),
               hit_at_1=hit[1], hit_at_3=hit[3], hit_at_5=hit[5],
               top1_answerable_mean=round(float(np.mean(top_ans)), 4), top1_unanswerable_mean=round(float(np.mean(top_neg)), 4),
               pass_rate_answerable=round(float(np.mean([s >= th for s in top_ans])), 4),
               block_rate_unanswerable=round(float(np.mean([s < th for s in top_neg])), 4), threshold=th,
               variant='E_문서제목+절제목+고객용문장', device='cpu-fp32')
    json.dump(dict(metrics=met, sources=sources, sims=np.round(sims, 6).tolist()),
              open(os.path.join(HERE, f'policy_{tag}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return met


out_path = os.path.join(HERE, 'emb_rr_out_20261016.json')
out = json.load(open(out_path)) if os.path.exists(out_path) else {}
for key in sys.argv[1:]:
    hf_id, qkw, dkw, extra = MODELS[key]
    t = time.time()
    try:
        m = load(hf_id, extra)
        info = dict(dim=m.get_sentence_embedding_dimension(), load_s=round(time.time() - t, 1))
        out[hf_id] = plan_scores(m, qkw, dkw)
        json.dump(out, open(out_path + '.tmp', 'w')); os.replace(out_path + '.tmp', out_path)
        met = policy_metrics(m, qkw, dkw, hf_id, key)
        print(key, 'OK', json.dumps({**info, **met, 'sec': round(time.time() - t)}, ensure_ascii=False), flush=True)
        del m
    except Exception as e:  # noqa: BLE001
        print(key, 'FAIL', repr(e)[:600], flush=True)
    # 디스크가 좁다 — HF_HOME 은 이 시험 전용 폴더라 받은 파일을 통째로 지운다
    hf_home = os.environ['HF_HOME']
    for sub in ('hub', 'xet'):
        shutil.rmtree(os.path.join(hf_home, sub), ignore_errors=True)
    print(key, 'cleaned, free GiB', round(shutil.disk_usage(hf_home).free / 2 ** 30, 2), flush=True)
