# D3 — 라이선스 걱정 없는 보류 세트: Claude 가 쓴 합성 잡담 240문장(A 무관한 일상 120 · B 음식·장소·활동을 말하는 잡담 120, 정답 = 없음) + D 시험의 정답 있는 질문 120개.
#  쓰임: 학습 없는 FrogNano · 가르친 E4B 시드들 · Codex 솔의 오지목을 같은 문장으로 비교한다(AI Hub 문장을 외부 서비스에 보내지 않으려고 따로 만들었다).
#  일정 프롬프트는 D 시험의 일정에서 무작위로 골라 고객 질문만 바꾼다(형식 · 끝 지시 그대로).
# 사용: python build_d3.py <all_prompts.json> <d3_chat_synth.json> <출력 all_prompts_d3.json>
import json
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
allp, synth, dst = sys.argv[1], sys.argv[2], sys.argv[3]
rnd = random.Random(20261009)
P = json.load(open(allp, encoding='utf-8'))
S = json.load(open(synth, encoding='utf-8'))
assert len(S) == 240, len(S)
base = [p for p in P if p['type'] not in ('chitchat', 'compound_intent') and p['gold'] is None or p['type'] in ('tourist_synth_out',)]
base = [p for p in P if p['type'] not in ('chitchat', 'compound_intent')]
items = []
for n, x in enumerate(S):
    b = rnd.choice(base)
    head, rest = b['prompt'].split('고객 질문: ', 1)
    tail = rest.split('\n\n', 1)[1]
    items.append({'i': 800000 + n, 'set': 'd3', 'qi': n, 'type': 'synth_chat_' + x['group'], 'gold': None, 'prompt': head + '고객 질문: ' + x['q'].strip() + '\n\n' + tail})
ans = [p for p in P if p['gold'] is not None and p['type'] not in ('compound_intent',)]
for k, p in enumerate(rnd.sample(ans, 120)):
    items.append({'i': 810000 + k, 'set': 'd3', 'qi': 240 + k, 'type': p['type'], 'gold': p['gold'], 'prompt': p['prompt'], 'orig_i': p['i']})
json.dump(items, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
print(len(items), '문항(잡담 240 + 정답 있는 120)')
