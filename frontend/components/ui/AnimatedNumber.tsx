"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type NumberFormat = "number" | "money" | "compact";

type AnimatedNumberProps = {
  value: number;
  format?: NumberFormat;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  padStart?: number;
  duration?: number;
  delay?: number;
  className?: string;
};

function compact(value: number, decimals?: number) {
  const absolute = Math.abs(value);
  const unit = absolute >= 1_000_000 ? "M" : absolute >= 1_000 ? "K" : "";
  const divisor = unit === "M" ? 1_000_000 : unit === "K" ? 1_000 : 1;
  const scaled = value / divisor;
  const precision = decimals ?? (unit && Math.abs(scaled % 1) > 0.001 ? 1 : 0);
  return `${scaled.toLocaleString("en-NG", { minimumFractionDigits: precision, maximumFractionDigits: precision })}${unit}`;
}

function formatNumber(value: number, format: NumberFormat, decimals?: number, padStart = 0) {
  if (format === "money") return `₦${Math.round(value).toLocaleString("en-NG")}`;
  if (format === "compact") return compact(value, decimals);
  const precision = decimals ?? 0;
  const rendered = value.toLocaleString("en-NG", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
  return padStart ? rendered.padStart(padStart, "0") : rendered;
}

export function AnimatedNumber({
  value,
  format = "number",
  decimals,
  prefix = "",
  suffix = "",
  padStart = 0,
  duration = 1250,
  delay = 0,
  className = "",
}: AnimatedNumberProps) {
  const hostRef = useRef<HTMLSpanElement>(null);
  const displayedRef = useRef(0);
  const frameRef = useRef(0);
  const timerRef = useRef(0);
  const [displayed, setDisplayed] = useState(0);
  const [settled, setSettled] = useState(false);

  const finalText = useMemo(
    () => `${prefix}${formatNumber(value, format, decimals, padStart)}${suffix}`,
    [decimals, format, padStart, prefix, suffix, value],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let cancelled = false;

    const run = () => {
      window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        if (cancelled || reduceMotion) {
          displayedRef.current = value;
          setDisplayed(value);
          setSettled(true);
          return;
        }

        const from = displayedRef.current;
        const distance = value - from;
        const started = performance.now();
        setSettled(false);

        const update = (now: number) => {
          const progress = Math.min(1, (now - started) / duration);
          const eased = 1 - Math.pow(1 - progress, 5);
          const next = from + distance * eased;
          displayedRef.current = next;
          setDisplayed(next);
          if (progress < 1) frameRef.current = window.requestAnimationFrame(update);
          else {
            displayedRef.current = value;
            setDisplayed(value);
            setSettled(true);
          }
        };

        frameRef.current = window.requestAnimationFrame(update);
      }, delay);
    };

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        run();
      }
    }, { threshold: 0.2 });

    observer.observe(host);
    return () => {
      cancelled = true;
      observer.disconnect();
      window.clearTimeout(timerRef.current);
      window.cancelAnimationFrame(frameRef.current);
    };
  }, [delay, duration, value]);

  const rendered = `${prefix}${formatNumber(displayed, format, decimals, padStart)}${suffix}`;

  return (
    <span ref={hostRef} className={`animated-number${settled ? " is-settled" : ""}${className ? ` ${className}` : ""}`} aria-label={finalText}>
      <span aria-hidden="true">{rendered}</span>
    </span>
  );
}
