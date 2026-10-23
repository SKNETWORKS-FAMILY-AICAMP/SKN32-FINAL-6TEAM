"""선택한 이동 구간의 재검증 입력을 내부 일정 detail에 보존한다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json


def _stamp(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _place(place):
    return {key: deepcopy(place[key]) for key in ("key", "name", "lat", "lon") if key in place}


def express_version(sources):
    """런타임 스냅샷과 저장 직전 파일 대조에 같은 내용 식별 식을 쓴다."""
    contents = {}
    for line, signature in sources.items():
        if len(signature) == 2 and signature[1] is None:
            contents[line] = None
        elif len(signature) == 3 and isinstance(signature[2], str) and len(signature[2]) == 64:
            contents[line] = signature[2]
        else:
            raise ValueError('급행 입력 판에 내용 해시가 없다')
    encoded = json.dumps(contents, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    return hashlib.sha256(encoded).hexdigest()


def input_basis(runtime):
    """파일 현재값 대신 계산에 사용한 런타임의 입력 판을 저장·대조한다."""
    basis = {'timetable_built_at': _stamp(runtime.timetable_built_at),
             'rules_version': runtime.rules_version}
    sources = getattr(runtime, 'express_sources', None)
    if sources is not None:
        basis['express_version'] = express_version(sources)
    station_source = getattr(runtime, 'subway_station_source', None)
    if station_source is not None:
        basis['subway_station_version'] = station_source[1]
    return basis


def capture(options, *, runtime, origin, destination, stage, party, first_visit,
            service_date, start_min):
    """모델 분 단위·정류소 식별값을 복사한다. 실시간 관측으로 바꾸지 않는다."""
    from .subway_identity import boarding_identity
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "from_place": _place(origin), "to_place": _place(destination),
        "basis": input_basis(runtime),
        "stage": stage, "party": deepcopy(party), "first_visit": first_visit,
        "service_date": service_date.isoformat(), "start_min": start_min,
        "timing_unit": "model_minutes",
        "options": {
            option["id"]: {
                "option_id": option["id"], "eta_min": option["eta_min"],
                "start_min": option["_start"],
                "path_kind": ("direct_walk" if option.get("_key", (None,))[0] == "walk"
                              and not option.get("_legs") else "vehicle"),
                "legs": deepcopy(option.get("_legs") or []),
                "subway_identity": boarding_identity(runtime, option.get('_legs') or []),
                "check": deepcopy(option.get("_check")),
                "leg_results": [
                    {key: deepcopy(getattr(result, key, None)) for key in
                     ("idx", "verdict", "depart_min", "arrive_min", "wait_min", "ride_min",
                      "walk_min", "ride_src", "ride_grade")}
                    for result in option.get("_lr") or []
                ],
            }
            for option in options
        },
    }
