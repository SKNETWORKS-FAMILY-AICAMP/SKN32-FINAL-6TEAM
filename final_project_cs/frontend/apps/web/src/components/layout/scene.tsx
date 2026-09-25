"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import styles from "./scene.module.css";

export type SceneStage = 0 | 1 | 2;
export interface ScenePulse { kind: "soft" | "complete"; id: number }

const layers = [
  ["paper", "/images/tripilot-home-02-paper-seoul.png"],
  ["river", "/images/tripilot-home-01-han-river.png"],
  ["journey", "/images/tripilot-home-03-journey.png"],
] as const;

/**
 * Decorative landscape behind onboarding and the journey. No form data, storage or network.
 * The parent must establish the containing block (the viewport or a contained frame).
 */
export function Scene({ stage, step = 0, totalSteps = 1, complete = false, pulse, sizes }: {
  stage: SceneStage; step?: number; totalSteps?: number; complete?: boolean; pulse?: ScenePulse; sizes: string;
}) {
  const [loaded, setLoaded] = useState<Record<string, boolean>>({});
  const scene = useRef<HTMLDivElement>(null);
  const light = useRef<HTMLDivElement>(null);
  const active = complete ? 0 : stage;

  useEffect(() => {
    const fine = matchMedia("(hover: hover) and (pointer: fine)");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    function paint(x: number, y: number) {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        scene.current?.style.setProperty("--scene-x", `${x * 7}px`);
        scene.current?.style.setProperty("--scene-y", `${y * 5}px`);
      });
    }
    function move(event: PointerEvent) {
      if (!fine.matches || reduced.matches || event.pointerType === "touch") return;
      paint(Math.max(-1, Math.min(1, event.clientX / innerWidth * 2 - 1)), Math.max(-1, Math.min(1, event.clientY / innerHeight * 2 - 1)));
    }
    const reset = () => paint(0, 0);
    document.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", reset);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", reset);
    };
  }, []);

  useEffect(() => {
    if (!pulse || document.hidden || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const finishing = pulse.kind === "complete";
    const animation = light.current?.animate([
      { opacity: 0, transform: "scale(.98)" },
      { opacity: finishing ? .7 : .32, transform: "scale(1)", offset: .35 },
      { opacity: 0, transform: "scale(1.025)" },
    ], { duration: finishing ? 1250 : 700, easing: "ease-out" });
    return () => animation?.cancel();
  }, [pulse]);

  const progress = stage === 2 ? (step / Math.max(1, totalSteps - 1) - .5) * 12 : 0;
  const style = { "--scene-progress": `${progress}px` } as CSSProperties;

  return <div ref={scene} className={styles.scene} style={style} aria-hidden="true" data-scene={layers[active][0]}>
    <div className={styles.camera}>
      {layers.map(([name, src], index) => (
        <div key={name} className={styles.layer} data-scene={name} data-active={index === active} data-loaded={Boolean(loaded[name])}>
          <Image src={src} alt="" fill sizes={sizes} priority={index === 0} draggable={false} onLoad={() => setLoaded((current) => ({ ...current, [name]: true }))} />
        </div>
      ))}
    </div>
    <div className={styles.veil} />
    <div ref={light} className={styles.light} />
  </div>;
}
