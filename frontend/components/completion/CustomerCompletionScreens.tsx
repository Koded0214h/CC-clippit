"use client";
/* eslint-disable react/no-unescaped-entities */

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

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

function ServiceFrame({ children, active = "Help" }: { children: ReactNode; active?: "Help" | "Support" | "Legal" | "Account" }) {
  return <div className="completion-service">
    <header className="service-bar">
      <Link href="/" className="service-logo"><Mark /><strong>Clippit</strong></Link>
      <nav aria-label="Customer service navigation">
        <Link className={active === "Help" ? "is-active" : ""} href="/help">Help</Link>
        <Link className={active === "Support" ? "is-active" : ""} href="/support/tickets">Support</Link>
        <Link className={active === "Legal" ? "is-active" : ""} href="/legal">Legal</Link>
      </nav>
      <Link className="service-workspace" href="/dashboard">Open workspace<ProductIcon name="arrow" /></Link>
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
      {visible.length === 0 && <div className="completion-empty"><ProductIcon name="search" /><h2>No guide matched “{query}”</h2><p>Try a shorter phrase or send the support team a message.</p><BigAction href="/support/tickets/new">Contact support</BigAction></div>}
      <aside className="support-ribbon"><div><strong>Still stuck?</strong><span>Send the details once. Support can see the campaign, payout or transaction you attach.</span></div><BigAction href="/support/tickets/new" tone="ink">Start a support ticket</BigAction></aside>
    </section>
  </ServiceFrame>;
}

export function HelpArticleScreen({ slug }: { slug: string }) {
  const title = slug === "money-and-payouts" ? "Money and payouts" : slug === "connected-social-accounts" ? "Connected social accounts" : slug === "brand-workspace" ? "Using the brand workspace" : slug === "account-and-safety" ? "Account and safety" : slug === "how-views-are-checked" ? "How views are checked" : "How campaigns work";
  const steps = title.includes("Money") ? ["Approved clips begin earning from verified platform views.", "New earnings stay on hold for five days.", "When the hold ends, the money moves to Payable.", "A withdrawal sends Payable money to your verified bank account."] : title.includes("views") ? ["Clippit reads views from the connected publishing account.", "Only complete groups of 1,000 views are billable.", "Campaign caps and remaining pot are applied to every reading.", "The reading history stays attached to the earning entry."] : ["Open the campaign and read every requirement.", "Join before posting so the campaign can track your entry.", "Publish from a connected account and submit the public link.", "Follow the check result from My clips."];
  return <ServiceFrame>
    <article className="article-shell">
      <CompletionHead back="/help" kicker="Help guide" title={title} copy="The current Clippit process, in plain language." />
      <div className="article-layout"><aside><strong>In this guide</strong>{steps.map((step, index) => <a href={`#step-${index + 1}`} key={step}>{index + 1}. {step.split(".")[0]}</a>)}<BigAction href="/support/tickets/new" tone="gold">Ask support</BigAction></aside><div className="article-copy"><div className="article-note"><ProductIcon name="shield" /><p><strong>Clippit records the evidence.</strong><span>Campaign rules, platform readings and money movements remain attached to the relevant transaction.</span></p></div>{steps.map((step, index) => <section id={`step-${index + 1}`} key={step}><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{step}</h2><p>{index === 0 ? "The campaign screen shows the current rate, remaining pot, platform and any closing date before you act." : "If the status changes, the activity and notification screens show what changed and what you can do next."}</p></div></section>)}</div></div>
    </article>
  </ServiceFrame>;
}

const tickets = [
  { id: "CLP-2841", subject: "Instagram account needs reconnecting", category: "Connected accounts", time: "12 min ago", status: "Support replied", tone: "lime" as Tone },
  { id: "CLP-2718", subject: "Question about a five-day hold", category: "Earnings", time: "18 Sep", status: "Waiting for you", tone: "gold" as Tone },
  { id: "CLP-2430", subject: "Campaign brief was unclear", category: "Campaigns", time: "2 Sep", status: "Resolved", tone: "paper" as Tone },
];

export function SupportTicketsScreen() {
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Support tickets" copy="Your conversations with the Clippit support team." action={<BigAction href="/support/tickets/new">New ticket</BigAction>} /><div className="ticket-board"><aside><strong>2 open</strong><span>Average first reply</span><b>under 2 hours</b><MiniArt src={art.review} tone="gold" /></aside><section>{tickets.map((ticket) => <Link href={`/support/tickets/${ticket.id}`} key={ticket.id} className="ticket-row"><span><ProductIcon name={ticket.category === "Earnings" ? "wallet" : ticket.category === "Campaigns" ? "campaigns" : "link"} /></span><p><small>{ticket.id} · {ticket.category}</small><strong>{ticket.subject}</strong><em>{ticket.time}</em></p><Status tone={ticket.tone}>{ticket.status}</Status><ProductIcon name="arrow" /></Link>)}</section></div></section></ServiceFrame>;
}

export function NewSupportTicketScreen() {
  const [sent, setSent] = useState(false);
  const [category, setCategory] = useState("Campaigns");
  if (sent) return <ServiceFrame active="Support"><section className="completion-result"><MiniArt src={art.proof} /><Status tone="lime">Ticket CLP-2914</Status><h1>Your message is with support.</h1><p>We will notify you when the team replies. You can add more details from the ticket.</p><BigAction href="/support/tickets/CLP-2914">Open ticket</BigAction></section></ServiceFrame>;
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" title="Contact support" copy="Choose the issue and include the reference that support should inspect." /><form className="completion-form support-form" onSubmit={(event) => { event.preventDefault(); setSent(true); }}><div className="form-main"><fieldset><legend>What is this about?</legend><div className="choice-grid choice-grid--compact">{["Campaigns", "Money", "Connected accounts", "Account access"].map((item) => <label className={category === item ? "is-selected" : ""} key={item}><input type="radio" name="category" value={item} checked={category === item} onChange={() => setCategory(item)} /><ProductIcon name={item === "Money" ? "wallet" : item === "Campaigns" ? "campaigns" : item === "Connected accounts" ? "link" : "shield"} /><span>{item}</span></label>)}</div></fieldset><label><span>Subject</span><input required placeholder="A short description of the problem" /></label><label><span>What happened?</span><textarea required rows={7} placeholder="Tell us what you expected, what happened and when it happened." /></label><label><span>Related reference <small>Optional</small></span><input placeholder="Campaign, payout or transaction ID" /></label></div><aside className="form-aside"><div><ProductIcon name="upload" /><strong>Add screenshots or documents</strong><span>PNG, JPG or PDF · up to 10 MB each</span><input type="file" multiple /></div><p><ProductIcon name="shield" />Do not upload passwords, verification codes or full card details.</p><button className="completion-submit" type="submit">Send to support<ProductIcon name="arrow" /></button></aside></form></section></ServiceFrame>;
}

export function SupportTicketDetailScreen({ id }: { id: string }) {
  const [messages, setMessages] = useState(["I reconnected Instagram, but the status still says it needs attention.", "We found an expired permission. Please reconnect once more from Connected accounts; the new permission set is ready."]);
  const [reply, setReply] = useState("");
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" kicker={id} title="Instagram account needs reconnecting" action={<Status tone="lime">Support replied</Status>} /><div className="thread-layout"><section className="message-thread"><div className="thread-day">Today</div>{messages.map((message, index) => <article className={index % 2 ? "is-support" : "is-customer"} key={`${message}-${index}`}><span>{index % 2 ? <Mark /> : "TO"}</span><div><header><strong>{index % 2 ? "Clippit support" : "You"}</strong><time>{index ? "10:42" : "10:18"}</time></header><p>{message}</p></div></article>)}<form onSubmit={(event) => { event.preventDefault(); if (reply.trim()) { setMessages((current) => [...current, reply.trim()]); setReply(""); } }}><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Write a reply" rows={4} /><div><button type="button"><ProductIcon name="upload" />Attach file</button><button type="submit" disabled={!reply.trim()}>Send reply<ProductIcon name="arrow" /></button></div></form></section><aside className="case-facts"><h2>Ticket details</h2><dl><div><dt>Status</dt><dd>Open</dd></div><div><dt>Category</dt><dd>Connected accounts</dd></div><div><dt>Created</dt><dd>22 Sep 2026</dd></div><div><dt>Account</dt><dd>@tobioncam</dd></div></dl><Link href="/dashboard/accounts">Open connected accounts<ProductIcon name="arrow" /></Link></aside></div></section></ServiceFrame>;
}

const disputes = [
  { id: "DSP-0419", title: "Earning entry VIEW-21904", amount: "₦18,400", state: "More information needed", date: "Reply by 25 Sep", tone: "gold" as Tone },
  { id: "DSP-0372", title: "Submission SUB-01871", amount: "No money held", state: "Decision issued", date: "Closed 12 Sep", tone: "paper" as Tone },
];

export function DisputesScreen() {
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Disputes" copy="Formal reviews of a money movement or product decision." action={<BigAction href="/disputes/new">Open a dispute</BigAction>} /><div className="dispute-ledger"><header><span>Case</span><span>Value</span><span>Status</span><span>Deadline</span></header>{disputes.map((item) => <Link href={`/disputes/${item.id}`} key={item.id}><p><small>{item.id}</small><strong>{item.title}</strong></p><b>{item.amount}</b><Status tone={item.tone}>{item.state}</Status><time>{item.date}</time><ProductIcon name="arrow" /></Link>)}</div><div className="policy-note"><ProductIcon name="shield" /><p><strong>Use support for ordinary questions.</strong><span>Open a dispute when you need a formal decision about money, a verdict or a transaction.</span></p><Link href="/support/tickets/new">Ask support first</Link></div></section></ServiceFrame>;
}

export function NewDisputeScreen() {
  const [step, setStep] = useState(1);
  const [kind, setKind] = useState("Earning");
  return <ServiceFrame active="Support"><section className="service-content completion-page dispute-create"><CompletionHead back="/disputes" title={step === 3 ? "Check your dispute" : "Open a dispute"} copy="A dispute creates a formal, time-stamped case." /><div className="form-progress"><span style={{ width: `${step * 33.333}%` }} /></div>{step === 1 && <section className="step-sheet"><strong>What needs a formal review?</strong><div className="choice-grid">{["Earning", "Payout", "Submission verdict", "Campaign funding"].map((item) => <button className={kind === item ? "is-selected" : ""} onClick={() => setKind(item)} key={item}><ProductIcon name={item === "Earning" || item === "Payout" ? "wallet" : item === "Submission verdict" ? "play" : "campaigns"} /><span>{item}</span><small>{item === "Earning" ? "Amount, view reading or hold" : item === "Payout" ? "Failed or missing transfer" : item === "Submission verdict" ? "Escalate after an appeal" : "Funding, fee or refund"}</small></button>)}</div><button className="completion-submit" onClick={() => setStep(2)}>Continue<ProductIcon name="arrow" /></button></section>}{step === 2 && <section className="step-sheet"><strong>Give us the evidence</strong><label><span>{kind} reference</span><input defaultValue="VIEW-21904" /></label><label><span>What decision should be reviewed?</span><textarea rows={6} placeholder="Explain what is incorrect and the outcome you are requesting." /></label><label className="file-drop"><ProductIcon name="upload" /><strong>Add evidence</strong><small>Images, receipts or documents</small><input type="file" multiple /></label><div className="step-actions"><button onClick={() => setStep(1)}>Back</button><button className="completion-submit" onClick={() => setStep(3)}>Review dispute<ProductIcon name="arrow" /></button></div></section>}{step === 3 && <section className="step-sheet review-claim"><Status tone="gold">Not submitted</Status><h2>{kind} · VIEW-21904</h2><dl><div><dt>Requested review</dt><dd>Verified-view earning calculation</dd></div><div><dt>Money involved</dt><dd>₦18,400</dd></div><div><dt>Evidence</dt><dd>2 files attached</dd></div><div><dt>Response window</dt><dd>Usually within 5 working days</dd></div></dl><label><input type="checkbox" />I confirm the information is complete and accurate.</label><BigAction href="/disputes/DSP-0420">Submit dispute</BigAction></section>}</section></ServiceFrame>;
}

export function DisputeDetailScreen({ id }: { id: string }) {
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" kicker={id} title="Earning entry VIEW-21904" action={<Status tone="gold">More information needed</Status>} /><div className="dispute-case"><section className="case-timeline"><article className="is-current"><span><ProductIcon name="brief" /></span><div><small>22 Sep · 14:12</small><h2>Clippit requested the original platform insight</h2><p>Upload the insights screen that shows the post URL and total views.</p><button><ProductIcon name="upload" />Upload requested evidence</button></div></article><article><span><ProductIcon name="eye" /></span><div><small>22 Sep · 10:06</small><h2>Review started</h2><p>The earning entry and its platform readings were attached to the case.</p></div></article><article><span><ProductIcon name="check" /></span><div><small>21 Sep · 18:40</small><h2>Dispute received</h2><p>Your original claim and two evidence files were locked.</p></div></article></section><aside className="decision-clock"><span>Reply before</span><strong>25</strong><b>September</b><small>2 days remaining</small><dl><div><dt>Money on hold</dt><dd>₦18,400</dd></div><div><dt>Assigned team</dt><dd>Trust review</dd></div><div><dt>Case type</dt><dd>Earning</dd></div></dl></aside></div></section></ServiceFrame>;
}

export function AccountDataScreen() {
  const [requested, setRequested] = useState(false);
  return <ServiceFrame active="Account"><section className="service-content completion-page"><CompletionHead title="Your data" copy="Download the account information Clippit keeps for you." /><div className="data-vault"><section><div className="vault-door"><span><ProductIcon name="shield" /></span><i /><i /><i /></div><h2>{requested ? "Your export is being prepared" : "One private archive"}</h2><p>{requested ? "We will email you when the download is ready. The link will expire after 24 hours." : "Includes your profile, campaign activity, submissions, platform connections and money records."}</p>{requested ? <Status tone="gold">Usually ready within 24 hours</Status> : <button className="completion-submit" onClick={() => setRequested(true)}>Request my data<ProductIcon name="arrow" /></button>}</section><aside><h2>Included in the export</h2>{["Profile and preferences", "Campaign joins and submissions", "Earnings and withdrawals", "Support and dispute history", "Account activity and consents"].map((item) => <p key={item}><ProductIcon name="check" />{item}</p>)}<small>Passwords, payment-provider secrets and internal fraud signals are never included.</small></aside></div></section></ServiceFrame>;
}

export function DeleteAccountScreen() {
  const [confirmed, setConfirmed] = useState(false);
  return <ServiceFrame active="Account"><section className="service-content completion-page"><CompletionHead title="Delete account" copy="Check what must be settled before deletion can begin." /><div className="delete-layout"><section><h2>Two things need attention</h2><article><span><ProductIcon name="wallet" /></span><p><strong>₦18,400 is still payable</strong><small>Withdraw it before requesting deletion.</small></p><Link href="/dashboard/withdraw">Withdraw money</Link></article><article><span><ProductIcon name="brief" /></span><p><strong>One support ticket is open</strong><small>Close it or wait for the current reply.</small></p><Link href="/support/tickets">Open tickets</Link></article><article className="is-clear"><span><ProductIcon name="check" /></span><p><strong>No active campaigns or disputes</strong><small>This account has no other deletion blockers.</small></p></article></section><aside><MiniArt src={art.bank} tone="gold" /><h2>After the blockers are cleared</h2><p>Your public profile is hidden immediately. Required transaction and safety records are retained under the applicable policy; other eligible account data is deleted or anonymised.</p><label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />I understand this cannot be undone.</label><button disabled={!confirmed}>Request account deletion</button></aside></div></section></ServiceFrame>;
}

const legalDocs = [
  { slug: "terms", title: "Terms of use", copy: "The rules for using a Clippit account.", date: "Effective 1 September 2026" },
  { slug: "privacy", title: "Privacy policy", copy: "What data Clippit uses and why.", date: "Effective 1 September 2026" },
  { slug: "community-rules", title: "Community rules", copy: "Content and conduct expected on Clippit.", date: "Effective 12 September 2026" },
  { slug: "campaign-funding", title: "Campaign funding terms", copy: "Funding, fees, pots, payouts and refunds.", date: "Effective 12 September 2026" },
];

export function LegalCentreScreen() {
  return <ServiceFrame active="Legal"><section className="legal-hero"><div><Status tone="gold">Versioned documents</Status><h1>Legal centre</h1><p>Terms, policies and the versions accepted by your account.</p></div><div className="legal-stamp"><ProductIcon name="shield" /><strong>4/4</strong><span>current versions accepted</span></div></section><section className="service-content legal-list">{legalDocs.map((doc, index) => <Link href={`/legal/${doc.slug}`} key={doc.slug}><span>{String(index + 1).padStart(2, "0")}</span><p><strong>{doc.title}</strong><small>{doc.copy}</small></p><time>{doc.date}</time><ProductIcon name="arrow" /></Link>)}</section></ServiceFrame>;
}

export function LegalDocumentScreen({ slug }: { slug: string }) {
  const doc = legalDocs.find((item) => item.slug === slug) ?? legalDocs[0];
  return <ServiceFrame active="Legal"><article className="legal-document"><CompletionHead back="/legal" kicker="Version 2.1 · Accepted" title={doc.title} copy={doc.date} /><div className="legal-document__body"><aside><strong>Contents</strong><a href="#overview">Overview</a><a href="#account">Your account</a><a href="#money">Money and records</a><a href="#contact">Questions</a><button onClick={() => window.print()}>Print document<ProductIcon name="brief" /></button></aside><div><section id="overview"><h2>1. Overview</h2><p>This document explains the agreement between you and Clippit for the services named here. It applies to the version and effective date shown above.</p></section><section id="account"><h2>2. Your account</h2><p>Keep your account information accurate and protect your sign-in details. Actions taken through the account may be treated as authorised until you report unauthorised access.</p></section><section id="money"><h2>3. Money and records</h2><p>Campaign funding, creator earnings, fees, refunds and withdrawals are recorded against immutable transaction references. Specific timing and eligibility are shown before each money action.</p></section><section id="contact"><h2>4. Questions</h2><p>Use the support centre if you need an explanation of how this document applies to a Clippit action.</p><BigAction href="/support/tickets/new" tone="ink">Contact support</BigAction></section></div></div></article></ServiceFrame>;
}

export function ConsentUpdateScreen() {
  const [accepted, setAccepted] = useState(false);
  return <ServiceFrame active="Legal"><section className="consent-screen"><div className="consent-sheet"><Status tone="gold">Action required</Status><h1>Campaign funding terms changed.</h1><p>Review the changes before you fund or join another campaign.</p><ol><li><span>1</span><div><strong>Refund timing is clearer</strong><p>Unused balances show their expected return date after campaign close.</p></div></li><li><span>2</span><div><strong>Platform reading disputes have a deadline</strong><p>The deadline now appears beside every eligible transaction.</p></div></li><li><span>3</span><div><strong>No change to your current money</strong><p>Existing earnings, pots and transaction references remain unchanged.</p></div></li></ol><label><input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />I have read and accept version 2.1 of the campaign funding terms.</label><button className="completion-submit" disabled={!accepted}>Accept and continue<ProductIcon name="arrow" /></button><Link href="/legal/campaign-funding">Read the full document</Link></div><MiniArt src={art.brief} tone="gold" /></section></ServiceFrame>;
}

export function ReceiptVerificationScreen({ reference }: { reference: string }) {
  return <ServiceFrame><section className="verify-receipt"><div className="verify-radar"><i /><i /><i /><span><ProductIcon name="check" /></span></div><Status tone="lime">Authentic Clippit record</Status><h1>This receipt is valid.</h1><p>The transaction reference and amount match an immutable Clippit record.</p><section><header><Mark /><div><strong>Clippit</strong><span>Receipt verification</span></div></header><dl><div><dt>Reference</dt><dd>{reference}</dd></div><div><dt>Amount</dt><dd>₦18,400</dd></div><div><dt>Status</dt><dd>Settled</dd></div><div><dt>Processed</dt><dd>20 Sep 2026 · 15:07 WAT</dd></div><div><dt>Recipient</dt><dd>Tobi Adeyemi · GTBank ••6789</dd></div></dl><footer><ProductIcon name="shield" />Verified on 22 Sep 2026</footer></section><small>Clippit will never ask for a password or verification code on a receipt verification page.</small></section></ServiceFrame>;
}

function VerificationStart({ role }: { role: "creator" | "brand" }) {
  const brand = role === "brand";
  const base = brand ? "/brand/verification" : "/dashboard/verification";
  return <div className={`${brand ? "brand-page" : "dashboard-page"} completion-workspace`}><CompletionHead title={brand ? "Verify Gbedu Records" : "Verify your identity"} copy={brand ? "Required before higher campaign limits and organisation billing are enabled." : "Required before your first withdrawal."} action={<Status tone="gold">Not started</Status>} /><section className="verification-intro"><div><span className="verification-number">01</span><h2>{brand ? "Business details" : "Identity details"}</h2><p>{brand ? "Legal business name, registration number, address and an authorised representative." : "Your legal name, date of birth, phone number and address."}</p></div><div><span className="verification-number">02</span><h2>{brand ? "Business documents" : "Identity document"}</h2><p>{brand ? "Registration document and a recent proof of business address." : "A clear government-issued document and a quick face check."}</p></div><div><span className="verification-number">03</span><h2>Review</h2><p>Track every check and correct anything that cannot be verified.</p></div><aside><MiniArt src={brand ? art.brief : art.proof} tone={brand ? "gold" : "lime"} /><strong>Usually reviewed within one working day</strong><small>Your documents are encrypted and are not shown on your public profile.</small><BigAction href={`${base}/${brand ? "business" : "identity"}`}>Start verification</BigAction></aside></section></div>;
}

export function CreatorVerificationScreen() { return <VerificationStart role="creator" />; }
export function BrandVerificationScreen() { return <VerificationStart role="brand" />; }

function DetailsForm({ role }: { role: "creator" | "brand" }) {
  const brand = role === "brand";
  const base = brand ? "/brand/verification" : "/dashboard/verification";
  return <div className={`${brand ? "brand-page" : "dashboard-page"} completion-workspace`}><CompletionHead back={base} kicker="Step 1 of 3" title={brand ? "Business details" : "Identity details"} copy="Enter the details exactly as they appear on the document." /><form className="identity-sheet"><div className="identity-grid">{brand ? <><label><span>Registered business name</span><input defaultValue="Gbedu Records Limited" /></label><label><span>Registration number</span><input placeholder="RC number" /></label><label className="is-wide"><span>Registered address</span><input placeholder="Street, city and state" /></label><label><span>Representative's legal name</span><input defaultValue="Tomi Odukoya" /></label><label><span>Role in the organisation</span><select defaultValue="Director"><option>Director</option><option>Owner</option><option>Employee</option><option>Authorised agent</option></select></label></> : <><label><span>Legal first name</span><input defaultValue="Tobi" /></label><label><span>Legal last name</span><input defaultValue="Adeyemi" /></label><label><span>Date of birth</span><input type="date" /></label><label><span>Phone number</span><input defaultValue="+234 803 000 2041" /></label><label className="is-wide"><span>Residential address</span><input placeholder="Street, city and state" /></label></>}</div><div className="identity-confirm"><ProductIcon name="shield" /><p><strong>Use your legal details.</strong><span>They are used for verification and money controls, not your public display name.</span></p></div><BigAction href={`${base}/documents`}>Save and continue</BigAction></form></div>;
}

export function CreatorIdentityScreen() { return <DetailsForm role="creator" />; }
export function BrandBusinessScreen() { return <DetailsForm role="brand" />; }

function DocumentsScreen({ role }: { role: "creator" | "brand" }) {
  const brand = role === "brand";
  const base = brand ? "/brand/verification" : "/dashboard/verification";
  const [files, setFiles] = useState<string[]>([]);
  const add = (event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.target.files ?? []).map((file) => file.name));
  return <div className={`${brand ? "brand-page" : "dashboard-page"} completion-workspace`}><CompletionHead back={`${base}/${brand ? "business" : "identity"}`} kicker="Step 2 of 3" title={brand ? "Business documents" : "Identity document"} copy="Make every edge visible and keep text in focus." /><section className="document-studio"><div className="document-guide"><div className="document-frame"><i /><i /><i /><i /><ProductIcon name={brand ? "brief" : "person"} /></div><h2>{brand ? "Required documents" : "Choose a document"}</h2><p>{brand ? "CAC registration document and proof of business address issued within the last three months." : "National ID, driver's licence, voter card or international passport."}</p><ul><li><ProductIcon name="check" />Original document</li><li><ProductIcon name="check" />Colour image or PDF</li><li><ProductIcon name="check" />No glare or covered details</li></ul></div><div className="upload-stack"><label><ProductIcon name="upload" /><strong>{brand ? "Upload registration document" : "Upload the front of your document"}</strong><span>JPG, PNG or PDF · up to 10 MB</span><input type="file" onChange={add} /></label><label><ProductIcon name="camera" /><strong>{brand ? "Upload proof of address" : "Take a quick face photo"}</strong><span>{brand ? "Bank statement or utility bill" : "Use this device camera in good light"}</span><input type="file" accept="image/*" capture="user" onChange={add} /></label>{files.length > 0 && <div className="upload-ready">{files.map((file) => <p key={file}><ProductIcon name="check" /><span><strong>{file}</strong><small>Ready to submit</small></span></p>)}</div>}<BigAction href={`${base}/status`}>Submit for review</BigAction></div></section></div>;
}

export function CreatorDocumentsScreen() { return <DocumentsScreen role="creator" />; }
export function BrandDocumentsScreen() { return <DocumentsScreen role="brand" />; }

function VerificationStatus({ role }: { role: "creator" | "brand" }) {
  const brand = role === "brand";
  return <div className={`${brand ? "brand-page" : "dashboard-page"} completion-workspace`}><CompletionHead title="Verification status" copy={brand ? "Gbedu Records Limited" : "Tobi Adeyemi"} action={<Status tone="gold">In review</Status>} /><section className="verification-status"><div className="status-orbit"><i /><i /><i /><span><ProductIcon name="shield" /></span><strong>Reviewing</strong><small>Submitted today · 14:28</small></div><section><article className="is-complete"><span><ProductIcon name="check" /></span><p><strong>{brand ? "Business details" : "Identity details"}</strong><small>Details passed format and duplicate checks.</small></p><Status tone="lime">Complete</Status></article><article className="is-current"><span><ProductIcon name="eye" /></span><p><strong>{brand ? "Document check" : "Identity document"}</strong><small>A reviewer is checking the submitted images.</small></p><Status tone="gold">In review</Status></article><article><span>3</span><p><strong>Final decision</strong><small>You will get a notification as soon as this is complete.</small></p><Status>Waiting</Status></article></section><aside><ProductIcon name="clock" /><div><strong>Nothing else is needed right now.</strong><span>If a document needs correction, this screen will show exactly what to replace.</span></div></aside></section></div>;
}

export function CreatorVerificationStatusScreen() { return <VerificationStatus role="creator" />; }
export function BrandVerificationStatusScreen() { return <VerificationStatus role="brand" />; }

const statementRows = [
  ["20 Sep", "Main character sound", "36,800 views", 18400, "Payable"],
  ["18 Sep", "No long thing", "64,000 views", 32000, "On hold"],
  ["14 Sep", "Campus chop stories", "22,000 views", 11000, "Paid"],
  ["09 Sep", "Weekend reset", "18,000 views", 9000, "Paid"],
] as const;

export function EarningsStatementScreen() {
  const [range, setRange] = useState("September 2026");
  const total = useMemo(() => statementRows.reduce((sum, row) => sum + row[3], 0), []);
  return <div className="dashboard-page completion-workspace"><CompletionHead back="/dashboard/earnings" title="Earnings statement" copy="Every earning entry, view source and payout status." action={<button className="statement-download" onClick={() => window.print()}>Download statement<ProductIcon name="brief" /></button>} /><section className="statement-summary"><div><small>Statement period</small><select value={range} onChange={(event) => setRange(event.target.value)}><option>September 2026</option><option>August 2026</option><option>All time</option></select></div><div><small>Total earned</small><strong><AnimatedNumber value={total} format="money" /></strong></div><div><small>Entries</small><strong><AnimatedNumber value={statementRows.length} padStart={2} /></strong></div><MiniArt src={art.wallet} tone="gold" /></section><section className="statement-table"><header><span>Date</span><span>Campaign</span><span>Platform reading</span><span>Amount</span><span>Status</span></header>{statementRows.map((row) => <article key={row[0] + row[1]}><time>{row[0]}</time><strong>{row[1]}</strong><span>{row[2]}</span><b>₦{row[3].toLocaleString()}</b><Status tone={row[4] === "Payable" ? "lime" : row[4] === "On hold" ? "gold" : "paper"}>{row[4]}</Status></article>)}<footer><span>Statement ID STMT-TO-0926</span><strong>₦{total.toLocaleString()}</strong></footer></section></div>;
}

export function PublicCreatorProfileScreen({ handle }: { handle: string }) {
  return <ServiceFrame><section className="public-profile"><header><div className="profile-photo"><Image src="/assets/photos/creator-vlogger-pexels-6954220.jpg" alt="Tobi On Cam" fill sizes="260px" /></div><div><Status tone="lime"><ProductIcon name="shield" />Verified creator</Status><h1>Tobi On Cam</h1><p>@{handle} · Lagos, Nigeria</p><blockquote>Comedy, food and everyday Lagos stories.</blockquote><div><span>Comedy</span><span>Food</span><span>Lifestyle</span></div></div><aside><small>Verified views</small><strong><AnimatedNumber value={428600} format="compact" suffix=" views" /></strong><span>Across approved Clippit campaigns</span></aside></header><section className="profile-work"><div className="profile-work__head"><div><h2>Approved campaign work</h2><p>Only clips approved through Clippit appear here.</p></div><span>6 clips</span></div><div>{[
    ["/assets/photos/creator-studio-pexels-8359963.jpg", "Main character sound", "128K"],
    ["/assets/photos/creator-fashion-pexels-7585630.jpg", "Weekend reset", "94K"],
    ["/assets/photos/afro-style.jpg", "No long thing", "72K"],
  ].map(([src, title, views]) => <article key={title}><div><Image src={src} alt="" fill sizes="(max-width: 700px) 100vw, 33vw" /><span><ProductIcon name="play" /></span></div><p><strong>{title}</strong><small>{views} verified views</small></p></article>)}</div></section><footer><span><Mark /><strong>Profile verified by Clippit</strong></span><Link href="/auth/sign-up">Create your Clippit profile<ProductIcon name="arrow" /></Link></footer></section></ServiceFrame>;
}

const members = [
  { initials: "TO", name: "Tomi Odukoya", email: "tomi@gbedurecords.com", role: "Owner", status: "Active" },
  { initials: "AM", name: "Amina Musa", email: "amina@gbedurecords.com", role: "Campaign manager", status: "Active" },
  { initials: "KO", name: "Kunle Ojo", email: "kunle@gbedurecords.com", role: "Reviewer", status: "Active" },
  { initials: "IN", name: "Ife Nwosu", email: "ife@gbedurecords.com", role: "Finance", status: "Invited" },
];

export function BrandTeamScreen() {
  return <div className="brand-page completion-workspace"><CompletionHead title="Team" copy="Who can access Gbedu Records and what they can do." action={<BigAction href="/brand/team/invite">Invite someone</BigAction>} /><section className="team-board"><aside><strong><AnimatedNumber value={4} padStart={2} /></strong><span>people</span><div><b>1</b> invitation waiting</div><p>Owner access cannot be removed until ownership is transferred.</p></aside><div><header><span>Member</span><span>Role</span><span>Status</span><span>Access</span></header>{members.map((member) => <article key={member.email}><i>{member.initials}</i><p><strong>{member.name}</strong><small>{member.email}</small></p><b>{member.role}</b><Status tone={member.status === "Active" ? "lime" : "gold"}>{member.status}</Status><button aria-label={`Manage ${member.name}`}><ProductIcon name="more" /></button></article>)}</div></section></div>;
}

export function BrandInviteScreen() {
  const [role, setRole] = useState("Campaign manager");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<{ email: string; role: string } | null>(null);
  const roles = {
    "Campaign manager": ["Create and edit campaigns", "Review submissions", "View campaign transactions"],
    Reviewer: ["Review submissions", "Request corrections", "View campaign performance"],
    Finance: ["View billing and invoices", "Fund campaigns", "Request eligible refunds"],
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const invite = { email: email.trim().toLowerCase(), role, sentAt: new Date().toISOString() };
    try {
      const existing = JSON.parse(window.localStorage.getItem("clippit:brand-team-invites") || "[]") as Array<typeof invite>;
      window.localStorage.setItem("clippit:brand-team-invites", JSON.stringify([invite, ...existing.filter((item) => item.email !== invite.email)]));
    } catch {}
    setSent(invite);
    window.requestAnimationFrame(() => window.scrollTo({ top: 0 }));
  };
  if (sent) return <div className="brand-page completion-workspace"><CompletionHead back="/brand/team" title="Invitation sent" copy="The invite is ready for the recipient." /><section className="invite-success" role="status" aria-live="polite"><div className="invite-success__seal"><i /><span><ProductIcon name="check" /></span></div><Status tone="lime">Sent successfully</Status><h2>{sent.email}</h2><p>They can join Gbedu Records as a <strong>{sent.role}</strong>.</p><div className="invite-success__details"><span><ProductIcon name="brief" /><b>{sent.role}</b></span><span><ProductIcon name="clock" /><b>Invite pending</b></span></div><div className="invite-success__actions"><button type="button" onClick={() => { setEmail(""); setSent(null); }}>Invite another person<ProductIcon name="users" /></button><BigAction href="/brand/team">Back to team</BigAction></div></section></div>;
  return <div className="brand-page completion-workspace"><CompletionHead back="/brand/team" title="Invite a team member" copy="Choose access based on the work this person handles." /><form className="invite-layout" onSubmit={submit}><section><label><span>Work email</span><input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" /></label><fieldset><legend>Role</legend>{Object.keys(roles).map((item) => <label className={role === item ? "is-selected" : ""} key={item}><input type="radio" checked={role === item} onChange={() => setRole(item)} /><span><strong>{item}</strong><small>{item === "Campaign manager" ? "Runs campaigns from brief to closeout" : item === "Reviewer" ? "Decides whether creator work meets the brief" : "Handles funding, invoices and refunds"}</small></span><ProductIcon name="check" /></label>)}</fieldset><button className="completion-submit" type="submit" disabled={!email.trim()}>Send invitation<ProductIcon name="arrow" /></button></section><aside><span><ProductIcon name="users" /></span><h2>{role}</h2><p>This role can:</p>{roles[role as keyof typeof roles].map((item) => <div key={item}><ProductIcon name="check" />{item}</div>)}<small>You can change or remove this access later.</small></aside></form></div>;
}

const invoices = [
  { id: "INV-0926-041", date: "20 Sep 2026", label: "Clippit campaign fee (15%) · No long thing", amount: "₦75,000", status: "Paid" },
  { id: "INV-0926-033", date: "14 Sep 2026", label: "Clippit campaign fee (15%) · Campus chop stories", amount: "₦52,500", status: "Paid" },
  { id: "CN-0926-008", date: "12 Sep 2026", label: "Campaign credit note", amount: "−₦4,200", status: "Applied" },
];

type BillingDetails = { legalName: string; registration: string; address: string; email: string };
const DEFAULT_BILLING_DETAILS: BillingDetails = {
  legalName: "Gbedu Records Limited",
  registration: "RC 1829041",
  address: "Lagos, Nigeria",
  email: "finance@gbedurecords.com",
};

export function BrandBillingScreen() {
  const [details, setDetails] = useState<BillingDetails>(DEFAULT_BILLING_DETAILS);
  const [draft, setDraft] = useState<BillingDetails>(DEFAULT_BILLING_DETAILS);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const openEditor = () => { setDraft(details); setSaved(false); setEditing(true); };
  const saveDetails = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDetails(draft);
    setEditing(false);
    setSaved(true);
    try { window.localStorage.setItem("clippit:brand-billing-details", JSON.stringify(draft)); } catch {}
  };
  return <div className="brand-page completion-workspace billing-page">
    <CompletionHead title="Billing and invoices" copy={`${details.legalName} · Nigerian naira`} />
    {saved && <div className="billing-saved" role="status" aria-live="polite"><ProductIcon name="check" /><span><strong>Billing details updated</strong><small>New invoices will use these details.</small></span></div>}
    <section className="billing-identity">
      <div><span><ProductIcon name="building" /></span><p><small>Billing identity</small><strong>{details.legalName}</strong><em>{details.registration} · {details.address}</em><em>{details.email}</em></p></div>
      <Status tone="lime">Verified</Status>
      <button type="button" onClick={openEditor}>Edit billing details</button>
    </section>
    {editing && <form className="billing-editor" onSubmit={saveDetails}>
      <header><div><small>Billing identity</small><h2>Edit billing details</h2></div><button type="button" onClick={() => setEditing(false)} aria-label="Close billing editor"><ProductIcon name="more" /></button></header>
      <div className="billing-editor__grid">
        <label><span>Legal business name</span><input required value={draft.legalName} onChange={(event) => setDraft({ ...draft, legalName: event.target.value })} /></label>
        <label><span>Registration number</span><input required value={draft.registration} onChange={(event) => setDraft({ ...draft, registration: event.target.value })} /></label>
        <label><span>Billing address</span><input required value={draft.address} onChange={(event) => setDraft({ ...draft, address: event.target.value })} /></label>
        <label><span>Billing email</span><input required type="email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} /></label>
      </div>
      <footer><button type="button" onClick={() => setEditing(false)}>Cancel</button><button className="completion-submit" type="submit">Save changes<ProductIcon name="check" /></button></footer>
    </form>}
    <section className="invoice-stack"><header><div><h2>Invoices and credit notes</h2><p>Official documents issued for campaign charges.</p></div><button onClick={() => window.print()}>Download statement<ProductIcon name="brief" /></button></header>{invoices.map((invoice) => <Link href={`/brand/invoices/${invoice.id}`} key={invoice.id}><span><ProductIcon name="brief" /></span><p><small>{invoice.id} · {invoice.date}</small><strong>{invoice.label}</strong></p><b>{invoice.amount}</b><Status tone={invoice.status === "Paid" ? "lime" : "gold"}>{invoice.status}</Status><ProductIcon name="arrow" /></Link>)}</section>
  </div>;
}

export function BrandInvoiceScreen({ id }: { id: string }) {
  return <div className="brand-page completion-workspace"><CompletionHead back="/brand/billing" title="Invoice" action={<button className="statement-download" onClick={() => window.print()}>Download PDF<ProductIcon name="brief" /></button>} /><article className="official-invoice"><header><div><Image src="/assets/clippit-mark.png" width={58} height={58} alt="" /><span><strong>Clippit</strong><small>Official tax invoice</small></span></div><p><small>Invoice number</small><strong>{id}</strong><span>Issued 20 Sep 2026</span></p></header><section className="invoice-parties"><div><small>Billed to</small><strong>Gbedu Records Limited</strong><span>RC 1829041</span><span>14 Admiralty Way, Lekki, Lagos</span><span>finance@gbedurecords.com</span></div><div><small>Issued by</small><strong>Clippit Technologies Limited</strong><span>Lagos, Nigeria</span><span>billing@clippit.ng</span></div></section><table><thead><tr><th>Description</th><th>Reference</th><th>Amount</th></tr></thead><tbody><tr><td>Clippit campaign fee<br /><small>15% of ₦500,000 creator pot · No long thing</small></td><td>CLP-0926-041</td><td>₦75,000</td></tr></tbody><tfoot><tr><td colSpan={2}>Subtotal</td><td>₦75,000</td></tr><tr><td colSpan={2}>Tax</td><td>₦0</td></tr><tr><td colSpan={2}>Total paid</td><td>₦75,000</td></tr></tfoot></table><footer><span><ProductIcon name="check" /></span><p><strong>Paid in full</strong><small>Payment reference PAY-9091841 · 20 Sep 2026</small></p><i>CLIPPIT · {id} · CLIPPIT · {id}</i></footer></article></div>;
}

export function CampaignRefundScreen({ slug }: { slug: string }) {
  const [requested, setRequested] = useState(false);
  if (requested) return <div className="brand-page completion-workspace"><section className="completion-result completion-result--workspace"><MiniArt src={art.bank} tone="gold" /><Status tone="lime">Refund requested</Status><h1>₦42,800 is being returned.</h1><p>Destination: Wema Bank account ending 0193. We will notify the team when the provider confirms delivery.</p><BigAction href="/brand/transactions">Track in transactions</BigAction></section></div>;
  return <div className="brand-page completion-workspace"><CompletionHead back={`/brand/campaigns/${slug}/report`} title="Unused campaign balance" copy="Campus chop stories closed on 16 September 2026." /><section className="refund-sheet"><div className="refund-tally"><small>Eligible refund</small><strong><AnimatedNumber value={42800} format="money" /></strong><span>of ₦350,000 creator pot</span><div><i style={{ width: "87.77%" }} /><b /></div><p><span>Earned by creators</span><b>₦307,200</b></p><p><span>Unused creator pot</span><b>₦42,800</b></p></div><aside><h2>Return destination</h2><div><ProductIcon name="bank" /><p><strong>Gbedu Records Limited</strong><span>Wema Bank · •••• 0193</span></p><Status tone="lime">Verified</Status></div><dl><div><dt>Refund reference</dt><dd>REF-00812</dd></div><div><dt>Expected arrival</dt><dd>Within 5 working days</dd></div><div><dt>Campaign</dt><dd>Campus chop stories</dd></div></dl><label><input type="checkbox" />I confirm this refund destination.</label><button className="completion-submit" onClick={() => setRequested(true)}>Request ₦42,800 refund<ProductIcon name="arrow" /></button></aside></section></div>;
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
      { title: "Reconnect when a provider permission expires", body: "A platform can expire or revoke access. When that happens, the account shows Reconnect required and view checks pause until the creator completes the provider flow again." },
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

type CustomerTicket = { id: string; category: string; subject: string; message: string; reference: string; createdAt: string; replies: string[] };
type CustomerDispute = { id: string; kind: string; reference: string; claim: string; createdAt: string };
const SUPPORT_STORE = "clippit:customer-support-tickets";
const DISPUTE_STORE = "clippit:customer-disputes";

function readStored<T>(key: string): T[] {
  try { return JSON.parse(window.localStorage.getItem(key) || "[]") as T[]; } catch { return []; }
}

export function ProductionSupportTicketsScreen() {
  const [tickets, setTickets] = useState<CustomerTicket[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => { const frame = window.requestAnimationFrame(() => { setTickets(readStored<CustomerTicket>(SUPPORT_STORE)); setReady(true); }); return () => window.cancelAnimationFrame(frame); }, []);
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Support tickets" copy="Questions and replies attached to your account." action={<BigAction href="/support/tickets/new">New ticket</BigAction>} />{ready && tickets.length === 0 ? <section className="real-empty-panel"><MiniArt src={art.review} tone="gold" /><div><Status tone="lime">No open tickets</Status><h2>You have not contacted support yet.</h2><p>Search the help centre first. If the answer is not there, send the issue with its campaign, payout or transaction reference.</p><div><BigAction href="/help" tone="gold">Search help</BigAction><BigAction href="/support/tickets/new">Contact support</BigAction></div></div></section> : <div className="ticket-board ticket-board--real"><aside><strong>{String(tickets.length).padStart(2, "0")}</strong><span>Your tickets</span><b>{tickets.length ? "Saved on this device" : "Loading"}</b><MiniArt src={art.review} tone="gold" /></aside><section>{tickets.map((ticket) => <Link href={`/support/tickets/${ticket.id}`} key={ticket.id} className="ticket-row"><span><ProductIcon name="brief" /></span><p><small>{ticket.id} · {ticket.category}</small><strong>{ticket.subject}</strong><em>{new Date(ticket.createdAt).toLocaleString("en-NG", { dateStyle: "medium", timeStyle: "short" })}</em></p><Status tone="gold">Awaiting support</Status><ProductIcon name="arrow" /></Link>)}</section></div>}</section></ServiceFrame>;
}

export function ProductionNewSupportTicketScreen() {
  const router = useRouter();
  const [category, setCategory] = useState("Campaigns");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reference, setReference] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const ticket: CustomerTicket = { id: `CLP-${Date.now().toString().slice(-6)}`, category, subject: subject.trim(), message: message.trim(), reference: reference.trim(), createdAt: new Date().toISOString(), replies: [] };
    window.localStorage.setItem(SUPPORT_STORE, JSON.stringify([ticket, ...readStored<CustomerTicket>(SUPPORT_STORE)]));
    router.push(`/support/tickets/${ticket.id}`);
  };
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" title="Contact support" copy="Send the exact issue and attach the relevant Clippit reference." /><form className="completion-form support-form" onSubmit={submit}><div className="form-main"><fieldset><legend>What is this about?</legend><div className="choice-grid choice-grid--compact">{["Campaigns", "Money", "Connected accounts", "Account access"].map((item) => <label className={category === item ? "is-selected" : ""} key={item}><input type="radio" checked={category === item} onChange={() => setCategory(item)} /><ProductIcon name={item === "Money" ? "wallet" : item === "Campaigns" ? "campaigns" : item === "Connected accounts" ? "link" : "shield"} /><span>{item}</span></label>)}</div></fieldset><label><span>Subject</span><input required minLength={5} value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="A short description of the problem" /></label><label><span>What happened?</span><textarea required minLength={20} rows={7} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What did you expect, what happened and when?" /></label><label><span>Related Clippit reference <small>Optional</small></span><input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Campaign, submission, payout or transaction ID" /></label></div><aside className="form-aside"><div><ProductIcon name="upload" /><strong>Add evidence</strong><span>PNG, JPG or PDF · up to 10 MB each</span><input type="file" multiple /></div><p><ProductIcon name="shield" />Never upload a password, one-time code or full card number.</p><button className="completion-submit" type="submit" disabled={subject.trim().length < 5 || message.trim().length < 20}>Send to support<ProductIcon name="arrow" /></button></aside></form></section></ServiceFrame>;
}

export function ProductionSupportTicketDetailScreen({ id }: { id: string }) {
  const [ticket, setTicket] = useState<CustomerTicket | null>(null);
  const [ready, setReady] = useState(false);
  const [reply, setReply] = useState("");
  useEffect(() => { const frame = window.requestAnimationFrame(() => { setTicket(readStored<CustomerTicket>(SUPPORT_STORE).find((item) => item.id === id) ?? null); setReady(true); }); return () => window.cancelAnimationFrame(frame); }, [id]);
  const addReply = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!ticket || !reply.trim()) return; const next = { ...ticket, replies: [...ticket.replies, reply.trim()] }; const all = readStored<CustomerTicket>(SUPPORT_STORE).map((item) => item.id === id ? next : item); window.localStorage.setItem(SUPPORT_STORE, JSON.stringify(all)); setTicket(next); setReply(""); };
  if (ready && !ticket) return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" title="Ticket not found" copy={`No support ticket named ${id} belongs to this browser session.`} /><section className="real-empty-panel real-empty-panel--compact"><MiniArt src={art.review} tone="gold" /><div><h2>Open your ticket list or start a new request.</h2><p>Signed-in production accounts will load their support history from the support service.</p><div><BigAction href="/support/tickets" tone="gold">Ticket list</BigAction><BigAction href="/support/tickets/new">New ticket</BigAction></div></div></section></section></ServiceFrame>;
  if (!ticket) return null;
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/support/tickets" kicker={ticket.id} title={ticket.subject} action={<Status tone="gold">Awaiting support</Status>} /><div className="thread-layout"><section className="message-thread"><div className="thread-day">{new Date(ticket.createdAt).toLocaleDateString("en-NG", { dateStyle: "long" })}</div><article className="is-customer"><span>YOU</span><div><header><strong>You</strong><time>{new Date(ticket.createdAt).toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}</time></header><p>{ticket.message}</p></div></article>{ticket.replies.map((message, index) => <article className="is-customer" key={`${message}-${index}`}><span>YOU</span><div><header><strong>You</strong><time>Saved</time></header><p>{message}</p></div></article>)}<form onSubmit={addReply}><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Add more information" rows={4} /><div><span /><button type="submit" disabled={!reply.trim()}>Add message<ProductIcon name="arrow" /></button></div></form></section><aside className="case-facts"><h2>Ticket details</h2><dl><div><dt>Status</dt><dd>Awaiting support</dd></div><div><dt>Category</dt><dd>{ticket.category}</dd></div><div><dt>Reference</dt><dd>{ticket.reference || "Not supplied"}</dd></div><div><dt>Created</dt><dd>{new Date(ticket.createdAt).toLocaleDateString("en-NG", { dateStyle: "medium" })}</dd></div></dl></aside></div></section></ServiceFrame>;
}

export function ProductionDisputesScreen() {
  const [cases, setCases] = useState<CustomerDispute[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => { const frame = window.requestAnimationFrame(() => { setCases(readStored<CustomerDispute>(DISPUTE_STORE)); setReady(true); }); return () => window.cancelAnimationFrame(frame); }, []);
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead title="Disputes" copy="Formal reviews of eligible decisions and money records." action={<BigAction href="/disputes/new">Open a dispute</BigAction>} />{ready && cases.length === 0 ? <section className="real-empty-panel"><MiniArt src={art.proof} /><div><Status tone="lime">No disputes</Status><h2>There are no formal cases on this device.</h2><p>Use support for ordinary questions. Open a dispute only when you need a formal review of an eligible verdict, earning, payout, funding order, refund or transaction.</p><div><BigAction href="/support/tickets/new" tone="gold">Ask support</BigAction><BigAction href="/disputes/new">Open a dispute</BigAction></div></div></section> : <div className="dispute-ledger"><header><span>Case</span><span>Type</span><span>Status</span><span>Created</span></header>{cases.map((item) => <Link href={`/disputes/${item.id}`} key={item.id}><p><small>{item.id}</small><strong>{item.reference}</strong></p><b>{item.kind}</b><Status tone="gold">Submitted</Status><time>{new Date(item.createdAt).toLocaleDateString("en-NG", { dateStyle: "medium" })}</time><ProductIcon name="arrow" /></Link>)}</div>}</section></ServiceFrame>;
}

export function ProductionNewDisputeScreen() {
  const router = useRouter();
  const [kind, setKind] = useState("Earning");
  const [reference, setReference] = useState("");
  const [claim, setClaim] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const item: CustomerDispute = { id: `DSP-${Date.now().toString().slice(-6)}`, kind, reference: reference.trim(), claim: claim.trim(), createdAt: new Date().toISOString() }; window.localStorage.setItem(DISPUTE_STORE, JSON.stringify([item, ...readStored<CustomerDispute>(DISPUTE_STORE)])); router.push(`/disputes/${item.id}`); };
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" title="Open a dispute" copy="Use the exact Clippit reference so the original record stays attached." /><form className="completion-form" onSubmit={submit}><div className="form-main"><fieldset><legend>What should be reviewed?</legend><div className="choice-grid">{["Earning", "Payout", "Submission verdict", "Campaign funding"].map((item) => <label className={kind === item ? "is-selected" : ""} key={item}><input type="radio" checked={kind === item} onChange={() => setKind(item)} /><ProductIcon name={item === "Earning" || item === "Payout" ? "wallet" : item === "Submission verdict" ? "play" : "campaigns"} /><span>{item}</span></label>)}</div></fieldset><label><span>Clippit reference</span><input required value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Earning, payout, submission or funding reference" /></label><label><span>What decision is incorrect?</span><textarea required minLength={30} rows={7} value={claim} onChange={(event) => setClaim(event.target.value)} placeholder="Explain the record, the issue and the outcome you are requesting." /></label></div><aside className="form-aside"><div><ProductIcon name="upload" /><strong>Add evidence</strong><span>Original platform insights, receipts or documents</span><input type="file" multiple /></div><p><ProductIcon name="shield" />Submitting a dispute preserves the original decision and evidence.</p><button className="completion-submit" type="submit" disabled={!reference.trim() || claim.trim().length < 30}>Submit dispute<ProductIcon name="arrow" /></button></aside></form></section></ServiceFrame>;
}

export function ProductionDisputeDetailScreen({ id }: { id: string }) {
  const [item, setItem] = useState<CustomerDispute | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { const frame = window.requestAnimationFrame(() => { setItem(readStored<CustomerDispute>(DISPUTE_STORE).find((entry) => entry.id === id) ?? null); setReady(true); }); return () => window.cancelAnimationFrame(frame); }, [id]);
  if (ready && !item) return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" title="Dispute not found" copy={`No dispute named ${id} belongs to this browser session.`} /><section className="real-empty-panel real-empty-panel--compact"><MiniArt src={art.proof} /><div><h2>Open the dispute list to find an existing case.</h2><p>A production account loads owned cases from the dispute service and never exposes another customer's record.</p><BigAction href="/disputes">Open disputes</BigAction></div></section></section></ServiceFrame>;
  if (!item) return null;
  return <ServiceFrame active="Support"><section className="service-content completion-page"><CompletionHead back="/disputes" kicker={item.id} title={item.reference} action={<Status tone="gold">Submitted</Status>} /><div className="dispute-case"><section className="case-timeline"><article className="is-current"><span><ProductIcon name="brief" /></span><div><small>{new Date(item.createdAt).toLocaleString("en-NG", { dateStyle: "medium", timeStyle: "short" })}</small><h2>Dispute received</h2><p>{item.claim}</p></div></article><article><span><ProductIcon name="eye" /></span><div><small>Next</small><h2>Eligibility and evidence review</h2><p>Clippit will verify that the case is within the applicable review window and attach the original record.</p></div></article><article><span><ProductIcon name="check" /></span><div><small>After review</small><h2>Written decision</h2><p>The case will retain its decision, reasons and any approved money or verdict action.</p></div></article></section><aside className="decision-clock"><span>Case type</span><strong className="decision-clock__word">{item.kind}</strong><small>No deadline has been assigned yet</small><dl><div><dt>Reference</dt><dd>{item.reference}</dd></div><div><dt>Status</dt><dd>Submitted</dd></div><div><dt>Evidence</dt><dd>Original record requested</dd></div></dl></aside></div></section></ServiceFrame>;
}

type LegalSection = { title: string; paragraphs: string[]; points?: string[] };
type LegalDocument = { slug: string; title: string; summary: string; version: string; date: string; sections: LegalSection[] };

const productionLegalDocs: LegalDocument[] = [
  { slug: "terms", title: "Terms of use", summary: "The agreement for creator, funder and brand accounts on Clippit.", version: "1.0", date: "Effective 22 September 2026", sections: [
    { title: "Agreement and eligibility", paragraphs: ["These Terms govern access to Clippit's website, creator workspace, brand workspace, campaign marketplace, verification and money features. By creating an account or using a funded campaign, you agree to these Terms and any campaign-specific terms shown before you act.", "You must be at least 18 years old or the age of legal capacity where you live, use accurate information and be legally able to enter this agreement. The current service is intended for users and transactions supported in Nigeria."] },
    { title: "Accounts, roles and verification", paragraphs: ["A person may use a creator account or fund content as an individual. An organisation account must be managed by someone authorised to act for it. Keep sign-in details secure and tell support promptly about unauthorised access.", "Clippit may require identity verification before withdrawals and business verification for organisation funding, billing, risk limits or other sensitive actions. Verification does not endorse a user's content, business or future performance."] },
    { title: "Campaigns and submissions", paragraphs: ["Brands are responsible for lawful, accurate briefs, sufficient rights to supplied assets and clear mandatory requirements. Creators are responsible for original, lawful posts submitted from their connected accounts. Joining a campaign does not guarantee approval or payment.", "The rules displayed on the funded campaign govern platform, content requirements, exclusions, rate, minimum views, creator cap, pot and any closing date. Material payout rules cannot be changed for live participation without preserving the version accepted by affected users."] },
    { title: "Verified views and earnings", paragraphs: ["Only views read from an eligible connected platform account count. A clip must be approved and reach the campaign minimum. Earnings use complete groups of 1,000 billable views and remain subject to creator caps and the remaining funded pot.", "New creator earnings are held for five days before becoming payable. A documented fraud, platform, dispute or compliance hold may delay release. The earning record must show the reason and available next step."] },
    { title: "Funding, fees, payouts and refunds", paragraphs: ["A brand pays a Clippit campaign fee equal to 15% of the creator pot for each campaign. Before funding, Clippit shows the creator pot, campaign fee, applicable tax and total. Creator allocations cannot exceed the creator pot.", "A creator pays a Clippit fee equal to 7% of each withdrawal. The withdrawal confirmation shows the requested amount, fee and amount sent to the verified bank destination. Refund eligibility depends on campaign closeout, settled creator allocations and any open dispute."] },
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
    { title: "Funding order", paragraphs: ["Each brand campaign carries a Clippit campaign fee equal to 15% of its creator pot. Before payment, the funding quote identifies the campaign, creator pot, campaign fee, applicable tax, total, currency, payment method, expiry and terms version. The campaign opens only after funds clear and the required checks pass."] },
    { title: "Pot, rate and limits", paragraphs: ["The pot is the maximum campaign money available for creator allocations. The rate applies to complete groups of 1,000 verified, billable views after the minimum threshold. A creator cap and the remaining pot are hard limits."] },
    { title: "Campaign duration", paragraphs: ["A brand can set a closing date or choose no fixed duration. A campaign without a closing date remains open only while it is otherwise eligible and has available pot; it does not receive an automatic hidden deadline."] },
    { title: "Submission decisions", paragraphs: ["Only approved submissions can earn. A rejection or correction request must identify the failed requirement. Review decisions and appeals preserve the original evidence and cannot silently rewrite past versions."] },
    { title: "Allocations and five-day hold", paragraphs: ["Billable views reserve creator earnings against the pot. Newly accrued earnings remain on hold for five days before becoming payable, subject to a documented fraud, platform, legal or dispute hold."] },
    { title: "Closeout and refund", paragraphs: ["At closeout, Clippit records the creator pot, campaign fee, creator earnings, unsettled allocations, verified views and unused creator-pot balance separately. Only the eligible reconciled unused creator-pot balance is refundable. The refund returns through an approved destination and receives a separate reference."] },
    { title: "Cancellations and payment disputes", paragraphs: ["A funded campaign cannot be deleted as if it never existed. Cancellation follows the closeout and refund process. A chargeback or provider dispute may pause opening, allocations or refunds while the payment record is reconciled."] },
    { title: "Records and questions", paragraphs: ["The campaign activity log, transaction ledger, receipts and closeout report are the source records for campaign money. Contact support for an explanation or use the dispute flow for an eligible formal review."] },
  ] },
];

export function ProductionLegalCentreScreen() {
  return <ServiceFrame active="Legal"><section className="legal-hero"><div><Status tone="gold">Current product documents</Status><h1>Legal centre</h1><p>Clippit's account, privacy, community and campaign-funding rules.</p></div><div className="legal-stamp"><ProductIcon name="shield" /><strong>1.0</strong><span>current document set</span></div></section><section className="service-content legal-list">{productionLegalDocs.map((doc, index) => <Link href={`/legal/${doc.slug}`} key={doc.slug}><span>{String(index + 1).padStart(2, "0")}</span><p><strong>{doc.title}</strong><small>{doc.summary}</small></p><time>{doc.date}</time><ProductIcon name="arrow" /></Link>)}</section></ServiceFrame>;
}

export function ProductionLegalDocumentScreen({ slug }: { slug: string }) {
  const doc = productionLegalDocs.find((item) => item.slug === slug) ?? productionLegalDocs[0];
  return <ServiceFrame active="Legal"><article className="legal-document"><CompletionHead back="/legal" kicker={`Version ${doc.version}`} title={doc.title} copy={doc.date} /><div className="legal-document__body"><aside><strong>Contents</strong>{doc.sections.map((section, index) => <a href={`#legal-${index + 1}`} key={section.title}>{index + 1}. {section.title}</a>)}<button onClick={() => window.print()}>Print document<ProductIcon name="brief" /></button></aside><div>{doc.sections.map((section, index) => <section id={`legal-${index + 1}`} key={section.title}><h2>{index + 1}. {section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}{section.points && <ul>{section.points.map((point) => <li key={point}>{point}</li>)}</ul>}</section>)}<section className="legal-authorities"><h2>Official resources</h2><p>Privacy rights: <a href="https://ndpc.gov.ng/" target="_blank" rel="noreferrer">Nigeria Data Protection Commission</a>. Consumer rights: <a href="https://fccpc.gov.ng/consumers/" target="_blank" rel="noreferrer">Federal Competition and Consumer Protection Commission</a>.</p><p>For a question about your Clippit account, use the in-product support centre.</p><BigAction href="/support/tickets/new" tone="ink">Contact support</BigAction></section></div></div></article></ServiceFrame>;
}

export function ProductionConsentUpdateScreen() {
  return <ServiceFrame active="Legal"><section className="consent-screen consent-screen--current"><div className="consent-sheet"><Status tone="lime">No action required</Status><h1>Your legal documents are current.</h1><p>There is no new document waiting for acceptance on this browser session.</p><ol>{productionLegalDocs.map((doc) => <li key={doc.slug}><span><ProductIcon name="check" /></span><div><strong>{doc.title}</strong><p>Version {doc.version} · {doc.date}</p></div></li>)}</ol><BigAction href="/legal">Open legal centre</BigAction></div><MiniArt src={art.proof} /></section></ServiceFrame>;
}

const reviewRoutes = [
  ["Support", "/help", "Help centre"], ["Support", "/help/how-campaigns-work", "Help article"], ["Support", "/support/tickets", "Support tickets"], ["Support", "/support/tickets/new", "New support ticket"], ["Support", "/support/tickets/CLP-2841", "Support conversation"], ["Support", "/disputes", "Disputes"], ["Support", "/disputes/new", "Open dispute"], ["Support", "/disputes/DSP-0419", "Dispute case"],
  ["Privacy and legal", "/account/data", "Your data"], ["Privacy and legal", "/account/delete", "Delete account"], ["Privacy and legal", "/legal", "Legal centre"], ["Privacy and legal", "/legal/privacy", "Legal document"], ["Privacy and legal", "/consent/update", "Updated terms"], ["Privacy and legal", "/verify/VIEW-21904", "Receipt verification"],
  ["Creator", "/dashboard/verification", "Creator verification"], ["Creator", "/dashboard/verification/identity", "Identity details"], ["Creator", "/dashboard/verification/documents", "Identity document"], ["Creator", "/dashboard/verification/status", "Verification status"], ["Creator", "/dashboard/earnings/statement", "Earnings statement"], ["Creator", "/creators/tobioncam", "Public creator profile"],
  ["Brand", "/brand/verification", "Business verification"], ["Brand", "/brand/verification/business", "Business details"], ["Brand", "/brand/verification/documents", "Business documents"], ["Brand", "/brand/verification/status", "Business status"], ["Brand", "/brand/team", "Team members"], ["Brand", "/brand/team/invite", "Invite member"], ["Brand", "/brand/billing", "Billing"], ["Brand", "/brand/invoices/INV-0926-041", "Invoice"], ["Brand", "/brand/campaigns/campus-chop/refund", "Campaign refund"],
] as const;

export function CustomerScreenReviewIndex() {
  const groups = ["Support", "Privacy and legal", "Creator", "Brand"] as const;
  return <ServiceFrame><section className="review-index"><CompletionHead kicker="Development review" title="29 customer screens" copy="Open every completed screen from one place. The number and order match the production screen inventory." action={<Status tone="lime">29 / 29 built</Status>} />{groups.map((group) => <section key={group}><header><h2>{group}</h2><span>{reviewRoutes.filter((route) => route[0] === group).length} screens</span></header><div>{reviewRoutes.filter((route) => route[0] === group).map((route, index) => <Link href={route[1]} key={route[1]}><i>{String(index + 1).padStart(2, "0")}</i><p><strong>{route[2]}</strong><small>{route[1]}</small></p><ProductIcon name="arrow" /></Link>)}</div></section>)}</section></ServiceFrame>;
}
