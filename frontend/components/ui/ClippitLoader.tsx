"use client";

import { useId } from "react";

type LoaderTone = "paper" | "ink" | "gold" | "lime";

export function ClippitMarkMotion({ compact = false, light = false }: { compact?: boolean; light?: boolean }) {
  const instanceId = useId().replace(/:/g, "");
  const bodyMaskId = `clippit-write-body-${instanceId}`;
  const accentMaskId = `clippit-write-accent-${instanceId}`;
  return <span className={`clippit-mark-motion${compact ? " clippit-mark-motion--compact" : ""}${light ? " clippit-mark-motion--light" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 100 100" role="presentation">
      <defs>
        <mask id={bodyMaskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
          <path className="clippit-logo-path clippit-logo-path--body" pathLength="1" d="M69 48 C59 42 45 42 33 48 C21 54 15 66 15 79 C15 91 25 96 39 92 L57 87 C68 84 74 77 73 64" />
        </mask>
        <mask id={accentMaskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
          <path className="clippit-logo-path clippit-logo-path--play" pathLength="1" d="M42 54 L58 64 L42 75 Z" />
          <path className="clippit-logo-path clippit-logo-path--arrow" pathLength="1" d="M50 46 L89 8" />
          <path className="clippit-logo-path clippit-logo-path--arrow-head" pathLength="1" d="M71 15 L89 8 L85 28" />
        </mask>
      </defs>
      <image href={light ? "/assets/clippit-mark-light-loader.webp" : "/assets/clippit-mark-loader.webp"} width="100" height="100" preserveAspectRatio="xMidYMid meet" mask={`url(#${bodyMaskId})`} />
      <image href="/assets/clippit-mark-accent-loader.webp" width="100" height="100" preserveAspectRatio="xMidYMid meet" mask={`url(#${accentMaskId})`} />
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
