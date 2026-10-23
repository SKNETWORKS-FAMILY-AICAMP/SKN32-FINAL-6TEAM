# 서버에서: 「ML 앞단이 후보를 K개로 줄이고 가르친 E4B 가 그 안에서 고른다」가 의미가 있으려면 정답 항목이 후보 K개 안에 들어야 한다 — 임베딩 검색기마다 후보 재현율(recall@K)을 잰다.
#  질의 = (앞 대화 마지막 두 마디 + 고객 질문), 문서 = 「제목 @ 장소 [종류]」. 정답이 일정 항목인 문제(요청 둘 제외, 정답 null 제외)만 센다. 새 학습 없음 — 공개 임베딩 모델을 그대로 쓴다.
#  사용: python retriever_recall.py <모델이름> [<모델이름> …]   → retriever_recall_<모델>.json (문제별 정답 순위)
import json, os, sys, time
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
KS = (1, 3, 5, 8, 10)
for name in sys.argv[1:]:
    t0 = time.time()
    kw = {'trust_remote_code': False}
    m = SentenceTransformer(name, device='cuda', model_kwargs={'torch_dtype': torch.float16}, **kw)
    m.max_seq_length = 256
    ranks, types = [], []
    qpre = 'query: ' if 'e5' in name.lower() else ''
    dpre = 'passage: ' if 'e5' in name.lower() else ''
    for s in SETS:
        job = json.load(open(f'/root/work/{s}.json', encoding='utf-8'))['sets'][s]
        items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
        ids = [i['id'] for i in items]
        docs = [dpre + f"{i['title']} @ {i['place']} [{i['kind']}]" for i in items]
        qs = job['qs']
        texts = []
        for x in qs:
            hist = ' '.join(h['text'] for h in (x.get('history') or [])[-2:])
            texts.append(qpre + (hist + ' ' if hist else '') + x['q'])
        with torch.inference_mode():
            D = m.encode(docs, normalize_embeddings=True, batch_size=64, convert_to_numpy=True)
            Q = m.encode(texts, normalize_embeddings=True, batch_size=64, convert_to_numpy=True)
        S = Q @ D.T
        for qi, x in enumerate(qs):
            if x['type'] == 'compound_intent' or x['gold'] is None:
                continue
            order = np.argsort(-S[qi])
            rank = 1 + [ids[j] for j in order].index(x['gold'])
            ranks.append(rank)
            types.append(x['type'])
    r = np.array(ranks)
    out = {'model': name, 'n': int(len(r)), 'recall': {f'@{k}': float((r <= k).mean()) for k in KS}, 'by_type': {}}
    for t in sorted(set(types)):
        rr = np.array([a for a, b in zip(ranks, types) if b == t])
        out['by_type'][t] = {'n': int(len(rr)), **{f'@{k}': round(float((rr <= k).mean()), 3) for k in (5, 8)}}
    json.dump({**out, 'ranks': ranks, 'types': types}, open(f"/root/work/retriever_recall_{name.replace('/', '_')}.json", 'w', encoding='utf-8'), ensure_ascii=False)
    print(name, f'{time.time() - t0:.0f}초', json.dumps(out['recall']), flush=True)
    for t, v in out['by_type'].items():
        print('   ', t, v, flush=True)
    del m
    torch.cuda.empty_cache()
