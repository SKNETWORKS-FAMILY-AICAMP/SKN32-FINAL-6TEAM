# -*- coding: utf-8 -*-
"""4차 v2 — 팀별(이동 · 액티비티 · 요식업) 내용.

★이 파일의 수치는 전부 【팀 보고】다. 이번 작성에서 재실행하지 않았고, 아래 출처(브랜치:경로 또는 커밋)에서 읽었다.
  파일을 직접 읽거나 직접 센 값은 「파일」, 커밋 메시지·문서 서술에서만 본 값은 「커밋」이라고 적는다.
  ★09-17 통합 검토본(팀원이 Drive 에 올린 판)의 값은 「09-17 검토본」이라고 적는다. 그 뒤로 바뀐 것은 바뀐 값만 넣는다.
  ★찾지 못한 것은 「없다」가 아니라 「찾은 범위 안에서 못 찾았다」로 적는다.
"""

# ════════════════════════════════════════════════════════════════
# 요식업(dining) — 브랜치 team/role-dining (team/develop 과 같다)
# ════════════════════════════════════════════════════════════════
DINING = dict(
    tourapi_list=990, tourapi_intro=989, tourapi_added=789, intervals=(966, 989), rules=407,
    ledger=[("TourAPI 소개정보 받은 곳", 989), ("+ 비건 목록(신규)", 67), ("+ 할랄 시트", 24), ("+ 미쉐린(신규)", 145)],
    ledger_total=1225,
    truth_before=87.0, truth_after=99.0, truth_fixed=12, truth_broken=0,
    sample=200,
    fill=dict(interval=92.5, break_=32.5, last_order=47.0, closed_rule=37.0),
    closed_split=dict(none=121, present=73, unknown=6),
    e5=dict(base="intfloat/multilingual-e5-small", train=770, test=173, scored=157, epochs=3, batch=32, lr="2e-5", temp=0.05, secs=365,
            loss=(2.2695, 1.7685, 1.5544),
            rule=dict(top3=0.767, missing="11/157"),
            raw=dict(top3=0.873, missing="0/157", notag=0.758, hit1=0.265, hit5=0.519, mrr=0.373),
            tuned=dict(top3=0.915, missing="0/157", notag=0.818, hit1=0.290, hit5=0.630, mrr=0.437), notag_n=11),
    michelin=dict(total=180, star=42, bib=51, selected=87, matched=35, new=145, ledger_before=1080, ledger_after=1225),
    halal=dict(rows=24, licensed=23),
    vegan=dict(rows=70, new=67, unknown_cat=61),
    nokids=dict(yes=5, no=0, unknown=984, sheet=218),
)

DINING_SRC = ("team/role-dining 의 커밋 본문·README·정답셋 파일(2026-09-28 확인, e85e2ce8까지). "
              "인허가 원본 규모(685,389행 등)는 09-17 검토본의 값이다.")

# ════════════════════════════════════════════════════════════════
# 액티비티(activity) — 브랜치 team/role-activity
# ════════════════════════════════════════════════════════════════
ACTIVITY = dict(
    baseline=dict(datalab=100, merged=66, auto=58, unmatched=8, manual=5, hold=3, clean=63),      # 09-17 검토본(담당자 보고)
    merged_total=1173, tour=805, oliveyoung=368,
    final_total=2_466, final_tour=1_921, final_shops=545,        # 액티비티 담당 보고(w4 「엑티비티 반영」 문서, 2026-09-28)
    crawled=dict(oliveyoung=368, musinsa=53, daiso=196, artbox=59),
    stores=dict(oliveyoung=368, musinsa=53, daiso=196, artbox=59), enriched=dict(daiso=54, artbox=24),
    review=dict(match=20, same=19, different=1, tourapi_only=26, curated=24),
    lcls={"VE": 383, "SH": 139, "HS": 121, "EX": 46, "NA": 42, "EV": 40, "LS": 34},
    seoul_addr=(804, 805), out_of_box=10, ev_excluded_left=765,
    hours=(726, 805), closed=(673, 805), missing=dict(business_hours=79, closed_days=302, fee=975, overview=369),
)
ACTIVITY_SRC = ("team/role-activity:final_project_cs/app/modules/travel_ops/activity/data_processing/ 의 CSV 를 직접 셈(2026-09-28), "
                "커밋 87222daa·58a03c88·2af524ab. 09-17 검토본의 값은 따로 표시한다.")
