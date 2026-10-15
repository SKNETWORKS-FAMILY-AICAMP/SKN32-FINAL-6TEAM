"""직접 도보 출발 재검증의 최신 근거와 21개 기능 현황을 새 파일에 보존한다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v11'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v12'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['walk_departure'] = proof
    catalog['features'][10]['need'] += ' 직접 도보의 현재 경로·계단 시간·출발 안내 연결은 통제 시험으로 확인했다. 실제 도보 오차 검증은 남음.'
    catalog['features'][15]['need'] = ('자동 알림 코드 조립과 새 직접 도보 문맥의 현재 재계산을 검증했다. '
        '옛 문맥 재경로·늦음 Case 전달·탑승 중 갱신·실제 차량 도착 대조가 남음.')
    assert len(catalog['features']) == 21
    counts = Counter(row['status'] for row in catalog['features'])
    assert dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as out:
        json.dump(catalog, out, ensure_ascii=False, indent=2)
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[key]))}</td>'
        for key in ('name', 'status', 'scope', 'metric', 'reason', 'need'))+'</tr>'
        for row in catalog['features'])
    status = ' · '.join(f'{name} {count}/21' for name, count in counts.items())
    html = f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>서울 이동 검증 v12</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f5f6f8;color:#19242e}}
main{{max-width:1320px;margin:auto;padding:28px}}section{{background:white;border:1px solid #d7dce1;padding:24px;margin:20px 0}}
h1{{font-size:30px}}h2{{font-size:23px}}.flow{{display:flex;gap:12px;flex-wrap:wrap}}.flow span{{padding:12px;border:1px solid #b5c6cf;background:#eef4f7}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #d7dce1;vertical-align:top}}
th{{background:#edf1f3}}td:nth-child(1){{min-width:110px}}td:nth-child(2){{min-width:80px}}a{{color:#065b88}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style><main>
<h1>직접 도보도 출발할 때 다시 계산합니다</h1>
<p>관련 시험 {proof['target_passed']}/{proof['target_total']}, 확대 회귀 {proof['regression_passed']}/{proof['regression_total']} 통과.
전체 21개 기능의 실제 사용 수준 달성은 계속 진행 중입니다.</p>
<section><h2>이번에 해결한 출발 안내 연결</h2><div class="flow">
<span>현재 일정 장소·저장 동행 조건</span><span>→ 명시적 도보 종류 확인</span>
<span>→ 보행망·계단 시간 재계산</span><span>→ 운영 여유·도착 목표 검사</span><span>→ 현재 예상 소요로 안내</span></div>
<p>보행망 단절은 안내 보류. 계산기 미가용은 기존 거리 환산 모델과 대체 이유를 기록.
직접 도보 로컬 DB 시험 2/2, 10회 확인에서 안내 1회. 실제 서울 보행 시간 측정은 아닙니다.</p>
<p>빈 구간만 보고 도보라고 추정하지 않습니다. 옛 저장 문맥 누락·지각 일정의 실제 재조정은 다음 관문입니다.</p>
<p><a href="../../{escape(proof['report'])}">이번 보고서·시험 로그·백업</a> ·
<a href="../2026-10-09_mobility_readiness_v11/mobility-readiness.html">이전 판과 비교</a></p></section>
<section><h2>21개 기능의 판단과 필요한 근거</h2><p>{escape(status)}</p>
<p>상태는 직전 판의 판단을 유지했습니다. 아래 웹 비교는 기존 개발 표본이며 이번 변경의 새 독립 검증이 아닙니다.
제품 경로·대체 소스·허용 오차·새 표본이 각각 확인되기 전에는 전체 완료로 세지 않습니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>판단 근거</th><th>남은 일</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<p>mock 서버 시험: 이번 단계에서는 사용하지 않았습니다. 로컬 DB와 실제 계산 코드에 통제 응답을 주입했습니다.
배포된 cs 프로젝트 서버 응답·실제 탑승·결제 확인: 이번 단계에서 안 했습니다. 지도 개발자 API 호출 0회.</p></main></html>'''
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as out:
        out.write(html)
    print(json.dumps({'features': len(catalog['features']), 'counts': counts}, ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
