import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { InquiryPage, SupportForm, SupportPage } from "./support";
import { ServiceNotices } from "./service-notices";

// `[2026-10-12]` The support screens move between pages (list → an inquiry, the form → the list): the router is not under test here.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const answeredInquiry = { inquiries: [{ id: "one", title: "여행 문의", body: "<script>unsafe()</script>", receivedAt: "2026-10-08T01:00:00Z", status: "답변 완료", replies: [{ body: "여행 화면을 열어 주세요.", operator: "support", at: "2026-10-08T02:00:00Z" }] }] };

describe("customer support screen", () => {
  it("labels the form's required fields", () => {
    const html = renderToStaticMarkup(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(SupportForm)));
    expect(html).toContain('for="support-title"');
    expect(html).toContain('for="support-body"');
  });
  it("lists an inquiry by its title and status, linking to its own page", () => {
    const client = new QueryClient();
    client.setQueryData(["support-inquiries", "ko"], answeredInquiry);
    const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(SupportPage)));
    expect(html).toContain("여행 문의");
    expect(html).toContain("답변 완료");
    expect(html).toContain('href="/support/one"');
  });
  it("renders the inquiry and its answer as text", () => {
    const client = new QueryClient();
    client.setQueryData(["support-inquiries", "ko"], answeredInquiry);
    const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(InquiryPage, { id: "one" })));
    expect(html).toContain("여행 화면을 열어 주세요.");
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
