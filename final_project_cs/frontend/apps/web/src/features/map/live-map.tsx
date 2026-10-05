"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { controlsLayout, EdgeChips, MapControls } from "./map-controls";
import type { MapAdapter, MapController, MapView, MapViewProps, StayPoint } from "./model";
import styles from "./map.module.css";

const NO_STAYS: StayPoint[] = [];
/** The folded state of the map's buttons is kept for the customer (a convenience: the page works the same without it). */
const FOLD_KEY = "triPilot.mapControlsFolded";
const readFolded = () => { try { return window.localStorage.getItem(FOLD_KEY) === "1"; } catch { return false; } };
const writeFolded = (folded: boolean) => { try { window.localStorage.setItem(FOLD_KEY, folded ? "1" : "0"); } catch { /* private window: it just is not kept */ } };

export function MapUnavailable({ message }: { message: string }) {
  return <div className={styles.unavailable} role="alert"><strong>지도를 표시할 수 없어요</strong><p>{message}</p></div>;
}

export function LiveMap({ adapter, name, points, selectedId, onSelect, lines, topInset, bottomInset, me = null, stays = NO_STAYS, onZoom, meAvailable = false }: MapViewProps & { adapter: MapAdapter; name: string }) {
  const container = useRef<HTMLDivElement>(null);
  const controller = useRef<MapController | null>(null);
  const latest = useRef({ points, selectedId, onSelect, lines, topInset, me, stays, onZoom });
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
  const [folded, setFolded] = useState(readFolded);

  useEffect(() => {
    latest.current = { ...latest.current, points, selectedId, onSelect, lines, topInset, onZoom };
    controller.current?.update(points, selectedId, lines);
  }, [points, selectedId, onSelect, lines, topInset, onZoom]);

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
      onZoom: (zoom) => latest.current.onZoom?.(zoom),          // [2026-10-05] the screen above asks for the detailed route lines once this says the map is zoomed in
      onView: (next) => { if (!cancelled) setView(next); },
      onError: fail,
    }).then((created) => {
      if (cancelled) { created.destroy(); return; }
      instance = created;
      controller.current = created;
      created.update(latest.current.points, latest.current.selectedId, latest.current.lines);
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
  const closed = folded || layout === "tab";
  return <div className={styles.live} role="region" aria-label="여행 지도" aria-busy={state.status === "loading"} data-awake={awake || undefined} onPointerDown={wake}>
    <div className={styles.canvas} ref={container} aria-label={`${name} 지도`} />
    {state.status === "loading" && <div className={styles.overlay} role="status">지도를 불러오고 있어요…</div>}
    {state.status === "error" && <div className={styles.overlay} role="alert"><strong>지도를 불러오지 못했어요</strong><p>{state.message}</p><Button variant="secondary" onClick={() => { setState({ status: "loading" }); setAttempt((value) => value + 1); }}>지도 다시 불러오기</Button></div>}
    {ready && points.length > 0 && <EdgeChips view={view} points={points} topInset={topInset ?? 0} bottomInset={bottomInset ?? 0} keepRight={closed ? 56 : layout === "row" ? 0 : 64}
      onGo={(ids) => {
        const target = points.find((point) => point.id === ids[0]);
        if (!target) return;
        onSelect(target.id);
        controller.current?.centerOn(target.coordinates, true);
      }} />}
    {ready && <MapControls view={view} topInset={topInset ?? 0} layout={layout} folded={folded} onFold={(next) => { setFolded(next); writeFolded(next); }} canFit={canFit} me={meButton}
      onZoom={(delta) => controller.current?.zoomBy(delta)} onFit={() => controller.current?.fit()} onLocate={() => { if (me) controller.current?.centerOn(me.coordinates); }} />}
    {ready && points.length === 0 && <p className={styles.emptyNotice}>표시할 장소 좌표가 없어요.</p>}
  </div>;
}
