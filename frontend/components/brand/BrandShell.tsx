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
import { useUser } from "@/lib/user-context";
import { notificationsApi } from "@/lib/api/notifications";
import { brandApi } from "@/lib/api/brand";

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

const brandResourceNavigation: Array<{ href: string; label: string; copy: string; icon: ProductIconName }> = [
  { href: "/help", label: "Help centre", copy: "Campaign and account guides", icon: "brief" },
  { href: "/support/tickets", label: "Support", copy: "Messages and support tickets", icon: "users" },
  { href: "/disputes", label: "Disputes", copy: "Formal reviews and evidence", icon: "eye" },
  { href: "/account/data", label: "Account & data", copy: "Download or delete account data", icon: "person" },
  { href: "/legal", label: "Legal & privacy", copy: "Terms, policies and consent", icon: "shield" },
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
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [pendingReviews, setPendingReviews] = useState(0);
  const [livePot, setLivePot] = useState(312500);
  const { user, logout } = useUser();
  const displayName = user?.full_name ?? profile.name;
  useEffect(() => {
    notificationsApi.unreadCount().then((data) => setUnreadNotifications(data.unread_count)).catch(() => undefined);
    brandApi.overview().then((data) => {
      setPendingReviews(data.pending_reviews);
      setLivePot(data.total_pot - data.total_spent);
    }).catch(() => undefined);
  }, []);
  const initials = displayName.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "U";
  const mobilePrimary = navigation.filter((item) => item.mobile && item.label !== "Settings");
  const mobileMore = navigation.filter((item) => ["Transactions", "Team", "Billing", "Verification", "Settings"].includes(item.label));
  const moreIsCurrent = [...mobileMore, ...brandResourceNavigation].some((item) => current(pathname, item.href));
  return <BrandCampaignProvider><div className="brand-shell">
    <aside className="brand-rail">
      <Link href="/brand" className="brand-rail__logo" aria-label="Clippit brand workspace"><Image src="/assets/clippit-mark-light.png" width={42} height={42} alt="" priority /><strong>Clippit</strong><span>for brands</span></Link>
      <nav aria-label="Brand workspace navigation">{navigation.map((item) => <Link key={item.href} href={item.href} className={current(pathname, item.href) ? "is-active" : ""} aria-current={current(pathname, item.href) ? "page" : undefined}><ProductIcon name={item.icon} /><span>{item.label}</span>{item.label === "Review queue" && pendingReviews > 0 && <b>{pendingReviews}</b>}</Link>)}</nav>
      <nav className="brand-resource-nav" aria-label="Account and support"><Link href="/help"><ProductIcon name="brief" /><span>Help & support</span></Link><Link href="/legal"><ProductIcon name="shield" /><span>Legal & privacy</span></Link></nav>
      <div className="brand-rail__bottom"><div className="escrow-mark"><ProductIcon name="shield" /><span><small>Campaign funds</small><strong>Escrow protected</strong></span></div><Link href="/brand/settings" className="brand-profile"><ProfileAvatar profile={profile} fallback={initials} className="brand-profile__avatar" /><p><strong>{displayName}</strong><small>Brand workspace</small></p><ProductIcon name="chevron" /></Link><button type="button" className="rail-signout" onClick={logout} aria-label="Sign out">Sign out</button></div>
    </aside>
    <div className="brand-stage">
      <header className="brand-topbar"><Link href="/brand" className="brand-topbar__logo"><Image src="/assets/clippit-mark.png" width={31} height={31} alt="" /><strong>Clippit</strong><span>brands</span></Link><div className="brand-topbar__proof"><i />No long thing is live</div><div className="brand-topbar__actions"><Link href="/brand/transactions" className="brand-fund-pill"><ProductIcon name="wallet" /><span><small>Live pot</small><strong><AnimatedNumber value={livePot} format="money" /></strong></span></Link><Link href="/brand/notifications" className="brand-alert" aria-label={`${unreadNotifications} unread notifications`} aria-current={pathname === "/brand/notifications" ? "page" : undefined}><ProductIcon name="bell" />{unreadNotifications > 0 && <b>{unreadNotifications}</b>}</Link><Link href="/brand/settings" className="brand-avatar">{profile.photo ? <Image src={profile.photo} alt="" fill unoptimized sizes="48px" /> : initials}</Link></div></header>
      <main className="brand-content">{children}</main>
    </div>
    {moreOpen && <button className="brand-mobile-more-backdrop" type="button" aria-label="Close workspace menu" onClick={() => setMoreOpen(false)} />}
    <section className={`brand-mobile-more${moreOpen ? " is-open" : ""}`} aria-label="More brand workspace pages" aria-hidden={!moreOpen}>
      <header><div><small>Workspace</small><strong>More tools</strong></div><button type="button" onClick={() => setMoreOpen(false)} aria-label="Close workspace menu"><ProductIcon name="more" /></button></header>
      <nav>{mobileMore.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={current(pathname, item.href) ? "is-active" : ""}><span><ProductIcon name={item.icon} /></span><p><strong>{item.label}</strong><small>{item.label === "Transactions" ? "Funding and money movement" : item.label === "Team" ? "Members and invitations" : item.label === "Billing" ? "Details, invoices and receipts" : item.label === "Verification" ? "Business details and documents" : "Organisation and alerts"}</small></p><ProductIcon name="arrow" /></Link>)}{brandResourceNavigation.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={current(pathname, item.href) ? "is-active" : ""}><span><ProductIcon name={item.icon} /></span><p><strong>{item.label}</strong><small>{item.copy}</small></p><ProductIcon name="arrow" /></Link>)}</nav>
    </section>
    <nav className={`brand-mobile-dock${dockHidden && !moreOpen ? " is-hidden" : ""}`} aria-label="Brand mobile navigation">{mobilePrimary.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={current(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.mobile}</span>{item.label === "Review queue" && pendingReviews > 0 && <b>{pendingReviews}</b>}</Link>)}<button type="button" className={moreIsCurrent || moreOpen ? "is-active" : ""} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><ProductIcon name="more" /><span>More</span></button></nav>
  </div></BrandCampaignProvider>;
}
