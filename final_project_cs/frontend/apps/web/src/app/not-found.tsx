"use client";

import { JourneyShell } from "@/components/layout/journey-shell";
import { ButtonLink, PageHeading } from "@/components/ui";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";

export default function NotFound() {
  const t = useT();
  return <JourneyShell view="other" title={["페이지 없음", "Page not found"]}>
    <PageHeading title={t("페이지를 찾을 수 없어요", "This page could not be found")} description={t("여행 링크를 확인하거나 새로운 계획을 등록해 주세요.", "Check your trip link or add a new plan.")} />
    <ButtonLink href={routes.home} variant="primary">{t("처음 화면으로", "Back to start")}</ButtonLink>
  </JourneyShell>;
}
