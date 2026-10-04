"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Panel, ButtonLink } from "@/components/ui";
import { clearFlow, exchangeTicket, localPath, pendingFlow, providerName, socialErrorText, type SocialResult } from "@/lib/live/auth";
import { LiveError } from "@/lib/live/client";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./account.module.css";

type State = { kind: "working" } | { kind: "ok"; result: SocialResult; back: string } | { kind: "error"; text: string; back: string };

/**
 * `[2026-10-03]` The page a social sign-in ends on (`/auth/done?ticket=…` or `?error=…`, sent here by the server after the provider).
 *   - the ticket leaves the address bar at once (`replaceState`), so it is not left in history or shared by copying the address;
 *   - it is swapped for the result together with the nonce THIS browser made when it started the sign-in — a ticket this browser did
 *     not start (a link someone sent) has no nonce here and is refused before anything is asked of the server;
 *   - a sign-in (not a link) brings a session cookie (`exchangeTicket` asks for it and keeps its CSRF token in memory); the guest session this
 *     browser had is ended by the server. `[2026-10-04]` No key to keep any more.
 */
export function SocialDone() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [state, setState] = useState<State>({ kind: "working" });
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.search);
    const ticket = params.get("ticket"), error = params.get("error");
    window.history.replaceState(null, "", routes.authDone);
    const flow = pendingFlow();
    const back = localPath(flow?.returnTo ?? routes.myPage);
    clearFlow();
    void (async () => {
      if (error) { setState({ kind: "error", text: socialErrorText(error, t), back }); return; }
      if (!ticket || !flow) { setState({ kind: "error", text: socialErrorText("ticket_invalid", t), back }); return; }
      try {
        const result = await exchangeTicket(ticket, flow.nonce, language);
        void queryClient.invalidateQueries();
        setState({ kind: "ok", result, back });
      } catch (failure) {
        setState({ kind: "error", text: failure instanceof LiveError && failure.code === "ticket_invalid" ? socialErrorText("ticket_invalid", t) : failure instanceof Error ? failure.message : String(failure), back });
      }
    })();
  }, [language, queryClient, t]);

  if (state.kind === "working") return <Panel className={styles.done}><p role="status">{t("로그인을 마무리하는 중이에요…", "Finishing the sign-in…")}</p></Panel>;
  if (state.kind === "error") {
    return <Panel className={styles.done}>
      <h1>{t("로그인하지 못했어요", "Could not sign in")}</h1>
      <p role="alert">{state.text}</p>
      <div className={styles.actions}><ButtonLink href={state.back} variant="primary">{t("돌아가기", "Go back")}</ButtonLink></div>
    </Panel>;
  }
  const { result } = state;
  const name = t(...providerName(result.provider));
  const trips = result.trips !== null ? (result.trips > 0 ? t(` 여행 ${result.trips}개를 열 수 있어요.`, ` ${result.trips} trip${result.trips === 1 ? "" : "s"} can be opened.`) : t(" 아직 등록한 여행은 없어요.", " There are no trips yet.")) : "";
  const title = result.outcome === "linked" ? t(`${name} 계정을 연결했어요`, `${name} account linked`)
    : result.outcome === "created" ? t(`${name} 계정으로 시작했어요`, `Started with your ${name} account`)
      : t(`${name} 계정으로 로그인했어요`, `Signed in with your ${name} account`);
  const text = result.outcome === "linked"
    ? t("이제 이 기기의 여행이 계정에 보관돼요. 어느 기기에서든 이 계정으로 로그인해 열 수 있고, 게스트 제한도 없어졌어요. 이메일 같은 개인 정보는 받지 않았어요.", "Your trips are now kept with the account. Sign in with it on any device to open them, and the guest limits are gone. No personal details such as your email were taken.")
    : result.outcome === "created"
      ? t("새 계정으로 시작했어요. 이 기기에 로그인된 상태예요.", "You started with a new account and are signed in on this device.")
      : t("이 계정으로 이 기기에 로그인했어요.", "You are signed in on this device with this account.") + trips;
  return <Panel className={styles.done}>
    <h1>{title}</h1>
    <p role="status">{text}</p>
    <div className={styles.actions}>
      <ButtonLink href={result.outcome === "signed_in" ? routes.trips : state.back} variant="primary">{result.outcome === "signed_in" ? t("여행 목록 보기", "View my trips") : t("계속하기", "Continue")}</ButtonLink>
      {result.outcome !== "linked" && <ButtonLink href={routes.myPage}>{t("마이페이지", "My page")}</ButtonLink>}
    </div>
  </Panel>;
}
