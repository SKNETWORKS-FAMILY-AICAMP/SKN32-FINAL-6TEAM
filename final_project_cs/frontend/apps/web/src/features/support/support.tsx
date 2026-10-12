"use client";

import { useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, ButtonLink } from "@/components/ui";
import { useSettings, useT } from "@/lib/settings";
import { createInquiry, inquiries, requestIdentity } from "./client";
import styles from "./support.module.css";

export function SupportPage() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["support-inquiries", language], queryFn: () => inquiries(language) });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const identity = useRef<ReturnType<typeof requestIdentity> | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current || !title.trim() || !body.trim()) return;
    sending.current = true;
    setBusy(true);
    setMessage(null);
    identity.current = requestIdentity(identity.current, title, body, language);
    try {
      const { inquiry } = await createInquiry(language, { title: title.trim(), body: body.trim(), requestId: identity.current.requestId });
      queryClient.setQueryData<{ inquiries: typeof inquiry[] }>(["support-inquiries", language], (old) => ({ inquiries: [inquiry, ...(old?.inquiries ?? []).filter((item) => item.id !== inquiry.id)] }));
      setTitle(""); setBody(""); identity.current = null;
      setMessage({ ok: true, text: t("문의를 접수했어요. 아래 목록에서 답변을 확인할 수 있어요.", "Your inquiry was received. Check the list below for a reply.") });
    } catch (error) {
      setMessage({ ok: false, text: t("접수 여부를 확인하지 못했어요. 입력한 내용은 그대로예요. 같은 내용으로 다시 보내면 중복 접수되지 않아요.", "We could not confirm receipt. Your draft is kept. Sending the same draft again will not create a duplicate.") + (error instanceof Error ? ` ${error.message}` : "") });
    } finally { sending.current = false; setBusy(false); }
  }
  const status = (value: string) => value === "답변 완료" ? t("답변 완료", "Answered") : value === "처리 중" ? t("처리 중", "In progress") : t("접수", "Received");
  return <div className={styles.page}>
    <div className={styles.row}><h1>{t("문의하기", "Contact support")}</h1><ButtonLink href="/mypage" variant="quiet">{t("마이페이지", "My page")}</ButtonLink></div>
    <p className={styles.muted}>{t("triPilot 이용 중 불편한 점을 알려 주세요. 이 계정의 문의와 운영팀 답변만 보여요.", "Tell us about a problem using triPilot. Only your account’s inquiries and the support team’s replies are shown.")}</p>
    <form className={styles.section} onSubmit={(event) => void submit(event)} aria-busy={busy}>
      <div className={styles.field}><label htmlFor="support-title">{t("제목", "Subject")}</label><input id="support-title" value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} disabled={busy} /></div>
      <div className={styles.field}><label htmlFor="support-body">{t("문의 내용", "Message")}</label><textarea id="support-body" value={body} onChange={(event) => setBody(event.target.value)} required maxLength={5000} disabled={busy} aria-describedby="support-privacy" /></div>
      <p id="support-privacy" className={styles.muted}>{t("비밀번호·결제 정보 등 민감한 정보는 적지 마세요.", "Do not include passwords or payment details.")}</p>
      <Button type="submit" variant="primary" disabled={busy || !title.trim() || !body.trim()}>{busy ? t("접수 중…", "Sending…") : t("문의 보내기", "Send inquiry")}</Button>
      {message && <p className={message.ok ? styles.success : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
    </form>
    <section className={styles.section} aria-labelledby="support-list-title">
      <div className={styles.row}><h2 id="support-list-title">{t("내 문의와 답변", "My inquiries and replies")}</h2><Button disabled={list.isFetching} onClick={() => void list.refetch()}>{t("답변 새로고침", "Refresh replies")}</Button></div>
      {list.isPending && <p role="status">{t("문의를 불러오고 있어요.", "Loading your inquiries.")}</p>}
      {list.error && <p role="alert" className={styles.error}>{t("목록을 불러오지 못했어요. 답변 새로고침으로 다시 확인해 주세요.", "Could not load the list. Use Refresh replies to try again.")} {list.error.message}</p>}
      {list.data?.inquiries.length === 0 && <p className={styles.muted}>{t("아직 접수한 문의가 없어요. 위에서 첫 문의를 보내 주세요.", "No inquiries yet. Send your first inquiry above.")}</p>}
      <ul className={styles.list}>{list.data?.inquiries.map((item) => <li key={item.id} className={styles.inquiry}><details>
        <summary>{item.title} · {status(item.status)}</summary>
        <time dateTime={item.receivedAt}>{new Date(item.receivedAt).toLocaleString(language)}</time>
        <p className={styles.body}>{item.body}</p>
        {item.replies.length === 0 ? <p className={styles.muted}>{t("운영팀 답변을 기다리고 있어요.", "Waiting for a reply from the support team.")}</p> : item.replies.map((reply, index) => <div className={styles.reply} key={`${reply.at}-${index}`}><strong>{t("운영팀 답변", "Support team reply")}</strong><p className={styles.body}>{reply.body}</p><time dateTime={reply.at}>{new Date(reply.at).toLocaleString(language)}</time></div>)}
      </details></li>)}</ul>
    </section>
  </div>;
}
