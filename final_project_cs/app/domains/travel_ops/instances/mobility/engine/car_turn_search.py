"""들어온 유향 간선을 상태로 유지하여 부분 출발·도착에도 회전 조건을 검사한다."""
from __future__ import annotations

import heapq
import math

from .car import RouterDown, hav
from .turn_restrictions import permitted

NODE_EPS_M = 1e-6  # 실제 부분 간선은 교차로 시작으로 바꾸지 않는다.


def pieces(router, starts_snaps, goal_snaps, policy):
    deg, to, arcs, weights = router._adjacency('car')
    starts, goals = {}, {}

    def endpoints(snap, starting):
        edge = snap.e
        length = router._geom(edge)[1][-1]
        if length <= 0:
            raise RouterDown('turn_restrictions: 길이 없는 간선')
        forward, backward = router._allowed('car', edge)
        costs = router._cost('car', edge)
        # 시작은 부분 간선의 도착 방향, 목표는 마지막 부분 간선의 출발 방향이다.
        parts = [(router.eu[edge], snap.d_u, 'u', edge*2+(1 if starting else 0), backward if starting else forward),
                 (router.ev[edge], length-snap.d_u, 'v', edge*2+(0 if starting else 1), forward if starting else backward)]
        for node, distance, side, arc, allowed in parts:
            if distance <= NODE_EPS_M:
                yield node, -1, 0.0, side
            elif allowed:
                yield node, arc, costs*distance/length, side

    for snap in starts_snaps:
        for node, arc, cost, side in endpoints(snap, True):
            state = (node, arc)
            if state not in starts or cost < starts[state][0]:
                starts[state] = cost, side, snap
    for snap in goal_snaps:
        for node, arc, cost, side in endpoints(snap, False):
            goals.setdefault(node, []).append((arc, cost, side, snap))

    best, direct = math.inf, None
    for start in starts_snaps:
        for goal in goal_snaps:
            if start.e != goal.e:
                continue
            forward, backward = router._allowed('car', start.e)
            delta = goal.d_u-start.d_u
            if (delta >= 0 and forward) or (delta < 0 and backward):
                cost = router._cost('car', start.e)*abs(delta)/router._geom(start.e)[1][-1]
                if cost < best:
                    best, direct = cost, (start, goal)

    # 들어온 간선은 달라도 목표 거리는 같다. 목적지가 바뀌는 다음 요청에는 공유하지 않는다.
    node_heuristics = {}

    def heuristic(node):
        if router.force_dijkstra:
            return 0.0
        value = node_heuristics.get(node)
        if value is None:
            point = (router.nlon[node], router.nlat[node])
            value = min(hav(point, snap.pt) for snap in goal_snaps)/28.0
            node_heuristics[node] = value
        return value

    dist, parents, roots, queue = {}, {}, {}, []
    for state, value in starts.items():
        dist[state] = value[0]
        parents[state] = None
        roots[state] = value
        heapq.heappush(queue, (value[0]+heuristic(state[0]), value[0], state))
    selected, final_goal = None, None
    while queue:
        estimate, cost, state = heapq.heappop(queue)
        if estimate >= best:
            break
        if cost != dist.get(state):
            continue
        node, incoming = state
        for outgoing, tail, side, snap in goals.get(node, ()):
            if permitted(policy, incoming, outgoing) and cost+tail < best:
                best, selected, final_goal = cost+tail, state, (outgoing, side, snap)
        for idx in range(deg[node], deg[node+1]):
            outgoing = arcs[idx]
            if not permitted(policy, incoming, outgoing):
                continue
            next_state = (to[idx], outgoing)
            next_cost = cost+weights[idx]
            if next_cost < dist.get(next_state, math.inf):
                dist[next_state] = next_cost
                parents[next_state] = state
                roots.pop(next_state, None)
                heapq.heappush(queue, (next_cost+heuristic(next_state[0]), next_cost, next_state))
    if best == math.inf:
        raise RouterDown('no_path: 이 그래프의 적용 회전 조건에서 경로를 찾지 못했다')
    if selected is None:
        return [(direct[0].e, router._cut(*direct))], [], best, direct[0], direct[1]
    state, chain = selected, []
    while parents[state] is not None:
        chain.append(state[1])
        state = parents[state]
    chain.reverse()
    _cost, side, snap = roots[state]
    selected_start = snap
    result = [(snap.e, router._part(snap, side))]
    used_arcs = [state[1]] if state[1] >= 0 else []
    for arc in chain:
        edge, rev = arc >> 1, arc & 1
        geometry = router._geom(edge)[0]
        result.append((edge, list(reversed(geometry)) if rev else geometry))
        used_arcs.append(arc)
    outgoing, side, snap = final_goal
    result.append((snap.e, router._part(snap, side, entering=True)))
    if outgoing >= 0:
        used_arcs.append(outgoing)
    return result, used_arcs, best, selected_start, snap
