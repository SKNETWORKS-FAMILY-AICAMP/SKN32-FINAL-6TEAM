"use client";

import { useId, useState } from "react";
import { TAXI_PRODUCTS, type TaxiProduct, type WebTaxiPricing } from "@/lib/live/taxi-pricing";
import { useT } from "@/lib/settings";
import styles from "./taxi-pricing.module.css";

/** 저장 성공 응답의 현재값과 아직 저장하지 않은 선택을 구분합니다. */
export function TaxiPricing({ value, locked, onSave }: {
  value: WebTaxiPricing;
  locked: string | null;
  onSave: (value: WebTaxiPricing) => Promise<void>;
}) {
  const t = useT();
  const id = useId();
  const [draft, setDraft] = useState<TaxiProduct | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [saved, setSaved] = useState(false);
  const selected = draft ?? value.product;
  const current = TAXI_PRODUCTS.find((product) => product.id === value.product)!;
  async function save() {
    if (busy || locked || selected === value.product) return;
    setBusy(true); setProblem(""); setSaved(false);
    try {
      await onSave({ product: selected, quotes: [] });
      setDraft(null); setSaved(true);
    } catch (error) {
      setProblem(error instanceof Error ? error.message : t("저장하지 못했어요. 다시 저장해 주세요.", "Could not save. Try saving again."));
    } finally { setBusy(false); }
  }
  return <details className={styles.box}>
    <summary>{t("이 여행의 택시 호출 상품", "Taxi service for this trip")}<span>{t(current.ko, current.en)}</span></summary>
    <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <label htmlFor={id}>{t("호출 상품", "Taxi service")}</label>
      <select id={id} value={selected} disabled={busy || Boolean(locked)} aria-describedby={`${id}-help`}
        onChange={(event) => { setDraft(event.target.value as TaxiProduct); setProblem(""); setSaved(false); }}>
        {TAXI_PRODUCTS.map((product) => <option key={product.id} value={product.id}>{t(product.ko, product.en)}</option>)}
      </select>
      <p id={`${id}-help`}>{t("저장하면 이 여행의 모든 택시 구간을 같은 상품으로 다시 계산해요. 호출 상품별 공식 이용료 범위의 상단을 예산에 포함해요.", "Saving recalculates every taxi leg with this service. The budget includes the upper end of the official service fee range for the selected service.")}</p>
      <p>{t("예약·별도 견적 상품은 여기서 지원하지 않아요. 택시 배차나 결제는 진행하지 않아요.", "Reservations and services requiring separate quotes are not supported here. This does not book or pay for a taxi.")}</p>
      {locked && <p role="status">{locked}</p>}
      {problem && <p className={styles.error} role="alert">{problem}</p>}
      {saved && <p role="status">{t("저장했어요. 새 요금은 이동 수단에서 확인해 주세요.", "Saved. Check the new budget under Way to go.")}</p>}
      <button type="submit" disabled={busy || Boolean(locked) || selected === value.product}>{busy ? t("다시 계산하는 중…", "Recalculating…") : t("저장하고 요금 다시 계산", "Save and recalculate budget")}</button>
    </form>
  </details>;
}
