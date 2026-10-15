"""정적 단순 자동차 회전 관계를 정확한 그래프 판에 결합한다."""
from __future__ import annotations

import hashlib
import json

from .car import RouterDown

FILE_NAME = 'turn_restrictions_v1.json'
NO_VALUES = {'no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn'}
ONLY_VALUES = {'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn'}


def signature(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    # 원자 교체는 크기·수정시각이 같아도 다른 파일이다.
    # 파일 식별자가 없는 파일시스템에서는 내용으로 교체를 검사한다.
    identity = (stat.st_dev, stat.st_ino) if stat.st_ino else sha256(path)
    return identity, stat.st_mtime_ns, stat.st_size


def graph_signature(directory):
    return tuple(signature(directory/name) for name in ('nodes.jsonl.gz', 'edges.jsonl.gz'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(data, router):
    if data.get('schema_version') != 1 or not isinstance(data.get('rules'), list):
        raise RouterDown('turn_restrictions: 미지원 자료 형식')
    only, prohibited, ids = {}, {}, set()
    for row in data['rules']:
        rid, incoming, outgoing = row.get('relation_id'), row.get('incoming'), row.get('outgoing')
        value = row.get('value')
        if (any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (rid, incoming, outgoing))
                or rid in ids or value not in NO_VALUES | ONLY_VALUES):
            raise RouterDown('turn_restrictions: 잘못된 방향 관계')
        ids.add(rid)
        ie, oe = incoming >> 1, outgoing >> 1
        if ie >= len(router.eu) or oe >= len(router.eu):
            raise RouterDown('turn_restrictions: 그래프 간선 범위 불일치')
        iend = router.eu[ie] if incoming & 1 else router.ev[ie]
        ostart = router.ev[oe] if outgoing & 1 else router.eu[oe]
        if (iend != ostart or not router._allowed('car', ie)[incoming & 1]
                or not router._allowed('car', oe)[outgoing & 1]):
            raise RouterDown('turn_restrictions: 방향·교차로 불일치')
        if value in ONLY_VALUES:
            only.setdefault(incoming, {outgoing}).intersection_update({outgoing})
        else:
            prohibited.setdefault(incoming, set()).add(outgoing)
    if any(not allowed or not allowed - prohibited.get(inc, set()) for inc, allowed in only.items()):
        raise RouterDown('turn_restrictions: 허용·금지 관계 충돌')
    if data.get('applied_relations', len(ids)) != len(ids):
        raise RouterDown('turn_restrictions: 적용 분모 불일치')
    metadata = {'status': 'partial_static_motorcar', 'applied_relations': len(ids),
                'source_relations': data.get('source_relations'),
                'excluded_candidate_relations': data.get('excluded_candidate_relations'),
                'complete_road_rules': False}
    return only, prohibited, metadata


def load(router):
    """자료 교체는 재검사한다. 적용 뒤 삭제·손상은 옛 경로로 조용히 돌아가지 않는다."""
    records = router._records
    path = router.dir/FILE_NAME if records is None else None
    if records is None and graph_signature(router.dir) != router._graph_signature:
        raise RouterDown('turn_restrictions: 적재한 도로 그래프가 바뀌었다')
    with router._lock:
        if path is None:
            sig = 'records'
        else:
            try:
                payload = path.read_bytes()
            except FileNotFoundError:
                sig = None
            except OSError as exc:
                raise RouterDown('turn_restrictions: 자료를 읽지 못했다') from exc
            else:
                # copy2/원자 교체는 크기와 수정시각을 보존할 수 있다.
                # 비교한 것과 같은 바이트를 아래에서 검증하고 파싱한다.
                sig = hashlib.sha256(payload).hexdigest()
        if router._turns_loaded and sig == router._turn_signature:
            return router._turn_tables
        if sig is None:
            if router._turn_tables is not None:
                raise RouterDown('turn_restrictions: 적용 자료가 삭제되었다')
            selected = None
        else:
            try:
                data = (records.get('turn_restrictions') if records is not None
                        else json.loads(payload.decode('utf8')))
                if data is None:
                    selected = None
                else:
                    if records is None:
                        bound = data.get('graph_sha256') or {}
                        if any(bound.get(name) != sha256(router.dir/name)
                               for name in ('nodes.jsonl.gz', 'edges.jsonl.gz')):
                            raise RouterDown('turn_restrictions: 자료 해시가 그래프와 맞지 않는다')
                    selected = tables(data, router)
            except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
                raise RouterDown('turn_restrictions: 자료를 검증하지 못했다') from exc
        router._turn_tables, router._turn_signature, router._turns_loaded = selected, sig, True
        return selected


def permitted(policy, incoming, outgoing):
    if incoming < 0 or outgoing < 0:
        return True
    only, prohibited, _metadata = policy
    return (outgoing not in prohibited.get(incoming, ())
            and (incoming not in only or outgoing in only[incoming]))
