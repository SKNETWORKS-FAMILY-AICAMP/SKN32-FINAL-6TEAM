# 서버에서 돌린다: 질문·일정 쌍마다 관련도 점수(0~1). 모델은 문장을 만들지 않는다.
import json, sys, time
from sentence_transformers import CrossEncoder
pairs = json.load(open('pairs.json', encoding='utf-8'))
out = {}
for name in sys.argv[1:] or ['BAAI/bge-reranker-v2-m3']:
    t = time.time()
    m = CrossEncoder(name, max_length=512)
    s = m.predict([(p['q'], p['doc']) for p in pairs], batch_size=64, show_progress_bar=False)
    out[name] = [float(x) for x in s]
    print(name, len(s), f'{time.time() - t:.1f}s', flush=True)
json.dump(out, open('scores.json', 'w'), ensure_ascii=False)
