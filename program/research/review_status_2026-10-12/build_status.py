"""Save the reviewed W01-W25 status without rewriting historical findings."""
import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'program/research/wiki_review_2026-10-11/findings-v2.json'
findings = json.loads(SOURCE.read_text(encoding='utf-8-sig'))['findings']
# Documentation acceptance is distinct from implementation and deployment.
rows = [
('W01','wiki를 현재 사양 정본으로 지정','문서 반영 완료','작업 규칙·문서 입구 정정','추가 기능 작업 대상 아님'),
('W02','고객 웹·개인 AI·공유 계획서 역할','문서 반영 완료','세 경로의 역할·권한 계약 정리','각 경로의 구현·권한·연결 시험'),
('W03','항로 지킴이 자동 변경','문서 반영 완료','켜짐/꺼짐·고정 일정·재개 조건 정리','자동 적용·알림·기존 설정 호환성 검증'),
('W04','개인 AI OAuth 로그인·동의','B안 확정','이번 범위에 OAuth 구현 포함','OAuth 구현·연결·권한 시험'),
('W05','상주 상담원 없는 자동 운영','문서 반영 완료','고객 보완 입력·개발자/QA 사후 분석 정리','고객 화면·오류 기록·복구 경로 구현 대조'),
('W06','실패한 조회에 의존하는 작업만 보류','문서 반영 완료','정상 기능 유지·복구 계약 정리','장애 격리·자동 복구·고객 안내 인수 시험'),
('W07','모니터링 툴 간격과 자료 최신성','용어·문서 수정 완료','모니터링 툴로 명칭 통일·지연 구분','자료별 실제 지연 측정'),
('W08','분류 에이전트의 팀·순서·우선순위 결정','책임 문서 수정 완료','Activity 조정 설명 철회·현재 코드 차이 확인','분류 모델 기반 실행 계획·다중 팀 처리 구현'),
('W09','무료 자료 우선·검증 불가 표시·설정','요구사항 반영 완료','무료 우선 정책과 운영자 웹앱 설정 요구 기록','설정 저장·자료 조회 정책 연결 구현'),
('W10','여행 평가 안내로 교체','문서 반영 완료','쇼핑몰 평가와 현재 여행 평가 분리','추가 문서 작업 대상 아님'),
('W11','v11 보존·wiki 기반 v12 신규 작성','v11 보존 반영','v11은 과거 기록으로 유지','전체 정리 후 v12 안내서·최종 베이스라인 작성'),
('W12','에이전트 팀의 허용 도구 조회 범위','문서 반영 완료','권한·도구 목록·예산·근거·쓰기 경계 정리','전체 도구 호출 경로 구현·권한 시험'),
('W13','공통 시험과 여행 시험 분리','C안 구현·부분 검증','실행 목록·분리 실행기·여행 자료 반영','공통/여행 전체 시험 각각 실행'),
('W14','DB 구조·옛 표 삭제·재생성 방지','양쪽 DB 정리 완료','백업·복원 시험·5표 삭제·이미지·wiki 갱신','SQL 실행·향후 배포 안전 문제는 후속 세션'),
('W15','모델 판본표와 독립 실험 보고서','문서·목록 반영 완료','현재 평가 절차·기존 보고서 52개 링크 연결','실제 채택 모델·환경별 적용 증거 확인'),
('W16','기능별 책임과 디렉토리 경계','디렉토리 경계 반영·기능 책임 설계','실제 배치 유지·기능 책임표는 설계안','미확정 상시 담당자 배정·강제 검토는 미적용'),
('W17','현재 일정과 과거 주차표 분리','문서 반영 완료','현재 제출 일정과 과거 작업 이력 분리','추가 문서 작업 대상 아님'),
('W18','환경별 앱·DB·모니터링·모델 구분','문서 반영 완료','대상 기계·앱·확인 시점을 구분','모든 구성 요소의 현재 정상 동작 검증은 별도'),
('W19','datasets 전체 Git 제외 안내','문서 반영 완료','기존 제외 규칙으로 안내 통일·DB 백업 제외 확인','추가 문서 작업 대상 아님'),
('W20','결정·구현·검증·배포 상태 분리','기준·일부 적용','OAuth·장애 대응 결정에 상태 예시 적용','전체 wiki 적용은 미완료'),
('W21','깨진 링크 3개 수정','수정·검사 완료','확인된 잘못된 링크 3개 교체','추가 수정 대상 확인되지 않음'),
('W22','wiki 검사 범위 구분','검사기 구현·검증 완료','현재·생성 문서 301개 검사: 위반 0개','기록 본문·백업은 기본 검사 범위 밖'),
('W23','불변식 목록 수 자동 집계','자동 집계·검사 반영','현재 cs 생성 목록 70개 집계','집계 수를 시험 통과 수로 해석하지 않음'),
('W24','ODsay 제품 미사용·별도 연구 구분','문서 반영 완료','제품 도입과 독립 연구 범위 구분','연구의 실제 사용·저장·약관 적합성 확인은 별도'),
('W25','현재 계약 먼저·과거 이력은 근거 링크','기준·대상 문서 반영','현재 본문과 과거 기록 분리·근거 링크 유지','모든 wiki 본문의 의미 검토 완료를 뜻하지 않음'),
]
assert len(rows) == 25 and [r[0] for r in rows] == [f['id'] for f in findings]
result = []
for row, finding in zip(rows, findings):
    record = dict(zip(['id','subject','status','reflected','remaining'],row))
    record['selection'] = finding.get('selected') or 'v11 보존·v12 신규 작성 지시'
    evidence=[]
    for target in finding.get('targets',[]):
        path=ROOT / target
        evidence.append({'path':target,'exists':path.is_file(),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    record['evidence']=evidence
    result.append(record)

snapshot={
    'captured_at':datetime.now().astimezone().isoformat(),
    'scope':'W01-W25 결정·문서 반영 현황과 기존 실행 증거 대조. 전체 제품 기능의 신규 인수 시험 아님.',
    'source':str(SOURCE.relative_to(ROOT)),
    'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'rows_checked':len(result),
    'warning':'원래 findings의 completion_evidence에는 이전 시점 설명도 남아 있습니다. 현재 SQL 상태는 2026-10-12 실측 자료를 우선합니다.',
    'follow_up':{'thread_id':'01a12c3a-2ab8-7d10-9c24-37a21a994c1d',
                 'title':'SQL 실행 원자성·배포 안전장치 개선',
                 'status':'새 세션 실제 작업 시작 확인. 수정·시험 완료 전.',
                 'issues':['명시적 COMMIT이 전체 SQL 롤백을 깨뜨릴 수 있음',
                           '배포 시 Compose 추가 설정 누락에 따른 과거 표 재생성 위험',
                           '이미지 식별값 사전 확인·배포 시간 초과 복구 개선']},
    'items':result,
}

def link(target,label):
    import os
    rel=os.path.relpath(ROOT/target,OUT).replace('\\','/')
    return f'<a href="{html.escape(rel,quote=True)}">{html.escape(label)}</a>'

table=''.join('<tr>'+''.join(f'<td>{html.escape(r[k])}</td>' for k in ['id','subject','status','reflected','remaining'])+'<td>'+''.join(link(e['path'],e['path'])+'<br>' for e in r['evidence'] if e['exists'])+'</td></tr>' for r in result)
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>guguroute · 25개 반영 현황 · 2026-10-12</title>
<style>body{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 system-ui,sans-serif}main{max-width:1600px;margin:auto;padding:32px 24px}h1{font-size:30px}h2{font-size:21px}p{max-width:1000px}.notice{border-left:4px solid #a8720c;background:#f7f2e7;padding:14px 20px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:1000px;font-size:14px}th,td{padding:12px;border:1px solid #cbd2df;vertical-align:top;text-align:left}th{background:#eee9df}td:last-child{font-size:12px;min-width:240px;overflow-wrap:anywhere}a{color:#765000}li{margin:8px 0}small{color:#586277}a:focus-visible{outline:3px solid #a8720c;outline-offset:3px}</style>
<main><small>guguroute · 현재 기준 대조 · 2026-10-12</small><h1>25개 항목의 반영 현황</h1>
<p class="notice">25/25 항목의 상태를 정리했습니다. 문서 수정 완료와 기능 구현·검증·배포 완료는 구분합니다. 아래는 현재 파일과 기존 실행 증거를 대조한 보고이며 제품 전체를 새로 시험한 결과가 아닙니다.</p>
<p>현재 제품 사양은 wiki의 확정 결정·계약입니다. v11은 보존하며, v12 안내서와 최종 베이스라인은 아직 작성 완료하지 않았습니다.</p>
<div class="scroll"><table><thead><tr><th>항목</th><th>대상</th><th>반영 상태</th><th>반영한 내용</th><th>남은 작업·확인 범위</th><th>관련 현재 파일</th></tr></thead><tbody>'''+table+'''</tbody></table></div>
<h2>DB 정리의 실제 확인 범위</h2><p>로컬 개발 DB는 96→91표, x600 서버의 cs 프로젝트 DB는 92→87표입니다. 삭제 대상 5표는 양쪽에서 최종 0개입니다. 삭제 대상 밖의 표·열·제약·인덱스·트리거 구조는 전후 차이 0개이며 여행 핵심 6표의 내용 해시가 양쪽에서 유지됐습니다. 다른 이름의 같은 업무 자료·JSON 값 전체까지 모두 검사한 결과는 아닙니다.</p>
<p>관련 시험은 29/29 통과했습니다. 전체 시험 묶음이나 실제 고객 거래 시나리오를 실행했다는 뜻은 아닙니다. 로컬 실제 업무 DB의 추가 전체 SQL 재실행은 자동 승인 검토가 거절하여 실행하지 않았습니다. 복원한 격리 DB에서는 환경별 2회 재실행을 확인했습니다.</p>
<p>'''+link('program/research/sql_retirement_2026-10-12/index.html','현재 DB 구조·이미지·검사 결과')+' · '+link('program/research/sql_retirement_2026-10-12/summary.json','환경별 실측 데이터')+'''</p>
<h2>새 세션에서 시작한 추가 개선</h2><p>SQL 실행 원자성·배포 안전장치 개선 — 작업 지시 전달 완료. 결과는 새 세션에서 별도 보고합니다.</p>
<ol><li>SQL 실행 도중 실패했을 때 앞서 실행한 변경도 모두 취소되는지 검증하고 수정합니다.</li><li>다음 배포에서도 과거 표 재생성 방지 설정이 빠지지 않도록 검사·차단 장치를 보완합니다.</li><li>배포 전 사용할 이미지를 확인하고 시간 초과·부분 실패의 복구 절차를 보완합니다.</li></ol>
<p>새 세션은 로컬 수정·격리 DB 시험·배포안 준비를 진행합니다. 현재 보고서 시점에는 추가 수정이나 배포가 완료된 상태가 아닙니다.</p>
<p>'''+link('final_project_cs/wiki/data/migrations.md','SQL 적용 계약과 알려진 한계')+'''</p><small>원본 검토 자료에는 이전 시점 설명이 함께 남아 있으므로 현재 DB 상태는 2026-10-12 실측 자료를 우선합니다. 새 파일로 저장하여 기존 검토 자료를 덮어쓰지 않았습니다.</small></main></html>'''

page=page.replace('작업 지시 전달 완료. 결과는 새 세션에서 별도 보고합니다.','실제 작업 시작을 확인했습니다. 결과는 새 세션에서 별도 보고합니다.')
for name,body in [('status.json',json.dumps(snapshot,ensure_ascii=False,indent=2)),('index.html',page)]:
    path=OUT/name
    if path.exists():
        backup=OUT/'_backup'/datetime.now().strftime('%Y-%m-%d_%H%M%S_status')
        backup.mkdir(parents=True,exist_ok=True)
        import shutil
        shutil.copy2(path,backup/name)
    path.write_text(body,encoding='utf-8')

validation={'rows':len(result),'unique_ids':len({r['id'] for r in result}),
            'evidence_paths':sum(len(r['evidence']) for r in result),
            'missing_evidence_paths':[e['path'] for r in result for e in r['evidence'] if not e['exists']],
            'html_rows':page.count('<tr>')-1,'source_preserved':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==snapshot['source_sha256']}
assert validation['rows']==validation['unique_ids']==validation['html_rows']==25
assert validation['source_preserved']
(OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False))
