"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfileAvatar, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { ButtonLoader, ClippitLoader, ClippitMarkMotion } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { BRAND_CAMPAIGN_FEE_RATE, calculateFee } from "@/lib/fees";
import { money } from "@/lib/product";
import { authApi } from "@/lib/api/auth";
import type { SessionOut } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { announceNotificationsChanged, notificationsApi, type NotificationOut } from "@/lib/api/notifications";
import { bankDetailsApi, banksApi, type BankAccountOut, type BankOut } from "@/lib/api/bankDetails";
import { creatorProfileApi } from "@/lib/api/social";
import { publicProfilesApi, type PublicCreatorProfileOut } from "@/lib/api/account";
import { formatDate, platformLabel } from "@/lib/format";

function ScreenHead({ title, copy, back, action }: { title: string; copy: string; back?: string; action?: ReactNode }) {
  return <header className="customer-head">
    <div>{back && <Link className="customer-back" href={back}><ProductIcon name="chevron" />Back</Link>}<h1>{title}</h1><p>{copy}</p></div>
    {action}
  </header>;
}

type Notice = {
  id: number | string;
  kind: "Campaigns" | "Review" | "Money" | "Account" | "Clips";
  icon: ProductIconName;
  title: string;
  copy: string;
  time: string;
  href: string;
  unread: boolean;
};

const initialBrandNotices: Notice[] = [
  { id: 101, kind: "Review", icon: "eye", title: "7 clips need your decision", copy: "Open the queue to approve, request changes or decline each submission.", time: "Now", href: "/brand/reviews", unread: true },
  { id: 102, kind: "Review", icon: "play", title: "Kemi Frames submitted a new clip", copy: "The platform reading is ready for your review on No long thing.", time: "12 min", href: "/brand/reviews/kemi-frames", unread: true },
  { id: 103, kind: "Money", icon: "bank", title: "₦42,800 was returned", copy: "The unused balance from Campus chop stories is back in your account.", time: "1 hr", href: "/brand/transactions", unread: true },
  { id: 104, kind: "Campaigns", icon: "clock", title: "No long thing closes in 4 days", copy: "Approved clips can keep earning until the campaign closes or the pot runs out.", time: "3 hr", href: "/brand/campaigns/no-long-thing", unread: true },
  { id: 105, kind: "Campaigns", icon: "eye", title: "72,800 verified views today", copy: "The latest platform readings are now included in your campaign total.", time: "Yesterday", href: "/brand/campaigns/no-long-thing", unread: false },
  { id: 106, kind: "Account", icon: "shield", title: "Brand account verification is complete", copy: "Gbedu Records can fund campaigns and receive returned balances.", time: "18 Sep", href: "/brand/settings", unread: false },
];

function mapApiKind(kind: string): Notice["kind"] {
  const k = kind.toLowerCase();
  if (k.includes("money") || k.includes("earning") || k.includes("payout") || k.includes("withdrawal") || k.includes("wallet")) return "Money";
  if (k.includes("review") || k.includes("submission") || k.includes("appeal")) return "Review";
  if (k.includes("account") || k.includes("security") || k.includes("social")) return "Account";
  return "Campaigns";
}

function mapApiIcon(kind: string): ProductIconName {
  const k = kind.toLowerCase();
  if (k.includes("money") || k.includes("earning") || k.includes("payout")) return "wallet";
  if (k.includes("bank") || k.includes("withdrawal")) return "bank";
  if (k.includes("review") || k.includes("submission")) return "eye";
  if (k.includes("campaign") || k.includes("brief") || k.includes("match")) return "brief";
  if (k.includes("clock") || k.includes("closing")) return "clock";
  if (k.includes("security") || k.includes("shield")) return "shield";
  return "bell";
}

function relativeTimeFromDate(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins} min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} hr`;
    const days = Math.floor(hrs / 24);
    if (days === 1) return "Yesterday";
    return `${days} days ago`;
  } catch { return ""; }
}

function creatorNoticeKind(kind: string): Notice["kind"] {
  if (kind === "submission_verdict" || kind === "appeal_decision") return "Clips";
  if (kind === "earnings_payable" || kind === "payout") return "Money";
  if (kind === "new_campaign" || kind === "campaign_closing") return "Campaigns";
  return mapApiKind(kind) === "Review" ? "Clips" : mapApiKind(kind);
}

function creatorNoticeIcon(kind: string): ProductIconName {
  if (kind === "submission_verdict") return "eye";
  if (kind === "appeal_decision") return "shield";
  if (kind === "earnings_payable") return "wallet";
  if (kind === "payout") return "bank";
  return mapApiIcon(kind);
}

function toCreatorNotice(n: NotificationOut): Notice & { createdAt: string } {
  return { id: n.id, kind: creatorNoticeKind(n.kind), icon: creatorNoticeIcon(n.kind), title: n.title, copy: n.body, time: relativeTimeFromDate(n.created_at), href: n.link ?? "", unread: !n.read, createdAt: n.created_at };
}

const NOTICE_PAGE = 30;

export function NotificationsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [notices, setNotices] = useState<Array<Notice & { createdAt: string }> | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    notificationsApi.list({ limit: NOTICE_PAGE }).then((data) => {
      setNotices(data.items.map(toCreatorNotice));
      setHasMore(data.items.length === NOTICE_PAGE);
    }).catch((err) => setError(err instanceof ApiError ? err.detail : "We couldn't load your notifications."));
  }, []);

  if (error && !notices) return <div className="dashboard-page customer-page"><ScreenHead title="Notifications" copy={error} /></div>;
  if (!notices) return <div className="dashboard-page"><ClippitLoader contained label="Checking your notifications" note="Bringing in campaign decisions, money updates and account activity." /></div>;

  const visible = notices.filter((notice) => filter === "All" || notice.kind === filter);
  const unread = notices.filter((notice) => notice.unread).length;

  const markAllRead = async () => {
    const previous = notices;
    setNotices((current) => current && current.map((notice) => ({ ...notice, unread: false })));
    try {
      await notificationsApi.markAllRead();
      announceNotificationsChanged();
    } catch {
      setNotices(previous);
      setError("We couldn't mark those as read. Try again.");
    }
  };

  const open = (notice: Notice) => {
    if (notice.unread) {
      setNotices((current) => current && current.map((item) => item.id === notice.id ? { ...item, unread: false } : item));
      notificationsApi.markRead(String(notice.id)).then(announceNotificationsChanged).catch(() => undefined);
    }
    if (notice.href) router.push(notice.href);
  };

  const loadOlder = async () => {
    const last = notices[notices.length - 1];
    if (!last) return;
    setLoadingMore(true);
    try {
      const data = await notificationsApi.list({ limit: NOTICE_PAGE, before: last.createdAt });
      setNotices((current) => [...(current ?? []), ...data.items.map(toCreatorNotice)]);
      setHasMore(data.items.length === NOTICE_PAGE);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't load older notifications.");
    } finally {
      setLoadingMore(false);
    }
  };

  return <div className="dashboard-page customer-page notifications-page">
    <ScreenHead title="Notifications" copy="Clip decisions, money movement and account checks." action={<button className="customer-text-button" type="button" onClick={markAllRead} disabled={!unread}>Mark all as read</button>} />
    {error && <p className="auth-error" role="alert">{error}</p>}
    <section className="notification-console">
      <aside className="notification-tally"><span><ProductIcon name="bell" /><i>{unread}</i></span><strong>{unread ? `${unread} new` : "All read"}</strong><small>Latest account activity</small><div>{["All", "Clips", "Money", "Campaigns", "Account"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></aside>
      <div className="notification-tape">
        {!visible.length && <ClippitEmptyState className="notification-tape__empty" size="compact" tone="gold" icon="bell" title={notices.length ? `No ${filter.toLowerCase()} notifications` : "You're all caught up"} copy={notices.length ? "Choose another filter to see the rest of your updates." : "Clip decisions, payable earnings and payouts will appear here."} />}
        {visible.map((notice) => <a href={notice.href || undefined} className={notice.unread ? "is-unread" : ""} onClick={(event) => { event.preventDefault(); open(notice); }} key={notice.id}><span className={`notice-icon notice-icon--${notice.kind.toLowerCase()}`}><ProductIcon name={notice.icon} /></span><p><small>{notice.kind}</small><strong>{notice.title}</strong><span>{notice.copy}</span></p><time>{notice.time}</time><ProductIcon name="arrow" /></a>)}
        {hasMore && <button type="button" className="customer-text-button" disabled={loadingMore} onClick={loadOlder}>{loadingMore ? "Loading…" : "Show older notifications"}</button>}
      </div>
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    notificationsApi.list().then((data) => {
      if (data.items.length > 0) {
        setNotices(data.items.map((n, i) => ({
          id: i + 1,
          kind: mapApiKind(n.kind),
          icon: mapApiIcon(n.kind),
          title: n.title,
          copy: n.body,
          time: relativeTimeFromDate(n.created_at),
          href: n.link ?? "#",
          unread: !n.read,
        })));
        return;
      }
      const timer = window.setTimeout(() => {
        try {
          const read = JSON.parse(window.localStorage.getItem("clippit:brand-notifications-read") || "[]") as Array<number | string>;
          setNotices((current) => current.map((notice) => read.includes(notice.id) ? { ...notice, unread: false } : notice));
        } catch { /* keep default */ }
      }, 0);
      return () => window.clearTimeout(timer);
    }).catch(() => {
      const timer = window.setTimeout(() => {
        try {
          const read = JSON.parse(window.localStorage.getItem("clippit:brand-notifications-read") || "[]") as Array<number | string>;
          setNotices((current) => current.map((notice) => read.includes(notice.id) ? { ...notice, unread: false } : notice));
        } catch { /* keep default */ }
      }, 0);
      return () => window.clearTimeout(timer);
    }).finally(() => setLoading(false));
  }, []);

  const visible = notices.filter((notice) => filter === "All" || notice.kind === filter);
  const unread = notices.filter((notice) => notice.unread).length;
  const updateNotices = (next: Notice[]) => { setNotices(next); saveBrandRead(next); };

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking brand notifications" note="Bringing in reviews, campaign updates and money movement." /></div>;

  return <div className="brand-page customer-page notifications-page brand-notifications-page">
    <ScreenHead title="Notifications" copy="Reviews, campaign updates, money movement and account checks." action={<button className="customer-text-button" type="button" onClick={() => updateNotices(notices.map((notice) => ({ ...notice, unread: false })))} disabled={!unread}>Mark all as read</button>} />
    <section className="notification-console">
      <aside className="notification-tally"><span><ProductIcon name="bell" /><i>{unread}</i></span><strong>{unread ? `${unread} new` : "All read"}</strong><small>Gbedu Records activity</small><div>{["All", "Review", "Campaigns", "Money", "Account"].map((item) => <button type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)} key={item}>{item}</button>)}</div></aside>
      <div className="notification-tape">{visible.map((notice) => <Link href={notice.href} className={notice.unread ? "is-unread" : ""} onClick={() => updateNotices(notices.map((item) => item.id === notice.id ? { ...item, unread: false } : item))} key={notice.id}><span className={`notice-icon notice-icon--${notice.kind.toLowerCase()}`}><ProductIcon name={notice.icon} /></span><p><small>{notice.kind}</small><strong>{notice.title}</strong><span>{notice.copy}</span></p><time>{notice.time}</time><ProductIcon name="arrow" /></Link>)}</div>
    </section>
  </div>;
}

const FALLBACK_BANKS: BankOut[] = [
  { code: "058", name: "GTBank" },
  { code: "044", name: "Access Bank" },
  { code: "011", name: "First Bank" },
  { code: "090267", name: "Kuda" },
  { code: "100004", name: "OPay" },
  { code: "033", name: "UBA" },
  { code: "057", name: "Zenith Bank" },
];

export function PayoutAccountScreen() {
  const [step, setStep] = useState(0);
  const [existing, setExisting] = useState<BankAccountOut | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const [bankList, setBankList] = useState<BankOut[]>(FALLBACK_BANKS);
  const [banksNote, setBanksNote] = useState("");
  const [selectedBank, setSelectedBank] = useState<BankOut>(FALLBACK_BANKS[0]);
  const [account, setAccount] = useState("");
  const [resolution, setResolution] = useState<{ key: string; name: string | null; error: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [verified, setVerified] = useState<BankAccountOut | null>(null);

  useEffect(() => {
    bankDetailsApi.get().then(setExisting).catch(() => setExisting(null));
    banksApi.list().then((data) => {
      if (data.length > 0) {
        const sorted = [...data].sort((a, b) => a.name.localeCompare(b.name));
        setBankList(sorted);
        setSelectedBank(sorted[0]);
      }
    }).catch(() => setBanksNote("Showing popular banks while the full list loads."));
  }, []);

  const resolveKey = `${selectedBank.code}:${account}`;
  const current = account.length === 10 && resolution?.key === resolveKey ? resolution : null;
  const resolving = account.length === 10 && !current;
  const resolvedName = current?.name ?? null;
  const resolveError = current?.error ?? "";

  useEffect(() => {
    if (account.length !== 10) return;
    let cancelled = false;
    const key = `${selectedBank.code}:${account}`;
    bankDetailsApi.resolve(selectedBank.code, account)
      .then((data) => { if (!cancelled) setResolution({ key, name: data.account_name, error: "" }); })
      .catch((err) => { if (!cancelled) setResolution({ key, name: null, error: err instanceof ApiError ? err.detail : "We couldn't check that account. Try again." }); });
    return () => { cancelled = true; };
  }, [account, selectedBank.code]);

  const toConfirm = (event: FormEvent) => {
    event.preventDefault();
    if (resolvedName) { setError(""); setStep(1); }
  };

  const saveAndVerify = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await bankDetailsApi.save({ bank_code: selectedBank.code, bank_name: selectedBank.name, account_number: account });
      const result = await bankDetailsApi.verify();
      setVerified(result);
      setExisting(result);
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't verify this account. Check your connection and try again.");
    } finally {
      setSaving(false);
    }
  };

  const retryVerify = async () => {
    setSaving(true);
    setError("");
    try {
      const result = await bankDetailsApi.verify();
      setExisting(result);
      if (!result.verified) setError("The bank couldn't confirm this account yet. Try again shortly.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't verify this account.");
    } finally {
      setSaving(false);
    }
  };

  const removeAccount = async () => {
    const password = window.prompt("Enter your Clippit password to remove this payout account.");
    if (!password) return;
    setSaving(true);
    setError("");
    try {
      const challenge = await authApi.requestStepUp({ action: "delete_bank_details" });
      const stepUp = await authApi.verifyStepUp({ challenge_token: challenge.challenge_token, password });
      await bankDetailsApi.remove(stepUp.step_up_token);
      setExisting(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't remove this account.");
    } finally {
      setSaving(false);
    }
  };

  if (existing === undefined) return <div className="dashboard-page"><ClippitLoader contained label="Checking your payout account" /></div>;

  if (existing && !editing && step !== 2) {
    return <div className="dashboard-page customer-page payout-account-page">
      <ScreenHead title="Payout account" copy="Where your withdrawals land." back="/dashboard/settings" />
      <div className="bank-setup-layout">
        <aside className="bank-setup-rail"><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" alt="" width={520} height={520} /></aside>
        <section className="bank-verified-sheet"><div className="bank-verified-seal"><ProductIcon name={existing.verified ? "check" : "shield"} /><i /><i /></div><small>{existing.verified ? "Verified payout destination" : "Not verified yet"}</small><h2>{existing.bank_name}</h2><strong>{existing.account_number_masked}</strong><p>{existing.account_name ?? "Account name pending"}</p><dl><div><dt>Status</dt><dd>{existing.verified ? `Verified ${formatDate(existing.verified_at)}` : "Verify before withdrawing"}</dd></div><div><dt>Currency</dt><dd>Nigerian naira</dd></div><div><dt>Transfer time</dt><dd>Within 24 hours</dd></div></dl>
          {error && <p className="auth-error" role="alert">{error}</p>}
          {existing.verified ? <Link className="lime-button" href="/dashboard/withdraw">Withdraw money<ProductIcon name="arrow" /></Link> : <button className="lime-button" type="button" disabled={saving} onClick={retryVerify}>{saving ? <ButtonLoader label="Verifying" /> : <>Verify this account<ProductIcon name="arrow" /></>}</button>}
          <button className="customer-text-button" type="button" onClick={() => { setEditing(true); setStep(0); }}>Use a different account</button>
          <button className="customer-text-button" type="button" disabled={saving} onClick={removeAccount}>Remove this account</button>
        </section>
      </div>
    </div>;
  }

  const maskedAccount = account.length >= 4 ? `•••• ••${account.slice(-4)}` : account;
  const canSubmit = account.length === 10 && !resolving && resolvedName !== null;
  const displayName = resolvedName ?? (resolving ? "Checking account" : resolveError || "Enter all 10 digits to resolve the name");

  return <div className="dashboard-page customer-page payout-account-page">
    <ScreenHead title={step === 2 ? "Bank account verified" : "Payout account"} copy={step === 2 ? "Payable earnings can now move to this account." : "Add the Nigerian bank account where your withdrawals should land."} back="/dashboard/settings" />
    <div className="bank-setup-layout">
      <aside className="bank-setup-rail"><div>{["Account", "Confirm", "Verified"].map((item, index) => <span className={index <= step ? "is-done" : ""} key={item}><i>{index < step ? <ProductIcon name="check" /> : index + 1}</i><b>{item}</b></span>)}</div><Image src="/assets/illustrations/clippit-icons/withdraw-bank.webp" alt="" width={520} height={520} /></aside>
      {step === 0 && <form className="bank-setup-sheet" onSubmit={toConfirm}><header><span><ProductIcon name="bank" /></span><div><h2>Where should your money land?</h2><p>Use an account in your own name.</p></div></header><label><span>Bank</span><select value={selectedBank.code} onChange={(event) => { const found = bankList.find((b) => b.code === event.target.value); if (found) setSelectedBank(found); }}>{bankList.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select>{banksNote && <small>{banksNote}</small>}</label><label><span>Account number</span><input value={account} onChange={(event) => setAccount(event.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" placeholder="10-digit account number" /><small>{account.length}/10</small></label><div className={`account-resolution${resolvedName ? " is-resolved" : ""}${resolving ? " is-loading" : ""}${resolveError ? " is-error" : ""}`}><span>{resolvedName ? <ProductIcon name="check" /> : resolving ? <ClippitMarkMotion compact /> : <ProductIcon name="person" />}</span><p><small>Account holder</small><strong>{displayName}</strong></p></div><button className="lime-button" type="submit" disabled={!canSubmit}>Confirm this account<ProductIcon name="arrow" /></button>{existing && <button className="customer-text-button" type="button" onClick={() => setEditing(false)}>Keep my current account</button>}</form>}
      {step === 1 && <form className="bank-setup-sheet bank-confirm-sheet" onSubmit={saveAndVerify}><header><span><ProductIcon name="shield" /></span><div><h2>Is this your account?</h2><p>We&apos;ll save it and confirm the details with your bank. {existing ? "This replaces your current payout account." : ""}</p></div></header><div className="bank-confirm-card"><small>New payout account</small><strong>{selectedBank.name}</strong><b>{maskedAccount}</b><span>{resolvedName}</span></div>{error && <p className="auth-error" role="alert">{error}</p>}<button className="lime-button" type="submit" disabled={saving} aria-busy={saving}>{saving ? <ButtonLoader label="Verifying with your bank" /> : <>Save and verify<ProductIcon name="arrow" /></>}</button><button className="customer-text-button" type="button" onClick={() => setStep(0)}>Use a different account</button></form>}
      {step === 2 && verified && <section className="bank-verified-sheet"><div className="bank-verified-seal"><ProductIcon name="check" /><i /><i /></div><small>{verified.verified ? "Verified payout destination" : "Saved — verification pending"}</small><h2>{verified.bank_name}</h2><strong>{verified.account_number_masked}</strong><p>{verified.account_name ?? resolvedName}</p><dl><div><dt>Currency</dt><dd>Nigerian naira</dd></div><div><dt>Transfer time</dt><dd>Within 24 hours</dd></div><div><dt>Security</dt><dd>{verified.verified ? "Confirmed with your bank" : "Awaiting bank confirmation"}</dd></div></dl><Link className="lime-button" href="/dashboard/withdraw">Withdraw money<ProductIcon name="arrow" /></Link></section>}
    </div>
  </div>;
}

type Session = { id: string; device: string; place: string; seen: string; current?: boolean };

function relativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const diffMins = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} minutes ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hours ago`;
  if (diffHours < 48) return "Yesterday";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "long" });
}

export function SecurityScreen() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [sessionError, setSessionError] = useState("");
  const [saved, setSaved] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const valid = passwords.current.length >= 6 && passwords.next.length >= 8 && /\d/.test(passwords.next) && passwords.next === passwords.confirm;
  const update = (key: keyof typeof passwords, value: string) => setPasswords((current) => ({ ...current, [key]: value }));

  const loadSessions = () => authApi.getSessions()
    .then((data: SessionOut[]) => {
      setSessions(data.map((s) => ({
        id: s.id,
        device: s.device_label || "Unknown device",
        place: s.ip_address || "Unknown network",
        seen: s.current ? "Active now" : relativeTime(s.last_seen_at),
        current: s.current,
      })));
      setSessionError("");
    })
    .catch((err) => setSessionError(err instanceof ApiError ? err.detail : "We couldn't load your devices."));

  useEffect(() => { void loadSessions(); }, []);

  const signOutOthers = async () => {
    setSessionError("");
    try {
      await authApi.revokeOtherSessions();
      setSessions((current) => current && current.filter((s) => s.current));
    } catch (err) {
      setSessionError(err instanceof ApiError ? err.detail : "We couldn't sign out your other devices.");
    }
  };

  const removeSession = async (id: string) => {
    setSessionError("");
    try {
      await authApi.revokeSession(id);
      setSessions((current) => current && current.filter((s) => s.id !== id));
    } catch (err) {
      setSessionError(err instanceof ApiError ? err.detail : "We couldn't remove that device.");
    }
  };

  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid) return;
    setPasswordLoading(true);
    setPasswordError("");
    try {
      await authApi.changePassword({ current_password: passwords.current, new_password: passwords.next, revoke_other_sessions: true });
      setSaved(true);
      setPasswords({ current: "", next: "", confirm: "" });
      window.setTimeout(() => setSaved(false), 1800);
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.detail : "Failed to change password.");
    } finally {
      setPasswordLoading(false);
    }
  };

  return <div className="dashboard-page customer-page security-page">
    <ScreenHead title="Security" copy="Manage your password, verification method and signed-in devices." back="/dashboard/settings" />
    <div className="security-layout">
      <section className="security-sheet security-score"><div className="security-orbit"><strong><ProductIcon name="shield" /></strong><span>Account protection</span><i /><i /><i /></div><div><h2>Keep your account yours</h2><p>Use a strong password and remove devices you don&apos;t recognise. Removing your payout account asks for your password again.</p><label className="security-toggle is-disabled"><span><ProductIcon name="shield" /><b>Two-step verification</b><small>Coming soon — we&apos;ll let you know when it&apos;s ready.</small></span><input type="checkbox" checked={false} disabled readOnly /><i /></label></div></section>
      <form className="security-sheet password-sheet" onSubmit={changePassword}><header><span><ProductIcon name="settings" /></span><div><h2>Change password</h2><p>Use at least eight characters including a number.</p></div></header><label><span>Current password</span><input type="password" value={passwords.current} onChange={(event) => update("current", event.target.value)} /></label><label><span>New password</span><input type="password" value={passwords.next} onChange={(event) => update("next", event.target.value)} /></label><label><span>Confirm new password</span><input type="password" value={passwords.confirm} onChange={(event) => update("confirm", event.target.value)} /></label>{passwordError && <p className="auth-error" role="alert">{passwordError}</p>}<button className="lime-button" type="submit" disabled={!valid || passwordLoading} aria-busy={passwordLoading}>{passwordLoading ? <ButtonLoader label="Securing your password" /> : <>{saved ? "Password changed" : "Change password"}<ProductIcon name={saved ? "check" : "arrow"} /></>}</button></form>
      <section className="security-sheet sessions-sheet"><header><div><h2>Signed-in devices</h2><p>Remove any session you do not recognise.</p></div><button className="customer-text-button" type="button" onClick={signOutOthers} disabled={!sessions || sessions.length <= 1}>Sign out other devices</button></header>{sessionError && <p className="auth-error" role="alert">{sessionError}</p>}{!sessions && !sessionError && <p>Loading your devices…</p>}{(sessions ?? []).map((session) => <article key={session.id}><span><ProductIcon name={session.device.includes("Android") || session.device.includes("iPhone") ? "phone" : "tech"} /></span><p><strong>{session.device}{session.current && <i>Current</i>}</strong><small>{session.place} · {session.seen}</small></p>{!session.current && <button type="button" onClick={() => removeSession(session.id)}>Remove</button>}</article>)}</section>
    </div>
  </div>;
}

type BrandTransaction = { id: string; type: "Funding" | "Creator payout" | "Refund" | "Fee"; campaign: string; date: string; amount: number; status: string };
const transactions: BrandTransaction[] = [
  { id: "CLP-0926-041", type: "Funding", campaign: "No long thing", date: "20 Sep 2026", amount: -500000, status: "Cleared" },
  { id: "VIEW-21904", type: "Creator payout", campaign: "No long thing", date: "20 Sep 2026", amount: -18400, status: "Settled" },
  { id: "VIEW-21871", type: "Creator payout", campaign: "No long thing", date: "19 Sep 2026", amount: -32100, status: "Settled" },
  { id: "REF-00812", type: "Refund", campaign: "Campus chop stories", date: "16 Sep 2026", amount: 42800, status: "Returned" },
  { id: "FEE-00419", type: "Fee", campaign: "No long thing", date: "14 Sep 2026", amount: -calculateFee(500000, BRAND_CAMPAIGN_FEE_RATE), status: "Settled" },
];

function BrandReceiptDocument({ selected, fullPage = false }: { selected: BrandTransaction; fullPage?: boolean }) {
  const ticketArt = selected.type === "Funding" ? "/assets/illustrations/clippit-icons/funding-pot.webp" : selected.type === "Refund" ? "/assets/illustrations/clippit-icons/withdraw-bank.webp" : selected.type === "Creator payout" ? "/assets/illustrations/clippit-icons/payout-wallet.webp" : "/assets/illustrations/clippit-icons/verified-proof.webp";
  const recipient = selected.type === "Funding" ? ["Clippit Campaign Pot", "Brand wallet reservation"] : selected.type === "Refund" ? ["Gbedu Records Ltd.", "Brand wallet"] : selected.type === "Fee" ? ["Clippit Services", "Campaign fee account"] : ["Verified creator payout pool", "Creator settlement"];
  const sender = selected.type === "Refund" ? ["Clippit Campaign Escrow", "Campaign account · 041"] : ["Gbedu Records Ltd.", "Wema Bank · 012***0193"];
  return <aside className={`transaction-ticket${fullPage ? " transaction-ticket--full" : ""}`}><ReceiptHeader title="Official transaction receipt" reference={selected.id} /><div className="transaction-ticket__subject"><span><Image src={ticketArt} width={82} height={82} alt="" /></span><p><small>{selected.type}</small><strong>{selected.amount > 0 ? "+" : "−"}{money(Math.abs(selected.amount))}</strong><em><ProductIcon name="check" />{selected.status}</em><time>{selected.date} · 15:07:13 WAT</time></p></div><div className="transaction-ticket__parties"><section><h2>Recipient</h2><p><strong>{recipient[0]}</strong><span>{recipient[1]}</span></p></section><section><h2>Sender</h2><p><strong>{sender[0]}</strong><span>{sender[1]}</span></p></section></div><section className="transaction-ticket__information"><h2>Transaction information</h2><dl><div><dt>Transaction type</dt><dd>{selected.type}</dd></div><div><dt>Transaction ID</dt><dd>{selected.id}</dd></div><div><dt>Session ID</dt><dd>100033260920115117010192295902</dd></div><div><dt>Campaign</dt><dd>{selected.campaign}</dd></div><div><dt>Ledger entry</dt><dd>LDG-2026-0920-041</dd></div><div><dt>Settlement currency</dt><dd>Nigerian naira</dd></div></dl></section><div className="transaction-ticket__verified"><ProductIcon name="shield" /><span><strong>Verify this receipt</strong><small>clippit.ng/verify/{selected.id} · Code 7A19-C2F4</small></span></div>{selected.campaign === "Campus chop stories" && <Link href="/brand/campaigns/campus-chop/report">Open closeout report<ProductIcon name="arrow" /></Link>}<button type="button" onClick={() => window.print()}>Download receipt<ProductIcon name="brief" /></button></aside>;
}

export function BrandTransactionsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState(transactions[0]);
  const visible = transactions.filter((item) => filter === "All" || item.type === filter);
  return <div className="brand-page customer-page brand-transactions-page">
    <ScreenHead title="Transactions" copy="Review wallet funding, campaign deductions, creator payouts and refunds." action={<div className="brand-transaction-actions"><Link className="brand-button brand-button--dark" href="/brand/wallet">Open wallet<ProductIcon name="wallet" /></Link><button className="brand-button" type="button" onClick={() => window.print()}>Export statement<ProductIcon name="brief" /></button></div>} />
    <section className="transaction-balance"><div><small>Money moved this month</small><strong><AnimatedNumber value={1080300} format="money" /></strong><span><ProductIcon name="brief" />Across all Brand wallet activity</span></div><dl><div><dt>Creator pots funded</dt><dd><AnimatedNumber value={850000} format="money" /></dd></div><div><dt>Paid to creators</dt><dd><AnimatedNumber value={187500} format="money" /></dd></div><div><dt>Returned</dt><dd><AnimatedNumber value={42800} format="money" /></dd></div></dl></section>
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
    <div className="closeout-grid"><section className="platform-delivery"><header><h2>Where the views came from</h2><p>Final platform readings.</p></header>{[["TikTok", 50, 437500, "tiktok"], ["Instagram", 22, 192500, "instagram"], ["YouTube", 12, 105000, "youtube"], ["Facebook", 9, 78750, "facebook"], ["X", 7, 61250, "x"]].map(([name, share, views, icon]) => <div key={String(name)}><span><ProductIcon name={icon as ProductIconName} /></span><p><strong>{name}</strong><small><AnimatedNumber value={Number(views)} format="compact" /> views</small></p><i><b style={{ width: `${share}%` }} /></i><em>{share}%</em></div>)}</section><section className="top-delivery"><header><h2>Top clips</h2><p>Highest verified delivery.</p></header>{[["KM", "Kemi Frames", 146200], ["NE", "Nana Edits", 121800], ["DD", "Deji Does It", 98700]].map(([initials, name, views], index) => <article key={String(name)}><b>{index + 1}</b><span>{initials}</span><p><strong>{name}</strong><small><AnimatedNumber value={Number(views)} format="compact" /> verified views</small></p></article>)}</section></div>
  </div>;
}

export function PublicProfileScreen() {
  const [state, setState] = useState<{ handle: string | null; isPublic: boolean; location: string | null; profile: PublicCreatorProfileOut | null } | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    creatorProfileApi.get().then(async (me) => {
      let publicProfile: PublicCreatorProfileOut | null = null;
      if (me.handle && me.public_profile) publicProfile = await publicProfilesApi.creator(me.handle).catch(() => null);
      setState({ handle: me.handle, isPublic: me.public_profile, location: me.location ?? null, profile: publicProfile ?? { handle: me.handle ?? "", display_name: me.display_name, photo_url: me.photo_url, bio: me.bio, interests: me.interests, stats: { approved_clips: 0, verified_views: 0 }, recent_work: [] } });
    }).catch((err) => setError(err instanceof ApiError ? err.detail : "We couldn't load your profile."));
  }, []);

  if (error) return <div className="dashboard-page customer-page"><ScreenHead title="Public profile" copy={error} back="/dashboard/settings" /></div>;
  if (!state?.profile) return <div className="dashboard-page"><ClippitLoader contained label="Loading your public profile" /></div>;

  const { profile, handle } = state;
  const stored: StoredProfile = { name: profile.display_name, bio: profile.bio ?? "", photo: profile.photo_url ?? "" };
  const initials = profile.display_name.split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "CL";
  const link = handle && typeof window !== "undefined" ? `${window.location.origin}/creators/${handle}` : "";
  const copy = async () => { if (!link) return; try { await navigator.clipboard.writeText(link); setCopied(true); window.setTimeout(() => setCopied(false), 1600); } catch { /* clipboard blocked */ } };

  return <div className="dashboard-page customer-page public-profile-page">
    <ScreenHead title="Public profile" copy={!handle ? "Pick a handle in Settings to get a shareable profile page." : !state.isPublic ? "Your profile is hidden. Brands can't open it until you make it public in Settings." : "Preview what brands see when they open your creator profile."} back="/dashboard/settings" action={<div className="profile-head-actions">{link && state.isPublic && <button type="button" onClick={copy}>{copied ? "Link copied" : "Copy profile link"}<ProductIcon name={copied ? "check" : "link"} /></button>}<Link href="/dashboard/settings#profile">{handle ? "Edit profile" : "Pick a handle"}<ProductIcon name="arrow" /></Link></div>} />
    <section className="public-passport"><div className="public-passport__cover"><Image src="/assets/photos/lagos-portrait.jpg" alt="" fill sizes="(max-width: 700px) 100vw, 70vw" priority /><span>Available for funded briefs</span></div><div className="public-passport__identity"><ProfileAvatar profile={stored} fallback={initials} className="public-avatar" /><div><small>{handle ? `@${handle}` : "No handle yet"}</small><h2>{profile.display_name}</h2><p>{profile.bio || "Add a bio in Settings so brands know what you make."}</p>{state.location && <span><ProductIcon name="source" />{state.location}</span>}</div><div className="public-proof"><ProductIcon name="shield" /><span><strong>Verified creator</strong><small>Views read from connected accounts</small></span></div></div><dl><div><dt>Verified views</dt><dd><AnimatedNumber value={profile.stats.verified_views} format="compact" /></dd></div><div><dt>Approved clips</dt><dd><AnimatedNumber value={profile.stats.approved_clips} /></dd></div><div><dt>Content lanes</dt><dd>{profile.interests.length}</dd></div></dl></section>
    <section className="profile-work"><header><div><h2>Recent campaign work</h2><p>Approved posts with verified platform readings.</p></div><span>{profile.interests.join(" · ")}</span></header>
      {!profile.recent_work.length ? <ClippitEmptyState className="profile-work__empty" size="compact" icon="camera" title="No approved work yet" copy="Clips appear here after a brand accepts them." /> : <div>{profile.recent_work.map((work) => <article key={`${work.campaign_slug}-${work.submitted_at}`}><div><Image src="/assets/video/creator-reaction-poster.jpg" alt="" fill sizes="(max-width: 700px) 92vw, 28vw" /><span>{platformLabel(work.platform)}</span></div><small>{work.brand_name ?? "Brand"}</small><h3>{work.campaign_title}</h3><p><ProductIcon name="clock" />{formatDate(work.submitted_at)}</p></article>)}</div>}
    </section>
  </div>;
}
