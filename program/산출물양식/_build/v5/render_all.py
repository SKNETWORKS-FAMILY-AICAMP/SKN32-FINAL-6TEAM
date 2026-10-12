"""세 문서를 Word 로 PDF 변환하고 쪽 이미지를 뽑는다(검토용). 결과: C:/Users/playdata2/Documents/_render_tmp/v4/<키>/p01.png ..."""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_docx as Q
import fitz
OUT = Path(r"C:\Users\playdata2\Documents\_render_tmp\v4")
D = Path(__file__).resolve().parents[2] / "w4" / "데이터전처리_여행_4차v5"
keys = {"pre": "전처리", "train": "학습", "model": "모델"}
for key, name in keys.items():
    f = next(D.glob(f"*{'데이터 전처리 결과서' if key=='pre' else ('학습 결과서' if key=='train' else '학습한 ML_DL 모델')}*4차v5*.docx"))
    od = OUT / key
    shutil.rmtree(od, ignore_errors=True)
    pdf = Q.render_pdf(f, od)
    doc = fitz.open(str(pdf))
    for i, pg in enumerate(doc, 1):
        pg.get_pixmap(dpi=70).save(str(od / f"p{i:02d}.png"))
    print(key, doc.page_count)
    # 4쪽씩 몽타주
    from PIL import Image
    ims = [Image.open(od / f"p{i:02d}.png") for i in range(1, doc.page_count + 1)]
    w, h = ims[0].size
    for g in range(0, len(ims), 4):
        chunk = ims[g:g + 4]
        m = Image.new("RGB", (w * len(chunk), h), "white")
        for j, im in enumerate(chunk):
            m.paste(im, (j * w, 0))
        m.save(od / f"m{g // 4 + 1}.png")
