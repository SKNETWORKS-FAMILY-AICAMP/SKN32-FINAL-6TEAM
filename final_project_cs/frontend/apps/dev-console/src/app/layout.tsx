import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import { ConsoleShell } from "@/components/layout/console-shell";
import "./globals.css";

export const metadata: Metadata = { title: "triPilot 관리 앱", description: "가상 오류 기록 조회와 에이전트팀 검증을 위한 개발 작업공간", robots: { index: false, follow: false }, icons: { icon: "/favicon.svg" } };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ko"><body><Providers><ConsoleShell>{children}</ConsoleShell></Providers></body></html>;
}
