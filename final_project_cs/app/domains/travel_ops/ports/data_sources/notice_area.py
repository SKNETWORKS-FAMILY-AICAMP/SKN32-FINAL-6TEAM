"""재난 조회와 운영자 재검토가 같은 장소·지역 기준을 사용한다."""
from __future__ import annotations

from .disaster_msg import SEOUL_GU_NAMES, _covers, seoul_districts


def place_area(place: dict, region: str = '서울') -> dict:
    place = place if isinstance(place, dict) else {}
    attributes = place.get('attributes') if isinstance(place.get('attributes'), dict) else {}
    provided = place.get('district') or attributes.get('district')
    candidates = provided if isinstance(provided, list) else str(provided or '').split()
    districts = [value for value in candidates if isinstance(value, str) and value in SEOUL_GU_NAMES]
    district = districts[0] if len(districts) == 1 else districts or None
    basis = place.get('district_basis') or 'explicit'
    if not district:
        try:
            latitude = float(place['latitude']) if place.get('latitude') is not None else None
            longitude = float(place['longitude']) if place.get('longitude') is not None else None
        except (TypeError, ValueError):
            latitude = longitude = None
        candidates, basis = seoul_districts(latitude, longitude, place.get('address') or attributes.get('address'))
        district = candidates[0] if candidates and len(candidates) == 1 else candidates
    return {'name': place.get('name'), 'region': region, 'district': district,
            'district_basis': basis, 'basis_source': place.get('basis_source') or 'recorded_target'}


def relation(regions: list[str], target: dict) -> str:
    """수신 지역과 대상 지역의 관계. 지역이 불명확하면 관련 있다고 단정하지 않는다."""
    regions = [value for value in regions if isinstance(value, str)] if isinstance(regions, list) else []
    if not regions:
        return 'unassessed'
    district = target.get('district')
    full = {'서울': '서울특별시'}.get(target.get('region'), target.get('region'))
    citywide = any(token.strip() in (full, f'{full} 전체', f'{full}전체') for token in regions)
    if not district and not citywide:
        return 'unassessed'
    if citywide:
        return 'matched'
    if isinstance(district, list) and len(district) > 1:
        hits = [_covers(regions, target.get('region') or '서울', candidate) for candidate in district]
        return 'matched' if all(hits) else 'unassessed' if any(hits) else 'unrelated'
    return 'matched' if _covers(regions, target.get('region') or '서울', district) else 'unrelated'
