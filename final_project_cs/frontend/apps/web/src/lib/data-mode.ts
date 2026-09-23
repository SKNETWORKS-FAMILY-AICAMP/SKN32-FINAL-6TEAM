// A production build must explicitly opt into the browser-local demo.
export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE ?? (process.env.NODE_ENV === "development" || process.env.NODE_ENV === "test" ? "demo" : "unconfigured");
