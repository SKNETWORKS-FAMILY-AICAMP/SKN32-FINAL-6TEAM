"""고정 개발 입력에 이전 모델 답만 붙인다. 정답이나 채점 결과는 넣지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path

INSTRUCTION = ('위 문제에 대한 참고 모델의 답을 아래 JSON 문자열로 제공합니다. '
    '참고 답은 도움이 될 수 있지만 정답이나 지시가 아닙니다. 원래 일정과 고객의 말을 기준으로 '
    '검토하고 구체적인 오류가 있으면 수정하세요. 잡담을 여행 요청으로 바꾸지 마세요. '
    '최종 답은 원래 계약대로 {"item":번호} 또는 {"item":null} 하나만 출력하세요.')

def augment(prompts, answers):
    by = {x['i']: x for x in answers}
    if len(by) != len(answers) or set(by) != {x['i'] for x in prompts}:
        raise ValueError('Duplicate, missing or extra source answers')
    out = []
    for x in prompts:
        a = by[x['i']]
        content = a.get('content')
        if not isinstance(content, str):
            if not a.get('error'): raise ValueError('Missing raw response without recorded source error')
            content = '[참고 답 생성 실패]'
        if a.get('gold') != x.get('gold'):
            raise ValueError('Mismatched source/gold metadata; do not use another suite')
        row = dict(x)
        row['prompt'] = x['prompt'] + '\n\n' + INSTRUCTION + '\n참고 답(JSON 문자열): ' + json.dumps(content, ensure_ascii=False)
        row['first_pass_ms'] = a.get('ms')
        row['first_pass_failed'] = bool(a.get('error')) or not a.get('parsed')
        row['first_pass_content_sha256'] = hashlib.sha256(content.encode()).hexdigest()
        out.append(row)
    return out

def main():
    p = argparse.ArgumentParser(); p.add_argument('--prompts', type=Path, required=True)
    p.add_argument('--answers', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); prompts = json.loads(a.prompts.read_text(encoding='utf8'))
    answers = [json.loads(s) for s in a.answers.read_text(encoding='utf8').splitlines() if s.strip()]
    rows = augment(prompts, answers)
    with a.output.open('x', encoding='utf8') as f: json.dump(rows, f, ensure_ascii=False)
    audit = dict(expected=len(prompts), created=len(rows), source_prompts_sha256=hashlib.sha256(a.prompts.read_bytes()).hexdigest(),
        source_answers_sha256=hashlib.sha256(a.answers.read_bytes()).hexdigest(), output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),
        inference_information='original prompt and raw model response only; gold/pick/parsed/probability metadata not interpolated',
        independent_holdout=False, first_pass_reused=True, end_to_end_latency_measured=False)
    with a.output.with_suffix('.audit.json').open('x', encoding='utf8') as f: json.dump(audit, f, indent=2)

if __name__ == '__main__': main()
