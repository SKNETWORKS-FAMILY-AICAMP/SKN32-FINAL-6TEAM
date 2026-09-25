import Link from "next/link";
import { DATA_MODE } from "@/lib/data-mode";
import styles from "./app-header.module.css";

export function AppHeader() {
  return <><a href="#main-content" className={styles.skip}>본문으로 이동</a><header className={styles.header}><Link className={styles.brand} href="/" aria-label="triPilot 메인 홈페이지"><span className={styles.mark} aria-hidden="true">t</span>triPilot</Link></header></>;
}

export function DataModeNotice() {
  const demo = DATA_MODE === "demo";
  return <div className={styles.notice} role="note">{demo ? "화면 개발용 데모 · 입력은 이 탭에만 저장되며, 실제 검증·예약 변경은 실행하지 않습니다." : "실제 여행 API 연결이 필요합니다. 현재 모드에서는 데모 데이터를 사용하지 않습니다."}</div>;
}
