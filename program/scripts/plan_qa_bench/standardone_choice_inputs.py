"""여행 항목 선택 입력을 공식 선택지 API 형식으로 옮긴다. 정답은 요청에 넣지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def to_request(prompt, model):
    question_marker = '\n\n고객 질문: '
    rules_marker = '\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라.'
    output_marker = '\n\n답은 JSON 한 줄로만:'
    if prompt.count(question_marker) != 1 or prompt.count(output_marker) != 1:
        raise ValueError('Known prompt boundaries required; preserve unknown formats')
    state, _, tail = prompt.partition(question_marker)
    question, marker, rules = tail.partition(rules_marker)
    if not marker:
        raise ValueError('Known item-selection rules required')
    rules = rules.split(output_marker, 1)[0]
    itinerary = state.split('\n\n앞 대화:', 1)[0]
    items = re.findall(r'^(\d+)\. (.+)$', itinerary, re.MULTILINE)
    if not items or len({number for number, _ in items}) != len(items):
        raise ValueError('Distinct itinerary item IDs required')
    if len(items) + 1 > 255:
        raise ValueError('Official choice limit exceeded')
    criteria = {number: text for number, text in items}
    criteria['null'] = '일정 항목을 가리키지 않거나 확실하지 않음'
    instructions = ('고객 질문: ' + question + '\n\n'
                    '이 질문이 가리키는 일정 항목 번호 하나를 선택하세요.' + rules)
    request = {'model': model, 'state': state,
               'questions': {'item': {'type': 'choice', 'instructions': instructions,
                                      'criteria': criteria}},
               'options': {'temperature': 1.65, 'permutations': 1,
                           'return_logprobs': True}}
    return request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--official-server', required=True)
    args = ap.parse_args()
    sys.path.insert(0, args.official_server)
    from jev_adapter.protocol import SystemOneRequest, build_prompt, plan_question
    from jev_adapter.labels import candidate_tiers
    source = Path(args.input)
    rows = json.loads(source.read_text(encoding='utf-8'))
    requests, references = [], []
    for row in rows:
        payload = to_request(row['prompt'], 'standard-one-3b')
        validated = SystemOneRequest.model_validate(payload)
        plan = plan_question(validated.questions['item'])
        labels = candidate_tiers('upper')[0][:len(plan.option_names)]
        rendered = build_prompt(validated.state, plan, labels, wording='served')
        if row['q'] not in validated.questions['item'].instructions:
            raise ValueError('Source question was not preserved')
        # gold is used only in this separate local reference, never in request.
        key = 'null' if row['gold'] is None else str(row['gold'])
        if key not in payload['questions']['item']['criteria']:
            raise ValueError('Reference option outside supplied itinerary')
        requests.append({'i': row['i'], 'request': payload})
        references.append({'i': row['i'], 'gold': row['gold'], 'type': row['type'],
                           'source_prompt_sha256': hashlib.sha256(row['prompt'].encode()).hexdigest(),
                           'rendered_prompt_sha256': hashlib.sha256(rendered.encode()).hexdigest(),
                           'options': len(plan.option_names)})
    if len({r['i'] for r in requests}) != len(requests):
        raise ValueError('Duplicate input IDs')
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, records in [('requests_h.jsonl', requests), ('reference_h.jsonl', references)]:
        with (output / name).open('x', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    manifest = dict(suite='H', prepared=len(requests), expected=len(rows),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    request_sha256=hashlib.sha256((output/'requests_h.jsonl').read_bytes()).hexdigest(),
                    gold_in_requests=False, input_contract='travel-item-choice-v1',
                    official_render_validation=True, wording='served', temperature=1.65,
                    rotations=1, tokenizer_label_boundaries_verified=False,
                    gpu_model_measurement=False,
                    limitation='Template/schema check only; actual tokenizer and GPU compatibility pending')
    with (output / 'prepared_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=True))


if __name__ == '__main__':
    main()
