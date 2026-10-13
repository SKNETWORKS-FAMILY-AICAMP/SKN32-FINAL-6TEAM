"""완료 답안과 새 모델 준비를 오늘 기록에 반영한다. 수정 직전 원본을 백업한다."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

workspace = Path(__file__).resolve().parents[3]
research = workspace/'program/research/daily_rag_slm'
results = workspace/'program/scripts/plan_qa_bench/results'
preflight_root = results/'standardone_preflight_20261008'
if (preflight_root/'record_updated.json').exists():
    raise RuntimeError('Already recorded; use a new dated update')
tokenizers = json.loads((preflight_root/'tokenizer_probe.json').read_text(encoding='utf-8'))
context = json.loads((preflight_root/'travel_choice_h/context_probe_3b.json').read_text(encoding='utf-8'))
frog = json.loads((results/'gpu_backlog_20261008/frog_h/frog_h_counts.json').read_text(encoding='utf-8'))
a = json.loads((results/'gpu_backlog_20261008/A_snapshot_heartbeat_0057.json').read_text(encoding='utf-8'))
backups = research/'_backup'/datetime.now().strftime('%Y-%m-%d_%H%M_frog_and_standardone_preflight')
backups.mkdir(parents=True,exist_ok=False)
paths = [research/'2026-10-08.md', research/'2026-10-08.json',
         research/'model_release_watchlist.json', research/'gpu_backlog_2026-10-08.json']
for path in paths:
    shutil.copy2(path,backups/path.name)
watch_path = research/'model_release_watchlist.json'
watch = json.loads(watch_path.read_text(encoding='utf-8'))
for candidate in watch['candidates']:
    probe = next(t for t in tokenizers if t['repo_id']==candidate['repo_id'])
    folder = preflight_root/(candidate['repo_id'].split('-')[-1]+'_'+probe['revision'])
    meta = json.loads((folder/'preflight.json').read_text(encoding='utf-8'))
    candidate.update(revision_sha=meta['revision_sha'], weights_bytes=meta['weights_bytes'],
                     repository_last_modified=meta['last_modified'],
                     total_parameters=meta['safetensors']['total'],
                     language_parameters_nominal=3000000000 if candidate['repo_id'].endswith('3B') else 8000000000,
                     language_parameters_exact=None, active_parameters_exact=None,
                     license_body_verified=True, license_sha256=meta['license_sha256'],
                     license_notice_preserved=True,
                     status='revision_license_and_cpu_choice_tokenizer_verified; GPU_weight_and_runner_smoke_pending',
                     cpu_tokenizer_probe=probe,
                     prepared_suite=dict(suite='H',rows=1316,request_contains_gold=False,
                                         schema_and_information_checks_passed=5,
                                         schema_and_information_checks_total=5),
                     required_next_action='Build isolated HF 4-bit label-score runner; reserve model space after existing B54/B56; smoke 8192-token context then run matched original suites; do not use existing 4096-token JSON worker')
watch_path.write_text(json.dumps(watch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
daily_path=research/'2026-10-08.json'
daily=json.loads(daily_path.read_text(encoding='utf-8'))
daily['release_preflight'] = dict(verified=2,total=2, tokenizer_boundaries_passed=2,
                                 tokenizer_boundaries_total=2, prepared_h_requests=1316,
                                 cpu_contract_checks_passed=5,cpu_contract_checks_total=5,
                                 input_min_tokens=context['min_tokens'],input_max_tokens=context['max_tokens'],
                                 above_existing_4096_context=context['over_4096'],
                                 first_gpu_trial_context=8192, weights_downloaded=False,
                                 original_model_accuracy_measured=False,
                                 resume=watch['candidates'][0]['required_next_action'])
daily['new_completed_evaluations']=[dict(model='FrogNano-4B-2609',our_training=False,
                                       suite='H',saved=1316,expected=1316,errors=0,
                                       correct=419,positive_total=461,false_pick=377,negative_total=855,
                                       repetitions=1,full_ranking=False,
                                       report='program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_h/frog_h_report.md')]
daily_path.write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
queue_path=research/'gpu_backlog_2026-10-08.json'
queue=json.loads(queue_path.read_text(encoding='utf-8'))
queue['gpu_A'].update(state=a['state'],answers_saved_at_snapshot=a['answers'],
                     jobs_completed=1,jobs_running=1,jobs_ready_waiting=15,
                     snapshot='program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_heartbeat_0057.json',
                     observed_at='2026-10-08T09:57:00+09:00',
                     completed_frog_h_archived=True)
queue['gpu_B']['current_full_training_verified']=True
queue['latest_update_backup']=str(backups.relative_to(workspace))
queue_path.write_text(json.dumps(queue,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
backup_link='/C:/Users/playdata2/Documents/final_workspace/'+backups.relative_to(workspace).as_posix()
addition=f'''

## 10시 일일 확인 — 새 완료 답안과 신모델 실행 준비

오늘 조사·FINCH 구현은 중복 실행하지 않았습니다. 새로 끝난 FrogNano의 어려운 문장 평가를 보관·집계했고, StandardOne 두 후보의 수정판·라이선스와 CPU 선택지 입력을 실제 확인했습니다. 신모델 가중치의 GPU 시험은 아직 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| FrogNano H 답안 보관·문항 일치 | 완료 | 1,316/1,316 = 100% |
| FrogNano 정상 요청 정답 | 실측 | 419/461 = 90.89% |
| FrogNano 함정·잡담 오지목 | 실측 | 377/855 = 44.09% |
| 두 신모델 수정판·라이선스·토크나이저 경계 | 확인 완료 | 2/2 = 100% |
| 선택지 입력 형식·문항 정보 검사 | 통과 | 1,316/1,316 = 100% |
| 입력 변환 안전성 검사 | 통과 | 5/5 = 100% |

FrogNano-4B-2609는 우리 자료 추가 학습 없음·개발사 코딩 강화학습이 있는 배포판입니다. 정상 요청 461개와 정답 항목이 없는 855개가 각각 분모입니다. 오류·해석 실패·미완료 0개를 확인했고 모두 분모에 남깁니다. 항목 낱말이 섞인 잡담 118/118개, 짧고 모호한 말 99/150개, 새 항목 추가 요청 109/137개를 오지목해 후속 보강 후보로 기록합니다. 이미 본 H 진단 세트·한 번의 결과로 일반 우열을 확정하지 않습니다. [유형별 원본 집계](/C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_h/frog_h_counts.json)에 문항 일치·구간·해시·지연·실행 버전을 보관했습니다.

GPU 서버 A는 H 완료 후 혼합 요청 평가를 자동으로 시작했습니다. 이번 확인 순간 준비된 대기 15개·실행 중 1개이고, GPU 서버 B는 Winnow-E4B에 우리 자료로 본 학습 중이며 뒤 본 학습 4개가 예약돼 있습니다. 현재 두 기계 모두 보충 문턱인 대기 3개 미만에 해당하지 않아 새 GPU 작업을 중복 시작하지 않았습니다.

### 고정한 공식 모델 판과 파일 크기

| 후보 | 고정 수정판 | BF16 가중치 바이트 | 전체 매개변수 |
|---|---|---:|---:|
| [StandardOne-3B 공식 배포판](https://huggingface.co/StandardThinking/StandardOne-3B) | 70023495760b0cefecda7395377377f4d85a64fb | 7,698,241,064 | 3,849,090,048 |
| [StandardOne-8B 공식 배포판](https://huggingface.co/StandardThinking/StandardOne-8B) | ac495d1c221297f0ae951941eff27bcf58b5ce52 | 17,836,123,152 | 8,918,026,240 |

수치는 공식 API의 safetensors 파일 목록·매개변수 집계입니다. 모델 이름의 3B·8B는 언어 부분 명목 크기이며 비전까지 포함한 전체와 다릅니다. 언어·활성 매개변수의 정확한 개수를 잰 것으로 표시하지 않습니다. 두 LICENSE 전체 본문과 NOTICE를 읽고 보관했으며 두 라이선스 파일 SHA256이 동일했습니다. 한국어가 학습 혼합의 작은 몫이라는 공식 카드 한계도 유지합니다. 우리 학습 여부는 둘 다 없음이고 개발사 결정 학습은 있음입니다.

공식 선택지 API의 형식 검사에 맞춰 일정·앞 대화·고객 질문·선택 규칙을 유지하고 정답은 요청과 별도 파일로 분리했습니다. 26개를 넘는 선택지가 있어 공식 upper 라벨 선택 순서를 사용합니다. 실제 토크나이저에서는 AJ·AQ 등 일부 두 글자 조합이 빠지므로 알파벳 목록을 임의로 만들지 않습니다. 47개 선택지의 문맥 연결이 두 토크나이저 모두 통과했고 지원 라벨은 255개입니다. 이는 모델 정확도 시험이 아닙니다.

3B 입력 1,316개를 실제 토크나이저로 세니 4,131~4,785토큰이고 1,316/1,316개가 기존 실행기의 4,096토큰을 넘었습니다. 첫 GPU 연결 검사는 최소 8,192 문맥으로 준비합니다. 기존 JSON 생성 실행기에 그대로 넣어 실패·잘림을 숨기지 않습니다. [CPU 검사·고정 소스·요청 입력](/C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/results/standardone_preflight_20261008)에 보관했습니다. 입력 변환 코드는 [선택지 입력 준비 도구](/C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/standardone_choice_inputs.py)입니다.

재개할 일은 별도 HF 4비트 선택지 점수 실행기 구현 → 기존 B54/B56 뒤 모델 파일 공간 확보 → 긴 입력·GPU 메모리 연결 검사 → 같은 원본 시험 목록 실행입니다. 현재 돌아가는 학습·평가를 중단하지 않고, 새 결제·임대·기존 모델 삭제로 공간을 만들지 않습니다. 원본 성능과 상위권 판정은 아직 대기이며, 정확도·메모리 실측 전 채택하거나 새 모델 추가 학습을 완료했다고 쓰지 않습니다.

이 문서·일일 상태·후보 목록·GPU 요약의 수정 직전 판은 [백업]({backup_link})에 보관했습니다.
'''
with (research/'2026-10-08.md').open('a',encoding='utf-8') as f:
    f.write(addition)
with (preflight_root/'record_updated.json').open('x',encoding='utf-8') as f:
    json.dump(dict(backup=str(backups.relative_to(workspace)),frog_h_archived=1316,
                   model_preflight_verified=2,context_probe_rows=1316),f,indent=2)
print(json.dumps(dict(backup=str(backups.relative_to(workspace)),record_updated=True),ensure_ascii=True))
