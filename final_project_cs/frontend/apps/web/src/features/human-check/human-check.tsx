"use client";

import { useEffect, useRef, useState } from "react";
import { useSettings, useT } from "@/lib/settings";
import styles from "./human-check.module.css";

/**
 * Cloudflare Turnstile — a check that the sender is a person, shown only when Cloudflare is unsure
 * (`appearance: interaction-only`). It is on when `NEXT_PUBLIC_TURNSTILE_SITE_KEY` is set, off otherwise.
 *
 * ★The widget alone stops nothing: a bot can post without it. It counts only once the server checks the token
 *   with Cloudflare (siteverify) — that is the server's job (handed over 2026-09-28).
 */
export const TURNSTILE_SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "").trim();

const SCRIPT_ID = "cf-turnstile-api";
const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render(element: HTMLElement, options: Record<string, unknown>): string;
  reset(widgetId: string): void;
  remove(widgetId: string): void;
}
declare global { interface Window { turnstile?: TurnstileApi } }

let loading: Promise<TurnstileApi> | null = null;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null ?? Object.assign(document.createElement("script"), { id: SCRIPT_ID, src: SCRIPT_URL, async: true });
    script.addEventListener("load", () => window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile missing")));
    script.addEventListener("error", () => { loading = null; reject(new Error("turnstile load failed")); });
    if (!script.isConnected) document.head.appendChild(script);
  });
  return loading;
}

/**
 * Renders the check and hands its token up. `resetKey` changing asks for a fresh token (a token is good for one
 * submission). A load failure is said, not hidden: without the check the plan cannot be sent.
 */
export function HumanCheck({ onToken, resetKey }: { onToken: (token: string | null) => void; resetKey: number }) {
  const t = useT();
  const { language } = useSettings();
  const box = useRef<HTMLDivElement>(null);
  const widget = useRef<string | null>(null);
  const report = useRef(onToken);
  const [failed, setFailed] = useState(false);
  useEffect(() => { report.current = onToken; }, [onToken]);

  useEffect(() => {
    let cancelled = false;
    loadTurnstile().then((api) => {
      if (cancelled || !box.current) return;
      widget.current = api.render(box.current, {
        sitekey: TURNSTILE_SITE_KEY,
        appearance: "interaction-only",
        language: language === "ko" ? "ko" : "en",
        callback: (token: string) => { setFailed(false); report.current(token); },
        "expired-callback": () => report.current(null),
        "error-callback": () => { setFailed(true); report.current(null); },
      });
    }).catch(() => { if (!cancelled) setFailed(true); });
    return () => {
      cancelled = true;
      if (widget.current && window.turnstile) window.turnstile.remove(widget.current);
      widget.current = null;
    };
  }, [language]);

  useEffect(() => {
    if (resetKey === 0 || !widget.current || !window.turnstile) return;
    report.current(null);
    window.turnstile.reset(widget.current);
  }, [resetKey]);

  return <div className={styles.check}>
    <div ref={box} />
    {failed && <p className={styles.error} role="alert">{t("사람 확인을 불러오지 못했어요. 잠시 뒤 새로고침해 주세요.", "Could not load the human check. Please reload in a moment.")}</p>}
  </div>;
}
