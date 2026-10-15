"""Build the decision review. Changes here are plans, not product implementation."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape as h
import json, os, hashlib, shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STAMP = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
OLD = json.loads((OUT/'findings-v1.json').read_text(encoding='utf-8'))['findings']
PLANS = []

def add(id, title, decision, options, steps, replacement, checks, targets=None, basis=None, fixed=False):
    old = next(x for x in OLD if x['id'] == id)
    PLANS.append(dict(id=id, title=title, decision=decision, options=[dict(id=c, title=t, effect=e, recommended=c=='A') for c,t,e in options], steps=steps, replacement=replacement, checks=checks, targets=targets or list(dict.fromkeys(e['path'] for e in old['evidence'])), basis=basis or [], evidence=old['evidence'], fixed=fixed, selected='A', status='수정 계획'))
add('W01','현재 사양은 wiki, 계획서는 안내 자료',
    '현재 사양은 wiki의 확정 결정·계약으로 통일합니다.',
    [('A','wiki 우선 규칙 통일','본문과 자동으로 읽히는 작업 규칙을 함께 고칩니다.'),('B','정본 목록 페이지 추가','기능별 정본을 목록으로 지정합니다. 목록 관리가 추가됩니다.'),('C','현재 상태 먼저 동결','wiki와 코드 판본을 먼저 고정합니다. 남은 모순까지 함께 고정되는 단점이 있습니다.')],
    ['wiki/index·루트 AGENTS·research/index·cs AGENTS/RULE의 옛 계획서 우선 지시를 같은 원칙으로 교체합니다.','결정일·적용 범위·대체 관계를 연결하고 v11은 당시 기록, v12는 wiki 안내서라고 표시합니다.'],
    '현재 제품 사양은 wiki의 확정 결정·계약을 정본으로 삼는다. 구현 상태는 코드와 실행 기록으로 확인한다. 옛 계획서는 이후의 명시적 결정을 뒤집지 않는다.',
    ['현재 규칙에 옛 계획서 우선 지시가 남지 않습니다.','옛 기록은 보존하고 현재 사양으로 이동하는 링크를 둡니다.'],targets=['wiki/index.md','AGENTS.md','program/research/index.md','final_project_cs/AGENTS.md','final_project_cs/RULE.md'],fixed=True)

add('W02','고객 웹·개인 AI 연동·공유 계획서의 역할 명시',
    '“별도 접점”을 지우고, 고객이 이용하는 화면과 API의 역할을 적습니다.',
    [('A','현재 웹 기능까지 범위에 포함','웹 입력·일정 구성·검증·수정·감시 설정, 개인 AI 연동, 공유 계획서 열람을 함께 설명합니다.'),('B','웹은 입력·검토 중심','최초 자동 일정 구성은 시험 기능으로 표시합니다. 현재 기능을 제품 약속에서 좁히는 선택입니다.'),('C','개인 AI 중심으로 제공','개인 AI가 일정을 만들고 웹은 검토·관리만 합니다. 현재 웹 일정 구성 기능의 역할을 축소합니다.')],
    ['scope·positioning·system-context의 “자체 앱 없음/계획 생성은 우리 일 아님”을 현재 웹 흐름에 맞게 바꿉니다.','범위표에 고객 웹 화면, 개인 AI 연동(API/MCP), 공유 계획서 링크를 적습니다. 모두 같은 여행 상태를 사용하며 독립 앱 3개를 만들자는 뜻이 아닙니다.','최초 일정 구성과 여행 중 재계획을 분리하고 지원 지역·자료·검증 수준을 각 기능에 연결합니다.'],
    '고객은 triPilot 웹에서 여행 조건과 장소를 입력하고 일정을 구성·검토·수정한다. 개인 AI는 API/MCP로 본인 여행을 조회·처리한다. 공유 계획서 링크는 최신 일정을 읽는 화면이며 편집 권한을 주지 않는다.',
    ['제품 범위표와 실제 웹 입력→구성→검토→등록 흐름이 일치합니다.','웹 제공을 제외하는 현재 문구를 제거하고, 미검증 기능을 완료라고 쓰지 않습니다.'],targets=['wiki/product/scope.md','wiki/product/positioning.md','wiki/architecture/system-context.md','final_project_cs/wiki/external/rest-endpoints.md'])

add('W03','항로 지킴이 켜짐: 검증한 변경을 자동 적용',
    '항로 지킴이를 켜면 변경 필요 여부를 판단하고, 검증한 대체안을 적용한 결과를 제시합니다.',
    [('A','현재 모드와 예외를 한 표로 정리','켜짐은 자동 적용, 꺼짐은 변경 제안. 고정 일정·재난은 기존 별도 규칙을 유지합니다.'),('B','조건별 자동 변경 범위 설정','날씨·휴무·이동별로 허용 범위를 고객이 고릅니다. 설정과 검증 비용이 늘어납니다.'),('C','여행 등록 때 변경 권한 요약','고객이 등록할 때 자동 변경 범위를 확인합니다. 기존 여행의 재확인 절차가 추가됩니다.')],
    ['고객 설정 명칭을 항로 지킴이로 통일하고, 옛 설문 값 replace/ask_first는 구현 대응표에만 둡니다.','일반 사건은 켜짐=재계획→재검증→새 일정 저장→알림, 꺼짐=제안→고객 선택으로 적습니다.','고정 일정은 확인 후 변경, 재난은 일정 정지 후 고객이 명시적으로 재개, 업체 예약·결제는 자동 실행 범위 밖이라고 적습니다.','설문 미응답 여행의 guardian 표시·auto_on_disruption·pending.decide 경로를 대조합니다. 코드 버그로 단정하지 않고 동작 검사 항목으로 등록합니다.'],
    '항로 지킴이가 켜진 여행은 일반 사건에 대해 검증한 변경안을 자동 적용하고 변경 이유·결과·되돌리기를 제공한다. 고정 일정은 고객에게 확인한다. 재난은 대체 관광이 아니라 일정 정지와 공식 안전 안내로 처리하며 고객이 재개한다.',
    ['켜짐/꺼짐/고정 일정/재난/미응답 옛 여행을 각각 검사합니다.','중복 감지에 일정 판과 알림이 중복 생성되지 않으며 되돌리기는 새 판으로 기록합니다.'],targets=['wiki/product/positioning.md','wiki/product/scope.md','wiki/decisions/D-020-trip-survey-and-ask-first.md','final_project_cs/wiki/external/rest-endpoints.md'],fixed=True)

add('W04','인증 수단은 구분하고 여행 권한 검사는 공유',
    '기존 쿠키·에이전트 키를 유지하고, 모든 여행 작업에 같은 소유자·권한 검사를 적용합니다.',
    [('A','기존 인증 유지 + 공통 권한 검사','웹은 쿠키, 개인 AI는 에이전트 키, 공유 링크는 읽기 전용입니다. OAuth는 다음 단계로 둡니다.'),('B','개인 AI OAuth까지 이번에 구현','키 복사 대신 로그인·동의로 연결합니다. 코드 교환·만료·폐기 검사까지 구현 범위가 커집니다.'),('C','웹·공유 링크 먼저 출시','개인 AI 연결은 준비 기능으로 표시합니다. 개발량은 줄지만 기존 개인 AI 제공 범위를 늦춥니다.')],
    ['REST 계약을 기준으로 “누가/인증 수단/대상 여행/허용 작업/만료·폐기/구현 상태” 권한표를 만듭니다. 공유 토큰은 그 여행의 읽기 권한만 부여합니다.','인증 층이 검증한 사용자·tenant·권한을 Core에 전달합니다. 여행 소유자와 작업 권한은 매 요청 cs 프로젝트 앱에서 검사하며 LLM 판단에 맡기지 않습니다.','웹 변경은 쿠키+CSRF, 개인 AI는 read/write 키+MCP 쓰기 스위치, 외부 시스템은 별도 require_scope 계약을 연결합니다. 계정·키 관리는 웹 회원만 수행합니다.','D-CS-012의 에이전트 키 “구현 중”과 REST의 구현 기록을 대조합니다. 구현 파일 존재·기록상 시험·이번 실행·배포 확인을 구분하고 OAuth를 구현 완료로 쓰지 않습니다.'],
    '브라우저 세션, 에이전트 키, 공유 토큰은 다른 인증 수단이다. 인증된 사용자와 요청 자원의 소유 관계·허용 작업을 매 요청 검사한다. 공유 토큰은 해당 계획서 열람만 허용하며 회원 편집 권한으로 승격하지 않는다.',
    ['다른 고객 여행·공유 토큰 쓰기·read 키 쓰기·폐기/만료 키·계정 관리 접근을 거부합니다.','쿠키 CSRF 누락 및 쿠키+키 동시 요청 처리, MCP 쓰기 스위치, 게스트→회원 이관을 검사합니다.'],targets=['final_project_cs/wiki/external/rest-endpoints.md','final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md','final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md','final_project_cs/wiki/external/web-auth-transfer.md','wiki/architecture/system-context.md'],basis=['session','authorization','mcp'])

add('W05','자동 처리·고객 보완 입력·개발자/QA 사후 분석',
    '실시간 상담원 인계를 없애고, 자동 복구와 고객의 직접 해결을 지원하면서 결함 자료를 축적합니다.',
    [('A','기존 DB에 결함·영향 기록 + 사후 분석','현재 규모에 맞게 시작합니다. 개발자·QA 조회는 별도 내부 권한으로 제한합니다.'),('B','관측 도구에 결함 집계 위임','중복 오류와 추적을 도구가 묶습니다. 외부 전송 범위·보존 비용·영향 고객 연결을 추가 설계해야 합니다.'),('C','처음부터 전용 수집 작업자 분리','오류가 많아도 고객 처리와 자원을 분리합니다. 대기열·재전송·누락 검사 운영이 늘어납니다.')],
    ['실시간 상담원 대기·수동 처리 완료 기준을 제거합니다. 자동 재조회·대체 자료·재분류 후에도 실패하면 원인을 구분합니다.','고객이 고칠 수 있는 장소명·주소·날짜 등만 입력 요청합니다. 검증된 후보가 있으면 추천순으로 최대 3개와 추천 이유를 제시하고, 없으면 직접 입력 필드를 제공합니다. 외부 API 장애를 고객 입력 탓으로 돌리지 않습니다.','장소 미매칭, 처리 오류, 고객 건의를 별도 유형으로 저장합니다. 오류 발생 기록과 동일 결함 묶음, 영향 고객 연결을 분리합니다. 고객 건의와 장소 입력은 검증 전 공용 자료에 자동 반영하지 않습니다.','개발자·QA는 결함 유형·재현 조건·영향 고객·해결 판본을 사후 조회합니다. 고객 요청을 대신 처리하거나 일정 DB를 직접 고치는 권한은 부여하지 않습니다.','대기열 지연·DB 기록 지연이 기준을 넘으면 수집 작업자를 분리하고, 동일 결함은 집계·표본 상세로 저장합니다. 영향 고객 연결과 발생 건수는 표본으로 줄이지 않습니다.'],
    'triPilot은 실시간 상담원 또는 운영관리자의 개입 없이 동작한다. 자동 해결이 어려운 고객 입력은 추천안과 함께 고객이 보완한다. 미매칭 장소·오류·건의는 개발자·QA의 사후 개선을 위한 기록으로 축적하며 상담 인계나 수동 처리 완료로 표시하지 않는다.',
    ['실패 응답에 다음 행동·입력 항목·가능한 추천·고객용 오류 코드가 있습니다. 상담원 배정 약속은 없습니다.','같은 오류 반복 시 결함 묶음은 하나이고 발생 건수·영향 고객은 빠짐없이 집계됩니다.','진단 저장 실패가 추가 무한 재시도나 다른 고객 처리 중단을 만들지 않습니다.'],targets=['wiki/delivery/dod.md','final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md','final_project_cs/wiki/external/rest-endpoints.md','wiki/architecture/notifications.md'],basis=['logging','queue','retry'],fixed=True)

add('W06','조회 실패는 해당 기능에서 격리하고 복구',
    '외부 자료 실패로 cs 프로젝트 앱 전체를 끄지 않고, 근거가 필요한 변경만 보류합니다.',
    [('A','기능·요청 단위 장애 격리','실패한 조회와 변경만 멈추고 기존 일정·정상 기능은 유지합니다. 현재 구조에 가장 적합합니다.'),('B','해당 여행의 자동 변경 전체 보류','여행 일부의 필수 자료가 빠지면 그 여행의 변경을 모두 보류합니다. 정상 항목도 기다리게 됩니다.'),('C','장애 소스를 쓰는 자동 변경 전체 중지','장애 소스에 의존하는 모든 여행의 변경을 잠시 중지합니다. 광범위한 소스 장애 대응에는 단순하지만 영향이 큽니다.')],
    ['D-018을 그대로 승인하지 않고, 기동 필수 기반·외부 조회·고객 입력 부족·안전 사건의 처리표로 다시 작성합니다. “사람 인계”를 자동 복구/고객 안내/결함 기록으로 교체합니다.','DB·인증·테넌트 격리 같은 필수 기반을 보장할 수 없으면 해당 앱/기능의 준비 상태를 실패로 처리합니다. 외부 소스 하나가 불통인 것과 구분합니다.','일시 오류는 시간·횟수 예산 안에서 재시도하고 대체 자료를 사용합니다. 연속 실패 소스는 회로 차단(잠시 호출을 쉬고 시험 요청으로 복구 확인)을 적용합니다. 값·영업·안전을 추정해 정상 판정하지 않습니다.','자료가 없으면 의존하는 변경을 저장하지 않고 기존 일정과 마지막 확인 시각·검증 불가 상태를 표시합니다. 영향 항목 안내는 상태 전환 때 보내고 반복 오류 알림을 합칩니다.','복구 후 최신 일정 판·자료 유효시간·고객 모드를 다시 확인하고 재검증합니다. 낡은 제안을 그대로 재실행하지 않으며 다른 여행·항목은 계속 처리합니다.'],
    '외부 자료 조회 실패는 해당 판정과 변경을 보류한다. 기존 일정은 유지하되 현재 유효성이 확인되지 않았음을 알린다. 복구하면 최신 자료와 일정 판으로 재검증한다. 데이터 무결성·인증 실패와 재난 일정 정지는 별도 규칙으로 처리한다.',
    ['한 항목 조회 실패 중 다른 항목과 다른 여행은 처리됩니다. 미확인을 사건 없음으로 답하지 않습니다.','일시 오류·영구 오류·대체 실패·복구·기반 DB 실패를 나눠 검사합니다.','재시도가 결제·예약 같은 외부 쓰기를 중복 실행하지 않습니다.'],targets=['wiki/decisions/D-018-decision15-stop-paths.md','wiki/architecture/notifications.md','wiki/decisions/D-017-watch-cadence-golden-time.md'],basis=['bulkhead','circuit','retry'])

add('W07','감시 주기와 자료 지연을 따로 표시',
    '3분 감시를 3분 내 모든 사건 감지라는 약속으로 쓰지 않습니다.',
    [('A','자료별 지연표 작성','게시 지연·수집 간격·캐시·판정·통지를 각각 기록합니다.'),('B','안전 자료만 우선 새로 수집','감지 지연은 줄지만 호출 한도와 비용 검증이 먼저 필요합니다.'),('C','전체 자료 수집 주기 통일','관리하기 쉽지만 소스별 제한을 만족시키기 어렵습니다.')],
    ['D-017에 소스별 게시/수집/캐시/판정/통지 시간을 한 표로 추가합니다.','“최대 3분”을 실제 경로별 상한 또는 미측정으로 교체하고 20분 캐시와 모순을 제거합니다.'],
    '감시 실행 간격과 사건 감지 지연은 다르다. 감지 지연은 원천 게시 지연과 수집·캐시·판정 시간을 포함해 자료별로 기록한다.',
    ['실제 설정값의 위치와 확인 시각이 연결됩니다.','원천 시각부터 통지 기록까지 측정하지 않은 값은 목표/추정으로 표시합니다.'])

add('W08','같은 여행의 여러 일정 문제 처리: 호출 담당과 변경 규칙 정리',
    '여행 상태 점검에서 함께 발견한 여러 문제를 처리하는 기능입니다. 에이전트 팀 호출 담당과 항목별 계산 담당을 구분해 적습니다.',
    [('A','현행 공동 처리 구조를 정확히 문서화','Activity 에이전트 팀이 조정하고, 각 팀이 등록한 계산을 같은 일정 초안에 순서대로 적용합니다. 기존 결정 유지·추천입니다.'),('B','문제마다 별도 사건으로 처리','현재의 함께 처리하는 결정을 바꾸는 대안입니다. 일정 버전·알림이 여러 번 생길 수 있습니다.'),('C','Controller에 다중 팀 조정 기능 신설','새 설계입니다. Controller의 연쇄 실행·제안 병합·실패 계약을 다시 설계하고 공통 실행 규칙을 검사해야 합니다.')],
    ['D-017의 10월 3일 오후 결정과 D-CS-013의 10월 6일 등록 구조를 현재 설명으로 올립니다. 9월의 “아직 구현 없음”과 “코어가 세 팀을 순서대로 호출”은 당시 설계로 구분합니다.',
     '여행 상태 점검의 TripWatchCaseOpener가 같은 여행의 새 문제를 모아 사건(Case)을 만듭니다. 함께 처리하는 스위치가 켜지고 새 문제가 둘 이상일 때 적용하며, 현재 코드의 항목 수 상한을 넘으면 여러 사건으로 나누는 제한도 적습니다.',
     'Controller가 TeamRegistry.resolve로 담당 에이전트 팀을 선택하고 TeamExecutorPort.execute로 실행을 요청하는 순서를 명시합니다. LocalTeamExecutor는 등록된 팀의 execute를 호출하는 구현입니다.',
     '이 사건은 Activity 에이전트 팀이 조정합니다. ItineraryWork.run_itinerary → WatchBatch.run → watch_planners.planner(항목 종류) 순으로, 각 에이전트 팀이 조립 때 등록한 계산을 사용합니다. 다른 에이전트 팀의 execute를 연쇄 호출하는 구조로 적지 않습니다.',
     '활동→식당→이동 순으로 앞서 수정한 초안을 이어받고 전체 일정을 재검증합니다. Controller는 반환된 변경 제안을 검증하고 등록된 일정 적용기로 저장합니다. 성공한 변경은 일정 버전·변경 알림 각각 하나로 모으고, 고객 선택 질문은 항목마다 따로 보냅니다.',
     '해결하지 못한 항목은 유지하고 처리 가능한 다른 항목은 계속 처리합니다. 소스 실패의 고객 안내는 W06 개정안으로 명시하며, 현재 코드의 무통지 동작을 이미 변경한 것처럼 쓰지 않습니다.'],
    '같은 여행의 여러 일정 문제를 함께 처리하는 사건은 Controller가 TeamRegistry로 담당 Activity 에이전트 팀을 찾아 TeamExecutorPort를 통해 실행한다. Activity 쪽 WatchBatch는 watch_planners에 등록된 활동·식당·이동 계산을 한 초안 위에서 순서대로 사용한다. 재검증한 변경 제안의 저장은 Controller와 일정 적용기가 담당한다. 에이전트 팀끼리 execute를 직접 호출하지 않는다. 처리 가능한 변경은 함께 반영하고 고객 선택 질문은 항목마다 제공한다.',
    ['담당 선택·팀 실행·항목별 계산·변경 저장의 주체가 실제 코드 이름과 일치합니다.','동시 편집 충돌·중복 사건·일부 실패·고정 항목 질문·항목 수 상한이 계약에 표시됩니다.','에이전트 팀 간 직접 execute 호출과 등록된 계산 함수 사용을 혼동하지 않습니다.'],
    targets=['wiki/decisions/D-017-watch-cadence-golden-time.md','final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md','final_project_cs/wiki/teams/composition.md'])

add('W09','낮 휴무 확인의 자료·비용·한계 명시',
    '무료 자료를 우선 쓰고, 확인하지 못한 영업 상태는 정상이라고 표시하지 않습니다.',
    [('A','무료 자료 우선 + 검증 불가 표시','낮 조회 가능한 자료와 한계를 적습니다. 구글 호출 제한을 유지합니다.'),('B','필요한 장소만 유료 재조회','휴무 확인 범위를 넓히지만 고객·여행별 비용 상한을 다시 정해야 합니다.'),('C','고객 휴무 신고 중심','외부 조회 비용은 줄지만 선제 감지 범위를 축소합니다.')],
    ['D-CS-009/010과 D-020을 같은 자료 선택표로 연결합니다. 지도 표시와 영업 상태 조회를 구분합니다.','무료 주자료·대체 자료·관측 시각·조회 예산·실패 행동을 적고 W06의 검증 불가 상태를 사용합니다.'],
    '낮 휴무 감지는 사용 가능한 무료 자료와 고객 신고를 사용한다. 영업 상태를 확인하지 못하면 정상 영업으로 단정하지 않으며 유료 조회 확대는 비용 정책을 바꾼 뒤 적용한다.',
    ['낮 휴무 시나리오마다 실제 사용 자료·시각·비용·조회 실패 행동이 있습니다.','구글 새벽 배치 제한과 낮 조회 계약이 충돌하지 않습니다.'])

add('W10','평가 첫 화면을 여행 평가로 교체',
    '현재 여행 평가 자료와 도구로 안내하고 쇼핑몰 성과는 과거 기록으로 둡니다.',
    [('A','목적별 여행 평가 지도','분류·검색·선택·응답·제품 시나리오를 각각 연결합니다.'),('B','제품 종단 평가 중심','고객 흐름은 잘 보이지만 모델별 원인 분석이 어려워집니다.'),('C','모델별 평가 중심','학습 비교는 편하지만 제품 전체 성공 여부를 별도로 확인해야 합니다.')],
    ['evaluation/index의 현재 실행 안내를 여행 평가 자료·실재 도구·결과 위치로 교체합니다.','쇼핑몰 수치는 날짜와 도메인을 붙인 기록 링크로 내려 현재 출시 근거에서 제외합니다.'],
    '현재 제품 평가는 여행 도메인 자료로 수행한다. 분류·검색·선택·응답·전체 여행 시나리오의 평가 목적과 자료 판본을 구분한다.',
    ['현재 실행 명령이 여행 자료를 가리키고 실제 파일이 있습니다.','과거 쇼핑몰 통과 수가 현재 여행 품질 수치로 인용되지 않습니다.'])

add('W11','출시 기준을 현재 요구·시험·증거에 연결',
    '실행 불가능한 옛 명령과 과거 통과 수를 현재 출시 판정에서 제거합니다.',
    [('A','요구별 검증표 재작성','요구 ID·검사·결과·미구현 상태를 연결합니다.'),('B','고객 시나리오별 출시표','설명은 쉽지만 공통 보안·계약 조건이 중복됩니다.'),('C','기존 번호 유지 + 대응표','이력 연결은 쉽지만 옛 번호와 현재 의미를 계속 함께 관리합니다.')],
    ['dod·release-gate에 현재 여행 요구와 실행 가능한 검사 경로를 적습니다.','삭제된 check_judge 등은 과거 기록으로 표시합니다. W05의 상담원 인계 항목을 자동 복구·고객 보완 입력·결함 기록 검사로 교체합니다.'],
    '출시는 현재 여행 요구별 검증 결과로 판단한다. 파일 존재·과거 통과·문서 수정만으로 구현 완료 또는 출시 통과로 세지 않는다.',
    ['현재 검사 명령을 수집해 실재 여부를 확인합니다.','새 항목 수는 대응표를 만든 후 집계하며 v11 숫자를 자동 승계하지 않습니다.'])

add('W12','에이전트 팀의 자료 조회는 허용된 도구로 통제',
    '에이전트 팀은 허용된 도구로 조회하고, 변경 제안은 Controller가 검증한 뒤 등록된 적용기로 실행합니다.',
    [('A','통제된 읽기 도구 허용','허용 목록·예산·tenant 격리·근거 반환을 도구 실행 경로에서 강제합니다.'),('B','공통 실행 계층에서 모든 자료 선조회','에이전트 팀은 받은 입력만 읽습니다. 도메인을 모르는 공통 실행 계층에 여행별 조회 순서를 넣게 되는 문제가 있습니다.'),('C','전용 자료 조회 서비스 분리','도구 정책을 모으기 쉽지만 서비스·호출 계약이 추가됩니다.')],
    ['에이전트 팀 경계·불변식 문서의 “읽기 전면 금지”를 자료 조회/외부 변경/내부 상태 변경 표로 바꿉니다.','에이전트 팀은 허용된 Port로 조회하고 제안만 반환합니다. 인증 문맥·예산·근거를 강제하며 Controller에 여행별 계산을 넣지 않습니다.'],
    '에이전트 팀은 허용 목록과 예산·소유 범위를 강제하는 읽기 도구를 사용할 수 있다. 일정 변경과 외부 부수 효과는 직접 실행하지 않고 제안으로 반환한다. Controller가 제안을 검증하고 등록된 적용기로 실행한다.',
    ['미등록 도구·범위 밖 자료·예산 초과·직접 DB 변경이 차단됩니다.','플랫폼 코어가 에이전트 팀 내부 구현을 import하지 않습니다.'])

add('W13','쇼핑몰 시험 재료를 여행 재료로 대체',
    '쇼핑몰 자산 금지 결정을 유지하면서 공통 계약 검증은 여행 사례로 보존합니다.',
    [('A','동일 불변식을 여행 사례로 검증','금지 자료를 현재 실행 경로에서 빼고 검사 목적은 유지합니다.'),('B','도메인 중립 합성 계약 자료','공통 계약만 검사합니다. 실제 여행 흐름 검사는 별도로 필요합니다.'),('C','공통/여행 시험 묶음 분리','실행 범위는 명확하지만 두 묶음 유지 비용이 늘어납니다.')],
    ['시험 수집 목록과 CI에서 쇼핑몰 대조군 사용 경로를 확인합니다.','불변식 문서의 옛 예외를 D-023으로 대체하고 같은 실패를 잡는 여행 사례를 만든 뒤 실행 범위를 바꿉니다. 기록·원본을 임의 삭제하지 않습니다.'],
    '현재 검증·시연에는 쇼핑몰 자료를 사용하지 않는다. 공통 계약 검증은 여행 사례 또는 고객 자료 없는 합성 입력으로 유지한다.',
    ['대체 시험이 원래 불변식 위반을 실제로 잡습니다.','현재 시험 수집·실행 경로에 금지된 쇼핑몰 자료가 들어오지 않습니다.'])

add('W14','DB 안내는 현재 논리 구조와 환경별 적용 기록으로',
    'SQL 파일 개수 대신 실제 표 역할·관계와 환경별 적용 이력을 보여 줍니다.',
    [('A','논리 구조 + 환경별 적용표','여행·인증·통지·근거 구조와 실제 적용 상태를 나눠 적습니다.'),('B','스키마 전체 자동 생성','정확한 열 조회는 쉽지만 제품 역할 설명은 별도로 필요합니다.'),('C','기능별 DB 문서 분리','담당 기능은 보기 쉽지만 공통 표의 관계가 흩어집니다.')],
    ['data/index·schema/index를 현재 여행 저장 구조로 안내합니다.','활성/대기 SQL 파일과 로컬 개발 DB·배포 DB의 적용 이력을 구분합니다. 이번 문서 작업에서 DB 변경은 하지 않습니다.'],
    '마이그레이션 파일 수는 DB 적용 완료 수가 아니다. 환경별 실제 적용 이력과 현재 논리 구조를 각각 기록한다.',
    ['DB 적용 여부마다 조회 근거와 확인 시각이 있거나 미확인이라고 적힙니다.','쇼핑몰 표 안내가 현재 저장 구조로 오인되지 않습니다.'])

add('W15','학습·평가·서비스 채택 판정 분리',
    '정확한 모델 이름과 학습 여부·평가 조건으로 비교하고 채택 상태를 따로 적습니다.',
    [('A','현재 평가 절차 + 모델 판본표','원본/학습판/평가 완료/채택을 한 표로 추적합니다.'),('B','실험별 독립 보고서','실험 재현은 쉽지만 현재 채택 모델을 별도 목록에서 찾아야 합니다.'),('C','중앙 모델 등록 체계 도입','자동 추적은 편하지만 현재 규모에서 운영 구성 요소가 늘어납니다.')],
    ['중앙 finetuning 페이지는 cs의 현재 평가 절차로 안내하고 과거 모델 결과는 기록 링크로 분리합니다.','비교마다 정확한 모델 ID·학습 여부·기본 모델·자료 해시·설정·프롬프트·실행 조건·채택 판정을 적습니다.'],
    '모델 후보 선정, 추가 학습 효과, 서비스 채택은 서로 다른 판정이다. 비교 표에는 정확한 모델 이름과 학습 여부를 필수로 기록한다.',
    ['학습한 모델과 학습 없는 원본 비교를 같은 학습 조건이라고 쓰지 않습니다.','평가 자료 판본과 누수 여부·반복·편차가 연결됩니다.'])

add('W16','기능별 책임과 공유 계약 변경 절차 명시',
    '기능 책임 역할은 정하되 실제 팀원 배정을 임의로 만들지 않습니다.',
    [('A','기능 책임 역할표 갱신','인증·실행 안전·DB·평가·통합의 책임 역할과 검토 경계를 적습니다.'),('B','디렉터리 소유표만 갱신','수정 경계는 명확하지만 여러 폴더에 걸친 기능 책임이 남습니다.'),('C','작업별 담당 지정','유연하지만 상시 책임 공백과 인수인계 비용이 큽니다.')],
    ['roles의 옛 경로를 실제 팀 폴더와 맞추고 기능 책임·검토 역할을 구분합니다.','미배정은 그대로 표시합니다. 인증/공통 계약은 Core 책임 역할의 검토 대상이라는 제안으로 두고 팀원 이름은 팀 합의 후 채웁니다.'],
    '기능 책임과 코드 수정 경계는 역할로 정의한다. 실제 담당자 미배정은 숨기지 않으며 공유 계약 변경에는 관련 기능 담당자의 검토를 기록한다.',
    ['역할표의 현재 경로가 존재합니다.','미배정을 임의 인명으로 채우거나 배정 완료로 표시하지 않습니다.'])

add('W17','현재 제출 계획과 과거 주차표 분리',
    '확인된 발표 날짜는 유지하고, 남은 작업은 현재 여행 요구로 다시 연결합니다.',
    [('A','제출물→현재 요구→근거로 재정리','공식 날짜와 구현·평가·시연 준비를 연결합니다.'),('B','남은 주차별 계획 재작성','일정 파악은 쉽지만 작업이 바뀔 때 반복 편집이 필요합니다.'),('C','남은 작업 목록만 유지','갱신은 쉽지만 제출 준비와 마감 연결이 약해집니다.')],
    ['timeline의 “오늘”·상용 주문 자료·옛 Team 안내를 과거 이력으로 표시합니다.','현재 제출물은 여행 wiki·검증 근거에 연결합니다. 새 동결일·담당자·공식 마감은 확인 없이 만들지 않습니다.'],
    '현재 일정표는 공식 제출 날짜와 여행 제품의 남은 구현·평가·시연 작업을 보여 준다. 과거 주차표는 당시 기록으로 보존한다.',
    ['현재 제출 안내에 쇼핑몰 과제·29항목 관문이 들어오지 않습니다.','모든 새 날짜에 공식 근거 또는 제안 표시가 있습니다.'])

add('W18','환경별 앱·DB·감시·모델 상태 분리',
    '추론 성공과 고객용 앱 정상 가동을 구분하고 확인 시각을 붙입니다.',
    [('A','환경별 구성·상태표','로컬 개발·x600 배포·ARM 실험·GPU 추론을 따로 적습니다.'),('B','중앙 상태 화면 구축','최신 상태를 보기 쉽지만 별도 수집·인증·유지 비용이 있습니다.'),('C','환경별 운영 문서 분리','세부 운영은 편하지만 전체 배치 현황을 별도로 연결해야 합니다.')],
    ['always-on 첫 화면의 “전부 개발자 PC 콘솔”을 현재 환경 지도로 교체합니다.','실행 코드 SHA·이미지·DB 적용·감시/배달 작업·모델 상태·확인 시각을 구분합니다. 접속 비밀은 공용 문서에 쓰지 않습니다.'],
    '운영 상태는 환경과 구성 요소별로 기록한다. 모델 추론 성공은 고객용 앱·DB·감시·통지의 정상 동작을 증명하지 않는다.',
    ['각 상태에 실행 근거 또는 원격 미확인 표시가 있습니다.','기계 접속 정보·키·공인 주소가 문서에 노출되지 않습니다.'])

add('W19','datasets 전체 Git 제외 규칙으로 안내 통일',
    '데이터 주변 파일도 공개하지 않는 현재 규칙을 그대로 반영합니다.',
    [('A','데이터 안내 문구·지도 수정','datasets 전체 제외와 현재 REPORT 기준을 안내합니다.'),('B','공개용 도구를 별도 폴더로 분리','안전한 도구만 검토 후 옮깁니다. 이번 데이터 폴더를 공개하는 뜻은 아닙니다.'),('C','데이터 전달 절차 별도 문서','팀 공유 절차를 명확히 하지만 관리 문서가 늘어납니다.')],
    ['datasets/wiki의 “스크립트·스키마·REPORT는 Git 공개” 문장을 현재 전체 제외 규칙으로 교체합니다.','현재 자료 지도와 실제 REPORT를 대조합니다. 이번 작업에서 데이터 삭제·외부 공개는 하지 않습니다.'],
    'datasets는 폴더 전체를 Git에서 제외한다. 데이터와 주변 문서·스크립트의 공개는 별도 검토 없이 수행하지 않는다.',
    ['루트 제외 규칙과 데이터 안내가 일치합니다.','사라진 쇼핑몰 자료를 현재 사용 자료로 안내하지 않습니다.'])

add('W20','결정 상태·구현 상태·배포 상태를 따로 표시',
    'draft 하나로 미확정·미구현을 판단하지 않도록 메타데이터를 나눕니다.',
    [('A','결정/구현/검증 필드 분리','명시적 결정 근거와 현재 확인 상태를 함께 기록합니다.'),('B','본문 상태표만 통일','바로 적용하기 쉽지만 자동 집계가 어렵습니다.'),('C','결정 문서만 엄격한 메타데이터','부담은 작지만 일반 계약 페이지 상태의 모호함이 남습니다.')],
    ['document-standard에 decision_status·implementation_status·verified_at·supersedes의 의미와 예시를 정의합니다.','본문의 사용자 결정과 실제 근거를 대조해 페이지별로 전환합니다. 일괄 accepted 승격은 하지 않습니다.'],
    '결정 채택, 코드 구현, 실행 검증, 배포 확인은 별도 상태다. 결정 채택만으로 구현 또는 배포 완료를 주장하지 않는다.',
    ['D-017/D-020의 확정 문장과 D-018의 초안 상태를 구분할 수 있습니다.','상태 전환에 근거·확인일·적용 범위가 있습니다.'])

add('W21','깨진 링크 3곳을 실제 자료로 연결',
    '존재하는 목적지로 연결하고, 사라진 원본은 역사 자료라고 표시합니다.',
    [('A','목적지 직접 수정','open-items는 중앙 wiki로, Dining 원본은 확인된 현재 자료로 연결합니다.'),('B','옛 경로 안내 페이지 생성','옛 링크 호환은 좋지만 안내 파일이 늘어납니다.'),('C','근거 링크를 현재 설계로 대체','현재 읽기는 쉽지만 원본과 현재 자료의 관계 설명이 필요합니다.')],
    ['쿠키 결정·REST 계약의 open-items를 실제 중앙 페이지로 고칩니다.','Dining 체크리스트는 실제 원본을 찾으면 연결하고, 못 찾으면 당시 입력 파일 미확보라고 표시한 뒤 현재 설계로 안내합니다. 존재하지 않는 파일을 만들었다고 쓰지 않습니다.'],
    '현재 안내 링크는 실제 파일을 가리킨다. 과거 입력 자료가 확보되지 않았으면 그 사실과 현재 참고 문서를 함께 적는다.',
    ['확인된 3개 링크 목적지가 존재하거나 미확보 표시로 교체됩니다.','앵커·원격 링크까지 모두 정상이라는 주장은 하지 않습니다.'])

add('W22','wiki 검사 범위를 현재·기록·백업으로 구분',
    '백업의 상대경로 경고를 현재 wiki 결함으로 세지 않습니다.',
    [('A','기존 검사기에 문서 유형별 범위 추가','기본은 현재 본문, 기록·백업은 별도 선택 검사로 둡니다.'),('B','현재 본문 검사기 새로 작성','규칙을 명확히 만들 수 있지만 두 검사기 유지와 이관이 필요합니다.'),('C','명시적 파일 목록만 검사','범위는 정확하지만 새 페이지가 목록에서 빠질 수 있습니다.')],
    ['check_wiki.py의 수집 단계에 _backup·records·이관 임시·생성물 분류를 넣습니다.','현재 문서의 진짜 끊긴 링크는 계속 실패로 처리하고, 범위별 검사 파일 수와 위반 수를 따로 출력합니다.'],
    '기본 검사는 현재 wiki 본문에 적용한다. 보존 기록·백업·생성물은 별도 범위로 집계하며 백업 때문에 생긴 경로 변경을 현재 결함 수에 섞지 않는다.',
    ['백업 추가가 현재 본문 오류 수를 바꾸지 않습니다.','현재 문서에 의도적으로 넣은 끊긴 링크는 검사 실패로 잡힙니다.'])

add('W23','불변식 요약 숫자를 카탈로그에서 계산',
    '검증 규칙 개수와 시험 통과 수를 구분하고 코드 표식을 연결합니다.',
    [('A','단일 카탈로그 + 자동 집계','ID·현재/역사 상태·시험 경로로 요약 수를 계산합니다.'),('B','현재 표 숫자만 수정','빠르지만 다음 추가 때 다시 틀어질 수 있습니다.'),('C','시험 코드에서 문서 생성','실행 연결은 강하지만 코드에 없는 제품 규칙이 빠질 수 있습니다.')],
    ['고유 ID 71개·ACT 12개라는 발견 시점 집계를 검증하고 역사 항목을 분리합니다.','ARCH-007의 검사 의미를 읽고 정식 카탈로그 항목에 연결한 뒤 요약을 자동 계산합니다.'],
    '불변식 카탈로그의 규칙 수는 활성 ID에서 집계한다. 규칙 등록 수와 해당 시험의 실행·통과 수는 다른 지표다.',
    ['요약과 고유 ID 집계가 일치합니다.','코드의 미등록 표식·카탈로그의 누락 시험 연결을 검사합니다.'])

add('W24','ODsay 제품 미사용과 연구 대조 범위 구분',
    '제품 미사용을 유지하고, 연구용 대조는 승인·조건 확인 뒤 별도로 기록합니다.',
    [('A','제품 미사용 유지 + 연구 근거 확인','키 안내가 제품 연결 승인처럼 보이지 않게 표시합니다.'),('B','연구용 키 안내도 보류 표시','오해는 줄지만 이미 승인된 연구가 있다면 안내가 과도하게 제한됩니다.'),('C','승인된 연구 절차를 독립 문서로 분리','재현은 편하지만 승인 근거·약관·자료 보관 검토가 먼저 필요합니다.')],
    ['D-CS-005와 api-key-issue-guide에 제품 운영/독립 대조의 적용 범위를 표시합니다.','후속 승인 원문과 실제 사용·보관을 확인하기 전 연구 허용이나 약관 적합성을 확정하지 않습니다. 기존 키·자료를 삭제하지 않습니다.'],
    'ODsay는 제품 운영에 연결하지 않는다. 독립 연구 대조의 허용 범위는 승인 근거와 이용 조건을 확인해 별도 기록하며 키 발급 안내를 제품 채택 근거로 쓰지 않는다.',
    ['제품 코드 경로와 연구 경로의 사용 여부를 각각 확인합니다.','키 발급 가능과 이용 조건 적합을 같은 판단으로 쓰지 않습니다.'])

add('W25','현재 계약을 위에, 변경 이력은 근거 링크로',
    '페이지를 끝까지 읽어야 현재 규칙을 알 수 있는 구조를 바꿉니다.',
    [('A','현재 계약 + 대체 관계 + 기록 링크','주제별 정본 한 곳을 두고 날짜별 작업은 기록으로 연결합니다.'),('B','기존 본문에 역사 표시만 추가','변경량은 작지만 중복·모순 문장을 계속 읽어야 합니다.'),('C','현재 계약 파일 새로 분리','읽기는 쉬우나 옛 페이지와의 이동·대체 관계를 모두 관리해야 합니다.')],
    ['D-017부터 현재 계약·적용 범위·구현/검증 상태를 맨 위로 정리합니다.','옛 문장은 보존본 또는 역사 절에 두고 대체한 결정으로 연결합니다. 전체 정독하지 않은 253개 본문을 정상 판정하거나 일괄 다시 쓰지 않습니다.'],
    '개념·계약 페이지는 현재 규칙을 먼저 보여 준다. 날짜별 실행 이력은 기록에 보존하고 현재 규칙을 뒷받침하는 근거로 연결한다.',
    ['같은 주제의 현재 정본이 하나로 지정됩니다.','대체된 규칙이 현재 지시처럼 노출되지 않고 원본은 복구할 수 있습니다.'])

# Incorporate the first independent review without claiming product changes.
by_id={x['id']:x for x in PLANS}
by_id['W03']['steps'] += ['미응답은 꺼짐(먼저 확인)을 기본안으로 정하고 표시·판정·알림이 같은 값을 읽도록 맞춥니다. 고객이 직접 켠 기록은 유지합니다. 적용 전 실제 호출 경로와 기존 데이터 호환성을 검사합니다.','REST 재난 재개 절의 “자정에 자동 해제” 문장은 고객 명시 재개 규칙으로 교체합니다.']
by_id['W03']['replacement'] += ' 직접 켠 기록이 없는 여행은 자동 변경하지 않고 제안한다.'
by_id['W05']['steps'] += ['수집 이벤트에는 발생 고유 ID·배포 판본·정책 판본·상관 식별자를 기록합니다. Team은 도메인 결과를 반환하고 공통 실행 경로가 구조화한 기록을 저장합니다. 상담원 인계 의미를 없애려고 Case 상태 이름을 이번 문서 작업에서 바로 바꾸지는 않습니다.','배경 감시와 개인 AI 경로에서도 처리 실패 결과가 조용히 사라지지 않게 합니다. 고객 안내는 실패/복구의 상태 전환과 여행 범위로 중복을 막습니다.']
by_id['W05']['checks'] += ['발생 100건의 결함 묶음은 하나, 발생 수는 100이며 영향 고객 수는 중복 없이 계산합니다. 키·토큰·불필요한 고객 원문은 기록되지 않습니다.']
by_id['W06']['steps'] += ['실패 중인 조회의 재시도는 지수 간격과 무작위 분산을 사용하되 기존 설정·호출 예산에 상한을 둡니다. 인증 거부·잘못된 입력은 같은 조건으로 자동 재시도하지 않습니다.','알림 중복 키는 여행·장애 회차·상태 전환 종류를 포함합니다. 장애 자료가 새로 조회되었다는 이유만으로 기존 재난 정지를 해제하지 않습니다.']
by_id['W06']['checks'] += ['이미 정지한 재난 일정은 외부 조회 실패나 회복으로 자동 재개되지 않습니다.']
by_id['W16']['replacement'] += ' 여기서 책임 역할은 개발·검토 책임이며 실시간 고객 상담 담당이 아니다.'

# Resolve second-review issues explicitly; these are selected policies, not deployment claims.
by_id['W03']['steps'] += ['재난 정지의 우선순위는 일반 자동 변경보다 높습니다. 여행 종료 후 남은 항목이 없으면 감시·재안내를 끝내고 정지 이력만 보존합니다. 이것은 자동 재개가 아닙니다.']
by_id['W03']['checks'] += ['미응답 기본값 변경은 단순 문구 정정이 아니라 호환성 검증이 필요한 동작 변경으로 표시합니다. 명시 선택 기록은 guardian 저장 코드의 survey_answered를 근거로 구분합니다.','여행 종료 후 정지 안내가 무한히 반복되지 않으며 종료 처리가 자동 재개로 기록되지 않습니다.']
by_id['W04']['steps'] += ['한 요청에 쿠키와 사용자/에이전트 키가 함께 오면 기존 계약대로 400 ambiguous_credentials로 거부합니다. 공유 URL은 소유자 인증으로 승격하지 않습니다.','공유 토큰의 현재 생성 모듈은 여행·tenant와 공통 비밀에 대한 HMAC을 사용하며 자체 만료·개별 폐기 정보는 없습니다. 조회 핸들러의 전체 권한·수명 경로와 배포 상태는 별도 확인합니다.','개선안은 여행별 공유 중지·재발급과 만료 검사를 추가하는 것입니다. 초기 만료 제안은 여행 종료+7일과 자료 보존 만료 중 이른 시각이며 설정값으로 둡니다. 표준 의무값이 아닙니다.','공유 페이지 HTML/JSON/내려받기에 no-store·no-referrer 정책을 일관되게 적용하고, 접근 로그의 토큰 쿼리와 외부 링크 Referrer 전송을 검사합니다. 새 토큰 정책은 저장 구조·알림 링크 호환성 검증 후 구현합니다.']
by_id['W04']['replacement'] += ' 쿠키와 사용자·에이전트 키가 함께 오면 거부한다. 공유 링크는 소유자의 공유 중지·재발급과 만료를 지원하도록 개선하며 URL 토큰이 로그·외부 요청에 노출되지 않도록 한다. 후자의 수명·폐기 보강은 구현 계획이다.'
by_id['W04']['checks'] += ['공유 중지·재발급·만료 뒤 옛 토큰이 거부되고 새 알림은 새 링크를 사용합니다.','공유 URL 토큰이 접근 로그·외부 요청 Referer에 남지 않습니다. 현재 구현 확인과 새 정책 구현 완료를 구분합니다.']
by_id['W04']['targets'] += ['final_project_cs/app/domains/travel_ops/components/itinerary/plan_link.py','final_project_cs/app/domains/travel_ops/entry/trip_api.py','final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py']
by_id['W05']['steps'] += ['실제 support 화면의 “운영팀 답변 대기”와 문의 응답 타입을 건의·문제 신고 접수로 개편합니다. 접수 성공은 기록 완료만 뜻하고 고객 문제 해결을 뜻하지 않습니다. 계정 차단 문구의 “운영자에게 문의”도 자동 안내·건의 기록 경로로 바꿉니다.','고객의 업무 처리 결과는 완료/입력 필요/변경 보류/처리 불가로 설명하고, 내부 escalated가 상담원 대기라는 뜻으로 화면에 번역되지 않게 응답 대응표를 만듭니다. 상태기계 변경이 필요하면 계약 판올림과 이관을 별도 작업으로 수행합니다.','진단 DB 저장 실패는 제한된 마스킹 이벤트를 로컬 영속 대기 파일에 보관하고 복구 후 같은 발생 ID로 전송합니다. 용량 상한과 유실 지표를 둡니다. DB와 대기 파일 모두 실패하면 내부 관측에 수집 저하를 표시하고 영속 기록을 보장했다고 세지 않습니다.','서비스 설정·배포·결함 분석은 개발자의 유지보수 역할입니다. 고객 요청마다 운영관리자 승인을 기다리는 구조를 뜻하지 않으며, 고객 여행 편집 권한과 분리합니다.']
by_id['W05']['replacement']='triPilot은 실시간 상담원 대기나 건별 수동 처리를 전제하지 않는다. 자동 해결이 어려운 고객 입력은 추천안과 함께 고객이 보완한다. 미매칭 장소·오류·건의는 접근이 제한된 사후 개선 기록으로 축적하며 가명 고객 ID에도 접근통제·보존기한을 둔다. 개발자의 설정·배포·QA는 유지보수이며 고객 처리의 대기 조건이 아니다.'
by_id['W05']['checks'] += ['문의 화면·접수 응답·계정 차단 안내에 운영팀 답변을 기다린다는 약속이 남지 않습니다.','기록 저장 실패·대기 파일 포화·복구 재전송을 검사하고 기록 누락을 정상 수집으로 세지 않습니다.']
by_id['W05']['targets'] += ['final_project_cs/frontend/apps/web/src/features/support/support.tsx','final_project_cs/frontend/apps/web/src/features/support/client.ts','final_project_cs/app/domains/travel_ops/modules/web_account/admin_customer_api.py','final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py']
by_id['W06']['steps'] += ['D-017의 “점검 소스 실패는 알리지 않는다”를 명시적으로 대체합니다. 일시 재시도 중에는 알림을 만들지 않고, 주자료·대체 자료가 시간/횟수 예산 안에서 모두 실패해 영향을 확정했을 때 여행별 장애 회차에 한 번, 정상 재검증으로 회복했을 때 한 번 안내합니다.','설정 오류로 필수 기반을 보장할 수 없는 기동 실패와 외부 조회 하나의 실패를 분리합니다. 불확실한 상태에서 접근 권한을 완화하거나 쓰기를 재개하지 않습니다.']
by_id['W06']['replacement'] += ' D-017의 점검 소스 실패 무통지 규칙은 대체 실패·예산 소진으로 영향이 확정된 때의 1회 안내와 정상 재검증 후 회복 안내로 대체한다.'
by_id['W06']['checks'] += ['재시도 중 일시 실패에는 반복 알림이 없고, 확정 장애/정상 회복 상태 전환별 안내만 중복 없이 나갑니다.']
for id,path,needle in [
    ('W03','final_project_cs/app/domains/travel_ops/components/planning/survey.py','def auto_on_disruption'),
    ('W03','final_project_cs/app/domains/travel_ops/components/planning/guardian.py','constraints["survey_answered"]'),
    ('W04','final_project_cs/app/domains/travel_ops/components/itinerary/plan_link.py','return hmac.new'),
    ('W04','final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py','raise refuse(400, "ambiguous_credentials"'),
    ('W05','final_project_cs/frontend/apps/web/src/features/support/support.tsx','운영팀 답변을 기다리고 있어요.'),
    ('W05','final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py','운영자에게 문의해 주세요.')]:
    source=ROOT/path;lines=source.read_text(encoding='utf-8').splitlines();match=next((i,s) for i,s in enumerate(lines,1) if needle in s)
    by_id[id]['evidence'].append(dict(path=path,line=match[0],excerpt=match[1],sha256=hashlib.sha256(source.read_bytes()).hexdigest(),observed_at=STAMP))

# Current architecture evidence: preserve old quotations as dated evidence.
for path, needle in [
    ('final_project_cs/app/application/controller.py', 'self.team_executor.execute(task)'),
    ('final_project_cs/app/core/registry.py', 'def resolve('),
    ('final_project_cs/app/core/remote_team/executor.py', 'return await entry.module.execute(task)'),
    ('final_project_cs/app/domains/travel_ops/components/watch/trip_watch_cases.py', 'def _open_batch('),
    ('final_project_cs/app/domains/travel_ops/components/watch/trip_watch_batch.py', 'return watch_planners.planner(kind)'),
    ('final_project_cs/app/domains/travel_ops/components/team_hooks/watch_planners.py', 'def planner('),
    ('final_project_cs/app/domains/travel_ops/instances/_shared/itinerary_team.py', 'return WatchBatch(self, task, ctx).run()')]:
    source=ROOT/path; lines=source.read_text(encoding='utf-8').splitlines()
    number, excerpt=next((i,s) for i,s in enumerate(lines,1) if needle in s)
    by_id['W08']['evidence'].append(dict(path=path,line=number,excerpt=excerpt,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),observed_at=STAMP))

# Explain actors in prose; retain contract identifiers and historical evidence.
for finding in PLANS:
    for field in ['title','decision','replacement']:
        finding[field]=finding[field].replace('Team은','에이전트 팀은').replace('Team이','에이전트 팀이').replace('Team 안내','에이전트 팀 안내')
    for field in ['steps','checks']:
        finding[field]=[s.replace('Team은','에이전트 팀은').replace('Team이','에이전트 팀이').replace('Core에 전달','Controller에 전달').replace('Core 책임 역할','플랫폼 코어 개발 역할') for s in finding[field]]

TERMS = [
 ['에이전트 팀 · instances','Activity(활동)·Dining(식당)·Mobility(이동) 같은 업무 처리 단위입니다. 개발 팀원 조직과 구분합니다.'],
 ['Controller','사건 처리 흐름을 관리합니다. TeamRegistry에 담당 팀을 묻고 TeamExecutorPort에 실행을 요청합니다. 결과·변경 제안을 검증하고 등록된 적용기로 반영합니다.'],
 ['TeamRegistry · 문서의 Registry','사건 종류·요청 종류와 활성 등록 내용을 대조해 담당 에이전트 팀을 찾습니다. 팀을 실제 실행하는 객체는 아닙니다.'],
 ['TeamExecutorPort · LocalTeamExecutor','TeamExecutorPort는 팀 실행 계약입니다. LocalTeamExecutor는 등록된 에이전트 팀의 execute를 호출하는 구현입니다.'],
 ['여행 상태 점검 · components/watch','날씨·교통·장소 운영정보 등을 확인해 여행 일정에 문제가 생겼는지 검사합니다. 여기서 감지는 문제 발견을 뜻하고, 팀의 변경 계산·저장과는 단계가 다릅니다.'],
 ['같은 여행의 여러 일정 문제 함께 처리 · WatchBatch','한 번의 여행 상태 점검에서 새로 발견한 여러 문제를 같은 초안 위에서 처리합니다. Activity 에이전트 팀이 조정하며 활동→식당→이동 순서로 계산합니다.'],
 ['watch_planners · team_hooks','각 에이전트 팀이 조립 때 등록한 항목별 계산을 찾는 연결 지점입니다. WatchBatch가 이 계산을 사용합니다. 다른 팀의 execute를 연쇄 호출하는 것과 구분합니다.'],
 ['개발자·QA 모니터링 도구','오류·지연·처리 상태·영향 고객 등을 관측하고 사후 분석하는 도구·화면입니다. 위의 여행 상태 점검이나 WatchBatch라는 처리 기능과 구분해 적습니다.']
]
TERMS_EXAMPLE = '예: 같은 점검에서 관광지 폐쇄와 식당 휴무가 발견되면, 함께 처리하는 스위치와 항목 수 제한 안에서 사건 하나로 모읍니다. 활동 변경을 반영한 초안으로 식당·이동을 계산하고 전체 일정을 재검증합니다. 자동 적용 가능한 변경은 새 일정 버전·변경 알림 각각 하나로 모읍니다. 고객 확인이 필요한 질문은 항목마다 따로 보냅니다.'

SOURCES = {
 'session':('OWASP 세션 관리','https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html','브라우저 세션 속성·수명·폐기와 세션 식별자 보호의 근거. triPilot의 7일·90일을 정한 표준은 아닙니다.'),
 'authorization':('OWASP 권한 검사','https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html','최소 권한·기본 거부·매 요청 자원 권한 검사. 인증 수단과 편집 권한을 구분하는 근거입니다.'),
 'mcp':('MCP 인증 사양 2026-07-28','https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization','HTTP MCP 인증과 대상 자원·인가 흐름의 근거. 현재 키 방식이 OAuth 구현 완료라는 뜻은 아닙니다.'),
 'logging':('OWASP 로그 기록','https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html','오류·상관 식별자와 민감값 제외·접근 통제·기록 실패 검사. 제안한 보존 일수를 규정하지 않습니다.'),
 'bulkhead':('Microsoft 장애 격리 패턴','https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead','일부 장애가 다른 처리로 번지는 범위를 제한하는 설계 근거입니다.'),
 'circuit':('Microsoft 회로 차단 패턴','https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker','지속 실패하는 외부 의존성의 반복 호출을 제한하고 복구를 확인하는 근거입니다.'),
 'retry':('Microsoft 재시도 패턴','https://learn.microsoft.com/en-us/azure/architecture/patterns/retry','일시 오류와 영구 오류 구분·제한된 재시도·중복 실행 위험을 검토하는 근거입니다.'),
 'queue':('Microsoft 대기열 부하 완충','https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling','처리량 급증을 대기열과 제한된 작업자로 흡수하는 근거입니다. 특정 고객 수 기준을 제시하지 않습니다.')
}

AUTH = [
 ['고객 웹 회원','HttpOnly 쿠키 + 변경 요청 CSRF','본인 여행 조회·수정·설정, 계정·키 관리','기존 계약: 유휴 7일·절대 30일. 설정과 실제 적용은 재확인','구현 기록 있음; 이번 실행·배포 미확인'],
 ['고객 웹 게스트','브라우저 세션 쿠키','여행 1개·감시 불가·계획서 내려받기','쿠키 수명과 데이터 보존은 별개. 데이터 기본 7일·미래 일정 예외','구현 기록 있음; 회원 전환/이관 계약 있음'],
 ['개인 AI 에이전트','별도 에이전트 키','본인 여행 read/write. 계정·키 관리 금지','기본/최대 90일·개별 폐기·해시 저장','REST에 구현·시험 기록, D-CS-012 상태 문구 갱신 필요'],
 ['공유 계획서 독자','여행별 공유 토큰','해당 계획서 읽기만. 회원 편집 권한 없음','개선 제안: 공유 중지·재발급, 종료+7일/자료 만료 중 이른 때. 초기 정책값','생성 모듈은 HMAC, 자체 만료/개별 폐기 정보 없음. 전체 경로·배포 확인은 별도'],
 ['외부 시스템 연동 주체','테넌트 연동 키 + require_scope','승인된 테넌트 연동 작업만','고객용 에이전트 키와 분리해 기존 정책 확인','기존 경로 있음; 확장 제공 범위는 별도'],
 ['향후 개인 AI OAuth','로그인·동의 → OAuth 토큰','에이전트 키와 같은 여행 권한 정책','코드/access/refresh 제안값은 구현 전 정책','설계 단계. 이번 출시 필수로 추가하지 않음']
]

INCIDENT = [
 ['결함 묶음','fingerprint, error_code, component, operation, first_seen, last_seen, count, status, fixed_revision','지문은 오류 유형·컴포넌트·호출 작업·정규화한 원인으로 구성. 고객 ID를 지문에 넣지 않습니다.'],
 ['발생·영향 기록','occurrence_id, fingerprint, occurred_at, tenant_id, customer_id, trip_id, item_id, trace_id, build_version, policy_version, source, retry_count, result','고객·여행 ID는 가명 식별자여도 개인정보 관련 값입니다. 내부 권한으로만 조회하고 중복 수집은 occurrence_id로 막습니다.'],
 ['장소 미매칭','고객 입력명·주소 조각·검색 조건·검색 결과 ID·고객 보완 결과','주소·문장에 개인정보가 섞이면 마스킹합니다. 고객 입력을 검증 없이 공용 장소 목록에 반영하지 않습니다.'],
 ['고객 건의','건의 유형·마스킹한 내용·관련 여행/기능·접수 시각','장애 기록과 분리합니다. 건의 접수를 상담원 응답 보장이나 처리 완료로 표시하지 않습니다.'],
 ['보존·조회 제안','상세 30일·집계 90일, 설정으로 관리; 개발자·QA 조회 감사 기록','초기 정책 제안이며 법적 의무나 실측 최적값이 아닙니다. 기존 보존 정책과 정합성 확인 후 적용하고 이번에 데이터를 삭제하지 않습니다.'],
 ['금지 기록','키·쿠키·토큰·웹훅 주소·원문 인증 헤더·불필요한 고객 원문','오류 화면에는 고객용 코드와 다음 행동만 제공합니다. 스택과 내부 연결 정보는 노출하지 않습니다.'],
 ['진단 저장 장애','발생 ID를 유지한 제한된 로컬 영속 대기 파일·전송 상태·유실 건수','복구 후 중복 없이 전송합니다. 둘 다 저장 실패하면 수집 저하를 표시하며 영속 기록을 보장했다고 세지 않습니다.']
]

SCALE = [
 ['지금','기존 DB의 구조화한 결함·발생·영향 기록 + 기존 작업자','이름만 있는 새 고객 지원 부서를 만들지 않습니다. 저장·조회 기능은 신규 구현 계획입니다.'],
 ['수집 작업자 분리','기록 쓰기 p95 100ms 초과 또는 배경 대기 p95 60초 초과가 15분 지속','초기 운영 가정값입니다. 부하 시험으로 조정합니다. 오류 때문에 고객 요청이 그만큼 느려지는지 먼저 측정합니다.'],
 ['반복 오류 폭주 억제','같은 결함 상세는 시간창별 대표 표본, 건수·영향 고객은 정확히 유지','안전 사건은 일반 건의와 우선순위를 분리합니다. 수집 대기열은 상한·유실 감지·재전송 중복 방지가 필요합니다.'],
 ['DB 저장 구조 확장','보존 정리 지연·색인 조회 지연·쓰기 병목이 목표를 지속 위반','그때 시간별 분할/저장소 분리를 검토합니다. 고객 수만으로 Kafka·분산 서비스 도입을 결정하지 않습니다.'],
 ['수정 후 재처리','최신 일정·고객 설정·유효한 자료로 재검증한 작업만','개발자·QA가 고객 일정 DB를 직접 수정하지 않습니다. 결함 해결과 고객 여행 처리 완료는 따로 기록합니다.']
]

FAILURE = [
 ['필수 기반 실패','DB·인증·tenant 격리 보장 불가','해당 준비 상태/쓰기 기능 실패. 성공 응답 금지','기반 복구·무결성 확인 후 재개'],
 ['외부 조회 일시 실패','시간 초과·일시적인 제한','횟수/시간 예산 내 재시도 → 대체 자료 → 실패한 변경 보류','회로 시험 호출 성공 후 최신 판 재검증'],
 ['외부 조회 지속 실패','대체 자료까지 확보 불가','기존 일정 유지 + 검증 불가 상태·확인 시각·오류 코드. 자료를 지어내지 않음','자료 회복 후 모드·고정 조건 재확인'],
 ['고객 입력 부족','장소 미매칭·필수 날짜 없음','검증한 추천 후보와 구체적 입력 필드 제공. 기존 입력 보존','고객 보완 후 다시 검증'],
 ['감시 일부 실패','한 항목만 조회/대안 실패','실패 항목 유지, 독립적으로 검증 가능한 나머지 항목 계속','여행 전체 정합성 검증 후 적용'],
 ['재난·안전 정지','기존 안전 정책의 정지 조건','해당 일정 정지 + 공식 안내. 일반 장애 재시도로 재개하지 않음','고객의 명시적인 일정 재개']
]

def backup_write(path, text):
    if path.exists():
        folder=OUT/'_backup'/(datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S_%f')+'_v2-regenerate')
        folder.mkdir(parents=True,exist_ok=True);shutil.copy2(path,folder/path.name)
    path.write_text(text,encoding='utf-8',newline='\n')

def link(path,label=None):
    return '<a href="'+h(Path(os.path.relpath(ROOT/path,OUT)).as_posix(),quote=True)+'">'+h(label or path)+'</a>'

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+h(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+h(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def diagram():
    # One episode ends; a new user input or recovery starts a new episode.
    return '''<svg viewBox="0 0 720 832" role="img" aria-labelledby="auto-flow-title auto-flow-desc"><title id="auto-flow-title">자동 해결과 고객 보완 입력의 처리 순서</title><desc id="auto-flow-desc">자동 해결이 가능하면 검증한 변경을 적용하고, 불가능하면 고객 보완 입력을 안내합니다. 두 결과는 고객 응답으로 끝나며 오류 기록은 개발자와 QA가 사후 분석합니다.</desc><defs><marker id="auto-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#6b7488"/></marker></defs><g fill="none" stroke="#6b7488" stroke-width="1.2" marker-end="url(#auto-arrow)"><path d="M360 80V120"/><path d="M360 184V224"/><path d="M248 288H168Q160 288 160 296V384"/><path d="M472 288H552Q560 288 560 296V384"/><path d="M160 448V488Q160 496 168 496H324Q332 496 332 504V536"/><path d="M560 448V488Q560 496 552 496H396Q388 496 388 504V536"/><path d="M360 600V648"/></g><g fill="#fbfcfd"><rect x="180" y="256" width="48" height="24"/><rect x="492" y="256" width="64" height="24"/></g><g font-size="16" fill="#161c28" text-anchor="middle"><text x="204" y="272">가능</text><text x="524" y="272">불가능</text></g><g stroke="#161c28" stroke-width="1.2" fill="#fff"><ellipse cx="360" cy="48" rx="144" ry="32"/><rect x="184" y="120" width="352" height="64" rx="6"/><path d="M360 224L472 288L360 352L248 288Z"/><rect x="24" y="384" width="272" height="64" rx="6"/><rect x="424" y="384" width="272" height="64" rx="6"/><rect x="184" y="536" width="352" height="64" rx="6"/><ellipse cx="360" cy="680" rx="144" ry="32"/></g><g font-size="20" font-weight="600" fill="#161c28" text-anchor="middle"><text x="360" y="56">고객 요청·감시 시작</text><text x="360" y="160">자료 확인·제한된 자동 복구</text><text x="360" y="296">자동 해결 가능?</text><text x="160" y="424">검증 후 고객 모드대로 처리</text><text x="560" y="424">원인별 안내·추천 제공</text><text x="360" y="576">처리 결과·오류 코드 기록</text><text x="360" y="688">고객에게 결과 제공·종료</text></g><line x1="24" x2="696" y1="752" y2="752" stroke="#dbe0ea"/><g fill="#6b7488" font-size="16"><text x="24" y="784">타원: 시작·종료</text><text x="260" y="784">사각형: 처리</text><text x="496" y="784">마름모: 판단</text></g></svg>'''

css='''*{box-sizing:border-box}body{margin:0;background:#fbfcfd;color:#161c28;font-family:Geist,'Noto Sans KR','Malgun Gothic',sans-serif;line-height:1.75;font-size:16px}main{max-width:1100px;margin:auto;padding:40px 28px 80px}h1{font-family:'Instrument Serif','Noto Serif KR',serif;font-size:34px;font-weight:400;line-height:1.4}h2{font-size:24px;margin-top:36px}h3{font-size:21px;line-height:1.5}p{max-width:86ch}a{color:#2f5bd8;overflow-wrap:anywhere}header{border-bottom:2px solid #161c28;padding-bottom:16px}.muted{color:#546075;font-size:14px}.note,.adopt{border-left:3px solid #a8720c;background:#f7f2e8;padding:12px 16px}.finding{border-top:1px solid #dbe0ea;padding-top:16px;margin-top:32px;scroll-margin-top:16px}.options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;border:0;padding:0;margin:16px 0}.option{border:1px solid #cbd2df;border-radius:6px;padding:12px;cursor:pointer;min-width:0}.option:has(input:checked){border:2px solid #a8720c;padding:11px;background:#f7f2e8}.option strong{display:block}.option p{font-size:14px;margin:8px 0 0}.option input{accent-color:#a8720c;margin-right:8px}.badge{font-size:13px;font-weight:600;color:#6b4807}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:16px 0;table-layout:fixed}th,td{border-bottom:1px solid #dbe0ea;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere;font-size:14px}blockquote{margin:12px 0;padding:12px 16px;border-left:3px solid #2f5bd8;background:#f1f4f8}details{margin:16px 0}summary{cursor:pointer;font-weight:600}.targets{font-size:14px}nav ul{columns:2;padding-left:22px}nav li{break-inside:avoid}.tools{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}button{font:inherit;border:1px solid #cbd2df;background:#fff;padding:8px 12px;border-radius:4px;cursor:pointer;color:#161c28}button:hover{border-color:#2f5bd8}:focus-visible{outline:3px solid #2f5bd8;outline-offset:3px}.flow{max-width:720px;margin:16px auto}svg{width:100%;height:auto}li{margin:6px 0}.check-list{list-style:'□  '}.evidence{font-size:14px;padding:8px;background:#f1f4f8;margin:8px 0;overflow-wrap:anywhere}footer{border-top:1px solid #dbe0ea;margin-top:36px;padding-top:16px;font-size:14px}.selection-note{font-size:14px;min-height:24px}@media(max-width:700px){main{padding:24px 16px 56px}h1{font-size:28px}.options{grid-template-columns:1fr}nav ul{columns:1}table{min-width:640px}.progress table{min-width:0}th,td{padding:8px}svg text{font-family:'Malgun Gothic',sans-serif}}@media print{main{padding:0;max-width:none}.tools,nav,.selection-note{display:none}.options{grid-template-columns:repeat(3,minmax(0,1fr))}.table-wrap{overflow:visible}table{min-width:0}.finding{break-before:auto}.option{break-inside:avoid}details{display:block}svg{max-height:640px}.flow{max-width:500px}a{color:inherit}}'''

def team_call_diagram():
    # Normal execution path only. Error handling remains in W05/W06.
    return '''<svg viewBox="0 0 660 832" role="img" aria-labelledby="team-call-title team-call-desc"><title id="team-call-title">담당 에이전트 팀 선택·실행·변경 반영</title><desc id="team-call-desc">Controller가 TeamRegistry로 담당 팀을 찾고 실행 계약으로 호출하며, 에이전트 팀의 반환 제안은 Controller와 등록된 적용기가 검증하고 반영합니다.</desc><defs><marker id="team-call-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#6b7488"/></marker></defs><g fill="none" stroke="#6b7488" stroke-width="1.2" marker-end="url(#team-call-arrow)"><path d="M332 96V128"/><path d="M332 224V256"/><path d="M332 352V384"/><path d="M332 480V512"/><path d="M332 608V640"/></g><g fill="#fff" stroke="#161c28" stroke-width="1.2"><ellipse cx="332" cy="64" rx="220" ry="32"/><rect x="48" y="128" width="568" height="96" rx="6"/><rect x="48" y="256" width="568" height="96" rx="6"/><rect x="48" y="384" width="568" height="96" rx="6"/><rect x="48" y="512" width="568" height="96" rx="6"/><ellipse cx="332" cy="672" rx="220" ry="32"/></g><g font-family="Geist,'Malgun Gothic',sans-serif" font-size="24" text-anchor="middle" fill="#161c28"><text x="332" y="72">사건(Case) 생성 · 시작</text><text x="332" y="168">Controller → TeamRegistry</text><text x="332" y="204">담당 에이전트 팀 선택</text><text x="332" y="296">TeamExecutorPort.execute</text><text x="332" y="332">구현 예: LocalTeamExecutor</text><text x="332" y="424">선택한 에이전트 팀 실행</text><text x="332" y="460">계산 결과·변경 제안 반환</text><text x="332" y="552">Controller → 등록된 적용기</text><text x="332" y="588">제안 검증·허용된 변경 저장</text><text x="332" y="680">결과 기록 · 이번 처리 종료</text></g><line x1="48" x2="616" y1="752" y2="752" stroke="#dbe0ea"/><g font-size="20" fill="#6b7488"><text x="48" y="792">타원: 시작·종료</text><text x="360" y="792">사각형: 처리</text></g></svg>'''

def render():
    cli_path=OUT/'claude-review/review-response-v2.json'
    cli_ok=False;model='';review=''
    if cli_path.exists():
        wrap=json.loads(cli_path.read_text(encoding='utf-8'))
        try:
            raw=json.loads(wrap.get('stdout','{}'));review=raw.get('result','');model=', '.join(raw.get('modelUsage',{}));cli_ok=wrap.get('returncode')==0 and not raw.get('is_error',False) and bool(review) and 'claude-sonnet-5-5' in model
        except (ValueError,TypeError): pass
    round2=OUT/'claude-review/review-response-r2.json'
    second_ok=False
    if round2.exists():
        rw=json.loads(round2.read_text(encoding='utf-8'))
        try:
            rs=json.loads(rw.get('stdout','{}'));second_ok=rw.get('returncode')==0 and not rs.get('is_error',False) and bool(rs.get('result')) and 'claude-sonnet-5-5' in rs.get('modelUsage',{})
        except (ValueError,TypeError): pass
    consult=('Claude Code CLI · Claude Sonnet 5.5(claude-sonnet-5-5)와 '+('두 차례' if second_ok else '한 차례')+' 검토했습니다. 합의한 설계 방향과 Codex가 추가로 정한 세부 정책을 반영 판단 기록에서 구분했습니다.') if cli_ok else 'Claude Sonnet 5.5 검토 요청을 보냈으나 정상 응답 확인 전입니다. 공동 검토 완료로 표시하지 않습니다.'
    html='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>triPilot wiki 수정 계획 v2 · 선택지와 추천안</title><style>'+css+'</style></head><body><main>'
    html+='<header><p class="muted">triPilot · 현재 기준 정리 · 2026-10-11 · 수정 계획 v2</p><h1>wiki를 어떻게 고칠지 정했습니다.</h1><p>항로 지킴이는 자동 변경, 고객 대응은 자동 처리와 직접 보완 입력으로 정리합니다. 나머지는 각 항목의 A안을 기본으로 채택합니다.</p></header>'
    html+='<div class="progress">'+table(['할 일','상태','진행'],[['검토 항목의 수정 계획','작성','25/25 = 100%'],['항목별 선택지·추천안','작성','25/25 = 100%'],['전체 wiki 본문 정독','기존 확인 범위','31/284 = 10.9%'],['wiki 본문·제품 코드 적용','이 문서와 구분','이번 산출물은 적용 계획; 완료 수에 포함하지 않음']])+'</div>'
    html+='<p class="note"><strong>읽는 법</strong> — 각 항목에서 결론 → A/B/C 비교 → 실제 수정 문장과 완료 검사를 보시면 됩니다. 선택하지 않으면 A안입니다. 화면 선택은 이 기기의 검토 표시이며 wiki나 제품 설정을 바꾸지 않습니다. 말씀하신 자동 운영 방향은 선택지와 무관하게 유지합니다.</p>'
    html+='<div class="tools"><button id="export" type="button">선택 결과 보기</button><button id="reset" type="button">모든 항목을 추천안으로 되돌리기</button><button id="print" type="button">검토안 인쇄하기</button></div><p class="selection-note" id="selection-status" aria-live="polite"></p><div id="export-panel" hidden><label for="export-text">복사해서 전달할 선택 결과 · 화면 선택만으로 wiki가 바뀌지는 않습니다.</label><textarea id="export-text" readonly rows="12" style="width:100%;font:inherit"></textarea></div>'
    html+='<section id="architecture-terms"><h2>에이전트 팀을 누가 부르고, 무엇을 점검하나</h2><p><strong>이 문서의 팀은 에이전트 팀입니다.</strong> 호출 담당은 Controller, 담당 선택은 TeamRegistry, 실제 실행 경계는 TeamExecutorPort입니다. “코어”는 이 장치들을 포함한 공통 계층의 이름이므로 호출 주체를 설명할 때 대신 쓰지 않습니다.</p>'+table(['정확한 이름','하는 일'],TERMS)+'<p class="note"><strong>“감시 묶음”을 고쳤습니다.</strong> 이 문서가 가리킨 것은 여행 상태 점검에서 발견한 여러 일정 문제를 함께 처리하는 WatchBatch입니다. 여행 상태 점검 기능·에이전트 팀의 계산·개발자/QA 모니터링 도구를 구분해 적습니다.</p><p>'+h(TERMS_EXAMPLE)+'</p><p class="targets">근거: '+link('final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md','라우팅 결정')+' · '+link('final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md','에이전트 팀·등록 계산 구조')+' · '+link('wiki/decisions/D-017-watch-cadence-golden-time.md','여행 문제 공동 처리 결정')+' · <a href="#W08">현재 코드 위치와 제한</a></p><details open><summary>정상 실행 경로 · 정확한 장치 이름</summary><figure class="flow team-call-flow">'+team_call_diagram()+'<figcaption>정상 실행·반영 경로입니다. 고객 선택 대기와 실패 처리는 W03·W05·W06을 따릅니다. WatchBatch 내부에서 등록된 계산을 사용하는 것과 Controller가 에이전트 팀을 실행하는 것은 다른 경로입니다. 이 그림은 이번에 앱 실행을 검증했다는 뜻이 아닙니다.</figcaption></figure></details></section>'
    html+='<h2>이번 의견을 반영한 핵심 수정</h2><ul><li><a href="#W02">웹 화면·개인 AI 연동·공유 계획서의 역할</a>을 이름과 기능으로 설명합니다.</li><li><a href="#W03">항로 지킴이 자동 변경</a>과 고정 일정·재난의 예외를 같은 표로 정리합니다.</li><li><a href="#W04">인증·권한</a>은 기존 구조를 유지하고, <a href="#W05">개발자·QA 기록</a>은 실시간 고객 처리와 분리합니다.</li><li><a href="#W06">조회 실패</a>는 해당 기능에서 격리하고 복구합니다.</li></ul>'
    html+='<details><summary>자동 처리와 고객 보완 입력의 흐름</summary><figure class="flow">'+diagram()+'<figcaption>처리 불가가 고객 입력 부족이면 보완 입력을 요청합니다. 외부 조회 장애이면 변경 보류·복구 안내를 제공합니다. 오류 기록은 개발자·QA가 사후 분석하며 고객 처리의 대기 조건이 아닙니다. 재난 일정 정지는 별도 안전 정책을 따릅니다.</figcaption></figure></details>'
    html+='<h2>Claude 검토와 근거</h2><p>'+h(consult)+'</p><p class="muted">공식 자료는 인증·권한·로그·장애 격리 원칙의 근거입니다. 자동 여행 변경 범위, 후보 개수, 보존 일수, 확장 기준 수치는 우리 제품 정책·초기 제안이며 표준의 의무값이 아닙니다.</p><details><summary>논의 원문·반영 판단</summary><ul><li><a href="claude-review/review-request-v1.txt">Claude에 전달한 사실과 요청</a></li>'
    if cli_path.exists(): html+='<li><a href="claude-review/review-response-v2.md">Claude 응답 원문</a></li>'
    if second_ok: html+='<li><a href="claude-review/review-response-r2.md">Claude 2차 검토 원문</a></li>'
    if (OUT/'claude-review/decision-v2.md').exists():html+='<li><a href="claude-review/decision-v2.md">채택·수정·남은 한계</a></li>'
    html+='</ul></details><nav aria-label="수정 항목"><h2>수정 계획 25개</h2><ul>'+''.join('<li><a href="#'+x['id']+'">'+x['id']+' · '+h(x['title'])+'</a></li>' for x in PLANS)+'</ul></nav>'
    for x in PLANS:
        html+='<article class="finding" id="'+x['id']+'"><p class="badge">'+('사용자 방향 확정 · 세부 방식 A안 기본' if x['fixed'] else '추천 A안 기본 채택')+'</p><h2>'+x['id']+' · '+h(x['title'])+'</h2><p class="adopt">'+h(x['decision'])+'</p><fieldset class="options"><legend>수정 방식 선택 · 미선택 시 A안</legend>'
        for c in x['options']:
            html+='<label class="option"><strong><input type="radio" name="'+x['id']+'" value="'+c['id']+'" '+('checked' if c['recommended'] else '')+'>'+c['id']+' · '+h(c['title'])+(' <span class="badge">추천</span>' if c['recommended'] else '')+'</strong><p>'+h(c['effect'])+'</p></label>'
        html+='</fieldset><details'+(' open' if x['id'] in ['W02','W03','W04','W05','W06','W08'] else '')+'><summary>A안의 실제 수정 작업</summary><ol>'+''.join('<li>'+h(s)+'</li>' for s in x['steps'])+'</ol><p><strong>대체할 핵심 문장</strong></p><blockquote>'+h(x['replacement'])+'</blockquote><p class="targets"><strong>수정할 문서·후속 구현 대상</strong><br>'+' · '.join(link(t) for t in x['targets'])+'</p><p><strong>끝났다고 판단할 검사</strong></p><ul class="check-list">'+''.join('<li>'+h(c)+'</li>' for c in x['checks'])+'</ul></details>'
        if x['id']=='W03':html+='<details open><summary>항로 지킴이 처리표</summary>'+table(['상황','처리'],[['켜짐 + 일반 사건','검증한 변경 자동 적용 → 결과·이유·되돌리기 제공'],['꺼짐 + 일반 사건','검증한 대체안 제시 → 고객 선택 후 적용'],['고정한 일정','고객 확인 전 유지; 감지·알림은 계속'],['재난 정지 조건','일정 정지 + 공식 안내; 고객 명시 재개'],['업체 예약·결제','일정 DB 변경과 별개. 자동 변경 권한으로 실행하지 않음'],['설문 미응답 옛 여행','기본안: 꺼짐·제안. 실제 경로 검사와 기존 데이터 호환성 확인 후 적용']])+'</details>'
        if x['id']=='W04':html+='<details open><summary>인증·권한·현재 상태</summary>'+table(['이용 주체','인증','허용 작업','수명·폐기','확인 상태'],AUTH)+'<p>에이전트 팀이 필요한 사건 처리 경로는 인증·소유자 검사 → Controller → TeamRegistry의 담당 선택 → TeamExecutorPort의 팀 실행 → Controller의 제안 검증·등록된 적용기 실행 순서입니다. 계정·키 관리나 단순 조회를 모두 이 경로로 보내는 것은 아닙니다. 토큰 원문은 LLM에 전달하지 않습니다. 공유 토큰의 읽기 권한과 소유자의 수정 권한을 구분합니다.</p></details>'
        if x['id']=='W05':html+='<details open><summary>개발자·QA가 나중에 볼 기록</summary>'+table(['기록 종류','최소 항목','통제·주의'],INCIDENT)+'</details><details open><summary>고객이 늘 때의 확장 조건</summary>'+table(['단계','구현·도입 조건','판정 근거·한계'],SCALE)+'</details><p><strong>고객 화면 예시</strong> — “장소를 확정하지 못했습니다. 확인된 후보 중 ○○를 추천합니다. 다른 장소라면 주소나 지도 링크를 입력해 주세요. 오류 코드: PLACE_NOT_MATCHED.” 후보가 없으면 장소를 지어내지 않고 입력 방법을 제공합니다. 오류 코드·문구는 신규 계약 제안입니다.</p>'
        if x['id']=='W06':html+='<details open><summary>실패 범위와 재개 조건</summary>'+table(['실패 종류','예','현재 처리','재개 조건'],FAILURE)+'<p>재시도 횟수·시간 예산은 기존 설정을 먼저 확인해 한 곳에 둡니다. 이번 문서에서 근거 없는 공통 횟수나 서비스 수준 보장을 만들지 않습니다.</p></details>'
        html+='<details><summary>기존 문제의 근거'+(' · 공식 설계 근거' if x['basis'] else '')+'</summary>'
        for e in x['evidence']:
            html+='<div class="evidence">'+link(e['path'],e['path']+':'+str(e['line']))+'<br>'+h(e['excerpt'])+'</div>'
        html+='<p class="muted">위 인용은 각 검토 시점의 문장입니다. v2에서 확인한 코드 근거에는 확인 시각과 해시를 별도로 기록했습니다. 실제 수정 직전에 파일과 줄을 다시 확인합니다.</p>'
        for key in x['basis']:
            label,url,scope=SOURCES[key];html+='<p><a href="'+h(url,quote=True)+'">'+h(label)+'</a> — '+h(scope)+'</p>'
        html+='</details></article>'
    html+='<h2>반영 순서와 완료 범위</h2><ol><li>현재 정본·제품 범위·항로 지킴이·인증·자동 운영·장애 정책의 wiki 계약을 먼저 수정합니다.</li><li>계약과 다른 코드·시험·검사 도구를 각각 수정하고, 실행 증거로 구현 상태를 갱신합니다.</li><li>나머지 wiki 본문을 읽고 충돌을 재검사한 뒤 v12 안내서와 프로젝트 기준선 파일을 만듭니다.</li></ol><p>이 파일은 25개 문제의 수정 실행 계획입니다. wiki 전체 정독, 제품 코드 반영, DB 변경, 원격 배포, 출시 판정까지 완료했다는 보고가 아닙니다. 이번에 선택한 기본안은 계획에 반영했으며 파일 삭제·외부 게시·배포는 수행하지 않았습니다.</p>'
    html+='<footer><p>작성 '+h(STAMP)+' · v1 원문과 생성 스크립트는 _backup에 보관했습니다. 외부 폰트·라이브러리 없이 열립니다.</p><p><a href="wiki-review-v2.md">문자 문서</a> · <a href="findings-v2.json">수정 계획 데이터</a> · <a href="wiki-review-v1.html">이전 검토본</a> · <a href="reading-coverage-v1.json">전체 정독 확인 범위</a></p></footer>'
    html+='''</main><script>
const key='tripilot-wiki-review-v2-selections';
const form=[...document.querySelectorAll('input[type=radio]')];
const defaults=()=>Object.fromEntries([...new Set(form.map(x=>x.name))].map(k=>[k,'A']));
function selected(){return Object.fromEntries(form.filter(x=>x.checked).map(x=>[x.name,x.value]));}
function notify(){const n=Object.values(selected()).filter(x=>x!=='A').length;document.getElementById('selection-status').textContent=n?`추천안과 다른 선택 ${n}/25개. A안의 상세 작업은 비교용으로 계속 표시됩니다. 선택 결과를 복사해서 전달해 주세요.`:'25/25개 모두 추천 A안입니다. 별도 선택이 없으면 이 계획으로 진행합니다.';document.getElementById('export-panel').hidden=true;}
try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved)form.forEach(x=>{if(['A','B','C'].includes(saved[x.name]))x.checked=saved[x.name]===x.value;});}catch(e){}
form.forEach(x=>x.addEventListener('change',()=>{try{localStorage.setItem(key,JSON.stringify(selected()));}catch(e){}notify();}));
document.getElementById('reset').addEventListener('click',()=>{form.forEach(x=>x.checked=x.value==='A');try{localStorage.removeItem(key);}catch(e){}notify();});
document.getElementById('export').addEventListener('click',()=>{const data={document:'triPilot wiki review v2',selected_at:new Date().toISOString(),defaults:defaults(),selections:selected(),scope:'review choices only; no wiki or product mutation'};document.getElementById('export-panel').hidden=false;const text=document.getElementById('export-text');text.value=JSON.stringify(data,null,2);text.focus();text.select();});
document.getElementById('print').addEventListener('click',()=>{document.querySelectorAll('details').forEach(d=>d.open=true);window.print();});
notify();
</script></body></html>'''
    for x in PLANS:x['status']='수정 계획 기본안 채택; wiki·코드 적용 상태와 별개'
    backup_write(OUT/'wiki-review-v2.html',html)
    backup_write(OUT/'findings-v2.json',json.dumps(dict(updated_at=STAMP,default='A',claude_verified=cli_ok,claude_rounds=2 if second_ok else int(cli_ok),claude_model=model,scope='review plan only',findings=PLANS,sources=SOURCES,architecture_terms=TERMS,architecture_example=TERMS_EXAMPLE,terminology_review='2026-10-11; local decisions and code review; Claude rounds predate this wording correction'),ensure_ascii=False,indent=2))
    md='# triPilot wiki 수정 계획 v2\n\n항로 지킴이 자동 변경·상담원 없는 자동 운영을 반영했습니다. 별도 선택이 없으면 각 항목 A안을 기본 채택합니다. 이 문서는 실행 계획이며 wiki·코드·배포 완료 보고가 아닙니다.\n\n'+consult+'\n'
    md+='\n## 에이전트 팀 호출과 여행 상태 점검 용어\n\n팀은 에이전트 팀을 뜻합니다. 코어라는 계층 이름을 호출 담당의 이름 대신 쓰지 않습니다.\n\n| 정확한 이름 | 하는 일 |\n|---|---|\n'+''.join('| '+name+' | '+meaning+' |\n' for name,meaning in TERMS)+'\n'+TERMS_EXAMPLE+'\n\n이번 용어 정정은 개정 결정과 로컬 코드 대조 결과이며 앞선 Claude 두 차례 검토 이후에 수행했습니다.\n'
    for x in PLANS:
        md+='\n## '+x['id']+' · '+x['title']+'\n\n'+x['decision']+'\n\n'
        for c in x['options']:md+='- '+c['id']+' '+c['title']+(' **추천·기본**' if c['recommended'] else '')+' — '+c['effect']+'\n'
        md+='\n수정 작업:\n\n'+'\n'.join(f'{i+1}. {s}' for i,s in enumerate(x['steps']))+'\n\n대체 문장:\n\n> '+x['replacement']+'\n\n수정 대상:\n\n'+'\n'.join('- ['+t+']('+str(ROOT/t).replace('\\','/')+')' for t in x['targets'])+'\n\n완료 검사:\n\n'+'\n'.join('- [ ] '+c for c in x['checks'])+'\n'
    for title,headers,rows in [('인증·권한',['주체','인증','권한','만료·폐기','상태'],AUTH),('결함 기록',['종류','항목','주의'],INCIDENT),('규모 확장',['단계','조건','한계'],SCALE),('장애 정책',['종류','예','처리','재개'],FAILURE)]:
        md+='\n## '+title+'\n\n| '+' | '.join(headers)+' |\n|'+'---|'*len(headers)+'\n'+''.join('| '+' | '.join(str(v).replace('|','/') for v in row)+' |\n' for row in rows)
    md+='\n## 공식 근거와 적용 범위\n\n'+''.join('- ['+label+']('+url+') — '+scope+'\n' for label,url,scope in SOURCES.values())+'\n전체 본문 정독 확인 범위는 기존 31/284개입니다. 최신 원격 상태·DB 적용·제품 기능 시험은 이번 문서 수정에서 확인하지 않았습니다.\n'
    backup_write(OUT/'wiki-review-v2.md',md)
    print(json.dumps(dict(html=str(OUT/'wiki-review-v2.html'),plans=len(PLANS),options=sum(len(x['options']) for x in PLANS),claude_verified=cli_ok),ensure_ascii=False))

if __name__=='__main__': render()
