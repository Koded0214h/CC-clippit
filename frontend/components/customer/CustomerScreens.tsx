"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfileAvatar, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { money } from "@/lib/product";

const CREATOR_PROFILE: StoredProfile = {
  name: "Tobi On Cam",
  bio: "Comedy, food and everyday Lagos stories.",
  photo: "",
};

function ScreenHead({ title, copy, back, action }: { title: string; copy: string; back?: string; action?: ReactNode }) {
  return <header className="customer-head">
    <div>{back && <Link className="customer-back" href={back}><ProductIcon name="chevron" />Back</Link>}<h1>{title}</h1><p>{copy}</p></div>
    {action}
  </header>;
}

type Notice = {
  id: number;
  kind: "Campaigns" | "Review" | "Money" | "Account";
  icon: ProductIconName;
  title: string;
  copy: string;
  time: string;
  href: string;
  unread: boolean;
};

const initialNotices: Notice[] = [
  { id: 1, kind: "Money", icon: "wallet", title: "₦18,400 is ready to withdraw", copy: "The holding period ended for two approved clips.", time: "4 min", href: "/dashboard/earnings", unread: true },
  { id: 2, kind: "Campaigns", icon: "brief", title: "Your Gbedu clip was approved", copy: "New verified views can now earn from Main character sound.", time: "36 min", href: "/dashboard/submissions/approved", unread: true },
  { id: 3, kind: "Campaigns", icon: "clock", title: "No long thing closes in 4 days", copy: "Your approved clip can keep earning until the campaign closes.", time: "2 hr", href: "/dashboard/campaigns/indomie-no-long-thing", unread: false },
  { id: 4, kind: "Account", icon: "shield", title: "Instagram view reading restored", copy: "Your connected account is responding normally again.", time: "Yesterday", href: "/dashboard/accounts", unread: false },
  { id: 5, kind: "Money", icon: "bank", title: "Withdrawal delivered", copy: "₦10,000 landed in your GTBank account ending 6789.", time: "Yesterday", href: "/dashboard/payouts/receipt", unread: false },
  { id: 6, kind: "Campaigns", icon: "spark", title: "A new comedy brief matches your profile", copy: "PalmPay is paying ₦650 per 1,000 verified views.", time: "18 Sep", href: "/dashboard/campaigns/palmpay-send-am-sharp", unread: false },
];

const initialBrandNotices: Notice[] = [
  { id: 101, kind: "Review", icon: "eye", title: "7 clips need your decision", copy: "Open the queue to approve, request changes or decline each submission.", time: "Now", href: "/brand/reviews", unread: true },
  { id: 102, kind: "Review", icon: "play", title: "Kemi Frames submitted a new clip", copy: "The platform reading is ready for your review on No long thing.", time: "12 min", href: "/brand/reviews/kemi-frames", unread: true },
  { id: 103, kind: "Money", icon: "bank", title: "₦42,800 was returned", copy: "The unused balance from Campus chop stories is back in your account.", time: "1 hr", href: "/brand/transactions", unread: true },
  { id: 104, kind: "Campaigns", icon: "clock", title: "No long thing closes in 4 days", copy: "Approved clips can keep earning until the campaign closes or the pot runs out.", time: "3 hr", href: "/brand/campaigns/no-long-thing", unread: true },
  { id: 105, kind: "Campaigns", icon: "eye", title: "72,800 verified views today", copy: "The latest platform readings are now included in your campaign total.", time: "Yesterday", href: "/brand/campaigns/no-long-thing", unread: false },
  { id: 106, kind: "Account", icon: "shield", title: "Brand account verification is complete", copy: "Gbedu Records can fund campaigns and receive returned balances.", time: "18 Sep", href: "/brand/settings", unread: false },
];

export function NotificationsScreen() {
  const [filter, setFilter] = useState("All");
  const [notices, setNotices] = useState(initialNotices);
  const visible = notices.filter((notice) => filter === "All" || notice.kind === filter);
  const unread = notices.filter((notice) => notice.unread).length;

  return <div className="dashboard-page customer-page notifications-page">
    <ScreenHead title="Notifications" copy="Campaign decisions, money movement and account checks." action={<button className="customer-text-button" type="button" onClick={() => setNotices((current) => current.map((notice) => ({ ...notice, unread: false })))} disabled={!unread}>Mark all as read</button>} />
    <section className="notification-console">
      <aside className="notification-tally"><span><ProductIcon name="bell" /><i>{unread}</i></span><strong>{unread ? `${unread} new` : "All read"}</strong><small>Latest account activity</small><div>{["All", "Campaigns", "Money", "Account"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></aside>
      <div className="notification-tape">{visible.map((notice) => <Link href={notice.href} className={notice.unread ? "is-unread" : ""} onClick={() => setNotices((current) => current.map((item) => item.id === notice.id ? { ...item, unread: false } : item))} key={notice.id}><span className={`notice-icon notice-icon--${notice.kind.toLowerCase()}`}><ProductIcon name={notice.icon} /></span><p><small>{notice.kind}</small><strong>{notice.title}</strong><span>{notice.copy}</span></p><time>{notice.time}</time><ProductIcon name="arrow" /></Link>)}</div>
    </section>
  </div>;
}

const BRAND_NOTIFICATION_EVENT = "clippit:brand-notifications";

function saveBrandRead(notices: Notice[]) {
  const read = notices.filter((notice) => !notice.unread).map((notice) => notice.id);
  window.localStorage.setItem("clippit:brand-notifications-read", JSON.stringify(read));
  window.dispatchEvent(new CustomEvent(BRAND_NOTIFICATION_EVENT, { detail: notices.filter((notice) => notice.unread).length }));
}

export function BrandNotificationsScreen() {
  const [filter, setFilter] = useState("All");
  const [notices, setNotices] = useState(initialBrandNotices);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const read = JSON.parse(window.localStorage.getItem("clippit:brand-notifications-read") || "[]") as number[];
        setNotices((current) => current.map((notice) => read.includes(notice.id) ? { ...notice, unread: false } : notice));
      } catch { /* Keep the default unread state when stored data is unavailable. */ }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  const visible = notices.filter((notice) => filter === "All" || notice.kind === filter);
  const unread = notices.filter((notice) => notice.unread).length;
  const updateNotices = (next: Notice[]) => { setNotices(next); saveBrandRead(next); };

  return <div className="brand-page customer-page notifications-page brand-notifications-page">
    <ScreenHead title="Notifications" copy="Reviews, campaign updates, money movement and account checks." action={<button className="customer-text-button" type="button" onClick={() => updateNotices(notices.map((notice) => ({ ...notice, unread: false })))} disabled={!unread}>Mark all as read</button>} />
    <section className="notification-console">
      <aside className="notification-tally"><span><ProductIcon name="bell" /><i>{unread}</i></span><strong>{unread ? `${unread} new` : "All read"}</strong><small>Gbedu Records activity</small><div>{["All", "Review", "Campaigns", "Money", "Account"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></aside>
      <div className="notification-tape">{visible.map((notice) => <Link href={notice.href} className={notice.unread ? "is-unread" : ""} onClick={() => updateNotices(notices.map((item) => item.id === notice.id ? { ...item, unread: false } : item))} key={notice.id}><span className={`notice-icon notice-icon--${notice.kind.toLowerCase()}`}><ProductIcon name={notice.icon} /></span><p><small>{notice.kind}</small><strong>{notice.title}</strong><span>{notice.copy}</span></p><time>{notice.time}</time><ProductIcon name="arrow" /></Link>)}</div>
    </section>
  </div>;
}

const banks = ["GTBank", "Access Bank", "First Bank", "Kuda", "OPay", "UBA", "Zenith Bank"];

export function PayoutAccountScreen() {
  const [step, setStep] = useState(0);
  const [bank, setBank] = useState("GTBank");
  const [account, setAccount] = useState("");
  const [otp, setOtp] = useState("");
  const resolved = account.length === 10;
  const submitDetails = (event: FormEvent) => { event.preventDefault(); if (resolved) setStep(1); };
  const verify = (event: FormEvent) => { event.preventDefault(); if (otp.length === 6) { window.localStorage.setItem("clippit:payout-bank", JSON.stringify({ bank, account })); setStep(2); } };

  return <div className="dashboard-page customer-page payout-account-page">
    <ScreenHead title={step === 2 ? "Bank account verified" : "Payout account"} copy={step === 2 ? "Payable earnings can now move to this account." : "Add the Nigerian bank account where your withdrawals should land."} back="/dashboard/settings" />
    <div className="bank-setup-layout">
      <aside className="bank-setup-rail"><div>{["Account", "Confirm", "Verified"].map((item, index) => <span className={index <= step ? "is-done" : ""} key={item}><i>{index < step ? <ProductIcon name="check" /> : index + 1}</i><b>{item}</b></span>)}</div><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" alt="" width={520} height={520} /></aside>
      {step === 0 && <form className="bank-setup-sheet" onSubmit={submitDetails}><header><span><ProductIcon name="bank" /></span><div><h2>Where should your money land?</h2><p>The account name must match your verified identity.</p></div></header><label><span>Bank</span><select value={bank} onChange={(event) => setBank(event.target.value)}>{banks.map((item) => <option key={item}>{item}</option>)}</select></label><label><span>Account number</span><input value={account} onChange={(event) => setAccount(event.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" placeholder="10-digit account number" /><small>{account.length}/10</small></label><div className={`account-resolution${resolved ? " is-resolved" : ""}`}><span>{resolved ? <ProductIcon name="check" /> : <ProductIcon name="person" />}</span><p><small>Account holder</small><strong>{resolved ? "Tobi Adeyemi" : "Enter all 10 digits to resolve the name"}</strong></p></div><button className="lime-button" type="submit" disabled={!resolved}>Confirm this account<ProductIcon name="arrow" /></button></form>}
      {step === 1 && <form className="bank-setup-sheet bank-confirm-sheet" onSubmit={verify}><header><span><ProductIcon name="shield" /></span><div><h2>Confirm it is you</h2><p>Enter the six-digit code sent to your phone ending 2041.</p></div></header><div className="bank-confirm-card"><small>New payout account</small><strong>{bank}</strong><b>•••• ••{account.slice(-4)}</b><span>Tobi Adeyemi</span></div><label><span>Verification code</span><input value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder="000000" /><small>{otp.length}/6</small></label><button className="lime-button" type="submit" disabled={otp.length !== 6}>Verify payout account<ProductIcon name="arrow" /></button><button className="customer-text-button" type="button" onClick={() => setStep(0)}>Use a different account</button></form>}
      {step === 2 && <section className="bank-verified-sheet"><div className="bank-verified-seal"><ProductIcon name="check" /><i /><i /></div><small>Verified payout destination</small><h2>{bank}</h2><strong>•••• ••{account.slice(-4)}</strong><p>Tobi Adeyemi</p><dl><div><dt>Currency</dt><dd>Nigerian naira</dd></div><div><dt>Transfer time</dt><dd>Within 24 hours</dd></div><div><dt>Security</dt><dd>Identity matched</dd></div></dl><Link className="lime-button" href="/dashboard/withdraw">Withdraw money<ProductIcon name="arrow" /></Link></section>}
    </div>
  </div>;
}

type Session = { id: number; device: string; place: string; seen: string; current?: boolean };

export function SecurityScreen() {
  const [twoFactor, setTwoFactor] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([
    { id: 1, device: "Chrome on Windows", place: "Lagos, Nigeria", seen: "Active now", current: true },
    { id: 2, device: "Chrome on Android", place: "Lagos, Nigeria", seen: "18 minutes ago" },
    { id: 3, device: "Safari on iPhone", place: "Abuja, Nigeria", seen: "14 September" },
  ]);
  const [saved, setSaved] = useState(false);
  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const valid = passwords.current.length >= 6 && passwords.next.length >= 8 && passwords.next === passwords.confirm;
  const update = (key: keyof typeof passwords, value: string) => setPasswords((current) => ({ ...current, [key]: value }));

  return <div className="dashboard-page customer-page security-page">
    <ScreenHead title="Security" copy="Manage your password, verification method and signed-in devices." back="/dashboard/settings" />
    <div className="security-layout">
      <section className="security-sheet security-score"><div className="security-orbit"><strong><AnimatedNumber value={twoFactor ? 100 : 72} suffix="%" /></strong><span>Account protection</span><i /><i /><i /></div><div><h2>{twoFactor ? "Protection is complete" : "Add one more layer"}</h2><p>Turn on two-step verification before changing payout details.</p><label className="security-toggle"><span><ProductIcon name="shield" /><b>Two-step verification</b><small>Use a code when a new device signs in.</small></span><input type="checkbox" checked={twoFactor} onChange={() => setTwoFactor((value) => !value)} /><i /></label></div></section>
      <form className="security-sheet password-sheet" onSubmit={(event) => { event.preventDefault(); if (valid) { setSaved(true); setPasswords({ current: "", next: "", confirm: "" }); window.setTimeout(() => setSaved(false), 1800); } }}><header><span><ProductIcon name="settings" /></span><div><h2>Change password</h2><p>Use at least eight characters for the new password.</p></div></header><label><span>Current password</span><input type="password" value={passwords.current} onChange={(event) => update("current", event.target.value)} /></label><label><span>New password</span><input type="password" value={passwords.next} onChange={(event) => update("next", event.target.value)} /></label><label><span>Confirm new password</span><input type="password" value={passwords.confirm} onChange={(event) => update("confirm", event.target.value)} /></label><button className="lime-button" type="submit" disabled={!valid}>{saved ? "Password changed" : "Change password"}<ProductIcon name={saved ? "check" : "arrow"} /></button></form>
      <section className="security-sheet sessions-sheet"><header><div><h2>Signed-in devices</h2><p>Remove any session you do not recognise.</p></div><button className="customer-text-button" type="button" onClick={() => setSessions((current) => current.filter((session) => session.current))} disabled={sessions.length === 1}>Sign out other devices</button></header>{sessions.map((session) => <article key={session.id}><span><ProductIcon name={session.device.includes("Android") || session.device.includes("iPhone") ? "phone" : "tech"} /></span><p><strong>{session.device}{session.current && <i>Current</i>}</strong><small>{session.place} · {session.seen}</small></p>{!session.current && <button type="button" onClick={() => setSessions((current) => current.filter((item) => item.id !== session.id))}>Remove</button>}</article>)}</section>
    </div>
  </div>;
}

type BrandTransaction = { id: string; type: "Funding" | "Creator payout" | "Refund" | "Fee"; campaign: string; date: string; amount: number; status: string };
const transactions: BrandTransaction[] = [
  { id: "CLP-0926-041", type: "Funding", campaign: "No long thing", date: "20 Sep 2026", amount: -525000, status: "Cleared" },
  { id: "VIEW-21904", type: "Creator payout", campaign: "No long thing", date: "20 Sep 2026", amount: -18400, status: "Settled" },
  { id: "VIEW-21871", type: "Creator payout", campaign: "No long thing", date: "19 Sep 2026", amount: -32100, status: "Settled" },
  { id: "REF-00812", type: "Refund", campaign: "Campus chop stories", date: "16 Sep 2026", amount: 42800, status: "Returned" },
  { id: "FEE-00419", type: "Fee", campaign: "No long thing", date: "14 Sep 2026", amount: -25000, status: "Settled" },
];

function BrandReceiptDocument({ selected, fullPage = false }: { selected: BrandTransaction; fullPage?: boolean }) {
  const ticketArt = selected.type === "Funding" ? "/assets/illustrations/clippit-icons/funding-pot.webp" : selected.type === "Refund" ? "/assets/illustrations/clippit-icons/withdraw-bank.webp" : selected.type === "Creator payout" ? "/assets/illustrations/clippit-icons/payout-wallet.webp" : "/assets/illustrations/clippit-icons/verified-proof.webp";
  const recipient = selected.type === "Funding" ? ["Clippit Campaign Escrow", "Payaza · 019***9028"] : selected.type === "Refund" ? ["Gbedu Records Ltd.", "Wema Bank · 012***0193"] : selected.type === "Fee" ? ["Clippit Services", "Campaign verification account"] : ["Verified creator payout pool", "Payaza creator settlement"];
  const sender = selected.type === "Refund" ? ["Clippit Campaign Escrow", "Campaign account · 041"] : ["Gbedu Records Ltd.", "Wema Bank · 012***0193"];
  return <aside className={`transaction-ticket${fullPage ? " transaction-ticket--full" : ""}`}><ReceiptHeader title="Official transaction receipt" reference={selected.id} /><div className="transaction-ticket__subject"><span><Image src={ticketArt} width={82} height={82} alt="" /></span><p><small>{selected.type}</small><strong>{selected.amount > 0 ? "+" : "−"}{money(Math.abs(selected.amount))}</strong><em><ProductIcon name="check" />{selected.status}</em><time>{selected.date} · 15:07:13 WAT</time></p></div><div className="transaction-ticket__parties"><section><h2>Recipient</h2><p><strong>{recipient[0]}</strong><span>{recipient[1]}</span></p></section><section><h2>Sender</h2><p><strong>{sender[0]}</strong><span>{sender[1]}</span></p></section></div><section className="transaction-ticket__information"><h2>Transaction information</h2><dl><div><dt>Transaction type</dt><dd>{selected.type}</dd></div><div><dt>Transaction ID</dt><dd>{selected.id}</dd></div><div><dt>Session ID</dt><dd>100033260920115117010192295902</dd></div><div><dt>Campaign</dt><dd>{selected.campaign}</dd></div><div><dt>Ledger entry</dt><dd>LDG-2026-0920-041</dd></div><div><dt>Settlement currency</dt><dd>Nigerian naira</dd></div></dl></section><div className="transaction-ticket__verified"><ProductIcon name="shield" /><span><strong>Verify this receipt</strong><small>clippit.ng/verify/{selected.id} · Code 7A19-C2F4</small></span></div>{selected.campaign === "Campus chop stories" && <Link href="/brand/campaigns/campus-chop/report">Open closeout report<ProductIcon name="arrow" /></Link>}<button type="button" onClick={() => window.print()}>Download receipt<ProductIcon name="brief" /></button></aside>;
}

export function BrandTransactionsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState(transactions[0]);
  const visible = transactions.filter((item) => filter === "All" || item.type === filter);
  return <div className="brand-page customer-page brand-transactions-page">
    <ScreenHead title="Transactions" copy="Campaign funding, creator payouts, fees and returned money." action={<button className="brand-button" type="button" onClick={() => window.print()}>Export statement<ProductIcon name="brief" /></button>} />
    <section className="transaction-balance"><div><small>Money currently in campaign pots</small><strong><AnimatedNumber value={312500} format="money" /></strong><span><ProductIcon name="shield" />Held in escrow</span></div><dl><div><dt>Funded this month</dt><dd><AnimatedNumber value={875000} format="money" /></dd></div><div><dt>Paid to creators</dt><dd><AnimatedNumber value={187500} format="money" /></dd></div><div><dt>Returned</dt><dd><AnimatedNumber value={42800} format="money" /></dd></div></dl></section>
    <div className="transaction-workspace"><section className="transaction-ledger"><header><div>{["All", "Funding", "Creator payout", "Refund", "Fee"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div><span>{visible.length} records</span></header><div className="transaction-labels"><span>Reference</span><span>Campaign</span><span>Date</span><span>Amount</span><span>Status</span></div>{visible.map((item) => <button type="button" className={`transaction-row${selected.id === item.id ? " is-selected" : ""}`} onClick={() => window.matchMedia("(max-width: 900px)").matches ? router.push(`/brand/transactions/${item.id}`) : setSelected(item)} key={item.id}><span><i><ProductIcon name={item.type === "Refund" ? "arrow" : item.type === "Funding" ? "wallet" : "bank"} /></i><b>{item.type}</b><small>{item.id}</small></span><strong>{item.campaign}</strong><time>{item.date}</time><em className={item.amount > 0 ? "is-credit" : ""}>{item.amount > 0 ? "+" : "−"}{money(Math.abs(item.amount))}</em><u>{item.status}</u></button>)}</section><BrandReceiptDocument selected={selected} /></div>
  </div>;
}

export function BrandTransactionReceiptScreen({ transactionId }: { transactionId: string }) {
  const selected = transactions.find((item) => item.id === transactionId) || transactions[0];
  return <div className="brand-page customer-page transaction-receipt-page"><Link className="brand-back" href="/brand/transactions"><ProductIcon name="chevron" />Back to transactions</Link><BrandReceiptDocument selected={selected} fullPage /></div>;
}

export function CampaignCloseoutScreen() {
  return <div className="brand-page customer-page closeout-page">
    <ScreenHead title="Campaign closeout" copy="Final delivery and money record for Campus chop stories." back="/brand/campaigns" action={<button className="brand-button" type="button" onClick={() => window.print()}>Download report<ProductIcon name="brief" /></button>} />
    <section className="closeout-hero"><div><span><ProductIcon name="check" /></span><small>Campaign completed · 16 Sep 2026</small><h2>Campus chop stories</h2><p>All approved views are settled. Unused money has been returned.</p></div><div className="closeout-stamp"><Image src="/assets/illustrations/clippit-icons/verified-proof.webp" alt="" width={220} height={220} /><strong>Closed clean</strong></div></section>
    <section className="closeout-receipt"><ReceiptHeader title="Official campaign closeout" reference="CAM-0904-118" /><div className="closeout-receipt__campaign"><div><Image src="/assets/photos/street-style.jpg" alt="Campus chop stories campaign" fill sizes="110px" /></div><p><small>Completed campaign</small><strong>Campus chop stories</strong><span>Gbedu Records · Closed 16 Sep 2026</span></p><em><ProductIcon name="check" />Settled</em></div><div className="closeout-money"><p><small>Campaign pot</small><strong><AnimatedNumber value={350000} format="money" /></strong></p><i /><p><small>Earned by creators</small><strong><AnimatedNumber value={307200} format="money" /></strong></p><i /><p><small>Returned to Gbedu Records</small><strong><AnimatedNumber value={42800} format="money" /></strong></p></div><div className="closeout-proof"><article><small>Verified views</small><strong><AnimatedNumber value={875000} format="compact" /></strong><span>from platform readings</span></article><article><small>Approved clips</small><strong><AnimatedNumber value={93} /></strong><span>from 71 creators</span></article><article><small>Average cost</small><strong><AnimatedNumber value={351} format="money" /></strong><span>per 1K verified views</span></article><article><small>Review accuracy</small><strong><AnimatedNumber value={96} suffix="%" /></strong><span>4 verdicts overturned</span></article></div><footer className="closeout-receipt__footer"><ProductIcon name="shield" /><span><strong>Final settlement complete</strong><small>Creator earnings were settled and unused campaign funds returned.</small></span><b>Clippit verified</b></footer></section>
    <div className="closeout-grid"><section className="platform-delivery"><header><h2>Where the views came from</h2><p>Final platform readings.</p></header>{[["TikTok", 61, 533750, "tiktok"], ["Instagram", 27, 236250, "instagram"], ["YouTube", 12, 105000, "youtube"]].map(([name, share, views, icon]) => <div key={String(name)}><span><ProductIcon name={icon as ProductIconName} /></span><p><strong>{name}</strong><small><AnimatedNumber value={Number(views)} format="compact" /> views</small></p><i><b style={{ width: `${share}%` }} /></i><em>{share}%</em></div>)}</section><section className="top-delivery"><header><h2>Top clips</h2><p>Highest verified delivery.</p></header>{[["KM", "Kemi Frames", 146200], ["NE", "Nana Edits", 121800], ["DD", "Deji Does It", 98700]].map(([initials, name, views], index) => <article key={String(name)}><b>{index + 1}</b><span>{initials}</span><p><strong>{name}</strong><small><AnimatedNumber value={Number(views)} format="compact" /> verified views</small></p></article>)}</section></div>
  </div>;
}

export function PublicProfileScreen() {
  const profile = useStoredProfile("creator", CREATOR_PROFILE);
  const [copied, setCopied] = useState(false);
  const initials = useMemo(() => profile.name.split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "TO", [profile.name]);
  const copy = async () => { try { await navigator.clipboard.writeText("https://clippit.ng/creators/tobioncam"); } catch {} setCopied(true); window.setTimeout(() => setCopied(false), 1600); };
  return <div className="dashboard-page customer-page public-profile-page">
    <ScreenHead title="Public profile" copy="Preview what brands see when they open your creator profile." back="/dashboard/settings" action={<div className="profile-head-actions"><button type="button" onClick={copy}>{copied ? "Link copied" : "Copy profile link"}<ProductIcon name={copied ? "check" : "link"} /></button><Link href="/dashboard/settings#profile">Edit profile<ProductIcon name="arrow" /></Link></div>} />
    <section className="public-passport"><div className="public-passport__cover"><Image src="/assets/photos/lagos-portrait.jpg" alt="" fill sizes="(max-width: 700px) 100vw, 70vw" priority /><span>Available for funded briefs</span></div><div className="public-passport__identity"><ProfileAvatar profile={profile} fallback={initials} className="public-avatar" /><div><small>@tobioncam</small><h2>{profile.name}</h2><p>{profile.bio || "Comedy, food and everyday Lagos stories."}</p><span><ProductIcon name="source" />Lagos, Nigeria</span></div><div className="public-proof"><ProductIcon name="shield" /><span><strong>Verified creator</strong><small>Views read from connected accounts</small></span></div></div><dl><div><dt>Verified views</dt><dd><AnimatedNumber value={368000} format="compact" /></dd></div><div><dt>Approved clips</dt><dd><AnimatedNumber value={12} /></dd></div><div><dt>Campaigns</dt><dd><AnimatedNumber value={7} /></dd></div><div><dt>Approval rate</dt><dd><AnimatedNumber value={92} suffix="%" /></dd></div></dl></section>
    <section className="profile-work"><header><div><h2>Recent campaign work</h2><p>Approved posts with verified platform readings.</p></div><span>Comedy · Food · Lifestyle</span></header><div>{[{ image: "/assets/video/creator-reaction-poster.jpg", brand: "Indomie", title: "Hunger interrupted the group chat", views: 156800, platform: "TikTok" }, { image: "/assets/photos/headphones.jpg", brand: "Gbedu Records", title: "The main-character entrance", views: 121400, platform: "Instagram" }, { image: "/assets/photos/street-style.jpg", brand: "PalmPay", title: "Who paid for the ride?", views: 89800, platform: "YouTube" }].map((work) => <article key={work.title}><div><Image src={work.image} alt="" fill sizes="(max-width: 700px) 92vw, 28vw" /><span>{work.platform}</span></div><small>{work.brand}</small><h3>{work.title}</h3><p><ProductIcon name="eye" /><AnimatedNumber value={work.views} format="compact" /> verified views</p></article>)}</div></section>
  </div>;
}
