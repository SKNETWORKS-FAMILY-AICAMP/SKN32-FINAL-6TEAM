"""급행 입력의 안내 저장 전후 대조와 남은 확정 경합을 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v23'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v24'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD / 'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['express_notice_storage_validation'] = proof
    before = '조회와 안내 저장 사이 급행 입력 교체·실시간 지하철 연결·운영 수집과 배포는 남았습니다.'
    after = ('안내 INSERT 전후 급행 내용 판을 검사해 변경·읽기 실패 때 거래를 되돌리는 조건을 확인했습니다. '
             '마지막 검사~COMMIT 사이 외부 교체·실시간 지하철 연결·운영 수집과 배포는 남았습니다.')
    for row in catalog['features']:
        row['need'] = row['need'].replace(before, after)
    assert len(catalog['features']) == 21
    assert dict(Counter(row['status'] for row in catalog['features'])) == catalog['counts']
    cells = [(48, 104, '관측은 급행 판 A로 계산', '이때는 저장 문맥과 같은 판', False),
             (528, 104, '관측은 급행 판 A로 계산', '대조할 판 A를 별도 복사', False),
             (48, 224, '안내 저장 전후 급행 판 B로 교체', '급행 자료의 최종 검사가 없음', True),
             (528, 224, '안내 INSERT 전후 내용 판 대조', '파일만 읽기 · 도착 API 재조회 없음', True),
             (48, 344, '이전 판 A의 안내를 확정', '조회 뒤·삽입 뒤 두 조건에서 재현', False),
             (528, 344, '변경 감지 → 안내 거래 취소', '읽기 실패도 취소 · 다음 감시에 전달', False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" '
        f'fill="{"#f1f4f8" if focal else "#fbfcfd"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="16">{escape(detail)}</text>'
        for x, y, title, detail, focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#storage-arrow)"/>'
                    for x in (248, 728) for y in (176, 296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="storage-title storage-desc">
<title id="storage-title">급행표의 늦은 변경에서 이전 안내 저장을 되돌리기</title>
<desc id="storage-desc">수정 전에는 출발 관측 뒤 급행표가 바뀌어도 안내를 확정했습니다. 수정 후 안내 삽입 전후 내용 판을 대조해 변경 또는 읽기 실패가 있으면 저장 거래를 되돌립니다.</desc>
<defs><marker id="storage-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28"><text x="248" y="56" font-size="24" text-anchor="middle">수정 전</text><text x="728" y="56" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/><text x="48" y="488" font-size="16">마지막 검사 이후 외부 작성자의 교체까지 원자적으로 막았다는 뜻은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>' + ''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for row in catalog['features'])
    base, integration = proof['regression'], proof['integration']
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v24</title>
<style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>급행표가 늦게 바뀌면 이전 안내 저장을 되돌립니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 수정 전 결함 재현2/2 · 신규 단위10/10 · 신규 DB9/9 · 포함 관련21/21 · 이동 기본층 {base['passed']}/{base['total']} · 출발·하루 안내 통합 {integration['passed']}/{integration['total']}.</p>
<section><h2>같은 저장 거래 안에서 두 번 확인합니다</h2>{svg}
<p>관측 판을 별도 복사해 INSERT 전과 후에 같은 내용 식별 식으로 검사합니다. 도착 API를 다시 호출하거나 전체 시간표를 거래 안에서 적재하지 않습니다. 변경이면 저장 거래를 취소하고, 읽기 실패·잘못된 검사 응답이면 치명 상태를 보고하며 안내를 취소합니다. 기다림 문구·하루 안내·급행 추적 없는 수동 런타임은 기존 계약을 유지합니다.</p>
<p>실제 임시 gzip 파일을 바꾸는 통제 도보 구간의 로컬 개발 DB 시험입니다. 관측 뒤·삽입 뒤 변경과 삽입 뒤 문구 판 변조, 두 검사 시점의 실패·잘못된 응답·같은 바이트의 수정 시각 변경·중복9회 감시를 확인했습니다. 신규 단위10은 기본층에, 신규 DB9는 통합에 포함됩니다. 관련21은 두 묶음의 일부를 모은 수치로 중복 합산하지 않습니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v23/mobility-readiness.html">이전 v23</a></p></section>
<section><h2>21개 기능의 판단·비교 수치·남은 일</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 이번 상태 승격0/21. 아래 기존 웹 수치는 새 관측값이 아닙니다.</p><div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>마지막 검사~COMMIT 사이 외부 파일 교체·A→B→A 교체·확정/배달 뒤 변경에는 공통 자료 게시 절차가 필요합니다. 일반 시간표·다른 모델 입력의 저장 직전 검사, 실제 위치와 탑승, 실시간 지하철, 혼합 운임·누락 경로·1.2km 안의 독립 웹 표본도 남았습니다.</p>
<p>이번 새 웹 경로0건 · 실제 탑승/결제0건 · 지도 개발자 API 호출0건. 커밋·푸시·운영 배포·외부 메시지 전송은 하지 않았습니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음 — 로컬 개발 DB의 거래를 확인했으며 HTTP 응답을 확인한 것은 아닙니다.</p>
<p>HTML·SVG·JSON·링크 정적 검사만 수행합니다. 브라우저 렌더 확인은 하지 않았습니다. 폰트는 설치 상태에 따라 한국어 시스템 폰트로 대체됩니다.</p></main></body></html>'''
    OUT.mkdir(exist_ok=False)
    (OUT / 'readiness-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf8')
    (OUT / 'mobility-readiness.html').write_text(html, encoding='utf8')
    print(json.dumps(dict(features=21, counts=catalog['counts']), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
