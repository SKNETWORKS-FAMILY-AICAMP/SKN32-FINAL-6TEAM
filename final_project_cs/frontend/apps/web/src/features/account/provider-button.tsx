"use client";

import Image from "next/image";
import { providerName, type SocialProvider } from "@/lib/live/auth";
import { useT } from "@/lib/settings";
import { GoogleButton, GoogleIcon } from "./google-button";
import kakao from "./brand-assets/kakao.svg";
import naver from "./brand-assets/naver.png";
import discord from "./brand-assets/discord.svg";
import styles from "./account.module.css";

/** Official artwork only. See official source URLs in brand-assets/sources.ts. */
function ProviderIcon({ provider }: { provider: SocialProvider }) {
  return <span className={styles.providerIcon} data-provider-icon={provider} aria-hidden="true">
    {provider === "google" ? <GoogleIcon /> : <Image src={{ kakao, naver, discord }[provider]} alt="" width={provider === "naver" ? 48 : 20} height={provider === "naver" ? 48 : 20} unoptimized />}
  </span>;
}

/** The same brand identity remains visible after linking; unlink controls stay outside this label. */
export function ProviderIdentity({ provider }: { provider: SocialProvider }) {
  return <span className={styles.providerIdentity}><span className={styles.providerMark} data-brand={provider}><ProviderIcon provider={provider} /></span>{providerName(provider)[1]}</span>;
}

export function ProviderButton({ provider, disabled, onClick }: { provider: SocialProvider; disabled?: boolean; onClick: () => void }) {
  const t = useT();
  if (provider === "google") return <GoogleButton mode="link" disabled={disabled} onClick={onClick} />;
  const name = providerName(provider)[1];
  return <button type="button" className={styles.socialButton} data-brand={provider} data-provider-button={provider} disabled={disabled} onClick={onClick}>
    <ProviderIcon provider={provider} /><span>{t(`${name} 계정으로 계속`, `Continue with ${name}`)}</span>
  </button>;
}
