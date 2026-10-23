"""DB 에 쌓인 **숙소 · 항공 팀으로 간 고객 문장**을 뽑아, 해석 시험(`scripts/interpret_cases.json`)에 넣을 후보로 만든다. `[2026-10-10]`

- 읽기만 한다(`get_ops_read_connection` — 읽기 전용 계정이 있으면 그것). 쓰지 않는다.
- 뽑는 것: `customer_cases.subject`(고객이 처음 보낸 문장) 중 그 Case 의 팀 작업(`team_tasks.team_id`)이나 담당 팀
  (`owner_team_id`)이 lodging · flight 인 것. 같은 문장은 하나만. 고객 · Case 번호는 뽑지 않는다.
- 전화번호 · 이메일 모양은 가린다(`***`). 그 밖의 개인정보가 섞였는지는 **사람이 보고** 지운다 — 파일을 채팅에 붙이기 전에 확인할 것.
- 결과는 저장소 밖 `../output/interpret_samples_<날짜>.json`(git 이 추적하지 않는 폴더)에 쓴다. 정답(expect)은 비어 있다 —
  사람이 채운 뒤 `interpret_cases.json` 에 `"set": "real"` 로 옮긴다.

실행 위치: final_project_cs (로컬 DB 가 켜져 있어야 한다)
  python -m scripts.collect_interpret_samples            # 최근 200건까지
  python -m scripts.collect_interpret_samples --limit 50
"""
from argparse import ArgumentParser
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

TEAMS = ("lodging", "flight")
_PHONE = re.compile(r"\d{2,4}[- ]?\d{3,4}[- ]?\d{4}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

QUERY = """
SELECT c.subject, coalesce(t.team_id, c.owner_team_id) AS team, max(c.created_at) AS at
FROM customer_cases c
LEFT JOIN agent_runs r ON r.case_id = c.case_id
LEFT JOIN team_tasks t ON t.run_id = r.run_id
WHERE coalesce(t.team_id, c.owner_team_id) = ANY(%s)
GROUP BY c.subject, coalesce(t.team_id, c.owner_team_id)
ORDER BY at DESC
LIMIT %s
"""


def mask(text: str) -> str:
    return _EMAIL.sub("***", _PHONE.sub("***", text))


def main():
    from app.infrastructure.db.session import get_ops_read_connection

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    with get_ops_read_connection() as conn, conn.cursor() as cur:
        cur.execute(QUERY, (list(TEAMS), args.limit))
        rows = cur.fetchall()
    seen, samples = set(), {team: [] for team in TEAMS}
    for subject, team, at in rows:
        text = mask(" ".join(str(subject or "").split()))
        if not text or (team, text) in seen:
            continue
        seen.add((team, text))
        samples[team].append({"text": text, "at": at.isoformat() if at else None, "set": "real", "expect": {}})
    out = Path("..", "output", f"interpret_samples_{now:%Y%m%d_%H%M}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"collected_at": now.isoformat(timespec="seconds"), **samples}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"숙소 {len(samples['lodging'])}문장 · 항공 {len(samples['flight'])}문장 → {out.resolve()}")
    for team in TEAMS:
        for item in samples[team][:10]:
            print(f"  [{team}] {item['text']}")


if __name__ == "__main__":
    main()
