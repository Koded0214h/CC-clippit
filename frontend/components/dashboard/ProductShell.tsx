"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProfileAvatar, saveStoredProfile, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { useAutoHideDock } from "@/components/ui/useAutoHideDock";
import { useUser } from "@/lib/user-context";
import { earningsApi } from "@/lib/api/earnings";
import { NOTIFICATIONS_CHANGED, notificationsApi } from "@/lib/api/notifications";
import { creatorProfileApi, socialApi } from "@/lib/api/social";
import { timeAgo } from "@/lib/format";

const CREATOR_PROFILE_FALLBACK: StoredProfile = { name: "", bio: "", photo: "" };

const navItems: Array<{ href: string; label: string; icon: ProductIconName }> = [
  { href: "/dashboard", label: "Overview", icon: "home" },
  { href: "/dashboard/campaigns", label: "Campaigns", icon: "campaigns" },
  { href: "/dashboard/clips", label: "My clips", icon: "play" },
  { href: "/dashboard/wallet", label: "Wallet", icon: "wallet" },
  { href: "/dashboard/leaderboard", label: "Leaderboard", icon: "trophy" },
  { href: "/dashboard/settings", label: "Settings", icon: "settings" },
];

const mobileNavItems = navItems.filter((item) => !["Leaderboard", "Settings"].includes(item.label));

const creatorMoreItems: Array<{ href: string; label: string; copy: string; icon: ProductIconName }> = [
  { href: "/dashboard/settings", label: "Settings", copy: "Profile, accounts and alerts", icon: "settings" },
  { href: "/dashboard/leaderboard", label: "Leaderboard", copy: "Creator rankings", icon: "trophy" },
  { href: "/dashboard/verification", label: "Account checks", copy: "What you need to earn and withdraw", icon: "shield" },
  { href: "/account/data", label: "Account & data", copy: "Download or delete account data", icon: "person" },
  { href: "/help", label: "Help centre", copy: "Guides for using Clippit", icon: "brief" },
  { href: "/support/tickets", label: "Support", copy: "Messages and support tickets", icon: "users" },
  { href: "/disputes", label: "Disputes", copy: "Formal reviews and evidence", icon: "eye" },
  { href: "/legal", label: "Legal & privacy", copy: "Terms, policies and consent", icon: "shield" },
];

function isCurrent(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  if (href === "/dashboard/wallet" && ["/dashboard/wallet", "/dashboard/earnings", "/dashboard/withdraw", "/dashboard/payouts/receipt"].some((route) => pathname.startsWith(route))) return true;
  if (href === "/dashboard/settings" && ["/dashboard/accounts", "/dashboard/payout-account", "/dashboard/security", "/dashboard/profile", "/dashboard/verification"].some((route) => pathname.startsWith(route))) return true;
  return pathname.startsWith(href);
}

export function ProductShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const profile = useStoredProfile("creator", CREATOR_PROFILE_FALLBACK);
  const dockHidden = useAutoHideDock();
  const [moreOpen, setMoreOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [payable, setPayable] = useState<number | null>(null);
  const [notifCount, setNotifCount] = useState(0);
  const [lastChecked, setLastChecked] = useState<string | null | undefined>(undefined);
  const { user, logout } = useUser();
  const displayName = profile.name || user?.full_name || "";
  const initials = displayName.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "U";
  const moreIsCurrent = creatorMoreItems.some((item) => pathname.startsWith(item.href));

  useEffect(() => {
    creatorProfileApi.get().then((data) => saveStoredProfile("creator", { name: data.display_name, bio: data.bio ?? "", photo: data.photo_url ?? "" })).catch(() => undefined);
    socialApi.accounts().then((accounts) => {
      const times = accounts.map((account) => account.last_checked_at).filter((value): value is string => !!value).sort();
      setLastChecked(accounts.some((account) => account.connected) ? times[times.length - 1] ?? null : null);
    }).catch(() => setLastChecked(null));
  }, []);

  useEffect(() => {
    earningsApi.summary().then((data) => setPayable(data.payable)).catch(() => undefined);
    const refreshCount = () => notificationsApi.unreadCount().then((data) => setNotifCount(data.unread_count)).catch(() => undefined);
    void refreshCount();
    window.addEventListener(NOTIFICATIONS_CHANGED, refreshCount);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED, refreshCount);
  }, [pathname]);

  const verifyEmail = () => {
    try {
      if (user?.email) window.sessionStorage.setItem("clippit:verify-email", user.email);
      window.sessionStorage.setItem("clippit:verify-autosend", "1");
    } catch { /* storage blocked */ }
  };

  const signOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setMoreOpen(false);
    await logout();
  };

  return (
    <div className="product-shell">
      <aside className="studio-rail">
        <Link className="studio-brand" href="/dashboard" aria-label="Clippit overview">
          <Image src="/assets/clippit-mark-light.png" width={38} height={38} alt="" priority />
          <span>Clippit</span>
        </Link>
        <nav className="studio-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={isCurrent(pathname, item.href) ? "is-active" : ""}
              aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
            >
              <ProductIcon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <nav className="studio-resource-nav" aria-label="Account and support">
          <Link href="/help"><ProductIcon name="brief" /><span>Help & support</span></Link>
          <Link href="/legal"><ProductIcon name="shield" /><span>Legal & privacy</span></Link>
        </nav>
        <div className="studio-rail__bottom">
          <div className="trust-pulse">
            <ProductIcon name="shield" />
            <span>
              Platform views
              <strong>Verified</strong>
            </span>
          </div>
          <Link className="rail-profile" href="/dashboard/settings">
            <ProfileAvatar profile={profile} fallback={initials} className="avatar" />
            <span>
              <strong>{displayName}</strong>
              <small>Creator</small>
            </span>
            <ProductIcon name="chevron" />
          </Link>
          <button type="button" className="rail-signout" onClick={signOut} disabled={signingOut} aria-label="Sign out" aria-busy={signingOut}>
            <ProductIcon name="logout" /><span>Sign out</span>
          </button>
        </div>
      </aside>

      <div className="product-stage">
        <header className="product-topbar">
          <Link className="mobile-brand" href="/dashboard" aria-label="Clippit overview">
            <Image src="/assets/clippit-mark.png" width={32} height={32} alt="" priority />
            <strong>Clippit</strong>
          </Link>
          {lastChecked === null
            ? <Link className="topbar-proof" href="/dashboard/accounts"><span />Connect an account to track views</Link>
            : <div className="topbar-proof"><span />{lastChecked ? `Views last checked ${timeAgo(lastChecked)}` : "Views are checked after your first approved clip"}</div>}
          <div className="topbar-actions">
            <Link className="wallet-pill" href="/dashboard/wallet">
              <ProductIcon name="wallet" />
              <span>Payable</span>
              <strong>{payable === null ? "—" : <AnimatedNumber value={payable} format="money" duration={1000} />}</strong>
            </Link>
            <Link className="icon-button" href="/dashboard/notifications" aria-label="Notifications">
              <ProductIcon name="bell" />
              {notifCount > 0 && <b>{notifCount}</b>}
            </Link>
            <Link className="topbar-avatar" href="/dashboard/settings" aria-label="Open profile settings">
              {profile.photo ? <Image src={profile.photo} alt="" fill unoptimized sizes="48px" /> : initials}
            </Link>
          </div>
        </header>
        {user && !user.email_verified && (
          <div className="verify-email-banner" role="status">
            <ProductIcon name="shield" />
            <span><strong>Confirm your email to start earning.</strong> Joining campaigns, submitting clips and withdrawing all need a confirmed email.</span>
            <Link href="/auth/verify-email" onClick={verifyEmail}>Send code<ProductIcon name="arrow" /></Link>
          </div>
        )}
        <main className="product-content">{children}</main>
      </div>

      {moreOpen && <button className="creator-mobile-more-backdrop" type="button" aria-label="Close more menu" onClick={() => setMoreOpen(false)} />}
      <section id="creator-more-menu" className={`creator-mobile-more${moreOpen ? " is-open" : ""}`} aria-label="More creator pages" aria-hidden={!moreOpen}>
        <header><div><small>Your Clippit</small><strong>More</strong></div><button type="button" onClick={() => setMoreOpen(false)} aria-label="Close more menu"><ProductIcon name="more" /></button></header>
        <nav>{creatorMoreItems.map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={pathname.startsWith(item.href) ? "is-active" : ""}><span><ProductIcon name={item.icon} /></span><p><strong>{item.label}</strong><small>{item.copy}</small></p><ProductIcon name="arrow" /></Link>)}<button type="button" className="creator-mobile-signout" onClick={signOut} disabled={signingOut} aria-busy={signingOut}><span><ProductIcon name="logout" /></span><p><strong>Sign out</strong><small>End this session</small></p><ProductIcon name="arrow" /></button></nav>
      </section>
      <nav className={`mobile-dock${dockHidden && !moreOpen ? " is-hidden" : ""}`} aria-label="Mobile navigation">
        {mobileNavItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={isCurrent(pathname, item.href) ? "is-active" : ""}
            aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
          >
            <ProductIcon name={item.icon} />
            <span>{item.label === "Leaderboard" ? "Ranks" : item.label}</span>
          </Link>
        ))}
        <button type="button" className={moreIsCurrent || moreOpen ? "is-active" : ""} aria-expanded={moreOpen} aria-controls="creator-more-menu" onClick={() => setMoreOpen((value) => !value)}>
          <ProductIcon name="more" />
          <span>More</span>
        </button>
      </nav>
    </div>
  );
}
