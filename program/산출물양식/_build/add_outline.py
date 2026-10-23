#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
사용법:
    python add_outline.py <docx> [<docx> ...]

필요 패키지:
    pip install python-docx

원본은 보존하고 같은 폴더에 <원본이름>_outline.docx를 저장한다.
입력이 이미 *_outline.docx이면 해당 파일을 갱신한다.
변경할 제목이 없으면 저장하지 않는다.

대상 문서 조사 결과:
- 기획서: 지정된 절 제목 7개 + 직접 굵게 지정된 소제목 5개.
- 수집 보고서: 1수준 6개 + 2수준 6개.
- DB 설계서: 1수준 4개 + 2수준 5개.
- 일부 1수준 제목의 번호는 텍스트가 아니라 Word 자동 번호이다.
- 문서 기본 글꼴에 굵기가 지정되어 있으므로, 기획서 소제목은
  상속된 굵기가 아닌 run의 명시적 굵기로 구별한다.
- 표 안의 문단, 표지 제목, 표·그림 캡션은 제외한다.
- 여백 및 section 속성은 읽지 않는다.
"""

import argparse
import re
import sys
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


PLAN_SECTIONS = {
    "프로젝트 주제",
    "문제 정의",
    "시장조사 및 BM 분석",
    "시스템 구성 기획",
    "모델링 계획",
    "데이터 수집 전략",
    "역할분담(R&R)",
}

CAPTION = re.compile(r"^(?:표|그림)\s*(?:\d+\s*)?[.．]")
LEVEL_1 = re.compile(r"^\d+\.\s+\S")
LEVEL_2 = re.compile(r"^\d+\.\d+\.?\s+\S")
FALSE_VALUES = {"0", "false", "off"}

# 기존에 없던 Heading의 문단 서식이 유입되지 않도록 기본값도 고정한다.
PARAGRAPH_BASELINE = """
<w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:keepNext w:val="0"/>
  <w:keepLines w:val="0"/>
  <w:pageBreakBefore w:val="0"/>
  <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
</w:pPr>
"""


def normalized(text):
    return " ".join(text.split())


def child(parent, name):
    return None if parent is None else parent.find(qn("w:" + name))


def value(parent, name, default=None):
    element = child(parent, name)
    return default if element is None else element.get(qn("w:val"), default)


def style_chain(style):
    """기반 스타일부터 현재 스타일까지 반환한다."""
    result = []
    seen = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        result.append(style)
        style = style.base_style
    return list(reversed(result))


def merge_properties(destination, source):
    """XML 속성을 병합한다. source가 우선하며 기존 자식도 보존한다."""
    if source is None:
        return
    destination.attrib.update(source.attrib)
    for item in source:
        existing = destination.find(item.tag)
        if existing is None:
            destination.append(deepcopy(item))
        else:
            merge_properties(existing, item)


def default_properties(document, kind):
    defaults = child(document.styles.element, "docDefaults")
    wrapper = child(defaults, kind + "Default")
    return child(wrapper, kind)


def inherited_properties(document, style, kind):
    result = OxmlElement("w:" + kind)
    merge_properties(result, default_properties(document, kind))
    for ancestor in style_chain(style):
        merge_properties(result, child(ancestor.element, kind))
    return result


def fill_missing(destination, source):
    """
    既存の直接書式を上書きせず、不足している属性だけ補う。
    python-docxの生成メソッドを使い、主要な要素の順序を維持する。
    """
    for key, val in source.attrib.items():
        if key not in destination.attrib:
            destination.set(key, val)

    for item in source:
        local_name = item.tag.rsplit("}", 1)[-1]
        if local_name in {"pStyle", "rStyle", "outlineLvl"}:
            continue

        existing = destination.find(item.tag)
        if existing is None:
            factory = getattr(destination, "get_or_add_" + local_name, None)
            if factory is not None:
                existing = factory()
                merge_properties(existing, item)
            else:
                destination.append(deepcopy(item))
        else:
            fill_missing(existing, item)


def heading_styles(document):
    result = {}
    for level in (0, 1):
        names = {f"heading {level + 1}", f"제목 {level + 1}"}
        for style in document.styles:
            if (
                style.type == WD_STYLE_TYPE.PARAGRAPH
                and normalized(style.name or "").casefold() in names
            ):
                result[level] = style
                break
    return result


def preserve_appearance(document, paragraph):
    """
    스타일 교체 전에 기본값·기존 스타일의 상속 서식을 직접 서식으로 고정한다.
    기존 run, 텍스트, pPr 속성은 삭제하거나 다시 만들지 않는다.
    """
    from docx.oxml import parse_xml

    old_style = paragraph.style
    paragraph_properties = parse_xml(PARAGRAPH_BASELINE)
    merge_properties(
        paragraph_properties,
        inherited_properties(document, old_style, "pPr"),
    )
    ppr = paragraph._p.get_or_add_pPr()
    fill_missing(ppr, paragraph_properties)

    run_properties = inherited_properties(document, old_style, "rPr")

    # 문단 기호의 서식도 보존한다.
    marker = child(ppr, "rPr")
    if marker is None:
        marker = OxmlElement("w:rPr")
        ppr.insert_element_before(marker, "w:sectPr", "w:pPrChange")
    fill_missing(marker, run_properties)

    # 하이퍼링크 내부의 run도 포함하되 다른 중첩 문단은 제외한다.
    for run_element in paragraph._p.xpath(".//w:r"):
        ancestors = run_element.xpath("ancestor::w:p")
        if not ancestors or ancestors[-1] != paragraph._p:
            continue

        effective = deepcopy(run_properties)
        rpr = run_element.get_or_add_rPr()
        character_style_id = value(rpr, "rStyle")
        if character_style_id:
            character_style = next(
                (
                    s for s in document.styles
                    if s.style_id == character_style_id
                    and s.type == WD_STYLE_TYPE.CHARACTER
                ),
                None,
            )
            for ancestor in style_chain(character_style):
                merge_properties(effective, child(ancestor.element, "rPr"))

        fill_missing(rpr, effective)


def automatic_level(document, paragraph):
    """자동 번호의 형식이 실제로 1. 또는 2.1 형태인지 확인한다."""
    numpr = child(paragraph._p.pPr, "numPr")
    num_id = value(numpr, "numId")
    if not num_id or num_id == "0":
        return None

    ilvl = value(numpr, "ilvl", "0")
    try:
        numbering = document.part.numbering_part.element
    except (KeyError, NotImplementedError):
        return None

    num = next(
        (
            item for item in numbering.findall(qn("w:num"))
            if item.get(qn("w:numId")) == num_id
        ),
        None,
    )
    if num is None:
        return None

    abstract_id = value(num, "abstractNumId")
    abstract = next(
        (
            item for item in numbering.findall(qn("w:abstractNum"))
            if item.get(qn("w:abstractNumId")) == abstract_id
        ),
        None,
    )
    if abstract is None:
        return None

    level = next(
        (
            item for item in abstract.findall(qn("w:lvl"))
            if item.get(qn("w:ilvl")) == ilvl
        ),
        None,
    )

    for override in num.findall(qn("w:lvlOverride")):
        if override.get(qn("w:ilvl")) == ilvl:
            replacement = child(override, "lvl")
            if replacement is not None:
                level = replacement

    if level is None or value(level, "numFmt") != "decimal":
        return None

    pattern = value(level, "lvlText", "").strip()
    if ilvl == "0" and pattern == "%1.":
        return 0
    if ilvl == "1" and pattern in {"%1.%2", "%1.%2."}:
        return 1
    return None


def explicitly_bold(paragraph):
    runs = [run for run in paragraph.runs if run.text.strip()]
    return bool(runs) and all(run.bold is True for run in runs)


def find_headings(document):
    # Document.paragraphs는 표 셀의 문단을 포함하지 않는다.
    paragraphs = document.paragraphs
    texts = {normalized(p.text) for p in paragraphs}
    is_plan = PLAN_SECTIONS.issubset(texts)
    inside_section = False

    for paragraph in paragraphs:
        text = normalized(paragraph.text)
        if not text or CAPTION.match(text):
            continue

        level = None
        if is_plan:
            if text in PLAN_SECTIONS:
                level = 0
                inside_section = True
            elif inside_section and explicitly_bold(paragraph):
                level = 1
        else:
            if LEVEL_2.match(text):
                level = 1
            elif LEVEL_1.match(text):
                level = 0
            else:
                level = automatic_level(document, paragraph)

        if level is not None:
            yield paragraph, level, text


def add_outline(document):
    styles = heading_styles(document)

    # 스타일 변경으로 제목 판별 결과가 달라지지 않도록 먼저 확정한다.
    headings = list(find_headings(document))
    changed = 0
    report = []

    for paragraph, level, text in headings:
        existing = child(paragraph._p.pPr, "outlineLvl")
        if existing is not None:
            actual = existing.get(qn("w:val"), "?")
            report.append(
                (level, text, f"기존 outlineLvl={actual} 유지")
            )
            continue

        style = styles.get(level)
        if style is not None:
            preserve_appearance(document, paragraph)
            paragraph.style = style

        ppr = paragraph._p.get_or_add_pPr()
        outline = OxmlElement("w:outlineLvl")
        outline.set(qn("w:val"), str(level))
        ppr.insert_element_before(
            outline,
            "w:divId",
            "w:cnfStyle",
            "w:rPr",
            "w:sectPr",
            "w:pPrChange",
        )
        changed += 1
        status = style.name if style is not None else "outlineLvl만 지정"
        report.append((level, text, status))

    return changed, report


def process(path):
    if path.suffix.lower() != ".docx":
        raise ValueError("입력 파일은 .docx여야 합니다.")
    if not path.is_file():
        raise FileNotFoundError(path)

    document = Document(path)
    changed, report = add_outline(document)

    print(f"\n[{path.name}]")
    for level, text, status in report:
        print(f"  {level + 1}수준: {text} [{status}]")
    print(f"  제목 {len(report)}개, 변경 {changed}개")

    if not changed:
        print("  변경 사항이 없어 저장하지 않았습니다.")
        return

    output = (
        path
        if path.stem.endswith("_outline")
        else path.with_name(path.stem + "_outline.docx")
    )
    document.save(output)
    print(f"  저장: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="DOCX 본문 제목에 개요 수준과 제목 스타일을 지정합니다."
    )
    parser.add_argument("docx", nargs="+", type=Path, help="입력 DOCX 경로")
    args = parser.parse_args()

    failed = False
    seen = set()
    for path in args.docx:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            process(path)
        except Exception as exc:
            failed = True
            print(f"오류: {path}: {exc}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())