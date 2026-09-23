import type { ReactNode, SVGProps } from "react";

export type ProductIconName =
  | "arrow"
  | "bank"
  | "beauty"
  | "bell"
  | "brief"
  | "building"
  | "calendar"
  | "camera"
  | "campaigns"
  | "check"
  | "chevron"
  | "clock"
  | "filter"
  | "fitness"
  | "food"
  | "game"
  | "eye"
  | "facebook"
  | "home"
  | "instagram"
  | "link"
  | "more"
  | "music"
  | "pause"
  | "play"
  | "person"
  | "phone"
  | "search"
  | "settings"
  | "shield"
  | "spark"
  | "source"
  | "tiktok"
  | "tech"
  | "trophy"
  | "upload"
  | "users"
  | "wallet"
  | "travel"
  | "x"
  | "youtube";

export function ProductIcon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: ProductIconName }) {
  const paths: Record<ProductIconName, ReactNode> = {
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    bank: (
      <>
        <path d="M3 9h18L12 3 3 9Zm2 3v6m5-6v6m4-6v6m5-6v6M3 21h18" />
      </>
    ),
    beauty: (
      <>
        <path d="M8 4h8l-1 5H9L8 4Zm1 5h6l2 11H7L9 9Z" />
        <path d="M10 13h4M9 17h6" />
      </>
    ),
    bell: <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 13h4" />,
    brief: (
      <>
        <path d="M7 3h10v4H7zM5 5H3v16h18V5h-2" />
        <path d="M7 12h10M7 16h7" />
      </>
    ),
    building: (
      <>
        <path d="M4 21V5l8-3 8 3v16M2 21h20" />
        <path d="M8 7h2m4 0h2M8 11h2m4 0h2M8 15h2m4 0h2M10 21v-3h4v3" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
      </>
    ),
    camera: (
      <>
        <rect x="3" y="6" width="18" height="14" rx="3" />
        <path d="m8 6 1.5-2h5L16 6" />
        <circle cx="12" cy="13" r="4" />
      </>
    ),
    campaigns: (
      <>
        <path d="M4 13V8l13-4v13L4 13Zm13-5 4 2v5l-4 1" />
        <path d="m6 13 1.5 7h4L10 14" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    filter: <path d="M4 6h16M7 12h10m-7 6h4" />,
    fitness: <path d="M4 9v6m3-8v10m10-10v10m3-8v6M7 12h10M2 11v2m20-2v2" />,
    food: (
      <>
        <path d="M5 3v8m3-8v8M5 7h3m-1.5 4v10M16 3v18m0-18c3 2 4 5 4 8h-4" />
      </>
    ),
    eye: (
      <>
        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
        <circle cx="12" cy="12" r="2.7" />
      </>
    ),
    facebook: <path d="M14 8h4V3h-4c-4 0-6 2.4-6 6v3H5v5h3v4h5v-4h4l1-5h-5V9c0-.7.3-1 1-1Z" />,
    game: (
      <>
        <path d="M8 8h8c3 0 5 2.3 5 5.2 0 3.8-2 6-4 6-1.8 0-2.5-2.2-5-2.2s-3.2 2.2-5 2.2c-2 0-4-2.2-4-6C3 10.3 5 8 8 8Z" />
        <path d="M8 11v4m-2-2h4m6-1h.01m2 3h.01" />
      </>
    ),
    home: (
      <>
        <path d="m3 11 9-8 9 8" />
        <path d="M5 10v11h14V10M9 21v-7h6v7" />
      </>
    ),
    instagram: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r=".7" fill="currentColor" stroke="none" />
      </>
    ),
    link: (
      <>
        <path d="m9 15 6-6" />
        <path d="M7 17H5a4 4 0 0 1 0-8h4m6-2h4a4 4 0 0 1 0 8h-4" />
      </>
    ),
    more: (
      <>
        <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
      </>
    ),
    music: (
      <>
        <path d="M9 18V5l10-2v13" />
        <ellipse cx="6.5" cy="18" rx="2.5" ry="2" />
        <ellipse cx="16.5" cy="16" rx="2.5" ry="2" />
        <path d="M9 9l10-2" />
      </>
    ),
    pause: <path d="M7 5h3v14H7V5Zm7 0h3v14h-3V5Z" />,
    play: <path d="m9 7 8 5-8 5V7Z" />,
    person: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c.5-5 3.2-7.5 8-7.5s7.5 2.5 8 7.5" />
      </>
    ),
    phone: (
      <>
        <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
        <path d="M10 5h4M11 18.5h2" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    shield: <path d="M12 3 5 6v5c0 4.7 2.3 8 7 10 4.7-2 7-5.3 7-10V6l-7-3Zm-3 9 2 2 4-5" />,
    spark: <path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2Zm7 14 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" />,
    source: (
      <>
        <path d="M12 3v7m0 4v7M3 12h7m4 0h7" />
        <circle cx="12" cy="12" r="2" />
        <circle cx="12" cy="3" r="1.5" />
        <circle cx="21" cy="12" r="1.5" />
        <circle cx="12" cy="21" r="1.5" />
        <circle cx="3" cy="12" r="1.5" />
      </>
    ),
    tiktok: <path d="M14 4v10.5a4.5 4.5 0 1 1-4-4.5v3a1.7 1.7 0 1 0 1 1.6V4h3Zm0 0c.4 2.5 1.8 3.8 4 4" />,
    tech: (
      <>
        <rect x="4" y="5" width="16" height="12" rx="2" />
        <path d="M9 21h6m-3-4v4m-3-12-2 2 2 2m6-4 2 2-2 2m-4 1 2-6" />
      </>
    ),
    trophy: <path d="M8 4h8v4c0 4-1.3 6-4 6s-4-2-4-6V4Zm0 2H4v2c0 2.2 1.3 3.5 4 3.8M16 6h4v2c0 2.2-1.3 3.5-4 3.8M12 14v4m-4 3h8m-6-3h4" />,
    upload: <path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5" />,
    users: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c.4-4 2.4-6 6-6s5.6 2 6 6M16 5a3 3 0 0 1 0 6m1 3c2.5.5 3.8 2.5 4 6" />
      </>
    ),
    wallet: (
      <>
        <path d="M3 6h16a2 2 0 0 1 2 2v11H5a2 2 0 0 1-2-2V6Zm0 0 13-3v3" />
        <path d="M15 11h6v5h-6a2.5 2.5 0 0 1 0-5Z" />
      </>
    ),
    travel: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.4 2.5 3.6 5.5 3.6 9S14.4 18.5 12 21c-2.4-2.5-3.6-5.5-3.6-9S9.6 5.5 12 3Z" />
      </>
    ),
    x: <path d="M4 3h5.2l3.7 5.2L17.4 3H20l-5.9 7.1L20.5 21h-5.2l-4.1-5.8L6.3 21H3.7l6.2-7.7L4 3Zm3 2 9.4 14h1.2L8.2 5H7Z" />,
    youtube: (
      <>
        <path d="M21 12c0 3.2-.4 5-1.2 5.8S17.2 19 12 19s-7-.4-7.8-1.2S3 15.2 3 12s.4-5 1.2-5.8S6.8 5 12 5s7 .4 7.8 1.2S21 8.8 21 12Z" />
        <path d="m10 9 5 3-5 3V9Z" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
