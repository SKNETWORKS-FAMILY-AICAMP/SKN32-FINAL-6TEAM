# 「질의 분류 · 라우팅 모델 평가 시험 — 중요도 순위」 표를 한 장짜리 HTML 로 만든다(2026-10-07 사용자 요청: 하는 이유 · 방법 · 지표 · 근거 · 우리 근거 · 우선순위 · 순위, Codex 와 사실 대조 반영).
#  내용은 DATA 한 곳에만 둔다. 사실 대조 결과(Codex 솔 · Claude)는 CHECK 에 건수만 싣는다.
# 사용: python build_eval_table_html.py <출력.html>
import html
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUT = sys.argv[1]
L = {  # 근거 링크
    'clinc': ('CLINC150, EMNLP 2019', 'https://arxiv.org/abs/1909.02027'),
    'dror': ('Dror 외, ACL 2018', 'https://aclanthology.org/P18-1128/'),
    'rv': ('Rodrigues & Vas 2026 ★', 'https://arxiv.org/pdf/2608.20371'),
    'tau': ('τ-bench, 2024', 'https://arxiv.org/abs/2406.12045'),
    'check': ('CheckList, ACL 2020', 'https://arxiv.org/abs/2005.04118'),
    'cards': ('Model Cards, FAT* 2019', 'https://arxiv.org/abs/1810.03993'),
    'guo': ('Guo 외, ICML 2017', 'https://arxiv.org/abs/1706.04599'),
    'geif': ('Geifman & El-Yaniv, 2017', 'https://arxiv.org/abs/1705.08500'),
    'hend': ('Hendrycks & Gimpel, ICLR 2017', 'https://arxiv.org/abs/1610.02136'),
    'jac': ('Jacovi 외, 2023', 'https://arxiv.org/abs/2305.10160'),
    'rb': ('RouterBench, 2024', 'https://arxiv.org/abs/2403.12031'),
    'rl': ('RouteLLM, 2024', 'https://arxiv.org/abs/2406.18665'),
    'massive': ('MASSIVE, 2022', 'https://arxiv.org/abs/2204.08582'),
    'klue': ('KLUE, 2021', 'https://arxiv.org/abs/2105.09680'),
    'lora': ('LoRA Learns Less and Forgets Less, TMLR 2024', 'https://arxiv.org/abs/2405.09673'),
    'helm': ('HELM, TMLR 2023', 'https://arxiv.org/abs/2211.09110'),
    'rab': ('Rabanser 외, 2026', 'https://arxiv.org/abs/2602.16666'),
    'conf': ('Angelopoulos & Bates, 2021', 'https://arxiv.org/abs/2107.07511'),
    'mlts': ('ML Test Score, IEEE Big Data 2017', 'https://research.google/pubs/pub46555/'),
}
# (우선순위, 시험, 하는 이유, 방법 · 지표, 근거 링크 키들 또는 문구, 우리 프로젝트 근거, 상태)
DATA = [
    ('필수', '범위 밖 · 오지목', '무관한 말에 일정 항목을 지어내면 잘못 안내한다', '잡담·관광지·범위 밖 질의를 섞어 시험<br>오지목률(정답 없는 질문에서 항목을 짚은 비율) · 범위 밖 재현율', ['clinc'],
     '「근거 없으면 확정 금지」가 서비스 최우선 규칙. D 시험 오지목이 모델(0.9~17.4%)과 시드(4.3~16.0%)를 갈랐다', '했음'),
    ('필수', '통계적 유의성', '시험이 작고 학습마다 값이 흔들려 점 하나로 못 가린다', '같은 문장 짝지은 비교 + 시드 여러 개<br>부트스트랩 95% 구간 · McNemar · 시드 평균과 범위', ['dror'],
     '시드만 바꿔 769문제 748~760, D 시험 85.6~93.7% — 점 하나 비교는 틀린 결론을 낸다', '했음'),
    ('필수', '정확도 (클래스별)', '평균이 소수 클래스 실패를 가린다', '정확도 · 거시/가중 F1 · 클래스별 정밀도/재현율 · 혼동행렬', ['rv'],
     '약한 클래스를 이 지표로 찾았다(긴급도 medium 재현율 0.76, 대상 flight 0.78)', '했음'),
    ('필수', '운영 성능', '배포할 수 있는 속도 · 비용인지 본다', '실제 실행기에서 질문당 시간 · 동시 요청 · 메모리<br>p50/p95 지연 · 시간당 건수', ['rv'],
     '서버 A GPU: 다음 질문 0.24초, 동시 4에서 시간당 15,159건. CPU · 오라클 ARM 시험 진행 중', '했음'),
    ('필수', '일관성 (pass^k)', '같은 일을 시켰을 때 매번 같아야 믿는다', '같은 사례를 k번 반복<br>pass^k (k번 모두 성공)', ['tau'],
     '결정 단위 pass^3 91.3%. DB 최종 상태 비교는 Team 이 제안만 하므로 「제안 일치」로 바꿔 쓴다', '했음'),
    ('필수', '견고성 (말투 · 오타)', '실제 말은 오타 · 구어체 · 부정문이다', '변형 질의를 능력 × 유형 표로 시험<br>변형 전후 정확도 하락', ['check'],
     '질문 유형 10종이 같은 구조(이름 없는 설명 75문제 중 63). 말투 변형 묶음 시험은 아직 없다', '일부'),
    ('필수', '양자화 손실', '작게 줄이면 정확도가 떨어질 수 있다', '같은 문제를 Q8 · Q4 로 풀어 비교<br>정답 차이 · McNemar', '직접 측정(논문 불필요)',
     'Q8 756/769, Q4_K_M 756/769 (3 : 3) — 손실 없음', '했음'),
    ('필수', '의도 · 한계 문서화', '점수 밖에 의도한 사용과 한계를 밝힌다', '모델 카드 수준: 의도한 사용 · 유형별 성능 · 평가 절차', ['cards'],
     '학업 보고서에 한계와 출제자 편향을 적는 것으로 충족', '했음'),
    ('보통', '보정 (확신도)', '확신도 임계값으로 되묻기를 하려면 확신도가 맞아야 한다', '확신 0.9 인 답의 실제 정확도<br>ECE · 신뢰도 곡선', ['guo'],
     '임계값 기능을 켤 때 필수. 분류기 ECE 0.014~0.042, 서비스 실행기에서는 미측정', '일부'),
    ('보통', '기권 · 확신도', '맞출 만큼만 답하고 나머지는 되묻는다', '위험-커버리지 곡선 · 확신도 AUROC', ['geif', 'hend'],
     '제품에 사람 운영자 큐가 없어(D-CS-014) 기권 = 되묻기 · 「모른다」 안내. 곡선은 아직', '안 함'),
    ('보통', '학습-시험 겹침 검사', '시험 문장이 학습에 섞이면 점수가 부푼다', '정확 일치 · 글자 3-gram 자카드 검사', ['jac'],
     '잡담 보강 · D2 · D3 는 자카드 확인(최대 0.22~0.4). 일정 짚기 원본 학습-시험 검사는 문서가 없다', '일부'),
    ('보통', '라우팅 비교 (단계 처리)', '모델 조합이 비용 대비 이득인지 본다', '오라클 라우터와 비교 · 비용-성능 곡선', ['rb', 'rl'],
     '규칙 → ML → 분류 → LLM 단계 처리가 같은 구조(평가 방식만 차용)', '했음'),
    ('선택', '한국어 공개 세트', '합성 세트 밖의 독립 기준점', '의도 정확도 · 슬롯 F1', ['massive', 'klue'],
     '가상비서 · 뉴스 도메인이라 절대 점수 비교는 의미가 작다', '안 함'),
    ('선택', '일반 능력 잊음', '가르치면 다른 능력이 줄 수 있다', '일반 벤치마크 전후 비교', ['lora'],
     '짚기 전용 모델이고 다른 일은 12B 가 한다', '안 함'),
    ('선택', '종합 평가 축 (HELM)', '한 축만 올리다 다른 축이 무너지는 것을 막는다', '정확도 · 보정 · 견고성 · 효율 (7축 중 4축)', ['helm'],
     '4축은 위 항목에서 이미 측정 — 개념만 차용', '일부'),
    ('선택', '신뢰성 분해', '정확도가 올라도 신뢰성은 안 오를 수 있다', '일관성 · 견고성 · 예측가능성 · 안전 (12지표)', ['rab'],
     '일관성 = pass^3, 견고성 = 유형별 — 개념만 차용', '일부'),
    ('없어도 됨', '컨포멀 예측', '분포 가정 없이 오류율을 보장한다', '예측 집합 커버리지 보장', ['conf'],
     '학업 단계에 과하다', '안 함'),
    ('없어도 됨', '운영 점검표 28개 전체', '데이터 · 모델 · 인프라 · 감시를 점검한다', '28개 시험 점검', ['mlts'],
     '출시 후 감시 · 카나리 중심 — 지금은 「의도 · 한계 문서화」로 충분', '안 함'),
    ('없어도 됨', '공정성 · 독성', '집단 편향 · 유해 발화를 본다', 'HELM 의 나머지 축', ['helm'],
     '일정 짚기 모델의 일이 아니다', '안 함'),
]
CHECK = json.load(open(os.path.join(os.path.dirname(OUT), '_eval_table_check.json'), encoding='utf-8')) if os.path.exists(os.path.join(os.path.dirname(OUT), '_eval_table_check.json')) else None
TIER_CLASS = {'필수': 't1', '보통': 't2', '선택': 't3', '없어도 됨': 't4'}
ST_CLASS = {'했음': 's1', '일부': 's2', '안 함': 's3'}


def cell_links(x):
    if isinstance(x, str):
        return html.escape(x)
    return '<br>'.join(f'<a href="{L[k][1]}" target="_blank" rel="noopener">{html.escape(L[k][0])}</a>' for k in x)


rows, last = [], None
n = 0
cnt = {}
for tier, name, why, how, src, basis, st in DATA:
    cnt[tier] = cnt.get(tier, 0) + 1
for tier, name, why, how, src, basis, st in DATA:
    n += 1
    if tier != last:
        rows.append(f'<tr class="grp {TIER_CLASS[tier]}"><td colspan="8">{tier} <span>{cnt[tier]}</span></td></tr>')
        last = tier
    rows.append(f'<tr class="{TIER_CLASS[tier]}"><td class="no">{n}</td><td><span class="chip {TIER_CLASS[tier]}">{tier}</span></td><td class="nm">{html.escape(name)}</td><td>{html.escape(why)}</td><td>{how}</td><td class="src">{cell_links(src)}</td><td>{html.escape(basis)}</td><td><span class="st {ST_CLASS[st]}">{st}</span></td></tr>')
check_txt = ''
if CHECK:
    check_txt = f'<p class="foot">사실 대조: Codex 솔이 논문 · 수치 {CHECK["total"]}건을 대조 — 맞음 {CHECK["ok"]} · 표현 정정 {CHECK["fixed"]}(모두 반영)</p>'
page = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>평가 시험 중요도 순위</title>
<style>
:root{{--bg:#f7f6f2;--fg:#1f2328;--mut:#5f6670;--card:#fff;--bd:#dedbd2;--t1:#1d5fa8;--t1b:#e6f0fa;--t2:#2f7d4f;--t2b:#e7f4ec;--t3:#6b6b66;--t3b:#efeeea;--t4:#9a9a94;--t4b:#f5f4f1;--s1:#2f7d4f;--s2:#a8650d;--s3:#8a8a84}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181b;--fg:#e8e8e6;--mut:#a3a8ae;--card:#1e2125;--bd:#33373d;--t1:#7db4ee;--t1b:#1c2b3b;--t2:#7fcb9d;--t2b:#1b2e24;--t3:#b5b5ae;--t3b:#26282b;--t4:#8c8c86;--t4b:#212326;--s1:#7fcb9d;--s2:#e0a35a;--s3:#9a9a94}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;padding:24px 16px 40px}}
.wrap{{max-width:1280px;margin:0 auto}}h1{{font-size:20px;margin:0 0 4px;font-weight:600}}.sub{{color:var(--mut);margin:0 0 16px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px 16px;margin:0 0 14px;color:var(--mut);font-size:12.5px}}
.scroll{{overflow-x:auto;border:1px solid var(--bd);border-radius:10px;background:var(--card)}}
table{{border-collapse:collapse;width:100%;min-width:1180px;table-layout:fixed;word-break:keep-all;overflow-wrap:anywhere}}th{{position:sticky;top:0;background:var(--card);text-align:left;font-weight:600;font-size:12.5px;color:var(--mut);padding:10px 12px;border-bottom:1px solid var(--bd);white-space:nowrap}}
td{{padding:10px 12px;border-bottom:1px solid var(--bd);vertical-align:top}}tr:last-child td{{border-bottom:0}}
td.no{{color:var(--mut);text-align:center;width:34px;font-variant-numeric:tabular-nums}}td.nm{{font-weight:600}}td.src a{{color:var(--t1);text-decoration:none}}td.src a:hover{{text-decoration:underline}}
tr.grp td{{font-weight:600;padding:8px 12px;font-size:13px;border-bottom:1px solid var(--bd)}}tr.grp span{{font-weight:400;opacity:.7;margin-left:4px}}
tr.grp.t1 td{{background:var(--t1b);color:var(--t1)}}tr.grp.t2 td{{background:var(--t2b);color:var(--t2)}}tr.grp.t3 td{{background:var(--t3b);color:var(--t3)}}tr.grp.t4 td{{background:var(--t4b);color:var(--t4)}}
tr.t4:not(.grp) td{{color:var(--mut)}}
.chip{{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}}.chip.t1{{background:var(--t1b);color:var(--t1)}}.chip.t2{{background:var(--t2b);color:var(--t2)}}.chip.t3{{background:var(--t3b);color:var(--t3)}}.chip.t4{{background:var(--t4b);color:var(--t4)}}
.st{{font-weight:600;white-space:nowrap}}.st.s1{{color:var(--s1)}}.st.s2{{color:var(--s2)}}.st.s3{{color:var(--s3)}}
.foot{{color:var(--mut);font-size:12.5px;margin:12px 0 0}}
</style></head><body><div class="wrap">
<h1>질의 분류 · 라우팅 모델 평가 시험 — 중요도 순위</h1>
<p class="sub">논문 · 실무에서 하는 시험을 우리 프로젝트(여행 일정 질문 → 알맞은 에이전트)의 중요도 순으로 정리 · 2026-10-07</p>
<div class="legend"><span><b>필수</b> 안 하면 설계 규칙을 못 지킴</span><span><b>보통</b> 쓰는 기능이 있어 같이 재야 함</span><span><b>선택</b> 있으면 좋음</span><span><b>없어도 됨</b> 학업 단계에서는 과함</span><span>★ 원문을 끝까지 읽은 논문 · 나머지는 초록 페이지 확인</span></div>
<div class="scroll"><table><colgroup><col style="width:44px"><col style="width:76px"><col style="width:132px"><col style="width:17%"><col style="width:19%"><col style="width:15%"><col style="width:25%"><col style="width:64px"></colgroup><thead><tr><th>순위</th><th>우선순위</th><th>시험</th><th>하는 이유</th><th>방법 · 지표</th><th>근거(논문)</th><th>우리 프로젝트 근거</th><th>우리 상태</th></tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table></div>
{check_txt}
<p class="foot">수치 근거: 마스터 문서 §92 · 평가 베이스라인 리포트 · D 시험 표. 상업 이용 약관 · 규제는 별도 문서(비상업 학업 프로젝트라 해당 없음).</p>
</div></body></html>'''
open(OUT, 'w', encoding='utf-8').write(page)
print('저장', OUT, len(DATA), '행')
