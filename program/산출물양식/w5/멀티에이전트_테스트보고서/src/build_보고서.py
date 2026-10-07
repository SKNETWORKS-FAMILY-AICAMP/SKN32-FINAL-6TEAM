"""[모델링 및 평가] 멀티 에이전트 테스트 계획 및 결과 보고서 빌더 (2026-10-06).

재료: ../_재료/코덱스_초안.json(코덱스 초안, 코드 발췌 6개는 원문과 글자 대조 통과).
Claude 가 고친 곳: 기계 이름(GPU 서버 · x600 서버), 섞인 한자 · 일본어 글자, 그림 6장 새로 그림,
제품 코드 발췌 1개 추가(팀 재배분), 769문제 모델 비교 그림 추가.
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
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
W5 = HERE.parents[1]
ROOT = W5.parents[2]
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
TEMPLATE = W5.parent / "[모델링 및 평가] 멀티 에이전트 테스트 계획 및 결과 보고서_양식.docx"
OUT = HERE.parent / "[모델링 및 평가] 멀티 에이전트 테스트 계획 및 결과 보고서_6팀.docx"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
GREEN, GOLD, GREY, PURPLE = "#2D5F48", "#C8913A", "#9FB0A6", "#5B4FB3"

D = json.loads((MAT / "코덱스_초안.json").read_text(encoding="utf-8"))


# ---------- 그림 ----------
def dot(src, png):
    exe = Path(r"C:\Program Files\Graphviz\bin\dot.exe")
    subprocess.run([str(exe) if exe.exists() else "dot", "-Tpng", str(src), "-o", str(png)], check=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=200)
    plt.close(fig)
    return str(FIG / name)


def fig_ft():
    rows = [("주 지표 769문제", 688, 750, 769), ("Codex 작성 609문제", 548, 592, 609),
            ("Claude 작성 160문제", 140, 158, 160), ("새 여행자 검증 325문제", 265, 320, 325)]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = range(len(rows))
    for i, (n, a, b, den) in enumerate(rows):
        ax.bar(i - 0.19, a / den * 100, 0.36, color=GREY)
        ax.bar(i + 0.19, b / den * 100, 0.36, color=GREEN)
        ax.text(i - 0.19, a / den * 100 + 0.4, f"{a}", ha="center", fontsize=8)
        ax.text(i + 0.19, b / den * 100 + 0.4, f"{b}", ha="center", fontsize=8)
    ax.set_xticks(list(x), [r[0] for r in rows], fontsize=8.5)
    ax.set_ylim(75, 101)
    ax.set_ylabel("정답률(%) · 세로축 75%부터")
    ax.legend(handles=[Patch(color=GREY, label="가르치기 전(E4B)"), Patch(color=GREEN, label="가르친 뒤(E4B + LoRA)")],
              fontsize=8, frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "파인튜닝_전후.png")


def fig_769():
    rows = [("E4B 가르치기 전 (HF 4비트)", 688, "local"), ("E4B QAT (Ollama)", 701, "local"),
            ("Gemma 12B", 703, "big"), ("가르친 Kanana-2-3B", 715, "ft"), ("Winnow-12B Q8", 723, "big"), ("Decider-12B", 728, "big"),
            ("Gemma 26B-A4B", 732, "big"), ("가르친 Gemma 4 E2B", 739, "ft"), ("Luna (Codex CLI)", 741, "api"), ("OpenJev 26B", 743, "big"),
            ("E4B 가르친 뒤 CPU Q8", 748, "ft"), ("decider-chat 31B", 748, "big"), ("Qwen3.8 27B", 749, "big"),
            ("E4B 가르친 뒤 (HF 4비트)", 750, "ft"), *([] if RAG_REVERT else [("E4B 가르친 뒤 시드 2", 760, "ft")]), ("가르친 Winnow-E4B(Jev 계열)", 756, "ft"), ("Sol (Codex CLI)", 760, "api"),
            ("Claude Opus 5.5", 764, "api"), ("Claude Fable 5.1", 764, "api"), ("Astra (Codex CLI)", 766, "api")]
    col = {"local": GREY, "ft": GREEN, "big": GOLD, "api": PURPLE}
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    for i, (n, v, k) in enumerate(rows):
        ax.barh(i, v / 769 * 100, color=col[k], hatch="//" if k == "api" else None,
                edgecolor="white" if k == "api" else None, height=0.65)
        ax.text(v / 769 * 100 + 0.1, i, f"{v}/769 = {v / 769 * 100:.1f}%", va="center", fontsize=7.5)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=8)
    ax.set_xlim(88, 102)
    ax.set_xlabel("요청 둘 문제를 뺀 769문제 정답률(%) · 가로축 88%부터")
    ax.legend(handles=[Patch(color=GREY, label="소형 무학습"), Patch(color=GREEN, label="소형 가르친 뒤"),
                       Patch(color=GOLD, label="큰 로컬 모델(총 파라미터 기준, 소형 예산 밖 참고)"),
                       Patch(facecolor=PURPLE, hatch="//", edgecolor="white", label="상용 서비스(공정 비교 아님)")],
              fontsize=7.5, frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "모델별_769_비교.png")


def fig_cpu():
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    ax.barh([1, 0], [67.5, 4.55], color=[GOLD, GREEN], height=0.55)
    ax.text(68.5, 1, "평균 67.5초 (일정 5개)", va="center", fontsize=8.5)
    ax.text(5.5, 0, "평균 4.55초 · 95백분위 5.62초 (830질문)", va="center", fontsize=8.5)
    ax.set_yticks([1, 0], ["새 일정의 첫 질문", "같은 일정 후속 질문"], fontsize=9)
    ax.set_xlim(0, 95)
    ax.set_xlabel("CPU 코어 4개 · GGUF Q8 · GPU 끔 · 1회 실행 (2026-10-06)")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "CPU_지연.png")


def fig_cls():
    heads = ["의도", "감정", "긴급도", "대상"]
    rows = [("BGE-M3 (학습, 시드 3)", [97.7, 94.8, 89.8, 95.4], GREEN),
            ("mE5-base (학습, 시드 3)", [98.2, 94.5, 90.6, 93.4], "#5E9C7E"),
            ("E4B QAT (학습 없음, 중앙 지연 5.3초/건)", [97.2, 83.9, 60.9, 86.2], GOLD),
            ("Winnow-E4B 한국어 설명 (Jev 계열 LLM형, 학습 없음)", [94.5, 91.0, 63.5, 92.1], PURPLE)]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    w = 0.2
    for j, (n, v, c) in enumerate(rows):
        ax.bar([i + (j - 1.5) * w for i in range(4)], v, w, color=c, label=n)
    ax.set_xticks(range(4), [f"{h}" for h in heads])
    ax.set_ylim(0, 105)
    ax.set_ylabel("정확도(%) · CX 400")
    ax.legend(fontsize=7.5, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "분류모델_비교.png")


def fig_rag():
    fig, ax = plt.subplots(figsize=(7.2, 2.0))
    ax.barh([1, 0], [21 / 48 * 100, 31 / 48 * 100], color=[GREY, GREEN], height=0.55)
    ax.text(21 / 48 * 100 + 1, 1, "21/48", va="center", fontsize=9)
    ax.text(31 / 48 * 100 + 1, 0, "31/48", va="center", fontsize=9)
    ax.set_yticks([1, 0], ["지금 운영(본문 색인)", "실험 색인 E(미반영)"], fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("독립 질문에서 정답 근거 문장을 보여 준 비율(%) · 문턱 0.55 고정 · 2026-10-02")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "RAG_색인_비교.png")


# ---------- 글 고치기 ----------
BS = chr(92)
FIX = [(r"集합", "집합"), (r"±は", "±는"), (r"서버 A GPU", "GPU 서버 A"),
       (r"(?<!GPU )서버 ([AB])(?![a-zA-Z])", r"GPU 서버 \1"), (r"원격 모델 서버", "원격 GPU 서버"),
       (r"원격 제품 서버", "x600 서버의 cs 프로젝트 서버"), (r"실제 서버 강제 종료", "cs 프로젝트 서버 강제 종료"),
       (r"직접 서버에서는 키 거절", "경유 서버를 거치지 않으면 키 거절"),
       (r"서버 응답 로그 미확인", "llama.cpp 서버 응답 로그 미확인"), (r"원격 배포 기록은", "x600 서버 배포 기록은"),
       (r"실제 서버 종료·재시작·복구", "cs 프로젝트 서버 종료·재시작·복구"),
       (r"현재 로컬 DB·원격 서버·모델", "현재 로컬 DB·x600 서버·GPU 서버·모델"),
       (r"개선 색인이 제품에 반영됐는지와 실제 고객 질문 성능은 아직 확인하지 못했다" + BS + ".",
        "개선 색인은 아직 제품 적재 코드에 들어가지 않았다(지금 적재 코드는 본문을 임베딩한다). 실제 고객 질문 성능도 확인하지 못했다."),
       (r"RAG/blind/results/eval_variants_out" + BS + ".txt, 정본 §36~37" + BS + ".", "정본 §36~37(고정 문턱 21/48 · 31/48 은 §37 표)."),
       (r"^GPU 서버 ([AB])$", r"GPU 서버 " + BS + "1 (RunPod 원격)")]
BS = chr(92)

# 처음 나오는 곳에만 쉬운 말을 붙인다(코드 블록 제외)
TERMS = [("하네스", "하네스(같은 입력 · 실행 조건 · 채점 규칙을 쓰는 평가 틀)"),
         ("McNemar 정확검정", "McNemar 정확검정(같은 문제에서 두 모델의 정오답 차이가 우연인지 보는 통계 검사)"),
         ("NF4 QLoRA", "NF4 QLoRA(모델을 4비트로 줄여 싣고 작은 추가 가중치만 학습하는 방식)"),
         ("멱등", "멱등(같은 요청을 여러 번 받아도 처리는 한 번)"),
         ("shadow 적용", "shadow 적용(고객 처리에는 쓰지 않고 판단만 기록하는 시험 운영)")]


def gloss_first(secs):
    done = set()

    def walk(x):
        if isinstance(x, str):
            for t, g in TERMS:
                if t not in done and t in x:
                    x = x.replace(t, g, 1)
                    done.add(t)
            return x
        if isinstance(x, list):
            if x and x[0] == "code":
                return x
            return [walk(v) for v in x]
        return x
    return walk(secs)


def fix(x):
    if isinstance(x, str):
        for a, b in FIX:
            x = re.sub(a, b, x)
        return x
    if isinstance(x, list):
        return [fix(v) for v in x]
    return x


def reroute_code():
    f = ROOT / "final_project_cs/app/application/controller.py"
    lines = f.read_text(encoding="utf-8").splitlines()
    a = next(i for i, l in enumerate(lines) if "if self.reroute is None:" in l)
    z = next(i for i, l in enumerate(lines) if '"by": picked.get("by")' in l)
    head = next(i for i, l in enumerate(lines) if "def _reroute_once" in l)
    body = []
    for l in [lines[head]] + ["        ..." if False else "        # (설명 문자열 12줄 생략)"] + lines[a:z + 1]:
        body.append(re.sub(r"\s+#.*[—★].*$", "", l))
    return ["code", f"final_project_cs/app/application/controller.py:{head + 1} · {a + 1}~{z + 1}, 팀 재배분 (제품 코드)",
            "\n".join(body)], ["note", "제품용 코드다. 받는 팀이 없을 때 등록된 팀 목록을 넘겨 한 번만 다시 고르고, "
                                       "고른 결과를 등록부(Registry)에 다시 물어 없는 팀이면 버린다. 설명 문자열 12줄과 줄 끝 주석 2개는 지면 때문에 뺐다. 실행 코드는 원문 그대로다. "
                                       "연결된 시험: 팀 재배분 mock 서버 시험 10/10 (2026-10-06)."]


def strip_dup(b):
    return [x for x in b if not (x[0] == "h" and re.match(r"^\d\.\s", x[1]))]


def at(b, kind, start):
    for i, x in enumerate(b):
        if x[0] == kind and str(x[1]).startswith(start):
            return i
    raise KeyError(start)



# ---------- 요식 담당 팀원 보고서에서 가져온 것 (2026-10-06) ----------
SH_SRC = '출처: 요식 담당 팀원(정세환)의 「멀티 에이전트 테스트 계획 및 결과 보고서」(team_branch/sh, 2026-10-06), 기준 코드 조직 develop 2f3594a(PR #34, role-dining 3fad933). 우리 저장소에는 622639f4 에서 합쳤다. 이 세션에서 시험을 다시 돌리지 않았으며, 수치는 그 보고서의 실행 기록이다.'

SH_DESIGN = [
    ["b", "요식 에이전트 설계:", "입구 여섯 곳(웹 채팅 · 버튼 · Case · 일정 접수 · 일정 생성기 · 새벽 점검)이 같은 계산 함수와 같은 요식 원장(식당 영업 판정 표)을 쓴다. "
          "모델은 고객 문장의 분류와 신고 추출 두 곳에서만 부르고, 요식 Team 안의 판정 · 계산은 코드가 원장 값으로 한다. "
          "판정 항목은 폐업 · 휴업, 정기 휴무, 명절 · 공휴일, 영업시간 · 브레이크, 라스트오더, 당일 사정 여섯 가지다.", 0],
    ["note", "요식 담당 팀원의 「AI 시스템 아키텍처」(team_branch/sh, 2026-10-06)에서 가져왔다. 「Team 안에 모델 호출이 없다」는 지금 저장소의 "
             "app/domains/travel_ops/instances/dining 파이썬 파일에서 모델 호출 흔적을 찾지 못한 것으로 대조했다(검색 범위: 그 폴더). "
             "그 문서의 그림은 실패를 「사람 상담원 인계」로 끝내게 그려져 있어, 고객 건을 사람에게 넘기지 않는 지금 결정과 맞지 않아 가져오지 않았다."],
]

SH_TESTS = [
    ["h", "2.4 요식 에이전트 단위 · 통합 시험"],
    ["p", "요식 에이전트와 그것이 쓰는 여행 창구 · 요식 원장 · 새벽 점검 · Case 경로를 네 층으로 시험했다. 517건이 모두 통과했다. "
          "모델은 mock 으로 바꿔 결과가 매번 같게 했고, 실제 외부 API(구글 · 카카오 · 관광공사)는 부르지 않았다."],
    ["t", ["층", "보는 것", "통과/건수", "시간(초)"], [
        ["단위", "대체 후보 · 영업 판정 · 가격 순위 · 신고 검증 · 접수 · 생성기 · 등록 판정", "314/314", "0.56"],
        ["통합", "실제 PostgreSQL 에서 원장 판정 SQL · 근처 가게 · 코어 장소 연결 · 적재", "152/152", "3.26"],
        ["시나리오", "확정 시나리오 하루 · Case 버전 하루 · 새벽 점검 · 모름 처리", "46/46", "39.37"],
        ["e2e", "일정 생성기 → 등록 → 원장 연결(HTTP API)", "5/5", "3.13"],
        ["합계", "시험 파일 38개", "517/517 = 100%", "50.68"]], [1.2, 5.6, 1.8, 1.2]],
    ["p", "판정 항목마다 그것을 확인하는 시험을 짝지었다. 유스케이스 17개(서비스 14 · 운영 도구 3)도 같은 방식으로 짝지었는데, "
          "판정 근거를 보여 주는 화면(UC-16)만은 화면 전용 시험이 없고 같은 판정 SQL 시험(49건)으로 대신한다."],
    ["t", ["판정 항목", "확인하는 시험(예)", "층"], [
        ["C1 폐업 · 휴업", "폐업 가게는 「모름」이 아니라 「닫힘」(3건) · 닫은 가게는 대체 후보로 내지 않음", "통합"],
        ["C2 정기 휴무", "휴무로 확인된 날은 닫힘 · 규칙이 없는 요일은 닫힘이 아니라 모름", "통합 · 단위"],
        ["C3 명절 · 공휴일", "명절 당일과 연휴 구분 · 명절이면 확인 필요", "단위"],
        ["C4 영업시간 · 브레이크", "브레이크 사이는 닫힘 · 식사가 영업 종료를 넘기면 닫힘 · 새벽 방문은 전날 영업의 연장", "통합"],
        ["C5 라스트오더", "라스트오더를 넘기면 닫힘 · 모르면 판정에서 빼고 종료가 임박하면 경고", "통합"],
        ["C6 당일 사정", "오늘 닫은 점심을 하루 시작 전에 바꿈 · 키가 없으면 그렇다고 말하고 아무것도 부르지 않음", "시나리오"]],
     [2.0, 6.4, 1.4]],
    ["t", ["묶음", "결과", "언제 · 어디서"], [
        ["develop CI 관문(로컬): 구조 · 계약 · 단위", "2,110 통과 · 71 건너뜀 · 실제 모델 시험 214 제외", "2026-10-06 로컬, CI 와 같은 조건"],
        ["보안 시험", "23 통과", "같음"],
        ["GitHub CI(PR #34 · develop 머지)", "검사 9건 모두 success(웹 · 관리 화면 · Docker 빌드 포함)", "2026-10-04"]], [3.4, 4.0, 2.6]],
    ["note", SH_SRC + " 이 묶음은 요식 쪽 범위의 시험이라 5.1 의 cs 프로젝트 전체 시험 묶음(다른 날 · 다른 커밋)과 더하지 않는다."],
]

SH_LIVE = [
    ["h", "4.4 실제 모델(gemma4:e4b)로 돌린 여행 시나리오 30회"],
    ["p", "결론: 30회 중 19회가 판정을 통과했지만, 모델 호출 66회 중 62회가 모델 서버 연결 오류였다. 그래서 이 결과로는 실제 모델이 신고를 제대로 처리한다고 말할 수 없다. "
          "규칙을 어긴 변경과 치명 오류는 0건이었다."],
    ["t", ["지표", "결과", "읽는 법"], [
        ["시나리오 판정", "19/30 = 63.3%", "10개 시나리오 x 3회. 판정 통과와 실제 처리 성공은 다르다"],
        ["규칙 위반 · 치명 오류", "0건 · 0건", "모르는 값으로 일정을 바꾼 일은 없었다"],
        ["모델 호출 오류", "62/66 = 93.9%", "분류 34/36 · 신고 추출 28/30 이 연결 거부 · 끊김"],
        ["고객 요청 단계 결과", "36단계 중 처리 완료 2 · escalated 34", "escalated 는 처리 중단 기록이며 사람에게 넘긴 것이 아니다"],
        ["mock 결과와 일치", "2/36 = 5.6%", "상태와 담당 Team 이 모두 같은 단계 수"],
        ["신고 종류 정확도", "2/30 = 6.7%", "오류 때문에 모델 실력을 잰 값이 아니다"]], [2.4, 2.6, 5.0]],
    ["t", ["시나리오", "통과/3회", "본 것"], [
        ["확정 하루 전체", "1/3", "첫 회만 지연 · 휴무 처리. 이후 2회는 일정 판이 기대보다 덜 올라감"],
        ["사건 없는 하루 · 미세먼지 경보 · 경로 사건", "각 3/3", "모델을 부르지 않는 감시 경로라 오류 영향 없음"],
        ["70분 지연 · 저녁 식당 임시휴무 · 대안 교체와 되돌리기", "각 0/3", "모델 호출 오류로 전부 처리 중단"],
        ["품절 문의 · 200분 지연 · 현금만 쓰는 여행", "각 3/3", "일정을 안 바꾸는 것이 정답이라 통과했지만 안내 처리 성공은 확인 안 됨"]], [4.0, 1.4, 4.6]],
    ["p", "정상 응답이 온 두 번(확정 하루의 지연 · 휴무 신고)은 지연 70분 · 휴무를 바르게 뽑아 요식 Team 이 처리를 끝냈다. "
          "모델 서버(Ollama)를 복구한 뒤 같은 30회를 다시 돌려야 정확도 · 반복 안정성 · 응답 시간을 말할 수 있다."],
    ["note", SH_SRC + " 실행 식별자 20261006_122714, 평가 자료 eval/datasets/travel_scenarios.jsonl, 사건 출처는 재생 자료. "
             "실행 결과 파일(2026-10-06_travel_scenarios_live_gemma4-e4b.json · _score.json)은 이 작업 폴더에서 찾지 못했다(검색 범위: final_workspace 전체)."],
]


def add_sh(secs):
    # 1.3: 요식 설계 한 줄
    s1 = secs[0]
    i = at(s1, "h", "1.3")
    j = next(k for k in range(i + 1, len(s1)) if s1[k][0] == "t")
    s1[j + 1:j + 1] = SH_DESIGN
    # 2.4 / 4.4
    secs[1] += SH_TESTS
    s4 = secs[3]
    k = at(s4, "h", "4.3")
    s4[k:k] = SH_LIVE
    for x in s4:
        if x[0] == "h" and x[1].startswith("4.3"):
            x[1] = x[1].replace("4.3", "4.5", 1)
    # 4.4 를 4.3 앞에 넣었으니 번호를 4.3 실제 모델 / 4.4 예외로 맞춘다
    for x in s4:
        if x[0] == "h" and x[1].startswith("4.4 실제 모델"):
            x[1] = x[1].replace("4.4", "4.3", 1)
        elif x[0] == "h" and x[1].startswith("4.5"):
            x[1] = x[1].replace("4.5", "4.4", 1)
    # 5.1 표 · 5.2 표 · 다음에 잴 것
    s5 = secs[4]
    for x in s5:
        if x[0] == "t" and x[1][:2] == ["구분", "테스트 수"]:
            x[2] += [["요식 에이전트 시험(팀원)", "517", "517", "0", "517/517, 100%", "2026-10-06, 조직 develop 2f3594a. 다른 묶음과 합산 금지"],
                     ["실제 모델 여행 시나리오(팀원)", "30", "19", "11", "19/30, 63.3%", "2026-10-06, 모델 호출 62/66 오류라 모델 성능 판단 불가"]]
        if x[0] == "t" and x[1][:1] == ["이슈"]:
            x[2] += [["API 키 템플릿 시험 오판(팀원 보고)", "네이버 검색 키 이름이 _CLIENT_ID · _CLIENT_SECRET 으로 끝나 비밀 키로 알아보지 못함",
                      "그런 이름도 비밀로 보게 고침(3fad933)", "2026-10-04 GitHub CI 9건 success"],
                     ["실제 모델 시나리오의 모델 서버 연결 오류(팀원 보고)", "Ollama 가 연결을 끊은 뒤 연결 거부가 반복(66회 중 62회)",
                      "모델 서버 상태 확인 뒤 같은 30회 재실행 필요", "미완료. 지연 · 휴무 · 대안 교체 11회 실패가 그대로 남음"]]
    last = max(k for k, x in enumerate(s5) if x[0] == "b" and str(x[1]).startswith("6."))
    s5.insert(last + 1, ["b", "7. 실제 모델 시나리오 재실행:", "모델 서버를 복구하고 요식 담당 팀원의 여행 시나리오 30회를 다시 돌려 정확도 · 반복 안정성 · 응답 시간을 잰다.", 0])
    return secs



# ---------- 한 줄로 이은 시험 (RAG 세션, 2026-10-06, 로컬 커밋 dcc64923) ----------
# 표기 규칙(2026-10-06 사용자 지시): 「Jev」라고만 쓰지 않는다. 학습 없는 판은 「Winnow-E4B(Jev 계열, 학습 없음)」,
# 가르친 판은 「가르친 Winnow-E4B(Jev 계열)」, 유료 API 는 「Jev API(유료)」, 개념은 「Jev 계열 모델」.
CHAIN_SRC = ("출처: program/scripts/plan_qa_bench/results/chain_report.txt · results/_pull/chain/chain_*.json(문제별 추적) · "
             "정본 program/research/여행일정_질문인식_모델비교_2026-09-29.md §92(사전 등록 §92-1~2, 사후 수정 §92-3, 결과 §92-4, 한계 §92-5, 가르친 Jev 계열 모델로 다시 §92-6). "
             "실행 코드 server/chain_e2e.py. 2026-10-06, GPU 서버 C(RunPod 원격, RTX 4000 Ada 20GB), 변형마다 1회(출력은 결정적).")
W_RAW = "Winnow-E4B(Jev 계열, 학습 없음)"
CHAIN_ROWS = [  # 변형, 정답, 못 찾음, 요청둘 A·B, 호출 규칙·ML·Winnow-E4B·E4B, 중앙·p95, 단독 대비
    ("가르친 E4B 단독(기준선)", 748, 0, "60 · 62", "0 · 0 · 0 · 835", "199 · 208", "기준"),
    ("규칙 → 가르친 E4B", 745, 0, "58 · 61", "835 · 0 · 0 · 710", "197 · 211", "3 : 6, p=0.51"),
    ("규칙 → ML 거름 → 가르친 E4B (Winnow-E4B 뺌)", 745, 0, "58 · 61", "835 · 626 · 0 · 674", "216 · 247", "3 : 6, p=0.51"),
    ("한 줄 연결 전체, 수정 판(Winnow-E4B 입력에 일정 목록)", 697, 53, "58 · 61", "835 · 626 · 590 · 502", "662 · 768", "3 : 54, p=4e-13"),
    ("수정 판에서 ML 뺌", 697, 53, "58 · 61", "835 · 0 · 626 · 502", "629 · 731", "3 : 54"),
    ("수정 판에서 규칙 뺌", 686, 67, "60 · 62", "0 · 835 · 792 · 609", "710 · 769", "0 : 62, p=4e-19"),
    ("Winnow-E4B 입력에 메시지만", 533, 217, "45 · 48", "835 · 626 · 590 · 351", "202 · 408", "4 : 219"),
    ("한 줄 연결 전체, 사전 등록 판", 472, 279, "37 · 40", "835 · 626 · 590 · 258", "201 · 406", "4 : 280"),
]
CS = json.loads((MAT / "c_scoring_new.json").read_text(encoding="utf-8"))  # src/c_scoring_new.py 결과(A · B · C)


def cfull(key):
    v = CS[key]
    return f"{v['C_all']}/835 ({v['C_all'] / 835 * 100:.1f}%)"


FAIR_MODELS = [  # 같은 레시피 QLoRA, 요청 둘 제외 769, HF 4비트 + 어댑터, GPU 서버 B
    ("가르친 Winnow-E4B(Jev 계열, 유효 4B)", "655 (85.2%, 읽기 오류 23)", "756 (98.3%)", "10 : 4 (p=0.18)", "1.58"),
    ("가르친 E4B(Gemma 4 E4B)", "688 (89.5%)", "750 (97.5%)", "기준", "1.58"),
    ("가르친 Gemma 4 E2B(유효 2B)", "", "739 (96.1%)", "", "1.11"),
    ("가르친 Kanana-2-3B-Instruct", "", "715 (93.0%)", "", "0.84"),
]
FAIR_STRUCT = [  # 구성, 정답/769, 가르친 E4B 단독 대비
    ("단독 가르친 E4B", 750, "기준"),
    ("단독 가르친 Winnow-E4B(Jev 계열)", 756, "10 : 4 (p=0.18)"),
    ("규칙 → ML → 가르친 E4B", 747, "4 : 7 (p=0.55)"),
    ("규칙 → ML → 가르친 Winnow-E4B(Jev 계열)", 752, "12 : 10 (p=0.83)"),
    ("규칙 → ML → 가르친 E4B, 확신 낮으면 가르친 Winnow-E4B 로 인계", 752, "11 : 9 (p=0.82)"),
    ("규칙 → ML → 가르친 Winnow-E4B, 확신 낮으면 가르친 E4B 로 인계", 750, "10 : 10 (p=1)"),
    ("규칙 → ML 유형 판별기 → 유형별로 더 나은 가르친 모델", 751, "9 : 8 (p=1)"),
    ("규칙 → 학습한 ML 라우터 → 두 가르친 모델 중 고름", 751, "10 : 9 (p=1)"),
    ("(상한) 규칙 · ML 뒤에서 두 가르친 모델 중 하나라도 맞히면", 755, "12 : 7 (p=0.36)"),
]


def fig_chain():
    rows = CHAIN_ROWS
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    cols = [GREEN, "#5E9C7E", "#5E9C7E", PURPLE, "#8C83C9", "#8C83C9", GREY, GOLD]
    for i, (n, v, *_rest) in enumerate(rows[::-1]):
        ax.barh(i, v / 769 * 100, color=cols[::-1][i], height=0.62)
        ax.text(v / 769 * 100 + 0.5, i, f"{v}/769 = {v / 769 * 100:.1f}%   건당 중앙 {_rest[3].split(' · ')[0]}ms", va="center", fontsize=7.8)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]], fontsize=7.6)
    ax.set_xlim(55, 138)
    ax.set_xticks([60, 70, 80, 90, 100])
    ax.set_xlabel("769문제 정답률(%) · 가로축 55%부터 · 빈 응답은 틀림")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "한줄연결_시험.png")


def fig_fair():
    rows = FAIR_STRUCT
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for i, (n, v, _p) in enumerate(rows[::-1]):
        c = GREEN if "Winnow" in n and "E4B 로 인계" not in n else ("#9FB0A6" if n.startswith("(상한)") else "#5E9C7E")
        if n == "단독 가르친 E4B":
            c = GREY
        ax.barh(i, v / 769 * 100, color=c, height=0.62)
        ax.text(v / 769 * 100 + 0.03, i, f"{v}/769 = {v / 769 * 100:.1f}%", va="center", fontsize=7.8)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]], fontsize=7.4)
    ax.set_xlim(96.5, 99.2)
    ax.set_xlabel("769문제 정답률(%) · 가로축 96.5%부터 · 모두 차이 구분 안 됨")
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "가르친_Jev계열_구성비교.png")


# ---------- 출제자를 뺀 상용 비교 (2026-10-06 사용자 지시) ----------
# 「클로드랑 코덱스는 각각 자기가 만든 테스트에서는 참여 못하게 하고 B, C 테스트에서 비교하게 했어야 해」.
# 계산: src/fair_commercial.py → _재료/fair_commercial.json (저장된 문제별 풀이를 다시 셈, 새 모델 호출 없음)
FAIRC = json.loads((MAT / "fair_commercial.json").read_text(encoding="utf-8"))


def fig_fair_comm():
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.9), sharex=False)
    titles = {"codex_made": "mix8~11 (Codex 출제, 659문제)\nCodex 모델은 뺌", "claude_made": "mix12 (Claude 출제, 176문제)\nClaude 모델은 뺌"}
    for ax, sub in zip(axes, ("codex_made", "claude_made")):
        rows = FAIRC[sub][::-1]
        ys = range(len(rows))
        n = rows[0]["n"]
        col = [PURPLE if r["kind"] in ("claude", "codex") else (GREEN if r["kind"] == "local_ft" else GOLD) for r in rows]
        ax.barh([y + 0.2 for y in ys], [r["B"] / n * 100 for r in rows], height=0.38, color=col, alpha=0.95, label="B 채점")
        ax.barh([y - 0.2 for y in ys], [r["C"] / n * 100 for r in rows], height=0.38, color=col, alpha=0.45, hatch="..", edgecolor="white", label="C 채점")
        for y, r in zip(ys, rows):
            ax.text(r["B"] / n * 100 + 0.2, y + 0.2, f"B {r['B'] / n * 100:.1f}%", va="center", fontsize=6.8)
            ax.text(r["C"] / n * 100 + 0.2, y - 0.2, f"C {r['C'] / n * 100:.1f}%", va="center", fontsize=6.8)
        ax.set_yticks(list(ys), [r["model"].replace("(", "\n(") for r in rows], fontsize=6.6)
        ax.set_xlim(84, 103)
        ax.set_title(titles[sub], fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("정답률(%) · 가로축 84%부터", fontsize=7)
    axes[0].legend(fontsize=6.8, loc="lower right")
    fig.tight_layout()
    return save(fig, "상용_출제자제외_BC.png")


def fair_comm_blocks():
    def rows(sub):
        return [[r["model"], f"{r['B']}/{r['n']} ({r['B'] / r['n'] * 100:.1f}%)", f"{r['C']}/{r['n']} ({r['C'] / r['n'] * 100:.1f}%)", r["note"] or "없음"] for r in FAIRC[sub]]
    return [
        ["b", "출제자를 뺀 상용 비교(B · C 채점):", "위 769문제 비교는 상용 모델이 자기가 낸 문제까지 풀어 공정하지 않았다. 그래서 문제를 쓴 쪽을 그 문제에서 빼고 다시 셌다. "
              "Codex 가 쓴 mix8~11(659문제)에서는 Codex 모델을, Claude 가 쓴 mix12(176문제)에서는 Claude 모델을 뺐다. 채점은 B(한 문장에 항목 둘을 묻는 질문은 하나라도 맞으면 정답)와 "
              "C(낸 항목 집합이 정답 집합과 완전히 같아야 정답) 두 가지다. 저장된 문제별 풀이를 다시 센 것이고 모델을 새로 부르지 않았다.", 0],
        ["t", ["mix8~11 (Codex 출제, 659문제) · Codex 모델 제외", "B 채점", "C 채점", "남는 치우침"], rows("codex_made"), [3.6, 1.6, 1.6, 2.4]],
        ["t", ["mix12 (Claude 출제, 176문제) · Claude 모델 제외", "B 채점", "C 채점", "남는 치우침"], rows("claude_made"), [3.6, 1.6, 1.6, 2.4]],
        ["img", fig_fair_comm(), "그림 4-1. 출제자를 뺀 비교. 진한 막대가 B, 옅은 점무늬 막대가 C 채점이다. 보라는 상용, 초록은 파인튜닝한 로컬 모델, 금색은 파인튜닝하지 않은 로컬 모델.", 9.0],
        ["p", "읽는 법: 출제자를 빼도 상용 모델이 B · C 모두 가장 높았다(mix8~11 에서 Claude 98.5~99.1% · mix12 에서 Codex Sol · Astra 99.4%). "
              "B 채점에서 파인튜닝한 E4B(약 4B)는 Qwen3.8 27B 와 같은 642/659 였고 mix12 에서는 26B · 27B 보다 2문제 많았다. "
              "C 채점에서 로컬 모델이 크게 낮은 것은 한 항목만 내는 구조라 복수 항목 질의(mix8~11 에 50문제, mix12 에 16문제)를 모두 놓치기 때문이다. "
              "mix12 는 176문제라 1~2문제 차이는 구분되지 않는다."],
        ["note", "남는 치우침: 복수 항목 질의의 정답 집합은 Claude 가 만들었으므로 mix8~11 의 C 채점에서도 Claude 모델은 정답 키 작성자와 같은 손이다. "
                 "파인튜닝 E4B 의 학습 자료도 Claude 가 만들어 mix12 에서 유리할 수 있다. 상용 모델은 문제마다 CLI 로 불렀고(생각 끔), 「항목이 둘이면 둘 다 내라」는 지시를 받은 집합 출력 실행이다. "
                 "계산: src/fair_commercial.py (program/scripts/plan_qa_bench/c_scoring_all.py 와 같은 결과 파일 · 같은 채점 정의)."],
    ]


def chain_code():
    f = ROOT / "program/scripts/plan_qa_bench/server/chain_e2e.py"
    lines = f.read_text(encoding="utf-8").splitlines()
    a = next(i for i, l in enumerate(lines) if l.startswith("    if ended is None and route is None and fl['ml']:"))
    z = next(i for i, l in enumerate(lines) if "tr['path'].append('reject→없음')" in l)
    body = [re.sub(r"\s+#.*$", "", l) if ("Jev" in l or "—" in l) else l for l in lines[a:z + 1]]
    return ["code", f"program/scripts/plan_qa_bench/server/chain_e2e.py:{a + 1}~{z + 1}, ML 거름 → Winnow-E4B(Jev 계열) 선택 → 전문가 호출 (연구용 코드, 줄 끝 주석 일부 생략)",
            "\n".join(body)]


CHAIN_SEC = [
    ["h", "4.4 한 줄로 이은 시험 (규칙 → ML → Jev 계열 모델 분류 → 전문가)"],
    ["p", "결론: 네 단계를 문제마다 실제로 불러 끝까지 이어 돌렸다. 보낼 곳을 고르는 자리에는 Jev 계열 모델 가운데 Winnow-E4B(학습 없는 원본)를 썼다. "
          "학습 없는 Winnow-E4B 를 그 자리에 넣은 한 줄 연결은 가르친 E4B 하나만 쓸 때보다 정답이 51개 적고(697 대 748, p=4e-13) 한 건에 3.4배 오래 걸렸다. "
          "Winnow-E4B 를 빼고 규칙과 ML 거름만 앞에 둔 구성은 단독과 구분되지 않으면서(745, 3 : 6, p=0.51) 가르친 E4B 호출을 19% 줄였다(835 → 674회)."],
    ["b", "공정성 표시:", "이 비교는 학습 조건이 달랐다. 전문가인 E4B 는 우리 데이터로 가르친 모델이었고, Winnow-E4B(Jev 계열)는 학습 없는 원본이었다. "
                         "그래서 「51개 손해」는 「학습 없는 Jev 계열 모델을 보낼 곳 판정에 넣으면」으로만 읽는다. 같은 방법으로 가르친 Winnow-E4B 로 다시 잰 결과는 이 절 끝에 있다.", 0],
    ["t", ["변형", "정답/769", "C 전체/835", "못 찾음", "요청 둘 A · B · C /66", "호출 규칙 · ML · Winnow-E4B · E4B", "건당 중앙 · p95 (ms)", "단독 대비(이쪽만 : 단독만)"],
     [[r[0], f"{r[1]} ({r[1] / 769 * 100:.1f}%)", f"{r[1]} ({r[1] / 835 * 100:.1f}%)", str(r[2]), r[3] + " · 0", r[4], r[5], r[6]] for r in CHAIN_ROWS],
     [2.8, 1.4, 1.4, 0.8, 1.3, 1.9, 1.3, 1.5]],
    ["note", "C 전체 = 835문제를 C(말한 항목을 모두 정확히 찾아야 정답)로 채점한 값이다. 이 시험의 전문가는 한 항목만 내므로 요청 둘 66문제의 C 가 0 이고, C 전체는 요청 둘 제외 정답 수를 835 로 나눈 값과 같다. 계산 src/c_scoring_new.py(저장된 문제별 추적을 다시 채점, 원 보고서 숫자와 일치 확인)."],
    ["img", "__CHAIN_FIG__", "그림 7. 한 줄로 이은 시험의 변형별 정답률. 보낼 곳 판정은 Winnow-E4B(Jev 계열, 학습 없음), 전문가는 가르친 E4B. 같은 GPU 서버 · 같은 GGUF · 같은 769문제, 2026-10-06."],
    ["p", "어디서 끝났나(수정 판, 835문제): 규칙이 125개(서수 · 상대 위치 73 · 같은 장소 22 · 「말고」 11 · 이름 없는 설명 9 · 변경 요청 6 · 요청 둘 3 · 범위 밖 1), "
          "ML 판별기가 범위 밖으로 36개(모두 잡담 유형, 모두 맞음), Winnow-E4B(Jev 계열, 학습 없음)가 범위 밖으로 172개, 나머지 502개가 가르친 E4B 로 갔다. "
          "캐시 없이 다시 부른 실제 지연은 단독 중앙 196ms · p95 204ms, 한 줄 연결 중앙 658ms · p95 765ms 였다. 단계별 중앙은 규칙 약 0ms · ML 35ms · Winnow-E4B 478ms · 가르친 E4B 198ms 다."],
    ["p", "Winnow-E4B(Jev 계열, 학습 없음)의 보낼 곳 선택 정확도(규칙 · 앞 대화가 끝낸 문제를 뺀 626문제, 범위 밖 유형만 「범위 밖」이 정답): 수정 판 488/626 = 78.0%, 사전 등록 판 250/626 = 39.9% 였다. "
          "손해는 대부분 일정 질문을 범위 밖으로 잘못 닫은 데서 나왔다(수정 판 135/550). 정답 항목이 있는데 놓친 53개 가운데 41개가 이름 없는 설명(「거기 그 국밥집」 같은 말)이다."],
    ["t", ["단계를 하나씩 뺀 비교(수정 판 697 기준)", "정답 변화", "읽는 법"], [
        ["규칙을 뺌", "697 → 686 (11개 손해)", "규칙이 서수 · 같은 장소 질문을 지켜 준다"],
        ["ML 판별기를 뺌", "697 → 697 (변화 없음)", "대신 Winnow-E4B 호출이 36개 늘어난다"],
        ["Winnow-E4B(학습 없음)를 뺌", "697 → 745 (48개 이득)", "학습 없는 Winnow-E4B 의 선택이 정답을 깎는다"]], [3.6, 2.6, 3.8]],
    ["b", "사후 개선 표시:", "수정 판(Winnow-E4B 입력에 고객 일정 목록)은 시험 세트에서 44문제(20문제마다 하나)를 본 뒤 만든 것이다. 깨끗한 사전 등록 결과는 472/769(61.4%)이고, 697 은 낙관 쪽으로 치우쳤을 수 있다.", 0],
    ["b", "선택 기준 문구:", "Winnow-E4B 에 준 선택 기준 문구는 한 가지만 썼다. 이름 없는 설명을 「일정 질문」으로 보게 고치면 달라질 수 있으나, 시험 세트로 문구를 고르지 않으려고 멈췄다.", 0],
    ["b", "시험한 범위:", "고를 전문가가 사실상 가르친 E4B 하나다. 그래서 「Jev 계열 모델이 상황마다 다른 전문 sLLM 을 고른다」는 구상 전체는 시험하지 않았고, "
                        "이 시험이 보인 것은 「고를 곳이 하나인데도 학습 없는 Jev 계열 모델의 선택이 비용을 만든다」까지다. 감정 · 긴급도 같은 분야별 전문가와 응답 문장 생성 단계는 구현하지 않았다.", 0],
    ["b", "출제자와 반복:", "변형마다 1회(출력은 결정적)다. 가르친 E4B 와 mix12 · 학습 자료의 작성자가 같다(Claude). 요청 둘 66문제는 한 항목만 내는 구조라 A · B 만 냈고 C 는 구조상 0 이다.", 0],
    ["b", "모델 기록:", "가르친 E4B 는 Q8 GGUF(SHA-256 ec8928dd 로 시작, GPU 서버 B 원본과 같음), 보낼 곳 판정은 Winnow-E4B Q8 을 학습 없이 썼다. "
                      "ML 판별기는 multilingual-e5-base(에폭 20, 시드 0 하나). 단독 748 은 GGUF · 빈 응답 엄격 기준이라 3절의 HF 4비트 750 과 평가 틀이 다르다.", 0],
    ["__CHAIN_CODE__"],
    ["note", "연구용 코드다. 입력은 문제 하나와 변형 설정(fl: 규칙 · ML · Winnow-E4B 단계를 켜고 끄기)이며, 출력은 고른 항목과 단계별 경로 · 호출 수 · 시간 · 실패 사유를 담은 추적 기록이다. "
             "ML 이 「범위 밖」 확률 문턱을 넘으면 닫고, 아니면 Winnow-E4B 가 보낼 곳을 고르며, 「짚기」면 가르친 E4B 를 부른다. 코드 안 이름 jev 는 Jev 계열 모델 단계를 뜻한다."],
    ["note", "__CHAIN_SRC__"],
    ["h", "가르친 Jev 계열 모델(가르친 Winnow-E4B)로 다시 잰 공정한 비교"],
    ["p", "결론: Winnow-E4B 를 가르친 E4B 와 같은 방법으로 가르치면(가르친 Winnow-E4B, Jev 계열 모델에 우리 데이터로 QLoRA 학습) 혼자서 756/769(98.3%)로 가장 높았다. "
          "다만 가르친 E4B(750)와 짝지어 비교하면 10 : 4, p=0.18 로 구분되지 않는다. 두 가르친 모델을 규칙 · ML 뒤에 두거나 서로 넘겨주는 구조는 747~752 로, 단독보다 나은 구성은 없었다."],
    ["t", ["같은 방법으로 가르친 모델(HF 4비트 + 어댑터)", "가르치기 전 /769", "가르친 뒤 /769", "C 전체/835", "요청 둘 A · B · C /66", "가르친 E4B 와(이쪽만 : E4B만)", "건당(초)"],
     [[r[0], r[1], r[2], cfull(k), f"{CS[k]['A66']} · {CS[k]['B66']} · {CS[k]['C66']}", r[3], r[4]]
      for r, k in zip(FAIR_MODELS, ["가르친 Winnow-E4B(Jev 계열)", "가르친 E4B", "가르친 Gemma 4 E2B", "가르친 Kanana-2-3B"])],
     [3.0, 1.8, 1.4, 1.5, 1.3, 1.7, 0.8]],
    ["p", "가르치기 전에는 Winnow-E4B 가 E4B 보다 낮았다(85.2% 대 89.5%). Jev 계열 원본은 우리 질의 형식을 그대로 따라오지 못하고, 우리 자료로 가르쳐야 같은 수준이 된다. "
          "유형별로는 이름 없는 설명 70/75 대 63/75, 서수 · 상대 위치 77/80 대 75/80 으로 가르친 Winnow-E4B 가 앞서고 나머지는 같거나 1개 낮다."],
    ["t", ["구성(규칙 · ML 은 실제 호출, 전문가 단계는 저장 결과)", "정답/769", "C 전체/835", "요청 둘 A · B /66", "단독 가르친 E4B 대비(이쪽만 : 단독만)"],
     [[r[0], f"{r[1]} ({r[1] / 769 * 100:.1f}%)", f"{r[1]} ({r[1] / 835 * 100:.1f}%)", f"{CS[ck]['A66']} · {CS[ck]['B66']}", r[2]]
      for r, ck in zip(FAIR_STRUCT, [k for k in CS if k.startswith("구조: ")])], [4.4, 1.5, 1.5, 1.2, 2.2]],
    ["p", "C 로 보면: 위 구성은 모두 한 항목만 내므로 요청 둘의 C 가 0 이고 C 전체는 83.5~90.5% 다. 요청 둘을 알아보는 규칙(질문 속 이름 조각이 항목 둘 이상에 걸리면)으로 "
          "그 질문만 「둘 다 찾기」 모델에 넘기면 C 가 오른다. 가르친 Winnow-E4B(Jev 계열)를 바탕으로 하면 가르친 E4B 를 바탕으로 할 때보다 C 전체가 6개씩 높다."],
    ["t", ["이어 붙이기(요청 둘로 보인 질문만 「둘 다 찾기」 모델에게)", "C 전체/835", "요청 둘 C /66", "요청 둘 제외 /769", "공정성"], [
        [k.replace("이어 붙이기: ", ""), cfull(k), f"{CS[k]['C66']}", f"{CS[k]['non769']}",
         "Claude 가 정답 집합 · mix12 를 만들어 출제자 편향(공정 비교 아님)" if "Claude" in k else "Gemma 12B 는 소형 예산 밖(12B)"]
        for k in CS if k.startswith("이어 붙이기: ")], [4.6, 1.5, 1.1, 1.3, 2.5]],
    ["note", "같은 계산이 원 기록(results/c_scoring_all.txt §5)의 가르친 E4B 794 · 797 · 770 을 그대로 다시 낸다. 가르친 Winnow-E4B 쪽 셋은 이번에 같은 규칙으로 새로 계산했다(새 호출 없음). "
             "요청 둘을 알아보는 규칙은 요청 둘 51/66 을 잡지만 요청 둘이 아닌 224/769 도 넘긴다(정밀도 0.19)."],
    ["img", "__FAIR_FIG__", "그림 8. 가르친 E4B 와 가르친 Winnow-E4B(Jev 계열)로 짠 구성들의 정답률(769문제, 2026-10-06). 가로축은 96.5%부터라 차이가 커 보이지만 모두 통계적으로 구분되지 않는다."],
    ["b", "읽는 법:", "규칙 · ML 을 거치지 않고 두 가르친 모델 중 하나라도 맞히는 문제는 760/769 다. 규칙 · ML 판별기를 앞에 붙이면 두 전문가 모두 3~4개 낮아진다(750 → 747, 756 → 752). 앞단은 호출을 줄이지만 점수는 올리지 못한다(규칙 · ML 이 닫은 문제 158/769). "
                    "넘겨주기 · 유형별 · 라우터 구성(750~752)은 서로도, 단독과도 구분되지 않는다.", 0],
    ["b", "한계:", "각 1회(시드 하나)다. 이 구조 시험의 전문가 단계는 GPU 서버 B 의 저장 결과이고, 가르친 Winnow-E4B 를 GPU 서버 C 에서 실제로 불러 한 줄로 잇지는 않았다. "
                 "가르친 Winnow-E4B 의 바탕은 GGUF 로만 공개돼 safetensors 로 되돌려 학습했다. 넘겨주는 구조의 분야별 전문가(감정 · 긴급도)는 시험하지 않았다.", 0],
    ["b", "Winnow-E4B 를 고른 이유:", "「오늘 가장 좋은 Jev 계열 sLLM 이라서」가 아니다. JevBench 오늘 판에는 Winnow-E4B 가 없고, 학습 없는 우리 시험에서는 4B 급 Jev 계열 가운데 가장 낮았다(70.9%). "
                                 "사용자가 「winnow e4b 도 파인튜닝」을 요청했고, 가르친 E4B 와 같은 Gemma-4-E4B 바탕이라 같은 조건에서 비교할 수 있어서 골랐다. "
                                 "JevBench 4B 급 상위(Plumb-4B · spark-s1-4b-v6)와 같은 E4B 바탕의 jevify-gemma4-e4b 를 같은 방법으로 가르치는 비교는 진행 중이다.", 0],
    ["note", "출처: 정본 §92 맨 앞 안내 · §92-6, 원본 results/_pull/distill_eval/ · chain_experts_offline.py. 문턱 · 유형별 전문가 · 라우터는 한 세트를 빼고 고른 값(leave-one-set-out)이다."],
]


def add_chain(secs):
    import copy as _copy
    sec = _copy.deepcopy(CHAIN_SEC)
    for i, x in enumerate(sec):
        if x[0] == "img" and x[1] == "__CHAIN_FIG__":
            x[1] = fig_chain()
        if x[0] == "img" and x[1] == "__FAIR_FIG__":
            x[1] = fig_fair()
        if x == ["__CHAIN_CODE__"]:
            sec[i] = chain_code()
        if x[0] == "note" and x[1] == "__CHAIN_SRC__":
            x[1] = CHAIN_SRC
    s1, s3, s4, s5 = secs[0], secs[2], secs[3], secs[4]
    # 1.1 첫 문단
    for x in s1:
        if x[0] == "p" and "끝까지 연결한 제품 성능은 아직 검증되지 않았다" in x[1]:
            x[1] = x[1].replace("다만 규칙·ML·Jev·전문가 모델을 끝까지 연결한 제품 성능은 아직 검증되지 않았다.",
                                "규칙 → ML → Jev 계열 모델 → 전문가를 한 줄로 이은 시험은 2026-10-06 연구 환경에서 했다(4.4절). 제품에 연결한 것은 아니다.")
    # 1.3 단계표
    for x in s1:
        if x[0] == "t" and x[1][:1] == ["단계"]:
            for r in x[2]:
                if r[0].startswith("3. Jev"):
                    r[0] = "3. Jev 계열 모델 분류"
                    r[1] = ("Winnow-E4B(Jev 계열 LLM형, 학습 없음, 한국어 설명): 의도 94.5% · 감정 91.0% · 긴급도 63.5% · 대상 92.1%. "
                            "한 줄 시험의 보낼 곳 선택 488/626 = 78.0%")
                    r[2] = "2026-10-06 각 1회. 인코더형 Jev 계열(Laya · OpenDecider-nano)은 한 라벨만 찍는 값 수준이라 쓰지 않는다"
                if r[0].startswith("5."):
                    r[1] = r[1] + ". 가르친 Winnow-E4B(Jev 계열) 756/769 = 98.3%"
    # 1.3 판정 문단
    for x in s1:
        if x[0] == "p" and x[1].startswith("현재 확보된 근거로는"):
            x[1] = ("2026-10-06 에 네 단계를 한 줄로 이어 문제마다 실제로 불러 보았다(4.4절). 학습 없는 Winnow-E4B(Jev 계열)를 보낼 곳 판정에 넣은 한 줄 연결은 "
                    "가르친 E4B 하나보다 낮았다(697 대 748, 사전 등록 판은 472). 다만 전문가는 가르친 모델, 보낼 곳 판정은 학습 없는 원본이라 공정한 비교가 아니었다. "
                    "같은 방법으로 가르친 Winnow-E4B(Jev 계열)는 혼자 756/769 로 가장 높았고, 가르친 E4B 와 함께 짠 구조들(747~752)은 단독과 구분되지 않았다. "
                    "Jev 계열 모델이 상황마다 다른 전문 sLLM 을 고르고 응답 문장까지 만드는 구성 전체는 아직 구현 · 시험하지 않았고, 가르친 모델들은 제품에 아직 연결하지 않았다. "
                    "판정: 구성요소 · 부분 조합 · 한 줄 연결 · 가르친 두 전문가의 구조 비교는 끝났고, 여러 분야 전문가를 고르는 전체 구성과 제품 통합은 남았다.")
    # 3.2: 769 표에 같은 방법으로 가르친 모델 셋
    for x in s3:
        if x[0] == "t" and x[1][:1] == ["모델·호출 방식"]:
            j = next(i for i, r in enumerate(x[2]) if r[0].startswith("E4B FT"))
            x[2][j + 1:j + 1] = [
                ["가르친 Winnow-E4B(Jev 계열), HF NF4+LoRA", "756/769, 98.31%", "유효 약 4B, 별도 LoRA", "같은 방법 · 같은 평가, 가르친 E4B 와 10 : 4 (p=0.18)"],
                ["가르친 Gemma 4 E2B, HF NF4+LoRA", "739/769, 96.10%", "유효 약 2B, 별도 LoRA", "같은 방법 · 같은 평가"],
                ["가르친 Kanana-2-3B, HF NF4+LoRA", "715/769, 92.98%", "3B, 별도 LoRA", "같은 방법 · 같은 평가"]]
    # 3.3 분류 표에 LLM형 Jev 계열 모델 두 줄
    for x in s3:
        if x[0] == "t" and x[1][:1] == ["모델"] and any("Laya" in r[0] for r in x[2]):
            j = max(i for i, r in enumerate(x[2]) if "OpenDecider-nano" in r[0])
            x[2][j + 1:j + 1] = [["Winnow-E4B 한국어 설명(Jev 계열 LLM형, 학습 없음)", "94.5%", "91.0%", "63.5%", "92.1%", "무학습 1회, GPU 서버 A, 253ms"],
                                 ["OpenDecider-small 한국어 설명(Jev 계열 LLM형, 학습 없음)", "89.9%", "92.1%", "65.2%", "88.9%", "무학습 1회, GPU 서버 A, 387ms"]]
    # 3.2 A · B · C 표에 같은 방법으로 가르친 모델 셋
    for x in s3:
        if x[0] == "t" and x[1][:1] == ["출력 방식·모델"]:
            j = next(i for i, r in enumerate(x[2]) if "FT E4B" in r[0])
            add = []
            for k, lab in (("가르친 Winnow-E4B(Jev 계열)", "단일 출력 가르친 Winnow-E4B(Jev 계열)"), ("가르친 Gemma 4 E2B", "단일 출력 가르친 E2B"), ("가르친 Kanana-2-3B", "단일 출력 가르친 Kanana-2-3B")):
                v = CS[k]
                add.append([lab, f"{v['A66']}/66", f"{v['B66']}/66", f"{v['C66']}/66", f"{v['C_all']}/835"])
            x[2][j + 1:j + 1] = add
    # 1.1 채점 방식 개편 경위
    for x in s1:
        if x[0] == "p" and "A·B·C는 별도 시험 세트가 아니라" in x[1]:
            x[1] += (" 채점 방식은 2026-10-05 에 한 번 바꿨다. 처음에는 A 하나로 채점했는데, 「먼저 말한 항목」은 모델 실력이 아니라 우리가 정한 라벨 규칙이라 "
                     "두 항목을 다 알아본 모델도 틀리게 된다는 것이 드러났다(정본 §66-2 · §66-3). 그래서 주 채점을 B 로 바꾸고, 가장 엄격한 C(말한 항목을 모두 정확히 찾아야 정답)를 "
                     "미리 등록해 함께 기록한다(정본 §67). 한 항목만 내는 모델은 C 에서 요청 둘 66문제를 모두 놓치므로 C 전체는 요청 둘 제외 정답 수 / 835 가 된다.")
    # 3.3 진행 중 → 결과
    for x in s3:
        if x[0] == "b" and str(x[1]).startswith("진행 중"):
            x[:] = ["b", "같은 방법으로 가르친 다른 모델:", "가르친 Winnow-E4B(Jev 계열) 756 · 가르친 E2B 739 · 가르친 Kanana-2-3B 715 (769문제, 4.4절 끝). "
                    "JevBench 4B 급 상위 Jev 계열 모델(Plumb-4B · spark-s1-4b-v6)과 jevify-gemma4-e4b 를 같은 방법으로 가르치는 비교는 진행 중이라 결과로 쓰지 않는다. OpenDecider-small 의 항목 짚기 성능은 미측정이다.", 0]
    # 4절: 예외 절 앞에 넣고 번호를 민다
    k = next(i for i, x in enumerate(s4) if x[0] == "h" and x[1].startswith("4.4 예외"))
    s4[k:k] = sec
    s4[k + len(sec)][1] = s4[k + len(sec)][1].replace("4.4", "4.5", 1)
    # 5.1 성능 표 · 판정 문단
    for x in s5:
        if x[0] == "t" and x[1][:1] == ["성능 평가"]:
            for r in x[2]:
                if r[0].startswith("전체 기능 전문가 구성"):
                    r[:] = ["한 줄 연결(규칙 → ML → Winnow-E4B(Jev 계열, 학습 없음) → 가르친 E4B)", "697/769 (사전 등록 판 472) 대 단독 748, p=4e-13",
                            "2026-10-06 1회. 학습 조건이 달라 공정한 비교 아님 · 수정 판은 사후 개선"]
            x[2] += [["규칙 → ML 거름 → 가르친 E4B", "745/769, 단독과 3 : 6 (p=0.51), 가르친 E4B 호출 19% 감소", "2026-10-06 1회. 연구 환경, 제품 미연결"],
                     ["가르친 Winnow-E4B(Jev 계열) 단독", "756/769, 가르친 E4B 750 과 10 : 4 (p=0.18)", "2026-10-06 1회, 같은 방법 · 같은 평가"],
                     ["두 가르친 모델로 짠 구조(인계 · 유형별 · 라우터)", "747~752/769, 단독과 구분 안 됨", "전문가 단계는 저장 결과, 실제 한 줄 호출은 아직"],
                     ["C 채점(835, 요청 둘은 모두 찾아야 정답)", f"가르친 Winnow-E4B {CS['가르친 Winnow-E4B(Jev 계열)']['C_all']} · 가르친 E4B {CS['가르친 E4B']['C_all']} (요청 둘 C 0/66). "
                      f"요청 둘만 「둘 다 찾기」 모델에 넘기면 가르친 Winnow-E4B + Gemma 12B {CS['이어 붙이기: 가르친 Winnow-E4B(Jev 계열) + Gemma 12B 둘 다 찾기']['C_all']}",
                      "저장 결과 재채점. Claude 와 이으면 800~803 이지만 출제자 편향"]]
        if x[0] == "p" and x[1].startswith("제출 판정은"):
            x[1] = ("제출 판정은 구성요소 · 부분 조합 · 한 줄 연결 · 가르친 두 전문가의 구조 비교 완료, 여러 분야 전문가를 고르는 전체 구성과 제품 통합은 미완료다. "
                    "학습 없는 Jev 계열 모델을 보낼 곳 판정에 넣으면 손해였고, 같은 방법으로 가르친 Winnow-E4B(Jev 계열)는 단독으로 가르친 E4B 와 같은 수준이었다. "
                    "FT E4B 의 높은 합성 시험 점수로 현재 제품의 잘못된 대상 변경 결함이나 RAG 연결 실패가 해결됐다고 판단하지 않는다.")
    for x in s5:
        if x[0] == "b" and str(x[1]).startswith("1. 전체 구성:"):
            x[1] = ("1. 전체 구성: 한 줄 연결은 2026-10-06 에 했다(4.4절). 남은 것은 가르친 Winnow-E4B(Jev 계열)를 실제로 불러 한 줄로 잇는 시험, 감정 · 긴급도 같은 다른 전문가를 두고 "
                    "Jev 계열 모델이 고르는 시험, 응답 문장 생성 단계, 선택 기준 문구를 개발 세트로 고른 뒤 새 시험 세트로 다시 재는 것이다.")
        if x[0] == "b" and str(x[1]).startswith("3. 전문가 선택:"):
            x[1] = ("3. 전문가 선택: 학습 없는 Winnow-E4B(Jev 계열)의 보낼 곳 선택 정확도는 488/626 = 78.0% 로 쟀다(4.4절). 전문가가 둘 이상일 때의 선택 정확도 · 잘못 보낸 비율은 아직이다.")
    last = max(k for k, x in enumerate(s5) if x[0] == "b" and str(x[1])[:2] in ("6.", "7."))
    s5.insert(last + 1, ["b", "8. 가르친 Jev 계열 모델 후보 비교:", "Plumb-4B · spark-s1-4b-v6 · jevify-gemma4-e4b 를 같은 방법으로 가르쳐 가르친 Winnow-E4B(756)와 비교한다(GPU 서버 B 대기열, 진행 중).", 0])
    return secs


# ---------- Jev API(유료) 와 Jev 계열 모델을 가른다 (2026-10-06 사용자 지시) ----------
import re as _re

JEV_DEF = ["b", "Jev 계열 모델과 Jev API(유료):", "Jev 계열 모델은 정해진 선택지 중 하나를 고르는 공개 소형 결정 모델들이다(Laya · OpenDecider · Winnow-E4B · OpenJev 26B 등). "
           "Jev API(유료)는 같은 방식의 유료 API 결정 모델(1.13.0 판, JevBench v1.5.6 3위)이다. 이 보고서의 단계 구성(3단계 분류)과 한 줄 시험에는 Jev 계열 모델 가운데 "
           "Winnow-E4B(학습 없는 원본)를 썼고, 같은 방법으로 가르친 판은 「가르친 Winnow-E4B(Jev 계열)」라고 쓴다. Jev API(유료)는 종량 과금이라 사용자가 지시했을 때만 따로 시험했다(3.2절 「Jev API(유료) 시험 결과」).", 0]

JEV_SEC = [
    ["p", "Jev API(유료)는 종량 과금이라 사용자 지시가 있을 때만 mix8 · mix9 에서 불렀다(2026-10-03). 769문제 전체(mix10~12)로는 부르지 않아 위 769 표에는 없다. "
          "같은 문제로 맞춰 보면 Jev API(유료)와 가르친 E4B 는 구분되지 않는다."],
    ["t", ["방식", "문제", "정답", "엉뚱한 답", "질문당", "읽는 법"], [
        ["Jev API(유료) 직접 짚기", "mix8+mix9, 요청 둘 제외 309", "298 (96.4%)", "6", "0.23초", "2026-10-03 호출"],
        ["가르친 E4B(HF 4비트)", "같은 309", "302 (97.7%)", "7", "", "Jev API(유료)와 짝비교 5 : 9, p=0.42 (구분 안 됨)"],
        ["E4B 가르치기 전(HF 4비트)", "같은 309", "280 (90.6%)", "", "", "참고"],
        ["Jev API(유료) 직접 짚기", "mix8+mix9 전체 336(요청 둘은 A 채점)", "319 (94.9%)", "11", "0.23초", "이 336 에서 이를 넘은 로컬 모델은 OpenJev 26B 직접 327 하나(p=0.077)"],
        ["J1 규칙 → 앞단 → Jev API(유료) 확신 0.5 이상이면 그 답, 아니면 E4B QAT", "같은 336", "319 (94.9%)", "13", "", "직접 짚기와 같음. Jev API(유료) 256회 + E4B 43회 호출"],
        ["Gemma 26B 직접 · L6 규칙 → 게이트 → E4B QAT", "같은 336", "311 · 316", "", "", "참고(로컬)"]],
     [3.6, 2.6, 1.5, 1.1, 0.9, 3.3]],
    ["p", "앞선 시험(2026-09-30): 순서 · 상대 위치 질문에서 Jev API(유료) 직접 짚기는 40%(19/48) · 33%(14/42)로 약했다(공식 문서가 경고한 「날짜 · 상대 표현」 약점과 같다). "
          "규칙이 자리표를 읽고 Jev API(유료)는 기준 항목만 고르게 하면 46/48 · 42/42 가 됐다(질문 · 규칙 작성자가 같아 낙관적)."],
    ["note", "출처: 정본 §17 · §47 · §51 · §54-1~2, results/jev_out_mix8.json · jev_out_mix9.json, 같은 문제 비교 계산 src/jev_vs_ft_309.py(새 호출 없음, 결과 _재료/jev_vs_ft_309.json). "
             "Jev API(유료)의 답은 확률이 가장 큰 선택지로 봤다. 비용은 입력 100만 토큰당 0.042달러(출력 무료), 지금까지 약 2,255건 호출에 0.23달러 안팎 `추정`, 예산은 총 5달러다. "
             "Jev API(유료)는 Codex 가 쓴 시험 문장만 받았고, 가르친 E4B 의 학습 자료는 Claude 가 썼다."],
]

_JEV = _re.compile(r"(?<![A-Za-z(])Jev(?![A-Za-z\-]| 계열| API|Bench)")
_PART = _re.compile(r"Jev 계열 모델 ?(를|을|가|이|는|은|와|과|의|에|로)(?=[\s,.·」)]|$)")
_FIX = {"를": "을", "을": "을", "가": "이", "이": "이", "는": "은", "은": "은", "와": "과", "과": "과", "의": "의", "에": "에", "로": "로"}


def _jev_text(t):
    t = t.replace("V9에는 Jev가 없다", "V9에는 Jev API(유료)가 없다")
    t = _JEV.sub("Jev 계열 모델", t)
    t = _PART.sub(lambda m: "Jev 계열 모델" + _FIX[m.group(1)], t)
    return t.replace("Jev 계열 모델 계열", "Jev 계열")


def fix_jev(secs):
    def walk(x):
        if isinstance(x, str):
            return _jev_text(x)
        if isinstance(x, list):
            if x and x[0] in ("code", "img"):
                return x
            return [walk(v) for v in x]
        return x
    secs = walk(secs)
    s1, s3 = secs[0], secs[2]
    i = next(k for k, x in enumerate(s1) if x[0] == "h" and x[1].startswith("1.3"))
    s1.insert(i + 1, JEV_DEF)
    k = next(k for k, x in enumerate(s3) if x[0] == "t" and x[1][:1] == ["FT E4B와의 짝비교"])
    k = next(j for j in range(k + 1, len(s3)) if s3[j][0] == "note")
    s3[k + 1:k + 1] = [["h", "Jev API(유료) 시험 결과"]] + JEV_SEC
    for x in secs[4]:
        if x[0] == "t" and x[1][:1] == ["성능 평가"]:
            x[2].append(["Jev API(유료) 직접 짚기", "309문제에서 298 대 가르친 E4B 302 (p=0.42)", "2026-10-03 호출, mix8+mix9 만. 769 전체는 안 함"])
    return secs


def assert_no_bare_jev(path):
    import docx
    d = docx.Document(str(path))
    from docx.oxml.ns import qn as _qn
    bad = []
    for el in d.element.body.iterchildren():
        t = "".join(x.text or "" for x in el.iter(_qn("w:t")))
        for m in _JEV.finditer(t):
            bad.append(t[max(0, m.start() - 30):m.end() + 30])
    if bad:
        raise ValueError("「Jev」만 쓴 곳이 남았다: " + " | ".join(bad[:5]))



# ---------- 사람(사용자)이 직접 한 일 기록 (2026-10-06 사용자 진술) ----------
HUMAN = [
    ("AI 작성 합성 문장", "AI 작성 합성 문장 · 사용자가 일부 직접 검수"),
    ("mix8~11은 Codex 작성, mix12와 정답 집합은 Claude 작성이다.",
     "mix8~11은 Codex 작성, mix12와 정답 집합은 Claude 작성이다. 다만 작업 도중 사용자가 Claude 에게 문제 · 정답을 보여 달라고 해 일부를 직접 검수했다."),
    ("Claude가 여행자 10명의 일정과 연습문제 1,760개를 만들었다.",
     "증류의 바탕이 된 처음 문제와 체크리스트는 사용자(사람)가 직접 작성 · 제공했고, 그 처음 자료의 수치는 사용자가 모두 검수했다. 그것을 바탕으로 Claude가 여행자 10명의 일정과 연습문제 1,760개를 만들었고, 작업 도중 사용자가 Claude 에게 문제 · 정답을 받아 일부를 직접 검수했다."),
    ("별도 풀이도 같은 Claude 계열이므로 사람이 검수한 정답 확정으로 표현하지 않는다.",
     "별도 풀이도 같은 Claude 계열이다."
     ""),
]


def add_human(secs):
    def walk(x):
        if isinstance(x, str):
            for a, b in HUMAN:
                x = x.replace(a, b)
            return x
        if isinstance(x, list):
            if x and x[0] in ("code", "img"):
                return x
            return [walk(v) for v in x]
        return x
    return walk(secs)



# ---------- 서비스 평가 베이스라인과 개선 전후 (RAG 세션 리포트, 2026-10-06) ----------
SVC_SRC = ("출처: final_project_cs/wiki/records/reports/2026-10-06_서비스_평가_베이스라인과_개선_전후.md §3 · §5 · §6 · §8 (RAG 세션 측정, 2026-10-06). "
           "질문 · 시험 자료는 모두 모델이 쓴 합성이다(Codex · Claude). 사람이 쓴 문장은 일상 대화 · 구어체 · 여행 대화 발화(AI Hub · KoCulture · KLUE-WoS)뿐이고 정답 라벨이 없다. "
           "사람 평가 점수는 0건이다(평가 시트 35행만 준비).")
MIX_SEC = [
    ["h", "4.5 실전처럼 섞은 흐름 2,735문제 (일정과 무관한 말이 섞일 때)"],
    ["p", "결론: 일정 질문 769(+요청 둘 66)에 관광지 질문 틀 600 · 일상 대화 1,000 · 구어체 300 을 섞어 문제마다 실제로 불렀다. 이렇게 일정과 무관한 말이 많이 섞이면 "
          "규칙 → ML 판별기 앞단이 이득이었다(정답 2,424 → 2,453/2,669, 37 : 8, p = 1.5e-5). 가르친 E4B 하나만 쓰면 일정과 무관한 말에 항목을 짚는 비율이 4.5% 다. 합성 시험 기준 점수다."],
    ["t", ["구조", "요청 둘 제외 정답 /2,669", "「없음」이 정답인데 항목을 짚음 /1,786", "정답 항목이 있는 질문 /883", "전문가 호출", "지연 중앙 / p95"], [
        ["가르친 E4B 단독", "2,424 = 90.8%", "80 = 4.5%", "786 = 89.0%", "2,735", "164 / 205ms"],
        ["규칙 → 가르친 E4B", "2,419 = 90.6%", "83 = 4.6%", "784 = 88.8%", "2,608", "163 / 206ms"],
        ["규칙 → ML 판별기 → 가르친 E4B", "2,453 = 91.9%", "58 = 3.2%", "784 = 88.8%", "2,117", "189 / 241ms"],
        ["규칙 → ML → Winnow-E4B(Jev 계열, 학습 없음) → 가르친 E4B", "2,385 = 89.4%", "9 = 0.5%", "639 = 72.4%", "768", "506 / 746ms"]],
     [3.4, 1.6, 1.8, 1.5, 1.0, 1.4]],
    ["b", "빈 답:", "2,735문제 중 85건(3.1%)이 빈 답이었고 두 번 돌려도 같은 85건이 나왔다. 원인은 확인하지 못했다. 그중 68건은 정답이 「없음」이라, 빈 답을 「해당 없음」으로 처리하면 90.8% → 93.4% 가 된다(같은 시험에서 정한 사후 계산이라 다른 자료로 확인해야 한다).", 0],
    ["b", "학습 없는 Winnow-E4B(Jev 계열):", "새어 나감은 0.5% 로 가장 낮지만 있는 일정 항목을 「없음」으로 닫는 일이 늘어 전체는 단독보다 낮다(114 : 153, p = 0.02). 학습 조건이 달라 공정한 비교가 아니다.", 0],
    ["b", "일정 안 장소 질문 71.3%:", "틀린 66건 중 59건은 같은 장소의 다른 일정 항목을 고른 것이다(장소가 일정에 두 번 이상 나오는 질문 132/300). 장소가 한 번만 나오는 질문은 159/168 = 94.6%.", 0],
    ["note", SVC_SRC + " 3-2 표는 GPU 서버 C 에서 변형당 1회, 섞는 순서 seed 20261006."],
]
HALL_SEC = [
    ["h", "환각 방지 · 근거 정확성 체크리스트 (2026-10-06)"],
    ["t", ["항목", "목표", "현재 값"], [
        ["규정 문장 인용 정확도(출처 문장과 글자 그대로 일치)", "100%", "334/334"],
        ["답 없는 질문에 규정을 보임(새어 나감)", "0", "3/110 = 2.7%"],
        ["알림 번역의 시각 · 금액 숫자 변조가 통과", "0", "0/115 (120호출)"],
        ["알림 번역의 금액 단위 변조가 통과", "0", "1건(일본어 원 → 엔)"],
        ["일정 항목 짚기에서 후보 목록 밖 번호", "0", "0/835 · 섞은 흐름 0/2,735"],
        ["일정과 무관한 말에 항목을 짚음", "0", "80/1,786 = 4.5% (ML 앞단 3.2%)"],
        ["계획 읽기: 원문에 없는 제목 · 예약번호를 뽑음(값 변조)", "0", "12/350 = 3.4%"],
        ["계획 읽기: 근거가 빈 값", "0", "0/1,828"],
        ["결정 단위: 엉뚱한 대상을 바꿈", "0", "1/172"],
        ["보기 밖 값 반영(일정 변경 초안)", "0", "측정하지 못함(초안을 만드는 모델 호출이 필요한 경로)"]], [5.2, 1.0, 3.8]],
    ["t", ["에이전트 과제", "값", "조건"], [
        ["결정 단위 재생(채팅 한 마디 → 할 일 + 대상)", "167/172 = 97.1%, 지연 p95 2.5~4.6초", "정답은 Claude 표기(사람 검수 아님), 2026-09-30 실행"],
        ["계획 읽기(일정 파일 · 사진 · PDF → 항목)", "항목 재현율 326/336 = 97.0% · 시각 321/321 · 값 변조 3.4%", "합성 60건 x 6형식, 2026-09-28, gemma4:12b"],
        ["사람 평가", "0건", "평가 시트 35행 · 기준 5개만 준비"]], [3.4, 3.6, 3.0]],
    ["note", SVC_SRC],
]


def add_svc(secs):
    s4, s5 = secs[3], secs[4]
    k = next(i for i, x in enumerate(s4) if x[0] == "h" and x[1].startswith("4.5 예외"))
    s4[k:k] = MIX_SEC
    s4[k + len(MIX_SEC)][1] = s4[k + len(MIX_SEC)][1].replace("4.5", "4.6", 1)
    j = next(i for i, x in enumerate(s5) if x[0] == "h" and x[1].startswith("5.2"))
    s5[j:j] = HALL_SEC
    for x in s5:
        if x[0] == "t" and x[1][:2] == ["구분", "테스트 수"]:
            x[2].insert(0, ["cs 프로젝트 전체 자동 시험(최신)", "4,251", "4,245", "6", "4,245/4,251, 99.9%",
                            "2026-10-06 18:09, 실제 모델 시험 238개 제외. 실패 · 오류 6건 중 5건은 로컬 환경 파일의 모르는 키 이름 때문"])
        if x[0] == "t" and x[1][:1] == ["이슈"]:
            x[2] += [["일정 항목 짚기 빈 답(85/2,735 = 3.1%)", "원인 미확인(같은 85건이 결정적으로 재현)", "빈 답을 「해당 없음」으로 처리하는 정책 제안", "미해결"],
                     ["알림 번역 금액 단위 변조 통과(일본어 원 → 엔 1건)", "보호 장치가 숫자만 대조하고 단위는 안 봄", "통화 단위 대조 추가 제안(가상 적용 시 1건 걸림, 오탐 0)", "미해결"]]
    return secs



# ---------- 시드 정정 (RAG 세션 §92-9, 2026-10-06): 가르친 E4B 시드 2 = 760 ----------
SEED_TXT = [
    ("같은 방법으로 가르친 Winnow-E4B(Jev 계열)는 혼자 756/769 로 가장 높았고, ",
     "같은 방법으로 가르친 Winnow-E4B(Jev 계열, 시드 1개)는 756/769 로, 시드만 바꿔 두 번 가르친 E4B(750 · 760)와 구분되지 않았고, "),
    ("혼자서 756/769(98.3%)로 가장 높았다. 다만 가르친 E4B(750)와 짝지어 비교하면 10 : 4, p=0.18 로 구분되지 않는다.",
     "756/769(98.3%, 시드 1개)였다. 가르친 E4B 는 시드만 바꿔 두 번 가르쳐 750 · 760 이 나왔고 그 차이도 통계적으로 구분된다(13 : 3, p=0.021). "
     "가르친 Winnow-E4B 는 그 둘 어느 쪽과도 구분되지 않는다(시드 1 과 10 : 4, p=0.18 · 시드 2 와 4 : 8, p=0.39). 학습 한 번의 차이가 모델 사이 차이만큼 커서, 모델 사이 순위는 시드 3개 이상이 필요하다."),
    ("가르친 Winnow-E4B(Jev 계열) 756 · 가르친 E2B 739 · 가르친 Kanana-2-3B 715 (769문제, 4.4절 끝).",
     "가르친 Winnow-E4B(Jev 계열) 756 · 가르친 E2B 739 · 가르친 Kanana-2-3B 715 (769문제, 시드 1개씩, 4.4절 끝). 가르친 E4B 는 시드 2개로 750 · 760 이다."),
    (". 가르친 Winnow-E4B(Jev 계열) 756/769 = 98.3%", ". 가르친 Winnow-E4B(Jev 계열) 756/769(시드 1개) · 가르친 E4B 시드 2 760/769"),
]


def add_seed(secs):
    def walk(x):
        if isinstance(x, str):
            for a, b in SEED_TXT:
                x = x.replace(a, b)
            return x
        if isinstance(x, list):
            if x and x[0] in ("code", "img"):
                return x
            return [walk(v) for v in x]
        return x
    secs = walk(secs)
    v = CS["가르친 E4B 시드 2"]
    for sec in secs:
        for x in sec:
            if x[0] != "t":
                continue
            h = x[1]
            if h[:1] == ["같은 방법으로 가르친 모델(HF 4비트 + 어댑터)"]:
                j = next(i for i, r in enumerate(x[2]) if r[0].startswith("가르친 E4B(Gemma 4 E4B)"))
                x[2][j][0] = "가르친 E4B(Gemma 4 E4B, 시드 1)"
                x[2].insert(j + 1, ["가르친 E4B(같은 방법, 시드 2)", "688 (89.5%)", "760 (98.8%)", f"{v['C_all']}/835 ({v['C_all'] / 835 * 100:.1f}%)",
                                    f"{v['A66']} · {v['B66']} · {v['C66']}", "시드 1 과 13 : 3 (p=0.021)", "1.58"])
                for r in x[2]:
                    if r[0].startswith("가르친 Winnow-E4B"):
                        r[5] = "시드 1 과 10 : 4 (p=0.18) · 시드 2 와 4 : 8 (p=0.39)"
            if h[:1] == ["모델·호출 방식"]:
                j = next(i for i, r in enumerate(x[2]) if r[0].startswith("E4B FT"))
                x[2].insert(j + 1, ["E4B FT 시드 2(같은 방법), HF NF4+LoRA", "760/769, 98.83%", "E4B 실효 약 4B, 별도 LoRA", "시드만 바꿈. 시드 1(750)과 13 : 3, p=0.021"])
            if h[:1] == ["출력 방식·모델"]:
                j = next(i for i, r in enumerate(x[2]) if "FT E4B" in r[0])
                x[2].insert(j + 1, ["단일 출력 FT E4B 시드 2", f"{v['A66']}/66", f"{v['B66']}/66", f"{v['C66']}/66", f"{v['C_all']}/835"])
            if h[:1] == ["성능 평가"]:
                for r in x[2]:
                    if r[0].startswith("가르친 Winnow-E4B(Jev 계열) 단독"):
                        r[1] = "756/769(시드 1개). 가르친 E4B 750 · 760(시드 2개)과 구분 안 됨"
                        r[2] = "2026-10-06, 같은 방법 · 같은 평가. 모델 사이 순위는 시드 3개 이상 필요"
                    if r[0].startswith("E4B 파인튜닝"):
                        r[1] = r[1] + " · 시드 2 는 760"
    # 3.2 본문에 시드 문장
    s3 = secs[2]
    for x in s3:
        if x[0] == "p" and x[1].startswith("동일 하네스에서 688/769에서 750/769로"):
            x[1] += (" 같은 방법으로 시드만 바꿔 한 번 더 가르치면 760/769(98.8%)가 나왔다(시드 1 과 13 : 3, p=0.021). "
                     "학습 한 번의 차이가 10문제(1.3%p)라, 학습 없는 기준선 대비 개선(688 → 750~760)은 확실하지만 가르친 모델끼리의 순위는 시드 3개 이상이 있어야 말할 수 있다.")
    return secs


# ---------- 5주차 되돌리기 (2026-10-06 사용자 결정 「C 안」, RAG 세션 전달) ----------
# RAG 세션 요청으로 넣었던 것(add_svc: 섞은 흐름 · 환각 방지 표 · 에이전트 과제 표 · 자동 시험 줄 · 결함 두 줄 /
# add_seed: 시드 2 = 760 표 3개 · 3.2 본문 · 5.1 표 · 769 그림 · 단계 그림)을 빼고, 「Winnow 가 가장 높다」 두 곳만 정정한다.
# 새 결과(시드 2 · 섞은 흐름 등)는 6주차 서비스 테스트 보고서에만 싣는다. 되돌리기 전 판: _backup/<시각>_RAG요청분_되돌리기전/
RAG_REVERT = True
WINNOW_FIX = [
    ("같은 방법으로 가르친 Winnow-E4B(Jev 계열)는 혼자 756/769 로 가장 높았고, ",
     "같은 방법으로 가르친 Winnow-E4B(Jev 계열, 시드 1개) 756 은 가르친 E4B 750(시드 1개)과 구분되지 않았고(모델 사이 순위는 시드 3개 이상 필요), "),
    ("혼자서 756/769(98.3%)로 가장 높았다. 다만 가르친 E4B(750)와 짝지어 비교하면 10 : 4, p=0.18 로 구분되지 않는다.",
     "756/769(98.3%, 시드 1개)였다. 가르친 E4B 750(시드 1개)과 짝지어 비교하면 10 : 4, p=0.18 로 구분되지 않으며, 모델 사이 순위는 시드 3개 이상이 필요하다."),
]
STAGES_FIX = ("가르친 E4B 750~760\\n(시드 차이 안이라 구분 안 됨)", "가르친 E4B 750\\n(구분 안 됨, 순위는 시드 3개 이상 필요)")


def fix_winnow(secs):
    hit = {a: 0 for a, _ in WINNOW_FIX}

    def walk(x):
        if isinstance(x, str):
            for a, b in WINNOW_FIX:
                if a in x:
                    hit[a] += 1
                    x = x.replace(a, b)
            return x
        if isinstance(x, list):
            if x and x[0] in ("code", "img"):
                return x
            return [walk(v) for v in x]
        return x
    secs = walk(secs)
    miss = [a for a, k in hit.items() if k == 0]
    if miss:
        raise ValueError(f"정정할 문장을 못 찾음: {miss}")
    return secs


def main():
    src = (HERE / "stages.dot").read_text(encoding="utf-8")
    if RAG_REVERT:
        assert STAGES_FIX[0] in src, "단계 그림 문구를 못 찾음"
        src = src.replace(*STAGES_FIX)
    src = TP.run_text(src)
    tmp = HERE / "_stages_build.dot"
    tmp.write_text(src, encoding="utf-8")
    dot(tmp, FIG / "단계구성_잰값.png")
    figs = {"stages": (str(FIG / "단계구성_잰값.png"),
                       "그림 1. 규칙 → ML → Jev 계열 분류 → 전문가 구성과 단계마다 잰 값(2026-10-06 한 줄 시험 포함). 붉은 메모는 한 줄 시험 결과와 아직 없는 것이다.", 13.0),
            "ft_before_after": (fig_ft(), "그림 3. 같은 평가 틀(HF 4비트)에서 가르치기 전후 정답 수. 학습 1회 · 평가 1회, 2026-10-06."),
            "rag_fixed": (fig_rag(), "그림 2. 독립 질문 48개에서 정답 근거를 보여 준 수."),
            "cpu_latency": (fig_cpu(), "그림 5. 가르친 E4B 를 CPU 로만 돌렸을 때 질문 하나에 걸린 시간."),
            "classifiers": (fig_cls(), "그림 6. 질문 분류 네 가지의 정확도. 학습한 작은 인코더와 학습 없는 모델의 조건이 달라 통제된 우열 비교는 아니다.")}
    secs = []
    for s in D["sections"]:
        b = fix(strip_dup(s))
        out = []
        for x in b:
            if x[0] == "fig":
                p, cap, *mh = figs[x[1]]
                out.append(["img", p, cap] + mh)
            else:
                out.append(x)
        secs.append(out)
    # 3절: 769 모델 비교 그림을 표 바로 뒤에
    s3 = secs[2]
    i = at(s3, "note", "상용 비교 각주")
    s3[i + 1:i + 1] = [["img", fig_769(), "그림 4. 같은 769문제에서 모델별 정답률. 빗금은 상용 서비스로, 실행 조건과 출제자가 달라 공정 비교가 아니다.", 12.0]] + fair_comm_blocks()
    # 4.2: 제품 코드(팀 재배분)
    s4 = secs[3]
    i = at(s4, "note", "제품용 항목 찾기 함수")
    s4[i + 1:i + 1] = list(reroute_code())
    secs = add_sh(secs)
    secs = add_chain(secs)
    secs = gloss_first(secs)
    secs = fix_jev(secs)
    secs = add_human(secs)
    if RAG_REVERT:
        secs = fix_winnow(secs)
    else:
        secs = add_svc(secs)
        secs = add_seed(secs)
    for blocks in secs:
        for x in blocks:
            if x[0] == "fig":
                raise ValueError(x)
    # 용어 정비(2026-10-06 사용자 지적 「너만 아는 단어 다 수정」): 실무 용어로 바꾸고 1절에 「용어 정의」 표
    secs, miss = TP.run_blocks(secs, "multi")
    print("용어 정비: 못 찾은 문장", len(miss))
    out = W.build(TEMPLATE, OUT, sections=secs, max_img_h_cm=9.0)
    assert_no_bare_jev(out)
    print("saved", out)


if __name__ == "__main__":
    main()
