import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppHeader, DataModeNotice } from "@/components/layout/app-header";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "triPilot · 당신의 계획에 여행의 여유를", template: "%s · triPilot" },
  description: "여행 계획을 등록하고 검증 흐름과 결과, 여행 일정을 확인하세요.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ko"><body><Providers><AppHeader /><DataModeNotice /><main id="main-content">{children}</main></Providers></body></html>;
}
