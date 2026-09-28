"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical, Workflow, GitCompareArrows, Plug, ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";
import { dataMode } from "@/lib/gateway";
import styles from "./console-shell.module.css";

const pages = [
  { href: "/teams", label: "팀별 테스트", icon: FlaskConical },
  { href: "/integration", label: "코어 통합 테스트", icon: Workflow },
  { href: "/cases", label: "사례·버전 비교", icon: GitCompareArrows },
];

export function ConsoleShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  return <>
    <a className={styles.skip} href="#main-content">본문으로 건너뛰기</a>
    <header className={styles.header}><Link href="/teams" className={styles.brand}><span className={styles.mark} aria-hidden="true">t.</span>triPilot <span className={styles.brandSub}>DEVELOPER CONSOLE</span></Link><span className={styles.mode}>{dataMode === "demo" ? "샘플 모드 · 실제 API 호출 없음" : "데이터 연결 미설정"}</span></header>
    <div className={styles.shell}><nav className={styles.nav} aria-label="개발팀 메뉴"><p className={styles.navLabel}>WORKSPACE</p>{pages.map(({ href, label, icon: Icon }) => <Link href={href} key={href} aria-current={path === href ? "page" : undefined}><Icon size={17} aria-hidden="true" />{label}</Link>)}<div className={styles.bottom}><Link href="/connections" aria-current={path === "/connections" ? "page" : undefined}><Plug size={17} aria-hidden="true" />연결 안내<ArrowUpRight size={13} aria-hidden="true" /></Link><p>Core API 미연결<br />개발·실험용 작업공간</p></div></nav><main id="main-content" className={styles.main}>{children}</main></div>
    <footer className={styles.footer}>가상 장소·고정 샘플 응답 · 기록은 현재 브라우저 탭에 보관됩니다.</footer>
  </>;
}
