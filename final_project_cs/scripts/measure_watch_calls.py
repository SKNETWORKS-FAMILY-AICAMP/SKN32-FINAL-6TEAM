# -*- coding: utf-8 -*-
"""감시 한 틱이 바깥으로 내보내는 요청 수를 센다 — 네트워크는 안 나간다(HTTP 바닥만 바꿔 기록한다). `[2026-10-03]`

    python -m scripts.measure_watch_calls        (저장소 루트 = final_project_cs 에서)

★센 값은 **시도한 요청**이다. 가짜 응답이 비어 있어 1차 소스(날씨 Open-Meteo · 대기질 에어코리아)의 파싱이 실패하면 대체 소스(`kma` · `open_meteo_air`)도 불리는데,
  실제로는 1차가 성공하면 대체를 안 부른다 — 보고서에서는 두 이름을 뺀 값을 「정상 경로」로 읽는다.

실제 조립(build_travel_sources)과 실제 점검(DisruptionCheck)을 그대로 쓰고, 어댑터가 `httpx.get` 을 부르는 자리(`TravelSource._http_get`)만 기록 함수로 바꾼다.
응답은 「성공 · 내용 없음」이라 캐시에는 담긴다(실제 성공 응답처럼). 내용이 없어 어댑터가 파싱에 실패하면 대체 소스를 부를 수 있으니 소스 이름별로 나눠 센다.
비밀값(서비스 키)은 기록하지 않는다 — 소스 이름 · 주소 경로 · 인자 이름 · 인자 값의 해시 앞 8자리만.
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
import httpx

from app.core.settings import get_settings
from app.infrastructure.travel.base import TravelSource, build_travel_sources
from app.infrastructure.travel.disruptions import DisruptionCheck

KST = ZoneInfo("Asia/Seoul")
calls: list[tuple[str, str, str]] = []


def fake_get(self, url, params):
    parsed = urlparse(url)
    key = hashlib.sha1(repr(sorted((str(k), str(v)) for k, v in params.items())).encode()).hexdigest()[:8]
    calls.append((self.name, parsed.netloc + parsed.path, key))
    request = httpx.Request("GET", url)
    if self.name in ("utic", "heritage"):          # XML 소스 — 성공으로 보이게(빈 XML)
        return httpx.Response(200, text="<root/>", request=request)
    return httpx.Response(200, json={}, request=request)


TravelSource._http_get = fake_get
TravelSource._allow = lambda self: True            # 속도 제한 대기 없이 — 우리가 세는 것은 「나가려는 요청」이다

settings = get_settings()
sources = build_travel_sources(settings)
print("붙어 있는 소스 / 못 붙은 소스(이 PC 설정 기준):")
print("  못 붙음:", sorted(sources.unavailable))
check = DisruptionCheck(sources).check


def place(i, rng):
    return {"place_id": f"p{i}", "latitude": 37.45 + rng.random() * 0.17, "longitude": 126.80 + rng.random() * 0.30,
            "weather_sensitive": True, "district": f"구{i % 25}"}


def summarize(label, window):
    by = Counter(name for name, _, _ in window)
    uniq = defaultdict(set)
    for name, path, key in window:
        uniq[name].add((path, key))
    print(f"\n[{label}] 요청 시도 {len(window)}건 · 서로 다른 요청 {sum(len(v) for v in uniq.values())}건")
    for name in sorted(by):
        print(f"   {name:<22} 시도 {by[name]:>3} · 서로 다른 요청 {len(uniq[name]):>3} · {sorted({p for p, _ in uniq[name]})[0]}")


rng = random.Random(7)
now = datetime.now(KST).replace(second=0, microsecond=0)

# ① 항목 하나, 캐시가 빈 상태(= 새 프로세스의 첫 점검)
sources_cache = sources.cache if hasattr(sources, "cache") else None
calls.clear()
check(place=place(0, rng), starts_at=now + timedelta(minutes=30))
summarize("항목 1개 · 빈 캐시", list(calls))

# ② 같은 항목을 곧바로 또 — 캐시가 있으면 새 요청이 없어야 한다(한 틱 안에서 Team 이 다시 점검하는 경우)
calls.clear()
check(place=place(0, random.Random(7)), starts_at=now + timedelta(minutes=30))
print(f"\n[같은 항목을 곧바로 다시 · 캐시 있음] 새 요청 {len(calls)}건")

# ③ 항목 N 개(서로 다른 장소) — 한 틱 · 한 프로세스(캐시 공유)
for n in (1, 5, 10, 20, 40):
    # 캐시를 비운다(새 프로세스처럼)
    if sources_cache is not None:
        sources_cache._items.clear()
    rng2 = random.Random(11)
    calls.clear()
    for i in range(n):
        check(place=place(i, rng2), starts_at=now + timedelta(minutes=30 + i))
    names = Counter(name for name, _, _ in calls)
    print(f"[한 틱 · 항목 {n:>2}개 · 장소가 서로 다름] 요청 {len(calls):>4}건  ({', '.join(f'{k} {v}' for k, v in sorted(names.items()))})")

# ④ 같은 장소 N 개(한 곳에 몰린 일정)
if sources_cache is not None:
    sources_cache._items.clear()
calls.clear()
same = place(0, random.Random(3))
for i in range(20):
    check(place={**same, "place_id": f"s{i}"}, starts_at=now + timedelta(minutes=30 + i))
print(f"[한 틱 · 항목 20개 · 장소가 같음] 요청 {len(calls)}건")

# ⑤ 같은 장소 · 시각만 다른 항목 — 어느 소스가 항목마다 새 요청을 내나
if sources_cache is not None:
    sources_cache._items.clear()
calls.clear()
check(place={**same, "place_id": "z0"}, starts_at=now + timedelta(minutes=30))
first = len(calls)
calls.clear()
check(place={**same, "place_id": "z1"}, starts_at=now + timedelta(minutes=45))
print(f"\n[같은 장소 · 15분 뒤 시각] 두 번째 항목이 낸 새 요청 {len(calls)}건:", sorted({n for n, _, _ in calls}))
calls.clear()
check(place={**same, "place_id": "z2"}, starts_at=now + timedelta(minutes=30))
print(f"[같은 장소 · 같은 시각] 새 요청 {len(calls)}건:", sorted({n for n, _, _ in calls}))
