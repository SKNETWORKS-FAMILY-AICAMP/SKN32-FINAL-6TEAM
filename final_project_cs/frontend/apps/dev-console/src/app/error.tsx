"use client";
import { Button, Notice, PageHeading } from "@/components/ui";
export default function ErrorPage({ reset }: { reset: () => void }) { return <><PageHeading title="화면을 불러오지 못했어요" /><Notice tone="error">다시 시도해 주세요. 샘플 기록은 현재 탭에 보관됩니다.<br /><Button onClick={reset}>다시 시도</Button></Notice></>; }
