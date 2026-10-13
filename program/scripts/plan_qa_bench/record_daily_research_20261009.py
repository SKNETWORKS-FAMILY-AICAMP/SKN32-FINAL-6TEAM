"""Reconcile dated research evidence; back up each existing artifact immediately."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
DAY = ROOT / "program/research/daily_rag_slm"
REPORT = "final_project_cs/wiki/records/reports/2026-10-09_1015_daily-research-and-serving.md"
OUT = ROOT / "program/scripts/rag_gate/results/daily_20261009_selective_v1"
NOW = datetime.now(ZoneInfo("Asia/Seoul"))
STAMP = NOW.strftime("%Y-%m-%d_%H%M%S") + "_daily_research_measured"
BACKUPS = []


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, body):
    if path.exists():
        backup = path.parent / "_backup" / STAMP
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup / path.name)
        BACKUPS.append((backup / path.name).relative_to(ROOT).as_posix())
    path.write_text(body, encoding="utf-8")


def save_json(path, obj):
    save(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main():
    assert not (ROOT / REPORT).exists(), "Do not repeat today's registered research reconciliation"
    result = read(OUT / "summary.json")
    decisions = [json.loads(line) for line in (OUT / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(decisions) == 1700
    assert sum(v['complete'] for suites in result['summaries'].values() for v in suites.values()) == 1700
    assert all(v['failures'] == 0 for suites in result['summaries'].values() for v in suites.values())
    papers = [
        dict(id="2610.09412v1", title="Finding the Right Balance: Relevance and Diversity in LLM Retrieval",
             publication="2026-10-07", checked="2026-10-09", recency="Newly reviewed recent paper; not claimed published after last survey",
             sources=["https://arxiv.org/abs/2610.09412", "https://arxiv.org/html/2610.09412v1", "https://github.com/GuillaumeBrouillette/finding-the-right-balance"],
             official_code_commit="not pinned; independently implemented equations, no upstream source copied",
             problem="Repeated similar evidence can occupy top-k; indiscriminate diversity can displace correct evidence",
             method="RNG score with strict closer-neighbor obstruction and selective Vendi/MMR; h1 exact nearest fallback",
             conditions="Strong/weak encoders, fixed pools; multi-evidence QA, controlled duplicates/overlap; h deployment estimator remains unresolved",
             cost="Existing normalized embeddings, small CPU matrix operations; no teacher/generator/model download",
             risk="False h2 assumption and clean-pool diversification lower relevance; alternate acceptable gold documents do not establish complementary evidence",
             developer_sets="RAG A180 and previously used B160; not itinerary A-E or fresh holdout",
             holdout="New independent travel retrieval evidence labels required; previously used H not read",
             criteria="Each set Recall@3>=90%, null false display<=2%, shown gold>=dense baseline, no new null false positives",
             state="Implemented, logic7/7; frozen five-variant measurement complete; gates failed; not adopted"),
        dict(id="2609.34776v1", title="Page-Aware Retrieval-Augmented Generation for EvalLLM 2026",
             publication="2026-09-28", checked="2026-10-09", recency="Recent background found after expanding window",
             sources=["https://arxiv.org/abs/2609.34776", "https://arxiv.org/html/2609.34776v1"],
             official_code_commit="Not identified in inspected manuscript; implementation availability not exhaustively established",
             problem="Semantic and lexical retrieval disagree; multi-part request may need separate evidence",
             method="Page-aware PDF chunks, dense/BM25 RRF, cross-encoder, optional query decomposition",
             conditions="French PDF595 challenge; 220-word chunks/40 overlap; RRF constant60/pools60; rerank25; gpt-5.4-mini generation",
             cost="RRF CPU low; cross-encoder/decomposition add inference and latency",
             risk="Dense or fused retrieval can underperform BM25; decomposition prompts/count/aggregation incompletely specified",
             developer_sets="Same frozen RAG A180/B160 for isolated RRF component only",
             holdout="New independent retrieval labels; no final holdout accessed",
             criteria="Same per-set retrieval/null gate as preregistration; no full-PDF or generator reproduction claim",
             state="RRF component implemented/tested; A null false4->2, B recall35->33; failed, no product change"),
        dict(id="2509.20758v3", title="SFT Doesn't Always Hurt General Capabilities",
             publication="2025-09-25", revision_date="2026-01-28", checked="2026-10-09", recency="Older background/reproduction candidate; not new October result",
             sources=["https://arxiv.org/abs/2509.20758", "https://arxiv.org/html/2509.20758v3"],
             official_code_commit="Not pinned in this review; implementation deferred",
             problem="Our trained models trade lower false picks for lower normal-request accuracy",
             method="Low learning rate and detached token-loss-dependent TALR weights with floor; weighted mean over supervised tokens, not weight renormalization",
             conditions="Domain supervised tasks and general capability checks; validate tau/floor/masking and packed batches before recipe",
             cost="Same teacher-free forward/backward, added per-token loss and class diagnostics",
             risk="Rare item IDs and null tokens may receive lower weight; short JSON target differs from paper tasks",
             developer_sets="Fixed normal/null/compound and D/H/E regression diagnostics; current FINCH/cosine repeat must finish first",
             holdout="Independent travel normal240/null480, human adjudication and frozen hashes pending",
             criteria="No normal-request regression, null upper limit and independent holdout; multiple paired seeds, no best-seed selection",
             state="Method reviewed; not implemented, queued or adopted; resume with class/token-loss probe after existing controlled schedules"),
    ]
    source_record = dict(date="2026-10-09", observed_at_kst=NOW.isoformat(), papers=papers,
                         survey_scope="Selected primary sources, not exhaustive publication inventory; searched last-day terms then broadened recent window",
                         search_queries=["site.arxiv.org/abs/2610 Oct2026 retrieval augmented generation small language model", "site.arxiv.org 8Oct2026 retrieval fine tuning"],
                         preregistration="program/research/daily_rag_slm/2026-10-09_retrieval_prereg_v1.json",
                         measurement="program/scripts/rag_gate/results/daily_20261009_selective_v1/summary.json",
                         code="program/scripts/rag_gate/rag_improve/selective_retrieval_20261009.py",
                         no_more_parameter_tuning_on_same_sets_today=True, independent_validation_completed=False, adopted=False)
    save_json(DAY / "2026-10-09_sources_and_review_v1.json", source_record)

    releases = read(ROOT / "program/scripts/plan_qa_bench/results/release_watch_20261009_v1/summary.json")['repositories']
    releases += read(ROOT / "program/scripts/plan_qa_bench/results/release_watch_20261009_extra_v1/summary.json")['repositories']
    watch = read(DAY / "model_release_watchlist.json")
    for r in releases:
        rid = r['repo_id']
        if any(c['repo_id'] == rid and c.get('revision_sha') == r['revision'] for c in watch['candidates']):
            continue
        valen = rid.startswith("Valen-Team/")
        north = rid.startswith("CohereLabs/")
        kolibri = rid.startswith("Aleph-Alpha/")
        license_file = next((f for f in r['metadata_files'] if f['name'] == 'LICENSE'), None)
        c = dict(repo_id=rid, revision_sha=r['revision'], checked_date="2026-10-09",
                 source_url="https://huggingface.co/"+rid, repository_created_at=r['created_at_utc'],
                 repository_last_modified=r['last_modified_utc'], total_parameters_exact=r['parameters']['total'],
                 language_parameters_exact=None, active_parameters_exact=None,
                 weights_bytes=r['weight_bytes'], weights_manifest=r['weights'],
                 our_finetuning=False, original_benchmark_completed=False, upper_tier=None,
                 korean_travel_measured=False, declared_languages=r['card_data'].get('language', []),
                 license=r['card_data']['license'], license_body_verified=valen or kolibri,
                 license_sha256=license_file['sha256'] if license_file else None,
                 license_body_scope="Full pinned LICENSE read; same Valen2/4 body hash verified" if valen else "Full pinned LICENSE read; card weights/config-only scope" if kolibri else "Card declared; repository siblings have no selected LICENSE filename, full model license provenance pending",
                 evidence=r['path'], original_benchmark_state="not started", product_adoption=False,
                 publisher_benchmarks_are_not_project_measurements=True)
        if valen:
            c.update(publisher_reported_release_date="2026-10-07", release_source="https://github.com/Liuziyu77/Valen",
                     model_role="Qwen3.5 backbone plus Mixer Choice/Noul/Score decision head; text/images/video",
                     publisher_training="Millions of decision samples;0.8/2 native full SFT FP32;4B merged LoRA/Mixer/visual merger",
                     language_parameters_nominal={"Valen-0.8B":800000000,"Valen-2B":2000000000,"Valen-4B":4000000000}[rid.split('/')[1]],
                     runtime="Custom audited local code for0.8B; Transformers>=official5.4.0; native shared_state/temperature1; no JSON generation speed equivalence",
                     finetune_eligibility="Only after matched original top3, small-language scope and real memory smoke; no ranking yet",
                     status="0.8B executable contract and existing runtime preflight passed; download/smoke registration in progress" if rid.endswith("0.8B") else "Public review complete; weight bytes exceed current disk free with3GiB reserve; preparation only",
                     required_next_action="Recheck actual space; pin local source+processor+weights SHA; original smoke12 then five matched suites; preserve all failures; only qualifying model proceeds to fresh adapter training")
            c['custom_code_review_files'] = 9 if rid.endswith('0.8B') else 0
        elif north:
            c.update(publisher_reported_release_date="2026-08-12", release_source="https://huggingface.co/blog/CohereLabs/meet-north-micro-vision-instruct",
                     language_parameters_nominal=2000000000, vision_parameters_nominal=400000000,
                     model_role="Multilingual vision/text instruction generation; no supported agent/tool workflow",
                     publisher_training="Publisher instruction-trained multimodal release", runtime="Official5.16.0 Transformers; text-only supported, system prompt not recommended",
                     status="reviewed; full license provenance and isolated runner/context checks pending; insufficient concurrent disk reserve after Valen0.8",
                     required_next_action="Finish license provenance; deterministic travel text-only contract; space/preflight before download",
                     finetune_eligibility="pending matched original comparison and actual fit")
        elif kolibri:
            c.update(publisher_reported_release_date="2026-10-03", announcement_date="2026-10-05",
                     release_source="https://aleph-alpha.com/en/blog/kolibri-has-landed-a-sovereign-open-weight-model/",
                     active_parameters_exact=3457573120, model_role="German/English sparse MoE reasoning generation",
                     publisher_training="Publisher instruction SFT/RL", runtime="kolibri1 vLLM plugin;78.84GB FP8 exported weights",
                     status="reviewed; existing disk/GPU capacity insufficient, no download",
                     required_next_action="Keep pinned metadata; re-evaluate only if existing approved capacity changes; no rental/payment/deletion",
                     finetune_eligibility="78.1B total is outside small language scope;3.46B active alone does not establish SLM")
        else:
            c.update(publisher_reported_release_date="2026-10-07", release_source="https://www.perplexity.ai/hub/blog/multimodal-embeddings-beyond-a-single-vector",
                     model_role="Multivector128D/token MaxSim retriever; not text-generation or item-selection SLM",
                     active_parameters_publisher_reported=340000000, publisher_training="Internal18B ColBERT teacher distillation; full finetuning of0.6B release",
                     status="official card/revision screened; full MIT provenance, ST6 runtime and new multivector travel index pending",
                     required_next_action="Isolated ST>=6 compatibility+license; own travel-only130-doc index; same frozen retrieval development contract then new independent retrieval holdout; keep1024D DB index separate",
                     finetune_eligibility="Retrieval role has separate gates; do not rank with generative original comparison")
        watch['candidates'].append(c)
    watch.update(last_checked_date="2026-10-09", latest_check_scope="Daily selected6 official revisions plus3papers; not exhaustive global inventory", updated_at_kst=NOW.isoformat())
    save_json(DAY / "model_release_watchlist.json", watch)

    armroot = ROOT / "program/scripts/plan_qa_bench/results/daily_20261009_arm_v1"
    obs = read(armroot / "observation.json")
    verification = read(armroot / "archive_verification.json")
    source = ROOT / "datasets/travel/arm_serving_20261008/d3.json"
    rows = read(source)
    answers = [json.loads(line) for line in (armroot / "completed/e4bt_q8_d3/answers.jsonl").read_text(encoding='utf-8').splitlines()]
    index = {r['i']:r for r in rows}
    metadata_match = sum(all(a[k] == index[a['i']][k] for k in ('set','type','gold')) for a in answers)
    assert metadata_match == 360
    assert hashlib.sha256(source.read_bytes()).hexdigest() == obs['state']['jobs']['e4bt_q8_d3']['job']['prompt_sha256']
    actual_correct = sum(a['parsed'] and a['pick'] == index[a['i']]['gold'] for a in answers)
    assert actual_correct == verification['summary']['correct']
    save_json(armroot / "parent_counts_verified.json", dict(metadata_match=metadata_match, expected=360, actual_correct=actual_correct, failures=sum(not a['parsed'] for a in answers), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    arm = read(DAY / "arm_serving_2026-10-09.json")
    arm.update(recorded_at_kst=NOW.isoformat(), resource_observed_at_utc=obs['observed_at'], resource_measurement=obs['resource_summary'],
               free_bytes=obs['free_bytes'], current_job_at_observation=obs['active']['job_id'], saved_at_observation=obs['active']['saved'],
               expected_at_observation=obs['active']['expected'], completed_jobs=2, running_jobs=1, pending_jobs_after_refill=11,
               completed_Q8_D3=verification['summary'], Q8_archive_verification="program/scripts/plan_qa_bench/results/daily_20261009_arm_v1/archive_verification.json",
               source_observation="program/scripts/plan_qa_bench/results/daily_20261009_arm_v1/observation.json", report=REPORT)
    arm['next_actions'][0] = "Q8 completed/archived; preserve existing ABBA cache diagnostics; do not repeat Q8 main suite"
    save_json(DAY / "arm_serving_2026-10-09.json", arm)

    table = "| 검색 방식 | RAG 개발 A 정답 근거@3 | A 요청 없음 오노출 | RAG 개발 B 정답 근거@3 | B 요청 없음 오노출 |\n|---|---|---|---|---|\n"
    for name in result['summaries']['A']:
        a,b = result['summaries']['A'][name],result['summaries']['B'][name]
        table += f"| {name} | {a['recall3']}/100 = {a['recall3']:.2f}% | {a['null_false_show']}/60 = {100*a['null_false_show']/60:.2f}% | {b['recall3']}/48 = {100*b['recall3']/48:.2f}% | {b['null_false_show']}/50 = {2*b['null_false_show']:.2f}% |\n"
    report = f"""---
type: report
title: 2026-10-09 일일 논문 검토·검색 실측·신모델 준비와 ARM 회수
description: 고정 여행 자료의 검색 개선을 시험하고 실패 기준과 후속 후보를 보존했다
status: draft
domain: travel
tags: [research, evaluation, rag, slm, serving]
---

# 일일 논문 검토와 실제 시험

검색 개선 구현은 실제로 시험했으나 전체 기준을 통과하지 못해 제품에 적용하지 않았다. 새 소형 결정 모델은 원본 조건을 검토해 기존 GPU 대기열로 시험 준비를 진행하고, 완료된 학습판과 ARM 답안을 회수했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 선정 논문 방법·조건 검토 | 완료 | 3/3 = 100% |
| 검색 구현 로직 검사 | 통과 | 7/7 = 100% |
| 고정 개발 자료 검색 실측 | 완료·기준 실패 | 1700/1700 = 100% |
| 공식 신모델 revision 확인 | 완료 | 6/6 = 100% |
| ARM 신규 완료 답안 회수 | SHA·문항 일치 | 360/360 = 100% |

관측·기록 시각: {NOW.isoformat()}. 선정 조사는 전 세계 출시 전체를 망라하지 않는다. 발표일과 확인일은 아래 원문·구조화 기록에서 구분한다. 검색의 개발 A/B는 일정 선택의 A~E 시험과 다르다.

## 논문에서 선택한 방법과 적용 조건

- [검색 관련성과 다양성 연구](https://arxiv.org/html/2610.09412v1), v1 10월7일: 비슷한 근거가 상위를 차지할 때만 다양성을 높이는 방법이다. 기존 벡터로 계산할 수 있으나 실제 필요한 근거 수를 모르면 정상 근거를 밀어낼 수 있다. 공개 식을 별도 구현했다. 저자 코드를 복사하거나 전체 벤치마크를 재현한 것은 아니다. [저자 저장소](https://github.com/GuillaumeBrouillette/finding-the-right-balance)는 확인했으나 커밋은 고정하지 않았다.
- [페이지 단위 RAG 연구](https://arxiv.org/html/2609.34776v1), v1 9월28일: 프랑스어 PDF595문항에서 페이지·문자/의미 검색 합산·재정렬·질문 분해를 비교했다. 220단어/40겹침, RRF60·목록60 조건 중 합산만 시험했다. 분해 세부 프롬프트 등은 열린 원문에서 충분히 확보하지 못해 전체 파이프라인 재현으로 표시하지 않는다.
- [도메인 추가 학습과 일반 능력 연구](https://arxiv.org/html/2509.20758v3), v1 2025년9월25일·v3 2026년1월28일: 작은 학습률과 토큰 손실에 따른 가중치를 검토했다. 낮은 확률의 일정 ID·null 토큰을 덜 학습할 위험이 있어 현재 두 시드 비교와 토큰별 진단을 먼저 회수한다. 이 방법은 구현·학습 중이 아니다.

각 방법의 해결 문제·추론/학습 비용·회귀 위험·개발/보류 자료·합격 기준·재개 지점은 [선정과 검토 원본](../../../../program/research/daily_rag_slm/2026-10-09_sources_and_review_v1.json)에 있다. 논문 수치를 우리 실측으로 옮기지 않았다. 최근 하루 검색을 우선한 뒤 기간을 넓혔으며 새로 확인한 이전 연구를 새 발표라고 부르지 않는다.

## 검색 실측 결과

여행 문서130개와 기존 BGE-M3 임베딩 캐시를 고정했다. 총340개 고유 개발 질문(A180·B160)을 방식5개로 재생해1700개 결정을 보관했다. 생성 모델 호출은 없으며 실패0개다. 정상 분모는 A100/B48, 요청 없음은 A60/B50, 부분 근거 질문 A20/B62는 별도 상태로 남겼다. 정답 근거@3는 허용 정답 문서 중 하나라도 상위3개에 있으면 맞음이다. 원문 수치·고유명사·출처·사용자 격리 계약은 바꾸지 않았다.

{table}

RRF는 A의 오노출을 줄였지만 B 정답 근거는35/48에서33/48로 떨어졌다. RNG는 A 한 질문만 늘고 B는 그대로다(같은 문항 정확검정 p=1.0). h1은 원래 상위 결과와340/340 동일하다. h2는 정답에서 추정한 값이 아니라 필요한 근거를2개로 가정한 진단이며 실제 복합 근거 판별기의 성능이 아니다. B가32/48로 떨어져 적용하지 않는다. 모든 방식은 세트별90% 적중·요청 없음2% 이하·기존 정상 근거 보존 기준을 통과하지 못했다. 같은 개발 자료로 매개변수를 더 고르지 않는다.

별도 보류 검증은 아직 하지 않았다. 전에 사용한 H 파일은 이번 실행에서 읽지 않았다. 선택 계산의 짧은 CPU 시간은 임베딩·BM25 준비·답변 생성·네트워크를 제외한 관측이며 실서빙 지연 비교가 아니다.

[사전 고정 조건](../../../../program/research/daily_rag_slm/2026-10-09_retrieval_prereg_v1.json) · [실행 도구](../../../../program/scripts/rag_gate/rag_improve/selective_retrieval_20261009.py) · [전체 집계](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/summary.json) · [1700개 원본 결정](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/decisions.jsonl).

## 새 모델 원본 비교 준비

| 공식 배포판 | 전체 매개변수 | 가중치 바이트 | 현재 준비 상태 |
|---|---|---|---|
| Valen-0.8B | 854,305,641 | 3,417,285,852 | 기존 실행환경·코드9파일·라이선스 확인, 원본 시험 등록 준비 |
| Valen-2B | 2,214,825,577 | 8,859,381,820 | 기존 공간과3GiB 보존 조건 초과 |
| Valen-4B | 4,540,981,545 | 9,085,489,252 | 기존 공간과3GiB 보존 조건 초과 |
| North Micro Vision Instruct | 2,484,847,856 | 4,969,765,248 | 언어 약2B·한국어 카드, 라이선스 출처·문맥 실행기 준비 대기 |
| Kolibri-1 | 78,103,074,560 | 78,841,467,208 | 활성3,457,573,120과 전체를 구분; 기존 용량 초과 |
| pplx-embed-v2-late-0.6b | 594,321,600 | 2,377,845,560 | 토큰별128차원 검색기; MIT 본문 출처·ST6·별도 색인 준비 |

Valen은10월7일 출시 공지를 확인했고0.8B/2B의 카드 수정일은10월8일이다. [공식 저장소](https://github.com/Liuziyu77/Valen)와 [0.8B 카드](https://huggingface.co/Valen-Team/Valen-0.8B)는 개발사 결정 학습을 밝힌다. 우리 여행 자료는 추가 학습하지 않았다.0.8B는 FP32 원본 저장·backbone BF16 계산·head FP32·shared_state를 유지하며 선택지별 head 확률을 쓴다. 말로 한 확신도나 다음 토큰 확률과 같다고 하지 않는다. 정답을 입력에 넣지 않고 문맥·질문·모든 일정 항목·NONE 선택지를 보존하는 계약을 작성한다.

[North 공식 카드](https://huggingface.co/CohereLabs/North-Micro-Vision-Instruct)는8월 모델이며 새10월 출시로 쓰지 않는다. [Kolibri 공식 발표](https://aleph-alpha.com/en/blog/kolibri-has-landed-a-sovereign-open-weight-model/)의 발표일10월5일과 배포일10월3일을 구분한다. [Perplexity 공식 카드](https://huggingface.co/perplexity-ai/pplx-embed-v2-late-0.6b)는10월7일 모델로, 현재1024차원 단일 벡터 검색과 색인 계약이 달라 별도 시험이 필요하다. 원본 시험 완료 전 상위권·추가 학습·제품 채택을 확정하지 않았다.

revision·파일별 SHA·정확한 역할·개발사/우리 학습 여부와 준비 상태의 정본은 [후보 목록](../../../../program/research/daily_rag_slm/model_release_watchlist.json)이다. [공식 원본 메타데이터](../../../../program/scripts/plan_qa_bench/results/release_watch_20261009_v1/summary.json) · [신규 검색 모델 원본](../../../../program/scripts/plan_qa_bench/results/release_watch_20261009_extra_v1/summary.json).

## 완료된 계산과 다음 유효 작업

GPU 담당 에이전트가 FINCH 첫 시드 남은8평가18,130/18,130·SHA32/32를 회수했다. 기존 D3 두 판720을 합치면18,850/18,850 완료다. 두 양자화 모두 E 사전 기준2/4이고 정상 요청 회귀가 있어 승격하지 않는다. 복합 요청을 여러 항목으로 답하는 누락 역할6개·5,010문항을 기존 GPU 서버 A worker에 등록했다. 과거 D/E나 새 보류 자료와 합치지 않는다. [등록 원본](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/multi_items_registration_daily0957_20261009.json) · [FINCH 회수 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_finch_completed_daily0957_20261009/archive_verification.json). 최신 실행 수는 [GPU 상태](../../../../program/research/daily_rag_slm/gpu_backlog_2026-10-09.json)에서 실제 관측 시각과 함께 본다.

Oracle ARM의 기존 합친 학습판 Q8 D3가10:06 KST에 완료됐다. 정상106/120=88.33%, 요청 없음 오지목31/240=12.92%, 실패·미완료0/360이다. 답안·로그·실행 조건 SHA4/4와 문항 메타데이터360/360을 대조했다. 정확한 학습 판은 레시피 미대조 상태다.1회 순차 측정의 지연 중앙값110.71초·p95 124.32초는 다른 양자화와 같은 엔진의 속도 우열을 증명하지 않는다.

10:09:54 KST에 서비스·잠금·worker를 유지한 채 캐시 대조 첫 작업0/60을 관측했다. 최근300.05초 실제 시험 CPU는 두 코어 전체 대비58.91%, 기계 전체59.29%, steal0.13%, 작업 메모리약9.00GiB, 남은 공간약50.66GiB다. 작업 전환 준비 구간이 포함됐으며24시간 유지 증거가 아니다. 남은 초기 작업11개와 성공판 soak가 이어진다. [ARM 회수 검증](../../../../program/scripts/plan_qa_bench/results/daily_20261009_arm_v1/archive_verification.json) · [실제 자원 원문](../../../../program/scripts/plan_qa_bench/results/daily_20261009_arm_v1/observation.json) · [문항 재계수](../../../../program/scripts/plan_qa_bench/results/daily_20261009_arm_v1/parent_counts_verified.json).

다음은 새 원본 결정 모델 연결검사→고정 전체 비교 회수, 기존 두 시드 FINCH/cosine 비교, ARM 캐시ABBA 네 작업, E 사람 검수와 독립 보류 자료 준비다. E 사람 검수0/158·별도720자료 미작성은 이전 감사의 미완료 사실이며 코드 검사를 사람 검수로 바꾸지 않는다. 연구 구현, 개발 기준 통과, 독립 검증, 제품 채택, 실제 배포를 각각 구분한다.

```mermaid
flowchart LR
  A[논문·새 모델 확인] --> B[별도 구현·원본 시험]
  B --> C{{정상 요청·오지목 기준}}
  C -->|이번 검색 기준 미달| D[실패 보관·제품 유지]
  C -->|통과한 후보| E[사람 검수·독립 검증]
  E --> F[회귀 통과 후 적용]
```

수정 직전 백업은 [이번 작업 백업 목록](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/document_backups.json)에 연결한다. 과거 날짜 근거는 보존한다.
"""
    save(ROOT / REPORT, report)
    day = read(DAY / "2026-10-09.json")
    day['research'].update(daily_paper_survey_completed=True, method_review_papers=3, recent_newly_reviewed_papers=2, background_papers=1, official_revisions_checked_this_daily_run=6)
    day['review']['retrieval_candidate_review_completed'] = True
    day['implementation'].update(retrieval_candidate_code_completed=True, retrieval_logic_tests=dict(passed=7,total=7))
    day['measurement'].update(retrieval_development_completed=True,retrieval_decisions_complete=1700,retrieval_decisions_expected=1700,retrieval_unique_questions=340,retrieval_errors=0,retrieval_adopted=False,retrieval_independent_validation_completed=False,ARM_Q8_D3_completed=360)
    day.update(updated_at_kst=NOW.isoformat(),scope="Daily selected paper and release survey, frozen retrieval experiment and completed GPU/ARM collection; independent verification pending",
               daily_sources="program/research/daily_rag_slm/2026-10-09_sources_and_review_v1.json",daily_measurement="program/scripts/rag_gate/results/daily_20261009_selective_v1/summary.json")
    day['reports'].append(REPORT)
    day['resume'] = [s for s in day['resume'] if "daily paper survey separately" not in s] + ["Daily selected survey and frozen experiment complete: do not duplicate today's1700decisions or tune on same sets; next new independent evidence labels", "Valen0.8B pinned original contract/preflight; read latest registration/weight proof before any launch, no duplicate worker", "Completed FINCH full suites and ARMQ8 must not be repeated; collect queued multi-item role and cacheABBA separately"]
    save_json(DAY / "2026-10-09.json", day)
    md = (DAY / "2026-10-09.md").read_text(encoding='utf-8')
    md = md.replace("独立", "독립")
    md = md.replace("독립 보류 검증과 오늘 오전10시 최신 논문 조사는 아직 완료되지 않았다.", "오늘 선정 논문 조사·검색 구현·고정 개발 실측은 완료했으나 개선 기준은 실패했고 독립 보류 검증은 아직 완료되지 않았다.")
    md += f"\n## 오전10시 일일 연구와 신규 완료 회수\n\n[선정 논문·검색 실측·신모델 준비·ARM 회수](../../../{REPORT}) — 조사3/3·로직7/7·결정1700/1700 완료, 검색 개선 채택0/4. [사전 조건](2026-10-09_retrieval_prereg_v1.json) · [후보별 비용·위험·재개](2026-10-09_sources_and_review_v1.json). 초기 절의 일일 조사 대기 표시는 당시 상태이며 현재 결과와 구분한다. 새 원본 모델 전체 비교와 독립 보류 검증은 대기다.\n"
    save(DAY / "2026-10-09.md", md)
    idx = (DAY / "index.md").read_text(encoding='utf-8').replace("Saluki 개발 시험 완료·채택 기준 실패·GPU 보충·ARM 회수; 독립 검증과 일일 논문 조사는 대기", "일일 논문·신모델 검토·검색 실측 기준 실패·GPU 보충·ARM 회수; 독립 검증 대기")
    save(DAY / "index.md", idx)
    overview_path = ROOT / "wiki/research/rag-slm-improvements.md"
    overview = overview_path.read_text(encoding='utf-8')
    start = overview.index('`[실측 2026-10-08 작업 트리]`')
    end = overview.index('\n\n연구 결과를 제품',start)
    overview = overview[:start] + f"`[실측 2026-10-09 작업 트리]` 학습률 조절의 첫 시드 비교와 검색 다양성·합산 후보를 완료했으나 정상 요청 회귀 또는 검색 기준 미달이 있어 제품에 승격하지 않았다. 새 원본 모델 시험·반복 시드·독립 보류 자료는 따로 이어간다. 상세 근거는 [일일 연구·실측 리포트](../../{REPORT})와 [현재 날짜 기록](../../program/research/daily_rag_slm/2026-10-09.json)에 있다." + overview[end:]
    save(overview_path,overview)
    log = ROOT / "final_project_cs/wiki/log.md"
    text = log.read_text(encoding='utf-8')
    text += f"\n- 2026-10-09: 선정 논문 검토를 여행 검색 구현·실측으로 연결했으나 합격 기준 미달로 제품 유지; 새 원본 후보 준비와 ARM 완료 회수. [근거](records/reports/{Path(REPORT).name}).\n"
    save(log,text)
    save_json(OUT / 'document_backups.json', dict(recorded_at_kst=NOW.isoformat(),files=BACKUPS))
    print(json.dumps(dict(papers=3,release_revisions=6,decisions=1700,adopted=False,report=REPORT,backups=len(BACKUPS)),ensure_ascii=False))


if __name__ == '__main__':
    main()
