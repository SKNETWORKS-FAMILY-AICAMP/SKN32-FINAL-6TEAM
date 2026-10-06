# Codex(gpt-6-luna · gpt-6-sol)를 규정 검색의 ① 재순위기(상위 20 후보에서 직접 답하는 줄을 순서대로 고름) ② 판정기(상위 5 후보 각각 「이 줄이 질문에 직접 답하나」 예/아니오)로 질문마다 한 번씩 부른다.
#  입력은 gemma4:12b 재순위(V7c)와 같은 1단계 후보(ce_input.json — 색인 E + 예상 질문) · 같은 지시문(rerank_lib.SYSTEM). 세트: B(160) · H(보류 140).
#  ★B 는 Codex(gpt-6-sol)가 쓴 질문이라 Codex 모델에 출제자 편향이 있다. H 는 Claude 작업자가 썼다 — H 를 주 비교로 읽는다.
#  ★H 는 이미 사전 등록 변형들을 한 번씩 쟀다. 이 실행은 새 변형(Codex 재순위기 · 판정기)이고 설정을 H 결과로 고르지 않는다(지시문 · 후보 수 고정).
# 사용: python codex_rerank_run.py <모델> <rerank|judge> [동시 수=3]   → ../results/rag_improve/codex_<역할>_<모델>.json (이어 돌리기 가능)
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'eval_kit'))
from codex_percall import call  # noqa: E402
from rerank_lib import SYSTEM  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
model, role = sys.argv[1], sys.argv[2]
par = int(sys.argv[3]) if len(sys.argv) > 3 else 3
OUT = os.path.abspath(os.path.join(HERE, '..', 'results', 'rag_improve'))
D = json.load(open(os.path.join(OUT, 'ce_input.json'), encoding='utf-8'))
text = {c['i']: c['text'] for c in D['chunks']}
dst = os.path.join(OUT, f'codex_{role}_{model.replace("/", "-")}.json')
res = json.load(open(dst, encoding='utf-8')) if os.path.exists(dst) else {}
NC = 20 if role == 'rerank' else 5
JUDGE = ('당신은 여행 서비스의 규정 안내 검수 담당입니다. 고객 질문과 후보 안내 문장들이 주어집니다. 각 후보는 서비스가 고객에게 그대로 보여 줄 안내 문장입니다. '
         '후보마다 「이 문장이 고객 질문에 직접 답이 되는가」를 예(true)/아니오(false)로 판정합니다. 관련 주제여도 질문이 묻는 구체 내용에 답하지 않으면 false 입니다. '
         '출력은 JSON: {"answers":[true/false, ...]} — 후보 순서 그대로 후보 수만큼.')
SCH_R = {'type': 'object', 'properties': {'ranking': {'type': 'array', 'items': {'type': 'integer'}}}}
SCH_J = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'boolean'}}}}


def one(job):
    sname, k, r = job
    cand = r['cand'][:NC]
    lines = '\n'.join(f'{n + 1}. {text[c]}' for n, c in enumerate(cand))
    prompt = f"{SYSTEM if role == 'rerank' else JUDGE}\n\n고객 질문: {r['q']}\n\n후보 안내 문장:\n{lines}\n\nJSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라."
    val, sec, err = call(model, prompt, SCH_R if role == 'rerank' else SCH_J)
    if val is None:
        return sname, k, {'error': err, 'sec': round(sec, 2)}
    if role == 'rerank':
        rk = [cand[int(n) - 1] for n in val.get('ranking', []) if isinstance(n, int) and 1 <= n <= len(cand)]
    else:
        ans = val.get('answers', [])
        rk = [c for c, a in zip(cand, ans) if a is True]
    return sname, k, {'picks': rk, 'sec': round(sec, 2)}


jobs = []
for sname in ('B', 'H'):
    got = res.setdefault(sname, {})
    for k, r in enumerate(D['sets'][sname]):
        if str(k) not in got or 'error' in got[str(k)]:
            jobs.append((sname, k, r))
print(model, role, '남은', len(jobs), flush=True)
t0 = time.time()
with ThreadPoolExecutor(par) as ex:
    for n, (sname, k, v) in enumerate(ex.map(one, jobs)):
        res[sname][str(k)] = v
        if (n + 1) % 30 == 0:
            json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
            print(n + 1, '/', len(jobs), round(time.time() - t0), '초', flush=True)
json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
print('끝', model, role, '오류', sum(1 for s in res.values() for v in s.values() if 'error' in v), round(time.time() - t0), '초')
