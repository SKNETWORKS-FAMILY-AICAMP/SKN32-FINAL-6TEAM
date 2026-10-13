# 서버에서: 증류 파일럿 평가 — 같은 4비트 학생 모델을 「어댑터 끈 상태(무학습 기준선)」와 「LoRA 어댑터 켠 상태」로 같은 문제에 풀게 한다.
#  문제: 평가 세트 mix8~mix12(작업 폴더의 <세트>.json) 또는 val.jsonl. 질의문은 distill_assemble.py 의 prompt() 와 같다(규칙 문장 없음 + 형식 한 줄).
#  풀이: 탐욕 생성(최대 12토큰) → {"item": 번호|null} 을 정규식으로 읽는다. 읽지 못하면 null 로 센다(오류 수를 따로 남긴다).
# 사용: python3 qlora_eval.py <모델폴더> <어댑터폴더|-> <태그> <세트들,쉼표|val> [--base]   → eval_<태그>_<세트>.json  (--base: 어댑터 끈 기준선도 같이 푼다)
import json, os, re, sys, time
from datetime import date
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL, ADAPTER, TAG, SETS = sys.argv[1:5]
BASE = '--base' in sys.argv
LIMIT = int(os.environ.get('LIMIT', '0'))   # 스모크용: 세트마다 앞 N문제만
CONF = os.environ.get('CONF') == '1'        # 1 이면 문제마다 짚은 답의 확신도(답 토큰 확률의 곱)를 같이 저장 — 확신 낮은 문제만 큰 모델에 넘기는 위임 모의용
LAST_CONF = [None]
W = '월화수목금토일'
SFX = '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'
tok = AutoTokenizer.from_pretrained(MODEL)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, dtype=torch.bfloat16, device_map={'': 0})
if ADAPTER != '-':
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()


def build(job, x):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + '\n'.join(lab(i) for i in items) + f"\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null." + SFX), {i['id'] for i in items}


def solve(prompt, valid):
    p = tok.apply_chat_template([{'role': 'user', 'content': prompt}], add_generation_prompt=True, tokenize=False)
    ids = tok(p, add_special_tokens=False, return_tensors='pt').to('cuda')
    with torch.inference_mode():
        if CONF:
            gen_out = model.generate(**ids, max_new_tokens=12, do_sample=False, output_scores=True, return_dict_in_generate=True)
            out = gen_out.sequences
        else:
            out = model.generate(**ids, max_new_tokens=12, do_sample=False)
    s = tok.decode(out[0, ids['input_ids'].shape[1]:], skip_special_tokens=True)
    if CONF:
        import math
        lp = 0.0
        for step, tid in enumerate(out[0, ids['input_ids'].shape[1]:]):
            if step >= len(gen_out.scores):
                break
            lp += torch.log_softmax(gen_out.scores[step][0].float(), -1)[tid].item()
            if tok.decode([tid.item()]).strip().endswith('}'):
                break
        LAST_CONF[0] = math.exp(lp)
    m = re.search(r'"item"\s*:\s*(null|\d+)', s)
    if not m:
        return None, True, s
    v = None if m.group(1) == 'null' else int(m.group(1))
    return (v if v in valid else None), False, s


def run(name, qs_iter, mode):
    picks, errs, t0, shown, confs = [], 0, time.time(), 0, []
    for n, (prompt, valid) in enumerate(qs_iter):
        if LIMIT and n >= LIMIT:
            break
        if (n + 1) % 50 == 0:
            print(f'  {name} {mode} {n + 1}문제 · {(time.time() - t0) / (n + 1):.2f}s/q', flush=True)
        if mode == 'base':
            with model.disable_adapter():
                v, e, s = solve(prompt, valid)
        else:
            v, e, s = solve(prompt, valid)
        picks.append(v)
        confs.append(LAST_CONF[0])
        errs += e
        if e and shown < 3:
            print('  읽기 실패 예:', repr(s[:80]), flush=True)
            shown += 1
    sec = (time.time() - t0) / max(1, len(picks))
    print(f'{name} {mode} {len(picks)}문제 {sec:.2f}s/q 읽기실패 {errs}', flush=True)
    return {'picks': picks, '_sec_per_q': sec, '_errors': errs, **({'_confs': confs} if CONF else {})}


modes = (['base'] if BASE else []) + (['lora'] if ADAPTER != '-' else [])
for s in SETS.split(','):
    res = {}
    if s == 'val':
        rows = [json.loads(l) for l in open('val.jsonl', encoding='utf-8')]
        for mode in modes:
            res[f'{TAG}#{mode}'] = run(s, ((r['prompt'], set(range(1, 200))) for r in rows), mode)
        res['_gold'] = [r['gold'] for r in rows]
        res['_type'] = [r['type'] for r in rows]
    else:
        job = json.load(open(f'{s}.json', encoding='utf-8'))['sets'][s]
        for mode in modes:
            res[f'{TAG}#{mode}'] = run(s, (build(job, x) for x in job['qs']), mode)
    json.dump(res, open(f'eval_{TAG}_{s}.json', 'w'), ensure_ascii=False)
print('EVAL_DONE', TAG, flush=True)
