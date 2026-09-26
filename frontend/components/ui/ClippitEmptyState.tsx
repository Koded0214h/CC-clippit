import Image from "next/image";
import type { ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

type EmptyTone = "lime" | "gold" | "paper" | "ink" | "danger";
type EmptySize = "hero" | "panel" | "compact" | "inline";

const emptyArt: Partial<Record<ProductIconName, string>> = {
  bank: "/assets/illustrations/clippit-icons/withdraw-bank.webp",
  bell: "/assets/illustrations/clippit-icons/appeal-review.webp",
  brief: "/assets/illustrations/clippit-icons/campaign-brief.webp",
  camera: "/assets/illustrations/clippit-icons/creator-camera.webp",
  campaigns: "/assets/illustrations/clippit-icons/campaign-brief.webp",
  eye: "/assets/illustrations/clippit-icons/taste-eye.webp",
  link: "/assets/illustrations/clippit-icons/social-connect.webp",
  person: "/assets/illustrations/clippit-icons/creator-camera.webp",
  play: "/assets/illustrations/clippit-icons/clip-submit.webp",
  search: "/assets/illustrations/clippit-icons/taste-eye.webp",
  shield: "/assets/illustrations/clippit-icons/verified-proof.webp",
  trophy: "/assets/illustrations/clippit-icons/verified-proof.webp",
  wallet: "/assets/illustrations/clippit-icons/payout-wallet.webp",
};

export function ClippitEmptyState({
  title,
  copy,
  icon = "spark",
  tone = "lime",
  size = "panel",
  action,
  artSrc,
  className = "",
  role,
}: {
  title: string;
  copy: string;
  icon?: ProductIconName;
  tone?: EmptyTone;
  size?: EmptySize;
  action?: ReactNode;
  artSrc?: string;
  className?: string;
  role?: "status" | "alert";
}) {
  const source = artSrc ?? emptyArt[icon] ?? "/assets/illustrations/clippit-icons/clip-submit.webp";

  return (
    <section className={`clippit-empty clippit-empty--${tone} clippit-empty--${size}${className ? ` ${className}` : ""}`} role={role}>
      <div className="clippit-empty__visual" aria-hidden="true">
        <span className="clippit-empty__track"><i /><i /><i /><i /></span>
        <span className="clippit-empty__art"><Image src={source} alt="" width={320} height={320} sizes="(max-width: 700px) 96px, 220px" /></span>
        <span className="clippit-empty__glyph"><ProductIcon name={icon} /></span>
        <span className="clippit-empty__count">00</span>
      </div>
      <div className="clippit-empty__body">
        <h2>{title}</h2>
        <p>{copy}</p>
        {action && <div className="clippit-empty__actions">{action}</div>}
      </div>
    </section>
  );
}
