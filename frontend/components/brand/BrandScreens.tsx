"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfileAvatar, ProfilePhotoPicker, saveStoredProfile, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import { brandCampaigns, brandReviews, type BrandCampaign, type BrandCampaignState, type BrandReview } from "@/lib/brand";
import { brandApi, type BrandOverviewOut, type ReviewCard as ApiReviewCard } from "@/lib/api/brand";
import { campaignsApi, type CampaignOut } from "@/lib/api/campaigns";
import { BRAND_CAMPAIGN_FEE_RATE, calculateFee, feePercentage } from "@/lib/fees";
import { useBrandCampaign, type BriefRule } from "./BrandCampaignProvider";
import { CampaignCoverPicker } from "./CampaignCoverPicker";

const art = {
  brief: "/assets/illustrations/clippit-icons/campaign-brief.webp",
  funding: "/assets/illustrations/clippit-icons/funding-pot.webp",
  proof: "/assets/illustrations/clippit-icons/verified-proof.webp",
  review: "/assets/illustrations/clippit-icons/appeal-review.webp",
  social: "/assets/illustrations/clippit-icons/social-connect.webp",
  payout: "/assets/illustrations/clippit-icons/payout-wallet.webp",
  bank: "/assets/illustrations/clippit-icons/withdraw-bank.webp",
};

const BRAND_PROFILE_FALLBACK: StoredProfile = {
  name: "Gbedu Records",
  bio: "Independent Lagos music label.",
  photo: "",
};

function Money({ value, compact = false, delay = 0 }: { value: number; compact?: boolean; delay?: number }) {
  return <AnimatedNumber value={value} format={compact ? "compact" : "money"} delay={delay} />;
}

function BrandArt({ src, label, tone = "gold", compact = false }: { src: string; label: string; tone?: "gold" | "lime" | "paper" | "ink"; compact?: boolean }) {
  return <div className={`brand-art brand-art--${tone}${compact ? " brand-art--compact" : ""}`}><Image src={src} alt="" width={768} height={768} /><span>{label}</span></div>;
}

function Status({ children, tone = "lime" }: { children: ReactNode; tone?: "lime" | "gold" | "ink" | "danger" | "paper" }) {
  return <span className={`brand-status brand-status--${tone}`}><i className="brand-status__dot" />{children}</span>;
}

function PageHeading({ note, title, copy, action }: { note?: string; title: string; copy?: string; action?: ReactNode }) {
  return <header className="brand-page-heading"><div>{note ? <p>{note}</p> : null}<h1>{title}</h1>{copy ? <span>{copy}</span> : null}</div>{action}</header>;
}

function ActionLink({ href, children, dark = false }: { href: string; children: ReactNode; dark?: boolean }) {
  return <Link href={href} className={dark ? "brand-button brand-button--dark" : "brand-button"}>{children}<ProductIcon name="arrow" /></Link>;
}

const builderSteps = [
  { label: "Campaign", href: "/brand/campaigns/new" },
  { label: "Brief", href: "/brand/campaigns/new/brief" },
  { label: "Platforms", href: "/brand/campaigns/new/platforms" },
  { label: "Rules", href: "/brand/campaigns/new/rules" },
  { label: "Money", href: "/brand/campaigns/new/budget" },
  { label: "Review", href: "/brand/campaigns/new/review" },
];

function BuilderFrame({ step, title, copy, artSrc, artLabel, children, aside }: { step: number; title: string; copy: string; artSrc: string; artLabel: string; children: ReactNode; aside?: ReactNode }) {
  const { draft } = useBrandCampaign();
  return <div className="brand-builder-page">
    <header className="builder-progress"><div><span>Campaign studio</span><strong>{String(step + 1).padStart(2, "0")} / 06</strong></div><nav aria-label="Campaign creation progress">{builderSteps.map((item, index) => <Link href={item.href} key={item.href} className={index === step ? "is-current" : index < step ? "is-done" : ""}><i>{index < step ? <ProductIcon name="check" /> : index + 1}</i><span>{item.label}</span></Link>)}</nav></header>
    <div className="builder-layout"><section className="builder-work"><div className="builder-title"><h1>{title}</h1><span>{copy}</span></div>{children}</section><aside className="builder-preview">{draft.coverImage ? <div className="builder-cover-preview"><Image src={draft.coverImage} alt={`${draft.title || "Campaign"} cover`} fill unoptimized sizes="420px" /><span>Campaign cover</span></div> : <BrandArt src={artSrc} label={artLabel} />}<div className="builder-live-card"><small>Campaign preview</small><h2>{draft.title || "Untitled campaign"}</h2><p>{draft.description || "Your campaign description will appear here."}</p><div><span>{draft.platforms.length ? draft.platforms.join(" + ") : "Choose platforms"}</span><strong><Money value={draft.rate} /> / 1K</strong></div><em>{draft.endCondition === "budget" ? "Runs until the pot is empty" : `${draft.days} day duration`}</em></div>{aside}</aside></div>
  </div>;
}

function FormActions({ back, next, label = "Continue" }: { back: string; next?: string; label?: string }) {
  return <div className="builder-actions"><Link href={back}><ProductIcon name="chevron" />Back</Link>{next ? <ActionLink href={next}>{label}</ActionLink> : <button type="submit" className="brand-button">{label}<ProductIcon name="arrow" /></button>}</div>;
}

function PotBar({ campaign }: { campaign: BrandCampaign }) {
  const percentage = Math.round((campaign.remaining / campaign.pot) * 100);
  return <div className="brand-pot-bar"><div><span>Pot still available</span><strong><Money value={campaign.remaining} /></strong></div><div className="brand-pot-bar__track"><i style={{ width: `${percentage}%` }} /><b><ProductIcon name="shield" /></b></div><p><AnimatedNumber value={percentage} suffix="%" /> of <Money value={campaign.pot} /> remains</p></div>;
}

export function BrandOverviewScreen() {
  const [overview, setOverview] = useState<BrandOverviewOut | null>(null);
  const live = brandCampaigns[0];

  useEffect(() => {
    brandApi.overview().then((data) => setOverview(data)).catch(() => undefined);
  }, []);

  const pendingReviews = overview?.pending_reviews ?? live.review;
  const orgName = overview?.organisation_name ?? "Gbedu Records";
  const featuredImage = overview?.featured?.cover_image_url ?? live.image;
  const featuredTitle = overview?.featured?.title ?? live.title;
  const featuredLine = overview?.featured?.tagline ?? live.line;
  const featuredSlug = overview?.featured?.slug ?? "no-long-thing";
  const featuredPot: BrandCampaign = overview?.featured
    ? {
        ...live,
        title: overview.featured.title,
        line: overview.featured.tagline ?? live.line,
        image: overview.featured.cover_image_url ?? live.image,
        slug: overview.featured.slug,
        pot: overview.featured.pot,
        remaining: overview.featured.remaining,
        rate: overview.featured.payout_rule?.rate_per_1000_views ?? live.rate,
        verifiedViews: overview.featured.metrics?.verified_views ?? live.verifiedViews,
        approved: overview.featured.metrics?.approved ?? live.approved,
        review: overview.featured.metrics?.review ?? live.review,
        submissions: overview.featured.metrics?.submissions ?? live.submissions,
      }
    : live;

  return <div className="brand-page brand-overview-page">
    <section className="brand-command"><div className="brand-command__copy"><Status tone={pendingReviews ? "gold" : "lime"}>{pendingReviews ? `${pendingReviews} need review` : "Campaign live"}</Status><h1>{pendingReviews ? <>{pendingReviews} clips need<br />your review.</> : <>What are we posting today,<br />{orgName}?</>}</h1><p>{pendingReviews ? "These submissions are waiting for a decision before they can earn." : "Create a campaign or check the campaigns already running."}</p><div className="brand-command__actions"><ActionLink href={pendingReviews ? "/brand/reviews" : "/brand/campaigns/new"}>{pendingReviews ? "Review submissions" : "Create a campaign"}</ActionLink><ActionLink href="/brand/campaigns/new" dark>Create campaign</ActionLink></div></div><div className="brand-command__visual"><div className="brand-command__image"><Image src={featuredImage} alt="Creator from the featured campaign" fill sizes="(max-width: 900px) 100vw, 44vw" priority /></div><BrandArt src={art.funding} label="Campaign pot" tone="gold" compact /><span className="brand-command__stamp"><b><AnimatedNumber value={featuredPot.submissions} /></b> submissions</span></div></section>
    <section className="brand-live-board"><div className="brand-live-board__head"><div><Status tone="gold">Closing in 4 days</Status><h2>{featuredTitle}</h2><p>{featuredLine}</p></div><Link href={`/brand/campaigns/${featuredSlug}`}>View campaign<ProductIcon name="arrow" /></Link></div><div className="brand-live-board__grid"><PotBar campaign={featuredPot} /><article><small>Verified views</small><strong><AnimatedNumber value={overview?.featured?.metrics?.verified_views ?? live.verifiedViews} format="compact" /></strong><p>read from connected creator accounts</p><span className="signal-ripples"><i /><i /><i /></span></article><article><small>Approved clips</small><strong><AnimatedNumber value={overview?.featured?.metrics?.approved ?? live.approved} padStart={2} /></strong><p>clips currently earning</p><div className="creator-token-stack"><i>KM</i><i>TO</i><i>NA</i><i>+58</i></div></article><article className="review-callout"><BrandArt src={art.review} label="Review queue" tone="lime" compact /><div><small>Needs review</small><strong><AnimatedNumber value={pendingReviews} padStart={2} /></strong><p>These clips do not earn until you decide.</p><Link href="/brand/reviews">Review now<ProductIcon name="arrow" /></Link></div></article></div></section>
    <section className="brand-proof-ribbon"><div><ProductIcon name="eye" /><span><small>Views verified today</small><strong><AnimatedNumber value={overview?.views_last_24h ?? 72800} /></strong></span></div><i /><div><ProductIcon name="wallet" /><span><small>Creator earnings today</small><strong><Money value={overview?.earnings_last_24h ?? 36400} /></strong></span></div><i /><div><ProductIcon name="shield" /><span><small>Unmatched spend</small><strong><Money value={overview?.unmatched_spend ?? 0} /></strong></span></div></section>
  </div>;
}

function CampaignCard({ campaign }: { campaign: BrandCampaign }) {
  const href = campaign.state === "Draft" ? "/brand/campaigns/new" : campaign.state === "Completed" ? `/brand/campaigns/${campaign.slug}/report` : `/brand/campaigns/${campaign.slug}`;
  return <Link href={href} className={`brand-campaign-card brand-campaign-card--${campaign.state.toLowerCase()}`}><div className="brand-campaign-card__image"><Image src={campaign.image} alt="" fill sizes="(max-width: 700px) 100vw, 320px" /><Status tone={campaign.state === "Live" ? "lime" : campaign.state === "Draft" ? "gold" : "paper"}>{campaign.state}</Status></div><div className="brand-campaign-card__body"><div><small>Gbedu Records</small><h2>{campaign.title}</h2><p>{campaign.line}</p></div><dl><div><dt>Rate</dt><dd><Money value={campaign.rate} /> / 1K</dd></div><div><dt>{campaign.state === "Completed" ? "Delivered" : "Pot left"}</dt><dd>{campaign.state === "Completed" ? <AnimatedNumber value={campaign.verifiedViews} format="compact" suffix=" views" /> : <Money value={campaign.remaining} />}</dd></div><div><dt>Clips</dt><dd><AnimatedNumber value={campaign.submissions} padStart={2} /></dd></div></dl><span>{campaign.state === "Completed" ? "Open closeout" : "Open campaign"}<ProductIcon name="arrow" /></span></div></Link>;
}

function campaignOutToBrand(c: CampaignOut): BrandCampaign {
  const phase = c.phase as BrandCampaignState;
  return {
    slug: c.slug,
    title: c.title,
    line: c.tagline ?? c.description.slice(0, 100),
    state: phase === "Funding" ? "Funding" : phase === "Draft" ? "Draft" : phase === "Completed" ? "Completed" : "Live",
    image: c.cover_image_url ?? "/assets/video/creator-reaction-poster.jpg",
    pot: c.pot,
    remaining: c.remaining,
    rate: c.payout_rule?.rate_per_1000_views ?? 0,
    verifiedViews: c.metrics?.verified_views ?? 0,
    submissions: c.metrics?.submissions ?? 0,
    approved: c.metrics?.approved ?? 0,
    review: c.metrics?.review ?? 0,
    daysLeft: c.time_left?.days ?? 0,
  };
}

export function BrandCampaignsScreen() {
  const [filter, setFilter] = useState<"All" | BrandCampaign["state"]>("All");
  const [allCampaigns, setAllCampaigns] = useState<BrandCampaign[]>(brandCampaigns);

  useEffect(() => {
    campaignsApi.list().then((data) => {
      if (data.items.length > 0) setAllCampaigns(data.items.map(campaignOutToBrand));
    }).catch(() => undefined);
  }, []);

  const visible = allCampaigns.filter((campaign) => filter === "All" || campaign.state === filter);
  return <div className="brand-page"><PageHeading title="Campaigns" copy="Create a campaign or open one that is already running." action={<ActionLink href="/brand/campaigns/new">Create campaign</ActionLink>} /><div className="brand-filter-row">{["All", "Live", "Draft", "Completed"].map((item) => <button type="button" key={item} className={filter === item ? "is-active" : ""} onClick={() => setFilter(item as typeof filter)}>{item}{item === "Live" && <i />}</button>)}</div><section className="brand-campaign-grid">{visible.map((campaign) => <CampaignCard campaign={campaign} key={campaign.slug} />)}</section></div>;
}

export function CampaignBasicsScreen() {
  const router = useRouter();
  const { draft, update } = useBrandCampaign();
  const submit = (event: FormEvent) => { event.preventDefault(); if (draft.title.trim() && draft.description.trim()) router.push("/brand/campaigns/new/brief"); };
  return <BuilderFrame step={0} title="Campaign details" copy="Add the image, title, description and source material creators will see." artSrc={art.brief} artLabel="Campaign details"><form className="brand-builder-form" onSubmit={submit}><CampaignCoverPicker value={draft.coverImage} title={draft.title} onChange={(coverImage) => update({ coverImage })} /><label><span>Campaign title</span><input value={draft.title} onChange={(event) => update({ title: event.target.value })} placeholder="The late-night bowl" maxLength={56} required /><small>{draft.title.length}/56</small></label><label><span>Campaign description</span><textarea value={draft.description} onChange={(event) => update({ description: event.target.value })} placeholder="Tell creators what the campaign is about" maxLength={180} required /><small>{draft.description.length}/180</small></label><label><span>Source material</span><div className="brand-input-with-icon"><ProductIcon name="link" /><input value={draft.sourceLink} onChange={(event) => update({ sourceLink: event.target.value })} placeholder="Paste a brand kit, sound or reference link" /></div><small>Optional. Creators see this beside the brief.</small></label><FormActions back="/brand/campaigns" label="Add requirements" /></form></BuilderFrame>;
}

export function CampaignBriefScreen() {
  const { draft, addRule, removeRule } = useBrandCampaign();
  const [text, setText] = useState("");
  const [kind, setKind] = useState<BriefRule["kind"]>("must");
  const add = () => { if (text.trim().length < 5) return; addRule(kind, text.trim()); setText(""); };
  return <BuilderFrame step={1} title="Campaign requirements" copy="Add one requirement per line. Each requirement should be easy to verify from the posted clip." artSrc={art.brief} artLabel="Requirements" aside={<p className="builder-margin-note">Only add requirements that can be checked from the public post.</p>}><div className="brief-composer"><div className="brief-add"><div className="brief-kind"><button type="button" className={kind === "must" ? "is-active" : ""} onClick={() => setKind("must")}><ProductIcon name="check" />Must do</button><button type="button" className={kind === "avoid" ? "is-active is-avoid" : ""} onClick={() => setKind("avoid")}><span>!</span>Must avoid</button></div><div className="brief-entry"><input value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); add(); } }} placeholder={kind === "must" ? "Show the prepared noodles clearly on screen" : "Do not make health or nutrition claims"} /><button type="button" onClick={add} aria-label="Add requirement"><ProductIcon name="arrow" /></button></div></div><ol className="brief-list">{draft.rules.map((rule, index) => <li key={rule.id} className={rule.kind === "avoid" ? "is-avoid" : ""}><span>{String(index + 1).padStart(2, "0")}</span><i>{rule.kind === "must" ? <ProductIcon name="check" /> : "!"}</i><p><small>{rule.kind === "must" ? "Must do" : "Must avoid"}</small><strong>{rule.text}</strong></p><button type="button" onClick={() => removeRule(rule.id)} aria-label={`Remove ${rule.text}`}>Remove</button></li>)}</ol><FormActions back="/brand/campaigns/new" next="/brand/campaigns/new/platforms" label="Choose platforms" /></div></BuilderFrame>;
}

const platformChoices: Array<{ name: string; icon: ProductIconName; note: string; signal: string }> = [
  { name: "TikTok", icon: "tiktok", note: "Short vertical video", signal: "View API ready" },
  { name: "Instagram", icon: "instagram", note: "Reels and visual content", signal: "View API ready" },
  { name: "YouTube", icon: "youtube", note: "Shorts and longer videos", signal: "View API ready" },
];

export function CampaignPlatformsScreen() {
  const { draft, togglePlatform } = useBrandCampaign();
  return <BuilderFrame step={2} title="Choose platforms" copy="Select where creators can publish for this campaign." artSrc={art.social} artLabel="Platforms"><div className="platform-picker">{platformChoices.map((platform) => { const selected = draft.platforms.includes(platform.name); return <button type="button" key={platform.name} onClick={() => togglePlatform(platform.name)} className={selected ? "is-selected" : ""}><span><ProductIcon name={platform.icon} /></span><p><strong>{platform.name}</strong><small>{platform.note}</small></p><i>{selected ? <ProductIcon name="check" /> : null}</i><b>{platform.signal}</b></button>; })}</div><div className="platform-proof"><ProductIcon name="shield" /><p><strong>Views come from connected accounts.</strong><small>Clippit reads approved posts directly from the creator account.</small></p></div><FormActions back="/brand/campaigns/new/brief" next="/brand/campaigns/new/rules" label="Set earning rules" /></BuilderFrame>;
}

export function CampaignRulesScreen() {
  const { draft, update } = useBrandCampaign();
  return <BuilderFrame step={3} title="Set earning rules" copy="Choose the minimum views, creator cap and when the campaign should close." artSrc={art.proof} artLabel="Earning rules"><div className="rules-console"><label><span><ProductIcon name="eye" />Minimum verified views</span><div><input type="number" min={1000} step={500} value={draft.minimumViews} onChange={(event) => update({ minimumViews: Number(event.target.value) })} /><b>views</b></div><small>A clip earns nothing before this point.</small></label><label><span><ProductIcon name="wallet" />Maximum per creator</span><div><b>₦</b><input type="number" min={10000} step={5000} value={draft.creatorCap} onChange={(event) => update({ creatorCap: Number(event.target.value) })} /></div><small>Across every approved clip in this campaign.</small></label></div><fieldset className="campaign-end-control"><legend>When should the campaign close?</legend><div><button type="button" className={draft.endCondition === "duration" ? "is-selected" : ""} onClick={() => update({ endCondition: "duration" })}><span><ProductIcon name="calendar" /></span><p><strong>After a fixed duration</strong><small>Set a deadline. The campaign can still end sooner if the pot empties.</small></p><i>{draft.endCondition === "duration" && <ProductIcon name="check" />}</i></button><button type="button" className={draft.endCondition === "budget" ? "is-selected" : ""} onClick={() => update({ endCondition: "budget" })}><span><ProductIcon name="wallet" /></span><p><strong>When the pot is empty</strong><small>No calendar deadline. The campaign runs while funded money remains.</small></p><i>{draft.endCondition === "budget" && <ProductIcon name="check" />}</i></button></div>{draft.endCondition === "duration" ? <label><span>Campaign duration</span><div><input type="number" min={1} max={90} value={draft.days} onChange={(event) => update({ days: Number(event.target.value) })} /><b>days</b></div><small>Choose between 1 and 90 days.</small></label> : <aside><ProductIcon name="shield" /><p><strong>No scheduled end date</strong><small>Clippit closes the campaign automatically when the remaining pot cannot fund another full earning unit.</small></p></aside>}</fieldset><div className="rule-contract"><span><AnimatedNumber value={5} suffix=" days" /></span><p><strong>Earnings are held for five days.</strong><small>This gives the fraud check time to catch bought views before withdrawal.</small></p></div><FormActions back="/brand/campaigns/new/platforms" next="/brand/campaigns/new/budget" label="Set budget" /></BuilderFrame>;
}

export function CampaignBudgetScreen() {
  const { draft, update } = useBrandCampaign();
  const views = draft.rate > 0 ? Math.floor((draft.pot / draft.rate) * 1000) : 0;
  const creators = draft.creatorCap > 0 ? Math.ceil(draft.pot / draft.creatorCap) : 0;
  const campaignFee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return <BuilderFrame step={4} title="Set the budget and rate" copy="Enter the creator pot and what you will pay per 1,000 verified views." artSrc={art.funding} artLabel="Campaign budget" aside={<div className="budget-side-note"><ProductIcon name="shield" /><span><strong>Funding required</strong><small>The full funding total is shown before payment.</small></span></div>}><div className="budget-console"><div className="budget-inputs"><label><span>Total creator pot</span><div><b>₦</b><input type="number" min={50000} step={50000} value={draft.pot} onChange={(event) => update({ pot: Number(event.target.value) })} /></div></label><label><span>Pay per 1,000 verified views</span><div><b>₦</b><input type="number" min={100} step={50} value={draft.rate} onChange={(event) => update({ rate: Number(event.target.value) })} /></div></label></div><div className="budget-equation"><div><small>Your pot</small><strong><Money value={draft.pot} /></strong></div><i>÷</i><div><small>Your rate</small><strong><Money value={draft.rate} /></strong></div><i>=</i><div className="is-answer"><small>Potential verified views</small><strong><AnimatedNumber value={views} format="compact" /></strong></div></div><div className="budget-guardrails budget-guardrails--fees"><div><span>Minimum creator spread</span><strong><AnimatedNumber value={creators} suffix=" creators" /></strong></div><div><span>Creator cap</span><strong><Money value={draft.creatorCap} /></strong></div><div><span>Clippit fee (15%)</span><strong><Money value={campaignFee} /></strong></div><div><span>Total to fund</span><strong><Money value={draft.pot + campaignFee} /></strong></div></div></div><FormActions back="/brand/campaigns/new/rules" next="/brand/campaigns/new/review" label="Review campaign" /></BuilderFrame>;
}

export function CampaignReviewScreen() {
  const { draft } = useBrandCampaign();
  const projectedViews = draft.rate ? Math.floor((draft.pot / draft.rate) * 1000) : 0;
  const campaignFee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return <BuilderFrame step={5} title="Review campaign" copy="Check the cover, brief, rules and full funding total." artSrc={art.proof} artLabel="Ready to fund"><div className="campaign-proof-sheet">{draft.coverImage && <div className="campaign-proof-cover"><Image src={draft.coverImage} alt={`${draft.title} campaign cover`} fill unoptimized sizes="(max-width: 700px) 100vw, 760px" /></div>}<header><Status tone="gold">Ready to fund</Status><span className="campaign-proof-brand">Gbedu Records</span><h2>{draft.title}</h2><p>{draft.description}</p><div>{draft.platforms.map((platform) => <i key={platform}>{platform}</i>)}</div></header><section className="campaign-proof-totals"><div><small>Live rate</small><strong><Money value={draft.rate} /></strong><span>per 1K verified views</span></div><div><small>Creator pot</small><strong><Money value={draft.pot} /></strong><span>up to <AnimatedNumber value={projectedViews} format="compact" /> views</span></div><div><small>Clippit fee</small><strong><Money value={campaignFee} /></strong><span>{feePercentage(BRAND_CAMPAIGN_FEE_RATE)}% of the creator pot</span></div><div><small>Total to fund</small><strong><Money value={draft.pot + campaignFee} /></strong><span>Creator pot plus Clippit fee</span></div></section><ol>{draft.rules.map((rule, index) => <li key={rule.id} className={rule.kind === "avoid" ? "is-avoid" : ""}><span>{String(index + 1).padStart(2, "0")}</span><ProductIcon name={rule.kind === "avoid" ? "shield" : "check"} /><p><small>{rule.kind === "avoid" ? "Must avoid" : "Must do"}</small><strong>{rule.text}</strong></p></li>)}</ol></div><FormActions back="/brand/campaigns/new/budget" next="/brand/campaigns/new/fund" label="Fund this campaign" /></BuilderFrame>;
}

export function CampaignFundingScreen() {
  const router = useRouter();
  const { draft } = useBrandCampaign();
  const [method, setMethod] = useState("bank");
  const [agreed, setAgreed] = useState(false);
  const fee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  const submit = (event: FormEvent) => { event.preventDefault(); if (agreed) router.push("/brand/campaigns/new/funded"); };
  return <div className="brand-page funding-page"><Link className="brand-back" href="/brand/campaigns/new/review"><ProductIcon name="chevron" />Back to campaign review</Link><PageHeading title="Fund the campaign" copy="Pay the creator pot and Clippit&apos;s 15% campaign fee. The rate and creator cap lock after funding." /><div className="funding-layout"><form className="funding-checkout" onSubmit={submit}><div className="funding-checkout__title"><BrandArt src={art.bank} label="Payment details" tone="gold" compact /><div><small>Campaign funding</small><h2>{draft.title}</h2><p>Gbedu Records</p></div></div><div className="funding-methods"><button type="button" className={method === "bank" ? "is-selected" : ""} onClick={() => setMethod("bank")}><ProductIcon name="bank" /><span><strong>Bank transfer</strong><small>Best for campaign funding</small></span><i>{method === "bank" && <ProductIcon name="check" />}</i></button><button type="button" className={method === "card" ? "is-selected" : ""} onClick={() => setMethod("card")}><ProductIcon name="wallet" /><span><strong>Business card</strong><small>Visa or Mastercard</small></span><i>{method === "card" && <ProductIcon name="check" />}</i></button></div>{method === "bank" ? <div className="funding-bank"><span><ProductIcon name="building" /></span><p><small>Payaza collection account</small><strong>CLIPPIT / GBEDU RECORDS</strong><b>012 884 0193</b><em>Wema Bank</em></p><button type="button">Copy details</button></div> : <div className="funding-card-fields"><label><span>Card number</span><input inputMode="numeric" placeholder="0000 0000 0000 0000" /></label><div><label><span>Expiry</span><input placeholder="MM / YY" /></label><label><span>CVV</span><input inputMode="numeric" placeholder="000" /></label></div></div>}<label className="funding-agreement"><input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} /><i><ProductIcon name="check" /></i><span>I approve the creator pot and the 15% Clippit campaign fee shown in this order.</span></label><button type="submit" className="brand-button" disabled={!agreed}>Confirm campaign funding<ProductIcon name="arrow" /></button></form><aside className="funding-receipt"><ReceiptHeader title="Campaign funding order" reference="CLP-0926-041" /><div className="funding-receipt__campaign"><span>{draft.coverImage ? <Image src={draft.coverImage} alt="" fill unoptimized sizes="76px" /> : <Image src={art.funding} alt="" fill sizes="76px" />}</span><p><small>Campaign</small><strong>{draft.title}</strong><em>Gbedu Records</em></p></div><div className="funding-receipt__parties"><section><h2>Recipient</h2><p><strong>Clippit Campaign Escrow</strong><span>Payaza · 019***9028</span></p></section><section><h2>Sender</h2><p><strong>Gbedu Records Ltd.</strong><span>Wema Bank · 012***0193</span></p></section></div><dl><div><dt>Funding ID</dt><dd>CLP-0926-041</dd></div><div><dt>Escrow reference</dt><dd>ESC-260920-041</dd></div><div><dt>Creator pot</dt><dd><Money value={draft.pot} /></dd></div><div><dt>Clippit campaign fee (15%)</dt><dd><Money value={fee} /></dd></div><div><dt>Campaign end</dt><dd>{draft.endCondition === "budget" ? "When the pot is empty" : `${draft.days} days or an empty pot`}</dd></div></dl><p className="funding-receipt__total"><span>Total to fund</span><strong><Money value={draft.pot + fee} /></strong></p><ul><li><ProductIcon name="shield" />Creator pot held in escrow</li><li><ProductIcon name="eye" />Only verified views draw from the pot</li><li><ProductIcon name="bank" />Unused creator-pot balance returns after closeout</li></ul></aside></div></div>;
}

export function CampaignFundedScreen() {
  const { draft } = useBrandCampaign();
  const fee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return <div className="brand-page funded-page"><section className="funded-hero"><div className="funded-art">{draft.coverImage ? <div className="funded-cover"><Image src={draft.coverImage} alt={`${draft.title} campaign cover`} fill unoptimized sizes="420px" /></div> : <BrandArt src={art.funding} label="Pot received" tone="lime" />}<span><ProductIcon name="check" /></span></div><Status>Funds confirmed</Status><h1>Campaign funded.</h1><p>{draft.title} is live. Creators can now join and submit clips.</p><div><ActionLink href="/brand/campaigns/no-long-thing">View campaign</ActionLink><ActionLink href="/brand/campaigns" dark>Back to campaigns</ActionLink></div></section><aside className="funded-ticket"><ReceiptHeader title="Campaign funding certificate" reference="CLP-LIVE-041" /><div className="funded-ticket__campaign"><span>{draft.coverImage ? <Image src={draft.coverImage} alt="" fill unoptimized sizes="84px" /> : <Image src={art.funding} alt="" fill sizes="84px" />}</span><p><small>Funded campaign</small><strong>{draft.title}</strong><em>Gbedu Records</em></p><i><ProductIcon name="check" />Live</i></div><div className="funded-ticket__amount"><small>Total paid</small><h2><Money value={draft.pot + fee} /></h2><time>20 Sep 2026 · 15:07:13 WAT</time></div><div className="funded-ticket__parties"><section><h2>Recipient</h2><p><strong>Clippit Campaign Escrow</strong><span>Payaza · 019***9028</span></p></section><section><h2>Sender</h2><p><strong>Gbedu Records Ltd.</strong><span>Wema Bank · 012***0193</span></p></section></div><section className="funded-ticket__information"><h2>Transaction information</h2><dl><div><dt>Funding transaction ID</dt><dd>CLP-LIVE-041</dd></div><div><dt>Session ID</dt><dd>100033260920115117010192295902</dd></div><div><dt>Creator pot</dt><dd><Money value={draft.pot} /></dd></div><div><dt>Clippit campaign fee (15%)</dt><dd><Money value={fee} /></dd></div><div><dt>Rate</dt><dd><Money value={draft.rate} /> / 1K views</dd></div><div><dt>Campaign end</dt><dd>{draft.endCondition === "budget" ? "When the pot is empty" : `${draft.days} days or an empty pot`}</dd></div></dl></section><footer><ProductIcon name="shield" /><span><strong>Verify this certificate</strong><small>clippit.ng/verify/CLP-LIVE-041 · Code C04A-7719</small></span></footer></aside></div>;
}

export function LiveCampaignScreen() {
  const campaign = brandCampaigns[0];
  const [paused, setPaused] = useState(false);
  return <div className="brand-page live-campaign-page"><header className="live-campaign-head"><div><Status>{paused ? "Paused" : "Live now"}</Status><p>Gbedu Records</p><h1>{campaign.title}</h1><span>{campaign.line}</span></div><div><button type="button" onClick={() => setPaused((value) => !value)}>{paused ? "Resume entries" : "Pause new entries"}</button><button type="button"><ProductIcon name="more" /></button></div></header><section className="live-money-room"><div className="live-money-room__visual"><Image src={campaign.image} alt="" fill sizes="(max-width: 900px) 100vw, 48vw" priority /><div><span>Live rate</span><strong><Money value={campaign.rate} /></strong><small>per 1K verified views</small></div></div><div className="live-money-room__pot"><BrandArt src={art.funding} label="Campaign pot" tone="gold" compact /><p>Money still in the pot</p><strong><Money value={campaign.remaining} /></strong><PotBar campaign={campaign} /><dl><div><dt>Started with</dt><dd><Money value={campaign.pot} /></dd></div><div><dt>Earned by creators</dt><dd><Money value={campaign.pot - campaign.remaining} /></dd></div><div><dt>Campaign closes</dt><dd><AnimatedNumber value={campaign.daysLeft} suffix="d 18h" /></dd></div></dl></div></section><section className="live-signal-grid"><article><small>Verified views</small><strong><AnimatedNumber value={campaign.verifiedViews} format="compact" /></strong><div className="brand-sparkline"><i /><i /><i /><i /><i /><i /><i /><i /></div><p><b>+72.8K</b> since yesterday</p></article><article><small>Submission flow</small><strong><AnimatedNumber value={campaign.submissions} /></strong><div className="submission-pipeline"><span><b>{campaign.approved}</b> earning</span><i /><span><b>{campaign.review}</b> need review</span><i /><span><b>16</b> checking</span></div><Link href="/brand/reviews">Open review queue<ProductIcon name="arrow" /></Link></article><article className="live-proof-card"><BrandArt src={art.proof} label="Views proven" tone="lime" compact /><p><small>Last platform reading</small><strong>2 minutes ago</strong><span>TikTok, Instagram and YouTube responded normally.</span></p></article></section><section className="brand-activity-sheet"><header><div><h2>Recent submissions</h2><p>Latest view and earning status for each submission.</p></div><button type="button">Export report<ProductIcon name="arrow" /></button></header><div className="brand-activity-sheet__labels"><span>Creator</span><span>Clip</span><span>Verified views</span><span>Earned</span><span>State</span></div>{[
    ["KM", "Kemi Frames", "Group call hunger", 98200, 49000, "Earning"],
    ["TO", "Tobi On Cam", "Roommate took the last pack", 76400, 38000, "Earning"],
    ["NA", "Nana Edits", "No light, no long thing", 51600, 25500, "Review"],
    ["DD", "Deji Does It", "Fastest flatmate alive", 34900, 17000, "Checking"],
  ].map((row) => <article key={String(row[1])}><span className="brand-activity-creator"><i>{row[0]}</i><p><strong>{row[1]}</strong><small>Connected account</small></p></span><strong>{row[2]}</strong><b><AnimatedNumber value={Number(row[3])} format="compact" /></b><b><Money value={Number(row[4])} /></b><Status tone={row[5] === "Earning" ? "lime" : row[5] === "Review" ? "gold" : "paper"}>{row[5]}</Status></article>)}</section></div>;
}

function ReviewCard({ review }: { review: BrandReview }) {
  return <Link href={`/brand/reviews/${review.id}`} className="review-card"><div className="review-card__image"><Image src={review.image} alt="" fill sizes="(max-width: 700px) 100vw, 280px" /><span><ProductIcon name="play" /></span><b>{review.platform}</b></div><div className="review-card__body"><div><Status tone="gold">Needs review</Status><small>{review.submitted}</small></div><h2>{review.title}</h2><p>{review.creator} <span>{review.handle}</span></p><blockquote>{review.issue}</blockquote><div><span>Checker confidence</span><strong><AnimatedNumber value={review.confidence} suffix="%" /></strong><i><b style={{ width: `${review.confidence}%` }} /></i></div></div><ProductIcon name="arrow" /></Link>;
}

const tabMap: Record<string, "needs_review" | "appeals" | "resolved"> = {
  "Needs review": "needs_review",
  "Appeals": "appeals",
  "Resolved": "resolved",
};

function apiReviewToBrand(r: ApiReviewCard): BrandReview {
  const validPlatforms = ["TikTok", "Instagram", "YouTube"] as const;
  const platform = validPlatforms.find((p) => p.toLowerCase() === r.platform.toLowerCase()) ?? "TikTok";
  return {
    id: r.id,
    title: r.title ?? r.campaign_title,
    creator: r.creator_name,
    handle: r.creator_handle ? `@${r.creator_handle.replace(/^@/, "")}` : "",
    platform,
    image: r.video_url ?? "/assets/video/creator-reaction-poster.jpg",
    submitted: new Date(r.submitted_at).toLocaleDateString("en-NG", { day: "numeric", month: "short" }),
    issue: r.issue ?? "Please review this submission.",
    confidence: Math.round((r.confidence ?? 0.75) * 100),
  };
}

export function BrandReviewQueueScreen() {
  const [filter, setFilter] = useState("Needs review");
  const [reviews, setReviews] = useState<BrandReview[]>(brandReviews);
  const [counts, setCounts] = useState({ needs_review: 7, appeals: 0, resolved: 0 });

  useEffect(() => {
    const tab = tabMap[filter] ?? "needs_review";
    brandApi.reviews(tab).then((data) => {
      setCounts(data.counts);
      if (tab === "needs_review") {
        setReviews(data.items.length > 0 ? data.items.map(apiReviewToBrand) : brandReviews);
      }
    }).catch(() => undefined);
  }, [filter]);

  const needsCount = counts.needs_review;
  return <div className="brand-page review-queue-page">
    <PageHeading title={`${needsCount} submission${needsCount !== 1 ? "s" : ""} need review.`} copy="Approve a submission or request a correction. These clips are not earning yet." action={<div className="review-count"><AnimatedNumber value={needsCount} padStart={2} /><span>waiting<br />for review</span></div>} />
    <div className="brand-filter-row">{["Needs review", "Appeals", "Resolved"].map((item) => <button type="button" key={item} onClick={() => setFilter(item)} className={filter === item ? "is-active" : ""}>{item}{item === "Needs review" && <b>{needsCount}</b>}</button>)}</div>
    {filter === "Needs review" ? <section className="review-list">{reviews.map((review) => <ReviewCard review={review} key={review.id} />)}</section> : <section className="review-empty"><BrandArt src={filter === "Appeals" ? art.review : art.proof} label={filter === "Appeals" ? "No appeals waiting" : "Queue cleared"} tone="lime" compact /><h2>{filter === "Appeals" ? "Nothing has been appealed." : "No resolved submissions yet."}</h2><p>{filter === "Appeals" ? "Creator appeals will arrive here with the original verdict and supporting evidence." : "Resolved submissions will appear here with the decision and evidence."}</p></section>}
  </div>;
}

export function BrandReviewDetailScreen({ id = "submission-1042" }: { id?: string }) {
  const review = brandReviews.find((item) => item.id === id) ?? brandReviews[0];
  const [decision, setDecision] = useState<"approve" | "changes" | null>(null);
  if (decision) return <div className="brand-page review-resolved"><BrandArt src={decision === "approve" ? art.proof : art.review} label={decision === "approve" ? "Approved" : "Correction requested"} tone={decision === "approve" ? "lime" : "gold"} /><Status tone={decision === "approve" ? "lime" : "gold"}>{decision === "approve" ? "Approved" : "Changes requested"}</Status><h1>{decision === "approve" ? "Clip approved." : "Correction requested."}</h1><p>{decision === "approve" ? "New verified views can now earn from the No long thing campaign." : "The creator received the failed requirement and can submit a corrected post."}</p><ActionLink href="/brand/reviews">Review the next clip</ActionLink></div>;
  return <div className="brand-page review-detail-page"><Link className="brand-back" href="/brand/reviews"><ProductIcon name="chevron" />Back to review queue</Link><header><div><Status tone="gold">Needs review</Status><h1>{review.title}</h1><p>{review.creator} <span>{review.handle}</span> · {review.platform}</p></div><div className="confidence-ticket"><span>Checker confidence</span><strong><AnimatedNumber value={review.confidence} suffix="%" /></strong><small>Below the 80% auto-decision threshold</small></div></header><div className="review-detail-grid"><section className="submission-player"><div><Image src={review.image} alt="Submission preview" fill sizes="(max-width: 900px) 100vw, 50vw" /><button type="button" aria-label="Play submission"><ProductIcon name="play" /></button><span>00:24</span></div><p><span><i>KM</i><strong>{review.creator}</strong><small>Connected {review.platform} account</small></span><a href="#public-post">Open public post<ProductIcon name="link" /></a></p></section><aside className="review-evidence"><BrandArt src={art.review} label="Review point" tone="gold" compact /><div><small>Flagged requirement</small><h2>{review.issue}</h2><p>The product appears between 00:11 and 00:13. The pack is visible, but another object covers part of the brand mark.</p></div></aside></div><section className="decision-sheet"><header><div><h2>Requirements</h2><p>Check each requirement before deciding.</p></div><Status tone="paper">4 requirements</Status></header><ol><li className="is-pass"><span><ProductIcon name="check" /></span><p><strong>Show the prepared noodles clearly on screen.</strong><small>Found at 00:08 and 00:19</small></p><b>Pass</b></li><li className="is-review"><span><ProductIcon name="eye" /></span><p><strong>Show the product pack clearly on screen.</strong><small>Partly visible at 00:11. Brand mark may be obscured.</small></p><b>Review</b></li><li className="is-pass"><span><ProductIcon name="check" /></span><p><strong>Say or display: No long thing.</strong><small>Transcript match at 00:17</small></p><b>Pass</b></li><li className="is-pass"><span><ProductIcon name="check" /></span><p><strong>Tag @indomie_nigeria and use #NoLongThing.</strong><small>Both found in the public caption</small></p><b>Pass</b></li></ol><div className="decision-actions"><button type="button" className="brand-button brand-button--dark" onClick={() => setDecision("changes")}>Request a correction<ProductIcon name="arrow" /></button><button type="button" className="brand-button" onClick={() => setDecision("approve")}>Approve this clip<ProductIcon name="check" /></button></div></section></div>;
}

export function BrandSettingsScreen() {
  const [saved, setSaved] = useState(false);
  const [notices, setNotices] = useState({ funding: true, reviews: true, reports: false });
  const storedProfile = useStoredProfile("brand", BRAND_PROFILE_FALLBACK);
  const [profile, setProfile] = useState(BRAND_PROFILE_FALLBACK);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setProfile(storedProfile));
    return () => window.cancelAnimationFrame(frame);
  }, [storedProfile]);

  return <div className="brand-page brand-settings-page"><PageHeading title="Settings" copy="Manage organisation details, funding contact and campaign alerts." /><div className="brand-settings-layout"><nav><a href="#identity">Organisation identity</a><a href="#funding">Funding contact</a><a href="#alerts">Campaign alerts</a></nav><div><section id="identity" className="brand-settings-sheet"><header><div><h2>Organisation identity</h2><p>Shown to creators on your campaigns.</p></div><ProfileAvatar profile={profile} fallback="GR" className="brand-settings-avatar" /></header><div className="brand-profile-editor"><ProfilePhotoPicker value={profile.photo} name={profile.name} onChange={(photo) => setProfile((current) => ({ ...current, photo }))} tone="gold" compact /><div className="brand-profile-fields"><label><span>Public organisation name</span><input value={profile.name} onChange={(event) => setProfile((current) => ({ ...current, name: event.target.value.slice(0, 60) }))} /></label><label><span>Short description</span><textarea value={profile.bio} onChange={(event) => setProfile((current) => ({ ...current, bio: event.target.value.slice(0, 240) }))} /></label><label><span>Website</span><input defaultValue="gbedurecords.com" /></label></div></div><button type="button" className="brand-button" disabled={profile.name.trim().length < 2 || profile.bio.trim().length < 2} onClick={() => { saveStoredProfile("brand", { ...profile, name: profile.name.trim(), bio: profile.bio.trim() }); setSaved(true); window.setTimeout(() => setSaved(false), 1800); }}>{saved ? "Changes saved" : "Save identity"}<ProductIcon name={saved ? "check" : "arrow"} /></button></section><section id="funding" className="brand-settings-sheet"><header><div><h2>Funding contact</h2><p>Used for receipts, settlement questions and campaign closeout.</p></div><ProductIcon name="bank" /></header><label><span>Finance email</span><input type="email" defaultValue="finance@gbedurecords.com" /></label><div className="verified-funder"><ProductIcon name="shield" /><span><strong>Gbedu Records Ltd.</strong><small>Business identity verified</small></span><Status>Verified</Status></div></section><section id="alerts" className="brand-settings-sheet"><header><div><h2>Campaign alerts</h2><p>Choose which campaign events send an alert.</p></div><ProductIcon name="bell" /></header>{Object.entries(notices).map(([key, value]) => <label className="brand-toggle" key={key}><span><strong>{key === "funding" ? "Funding and pot alerts" : key === "reviews" ? "Submission review alerts" : "Weekly performance report"}</strong><small>{key === "funding" ? "Cleared funds, low pot and campaign closeout" : key === "reviews" ? "Uncertain checks and creator appeals" : "Verified views and spend summary every Monday"}</small></span><input type="checkbox" checked={value} onChange={() => setNotices((current) => ({ ...current, [key]: !value }))} /><i /></label>)}</section></div></div></div>;
}
