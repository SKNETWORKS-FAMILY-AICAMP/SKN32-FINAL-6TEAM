# 임베딩 모델 한 개를 같은 규정 질문 180 · 정책 조각 130 에 붙여 유사도 행렬을 만든다.
#  변형 E(문서 제목 + 절 제목 + 고객용 문장)로만 임베딩한다 — 운영 색인 변형과 같은 조건으로 비교하려고 고정했다.
#  지표: 답 있음 100문항의 정답 줄 @1·@3·@5, 답 있음 1위 점수 평균, 답 없음(코퍼스에 없음·주제 밖 60) 1위 점수 평균,
#        운영 문턱(min_policy_score 0.55) 기준 답 있음 통과율 · 답 없음 차단율.
#  주의: 질문은 고객용 문장을 보고 만들었으므로 낱말이 겹쳐 낙관적이다. 모델 사이 비교용이지 운영 성능 주장이 아니다.
# 사용: python embed_compare_20261012.py --model <HF 저장소 id 또는 로컬 폴더> --tag <이름> [--query-prefix "..."] [--doc-prefix "..."] [--device cuda|cpu] [--trust-remote-code]
import argparse
import json
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAG = os.path.dirname(HERE)
CH = json.load(open(os.path.join(RAG, 'fixtures', 'policy_chunks.json'), encoding='utf-8'))
QS = json.load(open(os.path.join(RAG, 'fixtures', 'rag_questions.json'), encoding='utf-8'))['questions']
THRESHOLD = 0.55


def doc_text(c):
    return f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--query-prefix', default='')
    ap.add_argument('--doc-prefix', default='')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--trust-remote-code', action='store_true')
    ap.add_argument('--out-dir', default=os.path.join(HERE, 'embed_compare'))
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    model = SentenceTransformer(args.model, device=args.device, trust_remote_code=args.trust_remote_code)
    load_s = time.time() - t0

    qv = model.encode([args.query_prefix + q['q'] for q in QS], normalize_embeddings=True, batch_size=16)
    dv = model.encode([args.doc_prefix + doc_text(c) for c in CH], normalize_embeddings=True, batch_size=16)
    sims = np.asarray(qv) @ np.asarray(dv).T  # 질문 180 × 조각 130

    line_mask = np.array([bool(c['line']) for c in CH])
    sources = [c['source'] for c in CH]
    ans = [i for i, q in enumerate(QS) if q['type'] == 'answerable']
    neg = [i for i, q in enumerate(QS) if q['type'] in ('uncovered', 'offtopic')]
    hit = {1: 0, 3: 0, 5: 0}
    for qi in ans:
        row = np.where(line_mask, sims[qi], -9)
        order = [sources[j] for j in np.argsort(-row)]
        for k in hit:
            hit[k] += bool(set(order[:k]) & set(QS[qi]['gold']))
    top_ans = [float(np.max(np.where(line_mask, sims[i], -9))) for i in ans]
    top_neg = [float(np.max(np.where(line_mask, sims[i], -9))) for i in neg]
    metrics = dict(
        model=args.model, tag=args.tag, dim=int(np.asarray(dv).shape[1]), load_seconds=round(load_s, 1),
        answerable=len(ans), hit_at_1=hit[1], hit_at_3=hit[3], hit_at_5=hit[5],
        top1_answerable_mean=round(float(np.mean(top_ans)), 4), top1_unanswerable_mean=round(float(np.mean(top_neg)), 4),
        pass_rate_answerable=round(float(np.mean([s >= THRESHOLD for s in top_ans])), 4),
        block_rate_unanswerable=round(float(np.mean([s < THRESHOLD for s in top_neg])), 4),
        threshold=THRESHOLD,
        query_prefix=args.query_prefix, doc_prefix=args.doc_prefix, variant='E_문서제목+절제목+고객용문장',
    )
    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, f'{args.tag}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(metrics=metrics, sources=sources, sims=np.round(sims, 6).tolist()), f, ensure_ascii=False)
    print(json.dumps(metrics, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
