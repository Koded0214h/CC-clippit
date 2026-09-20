"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

const navItems: Array<{ href: string; label: string; icon: ProductIconName }> = [
  { href: "/dashboard", label: "Overview", icon: "home" },
  { href: "/dashboard/campaigns", label: "Campaigns", icon: "campaigns" },
  { href: "/dashboard/clips", label: "My clips", icon: "play" },
  { href: "/dashboard/earnings", label: "Earnings", icon: "wallet" },
  { href: "/dashboard/leaderboard", label: "Leaderboard", icon: "trophy" },
  { href: "/dashboard/settings", label: "Settings", icon: "settings" },
];

const mobileNavItems = navItems.filter((item) => item.label !== "Leaderboard");

function isCurrent(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  if (href === "/dashboard/settings" && pathname === "/dashboard/accounts") return true;
  return pathname.startsWith(href);
}

export function ProductShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

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
        <div className="studio-rail__bottom">
          <div className="trust-pulse">
            <ProductIcon name="shield" />
            <span>
              Platform views
              <strong>Verified</strong>
            </span>
          </div>
          <Link className="rail-profile" href="/dashboard/settings">
            <span className="avatar">TO</span>
            <span>
              <strong>Tobi On Cam</strong>
              <small>Creator</small>
            </span>
            <ProductIcon name="chevron" />
          </Link>
        </div>
      </aside>

      <div className="product-stage">
        <header className="product-topbar">
          <Link className="mobile-brand" href="/dashboard" aria-label="Clippit overview">
            <Image src="/assets/clippit-mark.png" width={32} height={32} alt="" priority />
            <strong>Clippit</strong>
          </Link>
          <div className="topbar-proof">
            <span />
            Views last checked 2 min ago
          </div>
          <div className="topbar-actions">
            <Link className="wallet-pill" href="/dashboard/earnings">
              <ProductIcon name="wallet" />
              <span>Payable</span>
              <strong>₦18,400</strong>
            </Link>
            <button className="icon-button" type="button" aria-label="Notifications">
              <ProductIcon name="bell" />
              <i />
            </button>
            <Link className="topbar-avatar" href="/dashboard/settings" aria-label="Open profile settings">
              TO
            </Link>
          </div>
        </header>
        <main className="product-content">{children}</main>
      </div>

      <nav className="mobile-dock" aria-label="Mobile navigation">
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
      </nav>
    </div>
  );
}
