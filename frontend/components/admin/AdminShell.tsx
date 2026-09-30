"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

import { authApi, clearTokens } from "@/lib/api/auth";
import { API_URL, errorMessage } from "@/lib/api/client";

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
  { href: "/admin/reports", label: "Reports", short: "Reports", icon: "shield", group: "Cases" },
  { href: "/admin/funding", label: "Funding", short: "Funding", icon: "bank", group: "Money" },
  { href: "/admin/earnings", label: "Earnings", short: "Earnings", icon: "wallet", group: "Money" },
  { href: "/admin/payouts", label: "Payouts", short: "Money", icon: "wallet", group: "Money" },
  { href: "/admin/refunds", label: "Refunds", short: "Refunds", icon: "bank", group: "Money" },
  { href: "/admin/ledger", label: "Ledger", short: "Ledger", icon: "source", group: "Money" },
  { href: "/admin/reconciliation", label: "Reconciliation", short: "Reconcile", icon: "check", group: "Money" },
  { href: "/admin/risk", label: "Risk cases", short: "Risk", icon: "eye", group: "Trust & delivery" },
  { href: "/admin/trust", label: "Trust rules", short: "Rules", icon: "shield", group: "Trust & delivery" },
  { href: "/admin/social-connections", label: "Social providers", short: "Social", icon: "link", group: "Trust & delivery" },
  { href: "/admin/webhooks", label: "Webhooks", short: "Webhooks", icon: "spark", group: "Trust & delivery" },
  { href: "/admin/notifications", label: "Notifications", short: "Delivery", icon: "bell", group: "Trust & delivery" },
  { href: "/admin/operators", label: "Operators", short: "Operators", icon: "users", group: "Access & system" },
  { href: "/admin/roles", label: "Roles & permissions", short: "Roles", icon: "shield", group: "Access & system" },
  { href: "/admin/audit", label: "Audit log", short: "Audit", icon: "brief", group: "Access & system" },
  { href: "/admin/system", label: "System health", short: "System", icon: "settings", group: "Access & system" },
  { href: "/admin/providers", label: "Provider configuration", short: "Providers", icon: "settings", group: "Access & system" },
];

// The standalone logs/diagnostics dashboard served by the API, with its own password.
export const OBSERVE_URL = `${API_URL}/observe`;

function isCurrent(pathname: string, href: string) {
  if (href === "/admin") return pathname === href;
  return pathname.startsWith(href);
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [operator, setOperator] = useState<{ full_name: string; email: string } | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pathname === "/admin/login" || pathname === "/admin/operators/accept") return;
    let active = true;
    authApi.me().then((user) => { if (active) setOperator({ full_name: user.full_name, email: user.email }); }).catch(() => undefined);
    return () => { active = false; };
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !menuRef.current?.contains(event.target as Node)) { setMenuOpen(false); setEditing(false); }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [menuOpen]);

  const displayName = operator?.full_name ?? "Operator";
  const initials = displayName.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();

  // Always ends signed out: the server call revokes the session, but a
  // network failure must never leave the operator stuck inside admin.
  const signOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try { await authApi.logout(); } catch { /* token is cleared below either way */ }
    clearTokens();
    setMenuOpen(false);
    router.replace("/admin/login");
  };

  const saveName = async (event: FormEvent) => {
    event.preventDefault();
    setSavingName(true);
    setNameError("");
    try {
      const user = await authApi.updateMe({ full_name: nameDraft.trim() });
      setOperator({ full_name: user.full_name, email: user.email });
      setEditing(false);
    } catch (err) {
      setNameError(errorMessage(err, "Couldn't save your name. Try again."));
    } finally {
      setSavingName(false);
    }
  };

  const [moreOpen, setMoreOpen] = useState(false);
  if (pathname === "/admin/login" || pathname === "/admin/operators/accept") return <>{children}</>;

  const primary = adminNavigation.filter((item) => ["/admin", "/admin/users", "/admin/submissions", "/admin/payouts"].includes(item.href));
  const moreCurrent = adminNavigation.filter((item) => !primary.includes(item)).some((item) => isCurrent(pathname, item.href));
  const groups = [...new Set(adminNavigation.map((item) => item.group))];

  return <div className="admin-shell">
    <aside className="admin-rail">
      <Link className="admin-brand" href="/admin"><Image src="/assets/clippit-mark-light.png" width={39} height={39} alt="" priority /><span><strong>Clippit</strong><small>operations</small></span></Link>
      <nav aria-label="Operations navigation">{groups.map((group) => <section key={group}><small>{group}</small>{adminNavigation.filter((item) => item.group === group).map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.label}</span></Link>)}{group === "Access & system" && <a href={OBSERVE_URL} target="_blank" rel="noreferrer"><ProductIcon name="eye" /><span>Logs &amp; diagnostics ↗</span></a>}</section>)}</nav>
      <div className="admin-operator"><span>{initials}</span><p><strong>{displayName}</strong><small>{operator?.email ?? "Administrator"}</small></p><button type="button" className="admin-operator__signout" onClick={signOut} disabled={signingOut} aria-label="Sign out" title="Sign out"><ProductIcon name="logout" /></button></div>
    </aside>

    <div className="admin-stage">
      <header className="admin-topbar"><Link href="/admin" className="admin-mobile-brand"><Image src="/assets/clippit-mark.png" width={31} height={31} alt="" /><strong>Ops</strong></Link><Link className="admin-live" href="/admin/system"><i />System health</Link><div className="admin-top-actions"><Link href="/admin/users" aria-label="Search customers"><ProductIcon name="search" /></Link><Link href="/admin/notifications" aria-label="Delivery alerts"><ProductIcon name="bell" /></Link>
        <div className="admin-account" ref={menuRef}>
          <button type="button" className="admin-account__trigger" aria-haspopup="menu" aria-expanded={menuOpen} aria-label={`Account menu for ${displayName}`} onClick={() => { setMenuOpen((open) => !open); setEditing(false); }}>{initials}</button>
          {menuOpen && <div className="admin-account__menu" role="menu">
            <header><span>{initials}</span><p><strong>{displayName}</strong><small>{operator?.email}</small><em>Administrator</em></p></header>
            {editing ? <form onSubmit={saveName}>
              <label htmlFor="admin-display-name">Display name</label>
              <input id="admin-display-name" value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} minLength={2} maxLength={120} required autoFocus />
              {nameError && <p role="alert">{nameError}</p>}
              <div><button type="button" onClick={() => setEditing(false)}>Cancel</button><button type="submit" disabled={savingName || nameDraft.trim().length < 2}>{savingName ? "Saving…" : "Save"}</button></div>
            </form> : <>
              <button type="button" role="menuitem" onClick={() => { setNameDraft(operator?.full_name ?? ""); setNameError(""); setEditing(true); }}><ProductIcon name="person" />Edit display name</button>
              <button type="button" role="menuitem" className="is-danger" onClick={signOut} disabled={signingOut}><ProductIcon name="logout" />{signingOut ? "Signing out…" : "Sign out"}</button>
            </>}
          </div>}
        </div>
      </div></header>
      <main className="admin-content">{children}</main>
    </div>

    {moreOpen && <button className="admin-more-backdrop" type="button" aria-label="Close operations menu" onClick={() => setMoreOpen(false)} />}
    <section className={`admin-more${moreOpen ? " is-open" : ""}`} aria-hidden={!moreOpen} aria-label="All operations pages"><header><div><small>Operations</small><strong>All tools</strong></div><button type="button" aria-label="Close operations menu" onClick={() => setMoreOpen(false)}><ProductIcon name="more" /></button></header><nav>{adminNavigation.filter((item) => item.href !== "/admin").map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""} onClick={() => setMoreOpen(false)}><span><ProductIcon name={item.icon} /></span><p><strong>{item.short}</strong><small>{item.group}</small></p><ProductIcon name="arrow" /></Link>)}<a href={OBSERVE_URL} target="_blank" rel="noreferrer"><span><ProductIcon name="eye" /></span><p><strong>Logs</strong><small>Diagnostics dashboard</small></p><ProductIcon name="arrow" /></a></nav></section>

    <nav className="admin-mobile-dock" aria-label="Mobile operations navigation">{primary.map((item) => <Link key={item.href} href={item.href} className={isCurrent(pathname, item.href) ? "is-active" : ""}><ProductIcon name={item.icon} /><span>{item.short}</span></Link>)}<button type="button" className={moreOpen || moreCurrent ? "is-active" : ""} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><ProductIcon name="more" /><span>More</span></button></nav>
  </div>;
}

export { adminNavigation };
