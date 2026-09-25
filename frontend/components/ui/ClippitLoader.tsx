"use client";

import { useId } from "react";

type LoaderTone = "paper" | "ink" | "gold" | "lime";

export function ClippitMarkMotion({ compact = false, light = false }: { compact?: boolean; light?: boolean }) {
  const maskId = `clippit-write-${useId().replace(/:/g, "")}`;
  return <span className={`clippit-mark-motion${compact ? " clippit-mark-motion--compact" : ""}${light ? " clippit-mark-motion--light" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 100 100" role="presentation">
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
          <path className="clippit-logo-path clippit-logo-path--c" pathLength="1" d="M69 48 C61 44 49 44 40 46 C31 48 27 55 25 65 L23 76 C22 85 27 89 37 87 L55 84 C64 83 69 77 69 68 L69 62" />
          <path className="clippit-logo-path clippit-logo-path--play" pathLength="1" d="M42 53 L59 64 L42 76 Z" />
          <path className="clippit-logo-path clippit-logo-path--arrow" pathLength="1" d="M49 45 L90 7" />
          <path className="clippit-logo-path clippit-logo-path--arrow-head" pathLength="1" d="M71 14 L90 7 L86 28" />
        </mask>
      </defs>
      <image href={light ? "/assets/clippit-mark-light.png" : "/assets/clippit-mark.png"} width="100" height="100" preserveAspectRatio="xMidYMid meet" mask={`url(#${maskId})`} />
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
