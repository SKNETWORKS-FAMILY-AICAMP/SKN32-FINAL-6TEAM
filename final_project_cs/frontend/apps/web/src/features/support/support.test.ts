import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { SupportPage } from "./support";
import { ServiceNotices } from "./service-notices";

describe("customer support screen", () => {
  it("renders existing replies as text and labels all required fields", () => {
    const client = new QueryClient();
    client.setQueryData(["support-inquiries", "ko"], { inquiries: [{ id: "one", title: "여행 문의", body: "<script>unsafe()</script>", receivedAt: "2026-10-08T01:00:00Z", status: "답변 완료", replies: [{ body: "여행 화면을 열어 주세요.", operator: "support", at: "2026-10-08T02:00:00Z" }] }] });
    const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(SupportPage)));
    expect(html).toContain('for="support-title"');
    expect(html).toContain('for="support-body"');
    expect(html).toContain("여행 화면을 열어 주세요.");
    expect(html).toContain("답변 완료");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>unsafe()");
  });
  it("renders enabled maintenance and gives a customer support path", () => {
    const client = new QueryClient();
    client.setQueryData(["service-notices", "ko"], { notices: [], maintenance: { enabled: true, message: "일정 확인 점검 중" } });
    const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(ServiceNotices)));
    expect(html).toContain('aria-label="서비스 공지"');
    expect(html).toContain("일정 확인 점검 중");
    expect(html).toContain('href="/support"');
  });
});
