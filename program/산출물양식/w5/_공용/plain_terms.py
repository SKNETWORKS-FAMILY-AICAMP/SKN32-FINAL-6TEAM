"""산출물 쉬운 말 · 실무 용어 정비 공용 도구 (2026-10-06).

사용자 지적: 「독립실험 A 가 뭔지 어떻게 알아? 설명 어디다 했냐? 없는 용어 가능한 쓰지 말고 실무 스타일 용어들 쓰고」.
빌더마다 마지막 단계에서 부른다 —
  1) rewrite(secs, pairs)   : 원문 조각을 고친 문장으로 그대로 바꾼다(못 찾은 조각은 목록으로 돌려준다)
  2) terms(secs, pairs)     : 우리끼리 만든 말을 실무 용어로 바꾸고, 뒤에 붙은 조사(은/는 · 이/가 · 을/를 · 과/와 · 으로/로)를 맞춘다
  3) strip_refs(secs)       : 읽는 사람이 열 수 없는 내부 참조(「정본 §66-2」 같은 것)를 본문에서 지운다
  4) glossary(rows)         : 문서 앞에 넣을 「용어 정의」 표 블록
블록 형식은 w5_docx.build 와 같다(h · p · b · t · img · code · note). 그림 · 코드 블록은 건드리지 않는다.
"""
from __future__ import annotations

import re

_SKIP = ("img", "code")
_JOSA = [("은", "는"), ("이", "가"), ("을", "를"), ("과", "와")]


def _coda(word: str):
    """마지막 글자에 받침이 있으면 True, 없으면 False, 모르면 None. 괄호로 끝나면 괄호 앞 글자를 본다."""
    w = word.rstrip()
    if w.endswith(")") and "(" in w:
        w = w[: w.rfind("(")].rstrip()
    if not w:
        return None
    ch = w[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():
        return ch in "013678"
    if ch.isalpha():
        return ch.lower() in "lmnr"
    return None


def _rieul(word: str) -> bool:
    w = word.rstrip()
    if w.endswith(")") and "(" in w:
        w = w[: w.rfind("(")].rstrip()
    ch = w[-1:] or " "
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 8


def _fix_josa(text: str, word: str) -> str:
    c = _coda(word)
    if c is None:
        return text
    esc = re.escape(word)
    end = r"(?=[\s,.)」』:;·]|$)"
    for a, b in _JOSA:
        want = a if c else b
        text = re.sub(esc + "(" + a + "|" + b + ")" + end, word + want, text)
    want = "로" if (not c or _rieul(word)) else "으로"
    text = re.sub(esc + "(으로|로)" + end, word + want, text)
    return text


def _walk(x, fn):
    if isinstance(x, str):
        return fn(x)
    if isinstance(x, list):
        if x and x[0] in _SKIP:
            y = list(x)
            if x[0] == "img" and len(x) > 2:  # 그림 캡션은 고친다
                y[2] = fn(y[2])
            if x[0] == "code" and len(x) > 1:  # 코드 제목은 고치고 코드 본문은 그대로
                y[1] = fn(y[1])
            return y
        return [_walk(v, fn) for v in x]
    return x


def rewrite(secs, pairs):
    """pairs: [(원문 조각, 고친 글)]. 돌려줌: (secs, 못 찾은 원문 목록)."""
    hit = {o: 0 for o, _ in pairs}

    def fn(s):
        for o, n in pairs:
            if o in s:
                hit[o] += 1
                s = s.replace(o, n)
        return s
    secs = _walk(secs, fn)
    return secs, [o for o, k in hit.items() if k == 0]


def terms(secs, pairs):
    """pairs: [(내부 말, 실무 용어)] — 긴 말부터 바꾼다."""
    pairs = sorted(pairs, key=lambda p: -len(p[0]))

    def fn(s):
        for o, n in pairs:
            if o in s:
                s = s.replace(o, n)
                s = _fix_josa(s, n)
        return s
    return _walk(secs, fn)


_REF = [
    re.compile(r"\s*\((?:정본|마스터 문서|연구 기록)\s*§[^)]*\)"),
    re.compile(r"\s*\(§\s*\d[\d\-~·, §]*\)"),
    re.compile(r"(?:정본|마스터 문서)\s*§\s*\d[\d\-~·, §]*"),
]


def strip_refs(secs):
    def fn(s):
        for r in _REF:
            s = r.sub("", s)
        return s
    return _walk(secs, fn)


def glossary(rows, title="읽기 전에: 이 문서의 시험 · 자료 이름", intro=None, ratio=(2.4, 7.6)):
    out = [["h", title]]
    out.append(["p", intro or "이 문서에서 팀이 붙인 시험 · 자료 · 구성 요소 이름입니다. 시험 문제와 질문은 모두 AI 모델(Codex · Claude)이 쓴 합성 자료이고, 사람이 쓴 실제 고객 문장 시험은 아직 없습니다."])
    out.append(["t", ["용어", "뜻"], [list(r) for r in rows], list(ratio)])
    return out


def leftovers(secs, words):
    """정비 뒤에도 남은 내부 말을 센다(검사용)."""
    found = {}

    def fn(s):
        for w in words:
            if w in s:
                found[w] = found.get(w, 0) + s.count(w)
        return s
    _walk(secs, fn)
    return found
