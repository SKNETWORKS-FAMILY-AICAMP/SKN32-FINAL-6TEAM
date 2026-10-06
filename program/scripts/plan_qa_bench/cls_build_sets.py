# 분류 자료 조립 — 작성자 라벨과 **다른 쪽 모델이 정답 없이 붙인 라벨**(교차 라벨)이 어긋나는 칸은 마스크(mask_<머리>)해서 학습·평가에서 뺀다.
#  학습 자료 CL = Claude 가 쓰고 Codex 가 교차 라벨 · 시험 자료 CX = Codex 가 쓰고 Claude 가 교차 라벨(출제자가 학습 자료와 다름, §84).
#  일치율(교차 라벨러 ↔ 작성자)은 「사람 라벨러 둘이 있었다면 나왔을 상한」의 대용 — 이 수가 소형 모델 점수의 현실적 천장이다.
# 사용: python cls_build_sets.py <cls 폴더> <출력 폴더>   → train.jsonl · test_cx.jsonl · test_g96.jsonl(복사) · agreement.json
import collections, glob, json, os, shutil, sys

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
HEADS = ['intent', 'case_type', 'sentiment', 'severity']


def load(pattern):
    rows = []
    for f in sorted(glob.glob(os.path.join(SRC, pattern))):
        rows += [json.loads(l) for l in open(f, encoding='utf-8')]
    return rows


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


report = {}
for tag, author_pat, cross_pat, out_name in (('CL(학습: Claude 작성 · Codex 교차)', 'cl_[0-9].jsonl', 'cl_codex_labels.jsonl', 'train.jsonl'),
                                              ('CX(시험: Codex 작성 · Claude 교차)', 'cx_[0-9].jsonl', 'cx_claude_labels_[0-9].jsonl', 'test_cx.jsonl')):
    author = {r['id']: r for r in load(author_pat)}
    cross = {r['id']: r for r in load(cross_pat)}
    ids = [i for i in author if i in cross]
    stat = {'n_author': len(author), 'n_crossed': len(ids), 'agree': {}, 'kappa': {}, 'all4': 0}
    rows = []
    for i in ids:
        r = dict(author[i])
        ok_all = True
        for h in HEADS:
            same = author[i][h] == cross[i][h]
            r['mask_' + h] = (not same)
            r['cross_' + h] = cross[i][h]
            ok_all &= same
        stat['all4'] += ok_all
        rows.append(r)
    for h in HEADS:
        a = [author[i][h] for i in ids]
        b = [cross[i][h] for i in ids]
        stat['agree'][h] = round(sum(x == y for x, y in zip(a, b)) / len(ids), 4)
        stat['kappa'][h] = round(kappa(a, b), 4)
    stat['all4'] = round(stat['all4'] / len(ids), 4)
    stat['intent_confusion_top'] = collections.Counter((author[i]['intent'], cross[i]['intent']) for i in ids if author[i]['intent'] != cross[i]['intent']).most_common(8)
    report[tag] = stat
    with open(os.path.join(OUT, out_name), 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
shutil.copy(os.path.join(SRC, 'test_g96.jsonl'), os.path.join(OUT, 'test_g96.jsonl'))
json.dump(report, open(os.path.join(OUT, 'agreement.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for tag, s in report.items():
    print(tag, '문제', s['n_crossed'], '| 일치율', s['agree'], '| 네 칸 모두 일치', s['all4'])
    print('   kappa', s['kappa'])
    print('   의도 어긋남 상위', s['intent_confusion_top'][:5])
