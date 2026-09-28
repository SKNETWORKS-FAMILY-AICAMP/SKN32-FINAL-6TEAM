export type MapConfiguration =
  | { provider: "demo" }
  | { provider: "naver"; clientId: string }
  | { provider: "google"; apiKey: string; mapId: string }
  | { provider: "unavailable"; message: string };

interface MapEnvironment {
  provider?: string;
  naverClientId?: string;
  googleApiKey?: string;
  googleMapId?: string;
}

export function resolveMapConfiguration(environment: MapEnvironment): MapConfiguration {
  const provider = environment.provider?.trim() || "demo";
  if (provider === "demo") return { provider };
  if (provider === "naver") {
    const clientId = environment.naverClientId?.trim();
    return clientId ? { provider, clientId } : { provider: "unavailable", message: "네이버지도 연결 설정이 필요해요." };
  }
  if (provider === "google") {
    const apiKey = environment.googleApiKey?.trim();
    const mapId = environment.googleMapId?.trim();
    return apiKey && mapId ? { provider, apiKey, mapId } : { provider: "unavailable", message: "Google Maps 연결 설정이 필요해요." };
  }
  return { provider: "unavailable", message: "지도 제공자 설정이 올바르지 않아요." };
}

// Static references are required for Next.js to embed these browser settings.
export const mapConfiguration = resolveMapConfiguration({
  provider: process.env.NEXT_PUBLIC_MAP_PROVIDER,
  naverClientId: process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID,
  googleApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAP_API_KEY,
  googleMapId: process.env.NEXT_PUBLIC_GOOGLE_MAP_ID,
});
