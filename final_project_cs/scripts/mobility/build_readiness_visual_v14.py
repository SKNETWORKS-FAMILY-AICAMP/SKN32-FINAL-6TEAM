"""선택 도로 근거 수정과 웹 경로 불일치를 새 판에 보존한다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v13'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v14'


def main(proof_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    probe = proof['post_probe']['repeats'][0]
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['selected_road_evidence'] = proof
    for index in (2, 3):
        catalog['features'][index]['need'] += (
            ' 실제 선택 도로의 붙임 거리와 다른 후보 사용 근거를 보존했다. '
            '동일 좌표의 네이버 100m·카카오 약 800m 차이는 출발 도로·시각 정렬 후 판정해야 한다.')
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={'width_ratios': [1.5, 1]})
    axes[0].barh(['네이버 웹 예상', '카카오 웹 예상(반올림)', '우리 모델(다른 진입 도로)'],
                 [100, 800, probe['distance_m']], color=['#607b8b', '#607b8b', '#156987'])
    axes[0].invert_yaxis()
    axes[0].set_xlabel('경로 거리(m) — 실제 주행 거리 측정 아님')
    axes[0].set_title('동일 요청 좌표, 출발 도로·시각은 미정렬', pad=15)
    axes[0].grid(axis='x', alpha=.18)
    axes[1].bar(['수정 전 응답', '수정 후 응답'], [0, probe['snap_m'][0]], color=['#a74f45', '#156987'])
    axes[1].set_ylabel('출발 좌표 → 선택 도로 거리(m)')
    axes[1].set_title('실제 선택 도로는 8.8m 떨어져 있음', pad=15)
    axes[1].set_ylim(0, 11)
    axes[1].text(0, .5, '잘못된 0m 표시', ha='center', color='#a74f45')
    axes[1].text(1, 9.1, '실제 선택 근거 보존', ha='center')
    fig.text(.025, .018,
             '개발 좌표쌍 1개 · 구글 경로 미제공(0m로 표시하지 않음) · 정확도 편입 0건 · 합법 진입 확인 미완료',
             fontsize=11)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(OUT/'selected-road-and-web-conflict.png', dpi=150)
    plt.close(fig)
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[key]))}</td>'
        for key in ('name', 'status', 'scope', 'metric', 'reason', 'need'))+'</tr>'
        for row in catalog['features'])
    status = ' · '.join(f'{name} {count}/21' for name, count in counts.items())
    passed, total = proof['regression_passed'], proof['regression_total']
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>서울 이동 검증 v14</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f5f6f8;color:#19242e}}
main{{max-width:1320px;margin:auto;padding:28px}}section{{background:white;border:1px solid #d7dce1;padding:24px;margin:20px 0}}
h1{{font-size:30px}}h2{{font-size:23px}}.flow{{display:flex;gap:12px;flex-wrap:wrap}}
.flow span{{padding:12px;border:1px solid #b5c6cf;background:#eef4f7}}img{{max-width:100%;height:auto}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}
th,td{{text-align:left;padding:12px;border-bottom:1px solid #d7dce1;vertical-align:top}}th{{background:#edf1f3}}
a{{color:#065b88}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>다른 도로를 선택했을 때 그 거리와 근거가 사라지는 결함을 고쳤습니다</h1>
<p>관련 시험 45/45 · 확대 회귀 {passed}/{total} 통과. 실제 그래프 동일 개발 좌표쌍 3회 일치.
전체 21개 기능은 계속 검증 중입니다.</p>
<section><h2>고친 동작</h2><div class="flow"><span>실제 선택한 출발·도착 도로</span>
<span>→ 좌표에서 떨어진 거리와 대체 후보 표시</span><span>→ 자동차·택시 계산 요약</span>
<span>→ 여행 판단 근거에 보존</span></div>
<p>이 사례는 가장 가까운 출발 도로가 0m이나, 회전 조건을 만족하는 다른 도로를 선택해 실제 붙임 거리는 8.8m입니다.
수정 전에는 0m로 표시했습니다. 이제 실제 선택 거리와 다른 후보 사용 여부를 보존합니다.
좌표열·내부 도로 탐색 목록은 여행 판단에 저장하지 않습니다.</p>
<p>8.8m 접근이 물리적으로 가능한지, 해당 도로 진입이 합법인지는 아직 확인하지 않았습니다.
이 표시 수정만으로 경로 거리·택시 예상액의 정확도가 개선됐다고 판정하지 않습니다.</p></section>
<section><h2>웹에서 확보한 대조군과 남은 충돌</h2>
<p>새 개발 좌표쌍 1개를 네이버·카카오·구글에서 조회했습니다. 경로 제공 2/3, 정확도 편입 0건입니다.
네이버는 1분·100m·택시 5,800원, 카카오는 2분·약 0.8km·유턴·택시 5,700원입니다.
구글은 이 좌표쌍의 자동차 경로를 제공하지 않았습니다. 구글의 TMap 출처 표시는 별도 티맵 대조군으로 세지 않았습니다.</p>
<img src="selected-road-and-web-conflict.png" alt="정렬하지 않은 웹 예상 거리와 실제 선택 도로 거리 표시 수정 비교">
<p>우리 모델은 다른 진입 도로에서 98.29m를 계산합니다. 실제 탑승·운행·결제 측정이 아닙니다.
OSM 웹의 해당 회전 관계는 오래된 금지 관계를 유지하지만 연결 도로에는 공사 반영 이력이 보입니다.
이 불일치만으로 금지 관계를 제거하거나 네이버 수치에 맞추지 않았습니다.</p>
<p>GPS 연속 관측을 활용하는 논문의 전제도 확인했습니다. 현재 고정 출발·도착 좌표만으로 실제 진입 도로를 확정할 수 있다는 근거로 쓰지 않았습니다.</p>
<p><a href="../../{escape(proof['report'])}">새 보고서·검증 로그·백업</a> ·
<a href="../2026-10-09_mobility_readiness_v13/mobility-readiness.html">이전 판 v13</a></p></section>
<section><h2>21개 기능의 판단과 남은 근거</h2><p>{escape(status)}</p>
<p>기능 수의 분모는 21개입니다. 위 상태 수는 제품 준비율이 아닙니다. 기존 판단을 승격하지 않았고
아래 비교 수치는 이전 개발 표본의 측정입니다. 제품 경로·대체 소스·허용 오차·새 검증 표본을 각각 확인해야 합니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<p>mock 서버 시험(화면 반응): 이번 단계에서 사용 안 함. 제어 응답을 주입한 단위 시험은 포함했습니다.
실서버 확인(로컬 개발 DB 연동): 확대 시험에 포함. 배포된 cs 프로젝트 서버 응답: 확인 안 함.
실제 탑승·결제: 측정 안 함. 지도 개발자 API 직접 호출 0회.</p>
</main></body></html>'''
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as f:
        f.write(html)
    print(json.dumps(dict(features=len(catalog['features']), counts=dict(counts)), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
