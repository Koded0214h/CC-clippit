"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfileAvatar, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { BrandCampaignProvider } from "./BrandCampaignProvider";

const BRAND_PROFILE_FALLBACK: StoredProfile = { name: "Gbedu Records", bio: "", photo: "" };

const navigation: Array<{ href: string; label: string; mobile: string; icon: ProductIconName }> = [
  { href: "/brand", label: "Overview", mobile: "Home", icon: "home" },
  { href: "/brand/campaigns", label: "Campaigns", mobile: "Campaigns", icon: "campaigns" },
  { href: "/brand/campaigns/new", label: "Create campaign", mobile: "Create", icon: "spark" },
  { href: "/brand/reviews", label: "Review queue", mobile: "Review", icon: "eye" },
  { href: "/brand/settings", label: "Settings", mobile: "Settings", icon: "settings" },
];

function current(pathname: string, href: string) {
  if (href === "/brand") return pathname === href;
  if (href === "/brand/campaigns/new") return pathname.startsWith(href);
  if (href === "/brand/campaigns") return pathname.startsWith(href) && !pathname.startsWith("/brand/campaigns/new");
  return pathname.startsWith(href);
}

export function BrandShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const profile = useStoredProfile("brand", BRAND_PROFILE_FALLBACK);
  const initials = profile.name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "GR";
  return <BrandCampaignProvider><div className="brand-shell">
    <aside className="brand-rail">
      <Link href="/brand" className="brand-rail__logo" aria-label="Clippit brand workspace"><Image src="/assets/clippit-mark-light.png" width={42} height={42} alt="" priority /><strong>Clippit</strong><span>for brands</span></Link>
      <nav aria-label="Brand workspace navigation">{navigation.map((item) => <Link key={item.href} href={item.href} className={current(pathname, item.href) ? "is-active" : ""} aria-current={current(pathname, item.href) ? "page" : undefined}><ProductIcon name={item.icon} /><span>{item.label}</span>{item.label === "Review queue" && <b>7</b>}</Link>)}</nav>
      <div className="brand-rail__bottom"><div className="escrow-mark"><ProductIcon name="shield" /><span><small>Campaign funds</small><strong>Escrow protected</strong></span></div><Link href="/brand/settings" className="brand-profile"><ProfileAvatar profile={profile} fallback={initials} className="brand-profile__avatar" /><p><strong>{profile.name}</strong><small>Brand workspace</small></p><ProductIcon name="chevron" /></Link></div>
    </aside>
    <div className="brand-stage">
      <header className="brand-topbar"><Link href="/brand" className="brand-topbar__logo"><Image src="/assets/clippit-mark.png" width={31} height={31} alt="" /><strong>Clippit</strong><span>brands</span></Link><div className="brand-topbar__proof"><i />No long thing is live</div><div className="brand-topbar__actions"><Link href="/brand/campaigns/no-long-thing" className="brand-fund-pill"><ProductIcon name="wallet" /><span><small>Live pot</small><strong><AnimatedNumber value={312500} format="money" /></strong></span></Link><Link href="/brand/reviews" className="brand-alert" aria-label="Seven submissions need review"><ProductIcon name="bell" /><b>7</b></Link><Link href="/brand/settings" className="brand-avatar">{profile.photo ? <Image src={profile.photo} alt="" fill unoptimized sizes="48px" /> : initials}</Link></div></header>
      <main className="brand-content">{children}</main>
    </div>
    <nav className="brand-mobile-dock" aria-label="Brand mobile navigation">{navigation.map((item) => <Link key={item.href} href={item.href} className={current(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.mobile}</span>{item.label === "Review queue" && <b>7</b>}</Link>)}</nav>
  </div></BrandCampaignProvider>;
}
