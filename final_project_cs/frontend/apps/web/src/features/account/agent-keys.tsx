"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { API_BASE, LiveError } from "@/lib/live/client";
import { connectCommand, createAgentKey, isAgentKeysUnsupported, isMemberOnly, listAgentKeys, revokeAgentKey, type AgentKey, type AgentScope, type CreatedAgentKey } from "@/lib/live/agent-keys";
import { useProfile } from "@/lib/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./account.module.css";

const NAME_MAX = 60;
const DAYS = [7, 30, 90] as const;
const keysKey = (language: string) => ["agent-keys", language] as const;

/**
 * `[2026-10-04 사용자 지시 · 서버 D-CS-012]` My page 「에이전트 연결」: a signed-in member makes a key a personal AI (Claude Code, an MCP client) uses to read — or also change —
 * THEIR trips only. A guest is told logging in opens it. ★The key is shown ONCE, right after it is made (the server keeps only a hash): it lives in this component state
 * only — never in storage or the query cache — and is gone when the card is closed or the page is left. The line that connects Claude Code carries the key in a header,
 * never in the address.
 */
export function AgentKeys() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const profile = useProfile();
  const member = profile?.session?.kind === "member";
  const keys = useQuery({ queryKey: keysKey(language), queryFn: () => listAgentKeys(language), enabled: member, retry: false });
  const [name, setName] = useState("");
  const [scope, setScope] = useState<AgentScope>("read");
  const [days, setDays] = useState<number>(90);
  const [created, setCreated] = useState<CreatedAgentKey | null>(null);
  const [copied, setCopied] = useState<"key" | "command" | "failed" | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const reason = (error: unknown) => error instanceof LiveError || error instanceof Error ? error.message : String(error);

  const make = useMutation({
    mutationFn: () => createAgentKey({ name, scope, expiresDays: days }, language),
    onSuccess: (key) => { setCreated(key); setCopied(null); setName(""); setMessage(null); void queryClient.invalidateQueries({ queryKey: keysKey(language) }); },
    onError: (error) => setMessage({ ok: false, text: isMemberOnly(error) ? t("로그인하면 에이전트를 연결할 수 있어요.", "Sign in to connect an agent.") : reason(error) }),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => revokeAgentKey(id, language),
    onSuccess: (_result, id) => {
      setRevoking(null);
      if (created?.id === id) setCreated(null);
      setMessage({ ok: true, text: t("키를 폐기했어요. 이 키를 쓰던 에이전트는 더 이상 열리지 않아요.", "The key is revoked. An agent that used it can no longer get in.") });
      void queryClient.invalidateQueries({ queryKey: keysKey(language) });
    },
    onError: (error) => { setRevoking(null); setMessage({ ok: false, text: reason(error) }); },
  });

  async function copy(what: "key" | "command", value: string) {
    try { await navigator.clipboard.writeText(value); setCopied(what); }
    catch { setCopied("failed"); }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || name.trim().length > NAME_MAX || make.isPending) return;
    make.mutate();
  }
  const date = (iso: string | null) => {
    const value = iso ? new Date(iso) : null;
    return value && !Number.isNaN(value.getTime()) ? value.toLocaleDateString(language === "ko" ? "ko-KR" : "en-US") : "–";
  };
  const statusText = (key: AgentKey) => key.status === "active" ? t("사용 중", "Active") : key.status === "expired" ? t("만료", "Expired") : t("폐기됨", "Revoked");

  const body = () => {
    if (profile === undefined) return <p className={styles.mutedNote} role="status">{t("불러오고 있어요.", "Loading.")}</p>;
    if (!member) return <p className={styles.explain}>{t("로그인한 사용자만 에이전트를 연결할 수 있어요. ", "Only signed-in users can connect an agent. ")}
      <Link href={`${routes.myPage}#accounts`}>{t("위의 소셜 계정을 연결하면", "Link a social account above and")}</Link>{t(" 쓸 수 있어요.", " it opens.")}</p>;
    if (keys.isError && isAgentKeysUnsupported(keys.error)) return <p className={styles.mutedNote}>{t("에이전트 연결은 서버가 준비 중이에요.", "Connecting an agent is being prepared on the server.")}</p>;
    const list = keys.data ?? [];
    const activeCount = list.filter((key) => key.status === "active").length;
    return <>
      <p className={styles.explain}>{t("클로드 코드 같은 개인 AI가 내 여행만 읽거나 다루게 하는 키예요. 키는 만들 때 한 번만 보여요. 쓰기 키라도 서버의 쓰기 스위치가 꺼져 있으면 읽기만 돼요.", "A key lets a personal AI such as Claude Code read — or change — your trips only. The key is shown once, when you make it. Even a write key reads only while the server's write switch is off.")}</p>

      {created && <div className={styles.row} role="status" aria-label={t("새 키", "New key")}>
        <p className={styles.warn}>{created.notice ?? t("이 키는 지금 한 번만 보여요. 이 화면을 닫으면 다시 볼 수 없어요 — 안전한 곳에 따로 보관해 주세요.", "This key is shown only now. Once you leave this screen you cannot see it again — keep it somewhere safe.")}</p>
        <input className={styles.keybox} readOnly value={created.key} aria-label={t("새 에이전트 키", "New agent key")} onFocus={(event) => event.currentTarget.select()} />
        <p className={styles.explain}>{t("클로드 코드에 연결하려면 터미널에서 아래 줄을 실행하세요. 키는 주소가 아니라 머리말에 실려 가요.", "To connect Claude Code, run this line in a terminal. The key travels in a header, never in the address.")}</p>
        <code className={styles.command}>{connectCommand(API_BASE, created.key)}</code>
        <div className={styles.actions}>
          <Button onClick={() => void copy("key", created.key)}>{copied === "key" ? t("복사했어요", "Copied") : t("키 복사", "Copy key")}</Button>
          <Button onClick={() => void copy("command", connectCommand(API_BASE, created.key))}>{copied === "command" ? t("복사했어요", "Copied") : t("연결 명령 복사", "Copy the command")}</Button>
          <Button variant="primary" onClick={() => { setCreated(null); setCopied(null); }}>{t("따로 보관했어요", "I saved it")}</Button>
        </div>
        {copied === "failed" && <p className={styles.error} role="alert">{t("복사하지 못했어요. 위 키를 눌러 선택한 뒤 직접 복사해 주세요.", "Could not copy. Select the key above and copy it yourself.")}</p>}
      </div>}

      <ul className={styles.providers} aria-label={t("만든 에이전트 키", "Agent keys")}>
        {keys.isPending && <li><span className={styles.mutedNote} role="status">{t("키를 불러오고 있어요.", "Loading the keys.")}</span></li>}
        {!keys.isPending && !keys.isError && list.length === 0 && <li><span className={styles.mutedNote}>{t("아직 만든 키가 없어요.", "No keys yet.")}</span></li>}
        {list.map((key) => <li key={key.id}>
          <span className={styles.keyInfo}>
            <span className={styles.providerName}>{key.name}</span>
            <small className={styles.keyMeta}>{key.scope === "write" ? t("읽기·쓰기", "Read & write") : t("읽기만", "Read only")} · {statusText(key)} · {t("만든 날", "Made")} {date(key.createdAt)} · {t("만료", "Expires")} {date(key.expiresAt)} · {key.lastUsedAt ? `${t("마지막 사용", "Last used")} ${date(key.lastUsedAt)}` : t("아직 안 썼어요", "Not used yet")}</small>
          </span>
          {key.status === "active" && (revoking === key.id
            ? <span className={styles.actions}>
              <Button variant="primary" disabled={revoke.isPending} onClick={() => revoke.mutate(key.id)}>{t("폐기하기", "Revoke")}</Button>
              <Button disabled={revoke.isPending} onClick={() => setRevoking(null)}>{t("취소", "Cancel")}</Button>
            </span>
            : <Button variant="quiet" disabled={revoke.isPending} onClick={() => setRevoking(key.id)} aria-label={t(`${key.name} 폐기`, `Revoke ${key.name}`)}>{t("폐기", "Revoke")}</Button>)}
        </li>)}
      </ul>
      {keys.isError && !isAgentKeysUnsupported(keys.error) && <p className={styles.error} role="alert">{reason(keys.error)} <Button variant="quiet" onClick={() => void keys.refetch()}>{t("다시 불러오기", "Try again")}</Button></p>}

      <form className={styles.row} onSubmit={submit}>
        <label htmlFor="agent-key-name">{t(`이름 (1~${NAME_MAX}자)`, `Name (1–${NAME_MAX} characters)`)}</label>
        <input id="agent-key-name" className={styles.keybox} value={name} maxLength={NAME_MAX} autoComplete="off" placeholder={t("예: 내 노트북의 클로드 코드", "e.g. Claude Code on my laptop")} onChange={(event) => setName(event.target.value)} />
        <fieldset className={styles.choices}>
          <legend>{t("권한", "Access")}</legend>
          <label><input type="radio" name="agent-scope" checked={scope === "read"} onChange={() => setScope("read")} />{t("읽기만 (추천)", "Read only (recommended)")}</label>
          <label><input type="radio" name="agent-scope" checked={scope === "write"} onChange={() => setScope("write")} />{t("읽기·쓰기", "Read & write")}</label>
        </fieldset>
        <label htmlFor="agent-key-days">{t("유효 기간", "Valid for")}</label>
        <select id="agent-key-days" className={styles.keybox} value={days} onChange={(event) => setDays(Number(event.target.value))}>
          {DAYS.map((count) => <option key={count} value={count}>{t(`${count}일`, `${count} days`)}</option>)}
        </select>
        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={make.isPending || !name.trim() || activeCount >= 10}>{make.isPending ? t("만드는 중…", "Making…") : t("키 만들기", "Make a key")}</Button>
        </div>
        {activeCount >= 10 && <p className={styles.warn}>{t("사용 중인 키가 10개예요. 쓰지 않는 키를 폐기한 뒤 만들 수 있어요.", "Ten keys are active. Revoke one you no longer use to make another.")}</p>}
      </form>
    </>;
  };

  return <fieldset className={styles.group} id="agents">
    <legend>{t("에이전트 연결", "Connect an agent")}</legend>
    {body()}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </fieldset>;
}
