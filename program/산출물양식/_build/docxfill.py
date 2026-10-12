# -*- coding: utf-8 -*-
"""산출물 docx 를 채우는 공용 도구.

- 양식을 풀고, 문단을 넣고, 그림을 넣고, 다시 압축한다.
- 사람이 안 쓰는 기호(줄표, 화살표, 별표 등)가 들어가면 그 자리에서 막는다.
"""
import os
import re
import shutil
import struct
import zipfile

FONT = ('<w:rFonts w:ascii="Malgun Gothic" w:cs="Malgun Gothic" '
        'w:eastAsia="Malgun Gothic" w:hAnsi="Malgun Gothic"/>')

# 사람이 쓰는 문장부호만 쓴다. 아래는 넣지 않는다.
BANNED = {
    "—": "줄표(em dash)", "–": "줄표(en dash)", "→": "화살표",
    "⇒": "이중화살표", "★": "검은 별", "☆": "흰 별",
    "✓": "체크", "✔": "체크", "✕": "가위표", "✗": "가위표",
    "▸": "삼각형", "…": "말줄임표", "⇄": "양방향화살표",
    "①": "동그라미1", "②": "동그라미2", "③": "동그라미3",
    "④": "동그라미4", "⑤": "동그라미5", "⑥": "동그라미6",
}


def check(text, where=""):
    for ch, name in BANNED.items():
        if ch in text:
            raise ValueError("금지 문자 %s(%s) 발견 %s: %s"
                             % (ch, name, where, text[:70]))
    return text


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def para(text, bold=False, indent=720, size=20, bullet=False):
    check(text)
    b = '<w:b w:val="1"/><w:bCs w:val="1"/>' if bold else ''
    body = ("- " + text) if bullet else text
    return ('<w:p><w:pPr><w:widowControl w:val="0"/>'
            '<w:spacing w:after="60" w:line="264" w:lineRule="auto"/>'
            '<w:ind w:left="%d"/><w:jc w:val="both"/></w:pPr>'
            '<w:r><w:rPr>%s%s<w:sz w:val="%d"/><w:szCs w:val="%d"/><w:rtl w:val="0"/></w:rPr>'
            '<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (indent, FONT, b, size, size, esc(body)))


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


class Doc:
    """양식 docx 하나를 열어 채우고 저장한다."""

    def __init__(self, template, workdir):
        shutil.rmtree(workdir, ignore_errors=True)
        os.makedirs(workdir)
        with zipfile.ZipFile(template) as z:
            z.extractall(workdir)
        self.root = workdir
        self.docpath = os.path.join(workdir, "word", "document.xml")
        with open(self.docpath, encoding="utf-8") as f:
            self.xml = f.read()
        self._rid = 500
        self._img = 0
        self.normalize_template()

    #: 양식 자체에 들어 있는 기호도 사람이 쓰는 것으로 바꾼다.
    TEMPLATE_FIX = [
        ("—", ","), ("–", ","), ("⇒", "은 다음과 같다"), ("→", "이 가리키는 곳은"),
        ("★", ""), ("✔", "O"), ("✓", "O"), ("▸", ""), ("…", "."),
    ]

    def normalize_template(self):
        def fix(m):
            t = m.group(1)
            for a, b in self.TEMPLATE_FIX:
                t = t.replace(a, b)
            return '<w:t xml:space="preserve">%s</w:t>' % t
        self.xml = re.sub(r'<w:t[^>]*>([^<]*)</w:t>', fix, self.xml)

    # ---- 텍스트 치환 -------------------------------------------------
    def replace_text(self, old, new, count=1):
        check(new)
        tag = '<w:t xml:space="preserve">%s</w:t>'
        if tag % esc(old) in self.xml:
            self.xml = self.xml.replace(tag % esc(old), tag % esc(new), count)
            return True
        if old in self.xml:                       # run 안에 그대로 있는 경우
            self.xml = self.xml.replace(old, esc(new), count)
            return True
        return False

    def fill_empty_para(self, para_id, text):
        m = re.search(r'(<w:p [^>]*w14:paraId="%s">.*?)(</w:p>)' % para_id, self.xml, re.S)
        if not m:
            return False
        run = ('<w:r><w:rPr>' + FONT + '<w:sz w:val="24"/><w:szCs w:val="24"/>'
               '<w:rtl w:val="0"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % esc(text))
        self.xml = self.xml[:m.start(2)] + run + self.xml[m.start(2):]
        return True

    # ---- 그림 -------------------------------------------------------
    def image_xml(self, png, width_in=6.0):
        w_px, h_px = png_size(png)
        cx = int(width_in * 914400)
        cy = int(cx * h_px / w_px)
        self._rid += 1
        self._img += 1
        rid = "rIdIMG%d" % self._rid
        name = "chart_%d.png" % self._img
        media = os.path.join(self.root, "word", "media")
        os.makedirs(media, exist_ok=True)
        shutil.copy(png, os.path.join(media, name))
        rels_path = os.path.join(self.root, "word", "_rels", "document.xml.rels")
        with open(rels_path, encoding="utf-8") as f:
            rels = f.read()
        rels = rels.replace("</Relationships>",
                            '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/'
                            'officeDocument/2006/relationships/image" Target="media/%s"/>'
                            "</Relationships>" % (rid, name))
        with open(rels_path, "w", encoding="utf-8") as f:
            f.write(rels)
        did = 900 + self._img
        return (
            '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="60"/></w:pPr>'
            '<w:r><w:rPr><w:noProof/></w:rPr><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            '<wp:docPr id="%d" name="그림 %d"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:nvPicPr><pic:cNvPr id="%d" name="그림 %d"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships" r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
            % (cx, cy, did, self._img, did, self._img, rid, cx, cy)
        )

    def caption(self, text):
        check(text)
        return ('<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="180"/></w:pPr>'
                '<w:r><w:rPr>%s<w:sz w:val="17"/><w:szCs w:val="17"/>'
                '<w:color w:val="595959"/><w:rtl w:val="0"/></w:rPr>'
                '<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (FONT, esc(text)))

    # ---- 절 채우기 ---------------------------------------------------
    def build(self, items):
        """items: 문자열 | ("b", 굵게) | ("l", 불릿) | ("img", png경로, 캡션)"""
        out = []
        for it in items:
            if isinstance(it, tuple) and it[0] == "img":
                out.append(self.image_xml(it[1], it[3] if len(it) > 3 else 6.0))
                out.append(self.caption(it[2]))
            elif isinstance(it, tuple):
                kind, t = it
                out.append(para(t, bold=(kind == "b"), bullet=(kind == "l"),
                                indent=1080 if kind == "l" else 720))
            else:
                out.append(para(it))
        return "".join(out)

    def after_heading(self, title, items, scope_tail=True):
        body = self.build(items)
        if scope_tail and "</w:tbl>" in self.xml:
            cut = self.xml.rfind("</w:tbl>") + len("</w:tbl>")
        else:
            cut = 0
        head, tail = self.xml[:cut], self.xml[cut:]
        pat = re.compile(r'(<w:p\b(?:(?!</w:p>).)*?<w:t[^>]*>' + re.escape(esc(title))
                         + r'</w:t>.*?</w:p>)', re.S)
        m = pat.search(tail)
        if not m:
            raise KeyError("제목 문단 없음: " + title)
        self.xml = head + tail[:m.end()] + body + tail[m.end():]

    # ---- paraId 로 문단 갈아 끼우기 -----------------------------------
    def _find_para(self, para_id):
        m = re.search(r'<w:p\b[^>]*w14:paraId="%s"[^>]*>' % para_id, self.xml)
        if not m:
            return None
        return m.start(), self.xml.index("</w:p>", m.end()) + len("</w:p>")

    def replace_para(self, para_id, texts):
        """그 문단을 texts[0] 으로 바꾸고 나머지는 같은 서식으로 뒤에 잇는다."""
        span = self._find_para(para_id)
        if not span:
            raise KeyError("문단 없음: " + para_id)
        s, e = span
        blk = self.xml[s:e]
        open_m = re.match(r'(<w:p\b[^>]*>)', blk)
        first_open = open_m.group(1)
        clone_open = re.sub(r' w14:paraId="[^"]*"', "", first_open)
        ppr_m = re.match(r'<w:pPr>.*?</w:pPr>', blk[open_m.end():], re.S)
        ppr = ppr_m.group(0) if ppr_m else ""
        rpr_m = re.search(r'<w:r\b[^>]*><w:rPr>(.*?)</w:rPr>', blk, re.S)
        rpr = rpr_m.group(1) if rpr_m else ""

        def one(open_tag, t):
            check(t)
            return ('%s%s<w:r><w:rPr>%s</w:rPr>'
                    '<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
                    % (open_tag, ppr, rpr, esc(t)))

        out = [one(first_open, texts[0])] + [one(clone_open, t) for t in texts[1:]]
        self.xml = self.xml[:s] + "".join(out) + self.xml[e:]

    def insert_after_para(self, para_id, xml_chunk):
        span = self._find_para(para_id)
        if not span:
            raise KeyError("문단 없음: " + para_id)
        self.xml = self.xml[:span[1]] + xml_chunk + self.xml[span[1]:]

    def insert_before_para(self, para_id, xml_chunk):
        span = self._find_para(para_id)
        if not span:
            raise KeyError("문단 없음: " + para_id)
        self.xml = self.xml[:span[0]] + xml_chunk + self.xml[span[0]:]

    def save(self, out):
        check_doc = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', self.xml)
        for t in check_doc:
            for ch, name in BANNED.items():
                if ch in t:
                    raise ValueError("저장 직전 금지 문자 %s(%s): %s" % (ch, name, t[:70]))
        with open(self.docpath, "w", encoding="utf-8") as f:
            f.write(self.xml)
        # Word 로 열어 둔 파일은 지울 수 없다. 그때는 옆에 새 이름으로 저장하고 알린다.
        if os.path.exists(out):
            try:
                os.remove(out)
            except PermissionError:
                base, ext = os.path.splitext(out)
                out = base + "_새버전" + ext
                print("  원본이 열려 있어 새 이름으로 저장한다:", os.path.basename(out))
                if os.path.exists(out):
                    os.remove(out)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(self.root):
                for fn in files:
                    p = os.path.join(root, fn)
                    z.write(p, os.path.relpath(p, self.root).replace(os.sep, "/"))
        return out
