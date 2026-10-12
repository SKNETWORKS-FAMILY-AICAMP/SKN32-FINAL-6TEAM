"""고정 E/MX 원본을 바꾸지 않고 전체 문장 목록과 대화 내 문항 보기를 만든다."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
CATEGORIES = {'MX1': '기존 항목 정보·확인 질문', 'MX2': '기존 항목 변경·취소', 'MX3': '일정 밖 장소·일반 여행 질문', 'MX4': '장소를 언급한 감상·잡담', 'MX5a': '새 항목 추가·일정 전체 변경', 'MX5b': '일정 전체 감정·불만', 'MX6a': '두 항목 언급 후 한 항목 요청'}

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    visualization_dir = Path(sys.argv[1])
    source = ROOT / 'datasets/travel/mx_testset/mx_main_prompts.json'
    raw = source.read_bytes()
    records = json.loads(raw)
    mixed = [r for r in records if r['kind'] == 'mixed']
    controls = {r['pair']: r for r in records if r['kind'] == 'control'}
    assert len(mixed) == 2007 and len(controls) == 2007
    assert len({r['i'] for r in mixed}) == 2007
    assert Counter(r['gold'] is None for r in mixed) == {False: 1033, True: 974}
    assert Counter(r['src'] for r in mixed) == {'code': 1768, 'llm': 239}
    schedules = {}
    for r in mixed:
        schedule = r['prompt'].split('\n\n고객 질문: ', 1)[0]
        assert schedules.setdefault(str(r['itin']), schedule) == schedule
        assert controls[r['pair']]['q'] == r['req']
        if r['gold'] is not None:
            assert any(line.startswith(str(r['gold']) + '. ') for line in schedule.splitlines())
    initial = next(i for i,r in enumerate(mixed) if r['src'] == 'llm' and r['gold'] is not None)
    payload = {'rows': [[r[k] for k in ['i','q','req','gold','cat','src','itin']] for r in mixed], 'itineraries': schedules, 'initialIndex': initial, 'categories': CATEGORIES}
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    stem = f'e-mixed-2007-{stamp}'
    view_dir = source.parent / 'views'
    view_dir.mkdir(exist_ok=True)
    fragment = visualization_dir / f'{stem}.html'
    template = (Path(__file__).parent / 'e_mixed_view_template.html').read_text(encoding='utf-8')
    html = template.replace('__E_DATA__', json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c'))
    assert len(html.encode()) < 1000000
    with fragment.open('x', encoding='utf-8') as f: f.write(html)
    md = view_dir / f'{stem}.md'
    def clean(s): return str(s).replace('|', '\\|').replace('\r', '').replace('\n', '<br>')
    lines = ['# E 혼합 문장 2,007개 원문 보기', '', '고정 시험 원본의 혼합 문장만 추린 보기입니다. 시험 원본·정답·모델 답안은 변경하지 않았습니다.', '', '| 할 일 | 상태 | 진행 |', '|---|---|---|', '| 혼합 문장 수록 | 완료 | 2,007/2,007 = 100% |', '', '정상 요청 1,033개와 기존 일정 항목을 고르면 안 되는 문장 974개입니다. 코드로 이어 붙인 1,768개와 모델이 자연스럽게 작성한 239개를 함께 보여 줍니다. 정답은 모델 간 합의로 정한 저장값이며 사람 검수 전입니다.', '', f'원본 SHA256: `{hashlib.sha256(raw).hexdigest()}`', '', '| 번호 | 원본 ID | 문장 | 잡담을 뺀 비교 문장 | 저장된 정답 항목 | 만든 방식 |', '|---:|---:|---|---|---|---|']
    for n,r in enumerate(mixed, 1):
        schedule = schedules[str(r['itin'])]
        gold = '선택 없음 (null)' if r['gold'] is None else next(line for line in schedule.splitlines() if line.startswith(str(r['gold']) + '. '))
        origin = '자연 혼합(모델 작성)' if r['src'] == 'llm' else '코드 이어 붙임'
        lines.append('| ' + ' | '.join(map(clean, [n,r['i'],r['q'],r['req'],gold,origin])) + ' |')
    lines += ['', '## 문장별 여행 일정', '', '문항과 함께 모델에 제공된 일정입니다. 원문 그대로이며 현재 실제 여행 상품 일정이 아닙니다.', '']
    for key,schedule in schedules.items():
        lines += [f'### 일정 {key}', '', schedule.replace('\n','  \n'), '']
    with md.open('x', encoding='utf-8') as f: f.write('\n'.join(lines))
    verification = {'source': str(source), 'source_sha256': hashlib.sha256(raw).hexdigest(), 'mixed': len(mixed), 'control': len(controls), 'normal': 1033, 'no_item': 974, 'code': 1768, 'natural': 239, 'itineraries': len(schedules), 'source_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == hashlib.sha256(raw).hexdigest(), 'all_control_text_matches': True, 'all_gold_items_exist': True, 'human_check': 0, 'viewer_bytes': fragment.stat().st_size, 'viewer': str(fragment), 'markdown': str(md), 'initial_item': initial+1}
    with (view_dir / f'{stem}.json').open('x', encoding='utf-8') as f: json.dump(verification,f,ensure_ascii=False,indent=2)
    print(json.dumps(verification,ensure_ascii=False))

if __name__ == '__main__': main()
