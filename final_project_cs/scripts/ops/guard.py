"""상시 작업을 스케줄러에 걸 때 생기는 세 가지를 막는다 — 겹침 · 로그 적체 · 조용한 실패.

★`[2026-09-22]` 왜 셋인가. 1분마다 도는 작업을 걸면 이런 것들이 따라온다.

    (1) **겹침** — 한 회차가 1분을 넘기면 다음 회차가 겹쳐 뜬다. DB 는 잠금이 막아 주지만
        **바깥 API 는 안 막는다** — 같은 조회가 두 번 나가 하루 한도를 갉는다(재난문자는
        하루 100회 `[미확인]`). 그래서 **앞 회차가 살아 있으면 이번 회차는 건너뛴다.**
    (2) **로그 적체** — 날짜별 파일이 지우는 사람 없이 쌓인다.
    (3) **조용한 실패** — 스케줄러는 「마지막 결과」에만 적는다. 사람이 그 화면을 안 보면
        며칠이고 안 돈 채로 지난다(실제로 바깥함 일꾼이 4시간 넘게 그랬다).

★**건너뛴 것을 성공으로 적지 않는다.** 건너뜀은 `exit 0` 이지만 흔적에 `skipped` 로 남고,
  점검(`healthcheck`)은 그 시각을 「돌았다」로 읽지 않는다 — 겹침이 계속되면 실제로는
  아무 일도 안 하고 시각만 새로 찍히는 상태가 된다.

★**알림은 연속 실패에만, 그것도 한 번만 보낸다.** 1분마다 도는 작업이 실패하면 하루 1,440건이
  나간다. 연속 실패가 기준을 넘는 **그 회차에 한 번** 보내고, 성공하면 「돌아왔다」를 한 번 보낸다.
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: 연속 실패 몇 번째에 알리나. ★출처: **우리가 고른 값**이다 — 1분 주기에서 한 번의 실패는
#:  흔하고(DB 재기동·일시적 네트워크), 세 번 연속이면 사람이 봐야 하는 상태로 봤다.
ALERT_AFTER = 3
#: 로그를 며칠 두나. ★우리가 고른 값.
LOG_RETENTION_DAYS = 14
#: 앞 회차가 이보다 오래 잠금을 쥐고 있으면 죽은 것으로 본다(`tick` 의 회차 상한과 같다).
STALE_LOCK_SECONDS = 600


class Skipped(RuntimeError):
    """앞 회차가 아직 돌고 있다 — 이번 회차는 하지 않는다."""


def _alive(pid: int) -> bool:
    """그 프로세스가 아직 사는가. ★모르면 **살아 있다고 본다** — 겹쳐 도는 쪽이 더 나쁘다."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def only_one(lock_path: Path, *, stale_seconds: int = STALE_LOCK_SECONDS) -> Iterator[None]:
    """같은 작업이 겹쳐 돌지 않게 한다.

    ★잠금 파일에 **pid 와 시각**을 적는다. 파일만 있으면 「죽은 회차가 남긴 파일」과
      「지금 도는 회차」를 못 가른다 — 그 구분이 없으면 한 번 죽은 뒤 영영 안 돈다.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if lock_path.exists():
        try:
            held = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            held = {}
        pid, since = int(held.get("pid") or 0), float(held.get("since") or 0)
        age = now - since
        if _alive(pid) and age < stale_seconds:
            raise Skipped(f"앞 회차가 아직 돈다(pid {pid} · {age:.0f}초째) — 이번 회차는 건너뛴다")
        # ★죽었거나 너무 오래됐다. 빼앗되 **왜 빼앗았는지**를 남긴다.
        lock_path.unlink(missing_ok=True)
    lock_path.write_text(json.dumps({"pid": os.getpid(), "since": now}), encoding="utf-8")
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def prune_logs(log_dir: Path, *, keep_days: int = LOG_RETENTION_DAYS) -> list[str]:
    """오래된 로그를 지운다. 지운 이름을 돌려준다(조용히 지우지 않는다)."""
    if not log_dir.exists():
        return []
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = []
    for path in sorted(log_dir.glob("*.log")):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
                removed.append(path.name)
        except OSError:
            continue
    return removed


def _alert_state_path(state_dir: Path, job: str) -> Path:
    return state_dir / f"{job}.alert.json"


def note_result(state_dir: Path, job: str, *, exit_code: int, detail: str = "") -> dict[str, Any]:
    """연속 실패를 세고, **알릴 때인지** 판정한다. 알리는 일 자체는 하지 않는다(순수).

    돌려주는 것 — `{"streak": n, "should_alert": bool, "kind": "failing"|"recovered"|None}`
    """
    path = _alert_state_path(state_dir, job)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    streak = int(state.get("streak") or 0)
    alerted = bool(state.get("alerted"))

    kind = None
    if exit_code == 0:
        # ★「돌아왔다」는 **알린 적이 있을 때만** 보낸다 — 평소 성공에 알림이 나가면 안 본다.
        kind = "recovered" if alerted else None
        streak, alerted = 0, False
    else:
        streak += 1
        if streak >= ALERT_AFTER and not alerted:
            kind, alerted = "failing", True

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"streak": streak, "alerted": alerted, "detail": detail[:500],
                                "at": datetime.now().astimezone().isoformat(timespec="seconds")},
                               ensure_ascii=False), encoding="utf-8")
    return {"streak": streak, "should_alert": kind is not None, "kind": kind}


def send_alert(job: str, kind: str, *, streak: int, detail: str = "") -> str:
    """운영자에게 알린다. ★보낼 곳이 없으면 **보내지 않고 그렇게 돌려준다**(조용히 성공하지 않는다).

    ★이것은 **고객 통지가 아니라 운영 알림**이다. 바깥함(`outbox`)을 타지 않고 곧장 나간다 —
      바깥함이 안 도는 것을 알리는 것이 이 알림의 일이라 같은 길을 쓰면 알릴 수가 없다.
    """
    from app.core.settings import get_settings

    settings = get_settings()
    url = getattr(settings, "ops_alert_webhook_url", "") or settings.discord_webhook_url
    if not url:
        return "보낼 곳이 없다(ACOP_DISCORD_WEBHOOK_URL 이 비어 있다) — 알리지 않았다"
    if kind == "failing":
        text = (f"[A-COP 운영] **{job}** 가 {streak}회 연속 실패했습니다.\n"
                f"{detail[:300]}\n확인: `python -m scripts.ops.healthcheck`")
    else:
        text = f"[A-COP 운영] **{job}** 가 다시 정상으로 돌아왔습니다."
    try:
        import httpx

        response = httpx.post(url, json={"content": text}, timeout=8.0)
        if not 200 <= response.status_code < 300:
            return f"알림 실패: HTTP {response.status_code}"
    except Exception as exc:                      # 알림이 실패해도 작업 결과를 덮지 않는다
        return f"알림 실패: {type(exc).__name__}: {exc}"[:160]
    return "알림 보냄"


__all__ = ["ALERT_AFTER", "LOG_RETENTION_DAYS", "Skipped", "note_result", "only_one",
           "prune_logs", "send_alert"]
