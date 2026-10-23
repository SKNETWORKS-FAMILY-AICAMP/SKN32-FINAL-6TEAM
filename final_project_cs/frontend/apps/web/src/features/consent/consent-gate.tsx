"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Button, ButtonLink } from "@/components/ui";
import { DeviceFrame } from "@/components/layout/device-frame";
import { Onboarding } from "@/features/onboarding/onboarding";
import { CONSENT_REQUIRED_EVENT, SESSION_CHANGED_EVENT, probeSession } from "@/lib/live/client";
import { nextIsReplace } from "@/lib/nav-history";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { CONSENT_CHECK_STEPS, reconcileConsents, type ConsentCheckProgress, type ReconcileResult } from "./consent-sync";
import { useRequiredConsents, useConsentsSynced } from "./consent-store";
import styles from "./consent.module.css";
import { notificationLoginPath, notificationTripAccess } from "./notification-entry";

/**
 * 약관에 동의하지 않아도 열리는 화면: 첫 소개, 약관 화면(시작), 소셜 로그인이 돌아오는 화면(로그인하면 서버에 있는 동의가 이 브라우저로 온다).
 * ★`[2026-10-16 사용자 결정 — ST4F-601 로그인 먼저]` 로그인 화면(`/mypage/account`)도 연다 — 「로그인 · 가입」이 약관 · 디스코드 · 취향 화면을 거쳐 계획 담기로 끝나던 것.
 *   서버도 로그인 · 세션 · 동의 길은 동의 없이 받는다(`consents.EXEMPT_PREFIXES`). 로그인한 뒤 서버에 동의가 없으면 가려던 화면에서 약관만 받는다.
 */
// `[2026-10-17 ST4F-604]` 공지사항 게시판도 연다 — 공지는 누구에게나 보이는 것이고(서버도 세션 없이 준다), 맨 위 배너도 약관 전부터 뜬다.
// `[2026-10-22 ST4F-717]` 이용 방법도 연다 — 약관 전 화면(소개 · 시작 · 계획 담기)의 (?) 가 이리로 오고, 읽는 것은 운영 스위치(세션 없이 읽음)뿐이다.
const OPEN_PATHS = new Set<string>([routes.home, routes.start, routes.authDone, routes.myPageAccount, routes.notices, routes.help]);
/** `[2026-10-12 사용자 지시]` 동의 확인 진행 카드는 확인이 이 시간을 넘게 걸릴 때만 보인다. 빨리 끝나면 아무것도 안 뜬다(「동의하고 다음으로」 뒤 로딩이 바로 뜨던 문제). */
const CHECK_CARD_AFTER_MS = 3000;

/** `[2026-10-16 ST4F-601]` 약관 화면 주소 — 가려던 화면(지금 주소)을 `returnTo` 로 실어, 동의가 끝나면 그 화면으로 돌아간다. */
function termsAddress(): string {
  return `${routes.start}?terms=required&returnTo=${encodeURIComponent(window.location.pathname + window.location.search)}`;
}

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
  const synced = useConsentsSynced();
  const search = ready ? window.location.search : "";
  const notificationEntry = notificationLoginPath(pathname, search, false) !== null;
  const [loginTarget, setLoginTarget] = useState<string | null>(null);
  const [result, setResult] = useState<ReconcileResult | null>(null);
  const [progress, setProgress] = useState<ConsentCheckProgress | null>(null);
  const [checking, setChecking] = useState(true);
  const [visible, setVisible] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [retry, setRetry] = useState(0);
  const [admitted, setAdmitted] = useState(false);
  const [sessionError, setSessionError] = useState(false);
  // `[2026-10-17 ST4F-604]` 공지 한 장(`/notices/<id>`)도 공지사항처럼 동의 없이 열린다.
  const open = OPEN_PATHS.has(pathname) || pathname.startsWith(`${routes.notices}/`);

  // 처음 읽은 동의로 열었던 화면은 버전 재확인 동안에도 유지한다.
  if (ready && agreed && synced && !admitted) setAdmitted(true);

  useEffect(() => {
    if (!ready || open) return;
    let cancelled = false;
    let running = false;
    const run = () => {
      // 세션 확인 자체도 변경 알림을 낸다. 같은 확인을 대기열에 겹치지 않는다.
      if (running) return;
      running = true;
      setChecking(true);
      setSessionError(false);
      setLoginTarget(null);
      setResult(null);
      setProgress(null);
      void (async () => {
        const session = await probeSession(language);
        if (session?.registrationPending) {
          if (!cancelled) {
            setLoginTarget(`${routes.start}?terms=required&signup=1&returnTo=${encodeURIComponent(pathname + search)}`);
            setChecking(false);
          }
          return;
        }
        if (notificationEntry) {
          let canAccess = false;
          try { canAccess = Boolean(session) && await notificationTripAccess(pathname, language); }
          catch (error) { if (!cancelled) setSessionError(true); throw error; }
          const login = notificationLoginPath(pathname, search, canAccess);
          if (login) {
            if (!cancelled) { setLoginTarget(login); setChecking(false); }
            return;
          }
        }
        const answer = await reconcileConsents(language, (next) => { if (!cancelled) setProgress(next); });
        if (!cancelled) { setResult(answer); setChecking(false); }
      })().catch(() => {
        if (!cancelled) { setResult("failed"); setChecking(false); }
      }).finally(() => { running = false; });
    };
    run();
    window.addEventListener(CONSENT_REQUIRED_EVENT, run);
    window.addEventListener(SESSION_CHANGED_EVENT, run);
    return () => { cancelled = true; window.removeEventListener(CONSENT_REQUIRED_EVENT, run); window.removeEventListener(SESSION_CHANGED_EVENT, run); };
  }, [ready, open, language, retry, notificationEntry, pathname, search]);

  useEffect(() => {
    if (!checking || !ready || open) return;
    const started = performance.now();
    const delay = setTimeout(() => setVisible(true), CHECK_CARD_AFTER_MS);
    const tick = setInterval(() => setElapsed(Math.floor((performance.now() - started) / 1000)), 1000);
    return () => { clearTimeout(delay); clearInterval(tick); setVisible(false); setElapsed(0); };
  }, [checking, ready, open]);

  useEffect(() => { if (loginTarget && !open) { nextIsReplace(); router.replace(loginTarget); } }, [loginTarget, open, router]);

  const loginPending = !open && (loginTarget !== null || (notificationEntry && checking));
  const needsTerms = !loginPending && ready && !agreed && result !== null && result !== "outdated" && result !== "failed";
  useEffect(() => { if (needsTerms && !open) { nextIsReplace(); router.replace(termsAddress()); } }, [needsTerms, open, router]);

  // ★`[2026-10-19 ST4F-611]` 「서버와 맞춤(synced)」은 처음 열어 줄 때만 기다린다. 이미 연 화면은 고객이 선택 동의를 철회해 사본을 보내는 동안(`saveConsents` 가
  //   synced 를 잠깐 false 로 둔다) 내리지 않는다 — 내렸다 다시 그리면 「선택 약관 동의」 창이 철회 결과를 보이기 전에 닫혔다(consent.spec 철회 시험 셋).
  //   필수 동의가 빠지면(`agreed` false) 그대로 바로 닫는다.
  const showPage = open || (ready && result !== "outdated" && (!loginPending && ((agreed && (synced || admitted)) || (checking && admitted))));
  const showError = !open && (result === "failed" || result === "outdated");
  const step = progress?.step ?? 0;
  const title = pathname.startsWith(routes.myPage) ? t("설정", "Settings")
    : pathname === routes.newTrip ? t("새 여행", "New trip") : t("나의 여행", "My trips");
  return <>
    {/* ★`[2026-10-12]` 동의 사본이 없으면 확인하는 동안 열린 약관을 먼저 보인다. 확인 뒤 `/start?terms=required` 로 가며 온보딩이 다시 그려질 때
        열림 애니메이션이 두 번 돌지 않게, 온보딩이 두 번째 그림에서는 애니메이션을 끈다(`onboarding.tsx` 의 `termsShownOnce`). */}
    {showPage ? children : ready && (!agreed || !synced) && !loginPending && result !== "outdated" ? <Onboarding termsRequired returnTo={window.location.pathname + window.location.search} /> : <DeviceFrame scroll headerInert>
      {/* 동의 확인 전에 보호 API를 호출하지 않는다. 기존 화면과 같은 틀·배치를 먼저 보여 준다. */}
      <main className={styles.waitingPage} aria-busy="true" data-consent-shell>
        <h1>{loginPending ? t("로그인 상태를 확인하고 있어요", "Checking sign-in") : title}</h1>
        {loginTarget && <ButtonLink href={loginTarget} variant="primary">{t("여행을 등록한 계정으로 로그인", "Sign in with the account that owns this trip")}</ButtonLink>}
        <div className={styles.placeholder} aria-hidden="true" />
        <div className={styles.placeholder} aria-hidden="true" />
        <div className={styles.placeholder} aria-hidden="true" />
      </main>
    </DeviceFrame>}
    {((checking && visible && (agreed || admitted) && !open) || showError) && <div className={styles.checkLayer} data-consent-check>
      <section className={styles.checkCard} role={showError ? "alert" : "status"} aria-label={t("약관 확인 진행", "Consent check progress")}>
        {showError ? <>
          <h2>{result === "outdated" ? t("약관이 새로 바뀌었어요", "The terms have been updated") : sessionError ? t("로그인 상태를 확인하지 못했어요", "Could not check your sign-in") : t("동의 기록을 확인하지 못했어요", "Could not check your consent record")}</h2>
          <p>{result === "outdated" ? t("새로 고침해서 새 약관을 확인해 주세요.", "Reload to see the new terms.") : sessionError ? t("연결을 확인한 뒤 다시 시도해 주세요.", "Check your connection and try again.") : t("기존 동의는 그대로 두었어요. 다시 확인해 주세요.", "Your existing consent was kept. Please try again.")}</p>
          <div className={styles.checkActions}>
            <Button variant="primary" onClick={() => result === "outdated" ? window.location.reload() : setRetry((value) => value + 1)}>{result === "outdated" ? t("새로 고침", "Reload") : t("다시 확인하기", "Check again")}</Button>
            {/* 서버 확인이 안 될 때도 고객이 직접 동의 화면으로 가서 다시 동의할 수 있게 한다. 오류 카드를 먼저 걷어야 약관 화면이 가려지지 않는다. */}
            {result === "failed" && !sessionError && <Button variant="quiet" onClick={() => { setResult(null); router.push(termsAddress()); }}>{t("동의 다시 하기", "Agree again")}</Button>}
          </div>
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
