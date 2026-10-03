"use client";

import { useT } from "@/lib/settings";
import styles from "./server-not-connected.module.css";

/**
 * ★`[2026-10-03 사용자 지시]` 모방 데이터는 없다 — 서버 연결(`NEXT_PUBLIC_DATA_MODE=live`)이 설정되지 않은 빌드는 다른 화면을
 * 열지 않고 이 한 화면만 보인다. 연결이 없는데 일정이나 답이 있는 것처럼 보이는 일이 없게 한다.
 */
export function ServerNotConnected() {
  const t = useT();
  return <main className={styles.page}>
    <h1>{t("서버 연결이 설정되지 않았어요", "The server connection is not set up")}</h1>
    <p>{t("이 화면은 triPilot 서버에서 받은 일정과 답만 보여 드려요. 서버 연결이 없으면 보여 드릴 것이 없어요.", "This app shows only itineraries and answers that come from the triPilot server. Without a connection there is nothing to show.")}</p>
    <p className={styles.hint}>{t("운영자는 .env.local 에 NEXT_PUBLIC_DATA_MODE=live 와 NEXT_PUBLIC_API_BASE 를 적고 다시 실행해 주세요.", "Operators: set NEXT_PUBLIC_DATA_MODE=live and NEXT_PUBLIC_API_BASE in .env.local and restart.")}</p>
  </main>;
}
