# 일정 항목 짚기 학습 자료에 「일정과 무관한 잡담 · 구어체」를 정답 「없음」으로 더한다(2026-10-07 — D 시험에서 가르친 E4B 의 잡담 오지목이 시드마다 5.1 · 21.5 · 9.4% 로 갈린 원인이 「학습 자료에 잡담이 한 건도 없음」이라고 보고).
#  원본 train.jsonl(서버 B /root/work/train.jsonl, 1,313행 · 「없음」 236행)의 일정 프롬프트에서 고객 질문만 잡담 문장으로 바꾸고 정답을 {"item": null} 로 둔다.
#  ★시험과 안 겹치게: D 시험의 잡담 1,300문장은 AI Hub 일상 대화의 앞 20만 줄 필터 결과 앞쪽 1,000개(세트당 200) + KoCulture 앞 300개(세트당 60)다(build_mixed_testset.py).
#   → 학습 쪽은 AI Hub 는 40만 줄 이후에서만, KoCulture 는 300번째 이후에서만 뽑고, D 시험 잡담과 글자 3-gram 자카드 0.6 이상 겹치는 문장도 뺀다. 겹침 수는 train_oos_report.json 에 남긴다.
#  난이도: 실패가 몰린 「음식 · 장소 · 활동을 말하는 잡담」(디저트 카페, 고기 구워 먹기, 꽃 보고 등반 …)을 일부 더 뽑는다(키워드 포함 문장) — 시험 문장이 아니라 같은 풀의 다른 문장이다.
# 사용: python build_train_oos.py <원본 train.jsonl> <출력 train_oos.jsonl> [N_RANDOM=200 N_KEYWORD=100 N_KOCUL=100 SEED=20261007]
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TRAVEL = os.path.join(ROOT, 'datasets', 'travel')
sys.stdout.reconfigure(encoding='utf-8')
src, dst = sys.argv[1], sys.argv[2]
N_RANDOM, N_KEYWORD, N_KOCUL = (int(os.environ.get(k, v)) for k, v in (('N_RANDOM', 200), ('N_KEYWORD', 100), ('N_KOCUL', 100)))
SEED = int(os.environ.get('SEED', '20261007'))
rnd = random.Random(SEED)
KEY = re.compile(r'(카페|커피|디저트|점심|저녁|아침|밥|고기|맛집|먹|술|맥주|치킨|피자|빵|놀러|구경|공원|산책|등산|등반|꽃|바다|호수|시장|박물관|영화|호텔|숙소|지하철|버스|택시|기차|공항)')


def trigrams(t):
    t = re.sub(r'\s+', '', t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def jacc(a, b):
    return len(a & b) / max(1, len(a | b))


# 시험의 잡담 문장(겹침 검사용)
test_chat = []
for n in (8, 9, 10, 11, 12):
    d = json.load(open(os.path.join(ROOT, 'datasets', 'core', 'pointing', 'testset', 'questions_plus_chitchat_v1', 'source', f'mixed{n}.json'), encoding='utf-8'))
    for q in d['sets'][f'mixed{n}']['qs']:
        if q['type'] == 'chitchat':
            test_chat.append(q['q'].strip())
test_set = set(test_chat)
test_tri = [trigrams(t) for t in test_chat]
assert len(test_chat) == 1300, len(test_chat)


def overlaps(t):
    if t in test_set:
        return True
    tg = trigrams(t)
    return any(jacc(tg, o) >= 0.6 for o in test_tri)


# AI Hub 일상 대화: 40만 줄 이후에서만
aihub = []
with open(os.path.join(TRAVEL, '020.주제별 텍스트 일상 대화 데이터', 'processed', 'chat_utterances.jsonl'), encoding='utf-8') as f:
    for k, line in enumerate(f):
        if k < 400000:
            continue
        if k >= 700000:
            break
        x = json.loads(line)
        t = x['t'].strip()
        if 6 <= len(t) <= 80 and '여행' not in (x.get('subject') or '') and not re.fullmatch(r'[ㅋㅎㅠㅜ\s.?!~]+', t):
            aihub.append(t)
kocul = []
for line in open(os.path.join(TRAVEL, 'koculture_dialogues', 'processed', 'utterances.jsonl'), encoding='utf-8'):
    t = json.loads(line)['question'].strip()
    if 6 <= len(t) <= 80:
        kocul.append(t)
kocul = kocul[300:]                      # 시험은 앞 300개(세트당 60 × 5)
rep = {'AI Hub 후보(40만 줄 이후, 필터 뒤)': len(aihub), 'KoCulture 후보(300번째 이후)': len(kocul)}


def pick(pool, n, need=None):
    pool = list(dict.fromkeys(pool))
    rnd.shuffle(pool)
    out, skipped = [], 0
    for t in pool:
        if need and not need.search(t):
            continue
        if overlaps(t):
            skipped += 1
            continue
        out.append(t)
        if len(out) == n:
            break
    return out, skipped


rand_s, sk1 = pick(aihub, N_RANDOM)
key_s, sk2 = pick([t for t in aihub if t not in set(rand_s)], N_KEYWORD, KEY)
koc_s, sk3 = pick(kocul, N_KOCUL)
rep['시험과 겹쳐 뺀 수'] = {'AI Hub 무작위': sk1, 'AI Hub 키워드': sk2, 'KoCulture': sk3}
negs = [('chitchat_neg_random', t) for t in rand_s] + [('chitchat_neg_keyword', t) for t in key_s] + [('chitchat_neg_kocul', t) for t in koc_s]
rep['더한 부정 예'] = {'무작위': len(rand_s), '키워드': len(key_s), 'KoCulture': len(koc_s), '합계': len(negs)}
# 최종 확인: 학습 부정 예와 시험 잡담의 정확 일치 · 높은 겹침 0 이어야 한다
assert not any(t in test_set for _, t in negs)
rep['최대 자카드(학습 부정 예 × 시험 잡담)'] = round(max(jacc(trigrams(t), o) for _, t in negs for o in test_tri), 3)

rows = [json.loads(l) for l in open(src, encoding='utf-8')]
base = [r for r in rows if r['type'] != 'compound_intent']
out = list(rows)
for k, (typ, t) in enumerate(negs):
    b = rnd.choice(base)
    head, rest = b['prompt'].split('고객 질문: ', 1)
    tail = rest.split('\n\n', 1)[1]
    prompt = head + '고객 질문: ' + t + '\n\n' + tail
    out.append({'persona': b['persona'], 'idx': -1 - k, 'type': typ, 'gold': None, 'prompt': prompt, 'completion': '{"item": null}'})
rnd.shuffle(out)
with open(dst, 'w', encoding='utf-8') as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
nul = sum(1 for r in out if r['completion'].strip() == '{"item": null}')
rep.update({'원본 행': len(rows), '출력 행': len(out), '「없음」 행': nul, '「없음」 비율': round(nul / len(out), 3), '씨앗': SEED})
json.dump(rep, open(os.path.splitext(dst)[0] + '_report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(rep, ensure_ascii=False, indent=1))
