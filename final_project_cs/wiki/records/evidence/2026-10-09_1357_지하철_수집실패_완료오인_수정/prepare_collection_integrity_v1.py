from pathlib import Path
from datetime import datetime
import json, hashlib, shutil

ROOT = Path(__file__).resolve().parents[2]
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_지하철_수집실패_완료오인_수정'
ev = ROOT / 'final_project_cs/wiki/records/evidence' / tag
ev.mkdir()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
prior = ROOT / 'final_project_cs/wiki/records/evidence/2026-10-09_1343_공항철도_공표승차시간_대조/final-integrity-v1.json'
doc = json.loads(prior.read_text(encoding='utf8'))
(ev/'prior-manifest-v1.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf8')
backups=[]
for rel in ['datasets/mobility/scripts/tago_subway_collect.py', 'datasets/mobility/scripts/tago_retry_empty.py',
            'datasets/mobility/scripts/README.md', 'datasets/mobility/REPORT.md', 'final_project_cs/wiki/teams/mobility.md']:
    p=ROOT/rel; b=p.parent/'_backup'/tag/p.name; b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p,b)
    backups.append({'path':rel,'backup':str(b.relative_to(ROOT)), 'sha256':sha(p)})
(ev/'backup-manifest-v1.json').write_text(json.dumps(backups,ensure_ascii=False,indent=2),encoding='utf8')
wiki=ROOT/'final_project_cs/wiki/teams/mobility.md'
with wiki.open('a',encoding='utf8') as f:
    f.write(f'\n\n## {tag} 수집 성공과 빈 시간표의 구분 계약\n\nTAGO 수집과 빈 조합 재조회는 HTTP 성공만으로 완료/빈 자료를 확정하지 않습니다. 공통 검사에서 정상 결과코드·응답 구조·전체 건수·페이지 번호/크기·모든 페이지 행수를 검증한 뒤 반환합니다. 실패는 비밀값/응답본문 없는 명시적 오류이며 기본 수집은 완료 체크포인트에 넣지 않고 중단합니다. 재조회는 오류 상태를 보존하며 ok 빈 자료로 분류하지 않습니다. 제공처 원문 행은 raw_item에 별도로 보존하되 열차번호·종류를 추정하지 않습니다. 기존 완료 표의 잘못된 항목과 이미 가공된 시간표는 자동 삭제/교체하지 않습니다. 현재 DATA_DIR 미설정 환경에서 전체 수집/가공을 실행하지 않습니다.\n')
debug=ROOT/'final_project_cs/wiki/records/reports/debugs'/f'{tag}.md'
debug.write_text('# 지하철 API 오류가 빈 시간표 완료로 남는 수집 결함\n\n## 미해결\n\n기본 수집 call이 HTTP200 본문의 결과코드를 확인하지 않고 body를 반환하며, 실패 때도 빈 dict를 반환합니다. 호출부는 빈 목록을 만든 뒤 done에 넣습니다. 재조회도 HTTP200 오류 body를 ok로 분류합니다. 첫 페이지만 받아 전체 건수 초과를 감지하지 않습니다.\n\n위치: datasets/mobility/scripts/tago_subway_collect.py:22,70,81 · tago_retry_empty.py:22,33. API 실패가 성공 빈 자료로 남아 재수집 대상에서 빠질 위험입니다. 이미 저장된 시간표의 누락 규모는 원자료/체크포인트 미확보로 아직 세지 못했습니다. 공식 명세: https://www.data.go.kr/data/15098554/openapi.do (2026-10-09 조회), 오류코드와 페이지 분할을 구분합니다. 재현과 수정 검증은 같은 시각 evidence 폴더에 보존합니다.\n',encoding='utf8')
state={'tag':tag,'evidence':str(ev.relative_to(ROOT)),'debug':str(debug.relative_to(ROOT)),'prepared_at':now.isoformat()}
(Path(__file__).parent/'collection-integrity-state-v1.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(state,ensure_ascii=False))
