"""최근 RAG 문서의 정본과 탐색 경로를 백업 후 연결한다. 일회성 작업 기록용."""
from pathlib import Path
import shutil
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime('%Y-%m-%d_%H%M') + '_rag_wiki_links'
changed = []
backups = []

def write(rel, text):
    p = ROOT / rel
    if p.exists():
        b = p.parent / '_backup' / STAMP / p.name
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
        backups.append(str(b.relative_to(ROOT)).replace('\\', '/'))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    changed.append(rel)

def insert(rel, marker, addition):
    p = ROOT / rel
    text = p.read_text(encoding='utf-8')
    assert marker in text, (rel, marker)
    assert addition.strip() not in text, 'Already applied'
    write(rel, text.replace(marker, marker + addition, 1))

report = 'final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md'
daily = 'program/research/daily_rag_slm/'
old_procedure = (ROOT / daily / '신모델_원본비교와_추가학습_절차.md').read_text(encoding='utf-8')

# 영역 색인을 본문 작성보다 먼저 등록한다.
insert('wiki/research/index.md', '|---|---|---|---|\n',
       '| [rag-slm-improvements.md](rag-slm-improvements.md) | 검색·소형 모델 개선 연구와 실험의 입구 | **여행** | 실측 후 채택 판정 |\n')
insert('final_project_cs/wiki/quality/index.md', '|---|---|\n',
       '| [slm-model-evaluation.md](slm-model-evaluation.md) | 새 모델 원본 비교·추가 학습·채택을 어떻게 구분하는가 |\n')
insert('final_project_cs/wiki/operations/index.md', '|---|---|\n',
       '| [gpu-work-queue.md](gpu-work-queue.md) | GPU 서버 A/B의 연구 일감을 어떻게 이어가는가 |\n')

write('wiki/research/rag-slm-improvements.md', '''---
type: research
title: RAG와 소형 모델 개선 연구
description: 외부 연구·실험·제품 적용의 근거를 찾는 입구
status: draft
domain: travel
tags: [data, evaluation, gpu]
impl_scope: cs
impl_scope_reason: 현재 여행 질의 인식과 검색의 적용 대상은 릴리스 프로젝트 cs이며 sample의 참고 계약을 바꾸지 않는다
---

# RAG와 소형 모델 개선 연구

여행 자료 검색과 사용자 질의 인식을 별도로 개선한다. 논문 결과는 재현 후보를 고르는 근거이며 우리 프로젝트의 성능 향상을 증명하지 않는다.

## 읽는 순서와 정본

| 알고 싶은 것 | 정본 |
|---|---|
| 어떤 연구를 검토하고 무엇을 시험했나 | [날짜별 연구 기록](../../program/research/daily_rag_slm/index.md) |
| 원본 모델을 어떻게 비교하고 추가 학습할까 | [모델 평가 기준](../../final_project_cs/wiki/quality/slm-model-evaluation.md) |
| 승인된 GPU 일감을 어떻게 이어갈까 | [GPU 작업 운영법](../../final_project_cs/wiki/operations/gpu-work-queue.md) |
| 제품의 자료 검색 경로는 무엇인가 | [RAG 검색](../../final_project_cs/wiki/context/rag-retrieval.md) |

## 연구에서 적용까지

```mermaid
flowchart LR
  A[논문·공식 구현 확인] --> B[현재 실패 유형과 연결]
  B --> C[별도 구현·고정 조건 시험]
  C --> D[독립 보류 자료로 검증]
  D --> E[회귀 기준 통과 후 작업 폴더 적용]
```

매일 마지막 확인 이후의 논문·모델 출시·가중치 수정판을 조사한다. 발표일과 확인일, 원문·공식 코드·버전을 기록한다. 후보별 적용 조건·비용·회귀 위험·개발 자료·보류 자료·사전 합격 기준을 정한다. 조사 완료, 검토 완료, 구현 완료, 실측 완료를 따로 관리한다.

검색 개선은 검색 적중과 근거 품질로, 질의 인식은 정상 요청 정답과 요청 없는 문장 오지목으로 평가한다. 한쪽 결과를 다른 쪽의 개선으로 쓰지 않는다. 사용자 자료 격리와 수치·고유명사·출처 보호를 유지하고 여행 자료만 사용한다.

## 확인된 범위와 남은 검증

`[실측 2026-10-08 작업 트리]` 학습률 조절의 별도 구현과 연결 검사는 끝났으나 본 학습 비교와 독립 보류 자료 검증은 대기 중이다. 연결 검사 통과를 정확도 개선으로 쓰지 않는다. 상세 상태는 [일일 연구 기록](../../program/research/daily_rag_slm/2026-10-08.md)과 [구조화된 실행 기록](../../program/research/daily_rag_slm/2026-10-08.json)에 있다.

연구 결과를 제품 반영으로 표시하려면 별도 보류 자료 검증·회귀 검사·실제 적용의 근거가 모두 필요하다. 모델 선별과 실서비스 배포는 별도 단계다.

문서 역할과 연결을 보완한 근거: [2026-10-08 문서 점검](../../final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md).
''')

body = old_procedure.split('## 매일 확인할 것', 1)[1].split('## 2026년 10월 8일 후보', 1)[0]
write('final_project_cs/wiki/quality/slm-model-evaluation.md', '''---
type: reference
title: 소형·대형 모델 비교와 추가 학습 기준
description: 원본 비교군에서 학습 후보를 고르고 별도 검증으로 채택하는 절차
status: draft
domain: travel
tags: [evaluation, gpu, testing]
---

# 소형·대형 모델 비교와 추가 학습 기준

우리 자료로 추가 학습하지 않은 원본을 먼저 비교하고, 상위권 소형 모델은 별도 학습판으로 시험한다. 모델을 학습 후보로 고르는 것과 서비스 모델로 채택하는 것은 서로 다른 판정이다.

이 페이지는 지속해서 따를 평가 절차의 정본이다. [후보 목록](../../../program/research/daily_rag_slm/model_release_watchlist.json)은 버전별 실제 실행 상태를 관리하고, [날짜별 기록](../../../program/research/daily_rag_slm/index.md)은 근거를 보관한다. 판정 규칙을 변경할 때 실행기의 조건과 함께 확인한다.

## 매일 확인할 것'''+body+'''
## 결과에 필요한 근거

실행마다 입력·정답 ID와 해시, 자료·프롬프트·시드·문턱, 모델 revision·양자화·엔진 버전, 답안 원본·오류·누락, 유형별 분자/분모, 반복 횟수·구간, 지연·메모리를 보관한다. 말로 답한 확신도와 토큰 확률은 같은 확률로 취급하지 않는다. 정확도와 같은 모델의 엔진 속도 비교를 분리한다.

새 독립 보류 자료는 작성·정답 검수·중복 검사 후 해시를 고정하고 최종 검증 전에 학습에 사용하지 않는다. 누적 개발 시험 결과만으로 채택하지 않는다.

## 인접 문서

- [평가 실행](eval-harness.md) — 제품 기능 평가의 입구
- [GPU 작업 운영법](../operations/gpu-work-queue.md) — 실행과 회수
- [연구 개요](../../../wiki/research/rag-slm-improvements.md) — 외부 근거와 적용 상태
- [문서 점검 기록](../records/reports/2026-10-08_rag-wiki-document-audit.md) — 정본 연결의 근거
''')

write('final_project_cs/wiki/operations/gpu-work-queue.md', '''---
type: runbook
title: GPU 연구 작업 대기열 운영
description: 승인된 GPU 서버 A/B에서 중복 없이 학습과 평가를 이어가는 방법
status: draft
domain: travel
tags: [gpu, evaluation]
---

# GPU 연구 작업 대기열 운영

승인된 GPU 서버 A/B의 준비된 일감을 유지하고 완료 결과를 로컬로 회수한다. 준비가 필요한 후보와 바로 실행 가능한 일을 구분한다. 단순 사용률을 채우려고 불필요한 시험을 반복하지 않는다.

## 시작 전에 확인

1. [최신 날짜별 기록](../../../program/research/daily_rag_slm/index.md), 현재 프로세스·잠금·대기열·GPU 메모리·저장공간을 읽는다. 이미 실행 중인 작업을 다시 시작하거나 중단하지 않는다.
2. [대기열 상태 기록](../../../program/research/daily_rag_slm/gpu_backlog_2026-10-08.json)에서 마지막 관측 시각을 확인하고 실제 상태와 대조한다. 이 파일은 날짜가 붙은 관측 기록이며 현재 프로세스의 생존을 보장하지 않는다.
3. 기계별 현재 계산, 다음 즉시 실행 가능한 일감, 준비가 필요한 후보를 따로 센다. 준비된 대기 작업이 기계별 3개 미만이면 아래 순서로 보충한다.

## 보충 순서

기존 누락 평가 → 완료 학습판 추가 평가 → 유망 신모델 원본 비교 → 선별된 소형 모델 학습 → 필요한 반복 시드·양자화·보정·검색 회귀 시험 순서로 준비한다. 앞 후보가 조건을 기다리면 다른 준비된 일을 먼저 실행한다. 선정·합격 기준은 [모델 평가 기준](../quality/slm-model-evaluation.md)을 따른다.

GPU 서버 A의 지속 평가 실행기는 [gpu_eval_queue.py](../../../program/scripts/plan_qa_bench/server/gpu_eval_queue.py)다. 실행기 PID가 살아 있으면 추가 실행기를 띄우지 않는다. 실행 위치의 manifest와 state, queue 로그, 작업별 답안·완료/실패 표시를 확인한다. manifest 보충 직전에 백업하고 같은 폴더의 임시 파일을 원자적으로 교체한다. 실패한 작업은 원인을 고친 새 판으로 기록한 뒤 재개하며 무조건 반복하지 않는다.

GPU 서버 B의 기존 후보 학습 뒤 학습률 비교는 [B56 실행 스크립트](../../../program/scripts/plan_qa_bench/server/queues/run_B56_daily_20261008.sh)로 이어진다. 순서를 변경하기 전에 기존 학습·대기 프로세스와 완료 표시를 확인한다. 완료 어댑터의 recipe 기록과 HF/GGUF 해시를 보관하고 GPU 서버 A에서 기반 모델·어댑터·평가 실행기 호환을 확인한 뒤 추가 평가를 넣는다.

## 완료·실패 처리

임시 폴더의 답안과 어댑터는 완료 시 즉시 로컬로 보관한다. 로그·실행 조건·입력 해시도 함께 회수한다. 기존 집계 산출물은 덮어쓰기 직전에 백업하며 오류·미완료를 평가 분모에서 빼지 않는다. 날짜별 기록에는 조사·검토·구현·실측의 완료를 나눠 적는다.

Strata 저장공간 제한은 사용자의 새 지시 없이 반복 재시작하지 않는다. 완료된 MAI 지정 시험은 보관하고 재실행하지 않는다. 기존 모델 영구 삭제·새 결제·GPU 임대·외부 게시·실서비스 배포는 별도 지시가 필요하다. 실제 접속 정보는 공용 문서에 넣지 않는다.

## 문서와 자동 확인

매일 한국 시간 오전 10시 연구 확인과 10분마다 대기열 확인은 같은 실행 기록을 공유한다. 의미 있는 완료·실패·비교 결과·필요한 사용자 조치가 있을 때만 보고한다. 기존 자동 확인 종료 조건보다 지속적인 일감 보충 지시가 우선한다.

지속 절차는 이 wiki와 평가 wiki에서 갱신하고, 매 작업의 변경·검증·미완료는 새 날짜의 `wiki/records/reports/`에 남긴다. wiki 본문과 log에는 결론 및 해당 리포트 링크를 연결한다. 새 문서는 먼저 영역 index에 등록한다. 날짜별 원본 기록은 보존한다.

초기 대기열을 만든 상세 근거는 [2026-10-08 운영 기록](../../../program/research/daily_rag_slm/GPU_대기열_운영_2026-10-08.md), 문서 정리는 [점검 기록](../records/reports/2026-10-08_rag-wiki-document-audit.md)에 있다.
''')

write(daily+'index.md', '''---
type: guide
title: 날짜별 RAG·소형 모델 연구 기록
description: 지속 절차의 wiki 정본과 날짜별 원본 근거를 연결한다
status: draft
domain: travel
---

# 날짜별 RAG·소형 모델 연구 기록

지속 절차는 [연구 개요](../../../wiki/research/rag-slm-improvements.md), [모델 평가 기준](../../../final_project_cs/wiki/quality/slm-model-evaluation.md), [GPU 작업 운영법](../../../final_project_cs/wiki/operations/gpu-work-queue.md)을 먼저 읽는다. 이 폴더는 날짜별 조사와 실행 상태를 보관한다.

| 기록 | 역할 |
|---|---|
| [2026-10-08.md](2026-10-08.md) · [실행 상태](2026-10-08.json) | 당일 조사·구현·실측과 재개 지점 |
| [신모델 후보 목록](model_release_watchlist.json) | 동일 revision 중복 방지와 준비·평가·학습 상태 |
| [GPU 대기열 상태](gpu_backlog_2026-10-08.json) | 날짜별 관측, 현재 상태는 실제 프로세스와 재대조 |
| [초기 GPU 운영 기록](GPU_대기열_운영_2026-10-08.md) | 대기열을 처음 구성한 시점의 근거 |
| [wiki 문서 점검](../../../final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md) | 문서 소유·연결·검증과 보완 내역 |

새 날의 기록은 새 파일로 추가한다. 당일 실행 상태를 갱신할 때 원본을 직전에 백업한다. 실행 중 시험을 다음 날 회수하되 날짜별 완료 표시만 보고 동일 작업을 중복 시작하지 않는다.
''')
write(daily+'신모델_원본비교와_추가학습_절차.md', '''# 새 모델 원본 비교와 추가 학습 — 정본 안내

지속 평가 절차의 정본은 [cs 프로젝트 모델 평가 wiki](../../../final_project_cs/wiki/quality/slm-model-evaluation.md)로 옮겼습니다. 기존 자동 확인의 진입 경로를 유지하기 위해 이 안내를 남깁니다.

후보별 최신 준비·실행 상태는 [신모델 후보 목록](model_release_watchlist.json), 날짜별 근거는 [연구 기록 색인](index.md)에서 확인합니다. 이전 절차와 당시 후보 상태는 같은 폴더의 `_backup/`에 보관했습니다. 정확한 보완·백업 위치는 [문서 점검 기록](../../../final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md)에 있습니다.
''')
p=ROOT/'program/research/index.md'
t=p.read_text(encoding='utf-8')
boundary=t.index('\n---',3)+4 if t.startswith('---\n') else t.index('\n')
write('program/research/index.md', t[:boundary]+'\n\n> 매일 RAG·소형 모델 개선의 입구: [연구 wiki](../../wiki/research/rag-slm-improvements.md) · [날짜별 연구 기록](daily_rag_slm/index.md).\n'+t[boundary:])

p=ROOT/'final_project_cs/wiki/quality/eval-harness.md'
t=p.read_text(encoding='utf-8')
write(str(p.relative_to(ROOT)).replace('\\','/'), t+'\n## 일정 항목 인식 모델의 비교\n\n원본 비교·추가 학습·최종 채택 조건은 [모델 평가 기준](slm-model-evaluation.md), 날짜별 실측은 [연구 기록](../../../program/research/daily_rag_slm/index.md)에서 확인한다.\n')
for rel, link in [('wiki/log.md','../'+report), ('final_project_cs/wiki/log.md','records/reports/2026-10-08_rag-wiki-document-audit.md')]:
    p=ROOT/rel
    text=p.read_text(encoding='utf-8')
    entry='\n## 2026-10-08 — RAG 연구·모델 평가·GPU 운영의 wiki 정본 연결\n\n최근 연구 문서의 정본·색인·작업 리포트 연결 누락을 보완했다. [문서 점검과 검증]('+link+').\n'
    if rel=='wiki/log.md':
        marker='\n# 문서 변경 이력\n'
        text=text.replace(marker,marker+entry,1)
    else:
        text+=entry
    write(rel,text)

write(report, '''# RAG·모델 비교 문서 관리 점검 — 2026-10-08

최근 연구 문서는 있었지만 wiki의 정본·색인·작업 리포트 연결은 누락됐다. 지속 절차와 날짜별 상태를 분리하고 기존 진입 경로를 보존했다.

## 범위와 근거

최근 RAG 작업의 산문 문서 3개(일일 연구, 초기 GPU 운영 기록, 신모델 평가 절차)를 중앙 wiki의 구조·문서 표준·작업 루프 및 cs 프로젝트 RULE과 대조했다. 다른 과거 연구 전체나 sample·datasets·dojo wiki 전체의 정합성 완료를 뜻하지 않는다.

수정 전 live wiki와 연구 색인에서 해당 세 문서의 진입 링크를 찾지 못했다. 전체 과거 기록의 모든 연결이 없다고 주장하지 않는다. 날짜별 연구·운영 기록은 보존하고 지속 평가 절차만 정본 안내로 교체했다.

## 정본과 변경

| 소유 | 문서 |
|---|---|
| 중앙 연구 wiki | [검색·소형 모델 연구 개요](../../../../wiki/research/rag-slm-improvements.md) |
| cs 평가 wiki | [원본 비교·추가 학습 기준](../../quality/slm-model-evaluation.md) |
| cs 운영 wiki | [GPU 작업 대기열 운영법](../../operations/gpu-work-queue.md) |
| 날짜별 조사·실행 근거 | [연구 기록 색인](../../../../program/research/daily_rag_slm/index.md) |

각 영역 index를 먼저 등록하고 본문을 작성했다. 중앙 연구 색인·cs 평가/운영 색인·연구 폴더 색인·평가 실행 문서·각 wiki log를 연결했다. 후보 준비 상태를 절차 정본에 중복해서 쓰던 부분은 후보 JSON을 참조하도록 바꿨다. 과거 연구 기록과 실제 GPU 실행은 변경하지 않았다.

## 검증

검증 출력과 예약 작업 반영은 아래 후속 검증 절에 기록한다. 문서 링크 검사는 모델 성능 시험이나 실서비스 반영의 증거가 아니다.

## 수정 직전 백업

'''+ '\n'.join('- ['+b+']('+str(Path('../../../../')/b).replace('\\','/')+')' for b in backups)+ '\n')
(ROOT/'program/scripts/rag_wiki_changes_20261008.json').write_text(json.dumps({'changed':changed,'backups':backups,'stamp':STAMP},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'changed':len(changed),'backups':len(backups),'stamp':STAMP},ensure_ascii=False))
