"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import type { MapAdapter, MapController, MapViewProps } from "./model";
import styles from "./map.module.css";

export function MapUnavailable({ message }: { message: string }) {
  return <div className={styles.unavailable} role="alert"><strong>지도를 표시할 수 없어요</strong><p>{message}</p></div>;
}

export function LiveMap({ adapter, name, points, selectedId, onSelect }: MapViewProps & { adapter: MapAdapter; name: string }) {
  const container = useRef<HTMLDivElement>(null);
  const controller = useRef<MapController | null>(null);
  const latest = useRef({ points, selectedId, onSelect });
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ status: "loading" | "ready" | "error"; message?: string }>({ status: "loading" });

  useEffect(() => {
    latest.current = { points, selectedId, onSelect };
    controller.current?.update(points, selectedId);
  }, [points, selectedId, onSelect]);

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
      onError: fail,
    }).then((created) => {
      if (cancelled) { created.destroy(); return; }
      instance = created;
      controller.current = created;
      created.update(latest.current.points, latest.current.selectedId);
      observer = new ResizeObserver(([entry]) => {
        if (entry && entry.contentRect.width > 0 && entry.contentRect.height > 0) created.resize();
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

  return <div className={styles.live} role="region" aria-label="여행 지도" aria-busy={state.status === "loading"}>
    <div className={styles.canvas} ref={container} aria-label={`${name} 지도`} />
    {state.status === "loading" && <div className={styles.overlay} role="status">지도를 불러오고 있어요…</div>}
    {state.status === "error" && <div className={styles.overlay} role="alert"><strong>지도를 불러오지 못했어요</strong><p>{state.message}</p><Button variant="secondary" onClick={() => { setState({ status: "loading" }); setAttempt((value) => value + 1); }}>지도 다시 불러오기</Button></div>}
    {state.status === "ready" && points.length === 0 && <p className={styles.emptyNotice}>표시할 장소 좌표가 없어요.</p>}
  </div>;
}
