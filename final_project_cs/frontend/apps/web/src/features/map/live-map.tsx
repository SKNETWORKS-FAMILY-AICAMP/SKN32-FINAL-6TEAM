"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { controlsLayout, EdgeChips, MapControls } from "./map-controls";
import type { MapAdapter, MapController, MapView, MapViewProps, StayPoint } from "./model";
import styles from "./map.module.css";
import { routeLabels } from "./route-labels";
import { MODE_NAMES } from "./route-lines";
import { LINE_TONE_VARIABLE } from "./providers/lines";
import { edgeChips } from "./map-geometry";

const NO_STAYS: StayPoint[] = [];
export function MapUnavailable({ message }: { message: string }) {
  return <div className={styles.unavailable} role="alert"><strong>지도를 표시할 수 없어요</strong><p>{message}</p></div>;
}

export function LiveMap({ adapter, name, points, selectedId, onSelect, lines, onSelectLine, selectedLineId, topInset, bottomInset, me = null, stays = NO_STAYS, onZoom, onInteractionChange, meAvailable = false }: MapViewProps & { adapter: MapAdapter; name: string }) {
  const surface = useRef<HTMLDivElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const controller = useRef<MapController | null>(null);
  const latest = useRef({ points, selectedId, onSelect, lines, onSelectLine, selectedLineId, topInset, bottomInset, me, stays, onZoom, onInteractionChange });
  const refreshLayout = useCallback(() => {
    controller.current?.relayout?.();
    const node = surface.current;
    if (!node) return;
    const occupied = [...node.querySelectorAll<HTMLElement>("[data-pin-body], [data-edge-chip], [data-map-controls]")]
      .filter((item) => getComputedStyle(item).visibility !== "hidden").map((item) => item.getBoundingClientRect());
    node.querySelectorAll<HTMLElement>("[data-route-label]").forEach((label) => {
      const box = label.getBoundingClientRect();
      const blocked = occupied.some((other) => Math.min(box.right,other.right)>Math.max(box.left,other.left)-4 && Math.min(box.bottom,other.bottom)>Math.max(box.top,other.top)-4);
      label.style.visibility = blocked ? "hidden" : "";
      if (!blocked) occupied.push(box);
    });
  }, []);
  const [attempt, setAttempt] = useState(0);
  // `[2026-10-03 사용자 지시]` The map's buttons show while the pointer is over the map, or for a few seconds after it is touched (a phone has no hover).
  const [awake, setAwake] = useState(false);
  const asleep = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const wake = () => { setAwake(true); clearTimeout(asleep.current); asleep.current = setTimeout(() => setAwake(false), 3_500); };
  useEffect(() => () => clearTimeout(asleep.current), []);
  const [state, setState] = useState<{ status: "loading" | "ready" | "error"; message?: string }>({ status: "loading" });
  // `[2026-10-05 사용자 선택]` What the map shows (for the scale ruler and the chips of stops out of view), how big the map is, and whether the customer folded its buttons.
  const [view, setView] = useState<MapView | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [folded, setFolded] = useState(true);
  const [moving, setMoving] = useState(false);
  const settled = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => { latest.current.onInteractionChange = onInteractionChange; }, [onInteractionChange]);
  useEffect(() => () => clearTimeout(settled.current), []);


  useEffect(() => {
    latest.current = { ...latest.current, points, selectedId, onSelect, lines, onSelectLine, selectedLineId, topInset, bottomInset, onZoom };
    controller.current?.update(points, selectedId, lines, selectedLineId);
  }, [points, selectedId, onSelect, lines, onSelectLine, selectedLineId, topInset, bottomInset, onZoom]);

  // `[2026-10-05 사용자 지시]` 「내 위치」 and the stays go to the map on their own: a new position does not redraw the pins.
  useEffect(() => {
    latest.current = { ...latest.current, me };
    controller.current?.setMe(me);
  }, [me]);
  useEffect(() => {
    latest.current = { ...latest.current, stays };
    controller.current?.setStays(stays);
  }, [stays]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    // Each effect owns its host: a cancelled async mount must not clear a newer map.
    const host = document.createElement("div");
    host.style.width = "100%";
    host.style.height = "100%";
    element.append(host);
    let cancelled = false;
    let observer: ResizeObserver | undefined;
    let instance: MapController | undefined;
    let failed = false;
    const fail = (error: Error) => {
      failed = true;
      if (!cancelled) setState({ status: "error", message: error.message });
    };
    void adapter.create(host, {
      ...latest.current,
      onSelect: (id) => latest.current.onSelect(id),
      onSelectLine: (id) => latest.current.onSelectLine?.(id),
      onZoom: (zoom) => latest.current.onZoom?.(zoom),          // [2026-10-05] the screen above asks for the detailed route lines once this says the map is zoomed in
      onView: (next) => { if (!cancelled) setView(next); },
      onInteractionChange: (active) => {
        clearTimeout(settled.current);
        if (active) { setMoving(true); latest.current.onInteractionChange?.(true); }
        else settled.current = setTimeout(() => { if (!cancelled) { setMoving(false); latest.current.onInteractionChange?.(false); } }, 180);
      },
      onError: fail,
    }).then((created) => {
      if (cancelled) { created.destroy(); return; }
      instance = created;
      controller.current = created;
      created.update(latest.current.points, latest.current.selectedId, latest.current.lines, latest.current.selectedLineId);
      created.setMe(latest.current.me);
      created.setStays(latest.current.stays);
      observer = new ResizeObserver(([entry]) => {
        if (!entry) return;
        setSize({ width: Math.round(entry.contentRect.width), height: Math.round(entry.contentRect.height) });
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) created.resize();
      });
      observer.observe(element);
      if (!failed) setState({ status: "ready" });
    }).catch((error: unknown) => fail(error instanceof Error ? error : new Error("지도 연결에 실패했어요.")));
    return () => {
      cancelled = true;
      observer?.disconnect();
      instance?.destroy();
      host.remove();
      if (controller.current === instance) controller.current = null;
    };
  }, [adapter, attempt]);

  const ready = state.status === "ready";
  const canFit = points.length > 1;
  const meButton = meAvailable ? (me ? "ready" : "waiting") : "off";
  const count = 2 + (canFit ? 1 : 0) + (meAvailable ? 1 : 0);
  const layout = controlsLayout(size, topInset ?? 0, count);
  const [controlArea, setControlArea] = useState<{ left: number; top: number; right: number; bottom: number }[]>([]);
  useLayoutEffect(() => {
    const node = surface.current, controls = node?.querySelector<HTMLElement>("[data-map-controls]");
    if (!node || !controls) return;
    const measure = () => {
      const root = node.getBoundingClientRect(), box = controls.getBoundingClientRect();
      const next = [{ left: box.left-root.left, top: box.top-root.top, right: box.right-root.left, bottom: box.bottom-root.top }];
      setControlArea((old) => JSON.stringify(old) === JSON.stringify(next) ? old : next);
    };
    measure();
    const observer = new ResizeObserver(measure); observer.observe(controls);
    return () => observer.disconnect();
  }, [ready, folded, layout, size.width, size.height, topInset]);
  // 칩과 마커가 같은 결과를 쓴다. layout effect로 브라우저가 그리기 전에
  // 표시를 교대하므로 지도 이동 중에도 같은 일정이 두 번 나타나지 않는다.
  const chips = useMemo(() => ready && view ? edgeChips(view, points, {
    top: topInset ?? 0, bottom: bottomInset ?? 0, obstacles: controlArea,
  }) : [], [ready, view, points, topInset, bottomInset, controlArea]);
  useLayoutEffect(() => { controller.current?.setHiddenPoints(chips.flatMap((chip) => chip.ids)); refreshLayout(); }, [chips, folded, refreshLayout]);
  return <div ref={surface} className={styles.live} role="region" aria-label="여행 지도" aria-busy={state.status === "loading"} data-moving={moving || undefined} data-awake={awake || undefined} onPointerDown={wake}>
    <div className={styles.canvas} ref={container} aria-label={`${name} 지도`} />
    {ready && <div className={styles.routeLabels} aria-hidden="true">
      {routeLabels(view, lines ?? [], points, topInset, bottomInset).map((label) => <span key={label.id} data-route-label={label.id} data-mode={label.mode}
        className={styles.routeLabel} style={{ left: label.x, top: label.y, color: `var(${LINE_TONE_VARIABLE[label.mode ?? "unknown"]})` }}>
        {MODE_NAMES[label.mode ?? "unknown"]}{label.dashed ? " · 직선 연결" : ""}
      </span>)}
    </div>}
    {state.status === "loading" && <div className={styles.overlay} role="status">지도를 불러오고 있어요…</div>}
    {state.status === "error" && <div className={styles.overlay} role="alert"><strong>지도를 불러오지 못했어요</strong><p>{state.message}</p><Button variant="secondary" onClick={() => { setState({ status: "loading" }); setAttempt((value) => value + 1); }}>지도 다시 불러오기</Button></div>}
    {ready && points.length > 0 && <EdgeChips chips={chips} width={view?.width ?? 0} moving={moving} onLayout={refreshLayout}
      onGo={(ids) => {
        const target = points.find((point) => point.id === ids[0]);
        if (!target) return;
        onSelect(target.id);
        controller.current?.centerOn(target.coordinates, true);
      }} />}
    {ready && <MapControls view={view} topInset={topInset ?? 0} layout={layout} folded={folded} onFold={(next) => { setFolded(next); }} canFit={canFit} me={meButton}
      onZoom={(delta) => controller.current?.zoomBy(delta)} onFit={() => controller.current?.fit()} onLocate={() => { if (me) controller.current?.centerOn(me.coordinates); }} />}
    {ready && points.length === 0 && <p className={styles.emptyNotice} role="status" data-empty-map-notice style={{ top: (topInset ?? 0) + 12 }}>표시할 장소 좌표가 없어요.</p>}
  </div>;
}
