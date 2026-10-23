"""코어가 요식 원장을 제대로 쓰게 됐는지, 한 브랜치의 코드를 보고 확인한다.

    python scripts/dining/check_core_integration.py                 origin/develop 을 본다
    python scripts/dining/check_core_integration.py --ref origin/x  다른 브랜치를 본다

2026-09-29 「요식 → 코어 통합」 문서의 여덟 항목과, 요식이 코어에 부탁한 연결 셋을 본다.
코드에 흔적이 있는지만 본다(git grep). 동작까지 맞는지는 rebuild · check_dining 으로 따로 본다.
받기 전에 git fetch 를 한다. 받지 못하면 로컬에 있는 ref 로 본다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = "final_project_cs/"

#: (번호, 무엇, 볼 파일(경로 앞부분), 있으면 됐다고 볼 패턴, 없어야 됐다고 볼 패턴)
CHECKS = [
    ("1", "같은 이름이 둘이어도 코어 장소에 들어간다", "app/infrastructure/db/migrations/",
     r"DROP INDEX[^;]*places_shared_name_kind_uq", None),   # 옛 유일 조건(029)을 걷어 내야 된 것
    ("2", "코어 장소가 요식 번호(place_uid)를 쓴다", "app/infrastructure/db/migrations/",
     r"place_uid", None),
    ("3", "일정 짜기 · 대체 판정이 영업시간을 요식 표에서 읽는다", "app/domains/travel_ops/",
     r"dining\.(open_at_slot|day_intervals|v_hours_rule_active)", None),
    ("6", "동행 조건 판정이 요식 속성을 읽는다", "app/domains/travel_ops/",
     r"dining\.(meets_condition|v_attribute_active)", None),
    ("7", "여행 등록이 요식 목록을 먼저 찾는다", "app/domains/travel_ops/components/intake/",
     r"dining\.|dn_place", None),
    ("8", "다시 적재가 코어 DB 를 지우지 않는다", "scripts/dining/rebuild.py",
     r"--target", None),
    ("제안 A", "휴무 · 지연 대안에 요식 원장 대안을 쓴다", "app/domains/travel_ops/components/itinerary/itinerary_changes.py",
     r"suggest_alternatives|alternative_pool", None),
    ("제안 B", "당일 점검(tick_once)을 코어가 부른다", "app/",
     r"tick_once", None),
    ("제안 C", "설문의 식이 조건을 요식 조건으로 옮긴다", "app/",
     r"conds_from_survey", None),
]

#: 요식 자기 파일은 「코어가 쓴다」의 근거가 아니다.
OWN = ("app/domains/travel_ops/instances/dining/", "app/infrastructure/db/migrations/2")


def grep(ref: str, pattern: str, path: str) -> list[str]:
    done = subprocess.run(["git", "grep", "-n", "-P", pattern, ref, "--", BASE + path],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    hits = []
    for line in done.stdout.splitlines():
        file = line.split(":", 2)[1].removeprefix(BASE)
        if not file.startswith(OWN) or path.startswith(OWN):
            hits.append(file)
    return sorted(set(hits))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/develop")
    ref = ap.parse_args().ref
    subprocess.run(["git", "fetch", "-q", "origin"], capture_output=True)
    head = subprocess.run(["git", "log", "-1", "--format=%h %cd %s", "--date=format:%m-%d %H:%M", ref],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    print(f"코어 통합 확인 — {ref}  ({head})\n")
    done = 0
    for no, what, path, need, forbid in CHECKS:
        if forbid:
            left = grep(ref, forbid, path)
            ok, note = not left, ("옛 유일 조건이 그대로" + f" ({left[0]})" if left else "옛 조건 없음")
        else:
            hits = grep(ref, need, path)
            ok, note = bool(hits), (", ".join(hits[:3]) if hits else "흔적 없음")
        done += ok
        print(f"  {'✅' if ok else '⬜'} {no:>5}  {what}\n           {note}")
    print(f"\n  {done}/{len(CHECKS)} 됨. 2 · 4 · 5 는 데이터 작업이라 코드로 다 볼 수 없다. DB 에서 따로 본다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
