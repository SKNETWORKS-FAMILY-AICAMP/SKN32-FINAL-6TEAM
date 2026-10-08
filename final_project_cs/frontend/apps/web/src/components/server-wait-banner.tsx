"use client";

import { useState } from "react";
import { useServerWait } from "@/lib/live/waiting";
import { useT } from "@/lib/settings";
import { WaitNotice } from "./wait-notice";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` Floats at the top of every screen while a call to the server has not answered for long (`lib/live/waiting.ts`: 8 s for a plain call,
 * 30 s without a new stage for a task). It says how long it has been and what the customer can do, gets stronger at 30 s and 1 minute, goes away by itself when the server answers, and can be closed
 * (it comes back for the next call that is slow). Nothing here guesses a cause: 「바쁘거나 느릴 수 있어요」 is a possibility, not a diagnosis.
 */
export function ServerWaitBanner() {
  const t = useT();
  const wait = useServerWait();
  const [closed, setClosed] = useState<number | null>(null);
  if (!wait || wait.id === closed) return null;
  const minutes = Math.floor(wait.seconds / 60);
  const [title, body] = wait.level === 1
    ? [t("서버 응답이 늦어지고 있어요", "The server is slow to answer"), t("잠시만 더 기다려 주세요.", "Please wait a little longer.")]
    : wait.level === 2
      ? [t("서버가 아직 답하지 않았어요", "The server has not answered yet"), t("서버가 바쁘거나 연결이 느릴 수 있어요. 조금 더 기다려도 되고, 계속 안 되면 잠시 뒤에 다시 시도해 주세요.", "It may be busy or the connection may be slow. You can wait a little longer, or try again shortly if it stays like this.")]
      : [t(`${Math.max(1, minutes)}분이 넘게 서버 답이 없어요`, `No answer from the server for over ${Math.max(1, minutes)} min`), t("서버나 연결에 문제가 있을 수 있어요. 이 화면을 둔 채 더 기다리거나, 뒤로 가서 잠시 뒤에 다시 시도해 주세요.", "There may be a problem with the server or the connection. Keep waiting on this screen, or go back and try again shortly.")];
  return <WaitNotice floating title={title} body={body} seconds={wait.seconds} onClose={() => setClosed(wait.id)} />;
}
