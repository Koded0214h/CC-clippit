"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { ButtonLoader, ClippitLoader } from "@/components/ui/ClippitLoader";
import { feePercentage } from "@/lib/fees";
import { money } from "@/lib/product";
import { earningsApi, type EarningEntryDetail, type EarningRow, type EarningsSummary } from "@/lib/api/earnings";
import { creatorApi, type ClipRow } from "@/lib/api/creator";
import { socialApi, type ConnectedAccountOut } from "@/lib/api/social";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";
import { campaignsApi, type CampaignOut } from "@/lib/api/campaigns";
import { submissionsApi, type SubmissionEarningsOut, type SubmissionOut } from "@/lib/api/submissions";
import { payoutsApi, type PayoutOut, type PayoutQuoteOut } from "@/lib/api/payouts";
import { uploadsApi } from "@/lib/api/account";
import { ApiError, errorMessage } from "@/lib/api/client";
import { formatDate, formatDateTime, platformIconName, platformLabel, timeAgo } from "@/lib/format";

const art = {
  appeal: "/assets/illustrations/clippit-icons/appeal-review.webp",
  connect: "/assets/illustrations/clippit-icons/social-connect.webp",
  proof: "/assets/illustrations/clippit-icons/verified-proof.webp",
  submit: "/assets/illustrations/clippit-icons/clip-submit.webp",
  wallet: "/assets/illustrations/clippit-icons/payout-wallet.webp",
  withdraw: "/assets/illustrations/clippit-icons/withdraw-bank.webp",
};

type Tone = "lime" | "gold" | "ink" | "danger" | "muted";

function CreatorHeading({ note, title, copy, action }: { note?: string; title: string; copy?: string; action?: ReactNode }) {
  return <header className="creator-page-heading"><div>{note ? <p className="marker-label">{note}</p> : null}<h1>{title}</h1>{copy ? <p>{copy}</p> : null}</div>{action}</header>;
}

function ArtTile({ src, label, tone = "lime", large = false }: { src: string; label: string; tone?: Tone; large?: boolean }) {
  return <div className={`creator-art creator-art--${tone}${large ? " creator-art--large" : ""}`}><Image src={src} alt="" width={768} height={768} priority={large} /><span>{label}</span></div>;
}

function AnimatedMoney({ value, delay = 0 }: { value: number; delay?: number }) {
  return <AnimatedNumber value={value} format="money" delay={delay} />;
}

function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`creator-status creator-status--${tone}`}><i />{children}</span>;
}

function PrimaryLink({ href, children, dark = false }: { href: string; children: ReactNode; dark?: boolean }) {
  return <Link className={dark ? "ink-button" : "lime-button"} href={href}>{children}<ProductIcon name="arrow" /></Link>;
}

function Loading({ label, note }: { label: string; note?: string }) {
  return <div className="dashboard-page"><ClippitLoader contained label={label} note={note} /></div>;
}

function Problem({ title, copy, action }: { title: string; copy: string; action?: ReactNode }) {
  return <div className="dashboard-page creator-flow-page"><section className="creator-sheet creator-empty" role="alert"><ProductIcon name="shield" /><h2>{title}</h2><p>{copy}</p>{action}</section></div>;
}

function Empty({ icon = "play", title, copy, action }: { icon?: ProductIconName; title: string; copy: string; action?: ReactNode }) {
  return <div className="creator-empty"><ProductIcon name={icon} /><h2>{title}</h2><p>{copy}</p>{action}</div>;
}

function useQueryId(): string | null | undefined {
  const [id, setId] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setId(new URLSearchParams(window.location.search).get("id")));
    return () => window.cancelAnimationFrame(frame);
  }, []);
  return id;
}

// --- My clips ------------------------------------------------------------------

function clipStatusTone(status: string): Tone {
  if (status === "approved") return "lime";
  if (status === "checking" || status === "appealed") return "gold";
  if (status === "needs_attention") return "danger";
  return "muted";
}

export function MyClipsScreen() {
  const [data, setData] = useState<{ active: number; views: number; earned: number; items: ClipRow[] } | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    creatorApi.clips()
      .then((clips) => { if (!cancelled) { setData({ active: clips.active_clips, views: clips.verified_views, earned: clips.total_earned, items: clips.items }); setError(""); } })
      .catch((err) => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, [reload]);

  if (error) return <Problem title="We couldn't load your clips" copy={error} action={<button className="ink-button" type="button" onClick={() => { setError(""); setReload((v) => v + 1); }}>Try again</button>} />;
  if (!data) return <Loading label="Gathering your clips" note="Checking submission status, verified views and earnings." />;

  return <div className="dashboard-page creator-flow-page">
    <CreatorHeading title="My clips" copy="Check submission status, verified views and earnings." action={<PrimaryLink href="/dashboard/campaigns">Submit a clip</PrimaryLink>} />
    <section className="clip-command" aria-label="Creator clip totals">
      <div className="clip-command__copy"><StatusPill tone="lime">{data.active} active clip{data.active === 1 ? "" : "s"}</StatusPill><h2>Clip activity</h2><p>Views and earnings update from your connected accounts.</p></div>
      <div className="clip-command__trail" aria-hidden="true"><span><ProductIcon name="play" /><b>Posted</b></span><i /><span><ProductIcon name="shield" /><b>Verified</b></span><i /><span><ProductIcon name="wallet" /><b>Earned</b></span></div>
      <ArtTile src={art.submit} label="Submission status" tone="lime" large />
      <div className="clip-command__numbers"><div><small>Active clips</small><strong><AnimatedNumber value={data.active} padStart={2} duration={700} /></strong></div><div><small>Verified views</small><strong><AnimatedNumber value={data.views} format="compact" delay={100} /></strong></div><div><small>Total earned</small><strong><AnimatedMoney value={data.earned} delay={200} /></strong></div></div>
    </section>
    <section className="creator-sheet"><div className="creator-sheet__head"><div><h2>All submissions</h2><p>Open a clip to view its checks, views and earnings.</p></div><Link href="/dashboard/accounts">Manage accounts<ProductIcon name="arrow" /></Link></div>
      {!data.items.length ? <Empty title="No clips yet" copy="Join a campaign, post your clip, then paste its link here to start earning from verified views." action={<PrimaryLink href="/dashboard/campaigns">Find a campaign</PrimaryLink>} /> :
      <div className="clip-ledger"><div className="clip-ledger__labels"><span>Clip</span><span>Status</span><span>Verified views</span><span>Earned</span><span /></div>{data.items.map((clip, index) => <Link key={clip.id} href={clip.link} className="clip-ledger__row"><span className="clip-ledger__title"><i><AnimatedNumber value={index + 1} padStart={2} duration={600} /></i><span><strong>{clip.title || clip.campaign_title}</strong><small>{clip.brand ?? clip.campaign_title} · {clip.campaign_title} · {platformLabel(clip.platform)}</small></span></span><StatusPill tone={clipStatusTone(clip.status)}>{clip.label}</StatusPill><strong>{clip.verified_views ? <AnimatedNumber value={clip.verified_views} format="compact" /> : clip.status === "checking" ? "Waiting" : "—"}</strong><strong className="money-ink">{clip.earned ? <AnimatedMoney value={clip.earned} /> : "—"}</strong><ProductIcon name="chevron" /></Link>)}</div>}
    </section>
  </div>;
}

// --- Connected accounts -------------------------------------------------------

export function ConnectedAccountsScreen() {
  const [accounts, setAccounts] = useState<ConnectedAccountOut[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [next, setNext] = useState("/dashboard/campaigns");

  const load = useCallback(() => socialApi.accounts().then((data) => { setAccounts(data); setError(""); }).catch((err) => setError(errorMessage(err))), []);

  useEffect(() => {
    void load();
    const frame = window.requestAnimationFrame(() => {
      const target = new URLSearchParams(window.location.search).get("next");
      if (target?.startsWith("/dashboard/")) setNext(target);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  const disconnect = async (platform: string) => {
    if (!window.confirm(`Disconnect ${platformLabel(platform)}? Clips posted there stop collecting verified views until you reconnect.`)) return;
    setBusy(platform);
    try {
      await socialApi.disconnect(platform);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy("");
    }
  };

  if (!accounts && error) return <Problem title="We couldn't load your accounts" copy={error} action={<button className="ink-button" type="button" onClick={() => void load()}>Try again</button>} />;
  if (!accounts) return <Loading label="Checking your connected accounts" note="Confirming which platforms are ready for submissions." />;

  const connectable = accounts.filter((account) => account.connectable);
  const connected = accounts.filter((account) => account.connected).length;

  return <div className="dashboard-page creator-flow-page">
    <CreatorHeading title="Connected accounts" copy="Connect the platform you post on before joining or submitting to its campaigns. Browsing doesn't need one." action={connected ? <PrimaryLink href={next}>{next === "/dashboard/campaigns" ? "Find a campaign" : "Continue"}</PrimaryLink> : undefined} />
    {error && <p className="creator-error" role="alert">{error}</p>}
    <div className="creator-split creator-split--connect"><section className="connect-stage"><ArtTile src={art.connect} label="Connected accounts" tone="lime" large /><div className="connect-score"><span><AnimatedNumber value={connected} suffix={`/${connectable.length || accounts.length}`} duration={650} /></span><p><strong>connected accounts</strong><small>{connectable.map((account) => platformLabel(account.platform)).join(", ")} can be connected today.</small></p></div><div className="connect-meter"><i style={{ width: `${connectable.length ? (connected / connectable.length) * 100 : 0}%` }} /></div></section>
      <section className="creator-sheet account-stack"><div className="creator-sheet__head"><div><h2>Your platforms</h2><p>You can disconnect at any time.</p></div></div>{accounts.map((account) => <article className={`account-card${account.connected ? " is-connected" : ""}`} key={account.platform}><span><ProductIcon name={platformIconName(account.platform)} /></span><div><strong>{platformLabel(account.platform)}</strong><small>{account.connected ? (account.handle ? `@${account.handle.replace(/^@/, "")}` : account.display_name ?? "Connected") : account.connectable ? "Connect to join its briefs" : "Coming soon"}</small><em>{account.connected ? `Views checked ${timeAgo(account.last_checked_at)}` : "Not connected"}</em></div>{account.connected && <StatusPill tone="lime">Connected</StatusPill>}{account.connected
        ? <button type="button" disabled={busy === account.platform} onClick={() => disconnect(account.platform)}>{busy === account.platform ? "Disconnecting…" : "Disconnect"}</button>
        : account.connectable ? <a className="account-card__connect" href={socialApi.connectUrl(account.platform)}>Connect</a> : <button type="button" disabled>Soon</button>}</article>)}</section>
    </div>
    <section className="permission-strip"><div><ProductIcon name="eye" /><span><strong>Clippit reads</strong><small>Post identity, public views, likes and comments.</small></span></div><div><ProductIcon name="shield" /><span><strong>Clippit never asks for</strong><small>Your password, DMs, drafts or private audience data.</small></span></div></section>
  </div>;
}

// --- Submit a clip -------------------------------------------------------------

function submitProblem(err: unknown, platform: string, slug: string): { message: string; href?: string; cta?: string } {
  if (err instanceof ApiError) {
    if (err.code === "email_not_verified") return { message: "Confirm your email address before submitting clips.", href: "/auth/verify-email", cta: "Confirm email" };
    if (err.status === 409 && /connect/i.test(err.detail)) return { message: err.detail, href: `/dashboard/accounts?next=/dashboard/campaigns/${slug}/submit`, cta: `Connect ${platformLabel(platform)}` };
    if (err.status === 502) return { message: "We couldn't reach the checking service. Your clip wasn't sent — try again in a minute." };
    return { message: err.detail };
  }
  return { message: "We couldn't send your clip. Check your connection and try again." };
}

export function SubmitClipScreen({ campaignSlug }: { campaignSlug: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resubmitId = searchParams?.get("resubmit") ?? null;
  const [campaign, setCampaign] = useState<CampaignOut | null>(null);
  const [loadError, setLoadError] = useState("");
  const [accounts, setAccounts] = useState<ConnectedAccountOut[]>([]);
  const [platform, setPlatform] = useState("");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [problem, setProblem] = useState<{ message: string; href?: string; cta?: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    campaignsApi.get(campaignSlug).then((data) => {
      setCampaign(data);
      setPlatform((current) => current || data.platforms[0] || "");
    }).catch((err) => setLoadError(err instanceof ApiError && err.status === 404 ? "This campaign isn't accepting clips, or the link is wrong." : errorMessage(err)));
    socialApi.accounts().then(setAccounts).catch(() => setAccounts([]));
  }, [campaignSlug]);

  if (loadError) return <Problem title="We can't open this campaign" copy={loadError} action={<PrimaryLink href="/dashboard/campaigns">Browse campaigns</PrimaryLink>} />;
  if (!campaign) return <Loading label="Opening the submission form" />;

  const account = accounts.find((item) => item.platform === platform);
  const notConnected = !!accounts.length && !!platform && !account?.connected;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const link = url.trim();
    if (!/^https?:\/\/\S+\.\S+/.test(link)) return setProblem({ message: "Paste the full public link to your posted clip, starting with https://" });
    setProblem(null);
    setSubmitting(true);
    try {
      const payload = { platform, url: link, title: title.trim() || null };
      const result = resubmitId
        ? await submissionsApi.resubmit(resubmitId, payload)
        : await submissionsApi.create({ campaign_id: campaign.id, ...payload });
      router.push(`/dashboard/submissions/processing?id=${result.id}`);
    } catch (err) {
      setProblem(submitProblem(err, platform, campaign.slug));
      setSubmitting(false);
    }
  };

  return <div className="dashboard-page creator-flow-page creator-submit-page">
    <Link className="product-back" href={`/dashboard/campaigns/${campaign.slug}`}><ProductIcon name="chevron" /> Back to campaign</Link>
    <CreatorHeading title={resubmitId ? "Submit a corrected clip" : "Submit clip"} copy="Paste the link to your live social post. We will check it against the campaign requirements." />
    <div className="creator-split"><form className="submission-form creator-sheet" onSubmit={submit}><div className="locked-campaign"><span><Image src={campaign.cover_image_url ?? "/assets/video/creator-reaction-poster.jpg"} alt="" fill sizes="80px" /></span><div><small>Submitting to</small><strong>{campaign.title}</strong><p>{campaign.brand?.name ?? "Brand"} · <AnimatedMoney value={campaign.payout_rule?.rate_per_1000_views ?? 0} /> per 1K verified views</p></div><ProductIcon name="shield" /></div>
      <fieldset><legend>Where did you post it?</legend><div className="platform-select">{campaign.platforms.map((item) => <button type="button" className={platform === item ? "is-selected" : ""} onClick={() => { setPlatform(item); setProblem(null); }} key={item}><ProductIcon name={platformIconName(item)} />{platformLabel(item)}<i><ProductIcon name="check" /></i></button>)}</div></fieldset>
      {notConnected && <p className="creator-warning"><ProductIcon name="link" /> Your {platformLabel(platform)} account isn&apos;t connected yet. <Link href={`/dashboard/accounts?next=/dashboard/campaigns/${campaign.slug}/submit`}>Connect it first</Link></p>}
      <label className="creator-field"><span>Public post link</span><div><ProductIcon name="link" /><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder={`https://www.${platform === "x" ? "x" : platform || "tiktok"}.com/...`} inputMode="url" maxLength={2048} /></div></label>
      <label className="creator-field"><span>Clip title <small>(optional)</small></span><div><ProductIcon name="play" /><input value={title} onChange={(event) => setTitle(event.target.value.slice(0, 200))} placeholder="What you called the post" /></div></label>
      <div className="url-retrieval-note"><ProductIcon name="play" /><span><strong>No video upload needed</strong><small>Keep the post public while Clippit checks it against the campaign requirements.</small></span></div>
      {problem && <p className="creator-error" role="alert">{problem.message}{problem.href && <> <Link href={problem.href}>{problem.cta}</Link></>}</p>}
      <button className="lime-button submission-submit" type="submit" disabled={submitting || !platform} aria-busy={submitting}>{submitting ? <ButtonLoader label="Sending for verification" /> : <>Send for verification<ProductIcon name="arrow" /></>}</button></form>
      <aside className="submission-proof"><ArtTile src={art.submit} label="Submission" tone="gold" large /><h2>What happens next</h2><ol><li><span>01</span><p><strong>We match the post.</strong><small>The connected account must own the link.</small></p></li><li><span>02</span><p><strong>We check the brief.</strong><small>Every must-do gets a reasoned verdict.</small></p></li><li><span>03</span><p><strong>We start reading.</strong><small>Approved clips enter scheduled view checks.</small></p></li></ol></aside>
    </div>
  </div>;
}

// --- Verification progress ---------------------------------------------------

const stepIcons: ProductIconName[] = ["link", "brief", "shield", "eye"];

function useSubmission(id: string | null | undefined) {
  const [submission, setSubmission] = useState<SubmissionOut | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    submissionsApi.get(id).then((data) => { if (!cancelled) { setSubmission(data); setError(""); } }).catch((err) => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, [id, reload]);
  return { submission, setSubmission, error, refresh: () => setReload((value) => value + 1) };
}

function verdictRoute(sub: SubmissionOut) {
  const status = sub.verification?.status;
  if (sub.status === "rejected" || status === "rejected") return `/dashboard/submissions/rejected?id=${sub.id}`;
  if (status === "approved") return `/dashboard/submissions/approved?id=${sub.id}`;
  if (status === "appealed") return `/dashboard/submissions/appeal?id=${sub.id}`;
  return null;
}

function MissingSubmission() {
  return <Problem title="Choose a clip to open" copy="Open a clip from My clips to see its checks and result." action={<PrimaryLink href="/dashboard/clips">Go to My clips</PrimaryLink>} />;
}

export function VerificationProgressScreen() {
  const router = useRouter();
  const id = useQueryId();
  const { submission, setSubmission, error } = useSubmission(id);

  useEffect(() => {
    if (!id) return;
    const timer = window.setInterval(() => {
      submissionsApi.get(id).then(setSubmission).catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [id, setSubmission]);

  useEffect(() => {
    const target = submission ? verdictRoute(submission) : null;
    if (target) router.replace(target);
  }, [submission, router]);

  if (id === undefined) return <Loading label="Opening your clip" />;
  if (!id) return <MissingSubmission />;
  if (error && !submission) return <Problem title="We couldn't open this clip" copy={error} action={<PrimaryLink href="/dashboard/clips">Go to My clips</PrimaryLink>} />;
  if (!submission) return <Loading label="Opening your clip" />;

  const steps = submission.verification?.steps ?? [];
  const needsReview = submission.verification?.status === "needs_review";

  return <div className="dashboard-page creator-flow-page verdict-page verdict-page--processing"><CreatorHeading title="Checking your clip" copy="You can leave this page. The result, evidence and any retry action will appear in My clips." />
    <section className="processing-stage"><div className="processing-orbit"><ArtTile src={art.proof} label="Verification in progress" tone="lime" large /></div><div className="processing-copy"><StatusPill tone="gold">{needsReview ? "With a human reviewer" : "Verification in progress"}</StatusPill><h2>{submission.campaign?.title ?? "Checking every requirement"}</h2><p>{needsReview ? "The automated check wasn't sure, so a reviewer from the brand's side is looking at it. You'll get a notification with the result." : "If we cannot complete the check, you will get a retry option. An incomplete check never counts as a rejection."}</p><div className="verification-list">{steps.map((step, index) => <div className={`${step.state === "active" ? "is-active" : ""}${step.state === "done" ? " is-done" : ""}${step.state === "failed" ? " is-failed" : ""}`} key={step.key}><span><ProductIcon name={stepIcons[index] ?? "check"} /></span><p><strong>{step.title}</strong><small>{step.detail}</small></p><i>{step.state === "done" ? <ProductIcon name="check" /> : String(index + 1).padStart(2, "0")}</i></div>)}</div><div className="processing-actions"><PrimaryLink href="/dashboard/clips">Return to My clips</PrimaryLink><a href={submission.url} target="_blank" rel="noreferrer">Open your post</a></div></div></section>
  </div>;
}

// --- Verdicts ------------------------------------------------------------------

export function ApprovedVerdictScreen() {
  const router = useRouter();
  const id = useQueryId();
  const { submission, error } = useSubmission(id);
  const [earnings, setEarnings] = useState<SubmissionEarningsOut | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    if (id) submissionsApi.getEarnings(id).then(setEarnings).catch(() => undefined);
  }, [id]);

  if (id === undefined) return <Loading label="Opening your clip" />;
  if (!id) return <MissingSubmission />;
  if (error) return <Problem title="We couldn't open this clip" copy={error} action={<PrimaryLink href="/dashboard/clips">Go to My clips</PrimaryLink>} />;
  if (!submission) return <Loading label="Opening your verdict" />;

  const verification = submission.verification;
  const passed = verification?.passed ?? 0;
  const total = verification?.total ?? 0;
  const withdrawn = submission.status === "withdrawn";

  const withdraw = async () => {
    if (!window.confirm("Withdraw this clip? It stops earning and can't be re-added to this campaign.")) return;
    setWithdrawing(true);
    setActionError("");
    try {
      await submissionsApi.withdraw(submission.id);
      router.push("/dashboard/clips");
    } catch (err) {
      setActionError(errorMessage(err));
      setWithdrawing(false);
    }
  };

  return <div className="dashboard-page creator-flow-page verdict-page"><CreatorHeading title={withdrawn ? "Clip withdrawn" : "Clip approved"} copy={withdrawn ? "This clip no longer earns." : "Official views are now tracked. Earnings stay held until the review window ends, then become payable."} action={<StatusPill tone={withdrawn ? "muted" : "lime"}>{withdrawn ? "Withdrawn" : "Earning"}</StatusPill>} />
    <section className="verdict-hero verdict-hero--approved"><div className="verdict-seal"><ArtTile src={art.proof} label="Verified" tone="lime" large /><span><ProductIcon name="check" /></span></div><div className="verdict-summary"><small>{submission.campaign?.title ?? "Campaign check"}</small><strong><AnimatedNumber value={passed} suffix={`/${total}`} duration={700} /></strong><h2>{passed} of {total} requirements passed</h2><p>Approved {formatDateTime(verification?.verdict_at)}{verification?.decided_by_human ? " by a reviewer" : ""}. {earnings?.next_payable_at ? `The next held amount becomes payable on ${formatDate(earnings.next_payable_at)}.` : ""}</p><div className="verdict-money"><div><small>Current verified views</small><strong><AnimatedNumber value={earnings?.verified_views ?? 0} format="compact" /></strong></div><div><small>Earned so far</small><strong><AnimatedMoney value={earnings?.accrued ?? 0} delay={100} /></strong></div><div><small>Payable now</small><strong><AnimatedMoney value={earnings?.payable_now ?? 0} delay={160} /></strong></div></div><div className="verdict-actions"><PrimaryLink href="/dashboard/earnings">View earnings</PrimaryLink>{!withdrawn && <button type="button" className="text-button" disabled={withdrawing} onClick={withdraw}>{withdrawing ? "Withdrawing…" : "Withdraw this clip"}</button>}</div>{actionError && <p className="creator-error" role="alert">{actionError}</p>}</div></section>
    {!!verification?.requirements.length && <section className="creator-sheet requirement-sheet"><div className="creator-sheet__head"><div><h2>Requirements checked</h2><p>Each requirement checked for this submission.</p></div></div><ol>{verification.requirements.map((item) => <li key={item.id}><span><ProductIcon name={item.verdict === "pass" ? "check" : "shield"} /></span><p><strong>Requirement {String(item.position + 1).padStart(2, "0")}</strong>{item.text}{item.note && <small>{item.note}</small>}</p></li>)}</ol></section>}
  </div>;
}

export function RejectedVerdictScreen() {
  const id = useQueryId();
  const { submission, error } = useSubmission(id);

  if (id === undefined) return <Loading label="Opening your clip" />;
  if (!id) return <MissingSubmission />;
  if (error) return <Problem title="We couldn't open this clip" copy={error} action={<PrimaryLink href="/dashboard/clips">Go to My clips</PrimaryLink>} />;
  if (!submission) return <Loading label="Opening your verdict" />;

  const verification = submission.verification;
  const failed = verification?.failed_requirement;
  const passedChecks = verification?.requirements.filter((item) => item.verdict === "pass") ?? [];
  const linkRejected = !verification && !!submission.rejection_message;
  const appeal = verification?.appeal;
  const slug = submission.campaign?.slug;

  return <div className="dashboard-page creator-flow-page verdict-page"><CreatorHeading title="Clip not approved" copy={failed ? `Requirement ${String(failed.position + 1).padStart(2, "0")} failed. Review the evidence, correct the post, or appeal.` : "This link couldn't be accepted."} action={<StatusPill tone="danger">Not earning</StatusPill>} />
    <section className="verdict-hero verdict-hero--rejected"><div className="verdict-seal"><ArtTile src={art.appeal} label="Correction needed" tone="danger" large /><span>!</span></div><div className="verdict-summary"><small>{submission.campaign?.title ?? "Campaign check"}</small>{verification && <strong><AnimatedNumber value={verification.passed} suffix={`/${verification.total}`} duration={700} /></strong>}<h2>{linkRejected ? "We couldn't use this link." : failed?.text ?? "A requirement wasn't met."}</h2><p>{linkRejected ? submission.rejection_message : failed?.note ?? verification?.summary ?? "Open the evidence below, correct the post, or ask for a human review if the result is wrong."}</p>
      {failed && <div className="failed-proof"><span><ProductIcon name="brief" /></span><p><small>Requirement {String(failed.position + 1).padStart(2, "0")} failed</small><strong>{failed.text}</strong><em>Checked {formatDateTime(verification?.verdict_at)}</em></p></div>}
      {appeal && <div className="failed-proof"><span><ProductIcon name="clock" /></span><p><small>Appeal {appeal.status === "open" ? "in review" : appeal.status}</small><strong>{appeal.decision_note ?? "A reviewer is checking your explanation."}</strong><em>Sent {formatDateTime(appeal.created_at)}</em></p></div>}
      <div className="verdict-actions">{verification && !appeal && <PrimaryLink href={`/dashboard/submissions/appeal?id=${submission.id}`}>Appeal this verdict</PrimaryLink>}{slug && <PrimaryLink href={`/dashboard/campaigns/${slug}/submit?resubmit=${submission.id}`} dark>Submit a corrected post</PrimaryLink>}</div></div></section>
    {!!passedChecks.length && <section className="creator-sheet mini-checks"><h2>What did pass</h2>{passedChecks.map((item) => <p key={item.id}><ProductIcon name="check" />{item.text}</p>)}</section>}
  </div>;
}

export function AppealScreen() {
  const id = useQueryId();
  const { submission, setSubmission, error } = useSubmission(id);
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");

  if (id === undefined) return <Loading label="Opening your clip" />;
  if (!id) return <MissingSubmission />;
  if (error) return <Problem title="We couldn't open this clip" copy={error} action={<PrimaryLink href="/dashboard/clips">Go to My clips</PrimaryLink>} />;
  if (!submission) return <Loading label="Opening your appeal" />;

  const appeal = submission.verification?.appeal;
  const failed = submission.verification?.failed_requirement;

  if (appeal) {
    const tone: Tone = appeal.status === "overturned" ? "lime" : appeal.status === "upheld" ? "danger" : "gold";
    const label = appeal.status === "overturned" ? "Appeal won" : appeal.status === "upheld" ? "Original decision kept" : "Appeal in review";
    return <div className="dashboard-page creator-flow-page appeal-success"><ArtTile src={art.appeal} label="Human review" tone="gold" large /><StatusPill tone={tone}>{label}</StatusPill><h1>{appeal.status === "open" ? "Appeal submitted." : label + "."}</h1><p>{appeal.decision_note ?? "A reviewer will check your explanation and evidence within one working day. We'll notify you with the result."}</p><PrimaryLink href="/dashboard/clips">Return to My clips</PrimaryLink></div>;
  }

  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (reason.trim().length < 20) return;
    setSending(true);
    setSendError("");
    try {
      const evidence = file ? await uploadsApi.evidence(file) : null;
      setSubmission(await submissionsApi.appeal(submission.id, reason.trim(), evidence?.id));
    } catch (err) {
      setSendError(err instanceof ApiError && err.code === "email_not_verified" ? "Confirm your email address before sending an appeal." : errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  return <div className="dashboard-page creator-flow-page"><Link className="product-back" href={`/dashboard/submissions/rejected?id=${submission.id}`}><ProductIcon name="chevron" /> Back to verdict</Link><CreatorHeading title="Request review" copy="Explain what the automated check missed and add evidence if needed." />
    <div className="creator-split"><form className="creator-sheet appeal-form" onSubmit={send}><div className="appeal-context"><StatusPill tone="danger">{failed ? `Requirement ${String(failed.position + 1).padStart(2, "0")}` : "Verdict"}</StatusPill><p><strong>{failed?.text ?? submission.campaign?.title}</strong><small>Automated result: {failed?.note ?? submission.verification?.summary ?? "not approved"}</small></p></div><label className="creator-field creator-field--textarea"><span>What should the reviewer check?</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="The tag is visible at the end of the caption. Please check the expanded caption…" maxLength={600} /><small>{reason.length}/600 · minimum 20</small></label><label className="upload-field upload-field--compact"><input type="file" accept="image/*,video/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><ProductIcon name="upload" /><span><strong>{file?.name || "Add supporting evidence"}</strong><small>Optional screenshot or screen recording</small></span><b>{file ? "Change" : "Choose"}</b></label>{sendError && <p className="creator-error" role="alert">{sendError}</p>}<button className="lime-button" type="submit" disabled={reason.trim().length < 20 || sending}>{sending ? "Sending…" : "Send appeal"}<ProductIcon name="arrow" /></button></form>
      <aside className="appeal-promise"><ArtTile src={art.appeal} label="Review details" tone="gold" /><h2>Review details</h2><ul><li><ProductIcon name="clock" /><span><strong>Review target</strong><small>Within one working day</small></span></li><li><ProductIcon name="shield" /><span><strong>Original decision retained</strong><small>The original decision stays in the audit trail.</small></span></li><li><ProductIcon name="bell" /><span><strong>Reviewer decision</strong><small>Sent with the appeal result.</small></span></li></ul></aside>
    </div>
  </div>;
}

// --- Earnings ------------------------------------------------------------------

function earningStateTone(state: string): Tone {
  if (state === "Payable") return "lime";
  if (state === "Accrued") return "gold";
  if (state === "Processing") return "muted";
  return "ink";
}

const HISTORY_PAGE = 30;

export function EarningsScreen() {
  const [summary, setSummary] = useState<EarningsSummary | null>(null);
  const [rows, setRows] = useState<EarningRow[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, EarningEntryDetail | "error">>({});
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([earningsApi.summary(), earningsApi.history({ limit: HISTORY_PAGE })]).then(([s, history]) => {
      if (cancelled) return;
      setSummary(s);
      setRows(history.items);
      setTotal(history.total);
      setError("");
    }).catch((err) => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, [reload]);

  if (error && !summary) return <Problem title="We couldn't load your earnings" copy={error} action={<button className="ink-button" type="button" onClick={() => { setError(""); setReload((v) => v + 1); }}>Try again</button>} />;
  if (!summary) return <Loading label="Counting every earning" note="Checking payable money, held earnings and payout history." />;

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const history = await earningsApi.history({ limit: HISTORY_PAGE, offset: rows.length });
      setRows((current) => [...current, ...history.items]);
      setTotal(history.total);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  };

  const toggleRow = (id: string) => {
    setOpenId((current) => (current === id ? null : id));
    if (!detail[id]) earningsApi.entry(id).then((entry) => setDetail((current) => ({ ...current, [id]: entry }))).catch(() => setDetail((current) => ({ ...current, [id]: "error" })));
  };

  const clears = summary.next_clears_at ? new Date(summary.next_clears_at) : null;
  const earned = summary.last_earned_at ? new Date(summary.last_earned_at) : null;

  return <div className="dashboard-page creator-flow-page earnings-page"><CreatorHeading title="Earnings" copy="See what is accrued, payable and already paid." action={<div className="creator-heading-actions"><PrimaryLink href="/dashboard/withdraw">Withdraw money</PrimaryLink><PrimaryLink href="/dashboard/earnings/statement" dark>Statement</PrimaryLink></div>} />
    <section className="earnings-stage"><div className="earnings-total"><StatusPill tone={summary.payable > 0 ? "lime" : "muted"}>{summary.payable > 0 ? "Ready now" : "Nothing payable yet"}</StatusPill><small>Available to withdraw</small><strong><AnimatedMoney value={summary.payable} /></strong><p>From <AnimatedNumber value={summary.lifetime_views} /> verified, billable views.</p><div className="money-wave" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div></div><ArtTile src={art.wallet} label="Available balance" tone="gold" large /><div className="earnings-buckets"><article><span>Held</span><strong><AnimatedMoney value={summary.in_hold} /></strong><small>In the {summary.hold_days}-day review window</small></article><article><span>Processing</span><strong><AnimatedMoney value={summary.processing} delay={80} /></strong><small>Withdrawal on the way</small></article><article><span>Paid</span><strong><AnimatedMoney value={summary.paid_all_time} delay={140} /></strong><small><AnimatedNumber value={summary.completed_payouts} /> completed payouts</small></article><article><span>Lifetime views</span><strong><AnimatedNumber value={summary.lifetime_views} format="compact" delay={200} /></strong><small>Official verified views</small></article></div></section>
    <section className="hold-strip"><div className="hold-strip__intro"><ProductIcon name="clock" /><span><strong>The {summary.hold_days}-day review window</strong><small>{clears ? `Your next held amount becomes payable on ${formatDate(summary.next_clears_at)}.` : "Approved clips start tracking views immediately. Held earnings become payable when the review window ends."}</small></span></div>{clears && earned && <div className="hold-track"><span className="is-past">{earned.getDate()}<small>Earned</small></span><i className="is-past" /><span className="is-past">{new Date().getDate()}<small>Today</small></span><i /><span>{clears.getDate()}<small>Available</small></span></div>}</section>
    <section className="creator-sheet earnings-ledger"><div className="creator-sheet__head"><div><h2>Earning history</h2><p>Tap an entry to see how it was calculated.</p></div></div>
      {!rows.length ? <Empty icon="wallet" title="No earnings yet" copy="Once an approved clip crosses its first 1,000 verified views, each earning shows up here." action={<PrimaryLink href="/dashboard/campaigns">Find a campaign</PrimaryLink>} /> : <>
      <div className="earnings-ledger__labels"><span>Date</span><span>Clip</span><span>Billable views</span><span>Amount</span><span>Status</span></div>
      {rows.map((row) => {
        const entry = detail[row.id];
        return <div key={row.id}>
          <article role="button" tabIndex={0} aria-expanded={openId === row.id} onClick={() => toggleRow(row.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleRow(row.id); } }}><span>{formatDate(row.date, { day: "numeric", month: "short" })}</span><p><strong>{row.clip}</strong><small>{row.brand ?? row.campaign_title}</small></p><strong><AnimatedNumber value={row.billable_views} format="compact" /></strong><strong><AnimatedMoney value={row.amount} /></strong><StatusPill tone={earningStateTone(row.state)}>{row.state}</StatusPill></article>
          {openId === row.id && <dl className="earning-entry-detail">{entry === "error" ? <div><dt>Details</dt><dd>Couldn&apos;t load this entry.</dd></div> : !entry ? <div><dt>Details</dt><dd>Loading…</dd></div> : <>
            <div><dt>Campaign</dt><dd><Link href={`/dashboard/campaigns/${entry.campaign_slug}`}>{entry.campaign_title}</Link></dd></div>
            {entry.rate_per_1000_views !== undefined && <div><dt>Rate</dt><dd>{money(entry.rate_per_1000_views)} per 1K views</dd></div>}
            {entry.thousands !== undefined && <div><dt>Billable thousands</dt><dd>{entry.thousands}</dd></div>}
            {entry.cap_amount ? <div><dt>Cap</dt><dd>{money(entry.cap_amount)}</dd></div> : null}
            <div><dt>Becomes payable</dt><dd>{formatDate(entry.payable_at)}</dd></div>
            {entry.reference && <div><dt>Reference</dt><dd>{entry.reference}</dd></div>}
            {entry.payout_id && <div><dt>Paid out in</dt><dd><Link href={`/dashboard/payouts/receipt?id=${entry.payout_id}`}>View payout receipt</Link></dd></div>}
            <div><dt>Something wrong?</dt><dd><Link href={`/disputes/new?type=earning_entry&resource=${entry.id}`}>Dispute this entry</Link></dd></div>
          </>}</dl>}
        </div>;
      })}
      {rows.length < total && <button type="button" className="ink-button" disabled={loadingMore} onClick={loadMore}>{loadingMore ? "Loading…" : `Load more (${total - rows.length} left)`}</button>}
      </>}
    </section>
  </div>;
}

// --- Withdraw ------------------------------------------------------------------

function withdrawProblem(err: unknown): { message: string; href?: string; cta?: string } {
  if (err instanceof ApiError) {
    if (err.code === "bank_not_verified") return { message: "Verify your payout account before withdrawing.", href: "/dashboard/payout-account", cta: "Verify account" };
    if (err.code === "email_not_verified") return { message: "Confirm your email address before withdrawing.", href: "/auth/verify-email", cta: "Confirm email" };
    if (err.code === "insufficient_payable") return { message: "That's more than your payable balance. Lower the amount and try again." };
    return { message: err.detail };
  }
  return { message: "We couldn't start this withdrawal. Check your connection and try again." };
}

export function WithdrawScreen() {
  const router = useRouter();
  const [summary, setSummary] = useState<EarningsSummary | null>(null);
  const [bankDetail, setBankDetail] = useState<BankAccountOut | null | undefined>(undefined);
  const [amount, setAmount] = useState("");
  const [quote, setQuote] = useState<PayoutQuoteOut | null>(null);
  const [quoteError, setQuoteError] = useState("");
  const [idempotencyKey] = useState(() => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `wd-${Date.now()}-${Math.random().toString(36).slice(2)}`));
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<{ message: string; href?: string; cta?: string } | null>(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    earningsApi.summary().then((data) => { setSummary(data); setAmount(String(Math.floor(data.payable))); }).catch((err) => setLoadError(errorMessage(err)));
    bankDetailsApi.get().then(setBankDetail).catch(() => setBankDetail(null));
  }, []);

  const number = Math.max(0, Number(amount) || 0);
  const minimum = summary?.min_withdrawal ?? 5000;

  const quotable = !!summary && number >= minimum && number <= summary.payable;

  useEffect(() => {
    if (!quotable) return;
    const timer = window.setTimeout(() => {
      payoutsApi.quote({ amount: number, idempotency_key: `${idempotencyKey}-q` }).then((data) => { setQuote(data); setQuoteError(""); }).catch((err) => { setQuote(null); setQuoteError(errorMessage(err)); });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [number, quotable, idempotencyKey]);

  if (loadError) return <Problem title="We couldn't load your balance" copy={loadError} />;
  if (!summary || bankDetail === undefined) return <Loading label="Preparing your withdrawal" note="Confirming your available balance and payout account." />;

  const balance = summary.payable;
  const liveQuote = quotable && quote && quote.amount === number ? quote : null;
  const blocker = !bankDetail ? "Add a payout account to withdraw." : !bankDetail.verified ? "Verify your payout account to withdraw." : balance < minimum ? `You need at least ${money(minimum)} payable to withdraw.` : "";
  const amountProblem = number > balance ? "That's more than your payable balance." : number > 0 && number < minimum ? `The minimum withdrawal is ${money(minimum)}.` : "";
  const valid = !blocker && !amountProblem && number >= minimum && !!liveQuote;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    setSubmitting(true);
    setProblem(null);
    try {
      const payout = await payoutsApi.withdraw({ amount: number, idempotency_key: idempotencyKey });
      router.push(`/dashboard/payouts/receipt?id=${payout.id}`);
    } catch (err) {
      setProblem(withdrawProblem(err));
      setSubmitting(false);
    }
  };

  const chips = Array.from(new Set([minimum, minimum * 2, Math.floor(balance)])).filter((value) => value >= minimum && value <= balance);

  return <div className="dashboard-page creator-flow-page withdraw-page"><Link className="product-back" href="/dashboard/wallet"><ProductIcon name="chevron" /> Back to wallet</Link><CreatorHeading title="Withdraw from your wallet" copy={`Send payable earnings to your verified bank account. The minimum withdrawal is ${money(minimum)}.`} />
    <div className="creator-split"><form className="creator-sheet withdraw-form" onSubmit={submit}><div className="withdraw-balance"><small>Available to withdraw</small><strong><AnimatedMoney value={balance} /></strong><StatusPill tone={balance >= minimum ? "lime" : "muted"}>{balance >= minimum ? "Cleared" : "Below minimum"}</StatusPill></div>
      {blocker && <p className="creator-warning" role="status"><ProductIcon name="bank" /> {blocker} {(!bankDetail || !bankDetail.verified) && <Link href="/dashboard/payout-account">{bankDetail ? "Verify account" : "Add account"}</Link>}</p>}
      <label className="amount-field"><span>Amount</span><div><b>₦</b><input value={amount} onChange={(event) => setAmount(event.target.value.replace(/\D/g, "").slice(0, 9))} inputMode="numeric" aria-label="Withdrawal amount" disabled={!!blocker} /></div></label>
      {amountProblem && <p className="creator-error" role="alert">{amountProblem}</p>}
      {!!chips.length && <div className="amount-chips">{chips.map((value) => <button type="button" className={number === value ? "is-selected" : ""} onClick={() => setAmount(String(value))} key={value}>{value === Math.floor(balance) ? "All" : money(value)}</button>)}</div>}
      <div className="withdraw-bank"><span><ProductIcon name="bank" /></span><p><small>Destination</small><strong>{bankDetail ? `${bankDetail.bank_name} · ${bankDetail.account_number_masked.slice(-4)}` : "No payout account yet"}</strong><em>{bankDetail ? `${bankDetail.account_name ?? "Name pending"} · ${bankDetail.verified ? "Verified" : "Needs verification"}` : "Add one to withdraw"}</em></p><Link href="/dashboard/payout-account">{bankDetail ? "Change" : "Add"}</Link></div>
      <dl className="withdraw-summary"><div><dt>Withdrawal amount</dt><dd><AnimatedMoney value={number} /></dd></div><div><dt>Clippit fee ({feePercentage(0.07)}%)</dt><dd>{liveQuote ? <>−<AnimatedMoney value={liveQuote.fee} /></> : "—"}</dd></div><div><dt>You receive</dt><dd>{liveQuote ? <AnimatedMoney value={liveQuote.net_amount} delay={80} /> : "—"}</dd></div></dl>
      {quoteError && quotable && !liveQuote && <p className="creator-error" role="alert">{quoteError}</p>}
      {problem && <p className="creator-error" role="alert">{problem.message}{problem.href && <> <Link href={problem.href}>{problem.cta}</Link></>}</p>}
      <button className="lime-button" type="submit" disabled={!valid || submitting}>{submitting ? <ButtonLoader label="Starting transfer" /> : <>Withdraw <AnimatedMoney value={number} /><ProductIcon name="arrow" /></>}</button></form>
      <aside className="withdraw-aside"><ArtTile src={art.withdraw} label="Money to bank" tone="gold" large /><h2>Transfer time</h2><p>Most transfers arrive within 24 hours. Failed transfers return to your payable balance.</p><div><ProductIcon name="shield" />Encrypted bank destination</div></aside></div>
  </div>;
}

// --- Payout receipt ------------------------------------------------------------

function payoutTone(status: string): { tone: Tone; label: string } {
  if (status === "succeeded") return { tone: "lime", label: "Transfer successful" };
  if (status === "failed") return { tone: "danger", label: "Transfer failed" };
  return { tone: "gold", label: status === "processing" ? "Transfer processing" : "Transfer pending" };
}

export function PayoutReceiptScreen() {
  const id = useQueryId();
  const [payout, setPayout] = useState<PayoutOut | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (id === undefined) return;
    let cancelled = false;
    const load = () => (id ? payoutsApi.get(id) : payoutsApi.list({ limit: 1 }).then((list) => {
      if (!list.items[0]) throw new ApiError(404, "You haven't made a withdrawal yet.");
      return list.items[0];
    }));
    load().then((data) => { if (!cancelled) setPayout(data); }).catch((err) => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    if (!payout || payout.status === "succeeded" || payout.status === "failed") return;
    const timer = window.setInterval(() => { payoutsApi.get(payout.id).then(setPayout).catch(() => undefined); }, 8000);
    return () => window.clearInterval(timer);
  }, [payout]);

  if (error) return <Problem title="No receipt to show" copy={error} action={<PrimaryLink href="/dashboard/wallet">Back to wallet</PrimaryLink>} />;
  if (!payout) return <Loading label="Opening your receipt" />;

  const state = payoutTone(payout.status);
  const destination = `${payout.destination.bank_name} ending ${payout.destination.account_number_masked.slice(-4)}`;
  const feeRate = payout.amount > 0 ? Math.round((payout.fee / payout.amount) * 100) : 7;

  return <div className="dashboard-page creator-flow-page receipt-page"><section className="receipt-hero"><div className="receipt-art"><ArtTile src={art.withdraw} label="Transfer" tone="gold" large /><span><ProductIcon name={payout.status === "failed" ? "shield" : "check"} /></span></div><div className="receipt-hero__details"><StatusPill tone={state.tone}>{state.label}</StatusPill><h1><AnimatedMoney value={payout.net} /></h1><p>{payout.status === "failed" ? `${payout.failure_reason ?? "The bank rejected the transfer."} The money is back in your payable balance.` : `${payout.status === "succeeded" ? "Sent" : "Sending"} to ${destination}.`}</p><div className="receipt-actions"><PrimaryLink href="/dashboard/wallet">Back to wallet</PrimaryLink><button type="button" className="ink-button" onClick={() => window.print()}>Download receipt<ProductIcon name="brief" /></button></div></div></section>
    <section className="creator-sheet payout-receipt"><ReceiptHeader title="Official payout receipt" reference={payout.reference} /><div className="payout-receipt__summary"><Image src={art.wallet} alt="" width={92} height={92} /><p><small>Amount transferred</small><strong>{money(payout.net)}</strong><span><ProductIcon name="check" />{state.label}</span><time>{formatDateTime(payout.completed_at ?? payout.initiated_at)}</time></p></div><div className="receipt-parties"><section><h2>Recipient</h2><p><strong>{payout.destination.account_name || payout.creator_name}</strong><span>{payout.destination.bank_name} · {payout.destination.account_number_masked}</span></p></section><section><h2>Sender</h2><p><strong>Clippit Payouts</strong><span>{payout.sandbox ? "Test transfer" : "Secure transfer"}</span></p></section></div><section className="receipt-information"><h2>Transaction information</h2><dl><div><dt>Transaction type</dt><dd>Campaign earnings withdrawal</dd></div><div><dt>Reference</dt><dd>{payout.reference}</dd></div><div><dt>Status</dt><dd>{state.label}</dd></div><div><dt>Started</dt><dd>{formatDateTime(payout.initiated_at)}</dd></div>{payout.completed_at && <div><dt>Completed</dt><dd>{formatDateTime(payout.completed_at)}</dd></div>}<div><dt>Withdrawal amount</dt><dd>{money(payout.amount)}</dd></div><div><dt>Clippit fee ({feeRate}%)</dt><dd>−{money(payout.fee)}</dd></div><div><dt>Amount transferred</dt><dd>{money(payout.net)}</dd></div></dl></section>
      {!!payout.provenance?.sources.length && <section className="receipt-information"><h2>Where this money came from</h2><dl>{payout.provenance.sources.map((source, index) => <div key={`${source.clip}-${index}`}><dt>{source.campaign_title} · {source.clip}</dt><dd>{money(source.amount)}</dd></div>)}</dl></section>}
      <div className="receipt-proof"><h2>Payment breakdown</h2><div><span><ProductIcon name="wallet" /></span><p><strong>{money(payout.amount)} withdrawn</strong><small>From payable earnings</small></p><i /><span><ProductIcon name="brief" /></span><p><strong>{money(payout.fee)} Clippit fee</strong><small>{feeRate}% withdrawal charge</small></p><i /><span><ProductIcon name="bank" /></span><p><strong>{money(payout.net)} {payout.status === "succeeded" ? "settled" : "to settle"}</strong><small>{destination}</small></p></div></div><footer className="receipt-footer"><ProductIcon name="shield" /><span><strong>Verify this receipt</strong><small><Link href={`/verify/${payout.reference}`}>clippit.click/verify/{payout.reference}</Link></small></span></footer></section>
  </div>;
}
