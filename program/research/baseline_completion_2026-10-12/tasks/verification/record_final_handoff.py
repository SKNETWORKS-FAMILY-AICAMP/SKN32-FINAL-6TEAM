"""전체 실행 대조와 영향 재검증을 기존 결과 보존 후 인계한다."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
RUN = HERE / 'runs/2026-10-12_followup_064826'
now = datetime.now(ZoneInfo('Asia/Seoul'))
audit = json.loads((RUN / 'integration-original-audit.json').read_text(encoding='utf-8'))
drift = json.loads((HERE / 'runs/2026-10-12_clean_travel/source_drift_065201.json').read_text(encoding='utf-8'))
assert audit['all_original_counts_and_hashes_match'] and audit['unique_tests'] == 7850
assert audit['latest_per_test_counts'] == {'passed': 7827, 'skipped': 7, 'failed': 2, 'error': 14}
tests = []
for label, total in [('prior22-final', 22), ('cookie-security-final', 156), ('mapping-final', 14)]:
    result = json.loads((RUN / (label + '-outcomes.json')).read_text(encoding='utf-8'))
    rows = [r for r in result['reports'] if r['when'] == 'call' or (r['when'] == 'setup' and r['outcome'] != 'passed')]
    counts = dict(Counter(r['outcome'] for r in rows))
    before = json.loads((RUN / (label + '-source-before.json')).read_text(encoding='utf-8'))
    after = json.loads((RUN / (label + '-source-after.json')).read_text(encoding='utf-8'))
    assert counts == {'passed': total} and result['exit'] == 0
    assert before == after == drift['current_sha256'] and result['network_blocks'] == []
    tests.append({'label': label, 'passed': total, 'failed': 0, 'skipped': 0,
                  'exit': 0, 'finished_at_kst': result['finished_at_kst'],
                  'source_files': len(before), 'source_changed': 0,
                  'evidence': str((RUN / (label + '-outcomes.json')).relative_to(ROOT)).replace('\\', '/'),
                  'junit_sha256': hashlib.sha256((RUN / (label + '.xml')).read_bytes()).hexdigest()})
cleanup = json.loads((RUN / 'cleanup.json').read_text(encoding='utf-8'))
assert cleanup['stop_exit'] == 0 and cleanup['pid_absent']
source = drift['current_sha256']
source_sha = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
backup = HERE / '_backup' / (now.strftime('%Y-%m-%d_%H%M%S') + '_final_handoff')
backup.mkdir(parents=True)
for name in ('status.json', 'current-results.md', 'report.md', 'failure-handoff.md'):
    shutil.copy2(HERE / name, backup / name)
rel_backup = backup.relative_to(HERE).as_posix()
summary = {'at_kst': now.isoformat(), 'verification_evidence_complete': True,
           'product_acceptance': 'not_accepted', 'deployment': 'not_deployed',
           'independent_final_runs': tests, 'source_files': len(source), 'source_manifest_sha256': source_sha,
           'source_manifest_encoding': 'SHA256 of UTF-8 json.dumps(source, sort_keys=True, separators=(comma,colon))',
           'whole_run_original_audit': 'integration-original-audit.json',
           'latest_unique_test_observations': audit['latest_per_test_counts'], 'unique_tests': 7850,
           'remaining_test_count': 23, 'remaining_tests': audit['remaining'],
           'isolated_cluster_stopped': True, 'backup': backup.relative_to(ROOT).as_posix(),
           'limitations': ['고유 시험별 후속 관측은 단일 전체 재실행 통과가 아님',
                          '검색 자료2실패·14준비 오류 및 요식5·이동2건너뜀 유지',
                          '실제 개인 AI 공개 HTTPS·등록·쿠키·callback 미실행',
                          '실경보 방향18/20실패와 택시 미터1000원 이내2/4 별도 미충족',
                          '운영 영속 볼륨·무료 관측 충족률·가격 예외 미인수',
                          'Python 과정 내 연결 차단이며 자식 과정까지 OS 수준 격리를 보장하지 않음']}
summary_path = RUN / 'final-handoff.json'
assert not summary_path.exists()
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

text = f'''# 독립 검증 최종 인계 — {now.isoformat()}

검증 실행·원본 대조·수정 영향 재검증의 인계 자료를 완성했습니다. 제품 전체의 인수·배포 완료 판정은 보류합니다.

| 검증 작업 | 상태 | 실행 결과 |
|---|---|---|
| 이전 실패의 독립 재검증 | 통과 | 22/22 = 100% |
| 로그인·권한·보안 수정 영향 | 통과 | 156/156 = 100% |
| 이력 단계 분류 수정 영향 | 통과 | 14/14 = 100% |
| 통합 담당 전체·후속 원본 대조 | 일치 | 7/7회 = 100% |

위 독립 시험192개는 수정 영향 범위의 시험이며 제품 기능 완료율이 아닙니다. 3회 모두 실패0·건너뜀0·차단 시도0, 시작·종료 및 최종 관측의 소스1410개 해시가 같습니다. 실행 명령은 이 채팅 실행 기록과 각 collection/resume JSON에 남겼으며 [최종 JSON](runs/2026-10-12_followup_064826/final-handoff.json)에 결과·원본 링크·JUnit 해시를 기록했습니다.

## 전체 실행과 후속 관측의 구분

통합 담당의 원본 JUnit7개를 직접 다시 집계하고 SHA256을 비교했습니다. 7/7 집계·해시 일치, 공통·여행 시험 중복0개입니다. [독립 원본 감사](runs/2026-10-12_followup_064826/integration-original-audit.json)에 각 원본·실패 식별자·현재 소스와의 차이를 보존했습니다.

| 실행 원본 | 통과 | 실패 | 준비 오류 | 건너뜀 | 실행 시험 전체 |
|---|---:|---:|---:|---:|---:|
| 공통 전체 | 892 | 0 | 0 | 12 | 904 |
| 여행 전체 | 6892 | 2 | 37 | 15 | 6946 |

전체 실행 뒤 격리 실행기가 거절한 시험 자체 임시 DB23개, 공통 opt-in20개, OAuth8개 등의 후속 원본을 대조했습니다. 고유 시험7850개에서 마지막 관측은 **7827통과·2실패·14준비 오류·7건너뜀**입니다. 여러 실행의 시험 식별자를 대조한 수치이며 한 번의 전체 실행이 전부 통과한 결과가 아닙니다. OAuth의 customer 매개변수 한 사례만 수집 시 UUID를 표준화했고 다른 매개변수는 합치지 않았습니다.

검색 자료 관련16개(2실패·14준비 오류)는 현재 정책에 맞는 여행 규정12문서·130청크·실제1024차원 벡터가 필요한 시험입니다. 요식 원장5개와 이동 실자료2개도 건너뜀으로 남습니다. 자료 부족을 빈 벡터·임의 규칙·업무 DB 복사로 대체하지 않았습니다. 실제 개인 AI 종단, 무료 관측 충족률, 가격 예외, 운영 영속 볼륨도 별도 미인수입니다.

## 수정 원인과 최종 소스

앞선 단독 선택 실패4개는 이동 계산기의 프로세스 설정 키를 준비하지 않은 시험 초기화였습니다. 통합 담당이 두 시나리오 시험의 초기화를 보완했고, 기존 실패22개를 동일한 선택으로 새 프로세스에서 모두 통과시켰습니다. 제품의 재시작 보호 조건을 낮추지 않았습니다.

그 뒤 바뀐 로그인 차단 안내와 이력 단계 분류를 각각156개·14개로 재검증했습니다. [최종 소스 관측](runs/2026-10-12_clean_travel/source_drift_065201.json)의1410파일 명세 해시는 `{source_sha}`입니다. 파일 확장자는 .py/.json/.yaml/.yml/.sql/.sh, 범위는 app/tests/eval/config/deploy/scripts이며 backup/legacy/cache를 제외합니다. 웹 화면 전체·다른 확장자·동시 편집 잠금은 이 해시의 범위가 아닙니다.

통합 담당 원 실행의1237파일 범위에는 eval173개가 포함되지 않았습니다. 이를 원 실행 당시 동결 증거로 확대하지 않습니다. 독립 실행은 eval을 포함한1410파일을 관측했고, 앞선 독립 결과 이후 바뀐 것은 로그인 안내·두 시나리오 시험·이력 분류4파일뿐입니다. 변경 영향은 위3회로 확인했습니다. SQL 담당 소스14/14 해시는 최신 감사에서 일치했습니다.

## 관문과 환경 확인의 한계

원 전체 실행의 보안92/92·계약283/283·구조156/156·평가16/16은 하위 집계이며 전체 수에 더하지 않습니다. 기존 v11 관문에 연결된26/26항목은 통과했으나 당시 제목·시험 연결을 확인한 결과입니다. 현재 wiki의 실자료·외부 종단·운영 환경 인수를 대신하지 않습니다. 최근20개 이력 strict 검사와14개 분류 시험의 통과도 현재 기능·배포 완료율이 아닙니다.

mock 서버 시험(화면 반응): 이번 후속192개는 UI 시험이 아닙니다. 기존 택시 화면4/4 기록은 앞선 [환경·실자료 대조](runs/2026-10-12_followup_060032/external-evidence-061742.json)에서 별도 구분했습니다.

실서버 확인(서버 응답): 로컬 검증 전용 PostgreSQL16.14에서 합성 여행·계정으로 시험했고 [잔여 연결0·종료 기록](runs/2026-10-12_followup_064826/cleanup.json)을 남겼습니다. x600 서버의 cs 프로젝트 서버·외부 제공처에는 이번 확인에서 접근하지 않았습니다. PostgreSQL17 운영 환경 인수도 하지 않았습니다. Python 과정 내 외부 연결 제한은 자식 과정 전체의 OS 수준 차단을 뜻하지 않습니다.

기존 오라클 ARM 기록은 학습 없는 원본 Gemma-4-E4B QAT Q4_0의 검색 진단6/6과 작은 사례4/4 관측입니다. 당일 해당 환경 증거이며 현재 로컬 소스·다른 환경·전체 검색 인수를 뜻하지 않습니다. Jev 계열 모델 중 학습 없는 Winnow-E4B와 우리 여행 자료로 QLoRA한 비교 모델의 학습 상태도 구분했습니다. [기존 ARM 증거 검토](runs/2026-10-12_followup_060032/existing-arm-evidence-review.json)를 보존했습니다.

실경보 방향 판정은2/20통과·18실패, 택시 사전 미터 예측은1000원 이내2/4·4/4과소 예측·MAE1125원으로 남습니다. 기존 자료 원본을 대조했으며 외부 수집·고객 일정·추론을 새로 실행하지 않았습니다. 무료 관측의 실제 사건 발생부터 고객 전달까지 지연은 분모·시각이 부족해 계산하지 않았습니다. ODsay 약관 검토는 별도 연구 범위로 보존하며 자료 삭제·제품 기능 중단 근거로 쓰지 않았습니다.

## 인계 상태

검증 자료를 통합 담당이 사용할 수 있도록 저장했으므로 `verification_evidence_complete=true`, `phase=ready_for_integration`으로 인계합니다. 위 필수 미통과23개와 외부·환경 인수 조건을 명시하며 **제품 인수 상태는 not_accepted**입니다. 최종 통합 담당이 이 실패·미검증 범위를 바탕으로 v12·베이스라인의 완료 여부를 판정해야 합니다. 동일한 후속 자동 확인은 종료합니다.

업무 DB 변경·원격 배포·재시작·고객 알림·유료 호출·수집 예산 확대·commit·push·다른 채팅 메시지를 수행하지 않았습니다. [덮어쓰기 전 백업]({rel_backup}/)에 이전 결과·상태4개를 보존했습니다.
'''
final_report = HERE / 'final-handoff-2026-10-12.md'
assert not final_report.exists()
final_report.write_text(text, encoding='utf-8')
prefix = f'''## 최종 독립 검증 인계 — {now.isoformat()}

[최종 결과와 필수 미통과·미검증 범위](final-handoff-2026-10-12.md)를 먼저 확인합니다. 이전22건·보안156건·이력14건은 모두 통과했고 통합 원본7/7회 집계·해시가 일치했습니다. 제품 전체 인수는 보류입니다. 검색16건과 요식·이동 실자료7건은 남아 있습니다. [현재 JSON](runs/2026-10-12_followup_064826/final-handoff.json), [변경 전 백업]({rel_backup}/).

'''
for name in ('current-results.md', 'report.md', 'failure-handoff.md'):
    p = HERE / name
    p.write_text(prefix + p.read_text(encoding='utf-8'), encoding='utf-8')
status_path = HERE / 'status.json'
status = json.loads(status_path.read_text(encoding='utf-8'))
status.update(phase='ready_for_integration', updated_at_kst=now.isoformat(),
              verification_evidence_complete=True, product_acceptance='not_accepted',
              latest_final_evidence=summary_path.relative_to(ROOT).as_posix(),
              latest_final_report=final_report.relative_to(ROOT).as_posix(),
              final_independent_runs=tests,
              dependencies_remaining=['현재 정책에 맞는 여행 검색 자료·실제 벡터16개 전제',
                                      '요식 원장5개·이동 실자료2개',
                                      '개인 AI 공개 HTTPS·등록·쿠키·callback 실제 종단',
                                      '실경보 방향·택시 미터 정확도·무료 관측 충족률·가격 예외·운영 영속 볼륨 인수'],
              unresolved=['고유7850개 마지막 관측: 7827통과·2실패·14준비 오류·7건너뜀; 단일 전체 통과 아님',
                          '기존 Windows native crash 원인 미확정; 이후 새 프로세스 통과로 원인을 단정하지 않음',
                          '운영·외부 환경 현재 인수는 미실행'],
              deployment='not_deployed', source_manifest_sha256=source_sha,
              ready_reason='검증 수행·실패 재검증·전체 원본 대조·환경 한계 인계 자료를 완성했습니다. 필수 실패·자료 부족을 명시하며 제품 전체 완료를 판정하지 않습니다.',
              backup=backup.relative_to(ROOT).as_posix(), followup_check_termination_requested=True)
for p in (Path(__file__), HERE / 'audit_final_suite_evidence.py', final_report):
    rel = p.relative_to(ROOT).as_posix()
    if rel not in status['changed_files']:
        status['changed_files'].append(rel)
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'report': final_report.relative_to(ROOT).as_posix(), 'backup': backup.relative_to(ROOT).as_posix(),
                  'phase': status['phase'], 'source_files': len(source), 'source_manifest_sha256': source_sha,
                  'final_independent_passed': sum(t['passed'] for t in tests), 'product_acceptance': status['product_acceptance']}, ensure_ascii=False))
