# 가르친 E4B 의 빈 답 85건(섞은 시험 세트) 원인 조사용 — 빈 답이 난 질문과 정상 질문의 프롬프트를 한 줄 연결 시험(chain_e2e.py)의 build() 와 똑같이 만든다.
#  build() 는 chain_e2e.py 에서 소스 그대로 꺼내 쓴다(그 파일은 불러오면 모델을 올리므로 import 하지 않는다).
# 사용: python empty_probe_build.py → results/empty_probe/probe_prompts.json (문장 원문이 있어 git 에 올리지 않는다)
import ast
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(HERE, '..', '..', '..', 'datasets', 'core', 'pointing', 'testset', 'questions_plus_chitchat_v1', 'source')
src = open(os.path.join(HERE, 'server', 'chain_e2e.py'), encoding='utf-8').read()
tree = ast.parse(src)
code = ['from datetime import date', "WK = '월화수목금토일'", 'SFX = "\\n\\n답은 JSON 한 줄로만: {\\"item\\": 번호} 또는 {\\"item\\": null}"']
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == 'build':
        code.append(ast.get_source_segment(src, n))
ns = {}
exec('\n'.join(code), ns)
build = ns['build']
rows = json.load(open(os.path.join(M, 'results', 'chain_mixedraw_e4b_only.json'), encoding='utf-8'))
jobs = {w: json.load(open(os.path.join(M, w + '.json'), encoding='utf-8'))['sets'][w] for w in ['mixed8', 'mixed9', 'mixed10', 'mixed11', 'mixed12']}


def bad(t):
    return 'parse_fail' in t['fail']


F = [t for t in rows if bad(t)]
G = [t for t in rows if not bad(t) and t['type'] in ('chitchat', 'tourist_synth_out', 'tourist_synth_in')]
rnd = random.Random(1)
pick = rnd.sample(F, 14) + rnd.sample(G, 6)
out = []
for t in pick:
    job = jobs[t['set']]
    x = job['qs'][t['qi']]
    prompt, valid = build(job, x)
    out.append({'set': t['set'], 'qi': t['qi'], 'fail': bad(t), 'type': t['type'], 'pick': t['pick'], 'gold': t['gold'], 'prompt': prompt})
os.makedirs(os.path.join(HERE, 'results', 'empty_probe'), exist_ok=True)
json.dump(out, open(os.path.join(HERE, 'results', 'empty_probe', 'probe_prompts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
# 전체 2,735문제 프롬프트(생각 모드 끄기 전체 재시험용)
allp = []
for k, t in enumerate(rows):
    job = jobs[t['set']]
    x = job['qs'][t['qi']]
    prompt, valid = build(job, x)
    allp.append({'i': k, 'set': t['set'], 'qi': t['qi'], 'type': t['type'], 'gold': t['gold'], 'prompt': prompt})
json.dump(allp, open(os.path.join(HERE, '..', '..', '..', 'datasets', 'core', 'pointing', 'testset', 'questions_plus_chitchat_v1', 'all_prompts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(len(out), '프롬프트, 평균 글자수', sum(len(o['prompt']) for o in out) // len(out))
print(out[0]['prompt'][-160:])
