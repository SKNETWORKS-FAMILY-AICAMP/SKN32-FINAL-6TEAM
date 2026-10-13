"""출발 보류의 감시·재탐색 연결 결과와 21개 기능 판단을 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v16'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v17'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['departure_watch_connection'] = proof
    for row in catalog['features']:
        if row['name'] in ('실시간 지하철·버스 도착', '도보 소요·역 접근 시간'):
            row['need'] = row['need'].replace('지각 Case 전달', '실제 탑승 상태와 안내 발행 경합 검증')
            row['need'] += ' 안내 미발행 이동의 감시·재탐색·새 일정·출발 안내 연결을 DB에서 확인했습니다. 실제 이동 오차와 탑승 중 재계산은 남았습니다.'
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    (OUT/'readiness-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    # acop 프로필, 비교 추적 흐름도. 첫 차이는 출발한 시각의 이동을 감시가 읽는지다.
    cells = [(48,112,'감시 대상 선정','미도달: 출발 시간이 지난 이동 제외',True),
        (528,112,'감시 대상 선정','실행: 출발 안내 미발행 이동 재검증',True),
        (48,232,'이동 담당 경로 계산','미도달: 사건 없으면 변경 안 함',False),
        (528,232,'이동 담당 경로 계산','실행: 현재 시각·인원·조건으로 재탐색',False),
        (48,352,'일정 적용·안내','미도달: 보류 결과가 끝으로 이어지지 않음',False),
        (528,352,'일정 적용·안내','통과한 새 일정 적용 후 출발 안내',False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" '
        f'fill="{"#f1f4f8" if focal else "#ffffff"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="15">{escape(state)}</text>'
        for x,y,title,state,focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#watch-arrow)"/>'
                    for x in (248,728) for y in (184,304))
    svg = f'''<svg viewBox="0 0 976 536" role="img" aria-labelledby="watch-title watch-desc">
<title id="watch-title">출발 보류에서 일정 재조정까지의 연결</title>
<desc id="watch-desc">수정 전은 출발 시간이 지난 이동을 감시하지 못했습니다. 수정 후는 안내 미발행 이동을 다시 읽고 현재 경로 계산과 일정 적용으로 연결합니다.</desc>
<defs><marker id="watch-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<rect width="976" height="536" fill="#fbfcfd"/><g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="64" font-size="24" text-anchor="middle">수정 전</text><text x="728" y="64" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="464" x2="928" y2="464" stroke="#dbe0ea"/>
<text x="48" y="492" font-size="16">첫 차이: 예정 출발~다음 방문 시작 전, 안내 미발행 이동을 다시 읽는가</text>
<text x="48" y="520" font-size="16">계획 출발지 기준입니다. 실제 위치·탑승·독립 정확도 검증은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name','status','scope','metric','reason','need'))+'</tr>' for row in catalog['features'])
    total = proof['regression']['total']
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v17</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>출발 안내가 보류된 이동을 일정 재조정까지 연결했습니다</h1>
<p>확대 시험 {proof['regression']['passed']}/{total} · 포함 관련 시험 {proof['related_passed']}/{proof['related_total']} · 로컬 개발 DB 2/2.</p>
<section><h2>현재 시각에서 새 경로를 계산합니다</h2><p>예정 출발 시간이 지난 이동도 다음 방문 시작 전까지, 출발 안내를 아직 발행하지 않았다면 감시가 다시 확인합니다.
이동 담당은 처리 시각과 최신 인원·조건으로 경로를 다시 만듭니다. 저장된 소요와 출발 시각을 대안으로 다시 쓰지 않습니다. 이미 안내한 이동의 탑승 상태는 추정하지 않습니다.</p>
{svg}<p>그림: 비교 추적 흐름도, 문서 폭 976×536, acop 프로필·로컬 글꼴 대체. 새 계산이 불가능하면 일정 적용 성공으로 처리하지 않습니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·로그·백업</a> · <a href="../2026-10-09_mobility_readiness_v16/mobility-readiness.html">이전 v16</a></p></section>
<section><h2>21개 기능의 근거와 남은 검증</h2><p>조건부 사용 4/21 · 개선 필요 9/21 · 추가 검증 8/21. 기능 수는 제품 준비율이 아닙니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>새 지도 경로 관측과 실제 이동·탑승·결제 측정은 이번에 수행하지 않았습니다. 안내 발행 경합, 현재 동행 조건 대조, 다음 방문 시작 이후 지각, 탑승 중 재탐색, 합법 차량 진입, 복잡한 회전, 혼합 운임은 남았습니다. 전체21 완료는 아닙니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(로컬 개발 DB 연동): 했음. 배포된 cs 프로젝트 서버 응답: 안 했음.</p>
<p>브라우저의 file: URL 정책 차단으로 화면 렌더 확인은 수행하지 못했습니다. 구조·링크·SVG 접근성 속성만 정적으로 검증했습니다.</p>
</main></body></html>'''
    (OUT/'mobility-readiness.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(features=21,counts=dict(counts)),ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
