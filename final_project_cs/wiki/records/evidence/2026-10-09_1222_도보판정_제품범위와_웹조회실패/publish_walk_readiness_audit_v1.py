from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import hashlib
import importlib.util
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
NOW = datetime.now().astimezone()
TAG = NOW.strftime('%Y-%m-%d_%H%M') + '_도보판정_제품범위와_웹조회실패'
EV = CS / 'wiki/records/evidence' / TAG
ASSETS = CS / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v43'
REPORT = CS / 'wiki/records/reports' / (TAG + '.md')
BASE = CS / 'scripts/mobility/build_readiness_visual.py'
WIKI = CS / 'wiki/teams/mobility.md'
PRIOR = CS / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v42'
INTEGRITY = CS / 'wiki/records/evidence/2026-10-09_1156_지하철_부분응답_누락해소/final-integrity-v1.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, data):
    with p.open('x', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def catalog_at(p):
    spec = importlib.util.spec_from_file_location('readiness_audit', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # 함수가 요구하는 지하철 집계 입력. 도보 행에는 이 값이 사용되지 않습니다.
    return module.catalog({'rail_before': {'comparable': 93}, 'rail_after': {'comparable': 94},
                          'rail_same_route': {'n': 93, 'before_present': 68,
                                              'after_present': 93, 'new_upper': 12}})


prior_proof = json.loads(INTEGRITY.read_text(encoding='utf8'))
checks = {k: {p: sha(ROOT / p) == h for p, h in prior_proof[k].items()}
          for k in ('source_test_data_hashes', 'artifact_hashes')}
assert all(all(v.values()) for v in checks.values()), '최신 입력이 바뀌었습니다. 재대조해야 합니다.'
assert not EV.exists() and not ASSETS.exists() and not REPORT.exists()
before_rows = catalog_at(BASE)
before_walk = next(f for f in before_rows if f['name'] == '장소 사이 도보 거리')
assert before_walk['status'] == '조건부 사용'
EV.mkdir()
ASSETS.mkdir()
save(EV / 'baseline-integrity-v1.json', {'checked_at': NOW.isoformat(), 'checks': checks})
backups = []
for p in (BASE, WIKI):
    dest = p.parent / '_backup' / (NOW.strftime('%Y-%m-%d_%H%M%S') + '_도보판정_정정전') / p.name
    dest.parent.mkdir(parents=True)
    shutil.copy2(p, dest)
    assert sha(p) == sha(dest)
    backups.append({'source': p.relative_to(ROOT).as_posix(),
                    'backup': dest.relative_to(ROOT).as_posix(), 'sha256': sha(dest)})

# 판정 계약을 먼저 남깁니다. 이전 보고서와 원자료는 수정하지 않습니다.
wiki_hash = sha(WIKI)
wiki = WIKI.read_text(encoding='utf8')
assert sha(WIKI) == wiki_hash
WIKI.write_text(wiki + f'''\n\n## {TAG} 도보 사용 판정의 제품 범위 계약

제품 상한 밖 원시 도보 비교를 제품 사용 판정의 근거로 삼지 않습니다. 장소 사이 도보 거리는 정책 안의 출입점·추천 경로·관측시각 대조가 확보되기 전 추가 검증입니다. 17/30은 이전 원시 진단으로 보존하며 정확도 개선이나 준비율로 쓰지 않습니다. 기존 산출물은 동결하고 생성 원본과 새 판만 정정합니다.
''', encoding='utf8')
base_hash = sha(BASE)
text = BASE.read_text(encoding='utf8')
old = """      feature('장소 사이 도보 거리','조건부 사용','도로망이 연결된 평지 경로','카카오 ±10% 17/30; 중앙 +2.1%. 네이버 절대오차 평균 0.68km/12쌍.',
              '현재 지도에는 일부 보행 전용 샛길·계단이 빠질 수 있다.',
              '보행 전용 그래프, 공원·계단·횡단보도 연결과 실제 경로 대조.','fresh'),"""
new = """      feature('장소 사이 도보 거리','추가 검증','1.2km 정책 안의 직접 도보; 출입점 정렬 검증 대기',
              '기존 카카오 30쌍은 제품 상한 밖: 공개 제공 0/30. 원시 진단 ±10% 17/30·중앙 +2.1%는 제품 정확도가 아니다. 기존 네이버 MAE 0.68km/12쌍도 출입점·정책 정렬 미검증.',
              '정책 밖 원시 거리 비교가 조건부 사용 판정에 연결돼 있었다. 정책 안의 정렬된 새 제품 비교를 확보하지 못했다.',
              '같은 출입점 좌표·조회시각·추천 경로를 보존한 정책 안 새 표본과 제품 도보 옵션을 대조하고 실제 보행도 별도로 측정한다. 공원·계단·횡단보도 연결을 검증한다.','fresh'),"""
assert text.count(old) == 1
assert sha(BASE) == base_hash
BASE.write_text(text.replace(old, new), encoding='utf8')
after_rows = catalog_at(BASE)
after_walk = next(f for f in after_rows if f['name'] == '장소 사이 도보 거리')
assert after_walk['status'] == '추가 검증'
assert len(before_rows) == len(after_rows) == 21
assert all(a == b for a, b in zip(before_rows, after_rows) if a['name'] != '장소 사이 도보 거리')
cat = json.loads((PRIOR / 'readiness-catalog.json').read_text(encoding='utf8'))
old_feature = next(f for f in cat['features'] if f['name'] == '장소 사이 도보 거리')
cat['features'] = [after_walk if f['name'] == after_walk['name'] else f for f in cat['features']]
cat['counts'] = dict(Counter(f['status'] for f in cat['features']))
assert cat['counts'] == {'조건부 사용': 3, '개선 필요': 9, '추가 검증': 9}
cat.update(created_at=NOW.isoformat(), scope='도보 거리의 정책 밖 근거를 제품 사용 판정에서 분리. 새 웹 경로 수집 실패와 연구 적용 전제 보존.',
           prior_catalog_sha256=sha(PRIOR / 'readiness-catalog.json'), full_feature_completion=False)
save(ASSETS / 'readiness-catalog.json', cat)
attempts = [
    {'provider': 'naver', 'operation': '지도 탭 생성', 'result': 'tab 15 navigate timeout'},
    {'provider': 'naver', 'operation': '같은 탭 읽기', 'result': 'timeout; kernel reset'},
    {'provider': 'kakao', 'operation': '지도 탭 생성', 'result': 'Timed out waiting for tab 16 to navigate to https://map.kakao.com/.'},
    {'provider': 'kakao', 'operation': '문서화된 tabs.get', 'result': 'Timed out running CDP command "Emulation.setFocusEmulationEnabled" for tab 16'},
    {'provider': 'kakao', 'operation': '문서화된 cua.getTab', 'result': 'Timed out running CDP command "Emulation.setFocusEmulationEnabled" for tab 16'},
    {'provider': 'naver', 'operation': '기존 W03 공개 경로 주소 web.open', 'result': 'Internal Error; route values not retrieved'},
]
save(EV / 'acquisition-attempts-v1.json', {'recorded_at': NOW.isoformat(),
    'timestamps_basis': '개별 호출 시각은 별도 측정하지 않음. 이 세션 도구 결과 순서와 기록 생성시각을 보존.',
    'providers_attempted': 2, 'attempts': attempts, 'public_tab_inventory':
    [{'id': '15', 'title': 'map.naver.com/p', 'url': 'https://map.naver.com/p'},
     {'id': '16', 'title': '카카오맵', 'url': 'https://map.kakao.com/'}],
    'new_route_observations': 0, 'aligned_product_comparisons': 0,
    'map_developer_api_calls': 0, 'actual_walks': 0,
    'finding': '페이지 주소/제목은 열렸으나 제어기의 화면 읽기 단계가 시간 초과. 웹 서비스 자체의 제공 실패로 단정하지 않음.'})
save(EV / 'research-v1.json', {'checked_at': NOW.isoformat(), 'cutoff': '2026-10-09',
    'sources': [
      {'url': 'https://link.springer.com/article/10.1186/s12942-026-00473-7',
       'published': '2026-05-19', 'finding': '233명 실제 GPS와 모델 경로 겹침을 비교. 도로망 기준선은 붙인 지점이 단절돼 3명 경로를 못 냄.',
       'applicability': '지도 예상값 비교와 실제 보행 검증을 분리하고 원좌표·붙인 간선·경로 형상을 함께 기록한다. 스코틀랜드 아동 통학 결과이며 서울 성능·허용 오차로 이전하지 않는다.'},
      {'url': 'https://drops.dagstuhl.de/opus/volltexte/2015/5459/pdf/10.pdf',
       'published': '2015', 'finding': '광장 경계 진입점과 장애물을 피해 연결한 가시성 그래프를 추가하고 내부 출발·도착을 처리한다.',
       'applicability': '서울광장 비교가 정렬된 뒤에도 우회하면 실제 보행 가능 영역·장애물 자료와 현 그래프 연결을 먼저 검증한다. W03 차이의 원인으로 확정하지 않으며 직선 지름길을 임의로 추가하지 않는다.'},
      {'url': 'https://help.naver.com/service/5637/contents/8285',
       'finding': '네이버 공식 도보 길찾기 도움말 페이지 확인. 경로의 거리/시간 실측 자료가 아님.'}],
    'new_algorithm_applied': False, 'new_calibration_applied': False,
    'next_measurement': ['동일 출입점 좌표를 지도 UI에서 선택하고 선택 결과를 캡처',
      '같은 시점의 추천 경로·옵션·거리/시간·형상 보존',
      '그 좌표로 실제 제품 도보 옵션 재계산 및 그래프 해시 보존',
      '접근 간선/연결성/광장 장애물과 경로 선택을 검사한 뒤 원인별 수정',
      '기존 개발 표본과 다른 새 구간 검증; 실제 보행 별도 관측']})
save(EV / 'catalog-validation-v1.json', {'created_at': NOW.isoformat(),
    'before': before_walk, 'after': after_walk, 'latest_before': old_feature,
    'before_counts': {'조건부 사용': 4, '개선 필요': 9, '추가 검증': 8}, 'after_counts': cat['counts'],
    'unchanged_feature_rows': 20, 'total_feature_rows': 21,
    'validation': '실제 생성 함수 실행 전후를 대조. 다른20행 일치; 기존 산출물은 보존.',
    'runtime_changes': 0, 'new_test_execution': False})
save(EV / 'backup-manifest-v1.json', {'created_at': NOW.isoformat(), 'backups': backups})
report_text = f'''# 도보 거리 판정의 제품 범위 정정과 웹 조회 실패

도보 거리를 조건부로 사용할 수 있다는 판정에서 정책 밖 비교 근거를 빼고 추가 검증으로 정정했습니다. 새 웹 표본은 화면 읽기 오류로 확보하지 못했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최신 코드·시험·자료 대조 | 일치 | 256/256 = 100% |
| 기존 산출물 대조 | 일치 | 40/40 = 100% |
| 잘못 연결된 도보 판정 정정 | 검증 | 1/1 = 100% |
| 목표 새 도보 표본 | 화면 읽기 실패 | 0/1 = 0% |

기준시각 {NOW.isoformat()}. 범위는 서울 이동 모듈의 도보 제품 검증이며 이번 제품 계산·요율·허용 오차 변경은0건입니다. 계획 기준은 v11 §5 이동·§6-B 출발 안내입니다.

## 정정한 근거

생성 원본의 `catalog` 함수와 최신v42 모두 장소 사이 도보 거리를 조건부 사용으로 분류했습니다. 근거17/30은 기존 카카오30쌍 원시 진단이지만 해당30쌍의 직선거리는1,617~3,897m로 제품1,200m정책 밖입니다. 제품 공개제공은0/30이고 정책 안의 출입점·추천 경로·조회시각이 맞는 새 비교는 이번에0개입니다. 네이버12쌍의0.68km도 같은 조건 검증을 대신하지 않습니다.

새v43은 추가 검증으로 분류하고 원시 진단17/30을 별도로 명시합니다. 전체21분류는 조건부3/21·개선9/21·추가검증9/21이며 완료율이 아닙니다. 다른20행은v42와 같습니다. 이전v42와 이전 보고서는 작성 당시 기록으로 보존합니다.

변경 파일은 [생성 원본](../../../scripts/mobility/build_readiness_visual.py), [이동 정본](../../teams/mobility.md), [새21개기능 시각화](assets/{ASSETS.name}/mobility-readiness.html)입니다. 생성 함수를 전후 실제 실행해 도보1행만 바뀌고20/20행이 같은지 확인했습니다. 기존 출력 생성 명령 전체를 실행하지 않았으며 예전 산출물을 다시 쓰지 않았습니다. 제품 시험을 새로 실행한 턴이 아닙니다. 이전284/284 시험은 이전 턴 결과입니다.

## 웹 확보 시도와 확인 범위

네이버·카카오 두 제공처에서 공개 지도 탭 생성과 문서화된 화면 읽기를 시도했습니다. 탭 목록에는 두 공개주소/제목이 표시됐지만 카카오는 `Emulation.setFocusEmulationEnabled` 단계 시간 초과가 두 읽기 방식에서 반복됐고 네이버도 시간 초과였습니다. 기존W03 네이버공개주소의web.open도Internal Error였습니다. 지도 서비스 자체가 경로를 제공하지 못한다고 결론 내리지 않습니다. 현재 확인 범위는 이 앱 브라우저 제어 경로이며 다른 기기/실보행은 미측정입니다.

새 지도 경로 관측0개·정렬된 제품 비교0개·지도 개발자API0회·실제 보행0회입니다. 기존W03의네이버101m2분/카카오236m4분은2026-10-09_0054 당시 자료이고 새 값으로 재사용하지 않았습니다. 같은 시설명으로 좌표가 같다고 추정하거나 그 차이를 요율/속도 상수로 보정하지 않았습니다. 상세도구결과는 [조회 시도 기록](../evidence/{TAG}/acquisition-attempts-v1.json)에 보존합니다.

## 오늘까지 공개된 연구와 다음 적용 조건

[2026년 실제GPS 대조 연구](https://link.springer.com/article/10.1186/s12942-026-00473-7)는233명 아동의 실제 보행과 지도모델을 구별하며 도로망 기준선에서 붙인 지점의 단절로3명 경로가 제외됨을 보고합니다. 서울의 오차율이나 보정계수로 옮기지 않습니다. [광장·공원 보행 연구](https://drops.dagstuhl.de/opus/volltexte/2015/5459/pdf/10.pdf)는 경계 진입점과 장애물을 반영한 연결을 제안합니다. 같은 출입점을 고정한 뒤에도 서울광장 우회가 남는 경우 검토할 방법이며 지금W03 차이의 원인으로 확정하지 않았습니다. 상세전제는 [연구 기록](../evidence/{TAG}/research-v1.json)에 있습니다.

다음에는 같은 좌표를 UI에서 선택하고 추천 옵션·거리/시간·형상·조회시각을 캡처한 뒤 그 좌표로 제품 도보 옵션을 계산합니다. 원좌표와 붙인 간선, 보행망 연결, 광장 장애물을 대조해 원인을 분리합니다. 임의 지름길이나 공급자 값에 맞춘 상수를 넣지 않습니다. 웹 비교는 실제 보행 정확도의 대체 근거가 아닙니다.

mock 서버 시험(화면 반응): 이번 턴 안 했음.

실서버 확인(서버 응답): cs 프로젝트 서버HTTP·배달·배포 확인 안 했음. 이번 공개지도 페이지의 경로값 읽기도 실패했습니다.

백업은 [명세](../evidence/{TAG}/backup-manifest-v1.json)의2개 경로에 생성 전판을 보존했습니다. 커밋·푸시·배포·외부 메시지는 하지 않았습니다. 전체21개 완료 판정을 내리지 않았습니다.
'''
with REPORT.open('x', encoding='utf8') as f:
    f.write(report_text)
debug = CS / 'wiki/records/reports/debugs' / (TAG + '.md')
with debug.open('x', encoding='utf8') as f:
    f.write(f'''# 도보 거리의 정책 밖 근거가 사용 판정에 연결됨

## 해결됨 (2026-10-09, 부분) — 생성 원본과 새 판의 판정 정정

위치: scripts/mobility/build_readiness_visual.py:56의catalog도보거리행·v42도보거리카드. 제품밖30쌍의17/30원시거리진단이조건부사용근거로쓰였습니다. 제품공개0/30·정렬된새비교0개인상태에서사용범위를과장할위험입니다. 생성함수전후실행도보1행수정·나머지20행유지와새v43추가검증/전체3·9·9집계로판정부분을닫았습니다. 제품도보정확도·새웹확보·브라우저제어오류는미해결입니다. [보고서](../{REPORT.name})·[검증원문](../../evidence/{TAG}/catalog-validation-v1.json).
''')
features_html = ''.join(f'<article data-status="{escape(f["status"])}"><p class="tag">{escape(f["status"])}</p><h3>{escape(f["name"])}</h3><p>{escape(f["scope"])}</p><p class="metric">{escape(f["metric"])}</p><details><summary>근거와 더 필요한 것</summary><p>{escape(f["reason"])}</p><p>{escape(f["need"])}</p></details></article>' for f in cat['features'])
visual = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>이동 사용 판정 정정 v43</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f6f8fb;color:#193a56;font-family:'Malgun Gothic',sans-serif;line-height:1.65}}main{{max-width:1140px;margin:auto;padding:40px 24px}}h1{{font-size:32px;line-height:1.3}}h2{{margin-top:36px}}.lead{{font-size:20px}}.notice,article{{background:white;border:1px solid #d7e0e8;padding:20px;border-radius:8px}}.notice{{border-left:5px solid #a05a00}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px}}.tag{{font-size:14px;color:#126b67}}.metric{{font-weight:600}}label{{display:block}}select{{padding:10px;margin-top:6px;font:inherit;max-width:100%}}a,summary{{color:#126b67}}summary{{cursor:pointer}}[hidden]{{display:none!important}}table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{padding:12px;border-bottom:1px solid #d7e0e8;text-align:left}}svg{{display:block;max-width:100%;height:auto}}footer{{margin-top:32px}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}main{{padding:24px 16px}}h1{{font-size:26px}}}}
</style><main><p>triPilot / 서울 이동 / {NOW.isoformat()} / v43</p><h1>도보 거리의 사용 판정을 바로잡았습니다</h1><p class="lead">정책 밖 원시 비교로는 정책 안의 제품 정확도를 입증할 수 없습니다.</p><div class="notice">도보 거리: 조건부 사용 → 추가 검증. 제품 계산이나 허용 오차를 바꾼 결과가 아닙니다. 새 웹 경로는 화면 읽기 오류로0개입니다.</div>
<svg viewBox="0 0 800 180" role="img" aria-labelledby="flow-title flow-desc"><title id="flow-title">도보 제품 비교의 근거 순서</title><desc id="flow-desc">정책 밖30쌍 원시진단은 보존하지만 제품 사용 판정에서 제외합니다. 정책 안 같은 좌표의 새 웹 경로와 실제 제품 옵션을 대조해야 합니다.</desc><g font-family="Malgun Gothic,sans-serif" font-size="17" fill="#193a56"><rect x="10" y="20" width="245" height="120" fill="#eef4f8"/><text x="25" y="55">기존30쌍 · 정책 밖</text><text x="25" y="87">제품 공개0/30</text><text x="25" y="119">원시17/30만 보존</text><text x="270" y="88">→</text><rect x="305" y="20" width="245" height="120" fill="#fff1da"/><text x="320" y="55">정책 안 · 같은 출입점</text><text x="320" y="87">새 웹 확보0개</text><text x="320" y="119">화면 읽기 실패</text><text x="565" y="88">→</text><rect x="605" y="20" width="185" height="120" fill="#eef4f8"/><text x="620" y="55">제품 옵션 대조</text><text x="620" y="87">追加 검증 필요</text><text x="620" y="119">실보행도 별도</text></g></svg>
<h2>21개 기능의 분류</h2><p>조건부 사용3/21 · 개선 필요9/21 · 추가 검증9/21. 제품 준비율이 아닙니다. 다른20개 수치는 이전v42의 근거이며 이번에 재측정하지 않았습니다.</p><label for="filter">판정별 보기</label><select id="filter"><option value="all">전체21개</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><p id="visible" aria-live="polite">21/21개 표시</p><section class="grid">{features_html}</section><h2>연구를 적용하기 전에 확인할 것</h2><p>지도 예측과 실제 보행을 구분하고 원좌표·붙인 간선·경로 형상을 기록합니다. 광장 내부 연결은 실제 보행 가능 영역·장애물 자료를 확인한 뒤 검토합니다. 해외 연구 수치를 서울 보정 상수로 옮기지 않았습니다.</p><footer><a href="../../{REPORT.name}">보고서</a> · <a href="../../../evidence/{TAG}/acquisition-attempts-v1.json">조회 실패 기록</a> · <a href="../../../evidence/{TAG}/research-v1.json">연구·적용 전제</a> · <a href="../../../evidence/{TAG}/backup-manifest-v1.json">백업 명세</a> · <a href="../{PRIOR.name}/mobility-readiness.html">이전v42</a><p>새 웹·실보행·지도 개발자API0개/회. 브라우저 로컬파일 접근 차단으로 화면 렌더링은 이번에도 확인하지 않았습니다.</p></footer></main><script>const select=document.querySelector('#filter');select.addEventListener('change',()=>{{const cards=[...document.querySelectorAll('article')];cards.forEach(a=>a.hidden=select.value!=='all'&&a.dataset.status!==select.value);document.querySelector('#visible').textContent=cards.filter(a=>!a.hidden).length+'/21개 표시';}});</script></html>'''
visual = visual.replace('追加 검증 필요', '추가 검증 필요')
with (ASSETS / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(visual)
# 결과 결론만 정본에 추가하며 방금 기록한 계약도 전판을 백업합니다.
wiki_second_backup = WIKI.parent / '_backup' / (datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S') + '_도보판정_결과추가전') / WIKI.name
wiki_second_backup.parent.mkdir(parents=True)
shutil.copy2(WIKI, wiki_second_backup)
backups.append({'source': WIKI.relative_to(ROOT).as_posix(), 'backup': wiki_second_backup.relative_to(ROOT).as_posix(), 'sha256': sha(wiki_second_backup)})
WIKI.write_text(WIKI.read_text(encoding='utf8') + f'''\n\n## {TAG} 검증 결과

정책밖30쌍원시진단17/30을도보거리제품사용판정의근거에서분리해조건부사용→추가검증으로정정했습니다. 생성함수실행전후1행변경·나머지20/20유지,전체21분류3/9/9이며완료율이아닙니다. 지도웹두제공처의화면읽기시간초과로새경로0개·정렬제품비교0개·개발자API0회.2026-05-19GPS대조연구와광장보행연구의적용전제를보존했지만보정상수/제품계산을바꾸지않았습니다. [보고서](../records/reports/{REPORT.name})·[시각화v43](../records/reports/assets/{ASSETS.name}/mobility-readiness.html). 제품정확도·실보행·브라우저연결오류·전체21완료는남았습니다.
''', encoding='utf8')
# 명세를 고치기 직전 원본도 보존합니다.
manifest = EV / 'backup-manifest-v1.json'
manifest_backup = EV / '_backup' / (NOW.strftime('%Y-%m-%d_%H%M%S') + '_최종백업명세전') / manifest.name
manifest_backup.parent.mkdir(parents=True)
shutil.copy2(manifest, manifest_backup)
manifest.write_text(json.dumps({'created_at': NOW.isoformat(), 'backups': backups,
    'prior_manifest_backup': manifest_backup.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2), encoding='utf8')
assert all(sha(ROOT / x['backup']) == x['sha256'] for x in backups)
source = dict(prior_proof['source_test_data_hashes'])
source[BASE.relative_to(ROOT).as_posix()] = sha(BASE)
assert all(sha(ROOT / p) == h for p, h in source.items())
assert all(sha(ROOT / p) == h for p, h in prior_proof['artifact_hashes'].items() if p != WIKI.relative_to(ROOT).as_posix())
save(EV / 'verification-proof-v1.json', {'created_at': NOW.isoformat(), 'source_test_data_hashes': source,
    'owned_changed_source': [BASE.relative_to(ROOT).as_posix()], 'source_hash_matches': len(source),
    'previous_artifacts_preserved_except_wiki_append': len(prior_proof['artifact_hashes']) - int(WIKI.relative_to(ROOT).as_posix() in prior_proof['artifact_hashes']),
    'feature_count': 21, 'unchanged_feature_rows': 20, 'counts': cat['counts'],
    'runtime_changes': 0, 'new_web_observations': 0, 'full_feature_completion': False})
shutil.copy2(Path(__file__), EV / Path(__file__).name)
files = [*EV.iterdir(), *ASSETS.iterdir(), REPORT, debug, WIKI]
save(EV / 'publication-integrity-v1.json', {'created_at': NOW.isoformat(),
    'artifact_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in files if p.is_file()},
    'report': REPORT.relative_to(ROOT).as_posix(), 'assets': ASSETS.relative_to(ROOT).as_posix(),
    'evidence': EV.relative_to(ROOT).as_posix(), 'browser_render_checked': False})
print(json.dumps({'report': REPORT.relative_to(ROOT).as_posix(), 'evidence': EV.relative_to(ROOT).as_posix(),
                  'counts': cat['counts'], 'source_hashes': len(source), 'backups': len(backups)}, ensure_ascii=False))
