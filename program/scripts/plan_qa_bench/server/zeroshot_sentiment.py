# 서버에서: 공개된 감정(긍·부정) 분류 모델을 학습 없이 그대로 우리 메시지에 돌려 positive/neutral/negative 로 맞춘다 — 「더 잘하는 애들이 있잖아」를 오늘 기준으로 확인한다.
#  라벨 대응: 모델의 라벨 이름에서 pos/neg/neu 를 읽는다(매우 부정·긍정 5단계는 둘씩 합침). 이진 모델(NSMC)은 중립이 없어 「확률이 0.5±마진 안」을 중립으로 본다 — 마진은 학습 자료(train.jsonl)에서 고른다.
# 사용: python zeroshot_sentiment.py <test.jsonl 이름들, 쉼표>  → zeroshot_sentiment.json
import json, os, sys
import numpy as np
import torch
from transformers import pipeline

W = '/root/work/cls'
TESTS = sys.argv[1].split(',')
MODELS = ['daekeun-ml/koelectra-small-v3-nsmc', 'Copycats/koelectra-base-v3-generalized-sentiment-analysis', 'nlp04/korean_sentiment_analysis_kcelectra',
          'tabularisai/multilingual-sentiment-analysis', 'clapAI/modernBERT-base-multilingual-sentiment']
S3 = ['positive', 'neutral', 'negative']


def rows(f):
    return [json.loads(l) for l in open(os.path.join(W, f), encoding='utf-8')]


def to3(label):
    l = label.lower()
    if 'neu' in l or l in ('2', 'label_2') and False:
        return 'neutral'
    if 'neg' in l or l in ('label_0', '0', 'negative', '부정'):
        return 'negative'
    if 'pos' in l or l in ('label_1', '1', 'positive', '긍정'):
        return 'positive'
    return None


def f1_macro(p, g):
    f = []
    for c in S3:
        tp = sum(1 for a, b in zip(p, g) if a == c and b == c); fp = sum(1 for a, b in zip(p, g) if a == c and b != c); fn = sum(1 for a, b in zip(p, g) if a != c and b == c)
        if any(b == c for b in g):
            f.append(2 * tp / max(1, 2 * tp + fp + fn))
    return float(np.mean(f))


train = rows('train.jsonl') if os.path.exists(os.path.join(W, 'train.jsonl')) else []
out = {}
for name in MODELS:
    try:
        pipe = pipeline('text-classification', model=name, top_k=None, device=0 if torch.cuda.is_available() else -1, truncation=True, max_length=128)
    except Exception as e:  # noqa: BLE001
        out[name] = {'error': str(e)[:160]}
        print(name, 'ERR', str(e)[:120], flush=True)
        continue
    labels = [pipe.model.config.id2label[i] for i in range(len(pipe.model.config.id2label))]
    print(name, labels, flush=True)

    def probs3(texts):
        res = pipe(texts, batch_size=32)
        out3 = []
        for r in res:
            d = {'positive': 0.0, 'neutral': 0.0, 'negative': 0.0}
            five = len(r) == 5
            for x in r:
                lab = x['label']
                if five:
                    idx = int(lab.split('_')[-1]) if lab.lower().startswith('label_') else None
                    l = lab.lower()
                    k = 'negative' if 'neg' in l else ('positive' if 'pos' in l else 'neutral')
                else:
                    k = to3(lab)
                if k:
                    d[k] += x['score']
            out3.append(d)
        return out3

    def decide(d, margin, binary):
        if binary:
            if d['positive'] - d['negative'] > margin:
                return 'positive'
            if d['negative'] - d['positive'] > margin:
                return 'negative'
            return 'neutral'
        return max(d, key=d.get)

    binary = len(labels) == 2
    margin = 0.0
    if binary and train:
        P = probs3([r['message'] for r in train]); G = [r['sentiment'] for r in train]
        best = max((f1_macro([decide(d, m, True) for d in P], G), m) for m in (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95))
        margin = best[1]
    res = {'labels': labels, 'margin': margin}
    for t in TESTS:
        T = rows(t)
        P = probs3([r['message'] for r in T])
        pr = [decide(d, margin, binary) for d in P]
        g = [r['sentiment'] for r in T]
        res[t] = {'acc': round(float(np.mean([a == b for a, b in zip(pr, g)])), 4), 'macro_f1': round(f1_macro(pr, g), 4), 'n': len(T)}
    out[name] = res
    print('  ', json.dumps({k: v for k, v in res.items() if k not in ('labels',)}), flush=True)
json.dump(out, open('/root/work/zeroshot_sentiment.json', 'w', encoding='utf-8'), ensure_ascii=False)
