"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { money } from "@/lib/product";
import { authApi, clearTokens, storeTokens } from "@/lib/api/auth";
import {
  adminApi,
  type AdminCampaignDetail,
  type AdminCampaignRow,
  type AdminLedgerRow,
  type AdminPayoutRow,
  type AdminSubmissionDetail,
  type AdminSubmissionRow,
  type AdminUserDetail,
  type AdminUserRow,
  type AuditRow,
  type BlockedAccountRow,
  type DisputeAdminOut,
  type DisputeOut,
  type OperatorRow,
  type ProviderHealth,
  type TicketAdminOut,
  type TicketOut,
} from "@/lib/api/admin";

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = Date.now() - then;
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function untilTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = then - Date.now();
  if (diffMs <= 0) return "Overdue";
  const days = Math.floor(diffMs / 86400000);
  if (days >= 1) return `${days}d left`;
  const hours = Math.round(diffMs / 3600000);
  return `${hours}h left`;
}

function titleCase(value: string): string {
  return value.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

type Tone = "lime" | "gold" | "red" | "blue" | "ink" | "paper";
type QueueKind = "users" | "creator-verifications" | "brand-verifications" | "campaigns" | "submissions" | "support" | "disputes" | "payouts" | "refunds" | "risk";
type DetailKind = "user" | "creator-verification" | "brand-verification" | "campaign" | "submission" | "support" | "dispute" | "payout" | "refund" | "risk";

function AdminStatus({ children, tone = "paper" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`admin-status admin-status--${tone}`}><i />{children}</span>;
}

function AdminHeading({ title, copy, eyebrow, action, back }: { title: string; copy?: string; eyebrow?: string; action?: ReactNode; back?: string }) {
  return <header className="admin-heading"><div>{back && <Link className="admin-back" href={back}><ProductIcon name="chevron" />Back</Link>}{eyebrow && <span>{eyebrow}</span>}<h1>{title}</h1>{copy && <p>{copy}</p>}</div>{action}</header>;
}

function AdminButton({ children, tone = "lime", onClick, type = "button", disabled }: { children: ReactNode; tone?: "lime" | "ink" | "gold"; onClick?: () => void; type?: "button" | "submit"; disabled?: boolean }) {
  return <button className={`admin-button admin-button--${tone}`} type={type} onClick={onClick} disabled={disabled}>{children}<ProductIcon name="arrow" /></button>;
}

const queueMeta: Record<QueueKind, { title: string; copy: string; eyebrow: string; metric: string; unit: string; icon: ProductIconName; rows: Array<{ id: string; name: string; meta: string; value: string; status: string; tone: Tone; age: string; href: string }> }> = {
  users: { title: "Customers", copy: "Find a person or organisation and open the complete account record.", eyebrow: "Customer directory", metric: "12,842", unit: "active accounts", icon: "users", rows: [
    { id: "USR-18402", name: "Tobi Adeyemi", meta: "Creator · @tobioncam", value: "₦18,400 payable", status: "Active", tone: "lime", age: "2 min ago", href: "/admin/users/USR-18402" },
    { id: "ORG-00918", name: "Gbedu Records", meta: "Brand · 4 team members", value: "₦312,500 live pot", status: "Verified", tone: "blue", age: "7 min ago", href: "/admin/users/ORG-00918" },
    { id: "USR-18376", name: "Kemi Makes", meta: "Creator · @kemimakes", value: "2 open submissions", status: "Review", tone: "gold", age: "18 min ago", href: "/admin/users/USR-18376" },
    { id: "ORG-00903", name: "ChopNow Foods", meta: "Brand · individual funder", value: "No active campaign", status: "Active", tone: "paper", age: "1 hr ago", href: "/admin/users/ORG-00903" },
  ] },
  "creator-verifications": { title: "Creator verification", copy: "Review identity details, documents and face-check results.", eyebrow: "KYC queue", metric: "17", unit: "waiting for review", icon: "person", rows: [
    { id: "KYC-2041", name: "Kemi Adeola", meta: "NIN · face check complete", value: "2 documents", status: "Ready", tone: "lime", age: "6 min", href: "/admin/creators/verifications/KYC-2041" },
    { id: "KYC-2038", name: "Tobi Adeyemi", meta: "Driver's licence · Lagos", value: "Name match 96%", status: "Review", tone: "gold", age: "24 min", href: "/admin/creators/verifications/KYC-2038" },
    { id: "KYC-2034", name: "Mariam Bello", meta: "Passport · address uploaded", value: "Face check retry", status: "Correction", tone: "red", age: "1 hr", href: "/admin/creators/verifications/KYC-2034" },
  ] },
  "brand-verifications": { title: "Business verification", copy: "Check organisations, representatives and registration evidence.", eyebrow: "KYB queue", metric: "09", unit: "organisations waiting", icon: "building", rows: [
    { id: "KYB-0918", name: "Gbedu Records Ltd.", meta: "RC 1849201 · Tomi Odukoya", value: "CAC + address", status: "Ready", tone: "lime", age: "11 min", href: "/admin/brands/verifications/KYB-0918" },
    { id: "KYB-0913", name: "ChopNow Foods", meta: "BN 3304911 · sole proprietor", value: "Address mismatch", status: "Review", tone: "gold", age: "38 min", href: "/admin/brands/verifications/KYB-0913" },
    { id: "KYB-0908", name: "Pulse Streetwear", meta: "RC 2108830 · F. Danjuma", value: "Representative ID", status: "Correction", tone: "red", age: "2 hr", href: "/admin/brands/verifications/KYB-0908" },
  ] },
  campaigns: { title: "Campaign oversight", copy: "Monitor funded campaigns, pots, rates and operational holds.", eyebrow: "Campaign operations", metric: "64", unit: "live campaigns", icon: "campaigns", rows: [
    { id: "CMP-IND-2409", name: "No long thing", meta: "Indomie Nigeria · TikTok + Instagram", value: "₦687,500 remaining", status: "Live", tone: "lime", age: "Ends on pot", href: "/admin/campaigns/no-long-thing" },
    { id: "CMP-GBD-1182", name: "Main character sound", meta: "Gbedu Records · TikTok", value: "₦312,500 remaining", status: "Live", tone: "lime", age: "5d 12h", href: "/admin/campaigns/main-character-sound" },
    { id: "CMP-CHP-0410", name: "Campus chop", meta: "ChopNow Foods · Instagram", value: "₦84,000 refundable", status: "Closing", tone: "gold", age: "Closeout", href: "/admin/campaigns/campus-chop" },
  ] },
  submissions: { title: "Submission moderation", copy: "Resolve checks that need a human decision before they can earn.", eyebrow: "Evidence queue", metric: "23", unit: "need a decision", icon: "play", rows: [
    { id: "SUB-1042", name: "Main character sound", meta: "Kemi Makes · TikTok", value: "74% confidence", status: "Brand visible?", tone: "gold", age: "8 min", href: "/admin/submissions/SUB-1042" },
    { id: "SUB-1039", name: "No long thing", meta: "Tobi On Cam · Instagram", value: "61% confidence", status: "Caption check", tone: "gold", age: "21 min", href: "/admin/submissions/SUB-1039" },
    { id: "SUB-1031", name: "Send am sharp", meta: "Mariam Bello · TikTok", value: "Risk signal", status: "Escalated", tone: "red", age: "46 min", href: "/admin/submissions/SUB-1031" },
  ] },
  support: { title: "Support queue", copy: "Reply with the full account, campaign and transaction context beside you.", eyebrow: "Customer support", metric: "31", unit: "open conversations", icon: "brief", rows: [
    { id: "CLP-2914", name: "Instagram account needs reconnecting", meta: "Tobi Adeyemi · Connected accounts", value: "Creator", status: "New", tone: "lime", age: "4 min", href: "/admin/support/CLP-2914" },
    { id: "CLP-2908", name: "Funding receipt has the wrong contact", meta: "Gbedu Records · Billing", value: "Brand", status: "Waiting", tone: "gold", age: "17 min", href: "/admin/support/CLP-2908" },
    { id: "CLP-2894", name: "Why is this earning on hold?", meta: "Kemi Adeola · Earnings", value: "Creator", status: "Replied", tone: "blue", age: "42 min", href: "/admin/support/CLP-2894" },
  ] },
  disputes: { title: "Dispute queue", copy: "Make formal, evidence-backed decisions before each response deadline.", eyebrow: "Trust review", metric: "08", unit: "open disputes", icon: "shield", rows: [
    { id: "DSP-0419", name: "Earning entry VIEW-21904", meta: "Tobi Adeyemi · verified views", value: "₦18,400 on hold", status: "Evidence due", tone: "gold", age: "2d left", href: "/admin/disputes/DSP-0419" },
    { id: "DSP-0414", name: "Campaign closeout CMP-CHP-0410", meta: "ChopNow Foods · refund", value: "₦84,000", status: "Review", tone: "blue", age: "4d left", href: "/admin/disputes/DSP-0414" },
    { id: "DSP-0407", name: "Submission verdict SUB-0991", meta: "Mariam Bello · rejection", value: "No money held", status: "Ready", tone: "lime", age: "Today", href: "/admin/disputes/DSP-0407" },
  ] },
  payouts: { title: "Payout operations", copy: "Track withdrawal batches, provider transfers and account-level holds.", eyebrow: "Money movement", metric: "₦4.82M", unit: "scheduled today", icon: "wallet", rows: [
    { id: "PAY-90241", name: "Tobi Adeyemi", meta: "GTBank ••6789 · TRF-90241", value: "₦17,112 net", status: "Processing", tone: "blue", age: "3 min", href: "/admin/payouts/PAY-90241" },
    { id: "PAY-90238", name: "Kemi Adeola", meta: "Kuda ••1142 · TRF-90238", value: "₦46,500 net", status: "Held", tone: "gold", age: "12 min", href: "/admin/payouts/PAY-90238" },
    { id: "PAY-90217", name: "Mariam Bello", meta: "Access ••4108 · TRF-90217", value: "₦29,760 net", status: "Failed", tone: "red", age: "41 min", href: "/admin/payouts/PAY-90217" },
  ] },
  refunds: { title: "Refund operations", copy: "Return reconciled unused campaign money to the approved destination.", eyebrow: "Campaign closeout", metric: "₦692K", unit: "awaiting release", icon: "bank", rows: [
    { id: "RFD-1840", name: "Campus chop", meta: "ChopNow Foods · CMP-CHP-0410", value: "₦84,000", status: "Ready", tone: "lime", age: "Today", href: "/admin/refunds/RFD-1840" },
    { id: "RFD-1832", name: "Weekend reset", meta: "SoftLife Home · CMP-SFT-0093", value: "₦128,400", status: "Reconciling", tone: "blue", age: "Yesterday", href: "/admin/refunds/RFD-1832" },
    { id: "RFD-1818", name: "Back to campus", meta: "Payaza · CMP-PYZ-0331", value: "₦56,000", status: "Blocked", tone: "red", age: "2 days", href: "/admin/refunds/RFD-1818" },
  ] },
  risk: { title: "Risk cases", copy: "Investigate account, content and money signals without losing the original evidence.", eyebrow: "Trust & safety", metric: "14", unit: "active cases", icon: "eye", rows: [
    { id: "RSK-7712", name: "Sudden view velocity", meta: "SUB-1031 · @mariambello", value: "18× baseline", status: "High", tone: "red", age: "5 min", href: "/admin/risk/RSK-7712" },
    { id: "RSK-7709", name: "Payout account changed", meta: "PAY-90238 · Kemi Adeola", value: "New device", status: "Review", tone: "gold", age: "18 min", href: "/admin/risk/RSK-7709" },
    { id: "RSK-7701", name: "Duplicate identity signal", meta: "KYC-2034 · 2 accounts", value: "Face similarity 91%", status: "Review", tone: "gold", age: "1 hr", href: "/admin/risk/RSK-7701" },
  ] },
};

export function AdminLoginScreen() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const submit = (event: FormEvent) => { event.preventDefault(); setBusy(true); window.setTimeout(() => router.push("/admin"), 550); };
  return <main className="admin-login"><section><Link href="/"><Image src="/assets/clippit-mark-light.png" width={44} height={44} alt="" /><strong>Clippit</strong><span>operations</span></Link><div className="admin-login__signal"><i /><i /><i /><span><ProductIcon name="shield" /></span></div><blockquote>Customer money and decisions require an accountable operator.</blockquote><small>Restricted workspace · actions are written to the audit log</small></section><form onSubmit={submit}><AdminStatus tone="gold">Operator access</AdminStatus><h1>Sign in to operations.</h1><p>Use your company account and security key.</p><label><span>Work email</span><input type="email" defaultValue="amara@clippit.ng" required /></label><label><span>Password</span><input type="password" defaultValue="password" required /></label><div className="admin-login__key"><ProductIcon name="shield" /><span><strong>Security key</strong><small>Ready on this device</small></span><AdminStatus tone="lime">Connected</AdminStatus></div><AdminButton type="submit" disabled={busy}>{busy ? "Opening workspace" : "Continue securely"}</AdminButton><Link href="/support/tickets/new">Cannot access your operator account?</Link></form></main>;
}

export function AdminCommandCentreScreen() {
  const pulse = [
    { label: "Money moving", value: 4820000, suffix: "", format: "money" as const, tone: "lime" as Tone, href: "/admin/payouts" },
    { label: "Decisions due", value: 23, suffix: "", format: "number" as const, tone: "gold" as Tone, href: "/admin/submissions" },
    { label: "Risk holds", value: 14, suffix: "", format: "number" as const, tone: "red" as Tone, href: "/admin/risk" },
    { label: "Delivery health", value: 99.94, suffix: "%", format: "number" as const, tone: "blue" as Tone, href: "/admin/system" },
  ];
  return <div className="admin-page"><AdminHeading eyebrow="Tuesday · 22 September" title="Operations, right now" copy="The queues that need a person before customers feel the delay." action={<AdminStatus tone="lime">Live</AdminStatus>} /><section className="admin-command-pulse">{pulse.map((item) => <Link href={item.href} key={item.label} className={`is-${item.tone}`}><small>{item.label}</small><strong><AnimatedNumber value={item.value} format={item.format} decimals={item.value % 1 ? 2 : 0} suffix={item.suffix} duration={720} /></strong><span>Open queue<ProductIcon name="arrow" /></span></Link>)}</section><div className="admin-command-grid"><section className="admin-now"><header><div><h2>Needs attention</h2><p>Ordered by customer impact and deadline.</p></div><Link href="/admin/audit">Open audit log<ProductIcon name="arrow" /></Link></header>{[
    ["red", "Payout failed", "PAY-90217 · Access Bank rejected the transfer", "₦29,760", "/admin/payouts/PAY-90217"],
    ["gold", "Evidence due in 2 days", "DSP-0419 · Verified-view earning dispute", "₦18,400", "/admin/disputes/DSP-0419"],
    ["gold", "Human content decision", "SUB-1042 · Product visibility uncertain", "8 min", "/admin/submissions/SUB-1042"],
    ["blue", "Provider backlog", "Instagram readings · 184 checks delayed", "11 min", "/admin/social-connections"],
  ].map(([tone, title, copy, value, href]) => <Link href={href} key={title}><AdminStatus tone={tone as Tone}>{title}</AdminStatus><p><strong>{copy}</strong><small>Open the full evidence and history</small></p><b>{value}</b><ProductIcon name="arrow" /></Link>)}</section><aside className="admin-shift"><div className="admin-shift__clock"><i /><span><small>Current shift</small><strong>08:00–16:00</strong></span></div><h2>Amara’s desk</h2><dl><div><dt>Assigned</dt><dd>12</dd></div><div><dt>Resolved today</dt><dd>31</dd></div><div><dt>Median decision</dt><dd>8m</dd></div></dl><Link href="/admin/operators">View operators<ProductIcon name="arrow" /></Link></aside></div><section className="admin-rail-health"><header><h2>Provider rails</h2><Link href="/admin/reconciliation">Reconcile money<ProductIcon name="arrow" /></Link></header>{["Paystack funding", "Payaza transfers", "TikTok readings", "Instagram readings", "Email delivery"].map((name, index) => <div key={name}><span><i className={index === 3 ? "is-slow" : ""} />{name}</span><strong>{index === 3 ? "Delayed" : "Operational"}</strong><small>{index === 3 ? "11m behind" : `${(99.91 + index / 50).toFixed(2)}%`}</small></div>)}</section></div>;
}

export function AdminQueueScreen({ kind }: { kind: QueueKind }) {
  const config = queueMeta[kind];
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const rows = useMemo(() => config.rows.filter((row) => `${row.name} ${row.id} ${row.meta}`.toLowerCase().includes(query.toLowerCase()) && (filter === "All" || row.status === filter)), [config.rows, filter, query]);
  const statuses = ["All", ...new Set(config.rows.map((row) => row.status))];
  return <div className="admin-page"><AdminHeading eyebrow={config.eyebrow} title={config.title} copy={config.copy} action={<div className="admin-queue-count"><ProductIcon name={config.icon} /><span><strong>{config.metric}</strong><small>{config.unit}</small></span></div>} /><section className="admin-queue-tools"><label><ProductIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${config.title.toLowerCase()}`} /></label><div>{statuses.map((status) => <button type="button" className={filter === status ? "is-active" : ""} onClick={() => setFilter(status)} key={status}>{status}</button>)}</div></section><section className="admin-queue"><header><span>Case</span><span>Account or subject</span><span>Value</span><span>Status</span><span>Age</span></header>{rows.map((row) => <Link href={row.href} key={row.id}><code>{row.id}</code><p><strong>{row.name}</strong><small>{row.meta}</small></p><b>{row.value}</b><AdminStatus tone={row.tone}>{row.status}</AdminStatus><time>{row.age}</time><ProductIcon name="arrow" /></Link>)}{rows.length === 0 && <div className="admin-queue-empty"><ProductIcon name="search" /><strong>No matching cases</strong><span>Clear the search or choose another status.</span></div>}</section></div>;
}

const detailMeta: Record<DetailKind, { back: string; eyebrow: string; title: string; subject: string; status: string; tone: Tone; amount: string; summary: string; facts: Array<[string, string]>; events: Array<[string, string, string]>; primary: string; secondary: string; image?: string }> = {
  user: { back: "/admin/users", eyebrow: "Customer account", title: "Tobi Adeyemi", subject: "USR-18402 · Creator · @tobioncam", status: "Active", tone: "lime", amount: "₦18,400", summary: "Verified creator with two connected platforms and one open support conversation.", facts: [["Joined", "14 May 2026"], ["Email", "tobi@example.com"], ["Phone", "+234 ••• ••184"], ["Last active", "2 minutes ago"], ["Verification", "Approved"], ["Risk level", "Low"]], events: [["Today · 10:18", "Opened support ticket CLP-2914", "Connected Instagram account needs attention."], ["20 Sep · 15:07", "Withdrawal settled", "PAY-89912 · ₦42,780 landed in GTBank."], ["19 Sep · 19:41", "Clip approved", "SUB-1011 began earning from verified views."]], primary: "Add account note", secondary: "Restrict account" },
  "creator-verification": { back: "/admin/creators/verifications", eyebrow: "Creator KYC review", title: "Tobi Adeyemi", subject: "KYC-2038 · Submitted 24 minutes ago", status: "Needs review", tone: "gold", amount: "96%", summary: "The legal name matches strongly. Confirm the licence crop and address before approval.", facts: [["Document", "Driver's licence"], ["Document ID", "•••• 8021"], ["Date of birth", "12 April 1998"], ["Address", "Yaba, Lagos"], ["Face match", "98%"], ["Name match", "96%"]], events: [["10:02", "Automated checks completed", "Face and liveness checks passed."], ["09:59", "Identity document uploaded", "Front image and extracted fields stored."], ["09:54", "Identity details submitted", "Phone and address confirmed."]], primary: "Approve identity", secondary: "Request correction" },
  "brand-verification": { back: "/admin/brands/verifications", eyebrow: "Business KYB review", title: "Gbedu Records Ltd.", subject: "KYB-0918 · RC 1849201", status: "Ready", tone: "lime", amount: "100%", summary: "Registration, address and authorised representative checks are complete.", facts: [["Organisation", "Private company"], ["Registration", "RC 1849201"], ["Representative", "Tomi Odukoya"], ["Role", "Director"], ["Address", "Lekki, Lagos"], ["Registry match", "Confirmed"]], events: [["09:48", "Registration matched", "Company name and status matched the registry result."], ["09:44", "Representative approved", "Identity and authority evidence passed."], ["09:37", "Documents uploaded", "CAC certificate and utility bill received."]], primary: "Approve business", secondary: "Request correction" },
  campaign: { back: "/admin/campaigns", eyebrow: "Campaign operations", title: "No long thing", subject: "CMP-IND-2409 · Indomie Nigeria", status: "Live", tone: "lime", amount: "₦687,500", summary: "The campaign stays open until its creator pot is exhausted. No fixed closing date is set.", facts: [["Creator pot", "₦1,000,000"], ["Clippit fee", "₦150,000"], ["Rate", "₦500 / 1K views"], ["Creator cap", "₦75,000"], ["Approved clips", "18"], ["Billable views", "625,000"]], events: [["10:14", "Two clips approved", "₦9,200 reserved from the creator pot."], ["09:31", "Instagram reading completed", "84,021 new eligible views found."], ["Yesterday", "Campaign funding cleared", "Provider reference CHG-804118 reconciled."]], primary: "Pause campaign", secondary: "Open brand workspace" },
  submission: { back: "/admin/submissions", eyebrow: "Evidence review", title: "Main character sound", subject: "SUB-1042 · Kemi Makes · TikTok", status: "Human decision", tone: "gold", amount: "74%", summary: "The product appears at 00:11, but another object covers part of the brand mark.", facts: [["Post", "tiktok.com/@kemimakes/…"], ["Duration", "00:24"], ["Published", "22 Sep · 09:48"], ["Account", "Connected"], ["Caption", "Passed"], ["Audio", "Passed"]], events: [["10:11", "Human review requested", "Product visibility confidence fell below 80%."], ["10:09", "Requirement checks completed", "Three passed; one uncertain."], ["10:06", "Public post verified", "Connected account and URL matched."]], primary: "Approve submission", secondary: "Request correction", image: "/assets/photos/creator-studio-pexels-8359963.jpg" },
  support: { back: "/admin/support", eyebrow: "Support workspace", title: "Instagram account needs reconnecting", subject: "CLP-2914 · Tobi Adeyemi", status: "New", tone: "lime", amount: "4m", summary: "The creator can sign in, but the Instagram connection expired during a scheduled view reading.", facts: [["Category", "Connected accounts"], ["Account", "@tobioncam"], ["Browser", "Chrome · Android"], ["Last connection", "18 Sep 2026"], ["Related campaign", "No long thing"], ["Assigned", "Unassigned"]], events: [["10:18", "Customer message", "Instagram keeps taking me back to connect."], ["10:17", "Diagnostics attached", "Token expired; reconnect attempt did not complete."], ["10:14", "Ticket created", "Account and device context attached automatically."]], primary: "Send reply", secondary: "Escalate to engineering" },
  dispute: { back: "/admin/disputes", eyebrow: "Formal dispute", title: "Earning entry VIEW-21904", subject: "DSP-0419 · Tobi Adeyemi", status: "Evidence due", tone: "gold", amount: "₦18,400", summary: "The customer disputes the verified-view total attached to an approved Indomie clip.", facts: [["Opened", "21 Sep · 18:40"], ["Reply deadline", "25 Sep"], ["Money held", "₦18,400"], ["Campaign", "No long thing"], ["Reading", "36,800 views"], ["Assigned", "Amara A."]], events: [["Today · 14:12", "Original insight requested", "Customer has two days to add the platform screen."], ["Today · 10:06", "Review started", "Earning and platform records locked to the case."], ["21 Sep · 18:40", "Dispute received", "Claim and two evidence files stored."]], primary: "Record decision", secondary: "Request evidence" },
  payout: { back: "/admin/payouts", eyebrow: "Payout investigation", title: "Tobi Adeyemi", subject: "PAY-90241 · TRF-90241", status: "Processing", tone: "blue", amount: "₦17,112", summary: "A ₦18,400 withdrawal less the 7% creator withdrawal fee is processing to GTBank.", facts: [["Gross", "₦18,400"], ["Withdrawal fee", "₦1,288"], ["Net transfer", "₦17,112"], ["Bank", "GTBank ••6789"], ["Provider", "Payaza"], ["Risk check", "Passed"]], events: [["10:21", "Transfer accepted", "Provider returned processing status."], ["10:20", "Ledger posted", "Gross, fee and net entries balanced."], ["10:19", "Withdrawal confirmed", "Customer confirmed destination account."]], primary: "Refresh provider status", secondary: "Place payout hold" },
  refund: { back: "/admin/refunds", eyebrow: "Refund investigation", title: "Campus chop", subject: "RFD-1840 · CMP-CHP-0410", status: "Ready", tone: "lime", amount: "₦84,000", summary: "The unused creator-pot balance is reconciled and ready for the original funding destination.", facts: [["Original pot", "₦500,000"], ["Creator earnings", "₦416,000"], ["Refundable", "₦84,000"], ["Destination", "Visa ••4402"], ["Provider", "Paystack"], ["Closeout", "Complete"]], events: [["09:52", "Refund quote locked", "Amount and destination approved."], ["09:49", "Campaign reconciled", "All creator allocations reached a final state."], ["Yesterday", "Campaign closed", "Brand requested closeout after the final review."]], primary: "Release refund", secondary: "Return to reconciliation" },
  risk: { back: "/admin/risk", eyebrow: "Risk investigation", title: "Sudden view velocity", subject: "RSK-7712 · SUB-1031", status: "High risk", tone: "red", amount: "18×", summary: "The public view count accelerated far beyond the account and campaign baseline within nine minutes.", facts: [["Account", "@mariambello"], ["Campaign", "Send am sharp"], ["Views added", "92,411"], ["Window", "9 minutes"], ["Baseline", "5,100 / hour"], ["Money held", "₦46,205"]], events: [["10:24", "Earning hold applied", "New allocation remains unavailable."], ["10:23", "Velocity rule triggered", "18× account baseline and 11× campaign median."], ["10:15", "Platform reading received", "Public view count increased by 92,411."]], primary: "Clear risk hold", secondary: "Restrict account" },
};

export function AdminDetailScreen({ kind, id }: { kind: DetailKind; id: string }) {
  const config = detailMeta[kind];
  const [decision, setDecision] = useState("");
  return <div className="admin-page"><AdminHeading back={config.back} eyebrow={`${config.eyebrow} · ${id}`} title={config.title} copy={config.subject} action={<AdminStatus tone={config.tone}>{config.status}</AdminStatus>} />{decision && <div className="admin-decision-saved" role="status"><ProductIcon name="check" /><span><strong>{decision}</strong><small>Recorded with your operator ID and the current evidence version.</small></span><button onClick={() => setDecision("")} type="button">Dismiss</button></div>}<div className="admin-case-layout"><section className="admin-docket"><header><div><small>Decision docket</small><strong>{config.amount}</strong></div><p>{config.summary}</p></header>{config.image && <div className="admin-evidence-image"><Image src={config.image} alt="Submission evidence" fill sizes="(max-width: 760px) 100vw, 45vw" /><button type="button" aria-label="Play evidence"><ProductIcon name="play" /></button><span>Evidence frame · 00:11</span></div>}<dl>{config.facts.map(([term, value]) => <div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl><footer><ProductIcon name="shield" /><span>Evidence snapshot locked when this case opened.</span></footer></section><aside className="admin-case-side"><section className="admin-case-timeline"><header><h2>Case history</h2><AdminStatus tone="paper">Immutable</AdminStatus></header>{config.events.map(([time, title, copy], index) => <article key={time + title} className={index === 0 ? "is-current" : ""}><span>{index + 1}</span><div><small>{time}</small><strong>{title}</strong><p>{copy}</p></div></article>)}</section><section className="admin-decision-box"><h2>Operator action</h2><label><span>Internal note</span><textarea rows={4} placeholder="Add the reason and evidence used for this action." /></label><AdminButton onClick={() => setDecision(config.primary)}>{config.primary}</AdminButton><AdminButton tone="gold" onClick={() => setDecision(config.secondary)}>{config.secondary}</AdminButton></section></aside></div></div>;
}

export function AdminLedgerScreen() {
  const [type, setType] = useState("All entries");
  const rows = [["LED-982104", "Campaign funding", "Gbedu Records", "+₦1,150,000", "Cleared"], ["LED-982103", "Creator allocation", "Tobi Adeyemi", "-₦18,400", "Held"], ["LED-982102", "Withdrawal fee", "PAY-90241", "+₦1,288", "Posted"], ["LED-982101", "Net payout", "GTBank ••6789", "-₦17,112", "Processing"], ["LED-982098", "Campaign refund", "Campus chop", "-₦84,000", "Ready"]];
  return <div className="admin-page"><AdminHeading eyebrow="Finance ledger" title="Every naira has two sides" copy="Search the immutable money record by reference, account or campaign." action={<AdminStatus tone="lime">Balanced</AdminStatus>} /><section className="admin-ledger-balance"><div><small>Ledger position</small><strong><AnimatedNumber value={28410300} format="money" /></strong></div><dl><div><dt>Creator liabilities</dt><dd>₦8.41M</dd></div><div><dt>Campaign pots</dt><dd>₦17.92M</dd></div><div><dt>Refund liabilities</dt><dd>₦2.08M</dd></div></dl><span><i />Difference ₦0.00</span></section><section className="admin-ledger-tools"><label><ProductIcon name="search" /><input placeholder="Reference, customer or campaign" /></label><select value={type} onChange={(event) => setType(event.target.value)}><option>All entries</option><option>Funding</option><option>Allocations</option><option>Payouts</option><option>Refunds</option></select><button type="button"><ProductIcon name="brief" />Export ledger</button></section><section className="admin-ledger-table"><header><span>Reference</span><span>Entry</span><span>Account</span><span>Amount</span><span>Status</span></header>{rows.map((row) => <article key={row[0]}><code>{row[0]}</code><strong>{row[1]}</strong><span>{row[2]}</span><b>{row[3]}</b><AdminStatus tone={row[4] === "Held" ? "gold" : row[4] === "Processing" ? "blue" : "lime"}>{row[4]}</AdminStatus></article>)}</section></div>;
}

export function AdminReconciliationScreen() {
  const [run, setRun] = useState(false);
  return <div className="admin-page"><AdminHeading eyebrow="Provider reconciliation" title="Books meet provider reality" copy="Compare Clippit entries with funding, transfer and refund records." action={<AdminButton onClick={() => setRun(true)}>{run ? "Reconciliation queued" : "Run reconciliation"}</AdminButton>} /><section className="admin-recon-board"><div className="admin-recon-sides"><article><span><ProductIcon name="source" /></span><small>Clippit ledger</small><strong>₦28,410,300</strong><p>2,841 entries through 10:30 WAT</p></article><div><i /><i /><i /><strong>₦0</strong><small>unexplained difference</small></div><article><span><ProductIcon name="bank" /></span><small>Provider records</small><strong>₦28,410,300</strong><p>Paystack + Payaza through 10:28 WAT</p></article></div><section>{[["Paystack collections", "1,204", "₦19.82M", "Matched"], ["Payaza transfers", "884", "₦6.51M", "3 pending"], ["Refund instructions", "42", "₦2.08M", "Matched"]].map((row) => <article key={row[0]}><p><strong>{row[0]}</strong><small>{row[1]} records</small></p><b>{row[2]}</b><AdminStatus tone={row[3] === "Matched" ? "lime" : "gold"}>{row[3]}</AdminStatus><button type="button">Inspect<ProductIcon name="arrow" /></button></article>)}</section></section></div>;
}

const deliveryCards = {
  social: [["TikTok", "Readings current", "99.97%", "128 ms", "lime"], ["Instagram", "184 checks delayed", "98.41%", "11 min", "gold"], ["YouTube", "Readings current", "99.92%", "241 ms", "lime"]],
  webhooks: [["Paystack", "Funding events", "99.99%", "82 ms", "lime"], ["Payaza", "Transfer events", "99.94%", "190 ms", "lime"], ["Identity provider", "Verification events", "99.12%", "3 retries", "gold"]],
  notifications: [["Email", "Transactional", "99.81%", "2.1 s", "lime"], ["Push", "Workspace alerts", "98.94%", "38 queued", "gold"], ["SMS", "Security codes", "99.98%", "4.2 s", "lime"]],
} as const;

export function AdminDeliveryScreen({ kind }: { kind: keyof typeof deliveryCards }) {
  const titles = { social: ["Social provider health", "Platform connections, permissions and view-reading freshness."], webhooks: ["Webhook delivery", "Provider events, retries and dead-letter activity."], notifications: ["Notification delivery", "Email, push and SMS delivery across customer journeys."] } as const;
  const [selected, setSelected] = useState(0);
  return <div className="admin-page"><AdminHeading eyebrow="Trust & delivery" title={titles[kind][0]} copy={titles[kind][1]} action={<AdminStatus tone="lime">Monitoring</AdminStatus>} /><section className="admin-provider-grid">{deliveryCards[kind].map((item, index) => <button type="button" key={item[0]} className={selected === index ? "is-selected" : ""} onClick={() => setSelected(index)}><span><ProductIcon name={kind === "social" ? "link" : kind === "webhooks" ? "spark" : "bell"} /></span><p><strong>{item[0]}</strong><small>{item[1]}</small></p><b>{item[2]}</b><AdminStatus tone={item[4] as Tone}>{item[4] === "gold" ? "Attention" : "Healthy"}</AdminStatus></button>)}</section><section className="admin-delivery-detail"><header><div><h2>{deliveryCards[kind][selected][0]} activity</h2><p>Last 60 minutes · live delivery window</p></div><strong>{deliveryCards[kind][selected][3]}</strong></header><div className="admin-signal-chart">{Array.from({ length: 24 }, (_, index) => <i key={index} style={{ height: `${22 + ((index * 17 + selected * 11) % 68)}%` }} />)}</div><footer><span><i />Successful</span><span><i />Retried</span><Link href="/admin/audit">View related audit events<ProductIcon name="arrow" /></Link></footer></section><section className="admin-delivery-log">{["Event accepted", "Customer record updated", "Delivery acknowledgement stored", "Retry window checked"].map((item, index) => <article key={item}><time>{`10:${28 - index * 3}`}</time><span><i className={index === 2 && selected === 1 ? "is-warn" : ""} /></span><p><strong>{item}</strong><small>{kind.toUpperCase()}-{88410 - index}</small></p><b>{index === 2 && selected === 1 ? "Retried" : "Complete"}</b></article>)}</section></div>;
}

export function AdminOperatorsScreen() {
  const operators = [["AA", "Amara A.", "Operations lead", "Online", "12 assigned"], ["KO", "Kunle O.", "Trust reviewer", "Online", "7 assigned"], ["NE", "Nneka E.", "Support specialist", "Away", "9 assigned"], ["IF", "Ife F.", "Finance operator", "Online", "4 assigned"]];
  return <div className="admin-page"><AdminHeading eyebrow="Operator access" title="Operators" copy="People with access to customer decisions, money and system controls." action={<Link className="admin-button admin-button--lime" href="/admin/operators/invite">Invite operator<ProductIcon name="arrow" /></Link>} /><section className="admin-operator-board"><header><span>Operator</span><span>Role</span><span>Presence</span><span>Workload</span></header>{operators.map((row) => <article key={row[1]}><i>{row[0]}</i><p><strong>{row[1]}</strong><small>Last active {row[3] === "Online" ? "now" : "18 min ago"}</small></p><b>{row[2]}</b><AdminStatus tone={row[3] === "Online" ? "lime" : "gold"}>{row[3]}</AdminStatus><span>{row[4]}</span><button type="button"><ProductIcon name="more" /></button></article>)}</section></div>;
}

export function AdminInviteOperatorScreen() {
  const [sent, setSent] = useState(false);
  const [role, setRole] = useState("Support specialist");
  if (sent) return <div className="admin-page admin-invite-success"><div><ProductIcon name="check" /><i /><i /></div><AdminStatus tone="lime">Invitation sent</AdminStatus><h1>Chidi can join operations.</h1><p>The invite expires in 48 hours. Access begins only after company sign-in and a registered security key.</p><Link className="admin-button admin-button--lime" href="/admin/operators">Back to operators<ProductIcon name="arrow" /></Link></div>;
  return <div className="admin-page"><AdminHeading back="/admin/operators" eyebrow="Operator access" title="Invite an operator" copy="Assign only the role needed for their work." /><form className="admin-invite-form" onSubmit={(event) => { event.preventDefault(); setSent(true); }}><section><label><span>Work email</span><input type="email" defaultValue="chidi@clippit.ng" required /></label><label><span>Display name</span><input defaultValue="Chidi N." required /></label><fieldset><legend>Role</legend>{["Support specialist", "Trust reviewer", "Finance operator", "Operations lead"].map((item) => <label className={role === item ? "is-selected" : ""} key={item}><input type="radio" checked={role === item} onChange={() => setRole(item)} /><span><ProductIcon name={item === "Finance operator" ? "wallet" : item === "Trust reviewer" ? "shield" : item === "Operations lead" ? "settings" : "brief"} /></span><p><strong>{item}</strong><small>{item === "Support specialist" ? "Tickets and customer records" : item === "Trust reviewer" ? "Verification, submissions, disputes and risk" : item === "Finance operator" ? "Payouts, refunds, ledger and reconciliation" : "All operations permissions"}</small></p></label>)}</fieldset><AdminButton type="submit">Send secure invitation</AdminButton></section><aside><ProductIcon name="shield" /><h2>Access starts safely</h2><ol><li>Company email is verified</li><li>Security key is registered</li><li>Role permissions are accepted</li><li>First sign-in is written to audit</li></ol><Link href="/admin/roles">Review role permissions<ProductIcon name="arrow" /></Link></aside></form></div>;
}

export function AdminRolesScreen() {
  const roles = ["Support specialist", "Trust reviewer", "Finance operator", "Operations lead"];
  const permissions = ["Customer profiles", "Verification evidence", "Campaign decisions", "Support tickets", "Money operations", "Risk controls", "Operator access", "System configuration"];
  return <div className="admin-page"><AdminHeading eyebrow="Access control" title="Roles & permissions" copy="A readable map of what each operator role can see and change." action={<AdminStatus tone="blue">4 roles</AdminStatus>} /><section className="admin-permission-matrix"><header><span>Permission</span>{roles.map((role) => <strong key={role}>{role}</strong>)}</header>{permissions.map((permission, row) => <article key={permission}><strong>{permission}</strong>{roles.map((role, col) => { const allowed = col === 3 || col === 0 && [0, 3].includes(row) || col === 1 && [0, 1, 2, 3, 5].includes(row) || col === 2 && [0, 4].includes(row); return <span className={allowed ? "is-allowed" : ""} key={role}>{allowed ? <ProductIcon name="check" /> : "—"}</span>; })}</article>)}</section><aside className="admin-role-note"><ProductIcon name="shield" /><p><strong>Permission changes require a second operations lead.</strong><span>No operator can approve their own access change.</span></p><button type="button">Request a role change<ProductIcon name="arrow" /></button></aside></div>;
}

export function AdminAuditScreen() {
  const events = [["10:31:42", "Amara A.", "Opened payout investigation", "PAY-90241", "Read"], ["10:29:08", "System", "Applied risk hold", "RSK-7712", "Automatic"], ["10:24:51", "Kunle O.", "Requested identity correction", "KYC-2034", "Write"], ["10:20:14", "Finance worker", "Posted payout ledger entries", "PAY-90241", "Automatic"], ["10:14:02", "Nneka E.", "Replied to support ticket", "CLP-2894", "Write"]];
  return <div className="admin-page"><AdminHeading eyebrow="Immutable record" title="Audit log" copy="Who did what, when, and which evidence version they saw." action={<button className="admin-export" type="button"><ProductIcon name="brief" />Export signed log</button>} /><section className="admin-audit-filters"><label><ProductIcon name="search" /><input placeholder="Operator, action or reference" /></label><button type="button"><ProductIcon name="calendar" />22 Sep 2026</button><button type="button"><ProductIcon name="filter" />All actions</button></section><section className="admin-audit-stream">{events.map((event, index) => <article key={event[0]}><time>{event[0]}<small>WAT</small></time><span><i /></span><p><strong>{event[2]}</strong><small>{event[1]} · {event[3]}</small></p><AdminStatus tone={event[4] === "Write" ? "gold" : event[4] === "Automatic" ? "blue" : "paper"}>{event[4]}</AdminStatus><button type="button" aria-label="Open event"><ProductIcon name="arrow" /></button>{index === 1 && <div><code>SHA-256 8f32…901c</code><span>Evidence version EV-10942</span></div>}</article>)}</section></div>;
}

export function AdminSystemScreen() {
  const [maintenance, setMaintenance] = useState(false);
  const services = [["API gateway", "Operational", "48 ms", "99.99%"], ["Database", "Operational", "12 ms", "99.98%"], ["Queue workers", "Operational", "184 jobs", "99.94%"], ["Media checks", "Operational", "38 running", "99.91%"], ["Receipt renderer", "Operational", "7 queued", "100%"], ["Object storage", "Operational", "21 ms", "99.99%"]];
  return <div className="admin-page"><AdminHeading eyebrow="Runtime controls" title="System health" copy="The services customers rely on, their current load and safe operational controls." action={<AdminStatus tone="lime">All systems operational</AdminStatus>} /><section className="admin-system-grid">{services.map((service, index) => <article key={service[0]}><header><span><i /></span><AdminStatus tone="lime">{service[1]}</AdminStatus></header><h2>{service[0]}</h2><dl><div><dt>{index === 2 || index === 3 || index === 4 ? "Current work" : "Latency"}</dt><dd>{service[2]}</dd></div><div><dt>30-day availability</dt><dd>{service[3]}</dd></div></dl><div>{Array.from({ length: 18 }, (_, bar) => <i key={bar} style={{ height: `${24 + ((bar * 13 + index * 19) % 65)}%` }} />)}</div></article>)}</section><section className="admin-runtime-controls"><header><div><h2>Runtime controls</h2><p>Changes are audited and require a typed confirmation in production.</p></div><ProductIcon name="settings" /></header><article><p><strong>Customer maintenance notice</strong><small>Show a status notice without disabling the product.</small></p><label><input type="checkbox" checked={maintenance} onChange={() => setMaintenance((value) => !value)} /><i /></label></article><article><p><strong>New campaign funding</strong><small>Funding is currently available.</small></p><AdminStatus tone="lime">Enabled</AdminStatus></article><article><p><strong>Creator withdrawals</strong><small>Withdrawal requests are currently available.</small></p><AdminStatus tone="lime">Enabled</AdminStatus></article>{maintenance && <div role="status"><ProductIcon name="check" />Maintenance notice will appear after an operations lead approves it.</div>}</section></div>;
}

const adminReviewRoutes = [
  ["Access", "/admin/login", "Operator sign in"], ["Access", "/admin", "Command centre"],
  ["Customers", "/admin/users", "Customer directory"], ["Customers", "/admin/users/USR-18402", "Customer account"],
  ["Customers", "/admin/creators/verifications", "Creator KYC queue"], ["Customers", "/admin/creators/verifications/KYC-2038", "Creator KYC review"],
  ["Customers", "/admin/brands/verifications", "Business KYB queue"], ["Customers", "/admin/brands/verifications/KYB-0918", "Business KYB review"],
  ["Content", "/admin/campaigns", "Campaign oversight"], ["Content", "/admin/campaigns/no-long-thing", "Campaign operations"],
  ["Content", "/admin/submissions", "Submission queue"], ["Content", "/admin/submissions/SUB-1042", "Evidence review"],
  ["Cases", "/admin/support", "Support queue"], ["Cases", "/admin/support/CLP-2914", "Support workspace"],
  ["Cases", "/admin/disputes", "Dispute queue"], ["Cases", "/admin/disputes/DSP-0419", "Dispute workspace"],
  ["Money", "/admin/payouts", "Payout operations"], ["Money", "/admin/payouts/PAY-90241", "Payout investigation"],
  ["Money", "/admin/refunds", "Refund operations"], ["Money", "/admin/refunds/RFD-1840", "Refund investigation"],
  ["Money", "/admin/ledger", "Finance ledger"], ["Money", "/admin/reconciliation", "Provider reconciliation"],
  ["Trust & delivery", "/admin/risk", "Risk queue"], ["Trust & delivery", "/admin/risk/RSK-7712", "Risk investigation"],
  ["Trust & delivery", "/admin/social-connections", "Social provider health"], ["Trust & delivery", "/admin/webhooks", "Webhook monitor"],
  ["Trust & delivery", "/admin/notifications", "Notification monitor"], ["System", "/admin/operators", "Operator directory"],
  ["System", "/admin/operators/invite", "Invite operator"], ["System", "/admin/roles", "Roles & permissions"],
  ["System", "/admin/audit", "Audit log"], ["System", "/admin/system", "System health"],
] as const;

export function AdminReviewIndexScreen() {
  const groups = ["Access", "Customers", "Content", "Cases", "Money", "Trust & delivery", "System"] as const;
  return <div className="admin-page"><AdminHeading eyebrow="Development review" title="32 operations screens" copy="The final locked admin and operations set, grouped by the work each screen supports." action={<AdminStatus tone="lime">32 / 32 built</AdminStatus>} /><section className="admin-review-index">{groups.map((group) => <section key={group}><header><h2>{group}</h2><span>{adminReviewRoutes.filter((route) => route[0] === group).length}</span></header><div>{adminReviewRoutes.filter((route) => route[0] === group).map((route, index) => <Link href={route[1]} key={route[1]}><i>{String(index + 1).padStart(2, "0")}</i><p><strong>{route[2]}</strong><small>{route[1]}</small></p><ProductIcon name="arrow" /></Link>)}</div></section>)}</section></div>;
}
