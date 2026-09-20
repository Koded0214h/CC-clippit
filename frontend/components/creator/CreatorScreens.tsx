"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { campaigns, money } from "@/lib/product";

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

const creatorClips = [
  { id: "indomie-hunger", title: "Hunger interrupted the group chat", campaign: "Indomie · No long thing", status: "Approved", tone: "lime" as Tone, views: 156800, earned: 38200, link: "/dashboard/submissions/approved" },
  { id: "gbedu-entry", title: "The main-character entrance", campaign: "Gbedu Records · Main character sound", status: "Checking", tone: "gold" as Tone, views: 0, earned: 0, link: "/dashboard/submissions/processing" },
  { id: "palmpay-save", title: "Who paid for the ride?", campaign: "PalmPay · Send am sharp", status: "Needs attention", tone: "danger" as Tone, views: 12400, earned: 0, link: "/dashboard/submissions/rejected" },
];

export function MyClipsScreen() {
  return <div className="dashboard-page creator-flow-page">
    <CreatorHeading title="My clips" copy="Check submission status, verified views and earnings." action={<PrimaryLink href="/dashboard/campaigns/indomie-no-long-thing/submit">Submit a clip</PrimaryLink>} />
    <section className="clip-command" aria-label="Creator clip totals">
      <div className="clip-command__copy"><StatusPill tone="lime">3 active clips</StatusPill><h2>Clip activity</h2><p>Views and earnings update from your connected accounts.</p></div>
      <div className="clip-command__trail" aria-hidden="true"><span><ProductIcon name="play" /><b>Posted</b></span><i /><span><ProductIcon name="shield" /><b>Verified</b></span><i /><span><ProductIcon name="wallet" /><b>Earned</b></span></div>
      <ArtTile src={art.submit} label="Submission status" tone="lime" large />
      <div className="clip-command__numbers"><div><small>Active clips</small><strong><AnimatedNumber value={3} padStart={2} duration={700} /></strong></div><div><small>Verified views</small><strong><AnimatedNumber value={312600} format="compact" delay={100} /></strong></div><div><small>Total earned</small><strong><AnimatedMoney value={42850} delay={200} /></strong></div></div>
    </section>
    <section className="creator-sheet"><div className="creator-sheet__head"><div><h2>All submissions</h2><p>Open a clip to view its checks, views and earnings.</p></div><Link href="/dashboard/accounts">Manage accounts<ProductIcon name="arrow" /></Link></div>
      <div className="clip-ledger"><div className="clip-ledger__labels"><span>Clip</span><span>Status</span><span>Verified views</span><span>Earned</span><span /></div>{creatorClips.map((clip, index) => <Link key={clip.id} href={clip.link} className="clip-ledger__row"><span className="clip-ledger__title"><i><AnimatedNumber value={index + 1} padStart={2} duration={600} /></i><span><strong>{clip.title}</strong><small>{clip.campaign}</small></span></span><StatusPill tone={clip.tone}>{clip.status}</StatusPill><strong>{clip.views ? <AnimatedNumber value={clip.views} format="compact" /> : "Waiting"}</strong><strong className="money-ink">{clip.earned ? <AnimatedMoney value={clip.earned} /> : "—"}</strong><ProductIcon name="chevron" /></Link>)}</div>
    </section>
  </div>;
}

type Social = { name: string; icon: ProductIconName; handle: string; connected: boolean; note: string };

export function ConnectedAccountsScreen() {
  const [accounts, setAccounts] = useState<Social[]>([
    { name: "TikTok", icon: "tiktok", handle: "@tobioncam", connected: true, note: "Views checked 2 min ago" },
    { name: "Instagram", icon: "instagram", handle: "@tobioncam", connected: true, note: "Views checked 4 min ago" },
    { name: "YouTube", icon: "youtube", handle: "", connected: false, note: "Required for YouTube briefs" },
  ]);
  const connected = accounts.filter((account) => account.connected).length;
  const toggle = (name: string) => setAccounts((current) => current.map((account) => account.name === name ? { ...account, connected: !account.connected, handle: account.handle || "@tobioncam", note: account.connected ? "Required for this platform" : "Connection ready for demo" } : account));
  return <div className="dashboard-page creator-flow-page">
    <CreatorHeading title="Connected accounts" copy="Connect the accounts Clippit should use to verify views." action={<PrimaryLink href="/dashboard/campaigns/indomie-no-long-thing/submit">Continue to submission</PrimaryLink>} />
    <div className="creator-split creator-split--connect"><section className="connect-stage"><ArtTile src={art.connect} label="Connected accounts" tone="lime" large /><div className="connect-score"><span><AnimatedNumber value={connected} suffix="/3" duration={650} /></span><p><strong>connected accounts</strong><small>Connect YouTube to submit to YouTube campaigns.</small></p></div><div className="connect-meter"><i style={{ width: `${(connected / 3) * 100}%` }} /></div></section>
      <section className="creator-sheet account-stack"><div className="creator-sheet__head"><div><h2>Your platforms</h2><p>You can disconnect at any time.</p></div></div>{accounts.map((account) => <article className={`account-card${account.connected ? " is-connected" : ""}`} key={account.name}><span><ProductIcon name={account.icon} /></span><div><strong>{account.name}</strong><small>{account.connected ? account.handle : account.note}</small><em>{account.connected ? account.note : "Not connected"}</em></div>{account.connected && <StatusPill tone="lime">Connected</StatusPill>}<button type="button" onClick={() => toggle(account.name)}>{account.connected ? "Disconnect" : "Connect"}</button></article>)}</section>
    </div>
    <section className="permission-strip"><div><ProductIcon name="eye" /><span><strong>Clippit reads</strong><small>Post identity, public views, likes and comments.</small></span></div><div><ProductIcon name="shield" /><span><strong>Clippit never asks for</strong><small>Your password, DMs, drafts or private audience data.</small></span></div></section>
  </div>;
}

export function SubmitClipScreen({ campaignSlug = "indomie-no-long-thing" }: { campaignSlug?: string }) {
  const router = useRouter();
  const campaign = campaigns.find((item) => item.slug === campaignSlug) ?? campaigns[0];
  const [platform, setPlatform] = useState("TikTok");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState("");
  const [error, setError] = useState("");
  const submit = (event: FormEvent) => { event.preventDefault(); if (!url.trim()) return setError("Paste the public link to your posted clip."); setError(""); window.localStorage.setItem("clippit:last-submission", JSON.stringify({ campaign: campaign.slug, platform, url, file })); router.push("/dashboard/submissions/processing"); };
  return <div className="dashboard-page creator-flow-page creator-submit-page">
    <Link className="product-back" href={`/dashboard/campaigns/${campaign.slug}`}><ProductIcon name="chevron" /> Back to campaign</Link>
    <CreatorHeading title="Submit clip" copy="Add the public post link and original video file." />
    <div className="creator-split"><form className="submission-form creator-sheet" onSubmit={submit}><div className="locked-campaign"><span><Image src={campaign.image} alt="" fill sizes="80px" /></span><div><small>Submitting to</small><strong>{campaign.title}</strong><p>{campaign.brand} · <AnimatedMoney value={campaign.rate} /> per 1K verified views</p></div><ProductIcon name="shield" /></div>
      <fieldset><legend>Where did you post it?</legend><div className="platform-select">{campaign.platforms.map((item) => <button type="button" className={platform === item ? "is-selected" : ""} onClick={() => setPlatform(item)} key={item}><ProductIcon name={item === "Instagram" ? "instagram" : item === "YouTube" ? "youtube" : "tiktok"} />{item}<i><ProductIcon name="check" /></i></button>)}</div></fieldset>
      <label className="creator-field"><span>Public post link</span><div><ProductIcon name="link" /><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.tiktok.com/@you/video/..." inputMode="url" /></div></label>
      <label className="upload-field"><input type="file" accept="video/*" onChange={(event) => setFile(event.target.files?.[0]?.name ?? "")} /><ProductIcon name="upload" /><span><strong>{file || "Add the original video file"}</strong><small>{file ? "Ready to upload" : "MP4 or MOV · up to 250MB"}</small></span><b>{file ? "Change" : "Choose file"}</b></label>
      <p className="creator-error" role="alert">{error}</p><button className="lime-button submission-submit" type="submit">Send for verification<ProductIcon name="arrow" /></button></form>
      <aside className="submission-proof"><ArtTile src={art.submit} label="Submission" tone="gold" large /><h2>What happens next</h2><ol><li><span>01</span><p><strong>We match the post.</strong><small>The connected account must own the link.</small></p></li><li><span>02</span><p><strong>We check the brief.</strong><small>Every must-do gets a reasoned verdict.</small></p></li><li><span>03</span><p><strong>We start reading.</strong><small>Approved clips enter scheduled view checks.</small></p></li></ol></aside>
    </div>
  </div>;
}

const verificationSteps = [
  { icon: "link" as ProductIconName, title: "Post ownership", copy: "Matched to @tobioncam", done: true },
  { icon: "brief" as ProductIconName, title: "Brief requirements", copy: "Checking six requirements", done: true },
  { icon: "shield" as ProductIconName, title: "Trust signals", copy: "Looking for unusual activity", done: true },
  { icon: "eye" as ProductIconName, title: "First view reading", copy: "Queued after approval", done: false },
];

export function VerificationProgressScreen() {
  const [active, setActive] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setActive((value) => (value + 1) % 3), 1600); return () => window.clearInterval(timer); }, []);
  return <div className="dashboard-page creator-flow-page verdict-page verdict-page--processing"><CreatorHeading title="Checking your clip" copy="You can leave this page. The result will appear in My clips." />
    <section className="processing-stage"><div className="processing-orbit"><ArtTile src={art.proof} label="Verification in progress" tone="lime" large /></div><div className="processing-copy"><StatusPill tone="gold">Usually under 5 minutes</StatusPill><h2>Checks in progress</h2><p>We are confirming the post owner, brief requirements and starting view count.</p><div className="verification-list">{verificationSteps.map((step, index) => <div className={`${index === active ? "is-active" : ""}${step.done ? " is-done" : ""}`} key={step.title}><span><ProductIcon name={step.icon} /></span><p><strong>{step.title}</strong><small>{step.copy}</small></p><i>{step.done ? <ProductIcon name="check" /> : String(index + 1).padStart(2, "0")}</i></div>)}</div><div className="processing-actions"><PrimaryLink href="/dashboard/submissions/approved">Open sample verdict</PrimaryLink><Link href="/dashboard/clips">Return to My clips</Link></div></div></section>
  </div>;
}

const requirementChecks = [
  "The prepared noodles are clearly visible.",
  "‘No long thing’ appears in the clip.",
  "@indomie_nigeria and #NoLongThing are included.",
  "The clip runs between 15 and 45 seconds.",
];

export function ApprovedVerdictScreen() {
  return <div className="dashboard-page creator-flow-page verdict-page"><CreatorHeading title="Clip approved" copy="This clip can now earn from verified views." action={<StatusPill tone="lime">Earning active</StatusPill>} />
    <section className="verdict-hero verdict-hero--approved"><div className="verdict-seal"><ArtTile src={art.proof} label="Verified" tone="lime" large /><span><ProductIcon name="check" /></span></div><div className="verdict-summary"><small>Compliance verdict</small><strong><AnimatedNumber value={4} suffix="/4" duration={700} /></strong><h2>4 of 4 requirements passed</h2><p>Approved 20 Sep 2026 at 14:32 WAT. The first billable thousand begins after 1,000 verified views.</p><div className="verdict-money"><div><small>Current verified views</small><strong><AnimatedNumber value={12400} format="compact" /></strong></div><div><small>Accrued so far</small><strong><AnimatedMoney value={6000} delay={100} /></strong></div><div><small>Becomes payable</small><strong>25 Sep</strong></div></div><PrimaryLink href="/dashboard/earnings">View earnings</PrimaryLink></div></section>
    <section className="creator-sheet requirement-sheet"><div className="creator-sheet__head"><div><h2>Requirements passed</h2><p>Each requirement checked for this submission.</p></div></div><ol>{requirementChecks.map((item, index) => <li key={item}><span><ProductIcon name="check" /></span><p><strong>Requirement {String(index + 1).padStart(2, "0")}</strong>{item}</p></li>)}</ol></section>
  </div>;
}

export function RejectedVerdictScreen() {
  return <div className="dashboard-page creator-flow-page verdict-page"><CreatorHeading title="Correction needed" copy="Requirement 03 failed. This clip is not earning." action={<StatusPill tone="danger">Not earning</StatusPill>} />
    <section className="verdict-hero verdict-hero--rejected"><div className="verdict-seal"><ArtTile src={art.appeal} label="Correction needed" tone="danger" large /><span>!</span></div><div className="verdict-summary"><small>Compliance verdict</small><strong><AnimatedNumber value={3} suffix="/4" duration={700} /></strong><h2>The campaign tag is missing.</h2><p>We could not find <b>@palmpayappng</b> in the post caption. This matters because the brief requires the brand mention on the published post—not only inside the video.</p><div className="failed-proof"><span><ProductIcon name="brief" /></span><p><small>Requirement 03 failed</small><strong>Tag @palmpayappng and use #SendAmSharp.</strong><em>Checked against the public caption at 14:29 WAT.</em></p></div><div className="verdict-actions"><PrimaryLink href="/dashboard/submissions/appeal">Appeal this verdict</PrimaryLink><PrimaryLink href="/dashboard/campaigns/palmpay-send-am-sharp/submit" dark>Submit a corrected post</PrimaryLink></div></div></section>
    <section className="creator-sheet mini-checks"><h2>What did pass</h2>{requirementChecks.slice(0, 3).map((item) => <p key={item}><ProductIcon name="check" />{item}</p>)}</section>
  </div>;
}

export function AppealScreen() {
  const [reason, setReason] = useState("");
  const [file, setFile] = useState("");
  const [sent, setSent] = useState(false);
  if (sent) return <div className="dashboard-page creator-flow-page appeal-success"><ArtTile src={art.appeal} label="Human review requested" tone="gold" large /><StatusPill tone="gold">Appeal received</StatusPill><h1>Appeal submitted.</h1><p>A reviewer will check your explanation and evidence within one working day.</p><PrimaryLink href="/dashboard/clips">Return to My clips</PrimaryLink></div>;
  return <div className="dashboard-page creator-flow-page"><Link className="product-back" href="/dashboard/submissions/rejected"><ProductIcon name="chevron" /> Back to verdict</Link><CreatorHeading title="Request review" copy="Explain what the automated check missed and add evidence if needed." />
    <div className="creator-split"><form className="creator-sheet appeal-form" onSubmit={(event) => { event.preventDefault(); if (reason.trim().length >= 20) setSent(true); }}><div className="appeal-context"><StatusPill tone="danger">Requirement 03</StatusPill><p><strong>Tag @palmpayappng and use #SendAmSharp.</strong><small>Automated result: tag not found in the public caption.</small></p></div><label className="creator-field creator-field--textarea"><span>What should the reviewer check?</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="The tag is visible at the end of the caption. Please check the expanded caption…" maxLength={600} /><small>{reason.length}/600 · minimum 20</small></label><label className="upload-field upload-field--compact"><input type="file" accept="image/*,video/*" onChange={(event) => setFile(event.target.files?.[0]?.name ?? "")} /><ProductIcon name="upload" /><span><strong>{file || "Add supporting evidence"}</strong><small>Optional screenshot or screen recording</small></span><b>{file ? "Change" : "Choose"}</b></label><button className="lime-button" type="submit" disabled={reason.trim().length < 20}>Send appeal<ProductIcon name="arrow" /></button></form>
      <aside className="appeal-promise"><ArtTile src={art.appeal} label="Review details" tone="gold" /><h2>Review details</h2><ul><li><ProductIcon name="clock" /><span><strong>Review target</strong><small>Within one working day</small></span></li><li><ProductIcon name="shield" /><span><strong>Original decision retained</strong><small>The original decision stays in the audit trail.</small></span></li><li><ProductIcon name="bell" /><span><strong>Reviewer decision</strong><small>Sent with the appeal result.</small></span></li></ul></aside>
    </div>
  </div>;
}

const earningRows = [
  { date: "20 Sep", clip: "Hunger interrupted the group chat", campaign: "Indomie", views: 12400, amount: 6000, state: "Accrued", tone: "gold" as Tone },
  { date: "19 Sep", clip: "The main-character entrance", campaign: "Gbedu Records", views: 52000, amount: 20800, state: "Payable", tone: "lime" as Tone },
  { date: "14 Sep", clip: "Face card, still outside", campaign: "House of Tara", views: 20600, amount: 16000, state: "Paid", tone: "ink" as Tone },
];

export function EarningsScreen() {
  return <div className="dashboard-page creator-flow-page earnings-page"><CreatorHeading title="Earnings" copy="See what is accrued, payable and already paid." action={<PrimaryLink href="/dashboard/withdraw">Withdraw money</PrimaryLink>} />
    <section className="earnings-stage"><div className="earnings-total"><StatusPill tone="lime">Ready now</StatusPill><small>Payable balance</small><strong><AnimatedMoney value={18400} /></strong><p>From <AnimatedNumber value={36800} /> verified, billable views.</p><div className="money-wave" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div></div><ArtTile src={art.wallet} label="Payable balance" tone="gold" large /><div className="earnings-buckets"><article><span>Still in hold</span><strong><AnimatedMoney value={6000} /></strong><small>Clears 25 Sep</small></article><article><span>Paid all time</span><strong><AnimatedMoney value={184450} delay={100} /></strong><small><AnimatedNumber value={8} /> completed payouts</small></article><article><span>Lifetime views</span><strong><AnimatedNumber value={492800} format="compact" delay={200} /></strong><small>Platform verified</small></article></div></section>
    <section className="hold-strip"><div className="hold-strip__intro"><ProductIcon name="clock" /><span><strong>The five-day hold</strong><small>Views keep earning immediately. Withdrawal unlocks after the fraud-check window.</small></span></div><div className="hold-track"><span className="is-past">20<small>Earned</small></span><i className="is-past" /><span className="is-past">22<small>Checking</small></span><i /><span>25<small>Payable</small></span></div></section>
    <section className="creator-sheet earnings-ledger"><div className="creator-sheet__head"><div><h2>Earning history</h2><p>Each amount includes the clip and verified view count.</p></div></div><div className="earnings-ledger__labels"><span>Date</span><span>Clip</span><span>Billable views</span><span>Amount</span><span>Status</span></div>{earningRows.map((row) => <article key={row.clip}><span>{row.date}</span><p><strong>{row.clip}</strong><small>{row.campaign}</small></p><strong><AnimatedNumber value={row.views} format="compact" /></strong><strong><AnimatedMoney value={row.amount} /></strong><StatusPill tone={row.tone}>{row.state}</StatusPill></article>)}</section>
  </div>;
}

export function WithdrawScreen() {
  const router = useRouter();
  const balance = 18400;
  const [amount, setAmount] = useState("18400");
  const number = Math.min(balance, Math.max(0, Number(amount) || 0));
  const valid = number >= 1000;
  return <div className="dashboard-page creator-flow-page withdraw-page"><Link className="product-back" href="/dashboard/earnings"><ProductIcon name="chevron" /> Back to earnings</Link><CreatorHeading title="Withdraw money" copy="Choose an amount and confirm the bank account." />
    <div className="creator-split"><form className="creator-sheet withdraw-form" onSubmit={(event) => { event.preventDefault(); if (valid) { window.localStorage.setItem("clippit:last-withdrawal", String(number)); router.push("/dashboard/payouts/receipt"); } }}><div className="withdraw-balance"><small>Available to withdraw</small><strong><AnimatedMoney value={balance} /></strong><StatusPill tone="lime">Cleared</StatusPill></div><label className="amount-field"><span>Amount</span><div><b>₦</b><input value={amount} onChange={(event) => setAmount(event.target.value.replace(/\D/g, "").slice(0, 8))} inputMode="numeric" aria-label="Withdrawal amount" /></div></label><div className="amount-chips">{[5000, 10000, balance].map((value) => <button type="button" className={number === value ? "is-selected" : ""} onClick={() => setAmount(String(value))} key={value}>{value === balance ? "All" : money(value)}</button>)}</div><div className="withdraw-bank"><span><ProductIcon name="bank" /></span><p><small>Destination</small><strong>GTBank · 6789</strong><em>Tobi Adeyemi · Verified</em></p><Link href="/dashboard/settings#payouts">Change</Link></div><dl className="withdraw-summary"><div><dt>Withdrawal</dt><dd><AnimatedMoney value={number} /></dd></div><div><dt>Transfer fee</dt><dd><AnimatedMoney value={0} /></dd></div><div><dt>You receive</dt><dd><AnimatedMoney value={number} delay={80} /></dd></div></dl><button className="lime-button" type="submit" disabled={!valid}>Confirm withdrawal<ProductIcon name="arrow" /></button></form>
      <aside className="withdraw-aside"><ArtTile src={art.withdraw} label="Money to bank" tone="gold" large /><h2>Transfer time</h2><p>Most transfers arrive within 24 hours. Rejected transfers return to your payable balance.</p><div><ProductIcon name="shield" />Encrypted bank destination</div></aside></div>
  </div>;
}

export function PayoutReceiptScreen() {
  const [amount, setAmount] = useState(18400);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = Number(window.localStorage.getItem("clippit:last-withdrawal"));
      if (stored >= 1000) setAmount(stored);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  const reference = useMemo(() => "CLP-260920-1847", []);
  return <div className="dashboard-page creator-flow-page receipt-page"><section className="receipt-hero"><div className="receipt-art"><ArtTile src={art.withdraw} label="Transfer sent" tone="gold" large /><span><ProductIcon name="check" /></span></div><StatusPill tone="lime">Transfer successful</StatusPill><h1><AnimatedMoney value={amount} /></h1><p>Sent to GTBank ending 6789.</p><div className="receipt-actions"><PrimaryLink href="/dashboard/earnings">Back to earnings</PrimaryLink><button type="button" className="ink-button" onClick={() => window.print()}>Download receipt<ProductIcon name="brief" /></button></div></section>
    <section className="creator-sheet payout-receipt"><div className="payout-receipt__top"><span className="receipt-brand"><Image src="/assets/clippit-mark-light.png" alt="" width={34} height={34} /><span><b>Clippit</b><small>Payout receipt</small></span></span><strong>{reference}</strong></div><dl><div><dt>Status</dt><dd><StatusPill tone="lime">Successful</StatusPill></dd></div><div><dt>Creator</dt><dd>Tobi Adeyemi</dd></div><div><dt>Bank destination</dt><dd>GTBank · 0123 456 789</dd></div><div><dt>Initiated</dt><dd>20 Sep 2026 · 15:07 WAT</dd></div><div><dt>Amount sent</dt><dd><AnimatedMoney value={amount} /></dd></div><div><dt>Fee</dt><dd><AnimatedMoney value={0} /></dd></div></dl><div className="receipt-proof"><h2>Where this money came from</h2><div><span><ProductIcon name="play" /></span><p><strong><AnimatedNumber value={2} /> approved clips</strong><small>Indomie + Gbedu Records</small></p><i /><span><ProductIcon name="eye" /></span><p><strong><AnimatedNumber value={36800} /> billable views</strong><small>Read directly from platforms</small></p><i /><span><ProductIcon name="bank" /></span><p><strong><AnimatedMoney value={amount} /> landed</strong><small>Payaza transfer complete</small></p></div></div></section>
  </div>;
}
