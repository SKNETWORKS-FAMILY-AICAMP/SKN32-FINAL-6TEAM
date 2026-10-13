"""버스 첫차·막차 캐시의 순수 정규화. 원본 데이터 없이 CI에서 검증한다."""
import re
from datetime import datetime


def _hm(m):
    return None if m is None else f"{m // 60:02d}:{m % 60:02d}"


def normalize_window(first_raw, last_raw, base_d):
    """원문 첫차·막차('YYYYMMDDHHMMSS') → (first 'HH:MM'|None, last, grade, note).

    base_d: 시간 기준일 'YYYYMMDD'. 정수 분으로 비교한다. 규칙은 파일 머리 주석(45번 방).
    날짜가 {base_d, base_d+1} 밖이면 ValueError — 혼합 캐시를 조용히 정규화하지 않는다.
    """
    from datetime import timedelta
    b = datetime.strptime(base_d, "%Y%m%d").date()
    ok_dates = {b, b + timedelta(days=1)}

    def mins(raw):
        raw = (raw or "").strip()
        if not re.fullmatch(r"\d{14}", raw):
            return None
        d = datetime.strptime(raw[:8], "%Y%m%d").date()
        if d not in ok_dates:
            raise ValueError(f"날짜 {raw[:8]} 가 기준일 {base_d}·+1 밖이다 — 혼합 캐시로 보고 중단한다")
        return (d - b).days * 1440 + int(raw[8:10]) * 60 + int(raw[10:12])

    ft, lt = (first_raw or "").strip(), (last_raw or "").strip()
    f, l = mins(ft), mins(lt)
    if f is None or l is None:
        return _hm(f), _hm(l), "근거없음", "첫차 또는 막차 원문이 없다"
    if ft == lt and ft.endswith("000000"):
        return None, None, "근거없음", (f"첫차=막차={ft}(시각부 000000) — 운행 구간을 신뢰성 있게 해석할 수 없음 "
                                      f"(단일 출발·24시간 운행·결측을 이 값만으로 못 가른다)")
    grade, note = "확정", None
    if l < f and f < 1440 and l < 1440:
        note = f"원문 첫차 {_hm(f)} > 막차 {_hm(l)}(같은 날) — 막차 +24h 로 추정 보정"
        l += 1440
        grade = "추정"
    if f > l:
        return None, None, "근거없음", f"첫차 {_hm(f)} > 막차 {_hm(l)} — 운행 구간을 해석할 수 없음"
    return _hm(f), _hm(l), grade, note


