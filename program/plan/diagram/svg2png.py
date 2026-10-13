# -*- coding: utf-8 -*-
"""SVG 다이어그램을 PNG로 렌더링한다. 한글이 두부(□)로 깨지지 않게 맑은고딕을 등록한다."""
import sys
sys.modules['cairocffi'] = None  # cairocffi가 DLL을 못 찾으므로 pycairo로 폴백

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

MALGUN = r"C:\Windows\Fonts\malgun.ttf"
MALGUN_BD = r"C:\Windows\Fonts\malgunbd.ttf"

# SVG의 font-family="sans-serif"가 이 이름들로 해석되도록 전부 같은 폰트에 묶는다.
for name, path in [("Malgun Gothic", MALGUN), ("Malgun Gothic-Bold", MALGUN_BD),
                   ("Helvetica", MALGUN), ("Helvetica-Bold", MALGUN_BD),
                   ("Helvetica-Oblique", MALGUN), ("Helvetica-BoldOblique", MALGUN_BD),
                   ("sans-serif", MALGUN)]:
    pdfmetrics.registerFont(TTFont(name, path))

addMapping("Helvetica", 0, 0, "Helvetica")
addMapping("Helvetica", 1, 0, "Helvetica-Bold")
addMapping("Helvetica", 0, 1, "Helvetica-Oblique")
addMapping("Helvetica", 1, 1, "Helvetica-BoldOblique")

scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6
d = svg2rlg(sys.argv[1])
d.width *= scale
d.height *= scale
d.scale(scale, scale)
renderPM.drawToFile(d, sys.argv[2], fmt="PNG", bg=0xFFFFFF)
print("%s -> %s (%dx%d)" % (sys.argv[1], sys.argv[2], d.width, d.height))
