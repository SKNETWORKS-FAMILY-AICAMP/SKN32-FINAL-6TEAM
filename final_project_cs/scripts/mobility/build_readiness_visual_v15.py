"""자료 없는 경로의 거리 표시 수정과 도로 선택 불안정을 새 판에 보존한다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v14'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v15'


def main(proof_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['legacy_selection'] = proof
    for index in (2, 3):
        catalog['features'][index]['need'] += ' 도로 위 좌표로 이동해도 다른 후보를 다시 선택했다. 진입 도로 통제가 필요하며 웹 확인은 미완료다.'
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].bar(['수정 전 응답', '수정 후 응답'], [0, 8.8], color=['#aa554c', '#1b6a87'])
    axes[0].set_title('회전 자료 없는 합성 도로: 실제 선택 거리 보존')
    axes[0].set_ylabel('출발 좌표 → 선택 도로(m)')
    axes[0].set_ylim(0, 12)
    axes[0].text(0, .5, '잘못된 0m', ha='center', color='#aa554c')
    axes[0].text(1, 9.2, '8.8m 보존', ha='center')
    original, shifted = proof['real_probe']['observations'][:2]
    axes[1].bar(['기존 출발점', '도로 위로 옮긴 출발점'],
                [original['snap_m'][0], shifted['snap_m'][0]], color=['#607b8b', '#aa554c'])
    axes[1].set_title('실제 서울 그래프: 좌표를 옮겨도 다른 도로 선택')
    axes[1].set_ylabel('요청 좌표 → 실제 선택 도로(m)')
    axes[1].set_ylim(0, 14)
    for i, value in enumerate([original['snap_m'][0], shifted['snap_m'][0]]):
        axes[1].text(i, value+.4, f'{value}m', ha='center')
    fig.text(.035, .018, '왼쪽: 통제 재현 4조건 · 오른쪽: 개발 좌표 2조건×3회 · 합법 진입 및 웹 정확도 검증 아님', fontsize=10)
    fig.tight_layout(rect=(0, .055, 1, 1))
    fig.savefig(OUT/'road-selection-instability.png', dpi=150)
    plt.close(fig)
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[key]))}</td>'
        for key in ('name', 'status', 'scope', 'metric', 'reason', 'need'))+'</tr>'
        for row in catalog['features'])
    status = ' · '.join(f'{name} {count}/21' for name, count in counts.items())
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>서울 이동 검증 v15</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f5f6f8;color:#19242e}}
main{{max-width:1320px;margin:auto;padding:28px}}section{{background:white;border:1px solid #d7dce1;padding:24px;margin:20px 0}}
h1{{font-size:30px}}h2{{font-size:23px}}img{{max-width:100%;height:auto}}.table{{overflow:auto}}
table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #d7dce1;vertical-align:top}}
th{{background:#edf1f3}}a{{color:#065b88}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>실제 선택 거리 표시는 고쳤고, 출발 도로가 다시 바뀌는 조건을 확인했습니다</h1>
<p>확대 회귀 {proof['regression']['passed']}/{proof['regression']['total']} 통과 · 관련 시험 {proof['target_passed']}/{proof['target_total']}.
전체 21개 기능 완료는 아닙니다.</p>
<section><h2>고친 부분과 남은 원인</h2><p>회전 자료가 없는 차량 경로에서도 실제 선택한 출발·도착 도로의 거리를 남깁니다.
자료 없는 상태는 계속 미가용이며 법규가 적용됐다고 표시하지 않습니다. 도보·자전거의 가장 가까운 후보 하나 정책은 유지했습니다.</p>
<p>실제 서울 그래프에서는 선택 도로 위로 출발점을 8.8m 옮겼는데, 다시 10.9m 떨어진 다른 도로를 선택했습니다.
원래 좌표의 모델 경로는 98.29m·9.175초, 옮긴 좌표는 87.32m·7.859초입니다.
요청 좌표가 다르므로 개선율이나 정확도 점수로 계산하지 않습니다.</p>
<img src="road-selection-instability.png" alt="합성 도로 거리 표시 수정과 실제 서울 좌표 이동 후 다른 도로 선택 현상">
<p>도로 접근의 물리적 가능성·합법 진입은 미확인입니다. 더 짧은 경로를 낼 수 있다는 사실로 이를 대신하지 않습니다.</p>
<p>새 네이버 조회는 화면 이동을 확인하지 못했습니다. 이번 새 웹 경로 결과 0건이며 기존 카카오·네이버 수치를 새로 측정한 값으로 쓰지 않았습니다.
OSRM 공식 문서의 도로 방향·반경·도로 측면 제약을 확인했으나 우리 제품에 구현한 것은 아닙니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·재현·백업</a> ·
<a href="../2026-10-09_mobility_readiness_v14/mobility-readiness.html">이전 v14</a></p></section>
<section><h2>21개 기능의 판단과 남은 검증</h2><p>{escape(status)}</p>
<p>기능 수는 준비율이 아닙니다. 과거 개발 표본의 비교 수치와 현재 코드 시험을 구분합니다.
각 기능의 제품 경로·대체 소스·허용 오차·새 표본 검증이 필요합니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>mock 서버 시험(화면 반응): 안 했음. 합성 도로의 후보를 주입한 단위 시험 포함.
실서버 확인(로컬 개발 DB 연동): 확대 시험에서 했음. 배포된 cs 프로젝트 서버 응답: 안 했음.
실제 탑승·결제: 안 했음. 지도 개발자 API 직접 호출 0회.</p></main></body></html>'''
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as f:
        f.write(html)
    print(json.dumps(dict(features=len(catalog['features']), counts=dict(counts)), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
