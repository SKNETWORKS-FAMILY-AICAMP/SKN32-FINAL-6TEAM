"""로컬 처리 흐름 두 장. 기존 출력이 있으면 덮어쓰지 않는다."""
from pathlib import Path
from datetime import datetime
import shutil
from html import escape

OUT = Path(__file__).parent / "service-improvement-flow.html"
PAPER, INK, MUTED, ACCENT = "#fbfcfd", "#161c28", "#6b7488", "#a8720c"


def node(kind, x, y, text, width=320):
    if kind == "decision":
        shape = f'<polygon points="{x},{y-48} {x+width//2},{y} {x},{y+48} {x-width//2},{y}"/>'
    else:
        radius = 24 if kind == "end" else 6
        shape = f'<rect x="{x-width//2}" y="{y-24}" width="{width}" height="48" rx="{radius}"/>'
    return f'<g fill="{PAPER}" stroke="{INK}" stroke-width="1">{shape}</g><text x="{x}" y="{y+4}">{escape(text)}</text>'


def arrow(x1, y1, x2, y2, label=""):
    result = f'<path d="M{x1} {y1} L{x2} {y2}" class="edge" marker-end="url(#arrow)"/>'
    if label:
        if x1 == x2:
            x, y = x1 + 24, (y1 + y2) // 2
            anchor = "start"
        else:
            x, y = (x1 + x2) // 2, y1 - 16
            anchor = "middle"
        result += f'<rect x="{x-4 if anchor == "start" else x-48}" y="{y-16}" width="96" height="24" fill="{PAPER}"/><text x="{x}" y="{y}" text-anchor="{anchor}" class="label">{label}</text>'
    return result


def figure(ident, title, description, nodes, edges):
    result = f'''<section><h2>{title}</h2><p>{description}</p>
<svg viewBox="0 0 1040 720" role="img" aria-labelledby="{ident}-title {ident}-desc">
<title id="{ident}-title">{title}</title><desc id="{ident}-desc">{description}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="{MUTED}"/></marker>
<marker id="arrow-accent" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="{ACCENT}"/></marker>
<marker id="arrow-link" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#2f5bd8"/></marker></defs>
{''.join(edges)}{''.join(nodes)}
<path d="M40 660 H1000" stroke="#dbe0ea"/><text x="40" y="692" text-anchor="start" class="label">타원: 시작·종료　 사각형: 처리　 마름모: 판단</text></svg></section>'''
    for marker in ("arrow-accent", "arrow-link", "arrow"):
        result = result.replace(f'id="{marker}"', f'id="{ident}-{marker}"').replace(f'url(#{marker})', f'url(#{ident}-{marker})')
    return result


first = figure("generation", "한 회차의 합성 후보 생성", "동의와 보유기한이 유효한 이용자만 포함합니다. 실패해도 생성 예산은 돌려주지 않습니다.", [
    node("end", 360, 48, "시작 · 생성 요청", 240),
    node("step", 360, 144, "누적 예산 확보 시도"),
    node("decision", 360, 264, "예산 확보?"),
    node("end", 840, 264, "종료 · 생성하지 않음", 304),
    node("step", 360, 384, "현재 동의자 수치 추출·잡음 처리", 400),
    node("decision", 360, 504, "잡음 처리 후 자료량 충족?", 400),
    node("end", 840, 504, "종료 · 후보 없음", 304),
    node("end", 360, 600, "종료 · 검토 대기 후보 저장", 368),
], [arrow(360,72,360,120), arrow(360,168,360,216), arrow(520,264,688,264,"아니요"),
    arrow(360,312,360,360,"예"), arrow(360,408,360,456), arrow(560,504,688,504,"아니요"), arrow(360,552,360,576,"예")])

second = figure("review", "검토와 합성본 이용", "후보는 최대 7일 보관합니다. 승인본도 연례 검토가 지나면 내보내기를 차단하며 생성일부터 최대 5년 뒤 파기합니다.", [
    node("end", 360, 48, "시작 · 후보 검토 요청", 304),
    node("step", 360, 144, "해시·약관·기한·심의 증빙 검사", 400),
    node("decision", 360, 264, "검토 승인 조건 충족?", 368),
    node("end", 840, 264, "종료 · 내보내기 차단", 304),
    node("step", 360, 384, "익명성 검토를 마친 합성본 승인", 400),
    node("decision", 360, 504, "현재 약관·연례 검토 유효?", 400),
    node("end", 840, 504, "종료 · 재검토 전 차단", 304),
    node("end", 360, 600, "종료 · 합성본만 내보내기", 368),
], [arrow(360,72,360,120), arrow(360,168,360,216), arrow(544,264,688,264,"아니요"),
    arrow(360,312,360,360,"예"), arrow(360,408,360,456), arrow(560,504,688,504,"아니요"), arrow(360,552,360,576,"예")])

html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서비스 개선 선택 동의와 합성 자료</title>
<style>:root{{--paper:{PAPER};--ink:{INK};--muted:{MUTED};--accent:{ACCENT}}}*{{box-sizing:border-box}}body{{margin:0;padding:40px;background:var(--paper);color:var(--ink);font-family:'Geist','Noto Sans KR','Malgun Gothic',sans-serif}}main{{max-width:1040px;margin:auto}}h1{{font:400 32px 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}p{{font-size:16px;line-height:1.8}}section{{margin:40px 0}}svg{{width:100%;height:auto}}svg text{{font-size:16px;font-weight:600;text-anchor:middle;fill:var(--ink)}}svg .label{{font-size:16px;font-weight:500}}.edge{{stroke:var(--muted);stroke-width:1.2;fill:none}}.notice{{border-left:4px solid var(--accent);padding-left:16px}}@media(max-width:700px){{body{{padding:20px}}section{{overflow:auto}}svg{{min-width:900px}}}}@media print{{section{{break-inside:avoid}}}}</style></head>
<body><main><h1>선택 동의부터 검토된 합성본까지</h1><p class="notice">로컬 구현의 처리 흐름입니다. 운영 배포·실제 이용자 추출·실제 익명성 심의를 완료했다는 뜻은 아닙니다.</p>
<p>원본 파기는 기존 보유기한대로 별도로 진행하며 합성 성공을 기다리지 않습니다. 동의 철회 시 검토 대기 후보는 폐기합니다. 새 회차는 별도 생성 요청과 남은 누적 예산이 있을 때만 시작합니다.</p>
{first}{second}<p>도표: diagram-design · acop 프로필 · 정적 흐름도 2장 · 내부 검토용. 글꼴은 설치된 글꼴로 대체될 수 있습니다. DB 잠금·추출 세부 조건은 운영 문서에서 확인합니다.</p></main></body></html>'''
html = html.replace("svg .label", 'svg [text-anchor="start"]{text-anchor:start}svg .label')
if OUT.exists():
    backup = OUT.parent / "_backup" / datetime.now().strftime("%Y-%m-%d_%H%M%S_flow")
    backup.mkdir(parents=True)
    shutil.copy2(OUT, backup / OUT.name)
with OUT.open("w", encoding="utf-8") as target:
    target.write(html)
