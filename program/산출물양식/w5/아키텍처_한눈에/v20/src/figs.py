# -*- coding: utf-8 -*-
"""v10 그림 다섯 장 — diagram-design 스킬(유형: Loop · Architecture · Flowchart · Layer stack), acop 스킨

사실은 v9(코덱스 검토 반영본, ../v9/코덱스_검토결과_v8.md)와 같다. 그림 모양만 스킬 규칙으로 다시 그린다.
"""
import math
from html import escape

from dd import (ACCENT, ACCENT_TINT, INK, MUTED, PAPER, RULE, SOFT, Fig, tw, up4)


# ---------------------------------------------------------------- 1. 바깥 루프 (Loop)
def fig_loop():
    N, R = 5, 300
    SW, SH, HW, HH = 232, 72, 200, 104
    cx, cy, W, H = 480, 424, 960, 840
    f = Fig("tp-loop", W, H, "guguroute 바깥 루프 — 여행 기간 동안 1분마다 도는 감시 순환",
            "낮 감시가 깨진 항목을 찾으면 오케스트레이터가 담당 에이전트를 고르고, 에이전트가 후보를 다시 점검하고, "
            "검증과 반영을 거쳐 알림을 보낸 뒤 다음 1분 주기에 다시 감시로 돌아온다. 가운데 여행 기록(DB)에 Case · 새 일정 버전 · 발송 기록이 쌓인다.")
    st = [("낮 감시", "1분마다 · 앞 90분 항목", "backend"),
          ("오케스트레이터", "Case → 담당 에이전트 1개", "backend"),
          ("에이전트 재점검", "요식 · 액티비티 · 후보 점검", "focal"),
          ("검증 · 반영", "묻기 / 새 일정 버전 / 거부", "backend"),
          ("알림 · 계획서 링크", "Discord · 첫 발송 포함 최대 3회", "backend")]
    rects = []
    for k, (nm, sub, kind) in enumerate(st):
        th = math.radians(-90 + k * 360 / N)
        px, py = cx + R * math.cos(th), cy + R * math.sin(th)
        x, y = round((px - SW / 2) / 4) * 4, round((py - SH / 2) / 4) * 4
        rects.append((x, y, SW, SH))
        f.box(nm, x, y, SW, SH, kind=kind, lines=[sub])
    hx, hy = cx - HW // 2, cy - HH // 2
    f.nodes["여행 기록"] = (hx, hy, HW, HH, "rect")

    def ang(px, py):
        return math.atan2(py - cy, px - cx)

    def hits(r):
        x, y, w, h = r
        out = []
        for xe in (x, x + w):
            d = R * R - (xe - cx) ** 2
            if d >= 0:
                for s in (1, -1):
                    yy = cy + s * math.sqrt(d)
                    if y <= yy <= y + h:
                        out.append((xe, yy))
        for ye in (y, y + h):
            d = R * R - (ye - cy) ** 2
            if d >= 0:
                for s in (1, -1):
                    xx = cx + s * math.sqrt(d)
                    if x <= xx <= x + w:
                        out.append((xx, ye))
        return out

    def norm(a):
        while a <= -math.pi:
            a += 2 * math.pi
        while a > math.pi:
            a -= 2 * math.pi
        return a

    ent, ext = [], []
    for k, r in enumerate(rects):
        th = math.radians(-90 + k * 360 / N)
        hs = hits(r)
        after = min(hs, key=lambda p: norm(ang(*p) - th) if norm(ang(*p) - th) > 0 else 9)
        before = min(hs, key=lambda p: -norm(ang(*p) - th) if norm(ang(*p) - th) < 0 else 9)
        ext.append(after)
        ent.append(before)
    arcs = []
    for k in range(N):
        j = (k + 1) % N
        a0 = ang(*ext[k])
        over = (1.6 if j == 0 else 1.2) / R
        pe = ang(*ent[j]) - over
        qx, qy = cx + R * math.cos(pe), cy + R * math.sin(pe)
        col, mk, sw = (ACCENT, "arrow-accent", 1.6) if j == 0 else (MUTED, "arrow", 1.2)
        if j == 0:
            f.accents += 1
        f.raw_paths.append(f'<path d="M{ext[k][0]:.3f} {ext[k][1]:.3f} A{R} {R} 0 0 1 {qx:.3f} {qy:.3f}" fill="none" '
                           f'stroke="{col}" stroke-width="{sw}" marker-end="url(#{mk})"/>')
        arcs.append((a0, ang(*ent[j])))

    # 되돌아가는 호(알림 → 낮 감시) 이름표 — 원 밖, 상자와 안 겹치게
    a0, a1 = arcs[N - 1]
    if a1 < a0:
        a1 += 2 * math.pi
    mid = (a0 + a1) / 2
    txt = "다음 1분 주기"
    lw = up4(tw(txt, 12) + 8)
    ux, uy = math.cos(mid), math.sin(mid)
    D = R + 8 + abs(ux) * lw / 2 + abs(uy) * 8
    lx, ly = cx + D * ux - lw / 2, cy + D * uy - 8
    lx, ly = int(lx // 4 * 4), int(ly // 4 * 4)
    f.labels.append(dict(rect=(lx, ly, lw, 16), path="(arc)", text=txt,
                         svg=f'<rect x="{lx}" y="{ly}" width="{lw}" height="16" rx="2" fill="{PAPER}"/>'
                             f'<text x="{lx + lw / 2:g}" y="{ly + 12}" class="lab" fill="{ACCENT}">{txt}</text>'))

    # 쓰기 방사선(점선) — 감시 · 반영 · 알림만 (실제로 기록을 남기는 곳)
    spokes = {0: "Case 열기", 3: "새 버전 저장", 4: "발송 기록"}
    for k, txt in spokes.items():
        x, y, w, h = rects[k]
        Px, Py = x + w / 2, y + h / 2
        L = math.hypot(Px - cx, Py - cy)
        ux, uy = (Px - cx) / L, (Py - cy) / L

        def bd(hw, hh):
            return min(hw / abs(ux) if abs(ux) > 1e-9 else 1e9, hh / abs(uy) if abs(uy) > 1e-9 else 1e9)
        sx, sy = Px - bd(w / 2, h / 2) * ux, Py - bd(w / 2, h / 2) * uy
        dh = bd(HW / 2, HH / 2) + 6
        ex, ey = cx + dh * ux, cy + dh * uy
        f.raw_paths.append(f'<path d="M{sx:.3f} {sy:.3f} L{ex:.3f} {ey:.3f}" fill="none" stroke="{SOFT}" stroke-width="1" '
                           f'stroke-dasharray="5,4" marker-end="url(#arrow-soft)"/>')
        lw = up4(tw(txt, 12) + 8)
        mx, my = (sx + ex) / 2, (sy + ey) / 2
        nx, ny = -uy, ux
        if nx < 0 or (abs(nx) < 1e-9 and ny < 0):
            nx, ny = -nx, -ny
        D = 8 + abs(nx) * lw / 2 + abs(ny) * 8
        lx, ly = mx + nx * D - lw / 2, my + ny * D - 8
        lx, ly = int(round(lx / 4) * 4), int(round(ly / 4) * 4)
        # 선과의 거리 확인(표본)
        dmin = 1e9
        for t in range(101):
            qx, qy = sx + (ex - sx) * t / 100, sy + (ey - sy) * t / 100
            ddx = max(lx - qx, 0, qx - (lx + lw))
            ddy = max(ly - qy, 0, qy - (ly + 16))
            dmin = min(dmin, math.hypot(ddx, ddy))
        if dmin < 6:
            f.errors.append(f"방사선 이름표가 선에 붙음 「{txt}」 {dmin:.1f}")
        f.labels.append(dict(rect=(lx, ly, lw, 16), path="(spoke)", text=txt,
                             svg=f'<rect x="{lx}" y="{ly}" width="{lw}" height="16" rx="2" fill="{PAPER}"/>'
                                 f'<text x="{lx + lw / 2:g}" y="{ly + 12}" class="lab" fill="{SOFT}">{txt}</text>'))

    # 들어오는 곳 — 등록된 여행이 감시 대상이 된다
    x0, y0, w0, h0 = rects[0]
    f.path("in", [(cx, 24), (cx, y0)], None, "낮 감시", color="muted", dash="5,4")
    f.label("in", cx + 8, 40, "등록된 여행부터", anchor="left")

    f.node_svg.append(f'<rect x="{hx}" y="{hy}" width="{HW}" height="{HH}" rx="8" fill="{INK}"/>'
                      f'<text x="{cx}" y="{cy - 8}" class="hub-name">여행 기록 (DB)</text>'
                      f'<text x="{cx}" y="{cy + 16}" class="hub-sub">Case · 일정 버전 · 발송 기록</text>')
    f.legend(H - 48, [("backend", "단계"), ("focal", "핵심 판단"), ("hub", "쌓이는 기록"),
                      ("line:muted", "순서"), ("line:accent", "되돌아감"), ("dash:soft", "기록 남김")])
    return f


# ---------------------------------------------------------------- 2. 전체 구조 (Architecture)
def fig_arch():
    W, H = 1200, 1100
    f = Fig("tp-arch", W, H, "guguroute 전체 구조 — 들어오는 세 길과 하나의 반영",
            "여행자가 모바일 웹앱으로 계획을 올리거나 채팅하면 API 서버가 받는다. 계획은 등록 판정을 거쳐 감시 대상이 되고, "
            "낮 감시가 연 Case 는 오케스트레이터가 요식 또는 액티비티 에이전트에 맡긴다. 채팅과 새벽 점검은 에이전트를 거치지 않는다. "
            "세 길 모두 같은 검증 · 반영을 거쳐 알림과 계획서 링크로 여행자에게 돌아가고, 감시는 다음 1분 주기에 다시 돈다.")
    L, M, Rr, BW, BH = 40, 440, 840, 320, 96
    f.box("여행자", M, 40, BW, BH, kind="input", title="여행자 · 모바일 웹앱", tag="WEB",
          io=[("I", "판정 통과 일정 · 알림 · 계획서 링크"), ("O", "계획 원문 · 채팅 · 다른 안 고르기")])
    f.box("API", M, 176, BW, BH, title="API 서버 (FastAPI)", tag="REST",
          io=[("I", "HTTP 요청 + 브라우저 키"), ("O", "JSON 응답 · 진행 신호(SSE)")])
    f.box("채팅", L, 328, BW, BH, title="채팅 창구 (TripDesk)", tag="CHAT",
          io=[("I", "바꿔 줘 · 늦어요 · 다른 안 · 되돌리기"), ("O", "변경 · 제안 · 답변")])
    f.box("계획", M, 328, BW, BH, title="계획 읽기 · 등록 판정", tag="INTAKE",
          io=[("I", "계획 원문 (글 · 사진 · 파일)"), ("O", "등록 + 링크 / 거절 + 고칠 방법")])
    f.box("감시", Rr, 328, BW, BH, title="감시 작업 (낮 1분 · 새벽)", tag="JOB",
          io=[("I", "앞 90분 항목 · 외부 6범주"), ("O", "깨진 항목 → Case 1건")])
    f.box("오케", Rr, 472, BW, BH, kind="focal", title="오케스트레이터", tag="SUPERVISOR",
          io=[("I", "Case (문제 코드 · 원인)"), ("O", "담당 1개 · 허용 툴 · 90초")])
    f.box("에이전트", Rr, 616, BW, BH, title="에이전트 — 요식 · 액티비티", tag="AGENT",
          io=[("I", "할 일 · 컨텍스트 · 툴 결과"), ("O", "변경 제안 / 그대로 / 못 함")])
    f.box("검증", M, 760, BW, BH, title="검증 · 반영", tag="VERIFY",
          io=[("I", "변경 제안 (세 길 모두)"), ("O", "새 일정 버전 / 묻기 / 거부")])
    f.box("알림", M, 904, BW, BH, title="알림 워커 → Discord", tag="OUTBOX",
          io=[("I", "등록 · 변경 · 묻기 · 정기 안내"), ("O", "Discord 알림 + 최신 계획서 링크")])

    f.path("a1", [(600, 136), (600, 176)], "여행자", "API")
    f.label("a1", 608, 148, "앱 요청", anchor="left")
    f.path("a2", [(560, 272), (560, 300), (200, 300), (200, 328)], "API", "채팅")
    f.label("a2", 300, 276, "채팅")
    f.path("a3", [(640, 272), (640, 328)], "API", "계획")
    f.label("a3", 648, 292, "계획 원문", anchor="left")
    f.path("a4", [(760, 376), (840, 376)], "계획", "감시")
    f.label("a4", 800, 352, "등록됨")
    f.path("a5", [(1000, 424), (1000, 472)], "감시", "오케")
    f.label("a5", 1008, 440, "Case 1건", anchor="left")
    f.path("a6", [(1000, 568), (1000, 616)], "오케", "에이전트")
    f.label("a6", 1008, 584, "할 일 · 허용 툴", anchor="left")
    f.path("a7", [(1000, 712), (1000, 808), (760, 808)], "에이전트", "검증")
    f.label("a7", 880, 784, "변경 제안")
    f.path("a12", [(840, 404), (800, 404), (800, 728), (640, 728), (640, 760)], "감시", "검증", dash="5,4")
    f.label("a12", 624, 552, "새벽 03~08시 · 직접 계산", anchor="left")
    f.path("a8", [(200, 424), (200, 808), (440, 808)], "채팅", "검증", dash="5,4")
    f.label("a8", 320, 784, "같은 계산 · 같은 반영")
    f.path("a9", [(600, 856), (600, 904)], "검증", "알림")
    f.label("a9", 608, 872, "새 버전 · 묻기", anchor="left")
    f.path("a10", [(440, 952), (20, 952), (20, 88), (440, 88)], "알림", "여행자", color="link")
    f.label("a10", 300, 928, "알림 + 계획서 링크")
    f.path("a11", [(760, 952), (1184, 952), (1184, 376), (1160, 376)], "알림", "감시", color="accent")
    f.label("a11", 1080, 928, "다음 1분 주기 · 다시 감시")

    f.legend(H - 56, [("input", "사람 · 화면"), ("backend", "서버 처리"), ("focal", "배정"),
                      ("line:muted", "처리 흐름"), ("dash:muted", "에이전트 안 거침"),
                      ("line:link", "여행자에게 감"), ("line:accent", "되돌아가는 루프")])
    return f


# ---------------------------------------------------------------- 3. 에이전트 안쪽 루프 (Flowchart)
def fig_agent():
    W, H = 960, 820
    f = Fig("tp-agent", W, H, "에이전트 안쪽 루프 — 통과할 때까지 다음 후보를 다시 점검",
            "에이전트는 지금 항목을 다시 점검해 문제 없음이면 그대로 두고, 확인이 안 되면 기록만 남기고, 깨졌으면 후보를 하나씩 점검한다. "
            "더 볼 후보가 있으면 다시 돌아가고, 다 본 뒤 통과한 곳이 있으면 최선 1곳과 다른 안 최대 2곳을 변경 제안으로 낸다.")
    f.oval("시작", 360, 40, 240, 56, title="할 일 받음", lines=["Case · 허용 툴 · 시간 제한 90초"])
    f.diamond("d1", 480, 176, 200, 96, "지금 상태?")
    f.oval("그대로", 80, 148, 200, 56, title="그대로 둔다", lines=["일정 안 바뀜"])
    f.oval("실패", 680, 148, 200, 56, title="기록만 남김", lines=["일정 그대로"])
    f.box("후보", 320, 272, 320, 80, kind="focal", title="다음 후보 1곳 점검",
          lines=["영업 · 거리 · 조건 + 같은 외부 점검", "요식은 순위순 최대 3곳"])
    f.diamond("d2", 480, 440, 200, 96, "더 볼 후보?")
    f.diamond("d3", 480, 584, 200, 96, "통과한 곳 있나?")
    f.oval("못함", 80, 556, 200, 56, title="못 함 · 일정 유지")
    f.oval("제안", 320, 680, 320, 64, title="변경 제안 → 검증으로", lines=["최선 1곳 + 다른 안 최대 2곳"])

    f.path("b1", [(480, 96), (480, 128)], "시작", "d1")
    f.path("b2", [(380, 176), (280, 176)], "d1", "그대로")
    f.label("b2", 332, 152, "문제 없음")
    f.path("b3", [(580, 176), (680, 176)], "d1", "실패")
    f.label("b3", 632, 152, "확인 안 됨")
    f.path("b4", [(480, 224), (480, 272)], "d1", "후보")
    f.label("b4", 488, 240, "깨짐", anchor="left")
    f.path("b5", [(480, 352), (480, 392)], "후보", "d2")
    f.path("b6", [(580, 440), (720, 440), (720, 312), (640, 312)], "d2", "후보", color="accent")
    f.label("b6", 728, 368, "예 · 다음 후보로", anchor="left")
    f.path("b7", [(480, 488), (480, 536)], "d2", "d3")
    f.label("b7", 488, 504, "아니오 · 다 봤음", anchor="left")
    f.path("b8", [(380, 584), (280, 584)], "d3", "못함")
    f.label("b8", 332, 560, "아니오")
    f.path("b9", [(480, 632), (480, 680)], "d3", "제안")
    f.label("b9", 488, 648, "예", anchor="left")
    f.legend(H - 48, [("oval:external", "시작 · 끝"), ("backend", "단계"), ("diamond", "판단"),
                      ("line:muted", "갈래"), ("line:accent", "안쪽 루프")])
    return f


# ---------------------------------------------------------------- 4. 검증 · 묻기 (Flowchart)
def fig_verify():
    W, H = 1000, 800
    f = Fig("tp-verify", W, H, "검증 · 묻기 루프 — 고객이 고르면 다시 검증한다",
            "변경 제안이 오면 고객 소유 · Case 버전 · 여행 기준 버전 · 항목 · 장소를 검증한다. 통과하지 못하면 거부하고, "
            "보호 일정처럼 물어볼 일정이면 고객에게 묻고 응답을 받아 다시 검증한다. 물어볼 일이 아니면 새 일정 버전을 저장하고 알림과 링크를 보낸다.")
    f.oval("시작", 400, 40, 240, 56, title="변경 제안 도착", lines=["에이전트 · 채팅 · 새벽 점검"])
    f.box("검증", 360, 128, 320, 80, title="검증", lines=["고객 소유 · Case 버전 · 여행 기준 버전", "항목 · 장소가 그대로인가"])
    f.diamond("d1", 520, 288, 200, 96, "검증 통과?")
    f.oval("거부", 760, 260, 200, 56, title="거부", lines=["일정 그대로 · 이유 기록"])
    f.diamond("d2", 520, 432, 200, 96, "물어볼 일정?")
    f.box("묻기", 40, 384, 280, 96, title="고객에게 묻기",
          lines=["보호 일정 · 「먼저 물어봐」", "날씨만 걸리고 실내 모름 → 바꿀까요?", "안전 경보면 안전 알림"])
    f.box("응답", 40, 528, 280, 64, kind="input", title="고객 응답", lines=["다른 안 고르기 · 그대로 두기"])
    f.box("새버전", 360, 528, 320, 72, kind="focal", title="새 일정 버전 저장", lines=["이전 판 보존 · 앞뒤 이동 재계산"])
    f.oval("알림", 380, 640, 280, 64, title="알림 + 계획서 링크", lines=["Discord · 첫 발송 포함 최대 3회"])

    f.path("c1", [(520, 96), (520, 128)], "시작", "검증")
    f.path("c2", [(520, 208), (520, 240)], "검증", "d1")
    f.path("c3", [(620, 288), (760, 288)], "d1", "거부")
    f.label("c3", 688, 264, "아니오")
    f.path("c4", [(520, 336), (520, 384)], "d1", "d2")
    f.label("c4", 528, 352, "예", anchor="left")
    f.path("c5", [(420, 432), (320, 432)], "d2", "묻기")
    f.label("c5", 372, 408, "예")
    f.path("c6", [(180, 480), (180, 528)], "묻기", "응답")
    f.path("c7", [(40, 560), (24, 560), (24, 168), (360, 168)], "응답", "검증", color="accent")
    f.label("c7", 200, 144, "다시 검증")
    f.path("c8", [(520, 480), (520, 528)], "d2", "새버전")
    f.label("c8", 528, 496, "아니오", anchor="left")
    f.path("c9", [(520, 600), (520, 640)], "새버전", "알림")
    f.legend(H - 48, [("oval:external", "시작 · 끝"), ("backend", "단계"), ("input", "고객"), ("diamond", "판단"),
                      ("line:muted", "갈래"), ("line:accent", "묻기 루프")])
    return f


# ---------------------------------------------------------------- 5. 툴 · 데이터 층 (Layer stack)
def fig_layers():
    W, H = 1000, 640
    f = Fig("tp-layers", W, H, "에이전트 · 툴 · 데이터 층 — 에이전트는 허용된 툴로만 읽는다",
            "위에서부터 에이전트, 툴 레이어(허용 목록), 공용 이동 판정 툴, PostgreSQL, 외부 데이터 6범주와 이동 자료가 쌓여 있다. "
            "에이전트는 DB 와 외부 API 를 직접 열지 않고 툴 레이어를 거쳐 조회하며, 툴은 근거와 판정을 돌려준다.")
    X, Wd, Hh, Y0 = 120, 800, 88, 72
    rows = [
        ("01 · AGENT", "에이전트 — 요식 · 액티비티", "DB · 외부 API 를 직접 열지 않는다 — 허용된 툴만 부른다",
         [("mono", "dining · activity"), ("kr", "에이전트끼리 직접 부르지 않는다")], False),
        ("02 · TOOLS", "툴 레이어 (허용 목록)", "목록 밖 거부 · 같은 툴 · 같은 인자 재호출 거부 · 12회 넘으면 멈춤",
         [("mono", "read.itinerary · read.disruptions"), ("mono", "read.dining_state · read.dining_alternatives"),
          ("mono", "read.place_catalog · read.policy")], True),
        ("03 · SHARED", "이동 판정 툴 (공용 · 에이전트 아님)", "두 장소 · 목표 도착 → 경로 · 소요 · 성립 / 불가 / 모름",
         [("kr", "반영할 때 앞뒤 이동 재계산"), ("kr", "후보 재점검 연결은 아직 · 코드엔 팀 등록")], False),
        ("04 · DB", "PostgreSQL + pgvector", "여행 · 일정 버전(이전 판 보존) · Case · 실행 기록",
         [("kr", "장소 · 요식 원장 · 규정 조각 + 임베딩"), ("kr", "bge-m3 (로컬 기본 · 설정으로 선택)")], False),
        ("05 · EXTERNAL", "외부 데이터 6범주 + 이동 자료", "기상 · 특보 · 지진 · 재난문자 · 교통(ITS+UTIC) · 대기질",
         [("kr", "지하철 시간표 · 버스 노선 444,915행"), ("kr", "대체 소스는 일부 범주만")], False),
    ]
    s = []
    bottom = Y0 + Hh * len(rows)
    # 방향 표시(왼쪽 여백)
    s.append(f'<line x1="56" y1="{Y0 + 8}" x2="56" y2="{bottom - 12}" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    s.append(f'<line x1="88" y1="{bottom - 8}" x2="88" y2="{Y0 + 12}" stroke="{SOFT}" stroke-width="1" stroke-dasharray="5,4" marker-end="url(#arrow-soft)"/>')
    s.append(f'<text x="56" y="{Y0 - 16}" class="lab" fill="{MUTED}">조회</text>')
    s.append(f'<text x="88" y="{bottom + 28}" class="lab" fill="{SOFT}">근거 · 판정</text>')
    for i, (tag, name, note, right, focal) in enumerate(rows):
        y = Y0 + Hh * i
        fill = ACCENT_TINT if focal else ("#ffffff" if i % 2 == 0 else "#f1f4f8")
        s.append(f'<rect x="{X}" y="{y}" width="{Wd}" height="{Hh}" fill="{fill}"/>')
        s.append(f'<text x="{X + 16}" y="{y + 20}" class="tag" text-anchor="start" style="text-anchor:start" fill="{ACCENT if focal else SOFT}">{tag}</text>')
        s.append(f'<text x="{X + 16}" y="{y + 48}" class="layer-name"{" fill=" + chr(34) + ACCENT + chr(34) if focal else ""}>{escape(name)}</text>')
        s.append(f'<text x="{X + 16}" y="{y + 72}" class="layer-note">{escape(note)}</text>')
        if tw(name, 16) > 424 or tw(note, 12) > 424:
            f.errors.append(f"층 글자 넘침 {name}")
        n = len(right)
        y1 = y + Hh / 2 - (n - 1) * 9 + 4
        for j, (kind, t) in enumerate(right):
            cls = "layer-tech" if kind == "mono" else "layer-note"
            s.append(f'<text x="{X + 448}" y="{y1 + 18 * j:g}" class="{cls}">{escape(t)}</text>')
            if tw(t, 12, mono=kind == "mono") > Wd - 448 - 16:
                f.errors.append(f"층 오른쪽 글자 넘침 「{t}」 {tw(t, 12, kind == 'mono'):.0f}")
        if i:
            s.append(f'<line x1="{X}" y1="{y}" x2="{X + Wd}" y2="{y}" stroke="{RULE}" stroke-width="1"/>')
    s.append(f'<rect x="{X}" y="{Y0 + Hh}" width="{Wd}" height="{Hh}" fill="none" stroke="{ACCENT}" stroke-width="1.2"/>')
    s.append(f'<rect x="{X}" y="{Y0}" width="{Wd}" height="{Hh * len(rows)}" fill="none" stroke="{INK}" stroke-width="1"/>')
    f.accents += 1
    f.node_svg.append("\n".join(s))
    f.legend(H - 48, [("backend", "층"), ("focal", "에이전트가 닿는 유일한 문"),
                      ("line:muted", "조회 방향"), ("dash:soft", "돌려주는 근거")])
    return f


ALL = [("그림1_바깥루프", fig_loop), ("그림2_전체구조", fig_arch), ("그림3_에이전트_안쪽루프", fig_agent),
       ("그림4_검증_묻기루프", fig_verify), ("그림5_툴_데이터층", fig_layers)]
