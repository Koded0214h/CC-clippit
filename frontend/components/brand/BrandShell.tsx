"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfileAvatar, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { useAutoHideDock } from "@/components/ui/useAutoHideDock";
import { BrandCampaignProvider } from "./BrandCampaignProvider";

const BRAND_PROFILE_FALLBACK: StoredProfile = { name: "Gbedu Records", bio: "", photo: "" };

const navigation: Array<{ href: string; label: string; mobile?: string; icon: ProductIconName }> = [
  { href: "/brand", label: "Overview", mobile: "Home", icon: "home" },
  { href: "/brand/campaigns", label: "Campaigns", mobile: "Campaigns", icon: "campaigns" },
  { href: "/brand/transactions", label: "Transactions", icon: "wallet" },
  { href: "/brand/campaigns/new", label: "Create campaign", mobile: "Create", icon: "spark" },
  { href: "/brand/reviews", label: "Review queue", mobile: "Review", icon: "eye" },
  { href: "/brand/team", label: "Team", icon: "users" },
  { href: "/brand/billing", label: "Billing", icon: "brief" },
  { href: "/brand/verification", label: "Verification", icon: "shield" },
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
  const dockHidden = useAutoHideDock();
  const [moreOpen, setMoreOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(4);
  useEffect(() => {
    const sync = (event?: Event) => {
      if (event instanceof CustomEvent && typeof event.detail === "number") { setUnreadNotifications(event.detail); return; }
      try {
        const read = JSON.parse(window.localStorage.getItem("clippit:brand-notifications-read") || "[]") as number[];
        setUnreadNotifications(Math.max(0, 4 - read.filter((id) => id >= 101 && id <= 104).length));
      } catch { setUnreadNotifications(4); }
    };
    sync();
    window.addEventListener("clippit:brand-notifications", sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener("clippit:brand-notifications", sync); window.removeEventListener("storage", sync); };
  }, []);
  const initials = profile.name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "GR";
  const mobilePrimary = navigation.filter((item) => item.mobile && item.label !== "Settings");
  const mobileMore = navigation.filter((item) => ["Transactions", "Team", "Billing", "Verification", "Settings"].includes(item.label));
  const moreIsCurrent = mobileMore.some((item) => current(pathname, item.href));
  return <BrandCampaignProvider><div className="brand-shell">
    <aside className="brand-rail">
      <Link href="/brand" className="brand-rail__logo" aria-label="Clippit brand workspace"><Image src="/assets/clippit-mark-light.png" width={42} height={42} alt="" priority /><strong>Clippit</strong><span>for brands</span></Link>
      <nav aria-label="Brand workspace navigation">{navigation.map((item) => <Link key={item.href} href={item.href} className={current(pathname, item.href) ? "is-active" : ""} aria-current={current(pathname, item.href) ? "page" : undefined}><ProductIcon name={item.icon} /><span>{item.label}</span>{item.label === "Review queue" && <b>7</b>}</Link>)}</nav>
      <div className="brand-rail__bottom"><div className="escrow-mark"><ProductIcon name="shield" /><span><small>Campaign funds</small><strong>Escrow protected</strong></span></div><Link href="/brand/settings" className="brand-profile"><ProfileAvatar profile={profile} fallback={initials} className="brand-profile__avatar" /><p><strong>{profile.name}</strong><small>Brand workspace</small></p><ProductIcon name="chevron" /></Link></div>
    </aside>
    <div className="brand-stage">
      <header className="brand-topbar"><Link href="/brand" className="brand-topbar__logo"><Image src="/assets/clippit-mark.png" width={31} height={31} alt="" /><strong>Clippit</strong><span>brands</span></Link><div className="brand-topbar__proof"><i />No long thing is live</div><div className="brand-topbar__actions"><Link href="/brand/transactions" className="brand-fund-pill"><ProductIcon name="wallet" /><span><small>Live pot</small><strong><AnimatedNumber value={312500} format="money" /></strong></span></Link><Link href="/brand/notifications" className="brand-alert" aria-label={`${unreadNotifications} unread notifications`} aria-current={pathname === "/brand/notifications" ? "page" : undefined}><ProductIcon name="bell" />{unreadNotifications > 0 && <b>{unreadNotifications}</b>}</Link><Link href="/brand/settings" className="brand-avatar">{profile.photo ? <Image src={profile.photo} alt="" fill unoptimized sizes="48px" /> : initials}</Link></div></header>
      <main className="brand-content">{children}</main>
    </div>
    {moreOpen && <button className="brand-mobile-more-backdrop" type="button" aria-label="Close workspace menu" onClick={() => setMoreOpen(false)} />}
    <section className={`brand-mobile-more${moreOpen ? " is-open" : ""}`} aria-label="More brand workspace pages" aria-hidden={!moreOpen}>
      <header><div><small>Workspace</small><strong>More tools</strong></div><button type="button" onClick={() => setMoreOpen(false)} aria-label="Close workspace menu"><ProductIcon name="more" /></button></header>
      <nav>{mobileMore.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={current(pathname, item.href) ? "is-active" : ""}><span><ProductIcon name={item.icon} /></span><strong>{item.label}</strong><ProductIcon name="arrow" /></Link>)}</nav>
    </section>
    <nav className={`brand-mobile-dock${dockHidden && !moreOpen ? " is-hidden" : ""}`} aria-label="Brand mobile navigation">{mobilePrimary.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={current(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.mobile}</span>{item.label === "Review queue" && <b>7</b>}</Link>)}<button type="button" className={moreIsCurrent || moreOpen ? "is-active" : ""} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><ProductIcon name="more" /><span>More</span></button></nav>
  </div></BrandCampaignProvider>;
}
