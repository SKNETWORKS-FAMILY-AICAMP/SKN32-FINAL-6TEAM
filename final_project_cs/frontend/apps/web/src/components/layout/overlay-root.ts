"use client";

import { createContext } from "react";

/** Where the drawer, the cards and the notices render: the phone frame (`DeviceFrame`) when the screen is inside one, the page otherwise (`null`). */
export const OverlayRoot = createContext<HTMLElement | null>(null);
