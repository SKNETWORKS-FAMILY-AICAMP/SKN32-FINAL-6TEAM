# 서버에서: 임베딩 모델(질문<->항목 코사인)과 재평가 모델(질문·항목 쌍 점수). 문장을 만들지 않는다.
import json, os, sys, time
import torch

pairs = json.load(open('pairs.json', encoding='utf-8'))
out = json.load(open('emb_rr_out.json')) if os.path.exists('emb_rr_out.json') and os.path.getsize('emb_rr_out.json') else {}
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
docs = sorted({p['doc'] for p in pairs})
qs = sorted({p['q'] for p in pairs})


def emb_model(name):
    from sentence_transformers import SentenceTransformer
    if 'VL-Embedding-8B' in name:
        # 16GB 에 다 안 들어간다 — GPU 13GB 까지만 올리고 나머지는 서버 메모리로 넘긴다
        m = SentenceTransformer(name, trust_remote_code=True, model_kwargs={
            'torch_dtype': torch.float16, 'device_map': 'auto', 'max_memory': {0: '13GiB', 'cpu': '200GiB'}})
    else:
        m = SentenceTransformer(name, device='cuda', trust_remote_code=True, model_kwargs={'torch_dtype': torch.float16})
    if 'Qwen3-Embedding' in name or 'VL-Embedding' in name:
        qv = m.encode(qs, prompt=f'Instruct: {TASK}\nQuery: ', normalize_embeddings=True, batch_size=16)
    else:
        qv = m.encode(qs, normalize_embeddings=True, batch_size=16)
    dv = m.encode(docs, normalize_embeddings=True, batch_size=16)
    qi = {q: i for i, q in enumerate(qs)}
    di = {d: i for i, d in enumerate(docs)}
    return [float((qv[qi[p['q']]] * dv[di[p['doc']]]).sum()) for p in pairs]


BIG = {'torch_dtype': torch.float16, 'device_map': 'auto', 'max_memory': {0: '13GiB', 'cpu': '200GiB'}}


def vl_rr(name):
    # 공식 안내: sentence-transformers CrossEncoder + prompt. 8B 는 GPU 13GB 까지만, 나머지는 서버 메모리
    from sentence_transformers import CrossEncoder
    if '8B' in name:
        m = CrossEncoder(name, trust_remote_code=True, model_kwargs=BIG)
    else:
        m = CrossEncoder(name, device='cuda', trust_remote_code=True, model_kwargs={'torch_dtype': torch.float16})
    return [float(x) for x in m.predict([(p['q'], p['doc']) for p in pairs], prompt=TASK, batch_size=8,
                                        show_progress_bar=False)]


def ce_rr(name):
    # KaLM(지시문 받음) · zerank(지시문 없음) — 각 카드의 CrossEncoder 사용법
    from sentence_transformers import CrossEncoder
    if 'KaLM' in name:
        m = CrossEncoder(name, trust_remote_code=True, device='cuda', model_kwargs={'dtype': torch.bfloat16, 'chunk_size': 4})
        return [float(x) for x in m.predict([(p['q'], p['doc']) for p in pairs], prompt=TASK, batch_size=8,
                                            show_progress_bar=False)]
    m = CrossEncoder(name, device='cuda', model_kwargs={'torch_dtype': torch.bfloat16})
    return [float(x) for x in m.predict([(p['q'], p['doc']) for p in pairs], batch_size=8, show_progress_bar=False)]


def qwen3_rr(name):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(name, padding_side='left')
    if '8B' in name:
        m = AutoModelForCausalLM.from_pretrained(name, **BIG).eval()
    else:
        m = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16, device_map='cuda').eval()
    yes, no = tok.convert_tokens_to_ids('yes'), tok.convert_tokens_to_ids('no')
    pre = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct '
           'provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
    suf = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    texts = [f"{pre}<Instruct>: {TASK}\n<Query>: {p['q']}\n<Document>: {p['doc']}{suf}" for p in pairs]
    s = []
    with torch.no_grad():
        for i in range(0, len(texts), 16):
            enc = tok(texts[i:i + 16], padding=True, truncation=True, max_length=512, return_tensors='pt').to('cuda')
            lg = m(**enc).logits[:, -1, :]
            pr = torch.softmax(torch.stack([lg[:, no], lg[:, yes]], 1).float(), 1)[:, 1]
            s += pr.tolist()
    return s


def jina_rr(name):
    from transformers import AutoModel
    m = AutoModel.from_pretrained(name, torch_dtype='auto', trust_remote_code=True).to('cuda').eval()
    by_q = {}
    for k, p in enumerate(pairs):
        by_q.setdefault(p['q'], []).append(k)
    s = [0.0] * len(pairs)
    for q, ks in by_q.items():
        for item in m.rerank(q, [pairs[k]['doc'] for k in ks]):
            s[ks[item['index']]] = float(item['relevance_score'])
    return s


for name in sys.argv[1:]:
    t = time.time()
    try:
        if 'VL-Reranker' in name:
            sc = vl_rr(name)
        elif 'Reranker' in name and 'Qwen3' in name:
            sc = qwen3_rr(name)
        elif 'KaLM-Reranker' in name or 'zerank' in name:
            sc = ce_rr(name)
        elif 'jina-reranker' in name:
            sc = jina_rr(name)
        else:
            sc = emb_model(name)
        out[name] = sc
        print(name, 'OK', f'{time.time() - t:.0f}s', flush=True)
    except Exception as e:  # noqa: BLE001
        print(name, 'FAIL', repr(e)[:300], flush=True)
    json.dump(out, open('emb_rr_out.json.tmp', 'w')); os.replace('emb_rr_out.json.tmp', 'emb_rr_out.json')
    torch.cuda.empty_cache()
