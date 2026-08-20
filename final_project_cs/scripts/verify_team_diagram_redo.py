"""Static checks for scratch_team_diagram_redo.html."""
from pathlib import Path
import re

HTML = Path(__file__).resolve().parents[1] / "scratch_team_diagram_redo.html"
text = HTML.read_text(encoding="utf-8")
svg = re.search(r'<svg\b[^>]*viewBox="0 0 1100 620".*?</svg>', text, re.S).group(0)

rects = [
    tuple(map(float, match))
    for match in re.findall(
        r'<rect\s+x="([0-9.]+)"\s+y="([0-9.]+)"\s+width="([0-9.]+)"\s+height="([0-9.]+)"', svg
    )
]
teams = [rect for rect in rects if rect[2:] == (220.0, 110.0)]
assert len(teams) == 6, f"expected 6 team boxes, found {len(teams)}"

def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

for index, left in enumerate(teams):
    for right in teams[index + 1 :]:
        assert not overlap(left, right), f"team boxes overlap: {left} and {right}"

assert sorted({box[0] for box in teams}) == [190.0, 430.0, 670.0]
assert sorted({box[1] for box in teams}) == [210.0, 344.0]
connector_area = re.sub(r'<defs>.*?</defs>', '', svg, flags=re.S)
assert ' C ' not in connector_area and '<path' not in connector_area, "curved/path connector found"

# Conservative width estimate: ASCII 8px, non-ASCII 14px. All team text starts at x+20.
labels = {
    "VOC & Store Manager": 13,
    "Response Generation": 12.5,
    "& Review": 12.5,
    "Return & Refund": 13,
    "Procurement + Order": 12.5,
    "& Payment": 12.5,
    "Fulfillment & Logistics": 13,
    "Catalog & Verification": 13,
    "voc_store_manager": 10,
    "response_generation_review": 9.5,
    "return_refund · Mock": 10,
    "procurement_order_payment": 9.5,
    "fulfillment_logistics": 10,
    "catalog_verification · A2A": 9.5,
    "케이스 유사도 인덱스": 10,
    "정책 RAG": 10,
    "데이터 없음": 10,
}

def estimated_width(value, font_size):
    # The actual font is narrower for most Latin text; this deliberately leaves margin.
    return sum((14 if ord(char) > 127 else 8) for char in value) * font_size / 13

for label, font_size in labels.items():
    assert estimated_width(label, font_size) <= 200, (
        f"text estimate exceeds box content width: {label!r}"
    )

print("PASS: 6 team boxes, exact 220x110 size, no rectangle overlap")
print("PASS: 3 columns x 2 rows at x=190/430/670 and y=210/344")
print("PASS: no curved/path connectors in the replacement SVG")
print("PASS: conservative team-label width estimates stay within 200px")
