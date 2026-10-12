# 서버에서: WeMM-Embedding(텐센트) 질문↔항목 점수. emb_rr_out.json 과 같은 모양(모델 이름 -> 쌍 3,498개 점수 배열)으로 합쳐 저장한다.
import json, os, sys, time
import torch

pairs = json.load(open('pairs.json', encoding='utf-8'))
out = json.load(open('emb_rr_out.json')) if os.path.exists('emb_rr_out.json') and os.path.getsize('emb_rr_out.json') else {}
docs = sorted({p['doc'] for p in pairs})
qs = sorted({p['q'] for p in pairs})
for name in sys.argv[1:]:
    t = time.time()
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(name, device='cuda', trust_remote_code=True, model_kwargs={'torch_dtype': torch.bfloat16})
        qv = m.encode_query(qs, normalize_embeddings=True, batch_size=int(os.environ.get('BS', '16')))
        dv = m.encode_document(docs, normalize_embeddings=True, batch_size=int(os.environ.get('BS', '16')))
        qi = {q: i for i, q in enumerate(qs)}
        di = {d: i for i, d in enumerate(docs)}
        out[name] = [float((qv[qi[p['q']]] * dv[di[p['doc']]]).sum()) for p in pairs]
        print(name, 'OK', f'{time.time() - t:.0f}s', flush=True)
    except Exception as e:  # noqa: BLE001
        print(name, 'FAIL', repr(e)[:300], flush=True)
    tmp = 'emb_rr_out.json.tmp'
    json.dump(out, open(tmp, 'w'))
    os.replace(tmp, 'emb_rr_out.json')
    torch.cuda.empty_cache()
