import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'triPilot · 운영자 콘솔', description: '운영 화면과 시나리오를 체험하는 명시적 데모' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="ko"><body>{children}</body></html>; }
