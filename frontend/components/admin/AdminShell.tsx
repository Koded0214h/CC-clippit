"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

type AdminNavItem = { href: string; label: string; short: string; icon: ProductIconName; group: string };

const adminNavigation: AdminNavItem[] = [
  { href: "/admin", label: "Command centre", short: "Home", icon: "home", group: "Workspace" },
  { href: "/admin/users", label: "Customers", short: "Customers", icon: "users", group: "Customers" },
  { href: "/admin/creators/verifications", label: "Creator verification", short: "KYC", icon: "person", group: "Customers" },
  { href: "/admin/brands/verifications", label: "Business verification", short: "KYB", icon: "building", group: "Customers" },
  { href: "/admin/campaigns", label: "Campaigns", short: "Campaigns", icon: "campaigns", group: "Content" },
  { href: "/admin/submissions", label: "Submissions", short: "Reviews", icon: "play", group: "Content" },
  { href: "/admin/support", label: "Support", short: "Support", icon: "brief", group: "Cases" },
  { href: "/admin/disputes", label: "Disputes", short: "Disputes", icon: "shield", group: "Cases" },
  { href: "/admin/payouts", label: "Payouts", short: "Money", icon: "wallet", group: "Money" },
  { href: "/admin/refunds", label: "Refunds", short: "Refunds", icon: "bank", group: "Money" },
  { href: "/admin/ledger", label: "Ledger", short: "Ledger", icon: "source", group: "Money" },
  { href: "/admin/reconciliation", label: "Reconciliation", short: "Reconcile", icon: "check", group: "Money" },
  { href: "/admin/risk", label: "Risk cases", short: "Risk", icon: "eye", group: "Trust & delivery" },
  { href: "/admin/social-connections", label: "Social providers", short: "Social", icon: "link", group: "Trust & delivery" },
  { href: "/admin/webhooks", label: "Webhooks", short: "Webhooks", icon: "spark", group: "Trust & delivery" },
  { href: "/admin/notifications", label: "Notifications", short: "Delivery", icon: "bell", group: "Trust & delivery" },
  { href: "/admin/operators", label: "Operators", short: "Operators", icon: "users", group: "Access & system" },
  { href: "/admin/roles", label: "Roles & permissions", short: "Roles", icon: "shield", group: "Access & system" },
  { href: "/admin/audit", label: "Audit log", short: "Audit", icon: "brief", group: "Access & system" },
  { href: "/admin/system", label: "System health", short: "System", icon: "settings", group: "Access & system" },
];

function isCurrent(pathname: string, href: string) {
  if (href === "/admin") return pathname === href;
  return pathname.startsWith(href);
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  if (pathname === "/admin/login") return <>{children}</>;

  const primary = adminNavigation.filter((item) => ["/admin", "/admin/users", "/admin/submissions", "/admin/payouts"].includes(item.href));
  const moreCurrent = adminNavigation.filter((item) => !primary.includes(item)).some((item) => isCurrent(pathname, item.href));
  const groups = [...new Set(adminNavigation.map((item) => item.group))];

  return <div className="admin-shell">
    <aside className="admin-rail">
      <Link className="admin-brand" href="/admin"><Image src="/assets/clippit-mark-light.png" width={39} height={39} alt="" priority /><span><strong>Clippit</strong><small>operations</small></span></Link>
      <nav aria-label="Operations navigation">{groups.map((group) => <section key={group}><small>{group}</small>{adminNavigation.filter((item) => item.group === group).map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.label}</span>{["/admin/creators/verifications", "/admin/submissions", "/admin/disputes", "/admin/risk"].includes(item.href) && <b />}</Link>)}</section>)}</nav>
      <div className="admin-operator"><span>AA</span><p><strong>Amara A.</strong><small>Operations lead</small></p><ProductIcon name="chevron" /></div>
    </aside>

    <div className="admin-stage">
      <header className="admin-topbar"><Link href="/admin" className="admin-mobile-brand"><Image src="/assets/clippit-mark.png" width={31} height={31} alt="" /><strong>Ops</strong></Link><div className="admin-live"><i />All money rails operational</div><div className="admin-top-actions"><button type="button" aria-label="Search operations"><ProductIcon name="search" /></button><Link href="/admin/notifications" aria-label="Delivery alerts"><ProductIcon name="bell" /><b>3</b></Link><span>AA</span></div></header>
      <main className="admin-content">{children}</main>
    </div>

    {moreOpen && <button className="admin-more-backdrop" type="button" aria-label="Close operations menu" onClick={() => setMoreOpen(false)} />}
    <section className={`admin-more${moreOpen ? " is-open" : ""}`} aria-hidden={!moreOpen} aria-label="All operations pages"><header><div><small>Operations</small><strong>All tools</strong></div><button type="button" aria-label="Close operations menu" onClick={() => setMoreOpen(false)}><ProductIcon name="more" /></button></header><nav>{adminNavigation.filter((item) => item.href !== "/admin").map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""} onClick={() => setMoreOpen(false)}><span><ProductIcon name={item.icon} /></span><p><strong>{item.short}</strong><small>{item.group}</small></p><ProductIcon name="arrow" /></Link>)}</nav></section>

    <nav className="admin-mobile-dock" aria-label="Mobile operations navigation">{primary.map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.short}</span></Link>)}<button type="button" className={moreOpen || moreCurrent ? "is-active" : ""} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><ProductIcon name="more" /><span>More</span></button></nav>
  </div>;
}

export { adminNavigation };
