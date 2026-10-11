"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { DeviceFrame } from "@/components/layout/device-frame";
import { Onboarding } from "@/features/onboarding/onboarding";
import { CONSENT_REQUIRED_EVENT, SESSION_CHANGED_EVENT } from "@/lib/live/client";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { CONSENT_CHECK_STEPS, reconcileConsents, type ConsentCheckProgress, type ReconcileResult } from "./consent-sync";
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
  const [progress, setProgress] = useState<ConsentCheckProgress | null>(null);
  const [checking, setChecking] = useState(true);
  const [visible, setVisible] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [retry, setRetry] = useState(0);
  const [admitted, setAdmitted] = useState(false);
  const open = OPEN_PATHS.has(pathname);

  // 처음 읽은 동의로 열었던 화면은 버전 재확인 동안에도 유지한다.
  if (ready && agreed && !admitted) setAdmitted(true);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    let running = false;
    const run = () => {
      // 세션 확인 자체도 변경 알림을 낸다. 같은 확인을 대기열에 겹치지 않는다.
      if (running) return;
      running = true;
      setChecking(true);
      setResult(null);
      setProgress(null);
      void reconcileConsents(language, (next) => { if (!cancelled) setProgress(next); }).then((answer) => {
        if (!cancelled) { setResult(answer); setChecking(false); }
      }).finally(() => { running = false; });
    };
    run();
    window.addEventListener(CONSENT_REQUIRED_EVENT, run);
    window.addEventListener(SESSION_CHANGED_EVENT, run);
    return () => { cancelled = true; window.removeEventListener(CONSENT_REQUIRED_EVENT, run); window.removeEventListener(SESSION_CHANGED_EVENT, run); };
  }, [ready, language, retry]);

  useEffect(() => {
    if (!checking || !ready) return;
    const started = performance.now();
    const delay = setTimeout(() => setVisible(true), 100);
    const tick = setInterval(() => setElapsed(Math.floor((performance.now() - started) / 1000)), 1000);
    return () => { clearTimeout(delay); clearInterval(tick); setVisible(false); setElapsed(0); };
  }, [checking, ready]);

  const needsTerms = ready && !agreed && result !== null && result !== "outdated" && result !== "failed";
  useEffect(() => { if (needsTerms && !open) router.replace(`${routes.start}?terms=required`); }, [needsTerms, open, router]);

  const showPage = open || (ready && result !== "outdated" && (agreed || (checking && admitted)));
  const showError = result === "failed" || result === "outdated";
  const step = progress?.step ?? 0;
  const title = pathname.startsWith(routes.myPage) ? t("마이페이지", "My page")
    : pathname === routes.newTrip ? t("새 여행", "New trip") : t("나의 여행", "My trips");
  return <>
    {showPage ? children : ready && !agreed && result !== "outdated" ? <Onboarding termsRequired /> : <DeviceFrame scroll headerInert>
      {/* 동의 확인 전에 보호 API를 호출하지 않는다. 기존 화면과 같은 틀·배치를 먼저 보여 준다. */}
      <main className={styles.waitingPage} aria-busy="true" data-consent-shell>
        <h1>{title}</h1>
        <div className={styles.placeholder} aria-hidden="true" />
        <div className={styles.placeholder} aria-hidden="true" />
        <div className={styles.placeholder} aria-hidden="true" />
      </main>
    </DeviceFrame>}
    {((checking && visible && (agreed || admitted) && !open) || showError) && <div className={styles.checkLayer} data-consent-check>
      <section className={styles.checkCard} role={showError ? "alert" : "status"} aria-label={t("약관 확인 진행", "Consent check progress")}>
        {showError ? <>
          <h2>{result === "outdated" ? t("약관이 새로 바뀌었어요", "The terms have been updated") : t("동의 기록을 확인하지 못했어요", "Could not check your consent record")}</h2>
          <p>{result === "outdated" ? t("새로 고침해서 새 약관을 확인해 주세요.", "Reload to see the new terms.") : t("기존 동의는 그대로 두었어요. 다시 확인해 주세요.", "Your existing consent was kept. Please try again.")}</p>
          <Button variant="primary" onClick={() => result === "outdated" ? window.location.reload() : setRetry((value) => value + 1)}>{result === "outdated" ? t("새로 고침", "Reload") : t("다시 확인하기", "Check again")}</Button>
        </> : <>
          <div className={styles.checkHead}><h2>{t("앱 사용 준비", "Getting ready")}</h2><span>{elapsed}{t("초", " s")}</span></div>
          <p className={styles.checkNow}>{progress?.lost ? t("연결이 끊겨 다시 확인하고 있어요", "Reconnecting to check again")
            : progress?.recording ? t("이 브라우저의 동의를 기록하고 있어요", "Recording this browser’s consent") : t(CONSENT_CHECK_STEPS[step][0], CONSENT_CHECK_STEPS[step][1])}</p>
          <p className={styles.checkCount}>{progress?.completed ?? 0}/{CONSENT_CHECK_STEPS.length}{t("단계 완료", " steps complete")}{progress?.slow ? t(" · 응답이 늦어지고 있어요", " · The reply is taking longer") : ""}</p>
          <ol className={styles.checkSteps}>
            {CONSENT_CHECK_STEPS.map((label, index) => <li key={label[1]} data-state={index < step ? "done" : index === step ? "current" : "waiting"} aria-current={index === step ? "step" : undefined}>
              <span aria-hidden="true">{index < step ? "✓" : index + 1}</span>{t(label[0], label[1])}
              <small>{index < step ? t("완료", "Done") : index === step ? t("진행 중", "In progress") : t("대기", "Waiting")}</small>
            </li>)}
          </ol>
        </>}
      </section>
    </div>}
  </>;
}
