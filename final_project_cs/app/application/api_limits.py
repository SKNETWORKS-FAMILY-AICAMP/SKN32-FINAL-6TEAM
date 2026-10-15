"""현재 프로세스의 호출 한도와 마지막 DB 계측을 읽는다. 비밀 설정은 직렬화하지 않는다."""
from datetime import datetime
from zoneinfo import ZoneInfo

from psycopg import Error as DatabaseError

from app.core.settings import get_guardrails, get_settings

KST = ZoneInfo('Asia/Seoul')
NAMES = {
    'open_meteo': 'Open-Meteo 날씨', 'open_meteo_air': 'Open-Meteo 대기질',
    'heritage_khs': '국가유산청', 'kasi_holiday': '공휴일', 'tour_api': '관광공사 TourAPI',
    'kma_warning': '기상청 특보', 'kma': '기상청 예보', 'kma_earthquake': '기상청 지진',
    'airkorea': '에어코리아', 'khoa': '해양 정보', 'tago': '대중교통 TAGO',
    'airport': '공항 정보', 'mofa': '외교부 여행 정보', 'its': '국가교통정보 ITS',
    'disaster_msg': '재난문자', 'utic': '도시교통 UTIC', 'odsay': '대중교통 ODsay',
    'subway_notice': '지하철 공지', 'seoul_subway_arrival': '서울 지하철 도착',
    'seoul_bus_arrival': '서울 버스 도착', 'seoul_bike': '서울 따릉이',
    'kakao': '카카오', 'naver_search': '네이버 검색', 'google_places': 'Google Places',
    'google_routes': 'Google Routes',
}


def _setting(settings, field: str, zero_meaning: str):
    if field not in type(settings).model_fields:
        return dict(env=None, value=None, origin='absent', zero_meaning=None)
    return dict(env='ACOP_' + field.upper(), value=int(getattr(settings, field)),
                origin='configured' if field in settings.model_fields_set else 'default', zero_meaning=zero_meaning)


def adjustable(settings=None) -> dict[str, dict[str, int | None]]:
    """운영자가 관리자 화면에서 상한을 정할 수 있는 API — 호출 전에 DB 예산을 확보하는 소스(가드레일 `travel.source_budget_sources`)뿐이다.
    값은 ENV 상한(하루 · 월, 월 미설정은 None). ★`[2026-10-15]` 운영자 상한은 ENV 보다 **낮게만** 정한다(`admin_service.api_cap` 이 작은 쪽을 쓴다) —
    올리려면 `.env.apikeys` 를 바꾸고 cs 프로젝트 서버를 다시 띄운다."""
    settings = settings if settings is not None else get_settings()
    guard = get_guardrails()
    if not guard.get("travel.source_budget_shared"):
        return {}
    daily, monthly = settings.source_rate_limits(), settings.source_monthly_limits()
    return {name: {"day": int(daily[name]), "month": int(monthly[name]) if monthly.get(name) else None}
            for name in (guard.get("travel.source_budget_sources") or []) if int(daily.get(name) or 0) > 0}


def snapshot(*, connection_factory, settings=None, now=None):
    settings = settings if settings is not None else get_settings()
    now = (now or datetime.now(KST)).astimezone(KST)
    limits = [dict(id=name, name=NAMES.get(name, name),
                   daily=_setting(settings, f'rate_{name}_per_day', 'no_interval_limit'),
                   monthly=_setting(settings, f'rate_{name}_per_month', 'unset'))
              for name in settings.source_rate_limits()]
    limits.append(dict(id='openai_failover', name='OpenAI 장애 대체 호출',
                       daily=_setting(settings, 'llm_failover_daily_cap', 'blocked'),
                       monthly=_setting(settings, 'llm_failover_monthly_cap', 'blocked')))
    periods = {}
    for row in limits:
        row['budget_timezone'] = 'UTC' if row['id'] == 'openai_failover' else 'Asia/Seoul'
        clock = now.astimezone(ZoneInfo(row['budget_timezone']))
        periods[row['id']] = {'day': f'day:{clock:%Y-%m-%d}', 'month': f'month:{clock:%Y-%m}'}
    records, overrides, error = {}, {}, None
    try:
        # 한 트랜잭션에서 읽기만 한다. 조회 때문에 예산 줄을 만들거나 갱신하지 않는다.
        with connection_factory() as conn, conn.cursor() as cur:
            ids = [row['id'] for row in limits]
            cur.execute('SELECT meter,period,used,cap,updated_at FROM external_call_budget '
                        'WHERE meter=ANY(%s) AND period=ANY(%s)', (ids, sorted({period for value in periods.values() for period in value.values()})))
            records = {(meter, period): dict(used=int(used), cap=int(cap), updated_at=at.isoformat())
                       for meter, period, used, cap, at in cur.fetchall()}
            cur.execute('SELECT meter,daily,monthly FROM admin_api_caps WHERE meter=ANY(%s)', (ids,))
            overrides = {meter: dict(day=int(day), month=int(month)) for meter, day, month in cur.fetchall()}
    except DatabaseError:
        # 오류를 명시한다. ENV는 읽었지만 계측을 못 읽은 상태를 0회로 위장하지 않는다.
        records, overrides = {}, {}
        error = 'DB 사용 기록을 읽지 못했습니다. 연결·DB 표를 확인하고 다시 읽어 주세요.'
    bounds = adjustable(settings)
    for row in limits:
        row['recorded'] = {kind: records.get((row['id'], periods[row['id']][kind])) for kind in ('day', 'month')}
        row['operator_cap'] = overrides.get(row['id'])
        # 화면의 「조정」 — DB 예산을 거치는 소스만 운영자 상한이 실제 호출에 걸린다. 나머지는 이유를 싣는다(눌러도 안 먹는 단추를 만들지 않는다)
        row['adjustable'] = row['id'] in bounds
        row['adjust_note'] = None if row['adjustable'] else (
            '전용 예산으로 셉니다 — 아래 「외부 API별 현황」에서 조정합니다.' if row['id'] in ('kakao', 'google_places', 'google_routes', 'openai_failover')
            else '호출 전 DB 예산을 거치지 않는 API라 운영자 상한이 걸리지 않습니다. ENV 를 바꾸고 cs 프로젝트 서버를 다시 띄웁니다.')
    return dict(as_of=now.isoformat(), timezone='Asia/Seoul', usage_error=error, limits=limits)
