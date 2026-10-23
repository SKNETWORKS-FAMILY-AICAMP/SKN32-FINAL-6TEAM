"""저장 구간을 현재 시각으로 다시 검증한다. 외부 소스는 콜백으로만 받는다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta
import math

from .plan import KST, Planner, service_day
from .timeutil import SERVICE_DAY_MAX_MIN
from .departure_context import input_basis


def _number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value >= 0)


def _same_place(saved, current):
    if not isinstance(saved, dict) or not isinstance(current, dict):
        return False
    return all(isinstance(saved.get(key), (int, float)) and not isinstance(saved[key], bool)
               and math.isfinite(saved[key]) and isinstance(current.get(key), (int, float))
               and not isinstance(current[key], bool) and math.isfinite(current[key])
               and saved[key] == current[key]
               for key in ('lat', 'lon'))


def _observe_walk(runtime, context, option, base, *, now, deadline, origin, destination):
    """직접 도보는 기존 계획의 보행망·동행 상한·시간 식을 현재 시각에서 재사용한다."""
    from .geo import meters

    def fail(status, reason):
        return {**base, 'status': status, 'reason': reason}

    if option.get('legs') != [] or option.get('check') is not None:
        return fail('needs_replan', 'walk_context_changed')
    planner = Planner(runtime, stage='pre_departure', modes={'walk'})
    straight = meters(origin['lat'], origin['lon'], destination['lat'], destination['lon'])
    if straight > planner._walk_limit(context['party']):
        return fail('needs_replan', 'walk_limit_exceeded')
    evidence = {'grade': '추정', 'checked_at': now.isoformat(),
                'claim': '현재 장소 사이 모델 재계산; 실제 보행 관측 아님'}
    distance, minutes, no_path = planner._walk_path(origin, destination, straight, evidence=evidence)
    base['observations'].append(evidence)
    if no_path:
        return fail('needs_replan', 'no_walk_path')
    if not _number(distance) or not _number(minutes):
        return fail('fatal', 'invalid_walk_model')
    start = now.astimezone(KST).replace(second=0, microsecond=0)
    if now > start:
        start += timedelta(minutes=1)
    arrival = start + timedelta(minutes=max(1, math.ceil(minutes)))
    margin = planner.v.rv('buffer', 'by_stage', 'pre_departure')
    if not _number(margin):
        return fail('fatal', 'invalid_departure_margin')
    base.update(checked_at=now.isoformat(), walk_m=distance, margin_min=margin)
    if arrival + timedelta(minutes=margin) > deadline:
        return fail('needs_replan', 'walk_arrive_late_or_margin')
    return {**base, 'status': 'model_revalidated', 'verdict': 'feasible',
            'departure_at': start.isoformat(), 'arrival_at': arrival.isoformat(),
            'worst_arrival_at': arrival.isoformat(),
            'eta_min': math.ceil((arrival-now).total_seconds()/60)}


def observe(runtime, context, option_id, *, now, deadline, origin, destination,
            bus_arrival=None, subway_arrival=None, disruptions=(), current_party=None, current_first_visit=None):
    """콜백의 실시간 예상과 모델 재검증을 구별한다. 일정·알림을 직접 쓰지 않는다."""
    base = {'option_id': option_id, 'observations': [], 'timing_unit': 'model_minutes',
            'party_check': 'current_trip_not_supplied'}

    def fail(status, reason):
        return {**base, 'status': status, 'reason': reason}

    if not isinstance(now, datetime) or now.utcoffset() is None:
        return fail('fatal', 'timezone_required')
    if not isinstance(deadline, datetime) or deadline.utcoffset() is None or deadline <= now:
        return fail('needs_replan', 'deadline_passed_or_invalid')
    if not isinstance(context, dict) or context.get('schema_version') != 1:
        return fail('needs_replan', 'context_missing_or_version')
    if context.get('timing_unit') != 'model_minutes':
        return fail('needs_replan', 'timing_unit_mismatch')
    if not (_same_place(context.get('from_place'), origin)
            and _same_place(context.get('to_place'), destination)):
        return fail('needs_replan', 'place_changed')
    basis = input_basis(runtime)
    if context.get('basis') != basis:
        return fail('needs_replan', 'basis_changed')
    options = context.get('options')
    option = options.get(option_id) if isinstance(options, dict) else None
    if not isinstance(option, dict) or option.get('option_id') != option_id:
        return fail('needs_replan', 'option_changed')
    check = option.get('check')
    legs = option.get('legs')
    party = context.get('party')
    if not isinstance(party, dict) or not isinstance(context.get('first_visit'), bool):
        return fail('needs_replan', 'party_context_invalid')
    if current_party is not None or current_first_visit is not None:
        if not isinstance(current_party, dict) or not isinstance(current_first_visit, bool):
            return fail('fatal', 'current_party_invalid')
        if party != current_party:
            base['party_check'] = 'changed'
            return fail('needs_replan', 'party_changed')
        if context['first_visit'] != current_first_visit:
            base['party_check'] = 'changed'
            return fail('needs_replan', 'first_visit_changed')
        base['party_check'] = 'matched'
    if option.get('path_kind') == 'direct_walk':
        base['basis'] = basis
        return _observe_walk(runtime, context, option, base, now=now, deadline=deadline,
                             origin=origin, destination=destination)
    if not isinstance(check, dict) or not legs or check.get('legs') != legs:
        return fail('needs_replan', 'route_check_missing_or_changed')
    if 'subway_identity' in option or 'subway_station_version' in basis:
        from .subway_identity import boarding_identity
        if option.get('subway_identity') != boarding_identity(runtime, legs):
            return fail('needs_replan', 'subway_identity_changed')
    names = ('walk_place_in', 'walk_stop_in', 'walk_stop_out', 'walk_place_out')
    if any(not _number(check.get(key)) for key in names):
        return fail('needs_replan', 'access_context_invalid')
    now_local = now.astimezone(KST)
    start = now_local.replace(second=0, microsecond=0)
    if now_local > start:
        start += timedelta(minutes=1)
    access = check['walk_place_in'] + check['walk_stop_in']
    egress = check['walk_stop_out'] + check['walk_place_out']
    ready = start + timedelta(minutes=math.ceil(access))
    service_date, depart_min = service_day(ready)
    midnight = datetime.combine(service_date, time(), tzinfo=KST)
    by_min = math.floor((deadline - midnight).total_seconds() / 60 - egress)
    if by_min < depart_min or by_min > SERVICE_DAY_MAX_MIN:
        return fail('needs_replan', 'deadline_outside_service_horizon')
    departures = {}
    rail_departures = {}
    evaluated = now
    first = legs[0]
    observation = None
    did_observe = False
    rail_identity, rail_services = None, []
    if first.get('mode', 'subway') == 'bus' and bus_arrival is not None:
        did_observe = True
        required = ('route_id', 'from_stop_id', 'from_sequence', 'to_sequence')
        if any(first.get(key) is None for key in required):
            return fail('needs_replan', 'boarding_identity_missing')
        observation = bus_arrival(first['route_id'], stop_id=first['from_stop_id'],
                                  stop_sequence=first['from_sequence'], now=now, ready_at=ready)
    elif first.get('mode', 'subway') == 'subway' and subway_arrival is not None:
        did_observe = True
        from .subway_departure import boarding_services
        rail_identity, rail_services = boarding_services(runtime, first)
        if rail_identity.get('status') == 'matched':
            fields = ('train_status', 'path_station_ids', 'next_station_names',
                      'terminal_station_names', 'boarding_neighbor_ids')
            public_services = [{k: deepcopy(service[k]) for k in fields if k in service}
                               for service in rail_services]
            observation = subway_arrival(rail_identity['query_station'], line_id=rail_identity['line_id'],
                station_id=rail_identity['station_id'], target_station_id=rail_identity['target_station_id'],
                allowed_services=public_services, now=now, ready_at=ready)
        else:
            observation = rail_identity
    if did_observe:
        if not isinstance(observation, dict):
            observation = {'status': 'unavailable', 'reason': 'invalid_observation'}
        base['observations'].append(deepcopy(observation))
        if 'evaluated_at' in observation:
            try:
                evaluated = datetime.fromisoformat(str(observation['evaluated_at']))
                if evaluated.utcoffset() is None or evaluated < now:
                    return fail('fatal', 'invalid_evaluation_clock')
            except (ValueError, TypeError):
                return fail('fatal', 'invalid_evaluation_clock')
            if evaluated >= deadline:
                return fail('needs_replan', 'deadline_passed_during_query')
            start = evaluated.astimezone(KST).replace(second=0, microsecond=0)
            if evaluated > start:
                start += timedelta(minutes=1)
            ready = start + timedelta(minutes=math.ceil(access))
            service_date, depart_min = service_day(ready)
            midnight = datetime.combine(service_date, time(), tzinfo=KST)
            by_min = math.floor((deadline - midnight).total_seconds() / 60 - egress)
            if by_min < depart_min or by_min > SERVICE_DAY_MAX_MIN:
                return fail('needs_replan', 'deadline_outside_service_horizon')
        if observation.get('status') == 'predicted':
            try:
                at = datetime.fromisoformat(str(observation['arrival_at']))
                confirmed = datetime.fromisoformat(str(observation['confirmed_at']))
                valid = (at.utcoffset() is not None and confirmed.utcoffset() is not None
                         and confirmed <= evaluated and at >= ready
                         and observation.get('source'))
                if rail_identity is None:
                    valid = (valid and str(observation.get('route_id')) == str(first['route_id'])
                             and str(observation.get('stop_id')) == str(first['from_stop_id'])
                             and observation.get('stop_sequence') == first['from_sequence'])
                else:
                    from .subway_departure import matched_service
                    rail_service = matched_service(observation, rail_identity, rail_services)
                    valid = valid and rail_service is not None
            except (KeyError, ValueError, TypeError):
                valid = False
            if not valid:
                return fail('fatal', 'observation_identity_or_clock_mismatch')
            predicted_min = math.ceil((at - midnight).total_seconds() / 60)
            if predicted_min > by_min:
                return fail('needs_replan', 'boarding_after_deadline')
            if rail_identity is not None:
                rail_departures[(0, first['line'], first['from'], first['to'])] = {
                    'depart_min': predicted_min, 'terminal': rail_service['terminal'],
                    'path_stations': deepcopy(rail_service['path_stations']),
                    'evidence': {'source_type': 'api', 'source_id': observation['source'], 'grade': '추정',
                                 'observed_at': observation['confirmed_at'],
                                 'claim': '정확한 역/다음역/종착역 일반열차 접근 이후 도착 예측; 승차 소요는 역간 모델'}}
            else:
                departures[(0, str(first['route_id']), first['from_sequence'], first['to_sequence'])] = {
                'depart_min': predicted_min,
                'evidence': {'source_type': 'api', 'source_id': observation['source'], 'grade': '추정',
                             'observed_at': observation['confirmed_at'],
                             'claim': '정확 승차 위치의 접근 이후 차량 도착 예측; 실제 탑승 관측 아님'}}
    case = {'id': f'departure/{option_id}', 'date': service_date.isoformat(),
            'stage': 'pre_departure', 'depart_at': depart_min, 'arrive_by': by_min,
            'legs': deepcopy(legs), 'party': deepcopy(party), 'first_visit': context['first_visit'],
            'no_alternatives': True, 'disruptions': list(disruptions)}
    result = runtime.verify_case(case, bus_departures=departures,
                                 **({'subway_departures': rail_departures} if rail_departures else {}))
    base.update(basis=basis, checked_at=evaluated.isoformat(), verdict=result.verdict,
                reason=result.code or result.reason,
                leg_results=[{'idx': leg.idx, 'verdict': leg.verdict, 'depart_min': leg.depart_min,
                              'arrive_min': leg.arrive_min, 'wait_min': leg.wait_min,
                              'ride_min': leg.ride_min, 'ride_src': leg.ride_src}
                             for leg in result.legs])
    if result.verdict != 'feasible' or result.arrive_min is None:
        return fail('fatal' if result.verdict == 'unknown' else 'needs_replan', base['reason'])
    arrival = midnight + timedelta(minutes=result.arrive_min + math.ceil(egress))
    worst = result.arrive_worst_min
    worst_arrival = midnight + timedelta(minutes=(worst if worst is not None else result.arrive_min)
                                         + math.ceil(egress))
    if arrival > deadline:
        return fail('needs_replan', 'arrive_late')
    if departures or rail_departures:
        base['realtime_mode'] = 'subway' if rail_departures else 'bus'
    return {**base, 'status': 'realtime' if departures or rail_departures else 'model_revalidated',
            'departure_at': start.isoformat(), 'arrival_at': arrival.isoformat(),
            'worst_arrival_at': worst_arrival.isoformat(),
            'eta_min': math.ceil((arrival - evaluated).total_seconds() / 60)}
