import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import { ConsoleShell } from "@/components/layout/console-shell";
import "./globals.css";

export const metadata: Metadata = { title: "triPilot 개발팀 콘솔", description: "에이전트팀 테스트와 코어 실행 기록을 확인하는 개발 작업공간", robots: { index: false, follow: false }, icons: { icon: "/favicon.svg" } };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ko"><body><Providers><ConsoleShell>{children}</ConsoleShell></Providers></body></html>;
}
