/** OpenStreetMap standard tiles. Policy: https only, visible attribution, no bulk/offline fetching. */
export const OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export type MapConfiguration =
  | { provider: "demo" }
  | { provider: "osm"; tileUrl: string }
  | { provider: "naver"; clientId: string }
  /** ★Google is only loaded after the server allows it (`POST /v1/web/map-load`); otherwise the free map (`tileUrl`) is shown. */
  | { provider: "google"; apiKey: string; mapId: string; tileUrl: string }
  | { provider: "unavailable"; message: string };

interface MapEnvironment {
  provider?: string;
  naverClientId?: string;
  googleApiKey?: string;
  googleMapId?: string;
  osmTileUrl?: string;
}

/** The free-map tile address; only https is accepted (the OSM tile policy forbids http). */
function tileUrl(value: string | undefined): string | null {
  const url = value?.trim() || OSM_TILE_URL;
  return url.startsWith("https://") && url.includes("{z}") && url.includes("{x}") && url.includes("{y}") ? url : null;
}

export function resolveMapConfiguration(environment: MapEnvironment): MapConfiguration {
  const provider = environment.provider?.trim() || "demo";
  if (provider === "demo") return { provider };
  const tiles = tileUrl(environment.osmTileUrl);
  if (provider === "osm") return tiles ? { provider, tileUrl: tiles } : { provider: "unavailable", message: "무료 지도 주소 설정이 올바르지 않아요(https 주소여야 해요)." };
  if (provider === "naver") {
    const clientId = environment.naverClientId?.trim();
    return clientId ? { provider, clientId } : { provider: "unavailable", message: "네이버지도 연결 설정이 필요해요." };
  }
  if (provider === "google") {
    const apiKey = environment.googleApiKey?.trim();
    const mapId = environment.googleMapId?.trim();
    if (!apiKey || !mapId) return { provider: "unavailable", message: "Google Maps 연결 설정이 필요해요." };
    return tiles ? { provider, apiKey, mapId, tileUrl: tiles } : { provider: "unavailable", message: "무료 지도 주소 설정이 올바르지 않아요(https 주소여야 해요)." };
  }
  return { provider: "unavailable", message: "지도 제공자 설정이 올바르지 않아요." };
}

// Static references are required for Next.js to embed these browser settings.
export const mapConfiguration = resolveMapConfiguration({
  provider: process.env.NEXT_PUBLIC_MAP_PROVIDER,
  naverClientId: process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID,
  googleApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAP_API_KEY,
  googleMapId: process.env.NEXT_PUBLIC_GOOGLE_MAP_ID,
  osmTileUrl: process.env.NEXT_PUBLIC_OSM_TILE_URL,
});
