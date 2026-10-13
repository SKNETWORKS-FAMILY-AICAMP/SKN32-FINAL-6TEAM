"""Current-version review report; v1 measurements and documents remain unchanged."""
from pathlib import Path
import datetime,html,json,shutil
from build_documents_v2 import CSS,table
HERE=Path(__file__).resolve().parent
def read(name,default=None):
 p=HERE/name
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else (default or {})
P=read('project-manifest-v2.json');C=read('checks/project-checks-v2.json')
A=read('checks/document-audit-v2.json');R=read('checks/render-audit-v2.json');D=read('checks/diagram-audit-v2.json');Q=read('checks/print-audit-v2.json')
rows=[]
for label,passed,total in [('原문·링크·현재 정책 대조',A.get('document_passed',0),A.get('document_total',28)),('PC·휴대폰 문서 렌더링',R.get('passed',0),R.get('total',4)),('그림 접근성·단일 파일',D.get('passed',0),D.get('total',4)),('인쇄 본문 확인',Q.get('passed',0),Q.get('total',2))]:
 rows.append([label.replace('原문','원문'),f'{passed}/{total} = {100*passed/total:.0f}%'])
state=A.get('state_observations',[{}])[0].get('detail',{})
drift=state.get('changed_paths',[])
body=f'''<h1>현재 버전 반영·재검토 기록 v2</h1>
<p class="lead">선택 동의·이동 경로 자료·웹 검토 동작을 현재 코드와 문서에 맞춰 갱신했습니다.</p>
<p>기준선 ID: {P['id']} · 관측 시각: {P['captured_at_kst']} · 작성·검수: Codex. 팀 채택과 제품 출시 판정은 별도입니다.</p>
{table(['문서 검사','결과'],rows)}
<h2>무엇을 반영했나</h2>
<p>첫 대조에서 이전 수집 범위 1,302개와 같은 방식으로 읽은 현재 1,308개 사이의 변경 경로 29개를 확인했습니다. 현재 명세는 운영 문서·서비스 개선 CLI·Saluki 학습 계획·웹 의존성 잠금 파일도 추가해 {P['file_count']:,}개를 식별합니다. 명세의 추가 경로에는 새로 관측 범위에 넣은 기존 파일이 포함되므로 전부 새 구현으로 세지 않습니다.</p>
{table(['반영한 내용','본문 처리'],[
['서비스 개선 선택 동의','약관 2026-10-10.1·필수/선택 6항목·읽는 자료·합성 후보·사람 검토/철회/기간·운영 미확인 명시'],
['차량 회전 자료 내용 교체','같은 크기·수정시각이어도 내용 해시로 재검사. 기존 범위·도로 그래프 자체의 교체 한계 유지'],
['웹 동의·지도·전체 복원','변경 관련 6개 파일의 단위 시험을 재실행하고 실제 제품 화면 검증과 구분'],
['학습 기준','기존 학습 자료 2,613행·해시와 정확한 모델/계획을 재대조. 서비스 개선 합성본과 질의 학습판의 목적을 분리'],
['기존 실패·책임 공백','현재 직접 의존 실패 2개와 미배정 책임·D-018 draft·독립 정답 검수를 숨기지 않고 관문으로 유지']])}
<h2>제품 관련 실행 증거</h2>
{table(['범위','실측 결과','해석'],[
['공통 계약·구조 4파일','236/238 = 99.16% · 실패 2','백업 1경로와 현행 Mobility 1경로의 직접 import 검사 실패'],
['새 기능 단위 2파일','81/81 = 100%','서비스 개선 76개, 회전 파일 내용 교체 5개. DB/운영 자료 추출 미실행'],
['관련 웹 단위 6파일','52/52 = 100%','함수 대역·정적 렌더링을 포함한 단위 검사. 실제 브라우저·API/DB 전체 동작 아님'],
['분류 자료 구조 검사','96/96 = 100%','golden72+holdout24, 전부 claude-draft. 모델 정확도·사람 검수·독립성 아님']])}
<p>백엔드 두 묶음의 합계는 317/319 = 99.37%입니다. 전체 제품 시험의 통과율이 아닙니다. v1의 235/238과는 수집 항목·파일이 달라 증감으로 성능을 비교하지 않습니다. 이전 개인정보 DB 시험에는 쇼핑몰 분류 fixture가 있어 이번 여행 검증에서 제외했습니다. 이번 판의 DB/API 개인정보 확인은 미실행입니다.</p>
<p>mock 서버 시험: 실행하지 않았습니다.<br>실서버 확인(서버 응답): 안 했습니다. x600 서버의 cs 프로젝트 서버·외부 API·GPU 모델·실제 고객 화면·전체 MVP 18항목은 이번 갱신에서 재검증하지 않았습니다.</p>
<h2>검토·수정 과정</h2>
<ol><li>현재 차이와 정책을 다시 읽고 관측 시각·범위·명세를 갱신했습니다. v1과 v11은 보존했습니다.</li>
<li>상품 요구와 로컬 구현, 동의 표시와 실제 검토, 데이터 생성과 모델 학습 허가를 구분했습니다. 이전 DB 오류가 현재 결과처럼 남아 있던 문구와 Mobility 세부 판 이름을 수정했습니다.</li>
<li>현재 수치·링크·정책·화면·그림·인쇄를 재검사하고 최종 결과를 이 보고서에 연결했습니다.</li></ol>
<p>새 백엔드 첫 실행은 76통과·임시 폴더 생성 오류5였으며 쓰기 가능한 새 시험 폴더를 지정해 81/81 통과했습니다. 웹 첫 실행은 28통과 후 2개 파일이 임시 SSR 파일을 찾지 못했고, 단일 threads 작업자로 6파일 전체를 재실행해 52/52 통과했습니다. 첫 실행의 원본도 백업에 보존했습니다. 이 오류를 제품 동작 결함으로 단정하지 않습니다.</p>
<h2>최종 시점 대조</h2>
<p>v2 명세와 최종 대조에서 다른 경로는 {len(drift)}개입니다. <a href="checks/document-audit-v2.json">경로·집합 해시·대조 결과</a>를 확인하십시오. 이후 편집이 생기면 같은 상태임을 다시 확인해야 합니다. 해시 명세는 코드 전체 백업이나 운영 DB·모델 복제본이 아닙니다.</p>
<h2>파일과 근거</h2><ul>
<li><a href="triPilot-baseline-v2.html">현재 기준선 v2</a> · <a href="baseline-writing-guide-v2.html">작성법 v2</a></li>
<li><a href="project-manifest-v2.json">현재 파일·모델 계획·자료 명세</a> · <a href="source-manifest.json">참고자료 11개 원문 명세</a></li>
<li><a href="checks/project-checks-v2.json">실행 명령·실측·재시도·한계</a> · <a href="checks/base-backend-v2.xml">공통 시험 원본</a> · <a href="checks/changes-backend-v2.xml">변경 시험 원본</a> · <a href="checks/frontend-v2.json">웹 시험 원본</a></li>
<li><a href="checks/document-audit-v2.json">문서 대조</a> · <a href="checks/render-audit-v2.json">렌더링</a> · <a href="checks/diagram-audit-v2.json">SVG 검사</a> · <a href="checks/print-audit-v2.json">인쇄 본문 검사</a></li>
<li><a href="triPilot-baseline-v1.html">이전 v1</a> · <a href="review-report.html">이전 검수 기록</a> · <a href="_backup/">수정 전 원본과 실행 오류 백업</a></li></ul>
<p class="small">단독 그림 검사에는 SVG를 추출해 적용했고 외부 인용 링크·외부 리소스 요청은 문서 검사로 따로 확인했습니다. 출처 11개 사본과 해시는 재사용했으며 이번 갱신에서 새로운 웹 자료를 받은 것은 아닙니다. HTML의 프로젝트 근거 링크는 기존 작업 폴더 구조가 필요합니다.</p>'''
doc='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>현재 버전 반영·검수 v2</title><style>'+CSS+'main{max-width:1000px;margin:auto;padding:48px 24px}h2{margin-top:40px}</style></head><body><main>'+body+'</main></body></html>'
p=HERE/'review-report-v2.html'
if p.exists():
 b=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_review_v2');b.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b/p.name)
p.write_text(doc,encoding='utf-8');print(p.name)
