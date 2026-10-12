"""[모델링 및 평가] 벡터DB/GraphDB 구축 결과서 빌더 (2026-10-06).

재료: ../_재료/코덱스_초안.json(코덱스 초안) + ../_재료/로컬DB_측정_2026-10-06.json(오늘 로컬 개발 DB 읽기 전용 측정).
Claude 가 초안을 검토해 고친 곳은 이 파일의 patch_* 함수에 모두 있다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
W5 = HERE.parents[1]
sys.path.insert(0, str(W5 / "_공용"))
import w5_docx as W  # noqa: E402
import term_pass as TP  # noqa: E402

# 그림 글자에도 같은 용어 정비를 건다(2026-10-06) — 본문만 바꾸면 그림 라벨과 말이 어긋난다
import matplotlib.text as _mt  # noqa: E402
_orig_set_text = _mt.Text.set_text


def _set_text(self, s):
    if isinstance(s, str) and s:
        s = TP.run_text(s)
    return _orig_set_text(self, s)


_mt.Text.set_text = _set_text


MAT = HERE.parent / "_재료"
FIG = HERE.parent / "그림"
FIG.mkdir(exist_ok=True)
TEMPLATE = W5.parent / "[모델링 및 평가] 벡터DB_GraphDB 구축 결과서_양식.docx"
OUT = HERE.parent / "[모델링 및 평가] 벡터DB_GraphDB 구축 결과서_6팀.docx"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
GREEN, GOLD, GREY = "#2D5F48", "#C8913A", "#9FB0A6"

D = json.loads((MAT / "코덱스_초안.json").read_text(encoding="utf-8"))
M = json.loads((MAT / "로컬DB_측정_2026-10-06.json").read_text(encoding="utf-8"))
S, G, N = M["search_ms"], M["graph_neighbors"], M["graph_subgraph"]


# ---------- 그림 ----------
def dot(src: Path, png: Path):
    exe = Path(r"C:\Program Files\Graphviz\bin\dot.exe")
    subprocess.run([str(exe) if exe.exists() else "dot", "-Tpng", str(src), "-o", str(png)], check=True)


def fig_policy():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), sharey=True)
    panels = [("낙관적 세트 100문제 (10-01)", 100, [66, 82, 86], [82, 93, 96]),
              ("독립 세트 48문제 (10-02)", 48, [19, 29, 32], [25, 35, 38])]
    for ax, (title, den, a, b) in zip(axes, panels):
        x = range(3)
        va = [v / den * 100 for v in a]
        vb = [v / den * 100 for v in b]
        ax.bar([i - 0.19 for i in x], va, 0.36, color=GREY, label="지금 운영(본문 색인)")
        ax.bar([i + 0.19 for i in x], vb, 0.36, color=GREEN, label="실험 색인 E(미반영)")
        for i in x:
            ax.text(i - 0.19, va[i] + 1.5, f"{a[i]}/{den}", ha="center", fontsize=7.5)
            ax.text(i + 0.19, vb[i] + 1.5, f"{b[i]}/{den}", ha="center", fontsize=7.5)
        ax.set_xticks(list(x), ["상위 1", "상위 3", "상위 5"])
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 108)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("정답 근거가 후보에 든 비율(%)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=8, loc="lower center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG / "정책검색_재현율.png", dpi=200)
    plt.close(fig)


def fig_itin():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    names = ["V1 임베딩 앞단", "V3 임베딩 + 같은 장소\n관계 문지기", "V13 이웃 정보를\n넣은 임베딩"]
    ok, wrong, calls = [307, 313, 304], [16, 10, 17], [136, 151, 150]
    cols = [GREY, GREEN, GOLD]
    bars = ax.barh(names[::-1], [v / 336 * 100 for v in ok][::-1], color=cols[::-1], height=0.55)
    for b, v, w, c in zip(bars, ok[::-1], wrong[::-1], calls[::-1]):
        ax.text(b.get_width() + 0.15, b.get_y() + b.get_height() / 2,
                f"{v}/336 = {v / 336 * 100:.1f}%   엉뚱한 답 {w} · 모델 호출 {c}", va="center", fontsize=8.5)
    ax.set_xlim(85, 100)
    ax.set_xlabel("정답률(%) · 가로축은 85%부터")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "일정판정_비교.png", dpi=200)
    plt.close(fig)


def fig_road():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    names = ["직선 거리 x 1.4", "도로 그래프 v1", "도로 그래프 v2"]
    mean, med, in10 = [39, 25, 11], [35, 9, 6], [4, 10, 13]
    x = range(3)
    ax.bar([i - 0.19 for i in x], mean, 0.36, color=GREY, label="평균 오차")
    ax.bar([i + 0.19 for i in x], med, 0.36, color=GREEN, label="중앙 오차")
    for i in x:
        ax.text(i - 0.19, mean[i] + 0.8, f"{mean[i]}%", ha="center", fontsize=8)
        ax.text(i + 0.19, med[i] + 0.8, f"{med[i]}%", ha="center", fontsize=8)
        ax.text(i, -7.5, f"오차 10% 안: {in10[i]}/16쌍", ha="center", fontsize=8, color="#444")
    ax.set_xticks(list(x), names)
    ax.set_ylim(-10, 46)
    ax.axhline(0, color="#888", lw=0.6)
    ax.set_ylabel("기준 거리 대비 오차(%)")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "도로거리_오차.png", dpi=200)
    plt.close(fig)


def fig_latency():
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    rows = [("벡터 검색 상위 3개\n(390회)", S["p50"], S["p95"], GREEN),
            ("관계 조회: 문서 이웃 2단계\n(20회)", G["ms_p50"], G["ms_p95"], GOLD),
            ("관계 조회: 사건 주변 2단계\n(20회)", N["ms_p50"], N["ms_p95"], GOLD)]
    for i, (n, p50, p95, c) in enumerate(rows[::-1]):
        ax.barh(i, p95, color=c, alpha=0.35, height=0.55)
        ax.barh(i, p50, color=c, height=0.55)
        ax.text(p95 + 0.3, i, f"중앙 {p50:.1f}ms · 95% {p95:.1f}ms", va="center", fontsize=8.5)
    ax.set_yticks(range(3), [r[0] for r in rows[::-1]], fontsize=8.5)
    ax.set_xlim(0, 30)
    ax.set_xlabel("1회 걸린 시간(ms) · 진한 막대 = 중앙값, 옅은 막대 = 95번째 백분위")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "DB_응답시간_2026-10-06.png", dpi=200)
    plt.close(fig)


# ---------- 초안 고치기 ----------
def drop_dup_heading(blocks):
    return [b for b in blocks if not (b[0] == "h" and re.match(r"^\d\.\s", b[1]))]


def find(blocks, kind, start):
    for i, b in enumerate(blocks):
        if b[0] == kind and str(b[1]).startswith(start):
            return i
    raise KeyError(start)


USE_TABLE = ["t", ["할 일", "알맞은 방식", "근거(분자/분모 · 날짜)", "지금 상태"], [
    ["표현이 달라도 같은 정책 근거 찾기", "벡터 검색(pgvector)",
     "독립 질문 48개 중 상위 5개 안에 정답 근거: 운영 32 · 색인 E 38 (10-02)", "운영 중(본문 색인)"],
    ["일정의 몇 번째 · 앞뒤 · 같은 장소", "관계 구조(그래프)",
     "순서 · 위치 질문 80개에서 임베딩만으로 상위 5개 안에 정답 13~19개(10-06). 별도 42문제에서 규칙 + 관계 조회 42/42(09-30, 질문 · 규칙 작성자 같음). 직접 비교 실험은 아니다", "연구 단계"],
    ["표현이 다양한 일정 항목 찾기", "임베딩 앞단 + 관계 문지기",
     "336문제: 임베딩만 307 · 관계 문지기 추가 313 (10-03, p=0.031)", "연구 단계"],
    ["이동 거리 · 경로", "도로 그래프(메모리)", "도보 16쌍 평균 오차: 직선 39% · 도로 그래프 v2 11% (10-04)",
     "공용 이동 판정 도구에서 사용"],
    ["사건 · 실행 · 근거 이력 추적", "SQL 관계 조회(재귀 질의)",
     f"사건 주변 2단계 조회 중앙 {N['ms_p50']:.1f}ms (10-06 로컬, 20회) · 정답 기준 없음", "관리 · 점검용"],
    ["별도 그래프DB 제품(Neo4j 등)", "쓰지 않음",
     f"정책 130조각 · 사건 {M['customer_cases']}건을 PostgreSQL 로 다룬다. 동시 요청 · 깊은 관계 탐색의 처리 능력은 재지 않았다", "채택 관문을 넘을 때 검토"],
], [24, 18, 40, 18]]


GLOSS = [
    ("S2 규칙 자리표 + Jev 기준항목 + 코드 관계 조회", "S2 규칙 자리표 + Jev API(유료) 기준항목 + 코드 관계 조회"),
    ("Jev 직접 항목 판정", "Jev API(유료) 직접 항목 판정"),
    ("실제 여행 코퍼스는 bge-m3의 1024차원 벡터로 적재되어 있다.",
     "여행 정책 문서 모음(코퍼스)은 bge-m3 모델로 문장 뜻을 숫자 1024개 목록으로 바꿔(임베딩) 저장했다."),
    ("정책 코퍼스는 판단 기준을 담는다.", "정책 문서 모음(코퍼스)은 판단 기준을 담는다."),
    ("Markdown의 ## 절 하나를 청크 하나로 분리", "문서를 검색용 조각(청크)으로 나눈다. Markdown의 ## 소절 하나가 조각 하나"),
    ("SqlGraphAdapter가 기존 관계형 표를 JOIN하고 WITH RECURSIVE로 순회한다.",
     "SqlGraphAdapter는 기존 표의 행과 연결 정보를 조회할 때 항목과 관계로 읽는다(관계 투영). 관련 표를 이은 뒤(JOIN) 정해진 깊이까지 관계를 따라간다(WITH RECURSIVE)."),
]


def gloss(x):
    if isinstance(x, str):
        for a, c in GLOSS:
            x = x.replace(a, c)
        return x
    if isinstance(x, list):
        return [gloss(v) for v in x]
    return x


def patch_s1(b):
    b = drop_dup_heading(b)
    # 정하지 않은 방안(선호 RAG)은 빼고 두 에이전트 + 공용 이동 도구 문장만 남긴다
    i = find(b, "p", "요식과 액티비티가")
    b[i] = ["p", "에이전트는 요식과 액티비티 둘이다. 이동은 두 에이전트가 함께 부르는 공용 판정 도구다. "
                 "요식 · 활동 표에는 벡터 열이 없다. 장소 추천을 벡터 검색으로 한다고 적지 않는다."]
    i = find(b, "fig", "fig_roles")
    b[i] = ["img", str(FIG / "역할_구성도.png"),
            "그림 1. 저장소와 관계 구조의 역할. 실선은 지금 쓰는 길, 점선은 실험 단계이거나 여행 요청 경로 밖인 길이다.", 12.5]
    b[i + 1:i + 1] = [
        ["h", "1.3 벡터DB와 그래프는 각각 어디에 쓰는 것이 좋은가"],
        ["p", "결론: 문장 뜻으로 찾는 일은 벡터 검색이, 순서 · 연결을 따지는 일은 관계 구조가 낫다. "
              "지금은 둘 다 PostgreSQL 하나와 프로세스 메모리로 다루고, 별도 그래프DB 제품은 들이지 않았다. 별도 제품은 정확도 · 비용 · 응답 시간 관문을 넘을 때 검토한다."],
        USE_TABLE,
        ["note", "표의 근거는 3절에 원 수치와 출처가 있다. 서로 다른 과제의 수치라 한 줄로 순위를 매기지 않는다."],
    ]
    return b


def patch_s2(b):
    b = drop_dup_heading(b)
    t = b[find(b, "t", ["항목"].__class__())] if False else None  # noqa: F841 (자리 표시)
    for blk in b:
        if blk[0] == "t" and blk[1][0] == "항목":
            for row in blk[2]:
                if row[0] == "색인":
                    row[2] = ("1024차원 열은 IS NOT NULL 부분 색인이다. 2026-10-06 로컬 개발 DB 실행계획을 보면 "
                              "130조각 규모에서는 색인 대신 전부 훑는 순차 탐색을 고른다(1회 1.4ms). 자료가 커질 때를 위한 준비다.")
                if row[0] == "청크 길이":
                    row[0] = "조각 길이"
                if row[0] == "청킹":
                    row[0] = "조각 나누기"
    return b


def patch_s3(b):
    b = drop_dup_heading(b)
    for blk in b:
        if blk[0] == "t" and blk[1][0] == "평가 항목":
            rows = []
            for row in blk[2]:
                if row[0].startswith("MCP"):
                    continue  # 이 결과서 범위 밖, 잰 기록도 없다
                if row[0] == "응답 속도":
                    row = ["DB 응답 시간", "1회 검색 · 관계 조회에 걸린 시간",
                           f"벡터 검색 SQL 중앙 {S['p50']:.2f}ms · p95 {S['p95']:.2f}ms ({S['n']}회) / 관계 어댑터 호출 중앙 "
                           f"{G['ms_p50']:.1f}~{N['ms_p50']:.1f}ms (각 20회)",
                           "2026-10-06 로컬 개발 DB 1대. 질문 임베딩, 연결 생성, 운영 검색의 사전 확인 · 본문 반환은 빠졌다. p95 = 잰 시간의 95%가 이 값 이하.",
                           "저장된 조각 벡터 130개를 질의로 3바퀴. 읽기 전용 트랜잭션"]
                if row[0] == "SQL 관계 탐색":
                    row = ["SQL 관계 탐색", "관계 조회가 실제로 이어지는가",
                           f"문서 이웃 2단계 {G['rows']}행(조각 {G['by_depth']['1']} · 다시 문서 {G['by_depth']['2']}) / "
                           f"사건 주변 2단계: 이벤트 4 · 실행 1 · 이슈 1 · 처리팀 1",
                           "정답표가 없어 정확도는 재지 못했다. 연결이 이어지는지만 확인했다.",
                           "2026-10-06 로컬 개발 DB에서 어댑터 실제 실행"]
                rows.append(row)
            blk[2] = rows
    i = find(b, "fig", "fig_policy_recall")
    b[i] = ["img", str(FIG / "정책검색_재현율.png"),
            "그림 2. 정책 검색: 정답 근거가 상위 후보에 든 비율. 낙관적 세트(질문 작성자가 답 문장을 봄)와 독립 세트를 나눠 그렸다."]
    i = find(b, "fig", "fig_itinerary_compare")
    b[i] = ["img", str(FIG / "일정판정_비교.png"),
            "그림 3. 일정 항목 판정 336문제(mix8 171 + mix9 165, 10-03). 여기서 그래프는 메모리 관계 구조이며 DB 제품 비교가 아니다."]
    i = find(b, "fig", "fig_road_error")
    b[i] = ["img", str(FIG / "도로거리_오차.png"),
            "그림 4. 도보 거리 16쌍(중복 2쌍 포함)을 같은 기준 거리 기록과 비교한 오차(10-04)."]
    # 오늘 잰 DB 응답 시간 소절
    j = find(b, "h", "3.2")
    b[j:j] = [
        ["h", "벡터 검색과 관계 조회의 DB 응답 시간 (2026-10-06 로컬 개발 DB)"],
        ["p", f"같은 DB에서 벡터 검색 SQL은 1회 중앙 {S['p50']:.2f}ms(p95 {S['p95']:.2f}ms), 관계 어댑터 호출은 중앙 {G['ms_p50']:.1f}ms와 {N['ms_p50']:.1f}ms 걸렸다. "
              "관계 조회는 여러 표에서 관계를 만들어 따라가는 일을 하지만, 시간 차이의 원인을 나눠 재지는 않았다. "
              "두 질의는 하는 일과 잰 범위가 달라 빠르기 순위로 읽지 않는다. 이번 로컬 측정의 중앙값은 모두 16ms 미만이었고, 실제 서비스의 전체 응답 시간은 재지 않았다."],
        ["img", str(FIG / "DB_응답시간_2026-10-06.png"),
         "그림 5. 1회 걸린 시간. 저장된 조각 벡터를 질의로 썼고 질문을 벡터로 바꾸는 시간은 빠졌다. 장비 1대 · 1회 측정 묶음."],
        ["note", f"PostgreSQL 16.14 · pgvector {M['pgvector']}. 측정 스크립트: w5/벡터DB_GraphDB_결과서/src/measure_local_db.py, "
                 "결과: _재료/로컬DB_측정_2026-10-06.json. 저장된 벡터로 검색했을 때 자기 조각이 1위인 결과는 130/130이었다. "
                 "이 실행은 순차 탐색을 써서 HNSW 색인의 정상 여부나 실제 질문의 검색 정확도를 검증한 것이 아니다."],
    ]
    # 3.2 문단: 내부 문서 번호 대신 동작을 쓴다
    i = find(b, "p", "결정 15의 원칙과")
    b[i] = ["p", "값을 끝내 못 얻을 때 서버를 끈다는 원칙 가운데 지금 코드에서 확인한 것은 세 가지다. "
                 "시작할 때 조립이 잘못되면 시작을 거부하고, 배치 작업은 실패로 끝내고, 요청 처리 중이면 치명 상태로 기록한다. "
                 "요청 처리 중에 서버 프로세스를 끄는 동작은 확인하지 못했다(코드 검색 범위: 결정 적용 경로 실측 기록과 해당 모듈)."]
    i = find(b, "note", "실제 정책 답 동작")
    b[i] = ["note", "출처: final_project_cs/app/domains/travel_ops/components/conversation/trip_replies.py(정책 답), "
                    "final_project_cs/wiki/records/reports/2026-09-21_0100_결정15_적용경로_실측.md(중단 경로)."]
    return b


def patch_s4(b):
    return drop_dup_heading(b)


def patch_s5(b):
    b = drop_dup_heading(b)
    i = find(b, "note", "2026-09-22 DoD-06T")
    b[i] = ["note", f"2026-09-22 적재 기록과 2026-10-06 {M['measured_at'][11:]} 로컬 개발 DB 재조회가 같다(아래 조회 결과). "
                    "x600 서버의 cs 프로젝트 DB는 이번에 조회하지 않았다."]
    i = find(b, "code", "기존 DB 조회")
    rows = "\n".join(f" {c['scope']:<20}| {c['docs']:>4} | {c['chunks']:>6} | {c['dim1536']:>7} | {c['dim1024']:>7}"
                     for c in M["corpus"])
    tot = [sum(c[k] for c in M["corpus"]) for k in ("docs", "chunks", "dim1536", "dim1024")]
    b[i] = ["code", f"적재 확인 조회 (2026-10-06 {M['measured_at'][11:]} 로컬 개발 DB, 읽기 전용)",
            "SELECT kd.scope, count(DISTINCT kd.document_id) docs, count(*) chunks,\n"
            "       count(kc.embedding) dim1536, count(kc.embedding_1024) dim1024\n"
            "  FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)\n"
            " GROUP BY kd.scope ORDER BY 1;\n\n"
            " scope               | docs | chunks | dim1536 | dim1024\n"
            "---------------------+------+--------+---------+---------\n"
            f"{rows}\n"
            f" (합계)              | {tot[0]:>4} | {tot[1]:>6} | {tot[2]:>7} | {tot[3]:>7}"]
    i = find(b, "note", "위 블록은 원문의")
    b[i] = ["note", "knowledge_chunks 표 전체가 여행 정책 130조각뿐이다(쇼핑몰 시절 자료는 지워졌다). 결과는 _재료/로컬DB_측정_2026-10-06.json."]
    for blk in b:
        if blk[0] == "t" and blk[1][0] == "구성":
            for row in blk[2]:
                if row[0].startswith("SqlGraphAdapter"):
                    row[1] = f"사건 {M['customer_cases']}건 등 기존 표를 질의 때 관계로 읽음(따로 적재한 노드 · 간선 없음)"
                    row[2] = "2026-10-06 로컬 개발 DB 실행"
    b = [x for x in b if not (x[0] == "p" and str(x[1]).startswith("선로 추정 요금"))]
    i = find(b, "p", "관계 조회의 구현 예시는")
    b[i] = ["p", "관계 조회를 오늘 로컬 개발 DB에서 실제로 돌렸다. 정책 문서 하나에서 2단계를 따라가면 조각 11개와 그 조각들이 속한 문서로 "
                 f"돌아오는 {G['rows']}행이 나왔다. 이벤트가 가장 많은 사건 하나의 주변 2단계는 이벤트 4 · 실행 요청 1 · 이슈 1 · 처리팀 1로 이어졌다."]
    # 캡처 자리: 오늘 실행 결과로 바꾼다
    k = find(b, "h", "화면 캡처 또는 실행 결과 자리")
    end = find(b, "h", "구축 상태와 남은 확인")
    ex = [re.sub(r"'\[[^']*\]'", "'<질의 벡터 1024차원>'", l) for l in M["explain"]]
    ex = [re.sub(r"\(cost=[^)]*\) ", "", l) for l in ex]
    b[k:end] = [
        ["h", "실행 결과"],
        ["code", "벡터 검색 실행계획 (2026-10-06 로컬 개발 DB, EXPLAIN ANALYZE, 핵심 줄)", "\n".join(plan_lines(ex))],
        ["note", "130조각에서는 색인 대신 순차 탐색 후 상위 3개를 고른다. 1회 실행 1.4ms."],
        ["code", "관계 조회 어댑터 실행 요약 (2026-10-06 로컬 개발 DB)",
         f"neighbors(정책 문서, [contains, in_document], depth=2)\n"
         f"  -> {G['rows']}행  (1단계 {G['by_depth']['1']} · 2단계 {G['by_depth']['2']})  중앙 {G['ms_p50']}ms / 95% {G['ms_p95']}ms (20회)\n"
         f"subgraph(사건 1건, depth=2)\n"
         f"  -> 간선 종류 {json.dumps(N['edge_kinds'], ensure_ascii=False)}  중앙 {N['ms_p50']}ms / 95% {N['ms_p95']}ms (20회)"],
    ]
    for blk in b:
        if blk[0] == "t" and blk[1] == ["항목", "결과"]:
            for row in blk[2]:
                if row[0].startswith("여행 정책 저장"):
                    row[1] = "구현. 2026-10-06 로컬 개발 DB 재조회로 12문서 · 130조각 · 1024차원 130/130 확인."
                if row[0].startswith("SQL 관계"):
                    row[1] = "구현. 여행 요청 처리 경로에서는 안 씀. 2026-10-06 로컬 실행으로 연결 확인, 정확도 기준은 없음."
                if row[0].startswith("현재 값 실패"):
                    row[1] = "시작 거부 · 배치 실패 종료 · 요청 치명 기록까지 확인. 요청 중 서버 종료는 확인 못 함."
    i = find(b, "note", "이 초안은 자료와")
    b[i] = ["note", "본문은 코덱스가 자료와 코드를 읽어 쓴 초안을 Claude 가 검토해 고쳤다. DB 수치 중 2026-10-06 표시가 있는 것은 "
                    "이 결과서를 위해 로컬 개발 DB에서 읽기 전용으로 새로 잰 값이고, 나머지 날짜는 원래 기록의 측정일이다."]
    return b


def plan_lines(ex):
    out = []
    for l in ex:
        if "Filter: ((tenant_id" in l:
            out.append("              Filter: tenant_id = 'demo' AND scope = 여행 정책 6개 범위")
        elif "Sort Key" in l:
            out.append("        Sort Key: (embedding_1024 <=> 질의 벡터)")
        else:
            out.append(l.rstrip())
    return out



# ---------- 제품 코드로 다시 잰 규정 검색 성능 (RAG 세션 리포트, 2026-10-06) ----------
RAG_SRC = ("출처: final_project_cs/wiki/records/reports/2026-10-06_RAG_평가지표_리포트.md §2 · §3 · §4-1 · §5 · §7 (RAG 세션 측정, 2026-10-06 16:52 기준선 · 17:35 개선 후). "
           "질문은 모두 모델이 쓴 합성 질문이다(A 180 · B 160, Codex 작성). 사람이 쓴 규정 질문과 사람 평가 점수는 없다. 정확도는 1회(검색은 결정적), 응답 시간만 120문제 x 3회.")
RAG_SEC = [
    ["h", "제품 코드로 다시 잰 규정 검색 성능 (2026-10-06)"],
    ["p", "결론: 제품의 규정 답 함수를 그대로 불러 질문 340개로 다시 쟀다. 독립 세트 B 에서 정답 규정이 상위 3개 안에 드는 비율은 30/48 = 62.5% 로 목표(0.90)에 못 미친다. "
          "답에 실린 규정 문장은 334/334 가 출처 문장과 글자 그대로 같았다. 색인 글을 고객용 문장으로 바꾸면 정답을 보인 비율이 21/48 → 31/48 로 오르지만, "
          "규정이 아닌 여행 대화 말에 규정을 붙이는 비율도 22.3% → 36.7% 로 오른다. 합성 시험 기준 점수이며 실서비스 점수가 아니다."],
    ["t", ["지표(답 있음 질문만)", "세트 A (100문제, 쉬움)", "세트 B (48문제, 독립)"], [
        ["Recall@1 (= Precision@1)", "0.660 (66/100)", "0.375 (18/48)"],
        ["Recall@3", "0.820 (82/100)", "0.625 (30/48)"],
        ["Recall@5 · Recall@10", "0.850 · 0.920", "0.667 · 0.729"],
        ["F1@3 (질문별 평균)", "0.410", "0.312"],
        ["MRR · nDCG@10", "0.750 · 0.788", "0.509 · 0.554"]], [3.4, 3.0, 3.0]],
    ["p", "세트 A 는 질문을 쓴 쪽이 고객용 문장을 보고 써서 쉽게 나온다. 판단은 세트 B 로 한다. 같은 B 를 10-02 에 다른 측정 도구로 잰 값(상위 1개 19/48)과 1개 차이가 나는데, 이 표가 제품 함수를 그대로 부른 최신 값이다."],
    ["t", ["문턱(최소 점수)", "B Precision", "B Recall", "B F1", "읽는 법"], [
        ["0.50", "0.852", "0.958", "0.902", ""],
        ["0.55 (운영)", "0.975 (39/40)", "0.812 (39/48)", "0.886", "답할 질문을 답함 39/48, 답 없는 질문 거절 49/50"],
        ["0.60", "1.000", "0.500", "0.667", "정답의 절반을 놓친다"]], [2.0, 1.6, 1.6, 1.2, 3.6]],
    ["t", ["근거 정확성 · 환각 방지", "목표", "값"], [
        ["답에 실린 규정 문장이 출처 문장과 글자 그대로 같음", "100%", "334/334 = 100% (모델이 규정 문장을 쓰지 않는 구조라 나오는 값)"],
        ["답 없는 질문에 규정을 보임(새어 나감)", "0", "3/110 = 2.7%"],
        ["인사 · 잡담을 규정 답으로 오인하지 않음", "", "39/40 = 97.5%"]], [4.4, 1.0, 4.6]],
    ["t", ["응답 시간(이 PC → x600 서버 임베딩 왕복 포함)", "p50", "p95", "오류"], [
        ["질문 임베딩만", "396ms", "579ms", "0/360"],
        ["규정 답 전체", "431ms", "596ms", "0/360"],
        ["pgvector SQL 만", "7ms", "10ms", "0/300"]], [4.6, 1.4, 1.4, 1.4]],
    ["t", ["색인 개선(직원용 본문 → 문서 제목 + 절 제목 + 고객용 문장)", "B 전 → 후"], [
        ["Recall@1 · Recall@3", "0.375 → 0.521 · 0.625 → 0.729"],
        ["MRR · nDCG@10", "0.509 → 0.654 · 0.554 → 0.701"],
        ["문턱 0.55 F1", "0.886 → 0.945"],
        ["정답 규정을 보인 비율", "21/48 → 31/48 (개선 후만 맞음 10 : 반대 0, p = 0.002)"],
        ["대가: 규정이 아닌 여행 대화 말(KLUE-WoS 300)에 규정을 붙임", "67/300 → 110/300 (22.3% → 36.7%)"]], [5.0, 4.4]],
    ["note", "색인 개선은 측정 도구가 같은 임베딩 함수로 색인을 메모리에 만들어 비교한 것이고, 제품 코드 · DB 는 바꾸지 않았다(운영 반영 전). "
             "번역 보호 장치는 시각 · 금액 숫자 변조 0/115 였지만 금액 단위가 바뀐 번역(일본어 원 → 엔) 1건이 통과했다. " + RAG_SRC],
]


RAG_REVERT = True


def add_rag(secs):
    s3 = secs[2]
    k = next(i for i, x in enumerate(s3) if x[0] == "h" and x[1].startswith("3.2"))
    s3[k:k] = RAG_SEC
    return secs


def main():
    _tmp = HERE / "_roles_build.dot"
    _tmp.write_text(TP.run_text((HERE / "roles.dot").read_text(encoding="utf-8")), encoding="utf-8")
    dot(_tmp, FIG / "역할_구성도.png")
    fig_policy(); fig_itin(); fig_road(); fig_latency()
    s = gloss(D["sections"])
    secs = [patch_s1(s[0]), patch_s2(s[1]), patch_s3(s[2]), patch_s4(s[3]), patch_s5(s[4])]
    # 2026-10-06 사용자 결정 「C 안」(RAG 세션 전달): RAG 세션 요청으로 넣은 3절 소절 「제품 코드로 다시 잰 규정 검색 성능」을 뺀다.
    # 그 결과는 6주차 서비스 테스트 보고서에만 싣는다. 되돌리기 전 판: _backup/<시각>_RAG요청분_되돌리기전/
    if not RAG_REVERT:
        secs = add_rag(secs)
    for blocks in secs:
        for blk in blocks:
            if blk[0] == "fig":
                raise ValueError(f"그림 자리가 남았다: {blk[1]}")
    # 용어 정비(2026-10-06 사용자 지적 「너만 아는 단어 다 수정」): 실무 용어로 바꾸고 1절에 「용어 정의」 표
    secs, miss = TP.run_blocks(secs, "vec")
    print("용어 정비: 못 찾은 문장", len(miss))
    out = W.build(TEMPLATE, OUT, sections=secs, max_img_h_cm=9.5, banners={
        2: "3. 검색 성능 및 정확도 검증 결과",
        3: "4. 데이터 운영 흐름 및 생명주기(Lifecycle)",
        4: "5. 구축 결과"})
    print("saved", out)


if __name__ == "__main__":
    main()
