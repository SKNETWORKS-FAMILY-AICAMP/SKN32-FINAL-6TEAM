"use client";

import { useEffect } from "react";

/** Page titles follow the chosen language, which is only known in the browser. */
export function useDocumentTitle(title: string) {
  useEffect(() => { document.title = title; }, [title]);
}
