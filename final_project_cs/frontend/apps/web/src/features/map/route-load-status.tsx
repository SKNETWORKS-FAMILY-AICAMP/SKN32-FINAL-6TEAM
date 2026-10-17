"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/settings";

export interface RouteLoadState { loading: boolean; error: boolean; retry: () => void }

export function RouteLoadStatus({ state }: { state?: RouteLoadState }) {
  const t = useT();
  const loading = Boolean(state?.loading);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWaiting(loading), loading ? 1000 : 0);
    return () => clearTimeout(timer);
  }, [loading]);
  if (state?.error) return <div role="status" data-route-load-error>
    <span>{t("경로선을 불러오지 못했어요.", "Could not load the route lines.")}</span>
    <button type="button" onClick={state.retry}>{t("경로 다시 불러오기", "Reload routes")}</button>
  </div>;
  return loading && waiting ? <p role="status" data-route-loading>{t("경로선을 불러오고 있어요…", "Loading route lines…")}</p> : null;
}
