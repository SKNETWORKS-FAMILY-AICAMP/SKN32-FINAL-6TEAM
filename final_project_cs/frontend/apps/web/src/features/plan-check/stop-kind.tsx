import { BedDouble, Bike, Bus, Car, CircleHelp, Footprints, MapPin, Plane, Route, TrainFront, Utensils } from "lucide-react";
import { useT } from "@/lib/settings";
import type { PlanItem } from "./model";
import styles from "./plan-check.module.css";

const kinds = {
  lodging: { icon: BedDouble, label: ["숙박", "Lodging"] },
  dining: { icon: Utensils, label: ["식사", "Dining"] },
  train: { icon: TrainFront, label: ["기차·지하철", "Train"] },
  flight: { icon: Plane, label: ["비행기", "Flight"] },
  bus: { icon: Bus, label: ["버스", "Bus"] },
  car: { icon: Car, label: ["차량", "Car"] },
  bike: { icon: Bike, label: ["자전거", "Bicycle"] },
  walk: { icon: Footprints, label: ["걷기", "Walking"] },
  activity: { icon: MapPin, label: ["활동", "Activity"] },
  transport: { icon: Route, label: ["이동", "Transport"] },
  unknown: { icon: CircleHelp, label: ["일정 종류 미정", "Stop type not set"] },
} as const;

/** Only explicit stop/place kinds are used; a place name is not evidence of its type. */
export function stopKind(kind: string | null | undefined): keyof typeof kinds {
  const value = kind?.trim().toLowerCase();
  if (/^(lodging|hotel|accommodation|stay|숙박|숙소|호텔)$/.test(value ?? "")) return "lodging";
  if (/^(dining|restaurant|meal|food|식사|요식업|식당)$/.test(value ?? "")) return "dining";
  if (/^(rail|train|subway|metro|기차|열차|지하철)$/.test(value ?? "")) return "train";
  if (/^(flight|airplane|plane|항공|비행기)$/.test(value ?? "")) return "flight";
  if (/^(bus|버스)$/.test(value ?? "")) return "bus";
  if (/^(car|taxi|차량|택시)$/.test(value ?? "")) return "car";
  if (/^(bike|bicycle|자전거)$/.test(value ?? "")) return "bike";
  if (/^(walk|walking|도보|걷기)$/.test(value ?? "")) return "walk";
  if (/^(activity|tourism|sightseeing|shopping|leisure|활동|관광|쇼핑)$/.test(value ?? "")) return "activity";
  if (/^(transport|mobility|이동)$/.test(value ?? "")) return "transport";
  return "unknown";
}

export function StopKind({ item }: { item: Pick<PlanItem, "kind" | "info"> }) {
  const t = useT();
  const kind = stopKind(item.kind || item.info?.kind);
  const { icon: Icon, label } = kinds[kind];
  return <span className={styles.itemKind} data-stop-kind={kind} role="img" aria-label={t(label[0], label[1])} title={t(label[0], label[1])}>
    <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
  </span>;
}
