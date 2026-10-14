"""저장 안내의 급행 내용 판 대조와 재계산 근거를 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v22'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v23'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD / 'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['stored_express_context_validation'] = proof
    old_need = '저장 안내 문맥의 급행 판 식별자·실시간 지하철 연결·운영 수집과 배포는 별도 남았습니다.'
    new_need = ('저장 문맥의 급행 내용 판 변경·옛 문맥 누락을 안내 보류와 재계산에 연결했습니다. '
                '조회와 안내 저장 사이 급행 입력 교체·실시간 지하철 연결·운영 수집과 배포는 남았습니다.')
    for row in catalog['features']:
        row['need'] = row['need'].replace(old_need, new_need)
    assert len(catalog['features']) == 21
    assert dict(Counter(row['status'] for row in catalog['features'])) == catalog['counts']
    cells = [(48, 104, '저장 후 급행표 A → B', '일반 시간표·규칙은 같은 판', False),
             (528, 104, '저장 후 급행표 A → B', '계산에 쓴 내용 판 A를 저장', False),
             (48, 224, '급행표 변경을 대조하지 않음', '일반 시간표·규칙만 비교', True),
             (528, 224, '내용 판 A ≠ B → 안내 보류', '외부 도착 조회 전에 재계산 요청', True),
             (48, 344, '이전 구간의 안내가 계속됨', '수정 전 두 조건에서 재현', False),
             (528, 344, '새 구간·판 B로 한 번 안내', '저장 → 사건 처리 → 새 안내 확인', False)]
    boxes = ''.join(
        f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" '
        f'fill="{"#f1f4f8" if focal else "#fbfcfd"}" '
        f'stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="16">{escape(detail)}</text>'
        for x, y, title, detail, focal in cells)
    arrows = ''.join(
        f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#context-arrow)"/>'
        for x in (248, 728) for y in (176, 296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="context-title context-desc">
<title id="context-title">급행표 변경을 저장된 출발 안내의 재계산으로 연결</title>
<desc id="context-desc">수정 전에는 급행표 변경을 놓쳤습니다. 수정 후 저장한 급행 내용 판과 현재 계산기의 판이 다르면 안내를 보류하고 새 구간을 계산해 한 번 안내합니다.</desc>
<defs><marker id="context-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="56" font-size="24" text-anchor="middle">수정 전</text>
<text x="728" y="56" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/>
<text x="48" y="488" font-size="16">통제 입력과 로컬 개발 DB 검증입니다. 실제 도착·탑승·배달 측정은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>' + ''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for row in catalog['features'])
    base, integration = proof['regression'], proof['integration']
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v23</title><style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>급행표가 바뀌면 이전 안내를 보류하고 다시 계산합니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 수정 전 결함 재현2/2 · 신규 단위8/8 · 포함 관련43/43 · 이동 기본층 {base['passed']}/{base['total']} · 출발 처리 통합 {integration['passed']}/{integration['total']}.</p>
<section><h2>내용 판의 저장·대조를 기존 재계산 흐름에 연결했습니다</h2>{svg}
<p>내용이 바뀌거나 이전 문맥에 판 식별자가 없으면 외부 도착 조회 전에 보류합니다. 경로·수정 시각만 바뀌고 내용이 같으면 불필요하게 보류하지 않습니다. 노선별 내용 해시와 파일 부재 상태만 식별자에 반영하며 로컬 파일 경로는 저장하지 않습니다.</p>
<p>실제 임시 급행 파일의10:00→10:05 교체를 계산기 연결에서 확인했습니다. 로컬 개발 DB의 신규2조건은 통제 도보 구간으로 이전 문맥·새 문맥 각각의 보류→사건 처리→새 일정→출발 안내1회 흐름을 확인했습니다. 실제 지하철 탑승 시나리오를 실행한 결과로 세지 않습니다. 신규8은 관련43과 기본층에 포함되고, 신규 DB2는 통합 묶음에 포함됩니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v22/mobility-readiness.html">이전 v22</a></p></section>
<section><h2>21개 기능의 판단과 비교 수치</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 이번 상태 승격0/21. 아래 기존 웹 수치는 새 측정값이 아닙니다.</p><div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>현재는 모든 저장 이동 구간에 공통 급행 내용 판을 대조합니다. 도보 등 직접 영향을 받지 않는 구간도 판 변경 때 한 번 다시 계산할 수 있습니다. 조회와 안내 저장 사이 입력 교체·이미 배달한 안내의 회수·실제 위치와 탑승·실시간 지하철 연결·혼합 운임·누락 경로·1.2km 안의 독립 웹 표본은 남았습니다.</p>
<p>이번 새 웹 경로0건 · 실제 탑승/결제0건 · 지도 개발자 API 호출0건. 커밋·푸시·운영 배포·외부 메시지 전송은 하지 않았습니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음 — 로컬 개발 DB의 저장 거래와 계산 시험을 했으며 HTTP 응답을 확인한 것은 아닙니다.</p>
<p>HTML·SVG·JSON·링크를 정적으로 검사합니다. 브라우저 렌더 확인은 하지 않았습니다. 폰트는 설치 상태에 따라 한국어 시스템 폰트로 대체됩니다.</p></main></body></html>'''
    OUT.mkdir(exist_ok=False)
    (OUT / 'readiness-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf8')
    (OUT / 'mobility-readiness.html').write_text(html, encoding='utf8')
    print(json.dumps(dict(features=21, counts=catalog['counts']), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
