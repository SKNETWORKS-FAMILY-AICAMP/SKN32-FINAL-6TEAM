"""이전 판을 보존하고 현재 출발 재검증의 실행 근거를 새 시각화에 추가한다."""
from pathlib import Path
from datetime import datetime
from copy import deepcopy
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v9'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v10'
EVIDENCE = ROOT / 'wiki/records/evidence/2026-10-09_0122_출발시점_버스재검증'

def main():
    proof = json.loads((EVIDENCE / 'publication.json').read_text(encoding='utf-8'))
    comparison = json.loads((EVIDENCE / 'controlled-comparison.json').read_text(encoding='utf-8'))
    OUT.mkdir(exist_ok=False)
    for path in OLD.iterdir():
        if path.is_file() and path.name not in ('mobility-readiness.html', 'readiness-catalog.json'):
            shutil.copy2(path, OUT / path.name)
    catalog = deepcopy(json.loads((OLD / 'readiness-catalog.json').read_text(encoding='utf-8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['departure_verification'] = proof
    catalog['features'][15]['need'] = ('관측 소비·후속 구간 재검증과 안내 내부 주입 시험은 통과. 운영 일꾼 조립·'
        '운영 신선도 정책·이전 문맥 재경로·늦음 Case 재조정·실제 도착 오차 검증이 남음.')
    with (OUT / 'readiness-catalog.json').open('x', encoding='utf-8') as out:
        json.dump(catalog, out, ensure_ascii=False, indent=2)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False, 'font.size': 12})
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    values = [comparison['saved_model']['eta_min'], comparison['wait_only_counterfactual_min'],
              comparison['current_revalidated']['eta_min']]
    bars = ax.barh(['저장 당시 모델', '대기만 바꾼 산술', '현재 구간 재검증'], values,
                   color=['#93A5B5', '#B88741', '#126B67'], height=.55)
    ax.bar_label(bars, labels=[f'{n}분' for n in values], padding=5)
    ax.set_xlim(0, max(values) + 6)
    ax.set_xlabel('예상 소요(분) · 고정 시험 입력, 실제 운행 측정 아님')
    ax.set_title('대기 교체만으로는 바뀐 승차 시간대를 반영하지 못합니다')
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(OUT / 'departure-recalculation.png', dpi=150)
    plt.close(fig)
    section = f'''<section><h2>출발 관측으로 승차·후속 환승을 다시 계산했습니다</h2>
<p>관련 단위·로컬 DB 시험 {proof['target_passed']}/{proof['target_passed']} 통과,
 확대 기본 회귀 {proof['regression_passed']}/{proof['regression_passed']} 통과,
 소스 선택→계산→문구 연결 2/2 통과입니다. 중복되는 시험 수는 합산하지 않습니다.</p>
<img class="chart" src="departure-recalculation.png" alt="고정 입력의 저장 모델16분, 대기만 교체12분, 현재 구간 재검증21분 비교">
<p>고정 입력에서 정류장까지 6분 걸리므로 3분 뒤 차량은 놓치고 7분 뒤 차량을 선택합니다.
저장 당시 승차3분은 현재 승차 시각대에서12분이 되어, 대기만 바꾼12분 대신21분을 안내합니다.
실제 노선의 정확도나 독립 새 표본 성공률이 아닙니다.</p>
<p>현재 도착 예측은 정확한 첫 버스에만 사용하고 후속 환승·승차 소요·막차를 순서대로 재검증합니다.
지하철 이후 미래 버스에는 현재 차량 예측을 고정하지 않습니다.
늦거나 문맥이 바뀌면 기존 안내를 보류하고, 모델도 값을 못 내면 치명 상태로 반환합니다.</p>
<p><strong>운영 연결은 남았습니다.</strong> 실제 자동 알림 일꾼에 소스·정책·팀 콜백을 조립하고,
보류 결과를 일정 재조정으로 전달해야 합니다. 전체21기능 완료를 선언하지 않습니다.</p>
<p><a href="../../{proof['report']}">현재 출발 재검증 보고서</a> ·
<a href="../../../evidence/2026-10-09_0122_출발시점_버스재검증/publication.json">이번 실행 근거</a></p></section>'''
    text = (OLD / 'mobility-readiness.html').read_text(encoding='utf-8')
    text = text.replace('v9', 'v10')
    text = text.replace('<section>', section + '<section>', 1)
    with (OUT / 'mobility-readiness.html').open('x', encoding='utf-8') as out:
        out.write(text)
    print(json.dumps({'features': len(catalog['features']), 'output': str(OUT)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
