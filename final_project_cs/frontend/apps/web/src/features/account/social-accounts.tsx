"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { HumanCheck, TURNSTILE_SITE_KEY } from "@/features/human-check/human-check";
import { getLinks, isSocialUnsupported, providerName, startSocial, unlinkSocial, type SocialMode, type SocialProvider } from "@/lib/live/auth";
import { LiveError } from "@/lib/live/client";
import { useProfile } from "@/lib/profile";
import { useSettings, useT } from "@/lib/settings";
import { ProviderButton, ProviderIdentity } from "./provider-button";
import { useAuthProviders } from "./use-auth-providers";
import styles from "./account.module.css";

const linksKey = (language: string) => ["auth-links", language] as const;

/** 같은 소셜 버튼에서 로그인과 가입을 처리하고 현재 게스트 일정을 보관한다. */
export function SocialAccounts() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const providers = useAuthProviders();
  const profile = useProfile();
  const session = profile?.session ?? null;
  const hasSession = Boolean(session);
  const isGuest = session?.kind === "guest";
  const [unlinking, setUnlinking] = useState<SocialProvider | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  // A login with no session may need a human check (`human_check_required`): the provider and mode wait for the token.
  const [waiting, setWaiting] = useState<{ provider: SocialProvider; mode: SocialMode } | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [checkRound, setCheckRound] = useState(0);

  const links = useQuery({
    queryKey: linksKey(language), queryFn: () => getLinks(language), enabled: hasSession && (providers.data?.length ?? 0) > 0, retry: false,
  });
  const linked = new Set((links.data ?? []).map((entry) => entry.provider));

  const reason = (error: unknown) => error instanceof LiveError || error instanceof Error ? error.message : String(error);

  const go = useMutation({
    mutationFn: async ({ provider, mode, humanToken }: { provider: SocialProvider; mode: SocialMode; humanToken?: string | null }) => {
      const address = await startSocial(provider, mode, new URLSearchParams(window.location.search).get("returnTo") ?? `${window.location.pathname}#accounts`, language, humanToken);
      window.location.assign(address);
    },
    onError: (error, { provider, mode }) => {
      if (error instanceof LiveError && error.code === "human_check_required" && TURNSTILE_SITE_KEY) {
        setWaiting({ provider, mode });
        setCheckRound((count) => count + 1);
        setMessage({ ok: false, text: t("사람인지 확인한 뒤 계속해요. 잠시만 기다려 주세요.", "Checking that you are a person first. One moment.") });
        return;
      }
      setWaiting(null);
      setMessage({ ok: false, text: reason(error) });
    },
  });
  // The check came back: send the sign-in again with it.
  useEffect(() => {
    if (waiting && token && !go.isPending) go.mutate({ ...waiting, humanToken: token });
  }, [waiting, token, go]);

  const unlink = useMutation({
    mutationFn: (provider: SocialProvider) => unlinkSocial(provider, language),
    onSuccess: (remaining, provider) => {
      queryClient.setQueryData(linksKey(language), remaining);
      setUnlinking(null);
      setMessage({ ok: true, text: t(`${providerName(provider)[0]} 계정 연결을 풀었어요. 여행은 그대로예요.`, `Unlinked ${providerName(provider)[1]}. Your trips are unchanged.`) });
    },
    onError: (error) => { setUnlinking(null); setMessage({ ok: false, text: reason(error) }); },
  });

  const busy = go.isPending || unlink.isPending || Boolean(waiting);
  const start = (provider: SocialProvider, mode: SocialMode) => { setMessage(null); setWaiting(null); setToken(null); go.mutate({ provider, mode }); };

  const body = () => {
    if (providers.isPending) return <p className={styles.mutedNote} role="status">{t("로그인 방법을 불러오고 있어요.", "Loading the sign-in methods.")}</p>;
    if (providers.isError) {
      return isSocialUnsupported(providers.error)
        ? <p className={styles.mutedNote}>{t("소셜 로그인(구글·카카오·네이버·디스코드)은 서버가 준비 중이에요.", "Social sign-in (Google, Kakao, Naver, Discord) is being prepared on the server.")}</p>
        : <p className={styles.error} role="alert">{reason(providers.error)} <Button variant="quiet" onClick={() => void providers.refetch()}>{t("다시 불러오기", "Try again")}</Button></p>;
    }
    if (!providers.data.length) return <p className={styles.mutedNote}>{t("서버에 설정된 로그인 방법이 아직 없어요.", "The server has no sign-in method set up yet.")}</p>;
    return <>
      {session?.kind === "member" && <div className={styles.row}>
        <p className={styles.explain}>{isGuest
          ? t("계정을 연결해 두면 창을 닫아도 여행이 보관되고, 게스트 제한도 없어져요. 다른 기기에서도 그 계정으로 로그인해 여행을 열 수 있어요. 이메일은 받지 않아요.", "Link an account and your trips are kept even after you close the window, the guest limits end, and you can sign in with it on another device. We do not take your email.")
          : t("연결된 계정으로 어느 기기에서든 로그인해 여행을 열 수 있어요. 이메일은 받지 않아요.", "Sign in with a linked account on any device to open your trips. We do not take your email.")}</p>
        <ul className={styles.providers} aria-label={t("연결할 계정", "Accounts to link")}>{providers.data.map((provider) => !linked.has(provider)
          ? <li key={provider} data-provider={provider} className={styles.brandRow}><ProviderButton provider={provider} disabled={busy || links.isPending} onClick={() => start(provider, "link")} /></li>
          : <li key={provider} data-provider={provider}>
          <ProviderIdentity provider={provider} />
          {linked.has(provider)
            ? (unlinking === provider
              ? <span className={styles.actions}>
                <Button variant="primary" disabled={busy} onClick={() => unlink.mutate(provider)}>{t("연결 풀기", "Unlink")}</Button>
                <Button disabled={busy} onClick={() => setUnlinking(null)}>{t("취소", "Cancel")}</Button>
              </span>
              : <span className={styles.actions}><span className={styles.linkedTag}>{t("연결됨", "Linked")}</span><Button variant="quiet" disabled={busy} onClick={() => setUnlinking(provider)}>{t("풀기", "Unlink")}</Button></span>)
            : <Button disabled={busy || links.isPending} onClick={() => start(provider, "link")}>{t("연결하기", "Link")}</Button>}
        </li>)}</ul>
        {links.isError && !isSocialUnsupported(links.error) && <p className={styles.error} role="alert">{reason(links.error)}</p>}
      </div>}

      {session?.kind !== "member" && <div className={styles.row}>
        <p className={styles.explain}>{t("계정으로 계속하면 기존 계정은 로그인되고, 처음이면 가입돼요. 지금 작성한 일정과 이 기기의 게스트 여행도 함께 보관돼요.", "Continue with an account to sign in or create one automatically. Your current plan and this device's guest trips will be kept together.")}</p>
        <ul className={styles.providers} aria-label={t("계정으로 계속하기", "Continue with an account")}>{providers.data.map((provider) =>
          <li key={provider} data-provider={provider} className={styles.brandRow}><ProviderButton provider={provider} disabled={busy} onClick={() => start(provider, "login")} /></li>)}</ul>
      </div>}
      {waiting && TURNSTILE_SITE_KEY && <HumanCheck onToken={setToken} resetKey={checkRound} />}
    </>;
  };

  return <fieldset className={styles.group} id="accounts">
    <legend>{t("소셜 계정", "Social accounts")}</legend>
    {body()}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </fieldset>;
}
