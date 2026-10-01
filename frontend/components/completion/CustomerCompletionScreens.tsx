"use client";
/* eslint-disable react/no-unescaped-entities */

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ButtonLoader, ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { authApi, clearTokens, getAccessToken, type UserOut } from "@/lib/api/auth";
import { ApiError, errorMessage } from "@/lib/api/client";
import { disputesApi, legalApi, publicProfilesApi, receiptsApi, supportApi, uploadsApi, type DisputeDetailOut, type DisputeOut, type DisputeType, type LegalDocumentOut, type PublicCreatorProfileOut, type PublicCreatorWork, type ReceiptVerifyOut, type TicketDetailOut, type TicketOut } from "@/lib/api/account";
import { earningsApi, type EarningRow } from "@/lib/api/earnings";
import { payoutsApi } from "@/lib/api/payouts";
import { creatorApi } from "@/lib/api/creator";
import { organisationsApi } from "@/lib/api/organisations";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";
import { socialApi } from "@/lib/api/social";
import { formatDate, formatDateTime, naira, platformLabel } from "@/lib/format";
import { BRAND_CANCELLATION_FEE_RATE, BRAND_TOP_UP_FEE_RATE, CREATOR_WITHDRAWAL_FEE_RATE, MINIMUM_WALLET_WITHDRAWAL, feePercentage } from "@/lib/fees";

const art = {
  proof: "/assets/illustrations/clippit-icons/verified-proof.webp",
  creator: "/assets/illustrations/clippit-icons/creator-camera.webp",
  wallet: "/assets/illustrations/clippit-icons/payout-wallet.webp",
  bank: "/assets/illustrations/clippit-icons/withdraw-bank.webp",
  brief: "/assets/illustrations/clippit-icons/campaign-brief.webp",
  review: "/assets/illustrations/clippit-icons/appeal-review.webp",
};

type Tone = "lime" | "gold" | "ink" | "paper" | "danger";

function Mark() {
  return <Image src="/assets/clippit-mark-light.png" width={38} height={38} alt="" priority />;
}

const subscribeToSessionPresence = () => () => undefined;

function useSessionPresence() {
  return useSyncExternalStore(
    subscribeToSessionPresence,
    () => Boolean(getAccessToken()),
    () => false,
  );
}

function ServiceFrame({ children, active = "Help" }: { children: ReactNode; active?: "Help" | "Support" | "Legal" | "Account" }) {
  const hasSession = useSessionPresence();
  const legalGuest = active === "Legal" && !hasSession;
  return <div className="completion-service">
    <header className="service-bar">
      <Link href="/" className="service-logo"><Mark /><strong>Clippit</strong></Link>
      <nav aria-label="Customer service navigation">
        <Link className={active === "Help" ? "is-active" : ""} href={legalGuest ? "/auth" : "/help"}>Help</Link>
        <Link className={active === "Support" ? "is-active" : ""} href={legalGuest ? "/auth" : "/support/tickets"}>Support</Link>
        <Link className={active === "Account" ? "is-active" : ""} href={legalGuest ? "/auth" : "/account/data"}>Account</Link>
        <Link className={active === "Legal" ? "is-active" : ""} href="/legal">Legal</Link>
      </nav>
      <Link className="service-workspace" href={hasSession ? "/dashboard" : "/auth"}>{hasSession ? "Open workspace" : "Sign in"}<ProductIcon name="arrow" /></Link>
    </header>
    <main>{children}</main>
  </div>;
}

function CompletionHead({ title, copy, back, kicker, action }: { title: string; copy?: string; back?: string; kicker?: string; action?: ReactNode }) {
  return <header className="completion-head">
    <div>
      {back && <Link className="completion-back" href={back}><ProductIcon name="chevron" />Back</Link>}
      {kicker && <span className="completion-kicker">{kicker}</span>}
      <h1>{title}</h1>
      {copy && <p>{copy}</p>}
    </div>
    {action}
  </header>;
}

function Status({ children, tone = "paper" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`completion-status completion-status--${tone}`}>{children}</span>;
}

function BigAction({ href, children, tone = "lime", icon = "arrow" }: { href: string; children: ReactNode; tone?: "lime" | "ink" | "gold"; icon?: ProductIconName }) {
  return <Link href={href} className={`completion-action completion-action--${tone}`}>{children}<ProductIcon name={icon} /></Link>;
}

function MiniArt({ src, alt = "", tone = "lime" }: { src: string; alt?: string; tone?: "lime" | "gold" | "paper" }) {
  return <div className={`completion-art completion-art--${tone}`}><i /><Image src={src} width={260} height={260} alt={alt} /></div>;
}

const helpTopics = [
  { icon: "campaigns" as const, title: "Campaigns", copy: "Joining, funding, rules and campaign status", slug: "how-campaigns-work" },
  { icon: "eye" as const, title: "Views and checks", copy: "Platform readings, reviews and corrections", slug: "how-views-are-checked" },
  { icon: "wallet" as const, title: "Money", copy: "Earnings, withdrawals, funding and refunds", slug: "money-and-payouts" },
  { icon: "link" as const, title: "Connected accounts", copy: "Connecting, reconnecting and permissions", slug: "connected-social-accounts" },
  { icon: "shield" as const, title: "Account and safety", copy: "Verification, security and your data", slug: "account-and-safety" },
  { icon: "brief" as const, title: "For brands", copy: "Briefs, reviews, billing and team access", slug: "brand-workspace" },
];

export function HelpCentreScreen() {
  const [query, setQuery] = useState("");
  const visible = helpTopics.filter((topic) => `${topic.title} ${topic.copy}`.toLowerCase().includes(query.toLowerCase()));
  return <ServiceFrame>
    <section className="help-hero">
      <div><Status tone="lime">Clippit support</Status><h1>What do you need help with?</h1><label><ProductIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search campaigns, payouts, reviews..." /><kbd>/</kbd></label></div>
      <MiniArt src={art.proof} />
    </section>
    <section className="service-content">
      <div className="topic-grid">{visible.map((topic) => <Link href={`/help/${topic.slug}`} key={topic.slug}><span><ProductIcon name={topic.icon} /></span><h2>{topic.title}</h2><p>{topic.copy}</p><ProductIcon name="arrow" /></Link>)}</div>
      {visible.length === 0 && <ClippitEmptyState className="completion-empty" size="compact" tone="gold" icon="search" title={`No guide matched “${query}”`} copy="Try a shorter phrase or send the support team a message." action={<BigAction href="/support/tickets/new">Contact support</BigAction>} />}
      <aside className="support-ribbon"><div><strong>Still stuck?</strong><span>Send the details once. Support can see the campaign, payout or transaction you attach.</span></div><BigAction href="/support/tickets/new" tone="ink">Start a support ticket</BigAction></aside>
    </section>
  </ServiceFrame>;
}

export function AccountDataScreen() {
  const [requested, setRequested] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [ticketId, setTicketId] = useState("");
  const requestExport = async () => {
    setRequesting(true);
    setRequestError("");
    try {
      const ticket = await supportApi.create({ category: "Privacy", subject: "Data export request", message: "Please prepare a copy of the personal data linked to my Clippit account and send the download link to my account email." });
      setTicketId(ticket.id);
      setRequested(true);
    } catch (err) {
      setRequestError(errorMessage(err, "We couldn't send your request. Try again."));
    } finally {
      setRequesting(false);
    }
  };
  const archiveItems = [
    ["person", "Profile", "Your account details and preferences"],
    ["campaigns", "Campaigns", "Joins, submissions and decisions"],
    ["wallet", "Money", "Earnings and withdrawal records"],
    ["brief", "Support", "Tickets, disputes and consents"],
  ] as const;
  return <ServiceFrame active="Account"><section className="service-content completion-page data-page"><CompletionHead title="Your data" copy="Download a copy of the information linked to your Clippit account." /><div className="data-vault">
    <section className="data-vault__request">
      <header><div className="vault-door"><span><ProductIcon name="shield" /></span><i /><i /><i /></div><div><Status tone="lime">Private archive</Status><h2>{requested ? "We’re preparing it" : "Your account, packed neatly"}</h2><p>{requested ? "We’ll email the download link when it is ready. The link expires after 24 hours." : "Request one ZIP file containing the account information available for export."}</p></div></header>
      <div className="data-vault__facts"><span><small>Format</small><strong>ZIP archive</strong></span><span><small>Usually ready</small><strong>Within 24 hours</strong></span><span><small>Link access</small><strong>24 hours</strong></span></div>
      {requested ? <div className="data-requested" role="status" aria-live="polite"><ProductIcon name="clock" /><span><strong>Request received</strong><small>We’ll send the link to your account email. <Link href={`/support/tickets/${ticketId}`}>Track the request</Link></small></span></div> : <>{requestError && <p className="auth-error" role="alert">{requestError}</p>}<button className="completion-submit" disabled={requesting} onClick={requestExport}>{requesting ? "Sending request…" : "Request my data"}<ProductIcon name="arrow" /></button></>}
    </section>
    <aside className="data-vault__contents"><header><span><ProductIcon name="brief" /></span><div><small>Inside the archive</small><h2>Four tidy folders</h2></div></header><div>{archiveItems.map(([icon, title, copy]) => <article key={title}><span><ProductIcon name={icon} /></span><p><strong>{title}</strong><small>{copy}</small></p><ProductIcon name="check" /></article>)}</div><footer><ProductIcon name="shield" /><span>Passwords and security secrets are never included.</span></footer></aside>
  </div><nav className="account-page-links" aria-label="More account options"><Link href="/dashboard/settings"><ProductIcon name="settings" /><span><strong>Account settings</strong><small>Profile, security and notifications</small></span><ProductIcon name="arrow" /></Link><Link href="/legal/privacy"><ProductIcon name="shield" /><span><strong>Privacy policy</strong><small>How Clippit uses account information</small></span><ProductIcon name="arrow" /></Link><Link href="/account/delete" className="is-danger"><ProductIcon name="person" /><span><strong>Delete account</strong><small>Check blockers and request deletion</small></span><ProductIcon name="arrow" /></Link></nav></section></ServiceFrame>;
}

export function DeleteAccountScreen() {
  const router = useRouter();
  const [confirmed, setConfirmed] = useState(false);
  const [stepPassword, setStepPassword] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [checks, setChecks] = useState<{ money: number; tickets: number; disputes: number } | null>(null);
  const [checksError, setChecksError] = useState("");

  useEffect(() => {
    authApi.me().then(async (me: UserOut) => {
      const [summary, tickets, disputes] = await Promise.all([
        me.role === "creator" ? earningsApi.summary() : Promise.resolve(null),
        supportApi.list("open"),
        disputesApi.list(),
      ]);
      setChecks({
        money: summary ? summary.payable + summary.in_hold + summary.processing : 0,
        tickets: tickets.length,
        disputes: disputes.filter((item) => item.status === "open" || item.status === "awaiting_customer").length,
      });
    }).catch((err) => setChecksError(errorMessage(err, "We couldn't verify whether your account has unresolved money or cases.")));
  }, []);

  const requestDeletion = async () => {
    if (!confirmed || !stepPassword) return;
    setDeleteLoading(true);
    setDeleteError("");
    try {
      const challenge = await authApi.requestStepUp({ action: "delete_account" });
      const stepUp = await authApi.verifyStepUp({ challenge_token: challenge.challenge_token, password: stepPassword });
      await authApi.deleteAccount({ step_up_token: stepUp.step_up_token });
      clearTokens();
      router.replace("/auth/sign-in");
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.detail : "Could not delete account. Try again.");
    } finally {
      setDeleteLoading(false);
    }
  };

  return <ServiceFrame active="Account"><section className="service-content completion-page"><CompletionHead back="/account/data" title="Delete account" copy="Check what must be settled before deletion can begin." /><div className="delete-layout"><section>{checksError ? <ClippitEmptyState tone="danger" icon="shield" title="We couldn't complete the safety check" copy={checksError} /> : !checks ? <p>Checking your account…</p> : <><h2>{checks.money > 0 || checks.tickets || checks.disputes ? "Check these first" : "Nothing is blocking deletion"}</h2>
      {checks.money > 0 ? <article><span><ProductIcon name="wallet" /></span><p><strong>{naira(checks.money)} hasn&apos;t been paid out yet</strong><small>Deletion is refused while earnings are payable, held or processing. Withdraw what&apos;s payable and wait for the rest to clear.</small></p><Link href="/dashboard/withdraw">Withdraw money</Link></article> : <article className="is-clear"><span><ProductIcon name="check" /></span><p><strong>No unsettled money</strong><small>Nothing is held, payable or processing.</small></p></article>}
      {checks.tickets > 0 && <article><span><ProductIcon name="brief" /></span><p><strong>{checks.tickets} support ticket{checks.tickets === 1 ? " is" : "s are"} open</strong><small>You&apos;ll lose access to replies once the account is deleted.</small></p><Link href="/support/tickets">Open tickets</Link></article>}
      {checks.disputes > 0 && <article><span><ProductIcon name="shield" /></span><p><strong>{checks.disputes} dispute{checks.disputes === 1 ? " is" : "s are"} still open</strong><small>Withdraw or wait for a decision before deleting.</small></p><Link href="/disputes">Open disputes</Link></article>}
    </>}</section><aside><MiniArt src={art.bank} tone="gold" /><h2>After the blockers are cleared</h2><p>Your public profile is hidden immediately. Required transaction and safety records are retained under the applicable policy; other eligible account data is deleted or anonymised.</p><label><input type="checkbox" checked={confirmed} disabled={!checks || !!checksError} onChange={(event) => setConfirmed(event.target.checked)} />I understand this cannot be undone.</label>{confirmed && <label className="delete-password-label"><span>Confirm your password to continue</span><input type="password" value={stepPassword} onChange={(event) => setStepPassword(event.target.value)} placeholder="Your current password" autoComplete="current-password" /></label>}{deleteError && <p className="auth-error" role="alert">{deleteError}</p>}<button disabled={!checks || !!checksError || !confirmed || !stepPassword || deleteLoading} aria-busy={deleteLoading} onClick={requestDeletion}>{deleteLoading ? <ButtonLoader label="Closing your account safely" /> : "Request account deletion"}</button></aside></div></section></ServiceFrame>;
}

const RECEIPT_TYPES: Record<string, string> = { payout: "Creator payout", funding: "Campaign funding", refund: "Campaign refund" };

export function ReceiptVerificationScreen({ reference }: { reference: string }) {
  const [receipt, setReceipt] = useState<ReceiptVerifyOut | null>(null);
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);
  useEffect(() => {
    receiptsApi.verify(reference).then(setReceipt).catch((err) => setError({ notFound: err instanceof ApiError && err.status === 404, message: errorMessage(err, "We couldn't check this receipt right now.") }));
  }, [reference]);

  if (error) return <ServiceFrame><section className="verify-receipt is-invalid"><div className="verify-radar"><i /><i /><i /><span><ProductIcon name="shield" /></span></div><Status tone="danger">{error.notFound ? "No matching record" : "Check unavailable"}</Status><h1>{error.notFound ? "We can't find this receipt." : "We couldn't check this receipt."}</h1><p>{error.notFound ? `No Clippit transaction has the reference ${reference}. Check the reference, and treat the receipt as unverified until it matches.` : error.message}</p><small>Clippit will never ask for a password or verification code on a receipt verification page.</small></section></ServiceFrame>;
  if (!receipt) return <ServiceFrame><section className="verify-receipt"><ClippitLoader contained compact label="Checking this receipt" /></section></ServiceFrame>;

  return <ServiceFrame><section className="verify-receipt"><div className="verify-radar"><i /><i /><i /><span><ProductIcon name="check" /></span></div><Status tone="lime">Authentic Clippit record</Status><h1>This receipt is valid.</h1><p>The reference matches a Clippit record. Compare the amount and date below with the receipt you were shown.</p><section><header><Mark /><div><strong>{receipt.issuer}</strong><span>Receipt verification</span></div></header><dl><div><dt>Reference</dt><dd>{receipt.reference}</dd></div><div><dt>Type</dt><dd>{RECEIPT_TYPES[receipt.type] ?? receipt.type}</dd></div><div><dt>Amount</dt><dd>{naira(receipt.amount)}</dd></div><div><dt>Status</dt><dd>{receipt.status}</dd></div><div><dt>Date</dt><dd>{formatDateTime(receipt.date)}</dd></div><div><dt>Record fingerprint</dt><dd>{receipt.digest.slice(0, 16).toUpperCase()}</dd></div></dl><footer><ProductIcon name="shield" />Checked {formatDateTime(new Date().toISOString())}</footer></section><small>Clippit will never ask for a password or verification code on a receipt verification page.</small></section></ServiceFrame>;
}

function CreatorReadinessScreen() {
  const [state, setState] = useState<{ user: UserOut; bank: BankAccountOut | null; connected: number } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const bank = bankDetailsApi.get().catch((err) => {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    });
    Promise.all([authApi.me(), bank, socialApi.accounts()])
      .then(([user, bank, accounts]) => setState({ user, bank, connected: accounts.filter((a) => a.connected).length }))
      .catch((err) => setError(errorMessage(err, "We couldn't verify your account readiness.")));
  }, []);
  if (error) return <div className="dashboard-page completion-workspace"><CompletionHead title="Account checks" copy={error} /></div>;
  if (!state) return <div className="dashboard-page"><ClippitLoader contained label="Checking your account" /></div>;
  const items = [
    { done: state.user.email_verified, title: "Email address confirmed", copy: "Needed to join campaigns, submit clips and withdraw.", href: "/auth/verify-email", cta: "Confirm email" },
    { done: state.connected > 0, title: "A social account connected", copy: "Proves you own the posts you submit and lets us read verified views.", href: "/dashboard/accounts", cta: "Connect an account" },
    { done: !!state.bank?.verified, title: "Payout account verified", copy: state.bank ? "Your bank confirmed the account name." : "Where your withdrawals land.", href: "/dashboard/payout-account", cta: state.bank ? "Verify account" : "Add account" },
  ];
  const doneCount = items.filter((item) => item.done).length;
  return <div className="dashboard-page completion-workspace"><CompletionHead title="Account checks" copy="What your account needs before you can earn and withdraw." action={<Status tone={doneCount === items.length ? "lime" : "gold"}>{doneCount}/{items.length} complete</Status>} /><section className="verification-status"><div className="status-orbit"><i /><i /><i /><span><ProductIcon name={doneCount === items.length ? "check" : "shield"} /></span><strong>{doneCount === items.length ? "Ready" : "Almost there"}</strong><small>{doneCount === items.length ? "You can join, submit and withdraw." : `${items.length - doneCount} step${items.length - doneCount === 1 ? "" : "s"} left`}</small></div><section>{items.map((item, index) => <article className={item.done ? "is-complete" : index === items.findIndex((i) => !i.done) ? "is-current" : ""} key={item.title}><span>{item.done ? <ProductIcon name="check" /> : index + 1}</span><p><strong>{item.title}</strong><small>{item.copy}</small></p>{item.done ? <Status tone="lime">Done</Status> : <Link href={item.href}>{item.cta}</Link>}</article>)}</section><aside><ProductIcon name="shield" /><div><strong>Identity document checks aren&apos;t required yet.</strong><span>If Clippit ever needs more, this page will tell you exactly what to send.</span></div></aside></section></div>;
}

export function CreatorVerificationScreen() { return <CreatorReadinessScreen />; }

export function CreatorIdentityScreen() { return <CreatorReadinessScreen />; }

export function CreatorDocumentsScreen() { return <CreatorReadinessScreen />; }

export function CreatorVerificationStatusScreen() { return <CreatorReadinessScreen />; }

function monthKey(iso: string) {
  const date = new Date(iso);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(key: string) {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export function EarningsStatementScreen() {
  const [rows, setRows] = useState<EarningRow[] | null>(null);
  const [error, setError] = useState("");
  const [range, setRange] = useState("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const all: EarningRow[] = [];
      for (let offset = 0; offset < 1000; offset += 100) {
        const page = await earningsApi.history({ limit: 100, offset });
        all.push(...page.items);
        if (all.length >= page.total || !page.items.length) break;
      }
      return all;
    })().then((all) => { if (!cancelled) setRows(all); }).catch((err) => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, []);

  const months = useMemo(() => Array.from(new Set((rows ?? []).map((row) => monthKey(row.date)))).sort().reverse(), [rows]);
  const visible = useMemo(() => (rows ?? []).filter((row) => range === "all" || monthKey(row.date) === range), [rows, range]);
  const total = visible.reduce((sum, row) => sum + row.amount, 0);

  if (error) return <div className="dashboard-page completion-workspace"><CompletionHead back="/dashboard/earnings" title="Earnings statement" copy={error} /></div>;
  if (!rows) return <div className="dashboard-page"><ClippitLoader contained label="Preparing your statement" /></div>;

  return <div className="dashboard-page completion-workspace"><CompletionHead back="/dashboard/earnings" title="Earnings statement" copy="Every earning entry, verified result and payout status." action={<button className="statement-download" onClick={() => window.print()} disabled={!visible.length}>Download statement<ProductIcon name="brief" /></button>} /><section className="statement-summary"><div><small>Statement period</small><select value={range} onChange={(event) => setRange(event.target.value)}><option value="all">All time</option>{months.map((key) => <option key={key} value={key}>{monthLabel(key)}</option>)}</select></div><div><small>Total earned</small><strong><AnimatedNumber value={total} format="money" /></strong></div><div><small>Entries</small><strong><AnimatedNumber value={visible.length} padStart={2} /></strong></div><MiniArt src={art.wallet} tone="gold" /></section><section className="statement-table"><header><span>Date</span><span>Campaign</span><span>Verified result</span><span>Amount</span><span>Status</span></header>{!visible.length && <ClippitEmptyState className="statement-table__empty" size="inline" tone="gold" icon="wallet" title="No earnings in this period" copy="Choose another period or check back after an approved clip starts earning." />}{visible.map((row) => <article key={row.id}><time>{formatDate(row.date, { day: "numeric", month: "short" })}</time><strong>{row.campaign_title}<small> · {row.clip}</small></strong><span>{(row.metric_type === "view" ? row.billable_views : row.billable_units).toLocaleString()} {row.metric_type}{(row.metric_type === "view" ? row.billable_views : row.billable_units) === 1 ? "" : "s"}</span><b>{naira(row.amount)}</b><Status tone={row.state === "Payable" ? "lime" : row.state === "Accrued" ? "gold" : "paper"}>{row.state === "Accrued" ? "On hold" : row.state}</Status></article>)}<footer><span>{range === "all" ? "All time" : monthLabel(range)} · generated {formatDate(new Date().toISOString())}</span><strong>{naira(total)}</strong></footer></section></div>;
}

export function PublicCreatorProfileScreen({ handle }: { handle: string }) {
  const [profile, setProfile] = useState<PublicCreatorProfileOut | null>(null);
  const [work, setWork] = useState<PublicCreatorWork[]>([]);
  const [workError, setWorkError] = useState("");
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);

  useEffect(() => {
    publicProfilesApi.creator(handle).then((data) => {
      setProfile(data);
      setWork(data.recent_work);
      publicProfilesApi.creatorClips(handle, 12)
        .then((items) => {
          setWork(items);
          setWorkError("");
        })
        .catch((err) => setWorkError(errorMessage(err, "Some recent work could not be loaded.")));
    }).catch((err) => setError({ notFound: err instanceof ApiError && err.status === 404, message: errorMessage(err) }));
  }, [handle]);

  if (error) return <ServiceFrame><section className="public-profile"><ClippitEmptyState className="completion-empty" tone="danger" icon="person" title={error.notFound ? `@${handle} isn't on Clippit` : "We couldn't load this profile"} copy={error.notFound ? "The handle may have changed, or the creator has made their profile private." : error.message} action={<BigAction href="/auth/sign-up">Create your Clippit profile</BigAction>} role="alert" /></section></ServiceFrame>;
  if (!profile) return <ServiceFrame><section className="public-profile"><ClippitLoader contained compact label="Loading creator profile" /></section></ServiceFrame>;

  return <ServiceFrame><section className="public-profile"><header><div className="profile-photo">{profile.photo_url ? <Image src={profile.photo_url} alt={profile.display_name} fill sizes="260px" unoptimized /> : <strong className="profile-photo__initials">{profile.display_name.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</strong>}</div><div><Status tone="lime"><ProductIcon name="shield" />Verified creator</Status><h1>{profile.display_name}</h1><p>@{profile.handle}</p>{profile.bio && <blockquote>{profile.bio}</blockquote>}<div>{profile.interests.map((lane) => <span key={lane}>{lane}</span>)}</div></div><aside><small>Verified views</small><strong><AnimatedNumber value={profile.stats.verified_views} format="compact" suffix=" views" /></strong><span>Across {profile.stats.approved_clips} approved Clippit clip{profile.stats.approved_clips === 1 ? "" : "s"}</span></aside></header><section className="profile-work"><div className="profile-work__head"><div><h2>Approved campaign work</h2><p>Only clips approved through Clippit appear here.</p></div><span>{profile.stats.approved_clips} clips</span></div>{workError && <p className="auth-error" role="alert">{workError}</p>}{!work.length && !workError ? <ClippitEmptyState className="profile-work__empty" size="compact" icon="camera" title="No approved campaign work yet" copy="Approved clips will appear here." /> : <div>{work.map((item) => <article key={`${item.campaign_slug}-${item.submitted_at}`}><div><Image src="/assets/photos/creator-studio-pexels-8359963.jpg" alt="" fill sizes="(max-width: 700px) 100vw, 33vw" /><span><ProductIcon name="play" /></span></div><p><strong>{item.campaign_title}</strong><small>{item.brand_name ?? "Brand"} · {platformLabel(item.platform)} · {formatDate(item.submitted_at)}</small></p></article>)}</div>}</section><footer><span><Mark /><strong>Profile verified by Clippit</strong></span><Link href="/auth/sign-up">Create your Clippit profile<ProductIcon name="arrow" /></Link></footer></section></ServiceFrame>;
}

type GuideSection = { title: string; body: string; points?: string[] };

const guideContent: Record<string, { title: string; summary: string; sections: GuideSection[] }> = {
  "how-campaigns-work": {
    title: "How campaigns work",
    summary: "The complete path from a funded brief to an approved creator payout.",
    sections: [
      { title: "Read the live brief before you act", body: "Every campaign shows its publishing platform, rate per 1,000 verified views, remaining pot, creator cap, minimum view threshold, required content and exclusions. A campaign may close on a date or stay open until its pot is exhausted." },
      { title: "Join before publishing", body: "A creator joins the open campaign with the account they intend to publish from. Joining does not guarantee approval or earnings; it records participation against the campaign rules that were live at that time." },
      { title: "Publish and submit the public post", body: "Publish from the connected account, keep the post public and submit its public URL. The post must belong to the connected creator account and match every mandatory requirement in the brief." },
      { title: "Clippit checks the evidence", body: "Clippit records the submitted post, requirement results and platform readings. Clear matches can be approved; uncertain or failed checks show the exact requirement that needs review or correction." },
      { title: "Approved work can earn", body: "Only approved clips earn. Billable views are limited by the campaign rate, minimum threshold, creator cap and remaining pot. A campaign stops allocating new earnings when it closes or its pot is exhausted." },
    ],
  },
  "how-views-are-checked": {
    title: "How views are checked",
    summary: "What counts, what does not count and where each reading comes from.",
    sections: [
      { title: "Views come from the publishing platform", body: "Clippit reads view totals from the creator's connected platform account. Screenshots, typed figures and views reported by another account do not replace a platform reading." },
      { title: "The first 1,000 views unlock earning", body: "A clip must reach at least 1,000 verified views. Payment is calculated in complete groups of 1,000; an unfinished group is carried into the next reading rather than rounded up." },
      { title: "Campaign limits are applied to every reading", body: "The creator cap and remaining campaign pot are hard limits. Verified views above either limit remain visible as performance, but they do not create earnings beyond the funded amount." },
      { title: "Readings stay attached to the earning entry", body: "Every earning entry keeps its platform, reading time, billable view count, rate and campaign reference so the amount can be explained and disputed." },
      { title: "A rejected check includes a reason", body: "A failed submission identifies the requirement that failed. Eligible creators can correct the post where the brief allows it or submit one appeal with supporting evidence." },
    ],
  },
  "money-and-payouts": {
    title: "Money, payouts and refunds",
    summary: "How naira moves through creator earnings and funded campaigns.",
    sections: [
      { title: "Creator earnings start with approved views", body: "An approved clip earns the campaign rate for each complete 1,000 billable views, subject to the creator cap and remaining pot. The earning screen shows the calculation and source reading." },
      { title: "New earnings have a five-day hold", body: "An earning remains on hold for five days before it becomes payable. A valid fraud, platform or dispute hold can pause release; the account must show the reason and next action." },
      { title: "Withdrawals use a verified Nigerian bank account", body: "Only payable earnings can be withdrawn. Clippit charges 7% of each withdrawal, and the confirmation screen shows the withdrawal amount, fee and amount reaching the bank before you confirm. Identity verification and a verified payout destination are required before the first transfer." },
      { title: "Brands see the full funding quote", body: "Clippit charges 15% of the creator pot for every brand campaign. Before payment, the funding quote shows the creator pot, Clippit campaign fee, any applicable tax and the total amount." },
      { title: "Unused campaign money follows the closeout record", body: "When a campaign closes, the closeout separates creator allocations, fees, unsettled amounts and the refundable unused balance. An eligible refund returns to the verified funding destination and receives its own transaction reference." },
      { title: "Clippit records money in Nigerian naira", body: "The current product supports Nigeria and Nigerian naira. Crypto, multi-currency balances and off-platform payout promises are not part of Clippit." },
    ],
  },
  "connected-social-accounts": {
    title: "Connected social accounts",
    summary: "Why an account is required and how Clippit handles platform access.",
    sections: [
      { title: "Connect the account you publish from", body: "The connected account proves ownership of the submitted post and lets Clippit read platform views. A submission from a different handle cannot be verified against the connection." },
      { title: "Clippit requests only the enabled permissions", body: "The connection screen must show the platform and permissions requested before redirecting to the provider. Clippit does not ask for your social password." },
      { title: "Reconnect when access expires", body: "A connected platform can expire or revoke access. When that happens, the account shows Reconnect required and view checks pause until the creator reconnects the account." },
      { title: "Disconnecting stops future readings", body: "Disconnecting removes Clippit's future access to the account. Existing campaign, submission, earning and audit records are retained where required to explain past decisions and money movements." },
    ],
  },
  "account-and-safety": {
    title: "Account and safety",
    summary: "Identity checks, account security, privacy controls and support.",
    sections: [
      { title: "Use one accurate account", body: "Keep your email, phone, public profile and legal identity accurate. Duplicate identities, impersonation and account sharing can pause campaigns, earnings or funding while the account is reviewed." },
      { title: "Verification happens before sensitive money actions", body: "Creators complete identity verification before their first withdrawal. Registered organisations complete business verification when required for funding limits, billing or risk review. Individual funders complete identity verification rather than business verification." },
      { title: "Protect sensitive changes", body: "Password, email, payout destination and account-deletion changes require a fresh security check. Review signed-in devices and remove any session you do not recognise." },
      { title: "Use support for questions and disputes for formal decisions", body: "A support ticket handles ordinary help. A dispute is for a formal review of an eligible verdict, earning, payout, funding order, refund or transaction and preserves the original record." },
      { title: "You can request access, correction or deletion", body: "The data screen provides an account export and deletion request. Some finance, safety and consent records may be retained where necessary for legal obligations, disputes or fraud prevention." },
    ],
  },
  "brand-workspace": {
    title: "Using the brand workspace",
    summary: "Create, fund, review and close a campaign without losing the money trail.",
    sections: [
      { title: "Build the complete brief", body: "Set the public campaign name, description, publishing platform, mandatory requirements, exclusions, source assets, rate, minimum views, creator cap, pot and closing rule. A campaign can use a date or remain open until the pot is exhausted." },
      { title: "Review the funding quote", body: "The funding quote shows the creator pot, Clippit's 15% campaign fee, any applicable tax and the total before payment. Funding must clear before the campaign can open to creators." },
      { title: "Review only uncertain submissions", body: "The review queue contains submissions that need a brand decision or appeal review. Every decision must identify the requirement and preserve the evidence used." },
      { title: "Follow verified delivery", body: "Campaign analytics separate total platform views, billable views, creator earnings, remaining pot and review outcomes. Activity records funding, opening, pauses, reviews and closeout." },
      { title: "Close and reconcile", body: "The closeout report fixes the final view, earning and pot totals. Eligible unused money is returned through the refund flow after payment-provider reconciliation." },
    ],
  },
};

export function ProductionHelpArticleScreen({ slug }: { slug: string }) {
  const guide = guideContent[slug] ?? guideContent["how-campaigns-work"];
  return <ServiceFrame><article className="article-shell"><CompletionHead back="/help" kicker="Help guide" title={guide.title} copy={guide.summary} /><div className="article-layout"><aside><strong>In this guide</strong>{guide.sections.map((section, index) => <a href={`#guide-${index + 1}`} key={section.title}>{index + 1}. {section.title}</a>)}<BigAction href="/support/tickets/new" tone="gold">Contact support</BigAction></aside><div className="article-copy"><div className="article-note"><ProductIcon name="shield" /><p><strong>These are the current Clippit product rules.</strong><span>Campaign-specific terms shown on a funded brief take precedence where they are more restrictive.</span></p></div>{guide.sections.map((section, index) => <section id={`guide-${index + 1}`} key={section.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{section.title}</h2><p>{section.body}</p>{section.points && <ul>{section.points.map((point) => <li key={point}>{point}</li>)}</ul>}</div></section>)}</div></div></article></ServiceFrame>;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const shortRef = (id: string) => id.slice(0, 8).toUpperCase();

function ticketTone(ticket: TicketOut): { tone: Tone; label: string } {
  if (ticket.status === "closed") return { tone: "paper", label: "Closed" };
  if (ticket.unread_count > 0) return { tone: "lime", label: "Support replied" };
  return { tone: "gold", label: "Awaiting support" };
}

async function uploadAll(files: File[], upload: (file: File) => Promise<{ id: string }>) {
  const ids: string[] = [];
  for (const file of files) ids.push((await upload(file)).id);
  return ids;
}

function ThreadMessages({ messages, you }: { messages: TicketDetailOut["messages"]; you: string }) {
  return <>{messages.map((message) => <article className={message.from_admin ? "is-support" : "is-customer"} key={message.id}><span>{message.from_admin ? <Mark /> : you}</span><div><header><strong>{message.from_admin ? "Clippit support" : "You"}</strong><time>{formatDateTime(message.created_at)}</time></header><p>{message.body}</p>{!!(message.attachment_upload_ids?.length || message.evidence_upload_ids?.length) && <small>{(message.attachment_upload_ids ?? message.evidence_upload_ids ?? []).length} attachment(s)</small>}</div></article>)}</>;
}

export function ProductionSupportTicketsScreen() {
  const [tickets, setTickets] = useState<TicketOut[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { supportApi.list().then(setTickets).catch((err) => setError(errorMessage(err))); }, []);
  const open = (tickets ?? []).filter((ticket) => ticket.status === "open").length;
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Support tickets" copy="Questions and replies attached to your account." action={<BigAction href="/support/tickets/new">New ticket</BigAction>} />{error ? <p className="auth-error" role="alert">{error}</p> : !tickets ? <ClippitLoader compact contained label="Opening your support history" note="Your conversations are being arranged by most recent activity." /> : tickets.length === 0 ? <ClippitEmptyState className="real-empty-panel" tone="gold" icon="brief" artSrc={art.review} title="No support tickets yet" copy="Search the help centre first. If the answer is not there, send us the issue and its reference." action={<><BigAction href="/help" tone="gold">Search help</BigAction><BigAction href="/support/tickets/new">Contact support</BigAction></>} /> : <div className="ticket-board ticket-board--real"><aside><strong>{String(open).padStart(2, "0")}</strong><span>Open tickets</span><b>{tickets.length} in total</b><MiniArt src={art.review} tone="gold" /></aside><section>{tickets.map((ticket) => { const state = ticketTone(ticket); return <Link href={`/support/tickets/${ticket.id}`} key={ticket.id} className="ticket-row"><span><ProductIcon name={ticket.category === "Money" ? "wallet" : ticket.category === "Connected accounts" ? "link" : "brief"} /></span><p><small>#{shortRef(ticket.id)} · {ticket.category}</small><strong>{ticket.subject}</strong><em>Updated {formatDateTime(ticket.updated_at)}</em></p><Status tone={state.tone}>{state.label}</Status><ProductIcon name="arrow" /></Link>; })}</section></div>}</section></ServiceFrame>;
}

const SUPPORT_CATEGORIES = ["Campaigns", "Money", "Connected accounts", "Account access", "Privacy"];

export function ProductionNewSupportTicketScreen() {
  const router = useRouter();
  const [category, setCategory] = useState("Campaigns");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reference, setReference] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      const ref = reference.trim();
      const attachmentIds = await uploadAll(files, uploadsApi.supportAttachment);
      const ticket = await supportApi.create({
        category,
        subject: subject.trim(),
        message: ref && !UUID_RE.test(ref) ? `${message.trim()}\n\nReference: ${ref}` : message.trim(),
        resource_type: ref && UUID_RE.test(ref) ? category.toLowerCase().replace(/\s+/g, "_").slice(0, 40) : null,
        resource_id: ref && UUID_RE.test(ref) ? ref : null,
        attachment_upload_ids: attachmentIds,
      });
      router.push(`/support/tickets/${ticket.id}`);
    } catch (err) {
      setError(errorMessage(err, "We couldn't send your ticket. Try again."));
      setSending(false);
    }
  };
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" title="Contact support" copy="Send the exact issue and attach the relevant Clippit reference." /><form className="completion-form support-form" onSubmit={submit}><div className="form-main"><fieldset><legend>What is this about?</legend><div className="choice-grid choice-grid--compact">{SUPPORT_CATEGORIES.map((item) => <label className={category === item ? "is-selected" : ""} key={item}><input type="radio" checked={category === item} onChange={() => setCategory(item)} /><ProductIcon name={item === "Money" ? "wallet" : item === "Campaigns" ? "campaigns" : item === "Connected accounts" ? "link" : "shield"} /><span>{item}</span></label>)}</div></fieldset><label><span>Subject</span><input required minLength={2} maxLength={200} value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="A short description of the problem" /></label><label><span>What happened?</span><textarea required rows={7} maxLength={5000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What did you expect, what happened and when?" /></label><label><span>Related Clippit reference <small>Optional</small></span><input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Campaign, submission, payout or transaction ID" /></label></div><aside className="form-aside"><div><ProductIcon name="upload" /><strong>{files.length ? `${files.length} file${files.length === 1 ? "" : "s"} ready` : "Add evidence"}</strong><span>Images or screen recordings · up to 10 files</span><input type="file" multiple accept="image/*,video/*" onChange={(event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.target.files ?? []).slice(0, 10))} /></div><p><ProductIcon name="shield" />Never upload a password, one-time code or full card number.</p>{error && <p className="auth-error" role="alert">{error}</p>}<button className="completion-submit" type="submit" disabled={sending || subject.trim().length < 2 || !message.trim()}>{sending ? "Sending…" : "Send to support"}<ProductIcon name="arrow" /></button></aside></form></section></ServiceFrame>;
}

export function ProductionSupportTicketDetailScreen({ id }: { id: string }) {
  const [ticket, setTicket] = useState<TicketDetailOut | null>(null);
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  useEffect(() => {
    supportApi.get(id).then(setTicket).catch((err) => setError({ notFound: err instanceof ApiError && (err.status === 404 || err.status === 403 || err.status === 422), message: errorMessage(err) }));
  }, [id]);
  if (error) return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" title={error.notFound ? "Ticket not found" : "We couldn't open this ticket"} copy={error.notFound ? "This ticket doesn't exist or belongs to another account." : error.message} /><ClippitEmptyState className="real-empty-panel real-empty-panel--compact" size="compact" tone="danger" icon="brief" artSrc={art.review} title={error.notFound ? "This ticket is not available" : "This ticket could not be opened"} copy={error.notFound ? "It may have been removed or it belongs to another account." : error.message} action={<><BigAction href="/support/tickets" tone="gold">Ticket list</BigAction><BigAction href="/support/tickets/new">New ticket</BigAction></>} role="alert" /></section></ServiceFrame>;
  if (!ticket) return <ServiceFrame active="Support"><section className="service-content completion-page"><ClippitLoader contained compact label="Opening your ticket" /></section></ServiceFrame>;
  const closed = ticket.status === "closed";
  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!reply.trim()) return;
    setBusy(true);
    setActionError("");
    try { setTicket(await supportApi.reply(ticket.id, reply.trim())); setReply(""); }
    catch (err) { setActionError(errorMessage(err)); }
    finally { setBusy(false); }
  };
  const toggle = async () => {
    setBusy(true);
    setActionError("");
    try { const updated = closed ? await supportApi.reopen(ticket.id) : await supportApi.close(ticket.id); setTicket({ ...ticket, ...updated }); }
    catch (err) { setActionError(errorMessage(err)); }
    finally { setBusy(false); }
  };
  const state = ticketTone(ticket);
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" kicker={`#${shortRef(ticket.id)}`} title={ticket.subject} action={<Status tone={state.tone}>{state.label}</Status>} /><div className="thread-layout"><section className="message-thread"><div className="thread-day">{formatDate(ticket.created_at, { day: "numeric", month: "long", year: "numeric" })}</div><ThreadMessages messages={ticket.messages} you="YOU" />{actionError && <p className="auth-error" role="alert">{actionError}</p>}{closed ? <p className="thread-closed">This ticket is closed. Reopen it to add more information.</p> : <form onSubmit={send}><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Add more information" rows={4} maxLength={5000} /><div><span /><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Sending…" : "Send reply"}<ProductIcon name="arrow" /></button></div></form>}</section><aside className="case-facts"><h2>Ticket details</h2><dl><div><dt>Status</dt><dd>{closed ? `Closed ${formatDate(ticket.closed_at)}` : "Open"}</dd></div><div><dt>Category</dt><dd>{ticket.category}</dd></div><div><dt>Priority</dt><dd>{ticket.priority}</dd></div><div><dt>Created</dt><dd>{formatDate(ticket.created_at)}</dd></div></dl><button type="button" className="customer-text-button" disabled={busy} onClick={toggle}>{closed ? "Reopen ticket" : "Close ticket"}</button></aside></div></section></ServiceFrame>;
}

const DISPUTE_TYPES: Array<{ type: DisputeType; label: string; copy: string; icon: ProductIconName }> = [
  { type: "earning_entry", label: "Earning", copy: "Amount, view reading or hold", icon: "wallet" },
  { type: "payout", label: "Payout", copy: "Failed or missing transfer", icon: "bank" },
  { type: "submission_verdict", label: "Submission verdict", copy: "Escalate after an appeal", icon: "play" },
  { type: "funding_order", label: "Campaign funding", copy: "Missing or incorrect campaign payment", icon: "campaigns" },
  { type: "refund", label: "Refund", copy: "Returned campaign balance", icon: "wallet" },
];
const DISPUTE_LABEL: Record<string, string> = { earning_entry: "Earning", payout: "Payout", submission_verdict: "Submission verdict", funding_order: "Campaign funding", refund: "Refund" };

function disputeTone(item: DisputeOut): { tone: Tone; label: string } {
  if (item.status === "awaiting_customer") return { tone: "gold", label: "Needs your reply" };
  if (item.status === "resolved") return { tone: item.resolution === "denied" ? "paper" : "lime", label: item.resolution ? `Resolved · ${item.resolution}` : "Resolved" };
  if (item.status === "withdrawn") return { tone: "paper", label: "Withdrawn" };
  return { tone: "gold", label: "Under review" };
}

export function ProductionDisputesScreen() {
  const [cases, setCases] = useState<DisputeOut[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { disputesApi.list().then(setCases).catch((err) => setError(errorMessage(err))); }, []);
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Disputes" copy="Formal reviews of eligible decisions and money records." action={<BigAction href="/disputes/new">Open a dispute</BigAction>} />{error ? <p className="auth-error" role="alert">{error}</p> : !cases ? <ClippitLoader compact contained label="Opening your cases" /> : cases.length === 0 ? <ClippitEmptyState className="real-empty-panel" icon="shield" artSrc={art.proof} title="No disputes open" copy="Use support for ordinary questions. Open a dispute when you need a formal review of an earning, payout or submission decision." action={<><BigAction href="/support/tickets/new" tone="gold">Ask support</BigAction><BigAction href="/disputes/new">Open a dispute</BigAction></>} /> : <div className="dispute-ledger"><header><span>Case</span><span>Value</span><span>Status</span><span>Deadline</span></header>{cases.map((item) => { const state = disputeTone(item); return <Link href={`/disputes/${item.id}`} key={item.id}><p><small>#{shortRef(item.id)}</small><strong>{DISPUTE_LABEL[item.type] ?? item.type} · {shortRef(item.resource_id)}</strong></p><b>{item.amount_at_risk ? naira(item.amount_at_risk) : "No money held"}</b><Status tone={state.tone}>{state.label}</Status><time>{item.status === "open" || item.status === "awaiting_customer" ? `Decision by ${formatDate(item.deadline_at, { day: "numeric", month: "short" })}` : formatDate(item.resolved_at ?? item.updated_at, { day: "numeric", month: "short" })}</time><ProductIcon name="arrow" /></Link>; })}</div>}</section></ServiceFrame>;
}

type DisputeOption = { id: string; label: string; detail: string };

export function ProductionNewDisputeScreen() {
  const router = useRouter();
  const [type, setType] = useState<DisputeType>("earning_entry");
  const [options, setOptions] = useState<Record<string, DisputeOption[]> | null>(null);
  const [accountRole, setAccountRole] = useState<UserOut["role"] | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [claim, setClaim] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const presetType = params.get("type") as DisputeType | null;
    const presetResource = params.get("resource");
    authApi.me().then(async (user) => {
      setAccountRole(user.role);
      if (user.role === "organisation") {
        const organisationTransactions = (await organisationsApi.transactions({ limit: 100 })).items;
        setOptions({
          funding_order: organisationTransactions.filter((row) => row.kind === "funding").map((row) => ({ id: row.id, label: `${naira(row.amount)} · ${row.campaign_title}`, detail: `${row.status} · ${row.reference} · ${formatDate(row.created_at)}` })),
          refund: organisationTransactions.filter((row) => row.kind === "refund").map((row) => ({ id: row.id, label: `${naira(row.amount)} · ${row.campaign_title}`, detail: `${row.status} · ${row.reference} · ${formatDate(row.created_at)}` })),
        });
        setType(presetType === "refund" ? "refund" : "funding_order");
      } else {
        const [earnings, payouts, clips] = await Promise.all([
          earningsApi.history({ limit: 50 }).then((data) => data.items),
          payoutsApi.list({ limit: 30 }).then((data) => data.items),
          creatorApi.clips().then((data) => data.items),
        ]);
        setOptions({
          earning_entry: earnings.map((row) => ({ id: row.id, label: `${naira(row.amount)} · ${row.campaign_title}`, detail: `${row.clip} · ${formatDate(row.date)} · ${row.state}` })),
          payout: payouts.map((payout) => ({ id: payout.id, label: `${naira(payout.amount)} · ${payout.reference}`, detail: `${payout.status} · ${formatDate(payout.initiated_at)}` })),
          submission_verdict: clips.map((clip) => ({ id: clip.id, label: clip.title || clip.campaign_title, detail: `${clip.label} · ${platformLabel(clip.platform)} · ${formatDate(clip.submitted_at)}` })),
        });
        if (presetType && ["earning_entry", "payout", "submission_verdict"].includes(presetType)) setType(presetType);
      }
      if (presetResource) setResourceId(presetResource);
    }).catch((err) => setOptionsError(errorMessage(err, "We couldn't load the records available for dispute.")));
  }, []);

  const availableTypes = DISPUTE_TYPES.filter((item) => accountRole === "organisation" ? ["funding_order", "refund"].includes(item.type) : ["earning_entry", "payout", "submission_verdict"].includes(item.type));
  const list = options?.[type] ?? [];
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      const created = await disputesApi.create({ type, resource_id: resourceId, reason: claim.trim() });
      router.push(`/disputes/${created.id}`);
    } catch (err) {
      setError(errorMessage(err, "We couldn't open this dispute. Try again."));
      setSending(false);
    }
  };

  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" title="Open a dispute" copy="Pick the exact record so the original evidence stays attached." />{optionsError ? <ClippitEmptyState tone="danger" icon="shield" title="Your eligible records could not be loaded" copy={optionsError} /> : <form className="completion-form" onSubmit={submit}><div className="form-main"><fieldset><legend>What should be reviewed?</legend><div className="choice-grid">{availableTypes.map((item) => <label className={type === item.type ? "is-selected" : ""} key={item.type}><input type="radio" checked={type === item.type} onChange={() => { setType(item.type); setResourceId(""); }} /><ProductIcon name={item.icon} /><span>{item.label}</span><small>{item.copy}</small></label>)}</div></fieldset>
    <label><span>Which record?</span>{!options ? <input disabled placeholder="Loading your records…" /> : list.length ? <select required value={resourceId} onChange={(event) => setResourceId(event.target.value)}><option value="">Choose a record</option>{list.map((option) => <option key={option.id} value={option.id}>{option.label} — {option.detail}</option>)}{resourceId && !list.some((option) => option.id === resourceId) && <option value={resourceId}>Record {shortRef(resourceId)}</option>}</select> : <input disabled placeholder={`You have no ${DISPUTE_TYPES.find((item) => item.type === type)?.label.toLowerCase()} records to dispute yet`} />}</label>
    <label><span>What decision is incorrect?</span><textarea required minLength={20} maxLength={2000} rows={7} value={claim} onChange={(event) => setClaim(event.target.value)} placeholder="Explain the record, the issue and the outcome you are requesting." /><small>{claim.trim().length}/2000 · minimum 20</small></label></div><aside className="form-aside"><p><ProductIcon name="shield" />Submitting a dispute preserves the original decision and evidence. You can add screenshots to the case after it opens.</p><p><ProductIcon name="clock" />Deadlines depend on the record type and are enforced by the server.</p>{error && <p className="auth-error" role="alert">{error}</p>}<button className="completion-submit" type="submit" disabled={sending || !resourceId || claim.trim().length < 20}>{sending ? "Submitting…" : "Submit dispute"}<ProductIcon name="arrow" /></button></aside></form>}</section></ServiceFrame>;
}

export function ProductionDisputeDetailScreen({ id }: { id: string }) {
  const [item, setItem] = useState<DisputeDetailOut | null>(null);
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [now] = useState(() => Date.now());
  useEffect(() => {
    disputesApi.get(id).then(setItem).catch((err) => setError({ notFound: err instanceof ApiError && (err.status === 404 || err.status === 403 || err.status === 422), message: errorMessage(err) }));
  }, [id]);
  if (error) return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" title={error.notFound ? "Dispute not found" : "We couldn't open this case"} copy={error.notFound ? "This case doesn't exist or belongs to another account." : error.message} /><ClippitEmptyState className="real-empty-panel real-empty-panel--compact" size="compact" tone="danger" icon="shield" artSrc={art.proof} title={error.notFound ? "This dispute is not available" : "This dispute could not be opened"} copy={error.notFound ? "It may have been removed or it belongs to another account." : error.message} action={<BigAction href="/disputes">Open disputes</BigAction>} role="alert" /></section></ServiceFrame>;
  if (!item) return <ServiceFrame active="Support"><section className="service-content completion-page"><ClippitLoader contained compact label="Opening your case" /></section></ServiceFrame>;
  const active = item.status === "open" || item.status === "awaiting_customer";
  const state = disputeTone(item);
  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!reply.trim()) return;
    setBusy(true);
    setActionError("");
    try {
      const evidence = await uploadAll(files, uploadsApi.evidence);
      setItem(await disputesApi.reply(item.id, reply.trim(), evidence));
      setReply("");
      setFiles([]);
    } catch (err) { setActionError(errorMessage(err)); }
    finally { setBusy(false); }
  };
  const withdraw = async () => {
    if (!window.confirm("Withdraw this dispute? The original decision stands.")) return;
    setBusy(true);
    try { const updated = await disputesApi.withdraw(item.id); setItem({ ...item, ...updated }); }
    catch (err) { setActionError(errorMessage(err)); }
    finally { setBusy(false); }
  };
  const deadline = new Date(item.deadline_at);
  const daysLeft = Math.max(0, Math.ceil((deadline.getTime() - now) / 86400000));
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" kicker={`#${shortRef(item.id)}`} title={`${DISPUTE_LABEL[item.type] ?? item.type} · ${shortRef(item.resource_id)}`} action={<Status tone={state.tone}>{state.label}</Status>} /><div className="dispute-case"><section className="case-timeline message-thread"><article className="is-current"><span><ProductIcon name="brief" /></span><div><small>{formatDateTime(item.created_at)}</small><h2>Your claim</h2><p>{item.reason}</p></div></article><ThreadMessages messages={item.messages} you="YOU" />{item.resolution_note && <article><span><ProductIcon name="check" /></span><div><small>{formatDateTime(item.resolved_at)}</small><h2>Decision: {item.resolution}</h2><p>{item.resolution_note}</p></div></article>}{actionError && <p className="auth-error" role="alert">{actionError}</p>}{active && <form onSubmit={send}><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder={item.status === "awaiting_customer" ? "Reply with the information requested" : "Add more information"} rows={4} maxLength={5000} /><div><label className="customer-text-button"><ProductIcon name="upload" />{files.length ? `${files.length} file(s)` : "Attach evidence"}<input type="file" multiple hidden accept="image/*,video/*" onChange={(event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.target.files ?? []).slice(0, 10))} /></label><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Sending…" : "Send"}<ProductIcon name="arrow" /></button></div></form>}</section><aside className="decision-clock">{active ? <><span>Decision due</span><strong>{deadline.getDate()}</strong><b>{deadline.toLocaleDateString("en-GB", { month: "long" })}</b><small>{daysLeft} day{daysLeft === 1 ? "" : "s"} remaining</small></> : <><span>Case</span><strong className="decision-clock__word">{state.label}</strong></>}<dl><div><dt>Money at stake</dt><dd>{item.amount_at_risk ? naira(item.amount_at_risk) : "None"}</dd></div><div><dt>Case type</dt><dd>{DISPUTE_LABEL[item.type] ?? item.type}</dd></div><div><dt>Opened</dt><dd>{formatDate(item.created_at)}</dd></div></dl>{active && <button type="button" className="customer-text-button" disabled={busy} onClick={withdraw}>Withdraw dispute</button>}</aside></div></section></ServiceFrame>;
}

type LegalSection = { title: string; paragraphs: string[]; points?: string[] };
type LegalDocument = { slug: string; title: string; summary: string; version: string; date: string; sections: LegalSection[] };

const productionLegalDocs: LegalDocument[] = [
  { slug: "terms", title: "Terms of use", summary: "The agreement for creator, funder and brand accounts on Clippit.", version: "1.0", date: "Effective 22 September 2026", sections: [
    { title: "Agreement and eligibility", paragraphs: ["These Terms govern access to Clippit's website, creator workspace, brand workspace, campaign marketplace, verification and money features. By creating an account or using a funded campaign, you agree to these Terms and any campaign-specific terms shown before you act.", "You must be at least 18 years old or the age of legal capacity where you live, use accurate information and be legally able to enter this agreement. The current service is intended for users and transactions supported in Nigeria."] },
    { title: "Accounts, roles and verification", paragraphs: ["A person may use a creator account or fund content as an individual. An organisation account must be managed by someone authorised to act for it. Keep sign-in details secure and tell support promptly about unauthorised access.", "Clippit may require identity verification before withdrawals and business verification for organisation funding, billing, risk limits or other sensitive actions. Verification does not endorse a user's content, business or future performance."] },
    { title: "Campaigns and submissions", paragraphs: ["Brands are responsible for lawful, accurate briefs, sufficient rights to supplied assets and clear mandatory requirements. Creators are responsible for original, lawful posts submitted from their connected accounts. Joining a campaign does not guarantee approval or payment.", "The rules displayed on the funded campaign govern platform, content requirements, exclusions, rate, minimum views, creator cap, pot and any closing date. Material payout rules cannot be changed for live participation without preserving the version accepted by affected users."] },
    { title: "Verified views and earnings", paragraphs: ["Only views read from an eligible connected platform account count. A clip must be approved and reach the campaign minimum. Earnings use complete groups of 1,000 billable views and remain subject to creator caps and the remaining funded pot.", "New creator earnings are held for five days before becoming payable. A documented fraud, platform, dispute or compliance hold may delay release. The earning record must show the reason and available next step."] },
    { title: "Funding, fees, payouts and refunds", paragraphs: ["A brand pays a Clippit campaign fee equal to 15% of the creator pot for each campaign. Adding money to a live campaign carries a 2.5% top-up fee. Before confirmation, Clippit shows the amount, fee, applicable tax and total.", `Creator wallet withdrawals carry a ${feePercentage(CREATOR_WITHDRAWAL_FEE_RATE)}% Clippit fee and require at least ${new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(MINIMUM_WALLET_WITHDRAWAL)}. Brand wallet withdrawals have no Clippit withdrawal fee. Manually cancelling a campaign carries a ${feePercentage(BRAND_CANCELLATION_FEE_RATE)}% fee on the refundable unused balance. Recognised creator earnings cannot be reversed.`] },
    { title: "Content and licence", paragraphs: ["Creators retain ownership of their content. They grant Clippit the limited rights needed to host evidence, verify a submission, operate the campaign, resolve disputes and display approved portfolio work where the creator has enabled public display.", "A brand receives only the usage rights expressly stated in the applicable campaign terms. Funding a campaign does not automatically transfer copyright or unrestricted advertising rights."] },
    { title: "Prohibited use and enforcement", paragraphs: ["Do not manipulate views, submit another person's post, impersonate a person or business, evade account limits, fund unlawful content, misuse payment systems, scrape private data, upload malware or interfere with platform checks.", "Clippit may restrict a feature, hold a money action, remove content, suspend an account or close a campaign where reasonably necessary for safety, fraud prevention, legal compliance or enforcement. Records needed for money, disputes and audit may be retained after account closure."] },
    { title: "Complaints, law and contact", paragraphs: ["Use support for ordinary problems and the dispute flow for an eligible formal review. Nothing in these Terms removes rights that cannot lawfully be excluded under Nigerian consumer law.", "These Terms are governed by the laws of the Federal Republic of Nigeria. Contact support through the in-product support centre for questions or notices."] },
  ] },
  { slug: "privacy", title: "Privacy policy", summary: "The personal data Clippit uses, why it is used and the choices available to you.", version: "1.0", date: "Effective 22 September 2026", sections: [
    { title: "Who this policy covers", paragraphs: ["This policy applies when Clippit processes personal data for visitors, creators, individual funders, organisation representatives and support contacts. Clippit acts as the data controller for the product data described here. A connected social platform and payment or verification provider may also act under its own privacy notice."] },
    { title: "Data we collect", paragraphs: ["Account and profile data includes name, email, phone, location, role, photo, bio and preferences. Verification data can include legal identity, date of birth, address, identity document, face check, business registration and authorised-representative information.", "Product data includes campaigns, briefs, posts, submission evidence, requirement results, platform readings, support messages, disputes and consent records. Money data includes masked bank details, funding orders, payout and refund references, invoices and ledger entries. Security data includes device, session, network, audit and fraud signals."] },
    { title: "Why we use data", paragraphs: ["We use data to create and secure accounts; connect platforms; operate campaigns; verify posts and views; calculate earnings; process funding, withdrawals and refunds; provide support; prevent fraud; keep required records; and improve reliability.", "Depending on the activity, the lawful basis may be performance of a contract, compliance with a legal obligation, legitimate interests such as security and fraud prevention, or consent where the law requires it. Withdrawing consent does not invalidate processing already carried out lawfully."] },
    { title: "Social, payment and verification providers", paragraphs: ["When you connect a social account, the provider sends the authorised account identity, tokens and eligible metrics. Clippit stores access credentials securely and uses them only for the enabled connection purposes.", "Payment and identity providers receive the information needed to resolve a bank account, collect campaign funds, transfer a payout, return a refund or complete verification. Clippit should not collect a full card number directly when a hosted provider checkout is used."] },
    { title: "Sharing and international processing", paragraphs: ["We share data only with service providers, connected platforms, payment and verification partners, professional advisers, authorities where lawfully required, and parties to a campaign where the product clearly shows the disclosure. We do not sell personal data.", "Where data is processed outside Nigeria, Clippit must use an approved transfer basis and safeguards appropriate to the destination and data involved."] },
    { title: "Retention and security", paragraphs: ["Profile and operational data is kept while the account is active and then deleted or anonymised when no longer needed. Finance, consent, fraud, dispute and legal records may be kept longer where necessary to meet a lawful retention, establish a claim or protect the service.", "Clippit uses access controls, encryption, audit logs, separation of public and restricted media, secure provider credentials and incident procedures. No service can guarantee absolute security; report suspected account compromise through support."] },
    { title: "Your rights", paragraphs: ["Under the Nigeria Data Protection Act 2023, applicable rights can include being informed, access, correction, objection, restriction, portability, erasure, complaint to the supervisory authority and protection in relation to qualifying automated decisions.", "Use Your data to request an export, update profile information directly, or contact support for another privacy request. Clippit may verify identity and may retain information where a lawful exception applies."], points: ["Request access or a portable copy", "Correct inaccurate personal data", "Object to or restrict qualifying processing", "Request deletion where no lawful retention applies", "Complain to the Nigeria Data Protection Commission"] },
    { title: "Automated checks, children and contact", paragraphs: ["Automated systems may compare a submission with campaign requirements or identify risk. A failed or uncertain result must provide a reason and an available human review or appeal where the decision materially affects eligibility or money.", "Clippit is not intended for children under 18. Privacy questions and rights requests can be submitted through the support centre. You may also contact the Nigeria Data Protection Commission through its official website."] },
  ] },
  { slug: "community-rules", title: "Community rules", summary: "The content and conduct required from everyone using Clippit.", version: "1.0", date: "Effective 22 September 2026", sections: [
    { title: "Use your real account", paragraphs: ["Do not impersonate another creator, organisation or representative; share verification credentials; create duplicate identities to evade limits; or submit a social account you do not control."] },
    { title: "Publish authentic work", paragraphs: ["Submit original content or content you are authorised to use. Do not buy or automate views, recycle another person's post, falsify insights, conceal sponsorship disclosures required by law or misrepresent where a post was published."] },
    { title: "Keep content lawful and safe", paragraphs: ["Do not fund or submit content that is illegal, exploitative, hateful, harassing, sexually exploitative, dangerously deceptive, privacy-invasive or designed to facilitate fraud. Do not expose another person's private identity or financial information."] },
    { title: "Respect intellectual property", paragraphs: ["Campaign assets must be supplied with the rights needed for the brief. Creators must have the rights to music, footage, images and other material in a submission. A rights complaint can pause a campaign, submission or payout while evidence is reviewed."] },
    { title: "Brands must write reviewable briefs", paragraphs: ["Requirements must be specific, lawful and visible before a creator joins. A brand cannot reject approved work for an unstated preference or demand off-platform work as a condition of releasing Clippit earnings."] },
    { title: "Enforcement and appeal", paragraphs: ["Clippit may remove content, limit features, hold an affected money action, close a campaign or suspend an account in proportion to the issue. The product must provide the reason and the applicable correction, appeal or dispute route."] },
  ] },
  { slug: "campaign-funding", title: "Campaign funding terms", summary: "The rules for pots, rates, creator allocations, fees, closeout and refunds.", version: "1.0", date: "Effective 22 September 2026", sections: [
    { title: "Funding order", paragraphs: ["Each brand campaign carries a Clippit campaign fee equal to 15% of its creator pot. Before payment, the funding quote identifies the campaign, creator pot, campaign fee, applicable tax, total, currency, payment method, expiry and terms version. The campaign opens only after funds clear and the required checks pass.", `Adding money to a live campaign carries a ${feePercentage(BRAND_TOP_UP_FEE_RATE)}% fee. A top-up increases available campaign money but does not change the live rate or campaign requirements.`] },
    { title: "Pot, rate and limits", paragraphs: ["The pot is the maximum campaign money available for creator allocations. The rate applies to complete groups of 1,000 verified, billable views after the minimum threshold. A creator cap and the remaining pot are hard limits."] },
    { title: "Campaign duration", paragraphs: ["A brand can set a closing date or choose no fixed duration. A campaign without a closing date remains open only while it is otherwise eligible and has available pot; it does not receive an automatic hidden deadline."] },
    { title: "Submission decisions", paragraphs: ["Only approved submissions can earn. A rejection or correction request must identify the failed requirement. Review decisions and appeals preserve the original evidence and cannot silently rewrite past versions."] },
    { title: "Allocations and five-day hold", paragraphs: ["Billable views reserve creator earnings against the pot. Newly accrued earnings remain on hold for five days before becoming payable, subject to a documented fraud, platform, legal or dispute hold."] },
    { title: "Closeout and refund", paragraphs: ["At closeout, Clippit records the creator pot, campaign fee, creator earnings, unsettled allocations, verified views and unused creator-pot balance separately. Only the eligible reconciled unused creator-pot balance is refundable. The refund returns through an approved destination and receives a separate reference."] },
    { title: "Cancellations and payment disputes", paragraphs: [`A funded campaign cannot be deleted as if it never existed. Manual cancellation follows closeout and carries a ${feePercentage(BRAND_CANCELLATION_FEE_RATE)}% fee on the eligible unused balance. Recognised creator earnings are not clawed back.`, "A payment dispute may pause opening, allocations or refunds while the money record is reconciled."] },
    { title: "Records and questions", paragraphs: ["The campaign activity log, transaction ledger, receipts and closeout report are the source records for campaign money. Contact support for an explanation or use the dispute flow for an eligible formal review."] },
  ] },
];

const BACKEND_LEGAL_SLUG: Record<string, string> = { "campaign-funding": "campaign-funding-terms" };
const FRONTEND_LEGAL_SLUG: Record<string, string> = { "campaign-funding-terms": "campaign-funding" };

function useLegalVersions() {
  const [versions, setVersions] = useState<Record<string, LegalDocumentOut>>({});
  useEffect(() => {
    let cancelled = false;
    Promise.all(productionLegalDocs.map((doc) => legalApi.document(BACKEND_LEGAL_SLUG[doc.slug] ?? doc.slug).catch(() => null))).then((docs) => {
      if (cancelled) return;
      const map: Record<string, LegalDocumentOut> = {};
      docs.forEach((doc) => { if (doc) map[FRONTEND_LEGAL_SLUG[doc.slug] ?? doc.slug] = doc; });
      setVersions(map);
    });
    return () => { cancelled = true; };
  }, []);
  return versions;
}

export function ProductionLegalCentreScreen() {
  const versions = useLegalVersions();
  const hasSession = useSessionPresence();
  return <ServiceFrame active="Legal"><section className="legal-hero"><div><Status tone="gold">Current product documents</Status><h1>Legal centre</h1><p>Clippit's account, privacy, community and campaign-funding rules.</p></div><div className="legal-stamp"><ProductIcon name="shield" /><strong>{productionLegalDocs.length}</strong><span>documents</span></div></section><section className="service-content legal-list">{productionLegalDocs.map((doc, index) => { const live = versions[doc.slug]; return <Link href={`/legal/${doc.slug}`} key={doc.slug}><span>{String(index + 1).padStart(2, "0")}</span><p><strong>{live?.title ?? doc.title}</strong><small>{doc.summary}</small></p><time>{live ? `Version ${live.version} · effective ${formatDate(live.effective_date)}` : doc.date}</time><ProductIcon name="arrow" /></Link>; })}<aside className="legal-account-links"><Link href={hasSession ? "/account/data" : "/auth"}><ProductIcon name="person" />Account data<ProductIcon name="arrow" /></Link><Link href={hasSession ? "/consent/update" : "/auth"}><ProductIcon name="check" />Accepted documents<ProductIcon name="arrow" /></Link><Link href={hasSession ? "/support/tickets/new" : "/auth"}><ProductIcon name="brief" />Ask a legal question<ProductIcon name="arrow" /></Link></aside></section></ServiceFrame>;
}

export function ProductionLegalDocumentScreen({ slug }: { slug: string }) {
  const doc = productionLegalDocs.find((item) => item.slug === slug) ?? productionLegalDocs[0];
  const live = useLegalVersions()[doc.slug];
  const hasSession = useSessionPresence();
  return <ServiceFrame active="Legal"><article className="legal-document"><CompletionHead back="/legal" kicker={`Version ${live?.version ?? doc.version}`} title={live?.title ?? doc.title} copy={live ? `Effective ${formatDate(live.effective_date, { day: "numeric", month: "long", year: "numeric" })}` : doc.date} /><div className="legal-document__body"><aside className="legal-toc"><div className="legal-toc__head"><strong>Contents</strong><button onClick={() => window.print()}>Print<ProductIcon name="brief" /></button></div><nav aria-label="Document contents">{doc.sections.map((section, index) => <a href={`#legal-${index + 1}`} key={section.title}><span>{index + 1}</span>{section.title}</a>)}</nav></aside><div>{doc.sections.map((section, index) => <section id={`legal-${index + 1}`} key={section.title}><h2>{index + 1}. {section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}{section.points && <ul>{section.points.map((point) => <li key={point}>{point}</li>)}</ul>}</section>)}<section className="legal-authorities"><header><span><ProductIcon name="shield" /></span><div><small>Verified public bodies</small><h2>Official resources</h2></div></header><div className="legal-authorities__links"><a href="https://ndpc.gov.ng/" target="_blank" rel="noreferrer"><span><small>Privacy rights</small><strong>Nigeria Data Protection Commission</strong></span><ProductIcon name="arrow" /></a><a href="https://fccpc.gov.ng/consumers/" target="_blank" rel="noreferrer"><span><small>Consumer rights</small><strong>Federal Competition and Consumer Protection Commission</strong></span><ProductIcon name="arrow" /></a></div><footer><p>Need help with your Clippit account or a policy?</p><BigAction href={hasSession ? "/support/tickets/new" : "/auth"} tone="ink">Contact support</BigAction></footer></section></div></div></article></ServiceFrame>;
}

export function ProductionConsentUpdateScreen() {
  const [required, setRequired] = useState<LegalDocumentOut[] | null>(null);
  const [accepted, setAccepted] = useState<Array<{ slug: string; version: string; accepted_at: string }>>([]);
  const [agree, setAgree] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    legalApi.myAcceptances().then(async (data) => {
      setAccepted(data.accepted);
      const docs = await Promise.all(data.newly_required.map((slug) => legalApi.document(slug).catch(() => null)));
      setRequired(docs.filter((doc): doc is LegalDocumentOut => !!doc));
    }).catch((err) => { setError(errorMessage(err)); setRequired([]); });
  }, []);

  const acceptAll = async () => {
    if (!required) return;
    setSaving(true);
    setError("");
    try {
      for (const doc of required) await legalApi.accept(doc.slug, doc.version);
      setAccepted((current) => [...current, ...required.map((doc) => ({ slug: doc.slug, version: doc.version, accepted_at: new Date().toISOString() }))]);
      setRequired([]);
    } catch (err) {
      setError(errorMessage(err, "We couldn't record your acceptance. Try again."));
    } finally {
      setSaving(false);
    }
  };

  if (!required) return <ServiceFrame active="Legal"><section className="consent-screen"><ClippitLoader contained compact label="Checking your accepted documents" /></section></ServiceFrame>;

  if (required.length) return <ServiceFrame active="Legal"><section className="consent-screen"><div className="consent-sheet"><Status tone="gold">Action required</Status><h1>{required.length === 1 ? `${required[0].title} changed.` : "Some terms changed."}</h1><p>Review the updated document{required.length === 1 ? "" : "s"} before you fund, join or withdraw.</p><ol>{required.map((doc, index) => <li key={doc.slug}><span>{index + 1}</span><div><strong>{doc.title}</strong><p>Version {doc.version} · effective {formatDate(doc.effective_date)} · <Link href={`/legal/${FRONTEND_LEGAL_SLUG[doc.slug] ?? doc.slug}`}>Read it</Link></p></div></li>)}</ol><label><input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} />I have read and accept {required.length === 1 ? "this version" : "these versions"}.</label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="completion-submit" disabled={!agree || saving} onClick={acceptAll}>{saving ? "Saving…" : "Accept and continue"}<ProductIcon name="arrow" /></button></div><MiniArt src={art.brief} tone="gold" /></section></ServiceFrame>;

  return <ServiceFrame active="Legal"><section className="consent-screen consent-screen--current"><div className="consent-sheet"><Status tone="lime">No action required</Status><h1>Your legal documents are current.</h1><p>{error || "There is no new document waiting for your acceptance."}</p>{!!accepted.length && <ol>{accepted.map((item) => <li key={`${item.slug}-${item.version}`}><span><ProductIcon name="check" /></span><div><strong>{productionLegalDocs.find((doc) => doc.slug === (FRONTEND_LEGAL_SLUG[item.slug] ?? item.slug))?.title ?? item.slug}</strong><p>Version {item.version} · accepted {formatDate(item.accepted_at)}</p></div></li>)}</ol>}<BigAction href="/legal">Open legal centre</BigAction></div><MiniArt src={art.proof} /></section></ServiceFrame>;
}

const reviewRoutes = [
  ["Support", "/help", "Help centre"], ["Support", "/help/how-campaigns-work", "Help article"], ["Support", "/support/tickets", "Support tickets"], ["Support", "/support/tickets/new", "New support ticket"], ["Support", "/disputes", "Disputes"], ["Support", "/disputes/new", "Open dispute"],
  ["Privacy and legal", "/account/data", "Your data"], ["Privacy and legal", "/account/delete", "Delete account"], ["Privacy and legal", "/legal", "Legal centre"], ["Privacy and legal", "/legal/privacy", "Legal document"], ["Privacy and legal", "/consent/update", "Updated terms"],
  ["Creator", "/dashboard/verification", "Creator verification"], ["Creator", "/dashboard/verification/identity", "Identity details"], ["Creator", "/dashboard/verification/documents", "Identity document"], ["Creator", "/dashboard/verification/status", "Verification status"], ["Creator", "/dashboard/earnings/statement", "Earnings statement"],
  ["Brand", "/brand/verification", "Business verification"], ["Brand", "/brand/verification/business", "Business details"], ["Brand", "/brand/verification/documents", "Business documents"], ["Brand", "/brand/verification/status", "Business status"], ["Brand", "/brand/team", "Team members"], ["Brand", "/brand/team/invite", "Invite member"], ["Brand", "/brand/billing", "Billing"],
] as const;

export function CustomerScreenReviewIndex() {
  const groups = ["Support", "Privacy and legal", "Creator", "Brand"] as const;
  return <ServiceFrame><section className="review-index"><CompletionHead kicker="Experience directory" title="Connected customer journeys" copy="Open each live journey from one place. Detail pages appear from real records in their lists." action={<Status tone="lime">Live routes</Status>} />{groups.map((group) => <section key={group}><header><h2>{group}</h2><span>{reviewRoutes.filter((route) => route[0] === group).length} screens</span></header><div>{reviewRoutes.filter((route) => route[0] === group).map((route, index) => <Link href={route[1]} key={route[1]}><i>{String(index + 1).padStart(2, "0")}</i><p><strong>{route[2]}</strong><small>{route[1]}</small></p><ProductIcon name="arrow" /></Link>)}</div></section>)}</section></ServiceFrame>;
}
