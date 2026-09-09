"""멈춘 Case 를 되잡는다: python -m scripts.run_sweepers --once

    --once      한 번 돌고 끝난다(cron·수동 실행용). 기본값이다.
    --interval  N 초마다 되돌린다(상주 실행용).
    --only      classifying | routing 중 하나만 돌린다.

★두 sweeper 는 경계를 나누며 생긴 틈을 막는 장치다:

    분류를 Case 생성 트랜잭션 밖으로  →  `classifying` 잔류
    실행을 접수 응답 뒤로              →  `routing` 잔류

  자세한 경위는 `wiki/records/reports/2026-09-03_경계를_나누며_생긴_틈과_승인이_막혀있던_제안.md`.

★**돌리는 주기는 이 파일이 정하지 않는다.** 임계값은
  `config/guardrails.yaml` 의 `reliability.*_stuck_after_seconds` 이고, 얼마나
  자주 부를지는 운영이 정한다. 기본 `--once` 인 이유가 그것이다 — 상주 루프를
  기본으로 두면 "언제 도는지" 가 코드에 숨는다.

★출력은 JSON 한 줄이다. `run_daily_feedback` 과 같은 관례이며, 세는 칸을 그대로
  낸다 — 특히 `errored` 는 **아무것도 기록하지 못한** 수라서 다음 회차에 또
  걸린다. 0 이 아니면 사람이 봐야 한다.

★**그 "사람이 봐야 한다" 를 실제로 전달한다**(2026-09-07). 전에는 세어서 찍기만
  하고 **exit 0** 이었다 — cron 에 걸어 두면 실패가 로그 속에만 남아 아무도 안
  본다. 세는 것과 알리는 것은 다르다(`CLAUDE.md` §3).

    --once      `errored` 가 있으면 **exit 1**. cron 이 실패로 본다
    --interval  **죽지 않는다.** 상주 sweeper 가 첫 실패에 멈추면 되잡기 자체가
                멈춘다 — 대신 stderr 로 알리고 계속 돈다

  어느 쪽이든 사유는 **stderr** 로 나간다. stdout 은 JSON 한 줄이라는 계약을
  지켜야 파이프로 받아 쓰는 쪽이 안 깨진다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from app.application.classification_sweeper import sweep_stuck_classifying
from app.application.routing_sweeper import sweep_stuck_routing
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection


def _run_once(tenant_id: str, only: str | None) -> dict[str, dict[str, int]]:
    from app import composition

    result: dict[str, dict[str, int]] = {}
    if only in (None, "classifying"):
        classifier = composition.build_classifier()
        with get_connection() as conn:
            result["classifying"] = sweep_stuck_classifying(
                conn, tenant_id=tenant_id, classifier=classifier, actor_id="sweeper")
    if only in (None, "routing"):
        controller = composition.build_controller()

        def run_case(*, tenant_id: str, case_id, actor_id: str):
            # ★Controller 의 run_case 는 coroutine 이다. sweeper 는 동기 루프라
            #   여기서 돌려 준다 — sweeper 가 asyncio 를 알 필요가 없다.
            import asyncio

            return asyncio.run(controller.run_case(
                tenant_id=tenant_id, case_id=case_id, actor_id=actor_id))

        with get_connection() as conn:
            result["routing"] = sweep_stuck_routing(
                conn, tenant_id=tenant_id, run_case=run_case, actor_id="sweeper")
    return result


def _report_errors(result: dict[str, dict[str, int]]) -> int:
    """`errored` 를 stderr 로 알리고 총합을 돌려준다.

    ★`errored` 와 `failed` 는 다르다. `failed` 는 실패를 **기록까지 한** 것이라
      Case 가 escalated 로 넘어가 사람 손에 들어간다. `errored` 는 아무것도
      기록하지 못한 것이라 Case 가 그 상태에 그대로 남고 **다음 회차에 또 걸린다** —
      아무도 안 보면 영원히 돈다.
    """
    total = 0
    for name, counts in sorted(result.items()):
        errored = int(counts.get("errored", 0))
        if errored:
            total += errored
            print(f"★{name} sweeper: errored={errored} · scanned={counts.get('scanned')} "
                  f"— 아무것도 기록하지 못했다. 다음 회차에 또 걸린다",
                  file=sys.stderr, flush=True)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--interval", type=int, default=None,
                        help="N 초마다 반복한다. 주면 --once 를 덮는다")
    parser.add_argument("--only", choices=("classifying", "routing"), default=None)
    args = parser.parse_args()

    tenant_id = get_settings().tenant_id
    if args.interval is None:
        result = _run_once(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # ★한 번 돌고 끝나는 모드는 exit code 가 유일한 신호다. cron 이 이걸 본다.
        return 1 if _report_errors(result) else 0

    # ★상주 모드에서도 한 회차의 결과를 그때그때 낸다. 다 끝나고 모아 내면
    #   중간에 죽었을 때 아무 기록도 안 남는다.
    while True:
        result = _run_once(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        # ★여기서는 **끝내지 않는다.** 상주 sweeper 가 첫 실패에 멈추면 되잡기
        #   자체가 멈춘다 — 멈춘 Case 를 되잡는 장치가 멈추는 것이 더 나쁘다.
        _report_errors(result)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
