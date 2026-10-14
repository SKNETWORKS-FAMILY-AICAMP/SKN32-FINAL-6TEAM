"""Assemble the local review record from measured check outputs."""
from pathlib import Path
import datetime, html, json, shutil
from build_documents import CSS, table
HERE=Path(__file__).resolve().parent
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
audit=read('checks/document-audit.json') if (HERE/'checks/document-audit.json').exists() else {}
render=read('checks/render-audit.json') if (HERE/'checks/render-audit.json').exists() else {}
print_check=read('checks/print-audit.json') if (HERE/'checks/print-audit.json').exists() else {}
diagram=read('checks/diagram-audit.json') if (HERE/'checks/diagram-audit.json').exists() else {}
state=audit.get('state_observations',[{}])[0].get('detail',{})
rows=[]
for label,data,passed,total in [
 ('원문·링크·문서 구조',audit,audit.get('document_passed',0),audit.get('document_total',25)),
 ('PC·휴대폰 렌더링',render,render.get('passed',0),render.get('total',4)),
 ('그림 접근성·단일 파일 검사',diagram,diagram.get('passed',0),diagram.get('total',4)),
 ('인쇄 본문 확인',print_check,print_check.get('passed',0),print_check.get('total',2))]:
 rows.append([label,f'{passed}/{total} = {passed/total*100:.0f}%','문서 검수. 제품 합격률이 아님'])
body=f'''<h1>기준선 작성·검수 기록</h1><p class="lead">출처와 프로젝트 관측을 대조하고, 내용·화면·인쇄를 수정한 검수 기록입니다.</p>
<p>작성일: 2026-10-10 KST · 검수: Codex 자체 검수. 팀원 독립 검토나 팀 채택으로 세지 않습니다.</p>
{table(['검사 묶음','완료','범위'],rows)}
<h2>검토와 수정 3회</h2>
{table(['회차','확인한 문제·차이','수정·처리'],[
 ['1. 근거·현황 대조','다운로드 범위 표기의 언어, 검수 보고서 연결 누락, 수집 뒤 코드 변경, AI 초안 표시','한국어 범위 표기·보고서 연결·이후 변경 주의문·AI 라벨 명시. 원문 11개 SHA-256 및 PDF 쪽 수 대조'],
 ['2. 화면·인쇄 대조','휴대폰 제목의 한 글자 줄바꿈, 접힌 상세 본문이 인쇄에서 빠짐','단어 단위 줄바꿈, 상세 본문 상시 표시, 작은 화면 그림의 좌우 접근 안내. 실제 PC·휴대폰 화면 및 흐름·구조 그림 확인'],
 ['3. 수정 후 재검사','원문·로컬 링크·중복 ID·오프라인·SVG·MVP 번호와 인쇄 내용','자동 검사와 실제 렌더링 재실행. 최종 수치는 위 표와 아래 기계 판독 파일에 기록']])}
<h2>현재 작업 상태 관측은 별도입니다</h2>
<p>처음 고정한 파일 목록은 1,302개입니다. 최종 대조에서는 {len(state.get('changed_paths',[]))}개 경로가 달라졌습니다. 원래 명세를 최신 상태처럼 덮어쓰지 않았습니다. 기준선 본문에 수집 시점과 이후 변경의 차이를 밝혔으며, 제품 시험 결과를 이후 변경의 통과 증거로 사용하지 않습니다.</p>
<p>이는 문서 링크 오류가 아니라 진행 중인 작업의 관측입니다. 정확한 채택 커밋·Git 밖 자료·모델과 재현 기록은 팀 채택 관문에 남겼습니다. 이 작업에서 코드·환경·제품 배포를 수정하지 않았습니다.</p>
<h2>제품 확인의 범위</h2>
<p>선택한 제품 시험 238개 중 235개 통과, 2개 실패, 1개 로컬 개발 DB 접속 오류였습니다. 실패 2개 중 하나는 백업 경로, 하나는 현행 Mobility 코드의 직접 import 검사입니다. 넓은 시험 묶음은 중단돼 전체 통과율이 없습니다.</p>
<p>mock 서버 시험: 실행하지 않았습니다.<br>실서버 확인(서버 응답): 안 했습니다. x600 서버의 cs 프로젝트 서버·외부 API·GPU 모델은 이 문서 작업에서 재검증하지 않았습니다.</p>
<p>여행 분류 자료 72+24=96건은 형식 검사 통과이며 전부 claude-draft입니다. 사람 정답 검수나 모델 정확도 측정으로 표시하지 않았습니다.</p>
<h2>출처와 검사 증거</h2>
<ul><li><a href="triPilot-baseline-v1.html">프로젝트 기준선 한 파일</a> · <a href="baseline-writing-guide.html">베이스라인 작성법</a></li>
<li><a href="source-manifest.json">참고자료 11개 주소·SHA-256·다운로드 범위</a> · <a href="project-manifest.json">프로젝트 관측 파일 목록</a></li>
<li><a href="checks/document-audit.json">원문·문서 검사 및 상태 변경 경로</a> · <a href="checks/render-audit.json">PC·휴대폰 렌더링 기록</a> · <a href="checks/print-audit.json">인쇄 본문 검사</a> · <a href="checks/diagram-audit.json">SVG 검사</a></li>
<li><a href="checks/project-checks.json">제품 선택 시험 결과·실행 명령·한계</a></li>
<li><a href="checks/screens/triPilot-baseline-v1-desktop.png">기준선 PC 화면</a> · <a href="checks/screens/baseline-writing-guide-mobile.png">작성법 휴대폰 화면</a> · <a href="checks/screens/triPilot-baseline-v1-flow-desktop.png">채택 흐름 그림</a></li>
<li><a href="_backup/">수정 전 원본 백업</a></li></ul>
<p class="small">그림 스킬의 단독 그림용 검사는 외부 인용 링크까지 차단합니다. 공식 출처 링크가 필요한 문서 전체에서는 그 검사를 그대로 합격 처리하지 않았습니다. 각 HTML에서 SVG를 추출해 그림 검사를 적용하고, 문서의 외부 리소스 요청·출처 링크는 별도 검사했습니다.</p>
<h2>다운로드·공유 범위</h2><p>공개 PDF 3개와 공개 웹 원문 8개를 받았습니다. SCM Patterns는 출판사가 공개한 소개·목차·서문 페이지이며 유료 책 전문이 아닙니다. IEEE 828 원문 전문도 확보한 것으로 표시하지 않았습니다. 참고자료의 전체 권리를 우리에게 이전한 것은 아니므로 이번 로컬 열람용 원문 사본을 공개 저장소에 올리지 않았습니다.</p>
<p>기준선 HTML 자체는 외부 리소스 없이 열립니다. 프로젝트 근거 링크까지 열려면 기존 작업 폴더 구조가 필요합니다. 팀에 전달할 때는 같은 저장소 접근 권한과 정확한 채택 버전을 연결하십시오. 문서 폴더만 전달한다고 코드·모델·DB까지 재현되는 것은 아닙니다.</p>'''
doc='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>기준선 작성·검수 기록</title><style>'+CSS+'main{max-width:1000px;margin:auto;padding:48px 24px}h2{margin-top:40px}</style></head><body><main>'+body+'</main></body></html>'
target=HERE/'review-report.html'
if target.exists():
 b=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_review');b.mkdir(parents=True,exist_ok=True);shutil.copy2(target,b/target.name)
target.write_text(doc,encoding='utf-8')
print(target.name)
