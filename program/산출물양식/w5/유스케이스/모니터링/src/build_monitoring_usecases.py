"""모니터링 유스케이스 명세와 사용자 목표 다이어그램을 함께 렌더링한다."""
from datetime import datetime
from html import escape
from pathlib import Path
import shutil
import markdown

OUT = Path(__file__).resolve().parent.parent
STEM = 'triPilot_모니터링_유스케이스_2026-10-10'

def back_up(path):
    if path.exists():
        destination = OUT / '_backup' / (datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_재생성전')
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination / path.name)

def text(x, y, value, cls='label', anchor='middle'):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(value)}</text>'

def actor(x, y, width, height, lines):
    result = f'<rect class="actor" x="{x}" y="{y}" width="{width}" height="{height}" rx="6"/>'
    mid = y + height // 2
    result += text(x + width // 2, mid - 28, '«actor»', 'actor-type')
    for i, line in enumerate(lines):
        result += text(x + width // 2, mid + i * 24, line)
    return result

def usecase(cx, cy, key, lines):
    value = f'<ellipse class="goal" cx="{cx}" cy="{cy}" rx="208" ry="44"/>'
    value += text(cx, cy - 20, key, 'uc-id')
    for i, line in enumerate(lines):
        value += text(cx, cy + 4 + i * 20, line)
    return value

def diagram(kind):
    customer = kind == 'traveler'
    title = '여행자 목표와 참여 액터' if customer else '운영자 목표와 참여 액터'
    count = 5 if customer else 4
    height = 680 if customer else 664
    slug = 'monitoring-' + kind
    value = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 {height}" role="img" aria-labelledby="{slug}-title {slug}-desc">'
    value += f'<title id="{slug}-title">{title}</title>'
    value += f'<desc id="{slug}-desc">triPilot 모니터링의 {"여행자" if customer else "운영자"} 목표와 외부 액터의 참여 관계를 보여준다. 연결선은 실행 순서가 아니다.</desc>'
    value += '<rect class="boundary" x="280" y="48" width="552" height="552" rx="8"/>'
    value += text(296, 80, 'triPilot · 모니터링', 'boundary-name', 'start')
    ys = [148 + i * 100 for i in range(count)]
    # 참여 관계는 화살표 없이 그린다. 상자와 타원보다 먼저 그려 가림을 방지한다.
    for y in ys:
        value += f'<path class="association" d="M220 {y} H348"/>'
    if customer:
        for y in ys[:4]:
            value += f'<path class="association" d="M764 {y} H880"/>'
        value += f'<path class="association" d="M764 {ys[4]} H880"/>'
        value += actor(40, 108, 180, 80, ['시간', '여행자 대신'])
        value += actor(40, 208, 180, 380, ['여행자'])
        value += actor(880, 108, 200, 380, ['외부 정보 서비스'])
        value += actor(880, 508, 200, 80, ['고객 외부 알림 채널'])
        goals = [
            ('UC-M01',['일정 문제를 현장에 가기 전에','알아챈다']),
            ('UC-M02',['예보를 고려해','일정을 조정한다']),
            ('UC-M03',['실제 문제에 맞춰','일정을 조정한다']),
            ('UC-M04',['재난으로 멈춘 여행을','다시 이어간다']),
            ('UC-M05',['여행 안내와 최신 일정','상태를 파악한다']),
        ]
    else:
        value += '<path class="association" d="M764 348 H880"/>'
        value += '<path class="association" d="M764 448 H880"/>'
        value += '<path class="association" d="M220 548 H548 Q556 548 556 540 V492"/>'
        value += actor(40, 108, 180, 380, ['운영자'])
        value += actor(40, 508, 180, 80, ['시간', '장애 보고 시점'])
        value += actor(880, 308, 200, 80, ['외부 정보 서비스'])
        value += actor(880, 408, 200, 80, ['운영 리포트 채널', '개발용 Discord 등'])
        goals = [
            ('UC-M06',['현재와 과거의 감시','상태를 파악한다']),
            ('UC-M07',['감시에 쓰는 정보의','사용 한도를 파악한다']),
            ('UC-M08',['재난 상황에서 여행 안내와','대응을 시험한다']),
            ('UC-M09',['감시 운영의 장애와','복구를 알아챈다']),
        ]
    for y, (key, lines) in zip(ys, goals):
        value += usecase(556, y, key, lines)
    value += '<path class="legend-rule" d="M40 624 H1080"/>'
    value += text(40, 652, '실선: 액터의 참여 관계 · 타원: 사용자 목표 · 사각 경계: triPilot의 책임 범위', 'legend', 'start')
    return value + '</svg>'

def build():
    source = OUT / (STEM + '.md')
    output = OUT / (STEM + '.html')
    body = markdown.markdown(source.read_text(encoding='utf-8'), extensions=['tables','toc','sane_lists'])
    body = body.replace('href="C:/', 'href="file:///C:/')
    diagrams = '<section class="diagrams"><h2>사용자 목표 유스케이스 다이어그램</h2><p>연결선은 참여 관계이며 처리 순서가 아닙니다. 시작·종료와 조건별 처리는 아래 텍스트 명세에 적었습니다.</p>'
    diagrams += '<figure>' + diagram('traveler') + '</figure><figure>' + diagram('operator') + '</figure></section>'
    css = """
    :root{color-scheme:light dark;--paper:light-dark(#fbfcfd,#141821);--ink:light-dark(#161c28,#e9edf4);--muted:light-dark(#6b7488,#9aa4b6);--rule:light-dark(#dbe0ea,#4c5260);--accent:light-dark(#a8720c,#d9a441)}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Geist,'Noto Sans KR','Malgun Gothic',sans-serif;font-size:16px;line-height:1.75}main{max-width:1160px;margin:auto;padding:32px 24px 64px}h1,h2,h3{line-height:1.4}h1{font-family:'Instrument Serif','Noto Serif KR',serif}h2{margin-top:48px;border-top:1px solid var(--rule);padding-top:24px}h3{margin-top:40px;color:var(--accent)}a{color:inherit;text-underline-offset:3px}table{border-collapse:collapse;width:100%;margin:16px 0 24px;font-size:15px}th,td{border-bottom:1px solid var(--rule);padding:12px;text-align:left;vertical-align:top}th{font-weight:600}td:first-child{min-width:120px}li{margin:8px 0}figure{margin:24px 0}svg{display:block;width:100%;height:auto}.boundary{fill:none;stroke:var(--ink);stroke-width:1.2}.actor,.goal{fill:var(--paper);stroke:var(--ink);stroke-width:1}.association{fill:none;stroke:var(--muted);stroke-width:1}.label{fill:var(--ink);font-size:16px;font-weight:500}.uc-id,.actor-type,.legend{fill:var(--muted);font-size:12px}.boundary-name{fill:var(--ink);font-size:16px;font-weight:600}.legend-rule{stroke:var(--rule);stroke-width:1}p,li,td{overflow-wrap:anywhere}@media(max-width:700px){main{padding:16px 12px}table{font-size:14px}th,td{padding:8px}td:first-child{min-width:80px}.diagrams figure{overflow-x:auto}.diagrams svg{width:1120px;max-width:none}}@media print{body{color:#161c28;background:#fbfcfd}main{padding:0}h3{break-after:avoid}tr{break-inside:avoid}.diagrams svg{width:100%;max-width:100%}}
    """
    result = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>triPilot 모니터링 유스케이스 명세</title><style>' + css + '</style></head><body><main>' + diagrams + body + '</main></body></html>'
    back_up(output)
    output.write_text(result, encoding='utf-8')
    for kind in ['traveler','operator']:
        svg_path = OUT / (STEM + '_' + kind + '.svg')
        back_up(svg_path)
        # SVG 단독 파일도 동일한 의미 토큰과 글꼴로 읽힌다.
        raw = diagram(kind)
        at = raw.index('</desc>') + len('</desc>')
        svg_path.write_text(raw[:at] + '<style>' + css + '</style>' + raw[at:], encoding='utf-8')
    print(output)

if __name__ == '__main__':
    build()
