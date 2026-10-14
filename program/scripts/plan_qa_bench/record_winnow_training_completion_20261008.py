"""회수된 학습 산출물·부분 평가를 검증하고 학습과 평가 상태를 분리한다."""
from pathlib import Path
from datetime import datetime
import hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308'
DAILY = ROOT / 'program/research/daily_rag_slm'

def main():
    r = json.loads((BASE / 'training_archive_verified.json').read_text(encoding='utf-8'))
    assert r['local_remote_hashes_match'] and not r['evaluation_done']
    for name, info in r['hf_files'].items():
        assert hashlib.sha256((ROOT / r['hf_local'] / name).read_bytes()).hexdigest() == info['sha256']
    assert hashlib.sha256((ROOT / r['gguf_local']).read_bytes()).hexdigest() == r['gguf']['sha256']
    saved = errors = 0
    for item in r['evaluation_files']:
        p = BASE / item['name']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256']
        content = json.loads(p.read_text(encoding='utf-8'))
        for mode, counts in item['modes'].items():
            assert len(content[mode]['picks']) == counts['saved']
            assert content[mode]['_errors'] == counts['errors']
            saved += counts['saved']; errors += counts['errors']
    assert saved == 323 and errors == 0
    now = datetime.now(); stamp = now.strftime('%Y-%m-%d_%H%M%S') + '_winnow_training_completion'
    report = f'final_project_cs/wiki/records/reports/{stamp}.md'
    day = json.loads((DAILY / '2026-10-08.json').read_text(encoding='utf-8'))
    entries = day.setdefault('new_completed_trainings', [])
    assert not any(x.get('variant') == 'winnow_e4b_oos' for x in entries)
    backups = []
    def save(rel, text):
        p = ROOT / rel
        if p.exists():
            b = p.parent / '_backup' / stamp / p.name
            b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, b)
            backups.append(b.relative_to(ROOT).as_posix())
        p.write_text(text, encoding='utf-8')
    entry = {'variant':'winnow_e4b_oos', 'model':'Winnow-E4B (Jev family)', 'our_training':True,
        'full_training_complete':True, 'conversion_complete':True, 'training_recipe':r['training_recipe'],
        'hf_local':r['hf_local'], 'gguf_local':r['gguf_local'], 'hashes_verified':True,
        'basic_evaluation':{'saved_archived':saved,'expected':835,'files_archived':2,'files_expected':5,
            'errors_in_archived_files':errors,'complete':False,'observed_at_utc':r['observed_at_utc']},
        'additional_eval_queued':False,'resume':r['additional_eval_resume'],'report':report}
    entries.append(entry)
    state = json.loads((DAILY / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
    state['gpu_B'].update({'current':'winnow_e4b_oos basic evaluation','current_phase':'basic_evaluation',
        'current_full_training_verified':False,'completed_full_training_variants':1,
        'completed_winnow_e4b_oos_training_archived':True,'winnow_training_completion':entry})
    state['recorded_at'] = now.isoformat()
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY / '2026-10-08.md').read_text(encoding='utf-8') +
        f'\n## {now:%H시%M분} — Winnow-E4B 우리 여행 자료 학습 완료\n\n본 학습과 변환을 완료하고 HF/GGUF 및 로그를 해시 검증 후 보관했다. 기본 평가 답안323/835개·완료 파일2/5개를 회수했다. 부분 평가의 오류0이며 전체 성능 개선 판정은 대기다. 학습률 비교 두 판의 완료 표시와 혼동하지 않는다. [완료·조건·재개 리포트](../../../{report}).\n')
    name = Path(report).name
    for rel, text in [
        ('final_project_cs/wiki/quality/slm-model-evaluation.md',f'\n`[실측 2026-10-08]` Jev 계열 모델 중 Winnow-E4B의 우리 여행 자료 학습판을 보관했다. 기본·추가 평가와 독립 보류 검증 전 성능 향상이나 채택을 확정하지 않는다. [완료·조건·재개 근거](../records/reports/{name}).\n'),
        ('final_project_cs/wiki/log.md',f'\n## {now:%Y-%m-%d} — Winnow-E4B 여행 학습 산출물 보관\n\n본 학습·변환 완료와 부분 성능 평가를 분리해서 기록했다. [검증·재개 리포트](records/reports/{name}).\n')]:
        save(rel,(ROOT / rel).read_text(encoding='utf-8')+text)
    folder = '../../../../' + BASE.relative_to(ROOT).as_posix()
    body = f'''---
type: report
title: Winnow-E4B 여행 학습 산출물 보관
description: 본 학습·변환 완료와 기본 평가 진행을 분리한 실행 근거
status: draft
domain: travel
---

# Winnow-E4B 여행 학습 산출물 보관

[실측] Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 본 학습·변환 산출물을 보관했다. 성능 평가는 진행 중이다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 본 학습·변환 | 완료 | 1/1판 = 100% |
| HF/GGUF 보관·해시 확인 | 완료 | 2/2종 = 100% |
| 기본 평가 답안 보관 | 진행 | 323/835개 = 38.68% |
| 기본 평가 완료 파일 | 부분 완료 | 2/5개 = 40% |
| 추가 평가 등록 | 호환 확인 대기 | 0/5개 = 0% |

## 조건·원본 근거

첫 보강 여행 자료1,713개, 시드20261012·r16·2에폭·학습률0.0002·누적8의 레시피다. 본 학습193.9분이며 학습 로그의 최대 GPU 사용량10.6GB다. 기반 배포 원본은 보존했고 다른 모델이나 두 번째 보강 자료로 바꾸지 않았다. 개발사 결정 학습과 우리 여행 자료 추가 학습을 구분한다.

[HF 어댑터](../../../../{r['hf_local']}) · [GGUF 어댑터](../../../../{r['gguf_local']}) · [학습 로그]({folder}/qlora_train_winnow_e4b_oos.log) · [원격/로컬 해시·레시피·환경·기반 설정 검증]({folder}/training_archive_verified.json).

HF 가중치 SHA256 `{r['hf_files']['adapter_model.safetensors']['sha256']}`, GGUF SHA256 `{r['gguf']['sha256']}`다. 원격 파일과 로컬 사본을 비교했고 README·설정도 일치한다. 실행 환경 버전과 학습 도구·자료 해시는 검증 JSON에 고정했다.

## 부분 평가·한계

[완료 파일 mix10]({folder}/eval_winnow_e4b_oos_mix10.json)160개와 [완료 파일 mix11]({folder}/eval_winnow_e4b_oos_mix11.json)163개를 보관하고 원격 해시와 개수를 확인했다. 두 파일의 호출 오류0이다. 아직 회수하지 않은512개는 완료 정답이나 전체 오류0으로 표시하지 않는다. 전체835개 완료 후 B/C를 같은 문항으로 집계한다. 이번 기록은 학습 종료를 확인한 것이며 정확도 향상의 실측을 뜻하지 않는다.

## 다음 실행·변경 범위

GPU 서버 B의 기존 평가가 끝나면 나머지 기본 답안·로그를 회수한다. GPU 서버 A의 Winnow 배포 기반과 어댑터의 출처·구조·실행 호환을 확인한 다음 기존 실행기에 새 이름의 D/D2/D3/H/MX 다섯 평가를 등록한다. 원본·기존 학습판·고정 보류 자료와 비교 전 제품 모델로 승격하지 않는다.

GPU 서버 A는 준비된 평가5개가 대기하며 GPU 서버 B는 뒤 본 학습4개(기존 기반2개·자동 다운로드 준비2개)를 유지한다. 다운로드 직전 저장공간은 다시 확인한다. 실행기 추가·중복 실행·작업 중단·새 결제·기존 모델 삭제는 하지 않았다.

변경 파일은 일일 Markdown/JSON, GPU 상태 JSON, 모델 평가 wiki와 cs wiki log다. 새 회수 파일과 이 리포트는 새 이름이며 기존 근거를 덮지 않았다. 기존 상태·문서 수정 직전 백업:

'''
    body += '\n'.join(f'- [{p}](../../../../{p})' for p in backups)+'\n'
    save(report,body)
    print(json.dumps({'report':report,'backup_stamp':stamp,'basic_archived':saved,'full_training_complete':True},ensure_ascii=False))

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
