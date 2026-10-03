"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { HumanCheck, TURNSTILE_SITE_KEY } from "@/features/human-check/human-check";
import { getLinks, isSocialUnsupported, providerName, startSocial, unlinkSocial, type SocialMode, type SocialProvider } from "@/lib/live/auth";
import { currentKey, KEY_CHANGED_EVENT, LiveError } from "@/lib/live/client";
import { useSettings, useT } from "@/lib/settings";
import { useAuthProviders } from "./use-auth-providers";
import styles from "./account.module.css";

const linksKey = (language: string) => ["auth-links", language] as const;

/**
 * `[2026-10-03 사용자 지시]` Social sign-in on My page (`#accounts`): link a Google / Kakao / Naver / Discord account to the key this browser
 * holds, or — with no key here — sign in with one that is already linked to bring its key. The server does the sign-in itself
 * (`lib/live/auth.ts`); this card only starts it and sends the browser to the provider.
 *
 * ★Nothing is faked: the buttons exist only for providers the server says it has set up. Without them (an older server, or none set
 *   up) the card says the server is not ready and offers nothing to press.
 * ★Signing in with a key already in this browser REPLACES that key, so it is asked first and the choice of 「연결」 is put before it
 *   (`client.ts`: a key swapped without a word makes the old trips vanish).
 */
export function SocialAccounts() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const providers = useAuthProviders();
  const [hasKey, setHasKey] = useState(false);
  const [replacing, setReplacing] = useState(false);          // the 「로그인」 warning is open (a key is already here)
  const [unlinking, setUnlinking] = useState<SocialProvider | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  // A login with no key may need a human check (`human_check_required`): the provider and mode wait for the token.
  const [waiting, setWaiting] = useState<{ provider: SocialProvider; mode: SocialMode } | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [checkRound, setCheckRound] = useState(0);

  useEffect(() => {
    const read = () => setHasKey(Boolean(currentKey()));
    read();
    window.addEventListener(KEY_CHANGED_EVENT, read);
    return () => window.removeEventListener(KEY_CHANGED_EVENT, read);
  }, []);

  const links = useQuery({
    queryKey: linksKey(language), queryFn: () => getLinks(language), enabled: hasKey && (providers.data?.length ?? 0) > 0, retry: false,
  });
  const linked = new Set((links.data ?? []).map((entry) => entry.provider));

  const reason = (error: unknown) => error instanceof LiveError || error instanceof Error ? error.message : String(error);

  const go = useMutation({
    mutationFn: async ({ provider, mode, humanToken }: { provider: SocialProvider; mode: SocialMode; humanToken?: string | null }) => {
      const address = await startSocial(provider, mode, `${window.location.pathname}#accounts`, language, humanToken);
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
      setMessage({ ok: true, text: t(`${providerName(provider)[0]} 계정 연결을 풀었어요. 토큰과 여행은 그대로예요.`, `Unlinked ${providerName(provider)[1]}. Your token and trips are unchanged.`) });
    },
    onError: (error) => { setUnlinking(null); setMessage({ ok: false, text: reason(error) }); },
  });

  const busy = go.isPending || unlink.isPending || Boolean(waiting);
  const start = (provider: SocialProvider, mode: SocialMode) => { setMessage(null); setWaiting(null); setToken(null); go.mutate({ provider, mode }); };

  const body = () => {
    if (providers.isPending) return <p className={styles.mutedNote} role="status">{t("로그인 방법을 불러오고 있어요.", "Loading the sign-in methods.")}</p>;
    if (providers.isError) {
      return isSocialUnsupported(providers.error)
        ? <p className={styles.mutedNote}>{t("소셜 로그인(구글·카카오·네이버·디스코드)은 서버가 준비 중이에요. 그동안은 위의 토큰을 따로 보관해 주세요.", "Social sign-in (Google, Kakao, Naver, Discord) is being prepared on the server. Until then, keep your token somewhere safe.")}</p>
        : <p className={styles.error} role="alert">{reason(providers.error)} <Button variant="quiet" onClick={() => void providers.refetch()}>{t("다시 불러오기", "Try again")}</Button></p>;
    }
    if (!providers.data.length) return <p className={styles.mutedNote}>{t("서버에 설정된 로그인 방법이 아직 없어요.", "The server has no sign-in method set up yet.")}</p>;
    return <>
      {hasKey && <div className={styles.row}>
        <p className={styles.explain}>{t("계정을 이 토큰에 연결해 두면, 토큰을 잃어도 그 계정으로 여행을 다시 열 수 있어요. 이메일은 받지 않아요.", "Link an account to this token and you can open your trips with it even if you lose the token. We do not take your email.")}</p>
        <ul className={styles.providers} aria-label={t("연결할 계정", "Accounts to link")}>{providers.data.map((provider) => <li key={provider}>
          <span className={styles.providerName}>{t(...providerName(provider))}</span>
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

      <div className={styles.row}>
        <p className={styles.explain}>{hasKey
          ? t("이미 계정을 연결해 둔 다른 토큰이 있나요?", "Do you have another token with an account linked?")
          : t("이미 계정을 연결해 두었다면 그 계정으로 로그인해서 여행을 열 수 있어요.", "If you already linked an account, sign in with it to open your trips.")}</p>
        {hasKey && !replacing
          ? <Button disabled={busy} onClick={() => setReplacing(true)}>{t("계정으로 로그인하기", "Sign in with an account")}</Button>
          : <>
            {hasKey && <p className={styles.warn} role="alert">{t("로그인하면 이 브라우저의 토큰이 계정의 토큰으로 바뀌어요. 지금 토큰의 여행은 그 토큰을 따로 보관해 두었을 때만 다시 열 수 있어요. 지금 토큰의 여행을 계속 쓰려면 위의 「연결하기」를 쓰세요.", "Signing in replaces this browser's token with the account's token. The trips of the current token can be opened again only if you kept that token. To keep using them, use “Link” above.")}</p>}
            <ul className={styles.providers} aria-label={t("로그인할 계정", "Accounts to sign in with")}>{providers.data.map((provider) => <li key={provider}>
              <span className={styles.providerName}>{t(...providerName(provider))}</span>
              <Button variant={hasKey ? "secondary" : "primary"} disabled={busy} onClick={() => start(provider, "login")}>{t("로그인", "Sign in")}</Button>
            </li>)}</ul>
            {hasKey && <Button variant="quiet" disabled={busy} onClick={() => setReplacing(false)}>{t("닫기", "Close")}</Button>}
          </>}
      </div>
      {waiting && TURNSTILE_SITE_KEY && <HumanCheck onToken={setToken} resetKey={checkRound} />}
    </>;
  };

  return <fieldset className={styles.group} id="accounts">
    <legend>{t("소셜 계정", "Social accounts")}</legend>
    {body()}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </fieldset>;
}
