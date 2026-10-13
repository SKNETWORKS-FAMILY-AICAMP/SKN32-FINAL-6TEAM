# -*- coding: utf-8 -*-
"""그림용 흐름을 사람이 고친 기록 — 코덱스가 줄인 흐름(../spec/*.md 「그림용 흐름」)에 Claude 검토로 고친 것을 덮어쓴다.

고친 까닭은 각 줄의 주석에 적었다. 다시 돌려도 같은 결과가 나온다(이미 고친 것은 건너뛴다).
"""
import re
from pathlib import Path

import yaml

from split_specs import flow_of

SPEC = Path(__file__).resolve().parent.parent / "spec"


def drop_edge(fl, a, b, note_node=None, note=None):
    before = len(fl["edges"])
    fl["edges"] = [e for e in fl["edges"] if not (e["from"] == a and e["to"] == b)]
    if note_node and len(fl["edges"]) < before:
        n = next(x for x in fl["nodes"] if x["id"] == note_node)
        lines = list(n.get("lines") or [])
        if note not in lines:
            n["lines"] = lines + [note]


def node(fl, nid):
    return next(x for x in fl["nodes"] if x["id"] == nid)


PATCHES = {
    # 「해석 불가」 선이 「필수 정보 없음」 선과 붙어 나란히 감 — 해석 실패는 낱말 규칙으로 넘어가므로(n3 둘째 줄) 선을 뺀다
    "A01": lambda fl: drop_edge(fl, "n3", "n7"),
    # 중복 요청은 이전 답을 그대로 돌려줄 뿐이라 갈래로 그리지 않고 접수 확인 줄에 적는다 · 규정 검색은 임베딩 검색이지 언어 모델 출력이 아니다
    "F05": lambda fl: (drop_edge(fl, "n2", "n10", "n2", "중복 요청은 이전 답 반환"),
                       node(fl, "n5").update(tag="공용 도구", title="규정 검색",
                                             lines=["질문을 임베딩해 조각 상위 3개", "검색 오류면 안내"])),
    # 저장 충돌은 검사 실패와 같은 거절로 끝난다 — 선 하나로 합친다
    "F08": lambda fl: drop_edge(fl, "n6", "n11", "n6", "판이 바뀌었으면 거절"),
    # 겹침 · 대상 없음은 기록만 하고 끝 — 접수 확인 줄로
    "F12": lambda fl: drop_edge(fl, "n3", "n10", "n2", "겹침·대상 없음은 기록만"),
    # 접수 거절은 오류 상자로 가는 두 번째 선이라 교차가 생긴다 — 줄로 옮긴다 · 시험 알림 발송은 우리 코드다
    "F13": lambda fl: (drop_edge(fl, "n2", "n10", "n2", "확인 실패면 거절 안내"),
                       node(fl, "n7").update(tag="코드")),
}


def main():
    for fid, fn in PATCHES.items():
        path = SPEC / f"{fid}.md"
        md = path.read_text(encoding="utf-8")
        fl = flow_of(md)
        fn(fl)
        body = yaml.safe_dump(fl, allow_unicode=True, sort_keys=False, default_flow_style=None, width=200)
        head, tail = md.split("### 그림용 흐름", 1)
        tail = re.sub(r"```yaml\n.*?```", "```yaml\n" + body.replace("\\", "\\\\") + "```", tail, count=1, flags=re.S)
        path.write_text(head + "### 그림용 흐름" + tail, encoding="utf-8")
        print(fid, "nodes", len(fl["nodes"]), "edges", len(fl["edges"]))


if __name__ == "__main__":
    main()
