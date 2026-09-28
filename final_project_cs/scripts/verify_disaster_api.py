"""행정안전부 긴급재난문자 API 실 키 첫 호출 검증.

★★disaster_msg.py 모듈 docstring의 「확인됨 / 추정」 구분을
  실제 응답으로 업데이트하기 위한 스크립트다.

    python -m scripts.verify_disaster_api

결과를 보고 disaster_msg.py 모듈 docstring을 갱신한다.
"""
from __future__ import annotations

import json
import pprint
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CHECKS: list[tuple[str, str]] = []
FAILED = 0


def record(label: str, ok: bool, detail: str) -> None:
    global FAILED
    mark = "OK  " if ok else "FAIL"
    if not ok:
        FAILED += 1
    CHECKS.append((f"[{mark}] {label}", detail))


def _load_key() -> str:
    """settings 에서 disaster API 키를 꺼낸다."""
    from app.core.settings import get_settings
    s = get_settings()
    key = getattr(s, "disaster_api_key", "") or ""
    # 공통 키 폴백 확인
    if not key:
        common = getattr(s, "data_go_kr_key", "") or ""
        return common
    return key


def main() -> int:
    print("=" * 70)
    print("재난문자 API 실 키 첫 호출 검증")
    print("=" * 70)

    # ── 0. 키 확인 ────────────────────────────────────────────────
    try:
        key = _load_key()
        record("API 키 로드", bool(key),
               f"len={len(key)}" if key else "비어 있음 — .env.apikeys 의 ACOP_DISASTER_API_KEY 확인")
    except Exception as exc:  # noqa: BLE001
        record("settings 로드", False, f"{type(exc).__name__}: {exc}")
        _print_results()
        return 1

    if not key:
        _print_results()
        return 1

    # ── 1. 클라이언트 생성 ────────────────────────────────────────
    from app.infrastructure.travel.disaster_msg import DisasterMsgSource
    source = DisasterMsgSource(service_key=key)
    record("클라이언트 생성", True, f"service_key 길이={len(key)}")

    # ── 2. 전국 조회 (rgnNm 없이) ────────────────────────────────
    print("\n[1차] 전국 조회 (rgnNm 없음, since_hours=6) …")
    result = source.recent(since_hours=6.0)

    if result is None:
        miss_summary = dict(source.misses)
        record("전국 조회 성공", False,
               f"None 반환 — misses: {miss_summary}")
        _print_results()
        return 1

    msgs = result.get("messages", [])
    record("전국 조회 성공", True,
           f"messages={len(msgs)}건  confirmed_at={result.get('confirmed_at', '?')[:19]}")
    record("source 필드 존재", result.get("source") == "disaster_msg",
           f"source={result.get('source')}")

    # ── 3. 응답 구조 검증 ─────────────────────────────────────────
    print(f"\n메시지 {len(msgs)}건 수신:")
    if msgs:
        for i, msg in enumerate(msgs[:3]):   # 최대 3건만 출력
            print(f"\n  [{i+1}] SN={msg.get('SN')}  등급={msg.get('EMRG_STEP_NM')}  "
                  f"재해={msg.get('DST_SE_NM')}")
            print(f"       수신지역={msg.get('RCPTN_RGN_NM')}")
            print(f"       발송시각={msg.get('CRT_DT')}")
            print(f"       내용(앞 80자)={str(msg.get('MSG_CN', ''))[:80]}")

        # 필드 존재 확인
        sample = msgs[0]
        expected_fields = ("SN", "CRT_DT", "MSG_CN", "RCPTN_RGN_NM", "DST_SE_NM", "EMRG_STEP_NM")
        missing = [f for f in expected_fields if not sample.get(f)]
        record("6개 필드 존재", len(missing) == 0,
               "모두 있음" if not missing else f"없는 필드: {missing}")

        # CRT_DT 포맷 확인 (14자리 yyyyMMddHHmmss 추정)
        crt_dt = sample.get("CRT_DT", "")
        parsed = DisasterMsgSource._parse_crt_dt(crt_dt)
        record("CRT_DT 포맷(14자리 추정)", parsed is not None,
               f"값={crt_dt!r}  → {'파싱 성공' if parsed else '파싱 실패 — 포맷이 다를 수 있다'}")
    else:
        print("  (현재 발령된 재난문자 없음 — 정상)")
        record("빈 목록도 정상 응답", True, "messages=[]")

    # ── 4. 지역 필터 확인 (rgnNm=서울특별시) ────────────────────────
    print("\n[2차] 지역 필터 조회 (rgnNm=서울특별시) …")
    source2 = DisasterMsgSource(service_key=key)
    result2 = source2.recent(since_hours=6.0, region_name="서울특별시")

    if result2 is None:
        record("지역 필터 조회", False,
               f"None — misses: {dict(source2.misses)}")
    else:
        msgs2 = result2.get("messages", [])
        record("지역 필터 조회", True,
               f"서울 한정 messages={len(msgs2)}건 (전국 {len(msgs)}건)")

    # ── 5. miss 요약 ──────────────────────────────────────────────
    total_misses = dict(source.misses)
    total_misses.update(source2.misses if result2 is not None else {})
    if total_misses:
        print(f"\n누적 miss: {total_misses}")
    else:
        print("\n누적 miss: 없음")

    # ── 6. 결과 출력 ──────────────────────────────────────────────
    _print_results()

    if FAILED == 0:
        print("\n★ disaster_msg.py 모듈 docstring의 '추정' 항목 중 확인된 것을 갱신하세요:")
        print("  - CRT_DT 포맷(14자리)")
        print("  - 오류 봉투 모양(header.resultCode)")
        print("  - rgnNm 파라미터 동작")

    return 1 if FAILED else 0


def _print_results() -> None:
    if not CHECKS:
        return
    width = max(len(label) for label, _ in CHECKS)
    print("\n" + "=" * (width + 50))
    for label, detail in CHECKS:
        print(f"{label.ljust(width)}  {detail}")
    print("=" * (width + 50))
    print(f"실패 {FAILED}건 / 전체 {len(CHECKS)}건")


if __name__ == "__main__":
    raise SystemExit(main())
