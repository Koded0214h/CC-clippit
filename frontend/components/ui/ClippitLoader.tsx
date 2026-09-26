"use client";

import { type CSSProperties, useId } from "react";

type LoaderTone = "paper" | "ink" | "gold" | "lime";

export function ClippitMarkMotion({ compact = false, light = false }: { compact?: boolean; light?: boolean }) {
  const instanceId = useId().replace(/:/g, "");
  const accentGradientId = `clippit-loader-accent-${instanceId}`;
  const bodyPath = "M69.38 16.25L24.69 27.19L20 29.38L15 34.06L12.5 38.12L10.94 42.5L4.38 69.69L.31 83.12L0 87.19L.62 90.31L2.5 93.75L5 96.25L10.31 98.75L16.25 99.06L62.19 91.56L65.94 90.62L70.62 88.44L76.25 83.44L77.81 81.25L79.69 77.19L81.88 65L81.88 62.5L81.25 62.19L67.81 66.25L67.5 56.56L80.62 51.88L81.88 50.62L81.88 33.12L81.25 33.12L65.94 47.5L65.62 43.75L69.69 40L51.56 40L47.5 43.75L41.25 43.75L46.88 39.06L69.69 17.19Z";
  const arrowPath = "M99.38 3.12L97.81 1.88L95.94 1.88L72.19 8.12L71.25 9.38L71.88 11.56L78.44 14.38L47.5 43.75L65.62 43.75L86.88 23.75L89.69 29.38L90.94 30.31L92.81 30L93.75 28.75L99.69 4.38Z";
  const playPath = "M42.5 48.75L40.62 49.06L39.06 51.25L39.06 71.25L39.69 72.5L40.62 73.12L42.5 73.12L57.81 62.5L59.38 60.62L59.06 58.44L58.12 57.5Z";

  return <span className={`clippit-mark-motion${compact ? " clippit-mark-motion--compact" : ""}${light ? " clippit-mark-motion--light" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 100 100" role="presentation">
      <defs>
        <linearGradient id={accentGradientId} x1="38" y1="72" x2="98" y2="2" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--load-accent-start, #a5ff12)" />
          <stop offset="1" stopColor="var(--load-accent-end, #c4ff2f)" />
        </linearGradient>
      </defs>
      <g className="clippit-logo-piece clippit-logo-piece--body">
        <path className="clippit-logo-fill" d={bodyPath} />
        <path className="clippit-logo-trace" pathLength="1" d={bodyPath} />
      </g>
      <path className="clippit-logo-play-space" d={playPath} />
      <g className="clippit-logo-piece clippit-logo-piece--play" style={{ "--clippit-accent": `url(#${accentGradientId})` } as CSSProperties}>
        <path className="clippit-logo-fill" d={playPath} />
        <path className="clippit-logo-trace" pathLength="1" d={playPath} />
      </g>
      <g className="clippit-logo-piece clippit-logo-piece--arrow" style={{ "--clippit-accent": `url(#${accentGradientId})` } as CSSProperties}>
        <path className="clippit-logo-fill" d={arrowPath} />
        <path className="clippit-logo-trace" pathLength="1" d={arrowPath} />
      </g>
    </svg>
  </span>;
}

export function ClippitLoader({
  label = "Opening Clippit",
  note = "Your workspace is almost ready.",
  tone = "paper",
  contained = false,
  compact = false,
}: {
  label?: string;
  note?: string;
  tone?: LoaderTone;
  contained?: boolean;
  compact?: boolean;
}) {
  return <div className={`clippit-loader clippit-loader--${tone}${contained ? " clippit-loader--contained" : ""}${compact ? " clippit-loader--compact" : ""}`} role="status" aria-label={`${label}. ${note}`} aria-live="polite" aria-busy="true">
    <div className="clippit-loader__stage">
      <ClippitMarkMotion compact={compact} light={tone === "ink"} />
    </div>
  </div>;
}

export function ButtonLoader({ label }: { label: string }) {
  return <span className="clippit-button-loader" role="status" aria-label={label} aria-live="polite"><ClippitMarkMotion compact /></span>;
}

export function InlineLoader({ label = "Loading" }: { label?: string }) {
  return <span className="clippit-inline-loader" role="status" aria-label={label} aria-live="polite" aria-busy="true"><ClippitMarkMotion compact /></span>;
}
