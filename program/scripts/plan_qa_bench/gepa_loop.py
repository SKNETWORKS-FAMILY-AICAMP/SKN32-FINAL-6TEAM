# GEPA식 프롬프트 최적화 (학습 없이 작은 모델을 끌어올리기) — 9월 논문 2607.24801 · ICLR 2026 GEPA(2507.19457) 의 방식을 우리 규모로 옮긴 것.
#  1) 서버에서 작은 모델(E4B/E2B)이 현재 프롬프트로 「최적화용(old_train)」 문제를 푼다 → 틀린 문제를 모은다.
#  2) 틀린 문제와 현재 프롬프트를 Codex(gpt-6-sol)에 주고 프롬프트 개정안을 받는다(정답 항목 번호나 특정 장소를 프롬프트에 넣지 말라고 지시).
#  3) 개정안을 old_train·old_val 에서 재고, old_val 이 좋아지면 채택. 반복.
#  4) 마지막에 최선 프롬프트를 사람이 쓴 heavy 판정·mix4 로 한 번 잰다(최적화에 쓰지 않은 세트).
# 사용: python gepa_loop.py <모델> <반복=6> <작업폴더>
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL, N, WORK = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(WORK, exist_ok=True)
SSH = 'acopilot-gpu'
INIT = ("오늘은 {today} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {q}\n\n"
        "이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
REQUIRED = ['{today}', '{plan}', '{hist}', '{q}']


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', shell=isinstance(cmd, str))


def evaluate(template, which, tag):
    f = os.path.join(WORK, f'tpl_{tag}.json')
    json.dump({'template': template}, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
    run(['scp', '-q', f, f'{SSH}:/workspace/heavy/tpl_{tag}.json'])
    r = run(['ssh', SSH, f'cd /workspace/heavy; python3 eval_prompt.py {MODEL} tpl_{tag}.json {which}'])
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        print('평가 실패', r.stdout[-300:], r.stderr[-300:])
        return None


SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['analysis', 'template'],
          'properties': {'analysis': {'type': 'string'}, 'template': {'type': 'string'}}}
json.dump(SCHEMA, open(os.path.join(WORK, 'schema.json'), 'w'))


def reflect(template, res, it):
    fails = '\n'.join(f"- 질문: 「{x['q']}」 / 정답 항목: {x['gold']} / 모델 답: {x['pred']} / 유형: {x['type']}" for x in res['fails'])
    prompt = f"""너는 작은 언어 모델(Gemma 4 E4B 급)이 읽을 프롬프트를 고치는 사람이다. 파일을 만들거나 고치지 말고 명령도 실행하지 마라. 한 번에 지정한 JSON 으로 답하라.

과제: 고객이 여행 일정(항목 번호별 한 줄)에 대해 보낸 한국어 짧은 채팅이 가리키는 일정 항목 번호 하나를 고르게 한다. 일정에 없는 곳·일반 정보를 묻거나 특정할 수 없으면 null. 모델은 JSON {{"item": 번호 또는 null}} 만 낸다.
현재 프롬프트 틀(자리표 {{today}} {{plan}} {{hist}} {{q}} 는 반드시 그대로 유지):
<<<
{template}
>>>
이 프롬프트로 최적화용 문제 {res['n']}개 중 {res['ok']}개를 맞혔다(엉뚱한 답 {res['bad']} · 못 찾음 {res['miss']}). 틀린 문제 표본:
{fails}

요청: 틀린 문제들의 **공통 원인**을 짚고(analysis), 그것을 고치는 개정 프롬프트 틀(template)을 써라.
규칙: ① 정답 번호·특정 장소 이름·위 질문 문장을 프롬프트에 그대로 넣지 마라(일반 지침과 형식·판단 순서만) ② 자리표 4개를 그대로 유지 ③ 예시(few-shot)는 넣어도 되지만 일정과 무관한 가상의 짧은 예로 2~4개까지 ④ 프롬프트는 한국어, 700자 이내 ⑤ 「확실하지 않으면 null」처럼 놓침을 늘리는 지시와 「무조건 하나 고르라」처럼 엉뚱한 답을 늘리는 지시 사이의 균형을 잡아라.
"""
    pf = os.path.join(WORK, f'reflect_{it}.md')
    open(pf, 'w', encoding='utf-8').write(prompt)
    of = os.path.join(WORK, f'reflect_{it}.json')
    if os.path.exists(of):
        os.remove(of)
    with open(pf, 'rb') as fin:
        subprocess.run([shutil.which('codex'), 'exec', '--skip-git-repo-check', '-s', 'read-only', '--ephemeral', '-C', WORK,
                        '--output-schema', os.path.join(WORK, 'schema.json'), '-o', of, '-m', 'gpt-6-sol', '-'], stdin=fin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(of, encoding='utf-8'))
    return d['template'], d['analysis']


best = INIT
tr = evaluate(best, 'old_train', 'cur')
va = evaluate(best, 'old_val', 'curv')
print(f'[0] 초기: train {tr["ok"]}/{tr["n"]} · val {va["ok"]}/{va["n"]} · {tr["sec"]:.0f}초', flush=True)
history = [{'it': 0, 'train': tr['ok'], 'val': va['ok'], 'template': best, 'accepted': True}]
best_val = va['ok']
for it in range(1, N + 1):
    new, analysis = reflect(best, tr, it)
    if not all(k in new for k in REQUIRED):
        print(f'[{it}] 자리표 누락 — 개정안 버림', flush=True)
        continue
    ntr = evaluate(new, 'old_train', f'c{it}')
    nva = evaluate(new, 'old_val', f'c{it}v')
    if not ntr or not nva:
        continue
    acc = nva['ok'] > best_val or (nva['ok'] == best_val and ntr['ok'] > tr['ok'])
    print(f'[{it}] train {ntr["ok"]}/{ntr["n"]} · val {nva["ok"]}/{nva["n"]} (엉뚱 {nva["bad"]} · 못 찾음 {nva["miss"]}) → {"채택" if acc else "버림"} | {analysis[:120]}', flush=True)
    history.append({'it': it, 'train': ntr['ok'], 'val': nva['ok'], 'template': new, 'accepted': acc, 'analysis': analysis})
    if acc:
        best, tr, best_val = new, ntr, nva['ok']
json.dump({'model': MODEL, 'best': best, 'history': history}, open(os.path.join(WORK, f'gepa_{MODEL.replace(":", "-")}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for which in ('heavy', 'mix4'):
    r = evaluate(best, which, 'final_' + which)
    print(f'최종 {which}: {r["ok"]}/{r["n"]} (엉뚱 {r["bad"]} · 못 찾음 {r["miss"]})', flush=True)
r0 = None
for which in ('heavy', 'mix4'):
    r0 = evaluate(INIT, which, 'init_' + which)
    print(f'초기 프롬프트 {which}: {r0["ok"]}/{r0["n"]} (엉뚱 {r0["bad"]} · 못 찾음 {r0["miss"]})', flush=True)
