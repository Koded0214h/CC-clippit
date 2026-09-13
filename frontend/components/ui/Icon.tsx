import type { ReactNode, SVGProps } from "react";

type IconName =
  | "arrow"
  | "back"
  | "building"
  | "check"
  | "eye"
  | "eye-off"
  | "lock"
  | "mail"
  | "user";

export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    back: <path d="m11 5-7 7 7 7M4 12h16" />,
    building: (
      <path d="M4 21V5l8-3v19M12 8h8v13M2 21h20M7 7h2m-2 4h2m-2 4h2m8-3h1m-1 4h1" />
    ),
    check: <path d="m5 12 4 4L19 6" />,
    eye: (
      <>
        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    "eye-off": (
      <path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A10 10 0 0 1 12 4c6 0 10 8 10 8a17 17 0 0 1-2.1 3.2M6.6 6.6C3.8 8.5 2 12 2 12s4 8 10 8a9.8 9.8 0 0 0 4.1-.9" />
    ),
    lock: (
      <>
        <rect x="4" y="10" width="16" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </>
    ),
    mail: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m4 7 8 6 8-6" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c.7-4.2 3.3-6.3 8-6.3s7.3 2.1 8 6.3" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true" {...props}>
      {paths[name]}
    </svg>
  );
}
