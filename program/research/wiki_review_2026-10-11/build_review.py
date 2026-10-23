from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from html import escape
import json, re, hashlib, shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STAMP = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
F = []

def add(title, severity, kind, problem, consequence, recommendation, discussion, sources):
    evidence = []
    for name, pattern in sources:
        p = ROOT / name
        lines = p.read_text(encoding='utf-8').splitlines()
        matches = [(i, s) for i, s in enumerate(lines, 1) if re.search(pattern, s)]
        if not matches:
            raise ValueError(f'Evidence pattern not found: {name}: {pattern}')
        # First matching assertion, with its original line number; never use fence-stripped line numbers.
        n, s = matches[0]
        evidence.append(dict(path=name, line=n, excerpt=s, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    F.append(dict(id=f'W{len(F)+1:02d}', title=title, severity=severity, kind=kind,
                  problem=problem, consequence=consequence, recommendation=recommendation,
                  discussion=discussion, evidence=evidence))

add('wiki를 읽어도 v11로 되돌아가는 우선순위', '중대', '모순',
    '중앙 첫 화면은 도메인 사실이 다르면 v11이 맞다고 적습니다. cs 자동 로드 규칙에는 v10, 프로세스 규칙에는 v6 기준선과 v9 작업 범위도 남습니다. 그러나 후속 감시 결정은 v11을 읽기 전용으로 두고 자신이 그 자리를 대신한다고 명시합니다. 이번 사용자 지시도 wiki를 현재 정본으로 정했습니다.',
    '새 결정이 있어도 옛 계획서로 되돌리는 기준선이 만들어집니다. 제가 앞서 만든 베이스라인도 이 오류를 따라갔습니다.',
    '현재 wiki의 명시적 결정과 계약을 정본으로 하고, 코드·실행 결과는 구현 상태의 근거로 둡니다. v11은 당시 기록, v12는 정리된 wiki를 소개하는 안내서로 둡니다. 날짜가 최신이라는 이유만으로 제안을 확정 결정으로 올리지 않습니다.',
    '정본 방향은 이번 사용자 지시로 정해졌습니다. 그 방향을 적용할 페이지·자동 로드 규칙의 수정 목록을 검토합니다.',
    [('wiki/index.md', '도메인 사실이 기준선과 다르면'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '읽기 전용이라 고치지 않고'), ('final_project_cs/AGENTS.md', '계획서.*v10'), ('final_project_cs/RULE.md', '구현·평가 기준선')])
add('제품 범위 설명에 새 웹 화면과 일정 구성 기능이 빠짐', '중대', '보완·모순',
    '제품 소개·범위·시스템 경계는 자체 앱과 일정 생성을 제외합니다. 후속 설문·변경 결정과 최신 웹 흐름 문서는 사용자의 직접 입력·검토·일정 작업을 다룹니다.',
    '팀원이 실제로 만드는 기능을 범위 밖이라고 오해하거나, 구현되어 있다는 이유만으로 모든 계획 생성 책임을 제품 약속에 넣을 수 있습니다.',
    '직접 쓰는 웹 화면, 외부 에이전트 입력, 공유 계획서를 별도 접점으로 설명합니다. 최초 일정 구성과 변경 후보 생성의 제품 책임·지원 범위를 구분해 현재 범위표를 다시 씁니다.',
    '웹 제공은 후속 문서에 있습니다. 최초 일정 생성까지 제품이 보장할 범위는 설문·웹 계약의 원문과 대조해 의논해야 합니다.',
    [('wiki/product/scope.md', '계획 생성은 우리 일이 아니다'), ('wiki/architecture/system-context.md', '자체 앱은 만들지'), ('wiki/decisions/D-020-trip-survey-and-ask-first.md', 'planner|설문')])
add('항상 먼저 변경한다는 설명과 먼저 묻기 설정의 충돌', '중대', '모순',
    '제품 소개는 우리 일정은 먼저 고치고 통지한다고 요약합니다. 후속 결정은 먼저 묻기, 고정 일정, 안전 사건에 대한 조건을 따로 정했습니다.',
    '고객 선택을 무시하고 자동 변경하거나, 자동 변경을 선택한 고객에게 불필요하게 기다리게 할 수 있습니다.',
    '기본 변경 방식·먼저 묻기·고정 일정·안전 사건·무응답을 한 조건표로 둡니다. 후속 명시 결정을 요약하고 옛 무조건 문장을 현재 설명에서 내립니다.',
    '새 제품 결정을 만들기보다 D-020의 이미 정한 조건을 정확히 통합하는 수정입니다.',
    [('wiki/product/positioning.md', '먼저 고치고 통지'), ('wiki/decisions/D-020-trip-survey-and-ask-first.md', '안전 사건도 자동으로 바꾸지 않는다')])
add('공유 링크·웹 로그인·개인 AI 인증의 설명이 흩어짐', '중대', '보완',
    'D-020의 브라우저 키 안내 뒤에 쿠키 세션과 별도 에이전트 키 결정이 추가됐습니다. 제품 소개는 여전히 API와 공유 링크 두 가지만 소개합니다. 공유 링크가 로그인 없이 열리는 것 자체는 쿠키 로그인과 양립합니다.',
    '공유용 읽기 권한과 소유자의 편집 권한을 혼동하거나, 폐기된 브라우저 키 보관 안내를 다시 사용할 수 있습니다.',
    '공유 계획서 열람 / 웹 소유자 작업 / 개인 AI 여행 작업 / 외부 시스템 연동을 구분하고 각각 인증·권한·만료·현재 구현 상태를 연결합니다. D-CS-011·012로 대체된 옛 안내를 표시합니다.',
    '공유 링크를 없애자는 제안이 아닙니다. OAuth와 새 에이전트 키는 요구와 실제 구현을 구분해 추가 확인합니다.',
    [('final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md', '위 09-29 결정을 이것이 대신'), ('final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md', '세 개의 문'), ('wiki/product/positioning.md', '접점.*둘')])
add('사람에게 넘긴다는 완료 기준과 사람이 없는 운영 구조', '차단', '모순',
    '완료 기준은 자동 처리 한계에서 사람에게 인계한다고 요구합니다. 후속 라우팅 결정은 지금 사람에게 넘길 수 없고 사람 대기를 약속하지 않는다고 정했습니다.',
    '인계 상태만 저장하고 고객의 문제가 처리된 것처럼 판정할 수 있습니다.',
    '처리 실패 상태를 기록하는 것과 실제 사람이 대응하는 서비스를 구분합니다. 재분류 횟수·재시도·고객 안내·일정 유지·종료 조건을 고객 경로와 자동 감시 경로별로 정합니다.',
    '가장 먼저 의논할 사항입니다. 추천은 사람 대기 약속을 제거하고, 가능한 자동 재시도와 실패 안내를 유한하게 정의하는 것입니다. 정확한 범위와 종료 조건은 합의가 필요합니다.',
    [('wiki/delivery/dod.md', '자동 처리 한계'), ('final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md', '사람에게는 지금 절대'), ('final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md', '사람 대기 약속')])
add('대체 자료까지 실패했을 때 멈추는 범위가 미정', '차단', '모순·미결',
    '옛 결정은 대체 자료까지 실패하면 cs 프로젝트 앱을 끈다는 규칙입니다. D-018은 기동 실패·요청 실패·배치 실패로 나눠 보자는 초안이며, 후속 묶음 감시는 한 항목을 못 풀어도 나머지를 진행한다고 정했습니다.',
    '한 요청 실패로 전체 앱을 멈추거나, 필수 자료가 없는 상태에서 정상 처리라고 답하는 양쪽 위험이 있습니다.',
    '자료별 필수 여부, 기동·요청·감시 회차의 실패 범위, 기존 일정 유지, 고객 통지, 재개 조건을 표로 정합니다. D-018을 합의된 정책처럼 승격하지 않습니다.',
    '제품 판단이 필요합니다. 필수 기반 자료 결손과 일시적인 개별 조회 실패를 구분하는 방향을 추천하지만 현재 규칙을 임의로 완화하지 않습니다.',
    [('wiki/decisions/D-018-decision15-stop-paths.md', '초안 2026-09-21'), ('wiki/decisions/D-018-decision15-stop-paths.md', '합의되면'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '하나를 못 풀어도 나머지는')])
add('감시 실행 주기와 실제 자료의 새로움이 섞임', '중대', '모순·보완',
    'v11의 2분, 후속 3분 감시, 300초 응답 보관, 재난문자 20분 보관이 함께 남아 있습니다. 같은 문서의 후반에는 스스로 알아채는 사건이 최대 3분 늦다고도 적습니다.',
    '3분마다 감시하니 모든 안전 사건도 3분 안에 감지한다고 잘못 약속할 수 있습니다.',
    '소스별 수집 간격·원천 게시 지연·응답 보관 시간·판정 간격·고객 통지 지연을 구분합니다. 5분/10분 목표 같은 제안값은 검증 전 목표로 표시합니다.',
    '소스별 현재 설정과 실측 대조가 남아 있습니다. 특히 재난문자 허용 지연은 안전 요구와 함께 의논합니다.',
    [('wiki/decisions/D-017-watch-cadence-golden-time.md', '기본 2분.*다르다|읽기 전용이라'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '안전 사건 감지가 최대 20분'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '최대 3분 늦게')])
add('감시 묶음의 최신 실행 주체와 옛 흐름이 공존', '중대', '모순',
    '후속 결정은 같은 여행의 새 문제를 묶고 하나를 못 풀어도 나머지를 진행하도록 바뀌었습니다. 같은 문서에는 코드가 아직 없다는 옛 절과 이전 실행 흐름이 남아 있습니다.',
    '코어가 팀을 순서대로 부르는 옛 설계로 새 코드를 되돌리거나, 한 회차의 변경·질문·실패 알림 개수를 오해합니다.',
    '현재 회차의 시작부터 종료까지를 별도 계약으로 정리합니다. 변경 묶음, 항목별 질문, 실패 결과, 중복 방지, 재검증 순서와 책임을 표시하고 이전 흐름은 당시 기록으로 옮깁니다.',
    '의미를 바꾸지 않는 통합을 먼저 제안합니다. 다른 Team 직접 호출 금지와 계산 함수 재사용의 차이는 경계 계약에서 함께 정해야 합니다.',
    [('wiki/decisions/D-017-watch-cadence-golden-time.md', '하나를 못 풀어도 나머지는'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '아직 코드에 없다'), ('final_project_cs/wiki/quality/invariants.md', 'INV-CS-ACT-006')])
add('낮 휴무 감지 요구와 구글 호출 제한 사이의 빈칸', '차단', '미결',
    'D-020은 낮 휴무를 고객 신고로 받는다고 적지만 D-CS-009가 이를 뒤집었습니다. D-CS-010은 구글 장소 조회를 새벽 창에 한정하며, 낮 감지와 어떤 자료로 양립시킬지 팀이 정하도록 남겼습니다.',
    '시스템이 방문 전에 휴무를 알아낸다고 약속하면서 실제로 읽을 자료가 없는 상태가 될 수 있습니다.',
    '낮에 조회할 실제 자료·대체 자료·허용 지연·호출 예산·실패 시 행동을 정하고 시나리오로 검증합니다. 지도 표시 호출은 장소 상태 조회와 구분합니다.',
    '이미 확정한 낮 감지 요구를 삭제하지 않습니다. 구현할 소스와 확인 실패 행동을 의논해야 합니다.',
    [('wiki/decisions/D-020-trip-survey-and-ask-first.md', '식당 영업 여부는'), ('final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md', '시스템이 방문 전에'), ('final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md', '낮 임시휴무 감지')])
add('현재 평가 첫 화면이 쇼핑몰 평가로 안내함', '중대', '모순',
    '평가 허브는 옛 72건·A/B/Proposed 결과와 쇼핑몰 파인튜닝 문서를 기본 읽기 순서로 둡니다. D-023은 쇼핑몰 자료를 지금 판단·평가·관문에 쓰지 못하게 했습니다.',
    '여행 분류·검색·답변의 실제 품질 대신 과거 다른 도메인의 점수로 성과를 설명할 수 있습니다.',
    '여행 분류 평가, 일정 항목 선택·검색·답변 평가, 추가 학습 비교, 제품 전체 시나리오의 목적과 현재 자료를 연결합니다. 옛 수치는 역사로 보존하고 현 제품 관문과 분리합니다.',
    '옛 기록 삭제가 아닙니다. 현재 평가 지표·자료·사람 검수 상태와 채택 관문을 확정할 때 의논합니다.',
    [('wiki/evaluation/index.md', '72|216'), ('wiki/decisions/D-023-no-commerce-assets-in-use.md', '지금 프로젝트의 판단'), ('final_project_cs/wiki/quality/slm-model-evaluation.md', '평가 절차의 정본')])
add('완료·출시 판정 문서가 삭제된 명령을 여전히 안내함', '차단', '모순·실재 확인',
    '출시 문서의 앞부분에는 v8 수치와 eval.check_judge 명령이 남아 있고 뒷부분에는 여행판 명령이 들어 있습니다. 완료 문서는 옛 verify_dod.py를 보존한다고 적지만 D-023은 삭제했다고 적습니다. 현재 작업 트리에서도 두 옛 실행 파일이 없음을 확인했습니다.',
    '재현 명령이 실행되지 않거나 서로 다른 항목 수로 출시 가능 여부를 판정합니다.',
    '현재 여행 요구별 ID·시험·근거·미구현 상태로 다시 연결합니다. 옛 통과 숫자는 날짜가 있는 기록으로 두고 현재 완료 주장에 사용하지 않습니다.',
    '새 완료 기준의 의미 변경은 합의 후 합니다. 실행되지 않는 명령과 역사 설명 정정은 제품 범위 변경과 구분합니다.',
    [('wiki/delivery/release-gate.md', '통과 24'), ('wiki/delivery/release-gate.md', 'eval.check_judge'), ('wiki/delivery/dod.md', '기록으로 남긴다'), ('wiki/decisions/D-023-no-commerce-assets-in-use.md', 'v8 29항목')])
add('Team의 읽기 도구 직접 사용 계약이 정리되지 않음', '중대', '미결',
    'Team 경계와 불변식은 직접 읽기를 금지하면서, 여행 Team은 허용 목록과 예산을 강제하는 읽기 도구를 직접 부른다고 기록합니다. 문서 자체가 규칙과 코드를 어느 쪽으로 고칠지 미정이라고 합니다.',
    '정상적인 통제된 조회를 위반으로 판정하거나, 도구 우회를 허용하는 식으로 경계를 느슨하게 만들 수 있습니다.',
    '조회 경유 지점·허용 도구·예산·테넌트 범위·근거 반환을 계약으로 정합니다. 부수 효과 실행과 읽기 조회를 구분하고 실제 경계를 검증하는 검사로 연결합니다.',
    '직접 읽기 전면 금지를 유지할지, 통제된 도구 사용을 허용할지 선택이 필요합니다. 구현을 근거로 규칙을 자동 승인하지 않습니다.',
    [('final_project_cs/wiki/teams/team-boundary.md', '어느 쪽이 맞는지 안 정해'), ('final_project_cs/wiki/quality/invariants.md', '불변식을 고칠지 코드를 고칠지')])
add('쇼핑몰 대조군을 허용한 옛 불변식과 금지 결정', '중대', '모순',
    '불변식 문서는 커머스 대조군 시험을 지우지 말라고 합니다. 후속 D-023과 전역 사용자 지시는 쇼핑몰 자산을 현재 시험·판단·관문에 쓰지 말라고 합니다. 해당 아키텍처 시험 파일은 현재 존재합니다.',
    '옛 예외를 근거로 금지된 자료가 현재 검증에 계속 사용될 수 있습니다. 파일 존재만으로 현 CI 실행 여부까지 단정하지는 않습니다.',
    '현재 실행 범위를 먼저 확인하고, 도메인 독립성 증명을 유지할 다른 시험 재료를 정합니다. 역사 보존과 현재 실행을 구분하며 시험을 임의로 지우거나 단순 비활성화하지 않습니다.',
    '후속 사용자 금지 규칙을 적용할 범위와 대체 시험을 함께 검토해야 합니다.',
    [('final_project_cs/wiki/quality/invariants.md', '이 파일은 지우지 않는다'), ('wiki/decisions/D-023-no-commerce-assets-in-use.md', '새 시험.*여행 도메인')])
add('DB 첫 화면과 스키마 계약이 아직 커머스 표 중심', '중대', '보완·실재 확인',
    '데이터 허브·스키마는 9월 10일의 표와 마이그레이션 수를 중심으로 설명합니다. 후속 문서는 여행 표·웹 세션·동의·보류 제안 등을 다루며, D-023은 로컬 개발 DB의 쇼핑몰 표 제거를 기록합니다. 현재 migrations 하위 SQL 파일은 재귀 집계 90개입니다.',
    '팀원이 새 기능의 저장 위치를 찾기 어렵고, 파일 수를 DB 적용 완료 수로 오해할 수 있습니다.',
    '현재 여행·인증·통지·근거의 표 관계와 스키마 소유를 안내합니다. 90은 pending 등을 포함한 파일 수일 뿐이며 적용 순서·활성 마이그레이션·환경별 실제 적용 내역은 별도로 확인합니다.',
    '이번에는 DB에 접속하지 않았습니다. 로컬 개발 DB·공개 배포 DB·별도 실험 DB 상태는 각각 확인할 필요가 있습니다.',
    [('final_project_cs/wiki/data/index.md', '작업 트리 13개'), ('final_project_cs/wiki/data/schema/index.md', '도메인 테이블.*커머스'), ('wiki/decisions/D-023-no-commerce-assets-in-use.md', '로컬 개발 DB')])
add('파인튜닝의 과거 결과와 현재 학습 절차의 연결 누락', '중대', '보완',
    '중앙 파인튜닝 문서는 v8의 배선·옛 학습 실패를 다룹니다. 최신 품질 문서는 원본 모델 비교와 학습판 재평가 절차를 현재 정본으로 명시합니다.',
    '옛 모델 미채택을 모든 추가 학습 금지로 읽거나, 현재 학습 후보를 서비스 채택 모델로 소개할 수 있습니다.',
    '현재 평가 절차로 안내하고 과거 모델·과거 데이터·지금 원본 후보·지금 학습판을 구분합니다. 각 비교에 모델 정확한 이름, 학습 여부, 자료 해시, 실행 조건, 채택 상태를 둡니다.',
    '새 평가 기준을 최종 확정할 때 검토합니다. 학습 후보 선정과 서비스 채택은 별도 판정으로 유지합니다.',
    [('wiki/evaluation/finetuning.md', 'v8.*이관'), ('final_project_cs/wiki/quality/slm-model-evaluation.md', '서로 다른 판정')])
add('현 역할표와 옛 디렉터리 소유표의 불일치', '중대', '보완·미결',
    '역할 문서는 옛 인원 배치를 정정했지만 본문 소유표에는 옛 Team·UI·VOC 경로와 동결된 handoff 경로가 남아 있습니다. Access & Action 담당은 미배정으로 남습니다.',
    '인증·권한·실행 안전 기능이 담당 공백이 되거나 여러 팀원이 같은 파일을 서로 덮어쓸 수 있습니다.',
    '사람 이름과 무관한 기능 소유·검토자·공유 계약 변경 절차를 현재 경로로 다시 씁니다. 인증·도구 실행·DB 변경·평가·통합의 최종 담당을 명시합니다.',
    '실제 담당자 배정은 팀 의논이 필요합니다. 제가 임의로 배정하지 않습니다.',
    [('wiki/delivery/roles.md', '담당 칸이 없다'), ('wiki/delivery/roles.md', 'app/modules/customer_ops/'), ('final_project_cs/wiki/teams/code-layout.md', '각자 폴더')])
add('현재 일정·제출물 안내에 옛 쇼핑몰 작업이 남음', '중대', '보완·모순',
    '전체 일정은 당시 날짜와 쇼핑몰 주차표를 역사라고 표시하지만, 최종발표까지·수집 데이터 보고서·역할별 배분에는 옛 Team·상용 주문 자료·29항목이 현재 안내처럼 남습니다.',
    '남은 기간의 우선순위와 제출 근거를 잘못 정합니다.',
    '공식 제출 일정, 현재 남은 구현·평가, 과거 주차 이력을 분리합니다. 현재 제출물의 근거는 정리된 여행 wiki와 유효한 실행 증거로 연결합니다.',
    '일정·동결일·평가 준비·시연 범위를 함께 정해야 합니다. 날짜가 지난 기록 자체를 오류로 취급하지 않습니다.',
    [('wiki/delivery/timeline.md', '오늘 2026-09-01'), ('wiki/delivery/timeline.md', '상용 주문'), ('wiki/delivery/timeline.md', 'DoD 29항목')])
add('상시 운영 안내가 개발자 PC 콘솔 시점에 머묾', '중대', '보완',
    '상시 운영 문서는 전부 개발자 PC 콘솔에 매달려 있다고 시작합니다. 최신 운영 기록은 공개 배포·별도 ARM 실험·추론과 앱의 서로 다른 상태를 다룹니다.',
    '어느 환경에서 무엇이 실행되는지 혼동하고, 모델 추론 성공을 고객 앱 정상 동작으로 확대할 수 있습니다.',
    '로컬 개발, 공개 운영, 별도 실험, GPU 추론을 나눠 앱·DB·감시·배달 작업·모델의 상태와 확인 시각을 둡니다. 운영 절차와 당시 진단 기록을 구분합니다.',
    '이번 감사는 원격 접속과 실서비스 호출을 하지 않았습니다. 실제 가동 여부는 문서 대조와 별도 확인해야 합니다.',
    [('final_project_cs/wiki/operations/always-on.md', '상시 실행은 전부 개발자 PC'), ('final_project_cs/wiki/log.md', 'ARM 추론 가동과 cs 프로젝트 앱 차단')])
add('데이터 wiki의 Git 공개 안내가 현재 개인정보 규칙과 다름', '중대', '모순',
    '데이터 wiki는 스크립트·스키마·REPORT만 Git에 올린다고 안내합니다. 현재 전역 규칙은 datasets 전체를 Git에서 제외하며, 쇼핑몰 원본은 백업 후 제거했습니다.',
    '옛 안내를 따라 데이터 주변 파일과 개인정보 조각을 공개할 수 있습니다.',
    '현재 데이터 지도와 공개 규칙으로 진입 문서를 다시 쓰고 옛 수집·배포 절차는 역사로 표시합니다. 데이터 삭제나 공개는 이번 작업에서 하지 않습니다.',
    '이미 정한 전역 규칙에 맞추는 수정입니다. 데이터별 현재 이용 목적은 각각 REPORT와 대조해야 합니다.',
    [('datasets/wiki/index.md', '스크립트와 스키마와'), ('wiki/decisions/D-023-no-commerce-assets-in-use.md', '원본 데이터|백업.*commerce_removal')])
add('draft 하나로 확정 여부·구현 여부를 판단할 수 없음', '중대', '보완',
    '현재 본문 284개 중 status=draft는 262개, accepted는 8개입니다. D-017·D-020처럼 사용자 결정이 본문에 있는 페이지도 draft이고, D-018은 실제 미합의 초안입니다. 구현 상태를 status로 쓰는 페이지도 있습니다.',
    '확정된 사용자 결정을 제안으로 버리거나, 작성 중인 설계를 제품 약속으로 받아들일 수 있습니다.',
    '결정 상태, 적용 범위, 구현 상태, 확인일, 대체한 결정 링크를 구분합니다. 페이지 메타데이터보다 본문의 명시적 결정 근거를 먼저 대조하고, 일괄 accepted 승격은 하지 않습니다.',
    '필드와 승격 절차는 정리 규칙으로 합의합니다. 위 숫자는 구조 점검 스냅샷의 값입니다.',
    [('wiki/decisions/D-020-trip-survey-and-ask-first.md', '^status: draft'), ('wiki/decisions/D-018-decision15-stop-paths.md', '합의되면')])
add('현재 본문에서 확인된 로컬 링크 목적지 3곳', '보통', '실재 확인',
    '쿠키 결정과 REST 계약의 open-items 링크는 cs wiki 안의 존재하지 않는 delivery 폴더를 가리킵니다. Dining 설계의 체크리스트 링크도 현재 목적지 파일이 없습니다.',
    '의사결정의 남은 항목과 설계 원본을 바로 확인할 수 없습니다.',
    'open-items는 중앙 허브의 실제 파일로 다시 연결합니다. 체크리스트는 현재 정본을 찾아 연결하거나 과거 입력이었다고 표시합니다. 자동 스캔이 좌표를 링크로 오인한 1건과 이관 임시 문서 1건은 현재 깨진 링크 수에서 제외했습니다.',
    '앵커·참조형 링크·코드 블록 예시·원격 링크는 이 자동 검사 범위 밖입니다. 3곳이 모든 종류의 링크 오류 전부라는 뜻은 아닙니다.',
    [('final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md', r'\[open-items\]\(../delivery/open-items.md\)'), ('final_project_cs/wiki/external/rest-endpoints.md', r'\[open-items\]\(../delivery/open-items.md\)'), ('final_project_cs/wiki/teams/dining-agent-design.md', r'체크리스트.md\]\(')])
add('기존 wiki 검사기가 백업 문서까지 현재 문서처럼 검사', '중대', '도구 범위 문제',
    '기존 검사기는 재귀 glob으로 문서를 모으고 records는 제외하지만 백업 폴더를 현재 문서에서 빼지 않습니다. 이번 실행은 2,126개를 검사하고 15,903건 위반을 출력했으며, 백업 위치에서 상대경로가 달라진 결과가 대량 포함됐습니다.',
    '실제 현재 문서 결함과 백업 보존으로 생긴 경고를 구분할 수 없어 검사 결과를 믿고 고치기 어렵습니다.',
    '현재 본문·이관 임시·동결 기록·백업·생성물을 먼저 분류하고 검사 범위와 규칙을 다르게 적용합니다. 원문 로그는 보존하고 15,903을 실제 결함 수로 쓰지 않습니다.',
    '검사기 수정은 별도 변경으로 제안합니다. 규칙을 통과시키기 위해 정상 태그·단일 구현 범위·백업을 임의로 지우지 않습니다.',
    [('program/scripts/check_wiki.py', r'docs \+= sorted\(glob.glob'), ('program/scripts/check_wiki.py', 'if "/records/" in rel')])
add('불변식 요약 수와 역방향 표식의 드리프트', '보통', '실재 확인',
    '카탈로그 요약은 61개와 ACT 4개로 적혀 있지만 표 행의 고유 ID는 71개, ACT는 12개입니다. 현재 코드의 ARCH-007 표식은 카탈로그 표 행에 없습니다. 이 집계는 시험 통과 수가 아닙니다.',
    '검증 대상과 실제 검사 연결 범위를 잘못 이해합니다.',
    'ID·판정·시험 경로를 단일 카탈로그에서 집계하고 비활성 역사 항목을 별도 상태로 표시합니다. 새 상태 전이도 일치 검사의 ID도 카탈로그와 연결합니다.',
    '유효한 현재 항목 수는 역사 항목의 상태까지 정리한 뒤 확정합니다. 이번 71개는 현재 표의 고유 ID 수입니다.',
    [('final_project_cs/wiki/quality/invariants.md', r'\| \*\*합계\*\*'), ('final_project_cs/tests/architecture/test_state_diagram_matches_code.py', 'INV-CS-ARCH-007')])
add('ODsay 미사용 결정과 후속 독립 대조 안내의 관계 미표시', '보통', '추가 확인',
    '9월 결정은 ODsay 미사용이고 10월 안내는 선택적인 독립 대조용 키 발급을 설명합니다. 운영 연결과 연구용 대조는 서로 다를 수 있으므로 바로 결정 위반으로 단정하지 않았습니다.',
    '키가 있으면 제품에 붙여도 된다고 오해하거나, 허용된 독립 측정까지 금지된 것으로 읽을 수 있습니다.',
    '현재 제품 연결 여부, 독립 측정의 승인 근거, 결과 보관 범위를 확인하고 예외의 적용 범위를 문서에 연결합니다. 약관 판단은 본문을 재확인하기 전 확정하지 않습니다.',
    '후속 사용자 승인과 실제 사용 범위 확인이 필요합니다. 이번 검토에서 ODsay 약관 전체를 다시 읽지는 않았습니다.',
    [('final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md', '사용자 판단'), ('final_project_cs/wiki/external/api-key-issue-guide.md', '선택 사항.*독립 대조')])
add('현재 계약과 날짜별 작업 기록이 같은 본문에 누적', '보통', '중복·보완',
    '여러 페이지에 정정문과 후속 기록을 덧붙여 옛 현재 상태·최신 결정·미구현 설명이 공존합니다. 문서 표준은 시점별 기록을 개념 문서에 쌓지 말라고 이미 정했습니다.',
    '전체를 다 읽지 않으면 현재 규칙을 알 수 없고, 일부만 읽는 사람이나 에이전트가 옛 문장을 현재 규칙으로 사용합니다.',
    '맨 위에는 현재 계약과 적용 범위, 아래에는 근거 링크·대체 결정 관계를 둡니다. 역사 기록을 보존하면서 현재 정본을 주제별 한 곳으로 정합니다. 큰 파일은 줄 수만으로 기계적으로 자르지 않습니다.',
    '모든 본문 정독과 연결 관계 확인이 남아 있습니다. 구조 변경 목록은 먼저 검토한 뒤 적용합니다.',
    [('wiki/governance/document-standard.md', '시점별 기록을 개념 문서에 쌓기'), ('wiki/decisions/D-017-watch-cadence-golden-time.md', '아직 코드에 없다')])

FULL = '''wiki/index.md
wiki/delivery/dod.md
wiki/delivery/release-gate.md
wiki/decisions/D-023-no-commerce-assets-in-use.md
wiki/evaluation/index.md
wiki/decisions/D-018-decision15-stop-paths.md
wiki/decisions/D-020-trip-survey-and-ask-first.md
wiki/decisions/D-017-watch-cadence-golden-time.md
wiki/evaluation/finetuning.md
wiki/business/pricing-travel.md
wiki/product/positioning.md
wiki/product/scope.md
wiki/governance/domain-axis.md
wiki/architecture/system-context.md
final_project_cs/wiki/index.md
final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md
final_project_cs/wiki/external/web-auth-transfer.md
final_project_cs/wiki/teams/team-boundary.md
final_project_cs/wiki/context/index.md
final_project_cs/wiki/quality/slm-model-evaluation.md
final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md
final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md
final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md
final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md
final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md
final_project_cs/wiki/external/api-key-issue-guide.md
datasets/wiki/index.md
wiki/delivery/timeline.md
wiki/delivery/roles.md
final_project_cs/wiki/data/index.md
final_project_cs/wiki/data/schema/index.md'''.splitlines()
overview = json.loads((OUT/'reading-overview.json').read_text(encoding='utf-8'))
assert len(overview) == 284 and len(set(FULL)) == len(FULL)
for p in FULL:
    assert p in {x['path'] for x in overview}, p
coverage = []
for x in overview:
    p = ROOT/x['path']
    coverage.append(dict(path=x['path'], review_level='본문 정독' if x['path'] in FULL else '제목·구조·도입부 검토; 본문 추가 정독 필요', sha256=hashlib.sha256(p.read_bytes()).hexdigest()))

def write_new(path, value):
    # Keep every previous generated deliverable before an explicit review rerun.
    if path.exists():
        backup = OUT/'_backup'/(datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')+'_generated-review')
        backup.mkdir(parents=True, exist_ok=True)
        target = backup/path.name
        if target.exists():
            raise FileExistsError(target)
        shutil.copy2(path, target)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(value)

write_new(OUT/'findings-v1.json', json.dumps(dict(reviewed_at=STAMP, status='first_pass_incomplete', findings=F),ensure_ascii=False,indent=2))
write_new(OUT/'reading-coverage-v1.json', json.dumps(dict(reviewed_at=STAMP, current=284, full_body=len(FULL), files=coverage),ensure_ascii=False,indent=2))

INTRO = f'''현재 wiki를 정리한 뒤 안내 계획서와 베이스라인을 만드는 방향이 맞습니다. v11을 현재 요구보다 우선한 이전 베이스라인 판단은 바로잡아야 합니다.

이 문서는 **1차 검토 보고서**입니다. 현재 본문 284개의 제목·구조·도입부를 검토하고, 아래에 명시한 핵심 문서 {len(FULL)}개를 본문 정독했습니다. **전체 본문 정독과 모든 문제 발견이 완료된 보고서는 아닙니다.** 근거가 확인된 문제·미결 사항을 25개 주제로 묶었습니다. 25는 전체 결함 수가 아닙니다.

중요도에서 **차단**은 이 내용이 정리되기 전 현재 제품의 베이스라인을 확정하면 안 된다는 뜻입니다. 이번 검토만으로 운영 중인 앱의 장애를 재현했다는 뜻은 아닙니다.

검토 시각: {STAMP}. 범위: 중앙 wiki·cs wiki·sample wiki·datasets wiki·acop_dojo wiki. 이관 임시 24개, 기록 1,528개, 백업 463개는 현재 규칙 본문과 분리했습니다. 동결 기록은 인용 근거를 확인할 때만 사용합니다. 이전 계획서·코드·문서가 증거 없이 자동으로 현재 요구가 되지는 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 현재 본문 제목·구조·도입부 | 완료 | 284/284개 = 100% |
| 본문 전체 정독 | 진행 | {len(FULL)}/284개 = {len(FULL)/284:.1%} |
| 1차 보고서 | 완료 | 1/1건 = 100% |
| 제품 규칙 합의·수정 | 미착수 | 분모는 의논 후 확정 |

본문 정독 수는 이번 작업에서 끝까지 읽었다고 확인한 보수적인 목록입니다. 부분 정독·검색으로 근거를 확인한 파일은 그 수에 넣지 않았습니다. 자동 구조 검사가 파일 전체를 읽었다는 사실도 사람 수준의 본문 정독으로 세지 않았습니다.
'''

WORKFLOW = '''현재 wiki 수집 → 본문 검토·근거 대조 → 미결 사항 의논 → wiki 수정·재검사 → 정리한 wiki에서 v12 안내서 작성 → 정리된 wiki 판본과 실행 증거를 고정한 베이스라인 작성. 재검사에서 충돌이 남으면 검토 단계로 돌아갑니다. 사용자 합의 전에는 현재 제품 규칙·v12·최종 베이스라인을 변경하지 않았습니다.'''

BASELINE = '''프로젝트 기준선은 전체 범위·공통 계약·품질 기준을 묶는 상위 묶음 하나로 두는 것을 제안합니다. Activity·Dining·Mobility 같은 기능과 모델 추가 학습에는 별도의 하위 명세·비교 기준이 필요할 수 있습니다. 이것을 팀원마다 독립적인 제품 정본으로 만들지는 않습니다. 예를 들어 Dining의 입력·출력·도구·실패 처리는 해당 기능의 기준이고, 같은 모델의 학습 전후 비교는 자료·설정·평가 결과를 고정한 실험 기준입니다. 상위 기준선이 그 판본들을 참조하며, 공유 파일 하나 안에 이를 모아 보여 줄 수 있습니다. 이 구조는 아직 합의 전 제안입니다.'''

LIMITS = '''이번에 한 것: 파일 목록·해시 수집, 현재/기록/백업 분리, 메타데이터와 일부 로컬 링크 검사, 기존 검사기 실행, 핵심 결정·계약 대조, 지정한 파일·명령의 실재 확인입니다. 앱 테스트를 새로 돌리지 않았고 DB·원격 기계·실서비스·실제 알림 전달을 검사하지 않았습니다. 원격 자료 약관·논문·외부 표준 전부를 재검증하지 않았습니다. 인증 문서가 인용한 RFC 10017 및 MCP 2026-07-28 인증 문서의 공식 원문 접근은 확인했지만, 그 사실만으로 해당 wiki의 모든 보안 주장이나 적합성을 검증한 것은 아닙니다. 현재 파일은 다른 작업에서 변경될 수 있으므로 후속 수정 직전에 다시 해시를 확인해야 합니다.'''

md = '# wiki 기준 재정립 — 1차 검토\n\n' + INTRO
md += '\n## 먼저 의논할 것\n\n사람 인계가 없는 실패 처리, 자료 결손 시 멈추는 범위, 낮 휴무 감지의 자료·예산을 먼저 의논할 것을 제안합니다. 이미 확정한 먼저 묻기·고정 일정 조건을 다시 취소하거나 새 결정을 받자는 뜻은 아닙니다.\n'
md += '\n## 작업 순서\n\n' + WORKFLOW + '\n\n## 기준선의 묶음\n\n' + BASELINE + '\n'
for x in F:
    md += f"\n## {x['id']} · {x['title']}\n\n**{x['severity']} · {x['kind']}**\n\n{x['problem']}\n\n영향: {x['consequence']}\n\n수정 제안: {x['recommendation']}\n\n의논·확인: {x['discussion']}\n\n근거:\n\n"
    for e in x['evidence']:
        md += f"- [{e['path']}:{e['line']}]({(ROOT/e['path']).as_posix()}:{e['line']}) — {e['excerpt']}\n"
md += '\n## 검증 범위와 남은 일\n\n' + LIMITS + '\n\n현재 본문 중 나머지 253개는 전체 본문 정독이 남았습니다. 링크·구조·도입부 검토에서 별다른 문제가 보이지 않았다는 이유로 정상 판정하지 않습니다. 보존 기록의 모든 본문을 읽는 일은 이번 현재 기준 정리의 기본 범위가 아닙니다.\n'
md += '\n## 핵심 본문 정독 목록\n\n' + '\n'.join('- '+p for p in FULL) + '\n'
md += '\n## 검사 근거\n\n- [전체 파일 스냅샷](inventory.json)\n- [구조 검사](structure-audit.json)\n- [기존 검사기 원문](existing-checker.log)\n- [파일별 읽기 범위](reading-coverage-v1.json)\n- [문제와 실제 줄 번호](findings-v1.json)\n'
md += '\n외부 원문 접근 확인: [RFC 10017](https://www.rfc-editor.org/rfc/rfc10017.html), [MCP 인증 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization).\n'
write_new(OUT/'wiki-review-v1.md', md)

def rel_link(path):
    import os
    return Path(os.path.relpath(ROOT/path,OUT)).as_posix()

svg = '''<svg viewBox="0 0 720 1000" role="img" aria-labelledby="wiki-review-flow-title wiki-review-flow-desc">
<title id="wiki-review-flow-title">wiki부터 베이스라인까지의 정리 순서</title><desc id="wiki-review-flow-desc">wiki를 검토하고 함께 결정한 뒤 수정하며, 재검사를 통과한 내용으로 안내서와 기준선을 만듭니다. 충돌이 남으면 다시 검토합니다.</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6Z" fill="#6b7488"/></marker><marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6Z" fill="#a8720c"/></marker><marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6Z" fill="#2f5bd8"/></marker></defs>
<g fill="none" stroke="#6b7488" stroke-width="1.2" marker-end="url(#arrow)"><path d="M360 96V136"/><path d="M360 200V240"/><path d="M360 304V344"/><path d="M360 408V448"/><path d="M360 512V552"/><path d="M472 616H616Q624 616 624 608V280Q624 272 616 272H520"/><path d="M360 680V720"/><path d="M360 784V824"/></g>
<g fill="#fbfcfd"><rect x="484" y="584" width="112" height="24"/><rect x="372" y="684" width="80" height="24"/></g>
<g fill="#6b7488" font-size="16"><text x="540" y="600" text-anchor="middle">충돌 남음</text><text x="412" y="700" text-anchor="middle">통과</text></g>
<g stroke="#161c28" fill="#fff" stroke-width="1.2"><ellipse cx="360" cy="64" rx="120" ry="32"/><rect x="200" y="136" width="320" height="64" rx="6"/><rect x="200" y="240" width="320" height="64" rx="6"/><rect x="200" y="344" width="320" height="64" rx="6"/><rect x="200" y="448" width="320" height="64" rx="6"/><path d="M360 552L472 616L360 680L248 616Z" fill="#fbfcfd"/><rect x="200" y="720" width="320" height="64" rx="6"/><ellipse cx="360" cy="856" rx="160" ry="32" fill="rgba(168,114,12,0.10)" stroke="#a8720c"/></g>
<g fill="#161c28" font-size="20" font-weight="600" text-anchor="middle"><text x="360" y="72">현재 wiki 수집</text><text x="360" y="176">본문 검토·근거 대조</text><text x="360" y="280">함께 의논하고 결정</text><text x="360" y="384">wiki 수정</text><text x="360" y="488">재검사</text><text x="360" y="624">충돌 해결?</text><text x="360" y="760">v12 안내서 작성</text><text x="360" y="864">기준선 파일 완성</text></g>
<line x1="64" x2="656" y1="932" y2="932" stroke="#dbe0ea"/><g fill="#6b7488" font-size="16"><text x="64" y="964">타원: 시작·완료</text><text x="264" y="964">사각형: 작업</text><text x="464" y="964">마름모: 판정</text></g></svg>'''

css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#fbfcfd;color:#161c28;font-family:Geist,'Noto Sans KR','Malgun Gothic',sans-serif;font-size:16px;line-height:1.8}main{max-width:1060px;margin:auto;padding:48px 32px 96px}h1{font-family:'Instrument Serif','Noto Serif KR',serif;font-size:36px;line-height:1.4;font-weight:400}h2{font-size:24px;margin-top:48px}h3{font-size:20px;line-height:1.5}a{color:#2f5bd8;overflow-wrap:anywhere}p{max-width:82ch}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{text-align:left;border-bottom:1px solid #dbe0ea;padding:12px}header{border-bottom:2px solid #161c28;padding-bottom:24px}.lead{font-size:20px}.note{border-left:4px solid #a8720c;padding:12px 20px;background:rgba(168,114,12,.06)}.muted{color:#6b7488}.finding{border-top:1px solid #dbe0ea;margin-top:32px;padding-top:16px;scroll-margin-top:24px}.tag{font-size:14px;border:1px solid #dbe0ea;padding:4px 8px;margin-right:8px}.evidence{padding:12px 16px;background:#f1f4f8;overflow-wrap:anywhere}.evidence blockquote{margin:8px 0 0;border-left:2px solid #dbe0ea;padding-left:12px;font-size:14px}.flow{max-width:620px}svg{width:100%;height:auto;font-family:Geist,'Noto Sans KR','Malgun Gothic',sans-serif}nav ul{columns:2;padding-left:24px}nav li{break-inside:avoid;margin-bottom:8px}summary{cursor:pointer;font-weight:600}footer{border-top:1px solid #dbe0ea;margin-top:48px;padding-top:16px;font-size:14px}:focus-visible{outline:3px solid #2f5bd8;outline-offset:4px}@media(max-width:650px){main{padding:24px 20px 64px}h1{font-size:28px}nav ul{columns:1}table{font-size:14px}td,th{padding:8px}}@media print{html{scroll-behavior:auto}main{max-width:none;padding:0}.finding{break-inside:avoid}nav{display:none}.flow{max-width:440px}a{color:inherit}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'''
html = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>guguroute wiki — 1차 검토 보고서</title><style>'+css+'</style></head><body><main>'
html += '<header><p class="muted">guguroute · 현재 기준 정리 · 2026-10-11</p><h1>wiki부터 다시 잡아야 합니다.</h1><p class="lead">최신 결정이 옛 계획서보다 뒤에 있는데, 제품 소개와 완료 기준은 이전 상태로 남아 있습니다.</p></header>'
html += f'<p class="note"><strong>1차 검토 · 전체 정독 미완료</strong><br>284개 제목·구조·도입부 검토, 핵심 {len(FULL)}개 본문 정독. 아래 25개는 확인된 문제·미결 사항의 주제 묶음이며 전체 결함 수가 아닙니다. 「차단」은 베이스라인 확정을 막는 미결 사항이며 운영 장애를 재현했다는 뜻은 아닙니다.</p>'
html += f'<table><thead><tr><th>할 일</th><th>상태</th><th>진행</th></tr></thead><tbody><tr><td>전체 구조·도입부</td><td>완료</td><td>284/284 = 100%</td></tr><tr><td>본문 전체 정독</td><td>진행</td><td>{len(FULL)}/284 = {len(FULL)/284:.1%}</td></tr><tr><td>1차 보고서</td><td>작성</td><td>1/1 = 100%</td></tr><tr><td>제품 규칙 수정</td><td>합의 전</td><td>분모는 의논 후 확정</td></tr></tbody></table>'
html += '<h2>먼저 의논할 세 가지</h2><ol><li>사람 인계 없이 처리 실패를 어떻게 끝낼지</li><li>필수 자료가 없을 때 어느 범위까지 멈출지</li><li>낮 휴무를 어떤 자료·예산으로 확인할지</li></ol><p>이미 정한 고객의 먼저 묻기·고정 일정 조건은 후속 결정대로 정리할 대상으로 봅니다.</p>'
html += '<h2>정리 순서</h2><p>'+escape(WORKFLOW)+'</p><figure class="flow">'+svg+'<figcaption>현재 위치: 본문 검토·근거 대조. 제품 규칙은 아직 변경하지 않았습니다.</figcaption></figure>'
html += '<h2>프로젝트 하나인가, 기능마다 하나인가</h2><p>'+escape(BASELINE)+'</p>'
html += '<nav aria-label="문제 목록"><h2>문제와 수정 제안 25개</h2><ul>'+''.join(f'<li><a href="#{x["id"]}">{x["id"]} · {escape(x["title"])}</a></li>' for x in F)+'</ul></nav>'
for x in F:
    html += f'<article class="finding" id="{x["id"]}"><p><span class="tag">{escape(x["severity"])}</span><span class="tag">{escape(x["kind"])}</span></p><h3>{x["id"]} · {escape(x["title"])}</h3><p>{escape(x["problem"])}</p><p><strong>영향</strong> — {escape(x["consequence"])}</p><p><strong>수정 제안</strong> — {escape(x["recommendation"])}</p><p><strong>의논·확인</strong> — {escape(x["discussion"])}</p><details><summary>근거 문장과 실제 줄 번호</summary>'
    for e in x['evidence']:
        html += '<div class="evidence"><a href="'+escape(rel_link(e['path']),quote=True)+'">'+escape(f"{e['path']}:{e['line']}")+'</a><blockquote>'+escape(e['excerpt'])+'</blockquote></div>'
    html += '</details></article>'
html += '<h2>확인 범위와 남은 일</h2><p>'+escape(LIMITS)+'</p><p>현재 본문 나머지 253개의 전체 정독이 남아 있습니다. 보존 기록 전부를 정독하는 것은 현재 규칙 검토와 구분합니다. 수정 후에는 같은 문제 목록을 다시 검사하고, 새 충돌이 나오면 기록해 의논합니다.</p>'
html += '<p>스냅샷의 현재 본문 284개는 중앙 124개 · cs 110개 · sample 34개 · datasets 8개 · 도장 8개입니다. 이관 임시 24개·기록 1,528개·백업 463개는 별도 분류했습니다. draft 262개를 미확정 결정 262개라고 해석하지 않습니다.</p>'
html += '<p>공식 원문 접근 확인: RFC 10017 · MCP 인증 2026-07-28. <a href="wiki-review-v1.md">문자 문서의 외부 출처 링크</a>에서 원문을 확인할 수 있습니다. 두 문서의 접근 확인을 전체 외부 근거 검증으로 확대하지 않았습니다.</p>'
html += '<details><summary>본문 정독 목록 '+str(len(FULL))+'개</summary><ul>'+''.join('<li><a href="'+escape(rel_link(p),quote=True)+'">'+escape(p)+'</a></li>' for p in FULL)+'</ul></details>'
html += '<footer><p>작성 시각 '+escape(STAMP)+'<br>기존 계획서·베이스라인·제품 wiki 본문을 변경하지 않았습니다. 보고서 재생성 전 원본은 같은 폴더의 _backup에 보관합니다. 외부 글꼴을 내려받지 않으므로 이 기기에서는 설치된 한글·기본 글꼴로 표시합니다.</p><p>'+ ' · '.join('<a href="'+n+'">'+label+'</a>' for n,label in [('wiki-review-v1.md','문자 문서'),('findings-v1.json','문제·줄 번호'),('reading-coverage-v1.json','파일별 검토 범위'),('inventory.json','전체 스냅샷'),('structure-audit.json','구조 검사'),('existing-checker.log','기존 검사기 원문')])+'</p></footer></main></body></html>'
write_new(OUT/'wiki-review-v1.html',html)
print(json.dumps(dict(findings=len(F),full_read=len(FULL),current=len(overview),severity=Counter(x['severity'] for x in F),html=str(OUT/'wiki-review-v1.html')),ensure_ascii=False))
