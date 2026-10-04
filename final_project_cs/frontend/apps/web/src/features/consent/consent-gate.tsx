"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { CONSENT_REQUIRED_EVENT, SESSION_CHANGED_EVENT } from "@/lib/live/client";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { reconcileConsents, type ReconcileResult } from "./consent-sync";
import { useRequiredConsents } from "./consent-store";
import styles from "./consent.module.css";

/** 약관에 동의하지 않아도 열리는 화면: 첫 소개, 약관 화면(시작), 소셜 로그인이 돌아오는 화면(로그인하면 서버에 있는 동의가 이 브라우저로 온다). */
const OPEN_PATHS = new Set<string>([routes.home, routes.start, routes.authDone]);

const subscribeNothing = () => () => {};
/** 서버 렌더와 첫 화면은 false, 화면이 붙은 뒤 true - 동의 사본(브라우저 저장소)은 그 뒤에야 읽힌다. */
function useClientReady(): boolean {
  return useSyncExternalStore(subscribeNothing, () => true, () => false);
}

/**
 * `[2026-10-05 사용자 지시]` 필수 약관에 동의하지 않으면 앱을 쓸 수 없다. 화면 쪽 문이다 - 진짜 막는 것은 서버(동의 기록이 없으면 403 `consent_required`)이고,
 * 이 문은 그 403 을 고객이 읽을 수 있는 화면(약관)으로 바꿔 준다.
 *   - 동의한 사본이 있으면 바로 연다. 백그라운드에서 서버 기록을 읽어 맞춘다(다른 기기에서 철회했으면 이 문이 닫힌다).
 *   - 동의가 없으면 서버 기록을 한 번 확인한 뒤(로그인한 계정은 이미 동의했을 수 있다) 약관 화면으로 보낸다. 서버에 물을 세션이 없는 방문자는 묻지 않고 바로 보낸다.
 *   - 서버가 이 앱이 모르는 새 약관 버전이라고 하면(`outdated`) 약관을 다시 받을 수 없으니 새로 고침을 안내한다.
 */
export function ConsentGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const { language } = useSettings();
  const ready = useClientReady();
  const agreed = useRequiredConsents();
  const [result, setResult] = useState<ReconcileResult | null>(null);
  const open = OPEN_PATHS.has(pathname);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const run = () => { void reconcileConsents(language).then((answer) => { if (!cancelled) setResult(answer); }); };
    run();
    window.addEventListener(CONSENT_REQUIRED_EVENT, run);
    window.addEventListener(SESSION_CHANGED_EVENT, run);
    return () => { cancelled = true; window.removeEventListener(CONSENT_REQUIRED_EVENT, run); window.removeEventListener(SESSION_CHANGED_EVENT, run); };
  }, [ready, language]);

  const needsTerms = ready && !agreed && result !== null && result !== "outdated";
  useEffect(() => { if (needsTerms && !open) router.replace(routes.start); }, [needsTerms, open, router]);

  if (open) return <>{children}</>;
  if (!ready) return null;
  if (result === "outdated") {
    return <main className={styles.gate} role="alert">
      <h1>{t("약관이 새로 바뀌었어요", "The terms have been updated")}</h1>
      <p>{t("이 화면은 옛 버전이에요. 새로 고침해서 새 약관을 확인해 주세요.", "This page is an older version. Reload to see the new terms.")}</p>
      <Button variant="primary" onClick={() => window.location.reload()}>{t("새로 고침", "Reload")}</Button>
    </main>;
  }
  if (agreed) return <>{children}</>;
  return <main className={styles.gate}><p role="status">{t("약관 동의를 확인하는 중이에요…", "Checking your consent…")}</p></main>;
}
