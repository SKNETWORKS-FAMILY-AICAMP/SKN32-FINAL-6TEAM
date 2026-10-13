"""이전 판을 보존하고 자동 출발 안내의 코드 조립 근거를 새 판으로 연결한다."""
from pathlib import Path
from datetime import datetime
from copy import deepcopy
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v10'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v11'

def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    OUT.mkdir(exist_ok=False)
    for path in OLD.iterdir():
        if path.is_file() and path.name not in ('mobility-readiness.html', 'readiness-catalog.json'):
            shutil.copy2(path, OUT/path.name)
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['departure_assembly'] = proof
    catalog['features'][15]['need'] = ('자동 알림 코드 조립·현재 일정 장소·기존 소스 캐시 연결을 검증했다. '
        '옛 문맥/직접도보 재경로·늦음 Case 전달·탑승 중 갱신·운영 계측·실제 도착 대조가 남음.')
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as out:
        json.dump(catalog, out, ensure_ascii=False, indent=2)
    section = f'''<section><h2>자동 출발 안내 작업에 현재 관측을 연결했습니다</h2>
<p>이번 조립·로컬 DB·기존 구성 시험44/44, 확대 회귀{proof['regression_passed']}/{proof['regression_passed']} 통과입니다.
직전 판의 시험 수와 합산하지 않습니다. 현재 일정의 방문 장소 좌표이며 고객의 GPS 위치 측정은 아닙니다.</p>
<table><thead><tr><th>연결 구간</th><th>확인한 결과</th><th>남은 범위</th></tr></thead><tbody>
<tr><th>출발 작업→팀 재검증</th><td>기존 끼움 자리로 현재 옵션·장소·목표시각 전달</td><td>옛 문맥·직접 도보의 새 경로 확보</td></tr>
<tr><th>도착 소스→정확 승차</th><td>실제 어댑터에 응답을 주입한2회 관측에서 HTTP1회</td><td>실제 운행 정확도·신선도 정책 계측</td></tr>
<tr><th>재검증→로컬 DB 안내</th><td>10회 확인에서 관측1회·발행1회, 지연은 발행0회</td><td>보류 결과→실제 일정 재조정</td></tr></tbody></table>
<p>자료 나이90초·미래폭2초는 설정에 둔 잠정 운영 정책입니다. 서울 API 정확도 보장이 아닙니다.
조회가 예측을 못 내면 현재 모델로 다시 계산했다는 근거를 남깁니다. 모델도 값을 못 내면 치명 상태이며 낡은 안내를 내지 않습니다.</p>
<p><strong>배포된 cs 프로젝트 서버의 안내·실제 탑승은 미확인입니다.</strong>
전체21기능 완료를 선언하지 않습니다.</p>
<p><a href="../../{proof['report']}">최신 조립 보고서·백업·실행 근거</a></p></section>'''
    text = (OLD/'mobility-readiness.html').read_text(encoding='utf8')
    text = text.replace('v10', 'v11')
    text = text.replace('<section>', section+'<section>', 1)
    text = text.replace('<strong>운영 연결은 남았습니다.</strong> 실제 자동 알림 일꾼에 소스·정책·팀 콜백을 조립하고,',
        '<strong>직전 판에서 남았던 운영 코드 조립은 이번 판에서 검증했습니다.</strong> 실제 고객 운행 검증과,')
    text = text.replace('실제 버스 도착정보를 안내에 연결하는 작업은 남아 있습니다.',
        '도착정보 소비의 코드 조립과 로컬 DB 안내는 이번 판에서 확인했고 실제 고객 운행 검증은 남아 있습니다.')
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as out:
        out.write(text)
    print(json.dumps({'features': len(catalog['features']), 'output': str(OUT)}, ensure_ascii=False))

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
