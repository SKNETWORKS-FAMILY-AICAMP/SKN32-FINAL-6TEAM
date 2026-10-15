"""급행 표 변경 감시와 런타임 교체 검증을 별도 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v21'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v22'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD / 'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['express_source_reload_validation'] = proof
    for row in catalog['features']:
        if row['name'] in ('지하철 경로 산출', '첫차·막차·출발 역산', '실시간 지하철·버스 도착'):
            row['need'] += ' 급행 표만 바뀐 경우 새 런타임의 열차를 갱신하는 통제 시험을 확인했습니다. 저장 안내 문맥의 급행 판 식별자·실시간 지하철 연결·운영 수집과 배포는 별도 남았습니다.'
    assert len(catalog['features']) == 21
    assert dict(Counter(row['status'] for row in catalog['features'])) == catalog['counts']
    cells = [(48,104,'급행 표 출발10:00→10:05','파일만 새 표로 바뀜',False),
        (528,104,'급행 표 출발10:00→10:05','파일 정보와 내용의 SHA-256 대조',False),
        (48,224,'노선 이름만으로 캐시 재사용','런타임 감시에서도 급행 표를 놓침',True),
        (528,224,'새 표로 런타임 다시 구성','구성 중 표가 바뀌면 게시 보류',True),
        (48,344,'다음 계산도 출발10:00 사용','두 통제 재현에서 옛 계산 확인',False),
        (528,344,'다음 계산은 최신 열차 사용','10:00 첫차 이전 · 10:05 탑승 계산',False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" fill="{"#f1f4f8" if focal else "#fbfcfd"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="16">{escape(detail)}</text>'
        for x,y,title,detail,focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#express-arrow)"/>'
        for x in (248,728) for y in (176,296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="express-title express-desc">
<title id="express-title">급행 표의 변경을 다음 이동 계산에 반영</title>
<desc id="express-desc">기존 계산은 노선 이름만으로 급행 표를 재사용했습니다. 수정 후 급행 파일의 입력 판을 대조하고 새 판정기로 교체하며 구성 도중 바뀐 입력은 게시하지 않습니다.</desc>
<defs><marker id="express-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<g font-family="Geist, Malgun Gothic, sans-serif" fill="#161c28"><text x="248" y="56" font-size="24" text-anchor="middle">수정 전</text><text x="728" y="56" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/><text x="48" y="488" font-size="16">통제 자료의 표 갱신 검증입니다. 실제 지하철 도착 관측·탑승 시험은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name','status','scope','metric','reason','need'))+'</tr>' for row in catalog['features'])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v22</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>급행 표만 갱신해도 다음 이동 계산에 최신 열차를 사용합니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 최초 결함 재현2/2 · 같은 파일 정보 교체 재현2/2 · 신규 조건11/11 · 포함 관련41/41 · 확대 {proof['regression']['passed']}/{proof['regression']['total']}.</p>
<section><h2>파일 변경 감시와 메모리 재사용을 함께 고쳤습니다</h2>{svg}
<p>표 변경·새 파일 생성·삭제·경로 변경·읽기 실패 후 복구·읽는 도중 교체·판정기 구성 도중 교체를 통제 시험에서 확인했습니다. 변경이 없으면 같은 열차 객체를 재사용합니다. 이미 계산 중인 이전 판의 객체는 바꾸지 않습니다.</p>
<p>수정 시각·크기·파일 식별자가 같은 교체도 내용 해시로 구별합니다. 최초 메타데이터 수정안이 재실행에서 놓친 두 조건도 보강 후 통과했습니다. 표가 처음부터 없거나 읽히지 않을 때의 기존 일반 시간표 사용 방식은 유지했으며, 그 대체 표의 실운행 정확도를 이번에 검증한 것은 아닙니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v21/mobility-readiness.html">이전 v21</a></p></section>
<section><h2>21개 기능의 판단과 비교 수치</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 이번에는 상태를 승격하지 않았습니다. 아래 기존 비교 수치를 새 웹 측정으로 부르지 않습니다.</p><div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>최초 자료 적재 지연·실제 요청 시간·저장 안내 문맥의 급행 판 식별·실시간 지하철 연결·전체 환승·혼합 운임·독립 웹 표본은 남았습니다. 새 웹 경로0건, 실제 탑승/결제0건. 운영 수집·배포는 수행하지 않았습니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음 — 이번에는 로컬 이동 계산을 실행했습니다.</p>
<p>HTML·SVG·JSON·링크를 정적으로 검사합니다. 브라우저 렌더 확인은 하지 않았습니다. 폰트는 설치 상태에 따라 한국어 시스템 폰트로 대체됩니다.</p></main></body></html>'''
    OUT.mkdir(exist_ok=False)
    (OUT/'readiness-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'mobility-readiness.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(features=21,counts=catalog['counts']),ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
