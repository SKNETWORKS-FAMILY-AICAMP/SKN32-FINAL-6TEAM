"""고정 여행 정보와 질문을 결정 모델의 원본 선택지 계약으로 옮긴다."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parents[2]
ROOT = HERE.parents[2]
OUT = ROOT/'datasets/core/pointing/evaluations/valen_native_eval_20261009'
SOURCES = dict(d=ROOT/'datasets/core/pointing/testset/questions_plus_chitchat_v1/all_prompts.json',
               d2=ROOT/'datasets/core/pointing/testset/chitchat_only_holdout_v1/all_prompts_d2.json',
               d3=ROOT/'datasets/core/pointing/testset/synthetic_chitchat_plus_questions_v1/all_prompts_d3.json',
               h=ROOT/'datasets/core/pointing/testset/confusing_trap_sentences_v1/h_set_test_30_20261015_agree.json',
               mx=ROOT/'datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1/mx_main_prompts.json')


def convert(row):
    # Only the general JSON formatting instruction is omitted. All supplied facts,
    # preceding dialogue and the common decision policy remain model input.
    base, policy, formatting = row['prompt'].rsplit('\n\n', 2)
    assert formatting == '답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'
    state, question = base.rsplit('\n\n고객 질문: ', 1)
    criteria = dict(re.findall(r'(?m)^(\d+)\. (.+)$', state))
    assert 1 <= len(criteria) < 255
    criteria['NONE'] = '이 질문이 기존 일정의 어떤 항목도 실제로 요청하지 않음. 일정에 없는 장소·일반 정보·잡담·범위 밖 문의 또는 확실하지 않은 경우.'
    request = dict(state=state+'\n\n'+policy, questions=dict(selection=dict(
        type='choice', instructions=question, criteria=criteria)))
    # Gold and experimental IDs only belong to the outer audit record.
    result = {k: v for k, v in row.items() if k != 'prompt'}
    result.update(request=request, source_prompt_sha256=hashlib.sha256(row['prompt'].encode()).hexdigest())
    assert result['request']['questions']['selection']['instructions'] == question
    return result


def main():
    OUT.mkdir(exist_ok=False)
    hashes = {}; data = {}
    for suite, source in SOURCES.items():
        original = json.loads(source.read_text(encoding='utf-8'))
        rows = [convert(x) for x in original]
        assert len(rows) == len({r['i'] for r in rows})
        path = OUT/(suite+'.json')
        with path.open('x', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        hashes[suite] = dict(source=str(source.relative_to(ROOT)),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            prompt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), expected=len(rows),
            max_choices=max(len(x['request']['questions']['selection']['criteria']) for x in rows))
        data[suite] = rows
    smoke=[]
    for group in [[r for r in data['d3'] if r['gold'] is not None],
                  [r for r in data['d3'] if r['gold'] is None],
                  [r for r in data['h'] if r['gold'] is None]]:
        smoke.extend(group[:4])
    for ix, row in enumerate(smoke):
        row = dict(row); row['source_i'] = row['i']; row['i'] = ix
        smoke[ix] = row
    assert len(smoke) == 12
    path=OUT/'smoke12.json'
    with path.open('x',encoding='utf-8') as f: json.dump(smoke,f,ensure_ascii=False,indent=2)
    hashes['smoke12']=dict(expected=12,prompt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          groups=dict(normal=4,no_request=4,trap=4))
    contract=dict(model='Valen-Team/Valen-0.8B', revision='3bf3e6d6318385884bf85e38dea1ca59afdf93f1',
        our_training=False, publisher_training='Developer decision SFT on Qwen3.5-0.8B',
        output='Native choice head probabilities; not generated JSON or next-token probabilities',
        execution='shared_state', temperature=1.0, checkpoint_dtype='float32',
        backbone_autocast='bfloat16', head_dtype='float32', max_choices=255,
        max_tokens=32768, truncation=False, information_contract='Original itinerary, date, previous dialogue, question and policy; exact item descriptions plus NONE',
        gold_not_in_predict_input=True, suites=hashes, main_expected=sum(len(x) for x in data.values()),
        final_ranking=False, smoke_purpose='API/load/memory/probability contract, not accuracy selection')
    with (OUT/'contract.json').open('x',encoding='utf-8') as f: json.dump(contract,f,ensure_ascii=False,indent=2)
    with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:
        f.write('# Valen-0.8B 원본 선택지 평가 입력\n\n기존 여행 개발·회귀 9,425문항을 원본 결정 API 입력으로 옮겼습니다. 정답·문항 번호는 감사 기록에만 보관하며 predict 입력에는 넣지 않습니다. 일정·날짜·앞 대화·질문·공통 판단 규칙은 유지하고 JSON 생성 형식 지시만 원본 선택지 API로 교체합니다. 정상 4·요청없음 4·함정 4의 연결검사는 별도입니다. 독립 보류 자료가 아니며 정확도·속도 경로를 일반 JSON 생성과 구분합니다.\n\n[고정 계약·해시](contract.json)\n')
    print(json.dumps(contract,ensure_ascii=False))

if __name__ == '__main__':
    main()
