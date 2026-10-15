"""검증 결과와 변경 전후 그림을 새 이름으로 보존하고 해결한 결함 기록을 닫는다."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
E=CS/'wiki/records/evidence/2026-10-11_parallel_sonnet_finish'
A=CS/'wiki/records/reports/assets/2026-10-11_mobility_fixes_v56'
A.mkdir(exist_ok=False)
NOW=datetime.now(timezone(timedelta(hours=9)))
STAMP=NOW.strftime('%Y-%m-%d_%H%M')
REPORT=f'{STAMP}_택시출발과환승운임_결함3건_마무리.md'

def backup(path):
    dst=path.parent/'_backup'/f'{STAMP}_parallel_finish_results'/path.name
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,dst)
    return str(dst.relative_to(ROOT))

metrics={}
for stage in ['plan-regression-after','final-related']:
    data=ET.parse(E/f'{stage}.xml').getroot().find('testsuite').attrib
    run=json.loads((E/f'{stage}-run.json').read_text(encoding='utf8'))
    network=json.loads((E/f'{stage}-network.json').read_text(encoding='utf8'))
    assert int(data['failures']) == int(data['errors']) == int(data['skipped']) == 0
    assert run['exit_code'] == 0 and network['network_attempts'] == 0
    metrics[stage]={'tests':int(data['tests']),'passed':int(data['tests']),
                    'seconds':float(data['time']),**network}
assert sum(v['tests'] for v in metrics.values()) == 283

reviews=[]
exported=set()
for folder in ['approved','review-fixes']:
    source=Path(__file__).parent/folder
    dest=E/f'claude-{folder}'
    dest.mkdir(exist_ok=False)
    for file in source.iterdir():
        if file.suffix in {'.json','.log','.txt'}:
            shutil.copy2(file,dest/file.name)
    for file in source.glob('*-stdout.json'):
        value=json.loads(file.read_text(encoding='utf8'))
        models=list(value.get('modelUsage',{}))
        assert models == ['claude-sonnet-5-5'], (file,models)
        reviews.append({'stream':folder+'/'+file.stem,'models':models,'is_error':value.get('is_error',False)})
    for file in source.glob('*manifest.json'):
        for record in json.loads(file.read_text(encoding='utf8')):
            exported.add(record['file'])
assert len(exported) == 12
summary={'created_at':NOW.isoformat(),'product_fixes':3,'new_regression_cases':55,
         'previous_failures_resolved':7,'strict_feature_completion':{'completed':0,'total':21},
         'verification':metrics,'claude_reviews':reviews,'approved_exported_unique_files':sorted(exported),
         'limited_data_api_calls':0,'deployment':False,'actual_boarding_or_payment':False}
(E/'completion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')

code_files=['app/domains/travel_ops/instances/mobility/engine/'+x for x in
            ['plan.py','options.py','departure_context.py','departure_observer.py']]
code_files+=['app/domains/travel_ops/components/watch/trip_reminders.py']
code_files+=['tests/unit/travel/mobility/'+x for x in
             ['test_departure_taxi_v1.py','test_taxi_departure_consistency_v1.py',
              'test_transfer_boarding_interval_v1.py','test_transfer_fare_product_v1.py','test_plan_v1.py']]
run=subprocess.run([sys.executable,'-m','ruff','check',*code_files],cwd=CS,
                   capture_output=True,text=True,encoding='utf8')
(E/'ruff-final.log').write_text(run.stdout+run.stderr,encoding='utf8')
assert run.returncode == 0

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(1,3,figsize=(15,5),facecolor='#f7f8fa')
panels=[('택시 출발 시각','조회하지 않은09:01에29분 안내\n그 시각 모델은40분 → 목표11분 초과',
         '조회한08:58과29분 안내\n목표 여유 충족 · 남는 시간3분'),
        ('버스 환승 할인 경계','승차 폭12:35~12:45를 무시\n조건이 불확실해도1,550원 안내',
         '시간 폭 전체로30/60분 조건 검사\n불확실하면3,050원 상단 예상'),
        ('택시 출발 안내 연결','빈 차량 구간을 읽지 못함\n출발 안내 보류',
         '현재 시각 소요·요금 한 번 조회\n20분·19,000원 예상 안내')]
for ax,(title,before,after) in zip(axes,panels):
    ax.set_facecolor('#ffffff');ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    ax.text(.05,.9,title,fontsize=17,weight='bold',color='#172b4d')
    ax.text(.05,.72,'수정 전',fontsize=12,weight='bold',color='#ac3030')
    ax.text(.05,.61,before,fontsize=11,linespacing=1.7,color='#334155',va='top')
    ax.text(.05,.36,'수정 후',fontsize=12,weight='bold',color='#006b56')
    ax.text(.05,.25,after,fontsize=11,linespacing=1.7,color='#334155',va='top')
fig.suptitle('실제 코드 수정 3건 · 계획/운임/출발 관련 시험 283/283 통과',fontsize=21,weight='bold',y=1.02)
fig.text(.03,.015,'같은 개발 입력의 모델 재생입니다. 실제 배차·탑승·결제·운영 배포·전체21기능 완료 검증은 포함하지 않습니다.',fontsize=11,color='#475569')
fig.tight_layout(rect=[0,.07,1,.97])
fig.savefig(A/'fixes-before-after-v1.png',dpi=150,bbox_inches='tight')
plt.close(fig)
shutil.copy2(Path(__file__),A/'preserve-results-source.py')

backups=[]
debugs=CS/'wiki/records/reports/debugs'
entries=[('2026-10-11_1925_택시_출발시각과소요_불일치.md',
          '최종 출발 자체에서 조회해 성립한 결과만 반환하도록 수정했습니다. 신규9/9, 택시·출발 관련 최종 시험과283/283 전체 관련 시험이 통과했습니다. 시간대 경계 개발 재생에서 목표 여유 초과11→0분을 확인했습니다.'),
         ('2026-10-11_1930_후속버스_환승시간폭_누락.md',
          '후속 버스의 모델 승차 시간 폭 전체가 공식30/60분 조건을 만족하는지 검사하도록 수정했습니다. 신규23/23와 관련 시험이 통과했고 불확실한 경계 입력은1,550원 할인 주장 대신3,050원 상단 예상액으로 전달됨을 확인했습니다.'),
         ('2026-10-11_0439_이동_기존기대결과_불일치.md',
          '기존 실패7개를 현재 보행망·혼합 수단·자료 판 계약에 맞게 검토해 수정했습니다. 엄격 골든 비교와 따로 판정한 성립성 검사는 유지했습니다. 버스405의13:58 출발에서 지하철을 다시 판정해50원 비용 비교를 보존했으며 전체 계획 시험56/56가 통과했습니다.')]
taxi_debug=next(debugs.glob('2026-10-11_1937*_택시_출발직전_문맥누락.md'))
proper=debugs/'2026-10-11_1937_택시_출발직전_문맥누락.md'
if taxi_debug != proper:
    backups.append(backup(taxi_debug))
    taxi_debug.rename(proper)
entries.append((proper.name,'새 택시 문맥에 direct_taxi를 명시하고 현재 출발의 차량 모델을 재계산하여 출발 안내까지 연결했습니다. 신규23/23가 통과했고 최신20분·19,000원 예상액이 안내에 반영되며 저장 일정이 바뀌지 않음을 확인했습니다.'))
for name,reason in entries:
    path=debugs/name
    backups.append(backup(path))
    text=path.read_text(encoding='utf8')
    text=text.replace('## 미해결','## 해결됨 (2026-10-11)\n\n'+reason+
                      '\n\n검증 원문: [최종 관련 시험](../../evidence/2026-10-11_parallel_sonnet_finish/final-related.log), '
                      '[전체 계획 시험](../../evidence/2026-10-11_parallel_sonnet_finish/plan-regression-after.log), '
                      '[동일 입력 전후 재생](../../evidence/2026-10-11_parallel_sonnet_finish/fixes-before-after.json).',1)
    path.write_text(text,encoding='utf8')

report='''# 택시 출발·환승 운임 결함 3건 수정과 기존 실패 7건 정리

택시 시각 불일치, 후속 버스 할인 경계 누락, 택시 출발 안내 보류를 실제 코드에서 수정했습니다. 관련 시험283/283이 통과했습니다. 로컬 구현·검증 결과이며 전체 실사용 완료나 운영 반영을 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 재현한 실제 결함 수정 | 완료 | 3/3 = 100% |
| 신규 회귀 시험 | 통과 | 55/55 = 100% |
| 기존 실패 정리 | 해결 | 7/7 = 100% |
| 전체 계획 시험 | 통과 | 56/56 = 100% |
| 운임·출발 관련 시험 | 통과 | 227/227 = 100% |
| 전체21기능의 엄격 완료 | 아직 미충족 | 0/21 = 0% |

시험 분모283은 서로 다른 두 실행의56+227개이며 신규55개는 그 안에 포함됩니다. 전체21기능 분모는 기존 준비도 목록의21개 기능이며 제품 경로·대체 소스·허용 오차·새 표본 검증을 모두 충족해야 완료입니다. 시험 통과율을 실사용 준비율로 바꾸지 않습니다.

![수정 전후](assets/2026-10-11_mobility_fixes_v56/fixes-before-after-v1.png)

## 달라진 동작과 근거

택시 역산은 최대6번 안에서 실제 조회해 성립한 출발만 반환합니다. 조회하지 않은 새 출발에 이전 시간대의 소요·요금을 붙이던 문제를 제거했습니다. 통제 교통 입력에서 기존09:01·29분 안내는 그 시각 모델40분을 적용하면 여유 포함 목표보다11분 늦었습니다. 현재08:58·29분은 목표를 만족하고3분이 남습니다. 전역 최적 출발을 보장하는 탐색은 아닙니다.

후속 버스 환승은 평균 승차 한 점 대신 기존 모델의 승차 시간 폭 전체를 검사합니다. 서울시의 환승 시간은 후승 승차 시각을 기준으로 주간30분·21시~익일07시60분입니다. 07시·21시·자정 경계에서 폭을 나눠 검사하고 입력을 확인할 수 없으면 기존 할인 전 상단 예상액을 유지합니다. [서울시 통합환승 할인제도](https://news.seoul.go.kr/traffic/transfer_discount),2026-10-11 확인. 승차 폭은 기존 배차 모델이지 실제 최대 대기시간의 측정값이 아닙니다. 첫 승차·지하철 개찰 시각 불확실성은 이번 수정 범위 밖입니다.

택시 계획은 내부 출발 문맥에서 직접 택시임을 명시합니다. 현재 장소·자료 판·동행 조건을 확인한 뒤 현재 시각을 분 단위 올림해 차량 모델에 한 번 질의합니다. 같은 조회의 거리·소요·예상 요금을 출발 안내에 연결하고, 사전 여유 부족은 재계획, 조회 실패나 잘못된 수치는 안내 중단으로 반환합니다. 옛 빈 vehicle 문맥을 택시로 추정하지 않습니다. 기존 일정·공개 route 스키마는 보존됩니다. 배차 대기·실제 탑승·결제 측정은 없습니다.

## 기존 실패 7건의 처리

골든 두 개의 변경54항목을 검토했습니다. 선택 수단·노선·운임은 유지됐고 보행망 접근 거리·소요, 연결 시각, 추가 정류장 쌍·GTX-A 후보의 제외 사유가 달라졌습니다. [검토한 차이](../evidence/2026-10-11_parallel_sonnet_finish/golden-reviewed-changes.json)에 원값·새값·검토 원인을 남겼고 전체 동일 비교를 유지했습니다. 시험은 로컬 보행망과 제한 API 비활성 조건을 명시합니다. 기존 별도 재판정·도착 여유·코어 등록 검사가56/56 안에 그대로 포함됩니다. 현재 제외되는GTX-A 서울/서울역 표기 후보를 유효 경로로 승격한 것은 아닙니다.

자료 판 기대에는 실제 지하철 역 자료 해시를 추가했습니다. 버스·지하철 혼합 접두를 단일 버스로 읽던 시험을 구분했습니다. 전체 수단의14:00 출발에서는405가 늦어 제외되므로 이를 명시적으로 검사하며, 버스 전용의13:58 출발·접근 도보 중복 없음·표시 상한0에서도 계획 버스 보존을 따로 확인합니다. 요금 재계획 시험은13:58에 지하철도 다시 판정한 공통 시각 후보로1,550−1,500=50원 비교를 유지합니다. 실제 환승 결제와 동일하다고 단정하지 않습니다.

## Claude CLI 병렬 검토와 실행 조건

사용자가 승인한 비밀값 제외 최대12개 소스·시험 파일만 전달했습니다. 도구·MCP·브라우저를 끈 Claude CLI의 초기 운임/출발 병렬 검토2개와 수정본 추가 병렬 검토2개가 실제 모델claude-sonnet-5-5로 응답했습니다. 코드 수정은 검토 제안을 재현한 뒤 Codex가 수행했습니다. UTC 승차 문자열 때문에 고객 시각이 틀린다는 초기 제안은 안내 출력이 이미 한국 시각으로 변환하므로 기각했습니다. [검토 입력·응답](../evidence/2026-10-11_parallel_sonnet_finish/claude-approved/) · [추가 검토](../evidence/2026-10-11_parallel_sonnet_finish/claude-review-fixes/).

최종 [실행 요약](../evidence/2026-10-11_parallel_sonnet_finish/completion-summary.json), [계획 시험56개](../evidence/2026-10-11_parallel_sonnet_finish/plan-regression-after.log), [관련 시험227개](../evidence/2026-10-11_parallel_sonnet_finish/final-related.log), [수정 전후 개발 재생](../evidence/2026-10-11_parallel_sonnet_finish/fixes-before-after.json), [Ruff10파일](../evidence/2026-10-11_parallel_sonnet_finish/ruff-final.log)을 보존했습니다. 일부 중간 실행은 공용 코어 조립 중 파일 미확보와 시험 편집 시점의 구문 오류로 실패했고 최종 재실행에서 해소됐습니다. 중간 실패 로그도 삭제하지 않았습니다. Python 종료 후pyreadline3 정리 경고는pytest 종료코드0과 구분합니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(서버 응답): 안 했음. cs 프로젝트 서버 HTTP·운영 배포·외부 알림 전송은 검증하지 않았습니다. 로컬 제품 계획·재검증·안내 생성 함수를 실행했습니다.

## API 예비량·백업·남은 범위

제한 데이터API 호출0회·재시도0회이며 최종 시험과 개발 재생의 외부 연결 시도0회입니다. 공급자별 공유 누적 사용량·잔여량·갱신 시각을 확인하지 못했으므로 해당 API를 호출하지 않았습니다. 20% 예비량을 실측 확인했다고 주장하지 않습니다. Claude CLI의 승인된 코드 검토 통신은 별도입니다. 운영 한도·예약 주기·알림 정책은 바꾸지 않았고 커밋·푸시·배포·결제·외부 메시지 전송을 수행하지 않았습니다.

수정 직전 원본·대체 코드·골든·위키·결함 기록을 보존했습니다. [전체 백업 목록](../evidence/2026-10-11_parallel_sonnet_finish/backups-final.json)과 [최종 해시](../evidence/2026-10-11_parallel_sonnet_finish/integrity-final.json)로 확인할 수 있습니다. 데이터 원본은 수정하지 않았습니다.

전체21기능 완료는 아직0/21입니다. 실시간 후속 환승·급행/순환선·정렬된 새 웹 표본·복잡한 도로 제약·실탑승/결제·운영 제품 확인은 기존 남은 범위대로 유지합니다. 이번55개는 개발 회귀 시험이며 독립 표본 검증으로 부르지 않습니다.
'''
(CS/'wiki/records/reports'/REPORT).write_text(report,encoding='utf8')
wiki=CS/'wiki/teams/mobility.md'
backups.append(backup(wiki))
text=wiki.read_text(encoding='utf8')
heading='## 2026-10-11 택시 출발·환승 경계 결함 3건 검증\n\n택시 출발 조회 시각 불일치, 후속 버스 환승 시간 폭 누락, 택시 출발 안내 보류를 수정했습니다. 신규55/55·전체 계획56/56·관련227/227, 기존 실패7/7 정리입니다. 같은 개발 입력에서 택시 목표 여유 초과11→0분, 불확실한 할인1,550원→상단3,050원, 택시 현재20분·19,000원 예상 안내 연결을 확인했습니다. Sonnet5.5 실제 병렬 검토4응답을 보존했고 제한 데이터API0회·배포0·실탑승/결제0·전체 엄격 완료0/21입니다. [수정·검증 보고서](../records/reports/'+REPORT+') · [전후 그림](../records/reports/assets/2026-10-11_mobility_fixes_v56/fixes-before-after-v1.png).\n\n'
text=text.replace('# Mobility Team\n\n','# Mobility Team\n\n'+heading,1)
wiki.write_text(text,encoding='utf8')
(E/'closing-backups.json').write_text(json.dumps(backups,ensure_ascii=False,indent=2),encoding='utf8')
(E/'report-location.json').write_text(json.dumps({'report':str((CS/'wiki/records/reports'/REPORT).relative_to(ROOT)),'asset':str(A.relative_to(ROOT))},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'report':REPORT,'verification':metrics,'new_tests':55,'exported_files':len(exported)},ensure_ascii=False),flush=True)
