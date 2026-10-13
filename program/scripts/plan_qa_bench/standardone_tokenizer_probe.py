"""고정 수정판의 CPU 토크나이저만 검사한다. 가중치·GPU를 사용하지 않는다."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
root = HERE / 'results/standardone_preflight_20261008'
server = root / '8B_ac495d1c221297f0ae951941eff27bcf58b5ce52/server'
sys.path.insert(0, str(server))
from jev_adapter.labels import select_labels
from jev_adapter.native_tokenizer import NativeTokenizer
from jev_adapter.protocol import SystemOneRequest, plan_question, build_prompt

rows = [json.loads(l) for l in (root/'travel_choice_h/requests_h.jsonl').read_text(encoding='utf-8').splitlines()]
sample = max(rows, key=lambda r: len(r['request']['questions']['item']['criteria']))
report = []
for folder in sorted(root.glob('*_*')):
    if not (folder/'preflight.json').exists():
        continue
    preflight = json.loads((folder/'preflight.json').read_text(encoding='utf-8'))
    result = dict(repo_id=preflight['repo_id'], revision=preflight['revision_sha'],
                  weights_downloaded=False, gpu_used=False)
    try:
        native = NativeTokenizer.from_pretrained(preflight['repo_id'], preflight['revision_sha'])
        labels, token_ids = select_labels(native.tokenizer, 'upper')
        validated = SystemOneRequest.model_validate(sample['request'])
        plan = plan_question(validated.questions['item'])
        count = len(plan.option_names)
        prompt = build_prompt(validated.state, plan, labels[:count], wording='served')
        ids = native.prepare(prompt, tuple(labels[:count]), tuple(token_ids[:count]), None)
        result.update(status='passed', label_count=len(labels), tested_options=count,
                      prompt_tokens=len(ids), label_boundary_verified=True,
                      labels=labels[:count], token_ids=token_ids[:count])
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error),
                      label_boundary_verified=False)
    report.append(result)
target = root/'tokenizer_probe.json'
with target.open('x',encoding='utf-8') as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=True))
