"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import {
  ProfileAvatar,
  ProfilePhotoPicker,
  saveStoredProfile,
  type StoredProfile,
} from "@/components/ui/ProfilePhotoPicker";
import { ReceiptHeader } from "@/components/ui/ReceiptHeader";
import {
  brandReviews,
  type BrandCampaign,
  type BrandCampaignState,
  type BrandReview,
} from "@/lib/brand";
import {
  brandApi,
  type BrandOverviewOut,
  type ReviewCard as ApiReviewCard,
} from "@/lib/api/brand";
import {
  campaignsApi,
  type CampaignOut,
  type CampaignStats,
  type CampaignSubmissionRow,
} from "@/lib/api/campaigns";
import { organisationsApi } from "@/lib/api/organisations";
import { profileApi } from "@/lib/api/profile";
import { errorMessage } from "@/lib/api/client";
import { uploadsApi, walletApi, type BrandWalletOut } from "@/lib/api/account";
import {
  BRAND_CAMPAIGN_FEE_RATE,
  calculateFee,
  feePercentage,
} from "@/lib/fees";
import {
  useBrandCampaign,
  type BriefRule,
  type CampaignMetricKey,
} from "./BrandCampaignProvider";
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
  name: "",
  bio: "",
  photo: "",
};

function Money({
  value,
  compact = false,
  delay = 0,
}: {
  value: number;
  compact?: boolean;
  delay?: number;
}) {
  return (
    <AnimatedNumber
      value={value}
      format={compact ? "compact" : "money"}
      delay={delay}
    />
  );
}

function BrandArt({
  src,
  label,
  tone = "gold",
  compact = false,
}: {
  src: string;
  label: string;
  tone?: "gold" | "lime" | "paper" | "ink";
  compact?: boolean;
}) {
  return (
    <div
      className={`brand-art brand-art--${tone}${compact ? " brand-art--compact" : ""}`}
    >
      <Image src={src} alt="" width={768} height={768} />
      <span>{label}</span>
    </div>
  );
}

function Status({
  children,
  tone = "lime",
}: {
  children: ReactNode;
  tone?: "lime" | "gold" | "ink" | "danger" | "paper";
}) {
  return (
    <span className={`brand-status brand-status--${tone}`}>
      <i className="brand-status__dot" />
      {children}
    </span>
  );
}

function PageHeading({
  note,
  title,
  copy,
  action,
}: {
  note?: string;
  title: string;
  copy?: string;
  action?: ReactNode;
}) {
  return (
    <header className="brand-page-heading">
      <div>
        {note ? <p>{note}</p> : null}
        <h1>{title}</h1>
        {copy ? <span>{copy}</span> : null}
      </div>
      {action}
    </header>
  );
}

function ActionLink({
  href,
  children,
  dark = false,
}: {
  href: string;
  children: ReactNode;
  dark?: boolean;
}) {
  return (
    <Link
      href={href}
      className={dark ? "brand-button brand-button--dark" : "brand-button"}
    >
      {children}
      <ProductIcon name="arrow" />
    </Link>
  );
}

const builderSteps = [
  { label: "Campaign", href: "/brand/campaigns/new" },
  { label: "Brief", href: "/brand/campaigns/new/brief" },
  { label: "Platforms", href: "/brand/campaigns/new/platforms" },
  { label: "Metrics", href: "/brand/campaigns/new/metrics" },
  { label: "Rules", href: "/brand/campaigns/new/rules" },
  { label: "Money", href: "/brand/campaigns/new/budget" },
  { label: "Review", href: "/brand/campaigns/new/review" },
];

function BuilderFrame({
  step,
  title,
  copy,
  artSrc,
  artLabel,
  children,
  aside,
}: {
  step: number;
  title: string;
  copy: string;
  artSrc: string;
  artLabel: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  const { draft, draftLoading, draftError } = useBrandCampaign();
  if (draftLoading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading campaign draft" note="" /></div>;
  if (draftError) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="campaigns" title="Campaign draft unavailable" copy={draftError} role="alert" /></div>;
  return (
    <div className="brand-builder-page">
      <header className="builder-progress">
        <div>
          <span>Campaign studio</span>
          <strong>
            {String(step + 1).padStart(2, "0")} /{" "}
            {String(builderSteps.length).padStart(2, "0")}
          </strong>
        </div>
        <nav aria-label="Campaign creation progress">
          {builderSteps.map((item, index) => (
            <Link
              href={item.href}
              key={item.href}
              className={
                index === step ? "is-current" : index < step ? "is-done" : ""
              }
            >
              <i>{index < step ? <ProductIcon name="check" /> : index + 1}</i>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </header>
      <div className="builder-layout">
        <section className="builder-work">
          <div className="builder-title">
            <h1>{title}</h1>
            <span>{copy}</span>
          </div>
          {children}
        </section>
        <aside className="builder-preview">
          {draft.coverImage ? (
            <div className="builder-cover-preview">
              <Image
                src={draft.coverImage}
                alt={`${draft.title || "Campaign"} cover`}
                fill
                unoptimized
                sizes="420px"
              />
              <span>Campaign cover</span>
            </div>
          ) : (
            <BrandArt src={artSrc} label={artLabel} />
          )}
          <div className="builder-live-card">
            <small>Campaign preview</small>
            <h2>{draft.title || "Untitled campaign"}</h2>
            <p>
              {draft.description ||
                "Your campaign description will appear here."}
            </p>
            <div>
              <span>
                {draft.platforms.length
                  ? draft.platforms.join(" + ")
                  : "Choose platforms"}
              </span>
              <strong>
                {draft.metrics.length}{" "}
                {draft.metrics.length === 1 ? "metric" : "metrics"}
              </strong>
            </div>
            <em>
              {draft.endCondition === "budget"
                ? "Runs until the pot is empty"
                : `${draft.days} day duration`}
            </em>
          </div>
          {aside}
        </aside>
      </div>
    </div>
  );
}

function FormActions({
  back,
  next,
  label = "Continue",
}: {
  back: string;
  next?: string;
  label?: string;
}) {
  return (
    <div className="builder-actions">
      <Link href={back}>
        <ProductIcon name="chevron" />
        Back
      </Link>
      {next ? (
        <ActionLink href={next}>{label}</ActionLink>
      ) : (
        <button type="submit" className="brand-button">
          {label}
          <ProductIcon name="arrow" />
        </button>
      )}
    </div>
  );
}

function PotBar({ campaign }: { campaign: BrandCampaign }) {
  const percentage = Math.round((campaign.remaining / campaign.pot) * 100);
  return (
    <div className="brand-pot-bar">
      <div>
        <span>Pot still available</span>
        <strong>
          <Money value={campaign.remaining} />
        </strong>
      </div>
      <div className="brand-pot-bar__track">
        <i style={{ width: `${percentage}%` }} />
        <b>
          <ProductIcon name="shield" />
        </b>
      </div>
      <p>
        <AnimatedNumber value={percentage} suffix="%" /> of{" "}
        <Money value={campaign.pot} /> remains
      </p>
    </div>
  );
}

export function BrandOverviewScreen() {
  const [overview, setOverview] = useState<BrandOverviewOut | null>(null);
  const [wallet, setWallet] = useState<BrandWalletOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([brandApi.overview(), walletApi.getBrand()])
      .then(([overviewData, walletData]) => { setOverview(overviewData); setWallet(walletData); })
      .catch((err) => setError(errorMessage(err, "We couldn't load your brand workspace.")))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="brand-page">
        <ClippitLoader
          contained
          tone="gold"
          label="Opening your brand workspace"
          note="Checking campaigns, reviews and wallet activity."
        />
      </div>
    );

  if (error || !overview || !wallet) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="campaigns" title="We couldn't load your workspace" copy={error || "The workspace response was incomplete."} role="alert" /></div>;

  const pendingReviews = overview.pending_reviews;
  const orgName = overview.organisation_name;
  if (!overview.featured) return <div className="brand-page brand-overview-page"><PageHeading title={`What are we posting today, ${orgName}?`} copy="Create a campaign to start receiving creator submissions." action={<ActionLink href="/brand/campaigns/new">Create campaign</ActionLink>} /><section className="brand-wallet-strip"><div><span><ProductIcon name="wallet" /></span><p><small>Available to withdraw</small><strong><Money value={wallet.available} /></strong></p><ActionLink href="/brand/wallet">Open wallet</ActionLink></div><dl><div><dt>Reserved in campaign pots</dt><dd><Money value={wallet.reserved} /></dd></div><div><dt>Live campaigns</dt><dd><AnimatedNumber value={overview.live_campaigns} /></dd></div><div><dt>Draft campaigns</dt><dd><AnimatedNumber value={overview.draft_campaigns} /></dd></div></dl></section><ClippitEmptyState tone="gold" icon="campaigns" artSrc={art.brief} title="No live campaign yet" copy="Your first funded campaign will appear here with real submissions, spend and performance." action={<ActionLink href="/brand/campaigns/new">Build a campaign</ActionLink>} /></div>;

  const featured = overview.featured;
  const featuredPot = campaignOutToBrand(featured);
  const featuredImage = featured.cover_image_url ?? "/assets/video/creator-reaction-poster.jpg";
  const featuredTitle = featured.title;
  const featuredLine = featured.tagline ?? featured.description;
  const featuredSlug = featured.slug;

  return (
    <div className="brand-page brand-overview-page">
      <section className="brand-command">
        <div className="brand-command__copy">
          <Status tone={pendingReviews ? "gold" : "lime"}>
            {pendingReviews ? `${pendingReviews} need review` : "Campaign live"}
          </Status>
          <h1>
            {pendingReviews ? (
              <>
                {pendingReviews} clips need
                <br />
                your review.
              </>
            ) : (
              <>
                What are we posting today,
                <br />
                {orgName}?
              </>
            )}
          </h1>
          <p>
            {pendingReviews
              ? "These submissions are waiting for a decision before they can earn."
              : "Create a campaign or check the campaigns already running."}
          </p>
          <div className="brand-command__actions">
            <ActionLink
              href={pendingReviews ? "/brand/reviews" : "/brand/campaigns/new"}
            >
              {pendingReviews ? "Review submissions" : "Create a campaign"}
            </ActionLink>
            <ActionLink href="/brand/campaigns/new" dark>
              Create campaign
            </ActionLink>
          </div>
        </div>
        <div className="brand-command__visual">
          <div className="brand-command__image">
            <Image
              src={featuredImage}
              alt="Creator from the featured campaign"
              fill
              sizes="(max-width: 900px) 100vw, 44vw"
              priority
            />
          </div>
          <BrandArt
            src={art.funding}
            label="Campaign pot"
            tone="gold"
            compact
          />
          <span className="brand-command__stamp">
            <b>
              <AnimatedNumber value={featuredPot.submissions} />
            </b>{" "}
            submissions
          </span>
        </div>
      </section>
      <section className="brand-wallet-strip">
        <div>
          <span>
            <ProductIcon name="wallet" />
          </span>
          <p>
            <small>Available in Brand wallet</small>
            <strong>
              <Money value={wallet.available} />
            </strong>
          </p>
          <ActionLink href="/brand/wallet">Open wallet</ActionLink>
        </div>
        <dl>
          <div>
            <dt>Reserved in campaign pots</dt>
            <dd>
              <Money value={wallet.reserved} />
            </dd>
          </div>
          <div>
            <dt>Withdrawn all time</dt>
            <dd>
              <Money value={wallet.withdrawn_all_time} />
            </dd>
          </div>
          <div>
            <dt>Available to withdraw</dt>
            <dd>
              <Money value={wallet.available} />
            </dd>
          </div>
        </dl>
      </section>
      <section className="brand-live-board">
        <div className="brand-live-board__head">
          <div>
            <Status tone="gold">{featured.time_left ? `Closing in ${featured.time_left.days} day${featured.time_left.days === 1 ? "" : "s"}` : "Runs until the pot is used"}</Status>
            <h2>{featuredTitle}</h2>
            <p>{featuredLine}</p>
          </div>
          <Link href={`/brand/campaigns/${featuredSlug}`}>
            View campaign
            <ProductIcon name="arrow" />
          </Link>
        </div>
        <div className="brand-live-board__grid">
          <PotBar campaign={featuredPot} />
          <article>
            <small>Verified views</small>
            <strong>
              <AnimatedNumber
                value={
                  featured.metrics?.verified_views ?? 0
                }
                format="compact"
              />
            </strong>
            <p>read from connected creator accounts</p>
            <span className="signal-ripples">
              <i />
              <i />
              <i />
            </span>
          </article>
          <article>
            <small>Approved clips</small>
            <strong>
              <AnimatedNumber
                value={featured.metrics?.approved ?? 0}
                padStart={2}
              />
            </strong>
            <p>clips currently earning</p>
            <div className="creator-token-stack">
              {Array.from({ length: Math.min(3, featured.metrics?.approved ?? 0) }, (_, index) => <i key={index}><ProductIcon name="person" /></i>)}
              {(featured.metrics?.approved ?? 0) > 3 && <i>+{(featured.metrics?.approved ?? 0) - 3}</i>}
            </div>
          </article>
          <article className="review-callout">
            <BrandArt
              src={art.review}
              label="Review queue"
              tone="lime"
              compact
            />
            <div>
              <small>Needs review</small>
              <strong>
                <AnimatedNumber value={pendingReviews} padStart={2} />
              </strong>
              <p>These clips do not earn until you decide.</p>
              <Link href="/brand/reviews">
                Review now
                <ProductIcon name="arrow" />
              </Link>
            </div>
          </article>
        </div>
      </section>
      <section className="brand-proof-ribbon">
        <div>
          <ProductIcon name="eye" />
          <span>
            <small>Views verified today</small>
            <strong>
              <AnimatedNumber value={overview.views_last_24h} />
            </strong>
          </span>
        </div>
        <i />
        <div>
          <ProductIcon name="wallet" />
          <span>
            <small>Creator earnings today</small>
            <strong>
              <Money value={overview.earnings_last_24h} />
            </strong>
          </span>
        </div>
        <i />
        <div>
          <ProductIcon name="shield" />
          <span>
            <small>Unmatched spend</small>
            <strong>
              <Money value={overview.unmatched_spend} />
            </strong>
          </span>
        </div>
      </section>
    </div>
  );
}

function CampaignCard({ campaign }: { campaign: BrandCampaign }) {
  const href =
    campaign.state === "Draft"
      ? "/brand/campaigns/new"
      : campaign.state === "Completed"
        ? `/brand/campaigns/${campaign.slug}/report`
        : `/brand/campaigns/${campaign.slug}`;
  return (
    <Link
      href={href}
      className={`brand-campaign-card brand-campaign-card--${campaign.state.toLowerCase()}`}
    >
      <div className="brand-campaign-card__image">
        <Image
          src={campaign.image}
          alt=""
          fill
          sizes="(max-width: 700px) 100vw, 320px"
        />
        <Status
          tone={
            campaign.state === "Live"
              ? "lime"
              : campaign.state === "Draft"
                ? "gold"
                : "paper"
          }
        >
          {campaign.state}
        </Status>
      </div>
      <div className="brand-campaign-card__body">
        <div>
          <small>{campaign.brandName ?? "Your organisation"}</small>
          <h2>{campaign.title}</h2>
          <p>{campaign.line}</p>
        </div>
        <dl>
          <div>
            <dt>Rate</dt>
            <dd>
              <Money value={campaign.rate} /> / 1K
            </dd>
          </div>
          <div>
            <dt>{campaign.state === "Completed" ? "Delivered" : "Pot left"}</dt>
            <dd>
              {campaign.state === "Completed" ? (
                <AnimatedNumber
                  value={campaign.verifiedViews}
                  format="compact"
                  suffix=" views"
                />
              ) : (
                <Money value={campaign.remaining} />
              )}
            </dd>
          </div>
          <div>
            <dt>Clips</dt>
            <dd>
              <AnimatedNumber value={campaign.submissions} padStart={2} />
            </dd>
          </div>
        </dl>
        <span>
          {campaign.state === "Completed" ? "Open closeout" : "Open campaign"}
          <ProductIcon name="arrow" />
        </span>
      </div>
    </Link>
  );
}

function campaignOutToBrand(c: CampaignOut): BrandCampaign {
  const phase = c.phase as BrandCampaignState;
  return {
    brandName: c.brand?.name ?? undefined,
    slug: c.slug,
    title: c.title,
    line: c.tagline ?? c.description.slice(0, 100),
    state: (
      [
        "Funding",
        "Draft",
        "Live",
        "Paused",
        "Completed",
        "Cancelled",
      ] as BrandCampaignState[]
    ).includes(phase)
      ? phase
      : "Live",
    image: c.cover_image_url ?? "/assets/video/creator-reaction-poster.jpg",
    pot: c.pot,
    remaining: c.remaining,
    rate: c.payout_rule?.rate_per_1000_views ?? 0,
    verifiedViews: c.metrics?.verified_views ?? 0,
    submissions: c.metrics?.submissions ?? 0,
    approved: c.metrics?.approved ?? 0,
    review: c.metrics?.review ?? 0,
    daysLeft: c.time_left?.days ?? 0,
    endCondition: c.time_left ? "duration" : "budget",
  };
}

export function BrandCampaignsScreen() {
  const [filter, setFilter] = useState<"All" | BrandCampaign["state"]>("All");
  const [allCampaigns, setAllCampaigns] =
    useState<BrandCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    campaignsApi
      .list()
      .then((data) => setAllCampaigns(data.map(campaignOutToBrand)))
      .catch((err) => setError(errorMessage(err, "We couldn't load your campaigns.")))
      .finally(() => setLoading(false));
  }, []);

  const visible = allCampaigns.filter(
    (campaign) => filter === "All" || campaign.state === filter,
  );
  return (
    <div className="brand-page">
      <PageHeading
        title="Campaigns"
        copy="Create a campaign or open one that is already running."
        action={
          <ActionLink href="/brand/campaigns/new">Create campaign</ActionLink>
        }
      />
      <div className="brand-filter-row">
        {[
          "All",
          "Live",
          "Paused",
          "Funding",
          "Draft",
          "Completed",
          "Cancelled",
        ].map((item) => (
          <button
            type="button"
            key={item}
            className={filter === item ? "is-active" : ""}
            onClick={() => setFilter(item as typeof filter)}
          >
            {item}
            {item === "Live" && <i />}
          </button>
        ))}
      </div>
      {loading ? (
        <ClippitLoader
          contained
          compact
          tone="gold"
          label="Gathering your campaigns"
          note="Checking current pots, submissions and campaign status."
        />
      ) : error ? (
        <ClippitEmptyState tone="danger" icon="campaigns" title="We couldn't load campaigns" copy={error} role="alert" />
      ) : visible.length ? (
        <section className="brand-campaign-grid">
          {visible.map((campaign) => (
            <CampaignCard campaign={campaign} key={campaign.slug} />
          ))}
        </section>
      ) : (
        <ClippitEmptyState tone="gold" icon="campaigns" artSrc={art.brief} title={filter === "All" ? "No campaigns yet" : `No ${filter.toLowerCase()} campaigns`} copy={filter === "All" ? "Create your first campaign to start receiving creator submissions." : "Campaigns with this status will appear here."} action={filter === "All" ? <ActionLink href="/brand/campaigns/new">Create campaign</ActionLink> : undefined} />
      )}
    </div>
  );
}

export function CampaignBasicsScreen() {
  const router = useRouter();
  const { draft, update } = useBrandCampaign();
  const [uploadingAssets, setUploadingAssets] = useState(false);
  const [assetError, setAssetError] = useState("");
  const uploadAssets = async (files: FileList | null) => {
    const selected = Array.from(files ?? []);
    if (!selected.length) return;
    setUploadingAssets(true);
    setAssetError("");
    try {
      const uploaded = await Promise.all(selected.map(async (file) => {
        if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
          throw new Error(`${file.name} is not an image or video.`);
        }
        const result = file.type.startsWith("video/")
          ? await uploadsApi.video(file)
          : await uploadsApi.image(file);
        return { id: result.id, name: file.name, url: result.url, kind: file.type.startsWith("video/") ? "video" : "image" };
      }));
      update({ assets: [...draft.assets, ...uploaded].slice(0, 20) });
    } catch (reason) {
      setAssetError(errorMessage(reason, "Those campaign assets could not be uploaded."));
    } finally {
      setUploadingAssets(false);
    }
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (draft.title.trim() && draft.description.trim())
      router.push("/brand/campaigns/new/brief");
  };
  return (
    <BuilderFrame
      step={0}
      title="Campaign details"
      copy="Add what creators need to understand and access this campaign."
      artSrc={art.brief}
      artLabel="Campaign details"
    >
      <form className="brand-builder-form" onSubmit={submit}>
        <CampaignCoverPicker
          value={draft.coverImage}
          title={draft.title}
          onChange={(coverImage) => update({ coverImage })}
        />
        <label>
          <span>Campaign title</span>
          <input
            value={draft.title}
            onChange={(event) => update({ title: event.target.value })}
            placeholder="The late-night bowl"
            maxLength={56}
            required
          />
          <small>{draft.title.length}/56</small>
        </label>
        <label>
          <span>Campaign description</span>
          <textarea
            value={draft.description}
            onChange={(event) => update({ description: event.target.value })}
            placeholder="Tell creators what the campaign is about"
            maxLength={180}
            required
          />
          <small>{draft.description.length}/180</small>
        </label>
        <div className="builder-inline-fields">
          <label>
            <span>Content niche</span>
            <select
              value={draft.niche}
              onChange={(event) => update({ niche: event.target.value })}
            >
              <option value="" disabled>Choose a niche</option>
              <option>Comedy</option>
              <option>Food</option>
              <option>Music</option>
              <option>Beauty</option>
              <option>Lifestyle</option>
              <option>Gaming</option>
              <option>Fitness</option>
              <option>Tech</option>
              <option>Travel</option>
            </select>
          </label>
          <fieldset>
            <legend>Who can join?</legend>
            <div className="builder-choice-row">
              <button
                type="button"
                className={draft.accessMode === "public" ? "is-selected" : ""}
                onClick={() => update({ accessMode: "public" })}
              >
                Public
              </button>
              <button
                type="button"
                className={draft.accessMode === "invite" ? "is-selected" : ""}
                onClick={() => update({ accessMode: "invite" })}
              >
                Invite only
              </button>
            </div>
          </fieldset>
        </div>
        {draft.accessMode === "invite" && <p className="platform-proof"><ProductIcon name="shield" /><span><strong>Clippit generates the invite code.</strong><small>It appears on the campaign page after the campaign is created.</small></span></p>}
        <label>
          <span>Source material</span>
          <div className="brand-input-with-icon">
            <ProductIcon name="link" />
            <input
              value={draft.sourceLink}
              onChange={(event) => update({ sourceLink: event.target.value })}
              placeholder="Paste a brand kit, sound or reference link"
            />
          </div>
          <small>Optional. Creators see this beside the brief.</small>
        </label>
        <label className="builder-asset-upload">
          <span>Campaign assets</span>
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"
            disabled={uploadingAssets}
            onChange={(event) => { void uploadAssets(event.target.files); event.target.value = ""; }}
          />
          <small>
            {uploadingAssets
              ? "Uploading assets..."
              : draft.assets.length
              ? `${draft.assets.length} assets ready`
              : "Optional product shots, clips or visual references"}
          </small>
          {assetError && <small className="campaign-cover-error" role="alert">{assetError}</small>}
        </label>
        <FormActions back="/brand/campaigns" label="Add requirements" />
      </form>
    </BuilderFrame>
  );
}

export function CampaignBriefScreen() {
  const { draft, addRule, removeRule } = useBrandCampaign();
  const [text, setText] = useState("");
  const [kind, setKind] = useState<BriefRule["kind"]>("must");
  const add = () => {
    if (text.trim().length < 5) return;
    addRule(kind, text.trim());
    setText("");
  };
  return (
    <BuilderFrame
      step={1}
      title="Campaign requirements"
      copy="Add one requirement per line. Each requirement should be easy to verify from the posted clip."
      artSrc={art.brief}
      artLabel="Requirements"
      aside={
        <p className="builder-margin-note">
          Only add requirements that can be checked from the public post.
        </p>
      }
    >
      <div className="brief-composer">
        <div className="brief-add">
          <div className="brief-kind">
            <button
              type="button"
              className={kind === "must" ? "is-active" : ""}
              onClick={() => setKind("must")}
            >
              <ProductIcon name="check" />
              Must do
            </button>
            <button
              type="button"
              className={kind === "avoid" ? "is-active is-avoid" : ""}
              onClick={() => setKind("avoid")}
            >
              <span>!</span>Must avoid
            </button>
          </div>
          <div className="brief-entry">
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  add();
                }
              }}
              placeholder={
                kind === "must"
                  ? "Show the prepared noodles clearly on screen"
                  : "Do not make health or nutrition claims"
              }
            />
            <button type="button" onClick={add} aria-label="Add requirement">
              <ProductIcon name="arrow" />
            </button>
          </div>
        </div>
        <ol className="brief-list">
          {draft.rules.map((rule, index) => (
            <li
              key={rule.id}
              className={rule.kind === "avoid" ? "is-avoid" : ""}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <i>{rule.kind === "must" ? <ProductIcon name="check" /> : "!"}</i>
              <p>
                <small>{rule.kind === "must" ? "Must do" : "Must avoid"}</small>
                <strong>{rule.text}</strong>
              </p>
              <button
                type="button"
                onClick={() => removeRule(rule.id)}
                aria-label={`Remove ${rule.text}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ol>
        <FormActions
          back="/brand/campaigns/new"
          next="/brand/campaigns/new/platforms"
          label="Choose platforms"
        />
      </div>
    </BuilderFrame>
  );
}

const platformChoices: Array<{
  name: string;
  icon: ProductIconName;
  note: string;
  signal: string;
}> = [
  {
    name: "TikTok",
    icon: "tiktok",
    note: "Short vertical video",
    signal: "Official views",
  },
  {
    name: "Instagram",
    icon: "instagram",
    note: "Reels and visual content",
    signal: "Official views",
  },
  {
    name: "Facebook",
    icon: "facebook",
    note: "Video and community posts",
    signal: "Official views",
  },
  {
    name: "X",
    icon: "x",
    note: "Video posts and conversations",
    signal: "Official views",
  },
  {
    name: "YouTube",
    icon: "youtube",
    note: "Shorts and longer videos",
    signal: "Official views",
  },
];

export function CampaignPlatformsScreen() {
  const { draft, togglePlatform } = useBrandCampaign();
  return (
    <BuilderFrame
      step={2}
      title="Choose platforms"
      copy="Select where creators can publish for this campaign."
      artSrc={art.social}
      artLabel="Platforms"
    >
      <div className="platform-picker">
        {platformChoices.map((platform) => {
          const selected = draft.platforms.includes(platform.name);
          return (
            <button
              type="button"
              key={platform.name}
              onClick={() => togglePlatform(platform.name)}
              className={selected ? "is-selected" : ""}
            >
              <span>
                <ProductIcon name={platform.icon} />
              </span>
              <p>
                <strong>{platform.name}</strong>
                <small>{platform.note}</small>
              </p>
              <i>{selected ? <ProductIcon name="check" /> : null}</i>
              <b>{platform.signal}</b>
            </button>
          );
        })}
      </div>
      <div className="platform-proof">
        <ProductIcon name="shield" />
        <p>
          <strong>Official platform readings count.</strong>
          <small>
            Selected social metrics start counting after a clip is approved.
          </small>
        </p>
      </div>
      <FormActions
        back="/brand/campaigns/new/brief"
        next="/brand/campaigns/new/metrics"
        label="Choose metrics"
      />
    </BuilderFrame>
  );
}

const metricChoices: Array<{
  type: CampaignMetricKey;
  title: string;
  note: string;
  icon: ProductIconName;
  group: "social" | "conversion";
}> = [
  {
    type: "view",
    title: "Views",
    note: "Verified plays from connected creator accounts",
    icon: "eye",
    group: "social",
  },
  {
    type: "comment",
    title: "Comments",
    note: "Public comments on approved posts",
    icon: "brief",
    group: "social",
  },
  {
    type: "share",
    title: "Shares",
    note: "Verified platform share counts",
    icon: "arrow",
    group: "social",
  },
  {
    type: "visit",
    title: "Store visits",
    note: "Clicks through a creator's Clippit link",
    icon: "link",
    group: "conversion",
  },
  {
    type: "signup",
    title: "Signups",
    note: "New accounts confirmed by your website",
    icon: "person",
    group: "conversion",
  },
  {
    type: "lead",
    title: "Leads",
    note: "Qualified enquiries or WhatsApp conversations",
    icon: "phone",
    group: "conversion",
  },
  {
    type: "purchase",
    title: "Purchases",
    note: "Completed orders confirmed by your store",
    icon: "wallet",
    group: "conversion",
  },
];

export function CampaignMetricsScreen() {
  const { draft, toggleMetric, updateMetric, update } = useBrandCampaign();
  const hasConversion = draft.metrics.some((metric) =>
    ["visit", "signup", "lead", "purchase"].includes(metric.type),
  );
  const validDestination =
    !hasConversion ||
    (draft.conversionMode === "website"
      ? /^https?:\/\//i.test(draft.storeUrl)
      : draft.whatsappNumber.replace(/\D/g, "").length >= 10);
  return (
    <BuilderFrame
      step={3}
      title="What should this campaign achieve?"
      copy="Choose only the results you want to pay for. Every selected result gets its own rate."
      artSrc={art.proof}
      artLabel="Campaign results"
      aside={
        <div className="metric-side-note">
          <span>{String(draft.metrics.length).padStart(2, "0")}</span>
          <p>
            <strong>results selected</strong>
            <small>
              The campaign dashboard will follow this exact scorecard.
            </small>
          </p>
        </div>
      }
    >
      <section className="metric-studio">
        <div className="metric-studio__rail" aria-label="Campaign metrics">
          {metricChoices.map((choice) => {
            const metric = draft.metrics.find(
              (item) => item.type === choice.type,
            );
            return (
              <article
                key={choice.type}
                className={metric ? "is-selected" : ""}
              >
                <button
                  type="button"
                  onClick={() => toggleMetric(choice.type)}
                  aria-pressed={Boolean(metric)}
                >
                  <span>
                    <ProductIcon name={choice.icon} />
                  </span>
                  <p>
                    <strong>{choice.title}</strong>
                    <small>{choice.note}</small>
                  </p>
                  <i>{metric ? <ProductIcon name="check" /> : null}</i>
                </button>
                {metric ? (
                  <label>
                    <span>Creator rate</span>
                    <div>
                      <b>₦</b>
                      <input
                        type="number"
                        min={1}
                        value={metric.rate}
                        onChange={(event) =>
                          updateMetric(choice.type, {
                            rate: Math.max(1, Number(event.target.value)),
                          })
                        }
                      />
                      <em>
                        {choice.type === "view" ? "per 1,000" : "per result"}
                      </em>
                    </div>
                  </label>
                ) : null}
              </article>
            );
          })}
        </div>
        {hasConversion ? (
          <section className="conversion-route">
            <header>
              <span>
                <ProductIcon name="link" />
              </span>
              <div>
                <small>Conversion route</small>
                <h2>Where should customers go?</h2>
              </div>
            </header>
            <div className="conversion-route__choices">
              <button
                type="button"
                className={
                  draft.conversionMode === "website" ? "is-selected" : ""
                }
                onClick={() => update({ conversionMode: "website" })}
              >
                <ProductIcon name="building" />
                <span>
                  <strong>Online store or website</strong>
                  <small>
                    Clippit adds a creator reference to the destination link.
                  </small>
                </span>
                <i>
                  {draft.conversionMode === "website" && (
                    <ProductIcon name="check" />
                  )}
                </i>
              </button>
              <button
                type="button"
                className={
                  draft.conversionMode === "whatsapp" ? "is-selected" : ""
                }
                onClick={() => update({ conversionMode: "whatsapp" })}
              >
                <ProductIcon name="phone" />
                <span>
                  <strong>WhatsApp orders</strong>
                  <small>
                    Customers open a prefilled chat with a trackable reference.
                  </small>
                </span>
                <i>
                  {draft.conversionMode === "whatsapp" && (
                    <ProductIcon name="check" />
                  )}
                </i>
              </button>
            </div>
            {draft.conversionMode === "website" ? (
              <label>
                <span>Store or website link</span>
                <div className="brand-input-with-icon">
                  <ProductIcon name="link" />
                  <input
                    type="url"
                    value={draft.storeUrl}
                    onChange={(event) =>
                      update({ storeUrl: event.target.value })
                    }
                    placeholder="https://yourstore.com/products"
                  />
                </div>
              </label>
            ) : (
              <label>
                <span>Business WhatsApp number</span>
                <div className="brand-input-with-icon">
                  <ProductIcon name="phone" />
                  <input
                    inputMode="tel"
                    value={draft.whatsappNumber}
                    onChange={(event) =>
                      update({ whatsappNumber: event.target.value })
                    }
                    placeholder="2348012345678"
                  />
                </div>
                <small>
                  Include the country code. Clippit will generate the wa.me
                  link.
                </small>
              </label>
            )}
            <div className="conversion-route__settings">
              <label>
                <span>Attribution window</span>
                <select
                  value={draft.attributionWindowDays}
                  onChange={(event) =>
                    update({
                      attributionWindowDays: Number(event.target.value),
                    })
                  }
                >
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                  <option value={90}>90 days</option>
                </select>
              </label>
              <label>
                <span>Credit goes to</span>
                <select
                  value={draft.attributionModel}
                  onChange={(event) =>
                    update({
                      attributionModel: event.target.value as
                        | "first_touch"
                        | "last_touch",
                    })
                  }
                >
                  <option value="last_touch">Last creator link used</option>
                  <option value="first_touch">First creator link used</option>
                </select>
              </label>
            </div>
            <p className="conversion-route__proof">
              <ProductIcon name="shield" />
              Visits are recorded by Clippit. Signups, leads and purchases are
              confirmed by your store or campaign integration.
            </p>
          </section>
        ) : null}
      </section>
      <div className="builder-actions">
        <Link href="/brand/campaigns/new/platforms">
          <ProductIcon name="chevron" />
          Back
        </Link>
        <Link
          aria-disabled={!validDestination}
          className={`brand-button${!validDestination ? " is-disabled" : ""}`}
          href={validDestination ? "/brand/campaigns/new/rules" : "#"}
        >
          Set earning limits
          <ProductIcon name="arrow" />
        </Link>
      </div>
    </BuilderFrame>
  );
}

export function CampaignRulesScreen() {
  const { draft, update } = useBrandCampaign();
  return (
    <BuilderFrame
      step={4}
      title="Set earning limits"
      copy="Set submission limits, earning caps and when the campaign should stop."
      artSrc={art.proof}
      artLabel="Earning rules"
    >
      <div className="rules-console rules-console--complete">
        <label>
          <span>
            <ProductIcon name="play" />
            Maximum submissions
          </span>
          <div>
            <input
              type="number"
              min={1}
              max={20}
              value={draft.maxSubmissions}
              onChange={(event) =>
                update({
                  maxSubmissions: Math.max(1, Number(event.target.value)),
                })
              }
            />
            <b>videos</b>
          </div>
          <small>Per creator in this campaign.</small>
        </label>
        <label>
          <span>
            <ProductIcon name="wallet" />
            Maximum per video
          </span>
          <div>
            <b>₦</b>
            <input
              type="number"
              min={1000}
              step={5000}
              value={draft.videoCap}
              onChange={(event) =>
                update({ videoCap: Number(event.target.value) })
              }
            />
          </div>
          <small>A single video cannot earn above this amount.</small>
        </label>
        <label>
          <span>
            <ProductIcon name="users" />
            Maximum per creator
          </span>
          <div>
            <b>₦</b>
            <input
              type="number"
              min={1000}
              step={5000}
              value={draft.creatorCap}
              onChange={(event) =>
                update({ creatorCap: Number(event.target.value) })
              }
            />
          </div>
          <small>Across every approved result from one creator.</small>
        </label>
      </div>
      <fieldset className="campaign-end-control">
        <legend>When should the campaign end?</legend>
        <div>
          <button
            type="button"
            className={draft.endCondition === "duration" ? "is-selected" : ""}
            onClick={() => update({ endCondition: "duration" })}
          >
            <span>
              <ProductIcon name="calendar" />
            </span>
            <p>
              <strong>End date or empty pot</strong>
              <small>
                End after the selected duration, or sooner if the pot empties.
              </small>
            </p>
            <i>
              {draft.endCondition === "duration" && (
                <ProductIcon name="check" />
              )}
            </i>
          </button>
          <button
            type="button"
            className={draft.endCondition === "budget" ? "is-selected" : ""}
            onClick={() => update({ endCondition: "budget" })}
          >
            <span>
              <ProductIcon name="wallet" />
            </span>
            <p>
              <strong>Pot exhaustion only</strong>
              <small>
                No fixed date. The campaign runs until available campaign money
                is exhausted.
              </small>
            </p>
            <i>
              {draft.endCondition === "budget" && <ProductIcon name="check" />}
            </i>
          </button>
        </div>
        {draft.endCondition === "duration" ? (
          <label>
            <span>Campaign duration</span>
            <div>
              <input
                type="number"
                min={1}
                max={90}
                value={draft.days}
                onChange={(event) =>
                  update({ days: Number(event.target.value) })
                }
              />
              <b>days</b>
            </div>
            <small>Choose between 1 and 90 days.</small>
          </label>
        ) : (
          <aside>
            <ProductIcon name="shield" />
            <p>
              <strong>No scheduled end date</strong>
              <small>
                The campaign stops when available campaign money is exhausted.
              </small>
            </p>
          </aside>
        )}
      </fieldset>
      <div className="rule-contract">
        <span>
          <AnimatedNumber value={5} suffix=" days" />
        </span>
        <p>
          <strong>Approved clips enter a five-day review window.</strong>
          <small>Verified results are held before they become payable.</small>
        </p>
      </div>
      <FormActions
        back="/brand/campaigns/new/metrics"
        next="/brand/campaigns/new/budget"
        label="Set budget"
      />
    </BuilderFrame>
  );
}

export function CampaignBudgetScreen() {
  const { draft, update } = useBrandCampaign();
  const creators =
    draft.creatorCap > 0 ? Math.ceil(draft.pot / draft.creatorCap) : 0;
  const campaignFee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return (
    <BuilderFrame
      step={5}
      title="Set the creator pot"
      copy="This balance pays creators across every result you selected."
      artSrc={art.funding}
      artLabel="Campaign budget"
      aside={
        <div className="budget-side-note">
          <ProductIcon name="shield" />
          <span>
            <strong>Funding required</strong>
            <small>The full funding total is shown before payment.</small>
          </span>
        </div>
      }
    >
      <div className="budget-console">
        <div className="budget-inputs">
          <label>
            <span>Total creator pot</span>
            <div>
              <b>₦</b>
              <input
                type="number"
                min={50000}
                step={50000}
                value={draft.pot}
                onChange={(event) =>
                  update({ pot: Number(event.target.value) })
                }
              />
            </div>
          </label>
        </div>
        <div className="metric-rate-recap">
          <header>
            <small>Your performance scorecard</small>
            <strong>{draft.metrics.length} active rates</strong>
          </header>
          {draft.metrics.map((metric) => (
            <div key={metric.type}>
              <span>
                {metric.type === "view"
                  ? "Views"
                  : `${metric.type.charAt(0).toUpperCase()}${metric.type.slice(1)}s`}
              </span>
              <strong>
                <Money value={metric.rate} />
              </strong>
              <small>
                {metric.type === "view"
                  ? "per 1,000 verified views"
                  : "per verified result"}
              </small>
            </div>
          ))}
        </div>
        <div className="budget-guardrails budget-guardrails--fees">
          <div>
            <span>Minimum creator spread</span>
            <strong>
              <AnimatedNumber value={creators} suffix=" creators" />
            </strong>
          </div>
          <div>
            <span>Creator cap</span>
            <strong>
              <Money value={draft.creatorCap} />
            </strong>
          </div>
          <div>
            <span>Clippit fee (15%)</span>
            <strong>
              <Money value={campaignFee} />
            </strong>
          </div>
          <div>
            <span>Total to fund</span>
            <strong>
              <Money value={draft.pot + campaignFee} />
            </strong>
          </div>
        </div>
      </div>
      <FormActions
        back="/brand/campaigns/new/rules"
        next="/brand/campaigns/new/review"
        label="Review campaign"
      />
    </BuilderFrame>
  );
}

export function CampaignReviewScreen() {
  const router = useRouter();
  const { draft } = useBrandCampaign();
  const [confirming, setConfirming] = useState(false);
  const [locked, setLocked] = useState(false);
  const campaignFee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return (
    <>
      <BuilderFrame
        step={6}
        title="Review campaign"
        copy="Check the audience, limits, rules and full funding total."
        artSrc={art.proof}
        artLabel="Ready to fund"
      >
        <div className="campaign-proof-sheet">
          {draft.coverImage && (
            <div className="campaign-proof-cover">
              <Image
                src={draft.coverImage}
                alt={`${draft.title} campaign cover`}
                fill
                unoptimized
                sizes="(max-width: 700px) 100vw, 760px"
              />
            </div>
          )}
          <header>
            <Status tone="gold">Ready to fund</Status>
            <span className="campaign-proof-brand">Your organisation</span>
            <h2>{draft.title}</h2>
            <p>{draft.description}</p>
            <div>
              {draft.platforms.map((platform) => (
                <i key={platform}>{platform}</i>
              ))}
            </div>
          </header>
          <section className="campaign-proof-meta">
            <span>
              <b>
                {draft.accessMode === "public"
                  ? "Public campaign"
                  : "Invite code generated after creation"}
              </b>
              <small>{draft.niche}</small>
            </span>
            <span>
              <b>{draft.maxSubmissions} videos per creator</b>
              <small>
                <Money value={draft.videoCap} /> per-video cap
              </small>
            </span>
            <span>
              <b>
                {draft.endCondition === "budget"
                  ? "Pot exhaustion"
                  : `${draft.days} days or empty pot`}
              </b>
              <small>{draft.assets.length} campaign assets</small>
            </span>
          </section>
          <section className="campaign-proof-totals">
            <div>
              <small>Results measured</small>
              <strong>{String(draft.metrics.length).padStart(2, "0")}</strong>
              <span>
                {draft.metrics.map((metric) => metric.type).join(" · ")}
              </span>
            </div>
            <div>
              <small>Creator pot</small>
              <strong>
                <Money value={draft.pot} />
              </strong>
              <span>shared across verified campaign results</span>
            </div>
            <div>
              <small>Clippit fee</small>
              <strong>
                <Money value={campaignFee} />
              </strong>
              <span>
                {feePercentage(BRAND_CAMPAIGN_FEE_RATE)}% of the creator pot
              </span>
            </div>
            <div>
              <small>Total to fund</small>
              <strong>
                <Money value={draft.pot + campaignFee} />
              </strong>
              <span>Creator pot plus Clippit fee</span>
            </div>
          </section>
          <ol>
            {draft.rules.map((rule, index) => (
              <li
                key={rule.id}
                className={rule.kind === "avoid" ? "is-avoid" : ""}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <ProductIcon
                  name={rule.kind === "avoid" ? "shield" : "check"}
                />
                <p>
                  <small>
                    {rule.kind === "avoid" ? "Must avoid" : "Must do"}
                  </small>
                  <strong>{rule.text}</strong>
                </p>
              </li>
            ))}
          </ol>
        </div>
        <div className="builder-actions">
          <Link href="/brand/campaigns/new/budget">
            <ProductIcon name="chevron" />
            Back
          </Link>
          <button
            type="button"
            className="brand-button"
            onClick={() => setConfirming(true)}
          >
            Continue to funding
            <ProductIcon name="arrow" />
          </button>
        </div>
      </BuilderFrame>
      {confirming && (
        <div
          className="campaign-lock-backdrop"
          role="presentation"
          onMouseDown={() => setConfirming(false)}
        >
          <section
            className="campaign-lock-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="campaign-lock-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <span>
              <ProductIcon name="shield" />
            </span>
            <h2 id="campaign-lock-title">
              Rules and result rates lock after launch.
            </h2>
            <p>
              You can still update allowed campaign details later, but the
              content requirements and selected performance rates cannot be
              changed once this campaign is live. Top-ups add money only.
            </p>
            <label>
              <input
                type="checkbox"
                checked={locked}
                onChange={(event) => setLocked(event.target.checked)}
              />
              <i>
                <ProductIcon name="check" />
              </i>
              <span>I have checked the rules and every performance rate.</span>
            </label>
            <div>
              <button type="button" onClick={() => setConfirming(false)}>
                Review again
              </button>
              <button
                type="button"
                className="brand-button"
                disabled={!locked}
                onClick={() => router.push("/brand/campaigns/new/fund")}
              >
                I understand, continue
                <ProductIcon name="arrow" />
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export function CampaignFundingScreen() {
  const router = useRouter();
  const { draft, draftLoading, draftError, finalize } = useBrandCampaign();
  const [method, setMethod] = useState<"bank" | "card">("bank");
  const [agreed, setAgreed] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState("");
  const fee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!agreed || publishing) return;
    setPublishing(true);
    setPublishError("");
    try {
      const campaign = await finalize();
      window.localStorage.setItem(
        "clippit:last-created-campaign",
        campaign.campaign_slug,
      );
      const order = await campaignsApi.fund(campaign.campaign_slug, method);
      window.sessionStorage.setItem("clippit:last-funding-order", JSON.stringify(order));
      if (order.checkout_url) {
        window.location.assign(order.checkout_url);
        return;
      }
      router.push("/brand/campaigns/new/funded");
    } catch (error) {
      setPublishError(
        errorMessage(
          error,
          "The campaign could not be created. Check the details and try again.",
        ),
      );
      setPublishing(false);
    }
  };
  if (draftLoading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading campaign draft" note="" /></div>;
  if (draftError) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="campaigns" title="Campaign draft unavailable" copy={draftError} role="alert" /></div>;
  return (
    <div className="brand-page funding-page">
      <Link className="brand-back" href="/brand/campaigns/new/review">
        <ProductIcon name="chevron" />
        Back to campaign review
      </Link>
      <PageHeading
        title="Fund the campaign"
        copy="Pay the creator pot and the 15% campaign fee using the secure payment option you choose."
      />
      <div className="funding-layout">
        <form className="funding-checkout" onSubmit={submit}>
          <div className="funding-checkout__title">
            <BrandArt
              src={art.bank}
              label="Wallet funding"
              tone="gold"
              compact
            />
            <div>
              <small>Campaign funding</small>
              <h2>{draft.title}</h2>
              <p>Your organisation</p>
            </div>
          </div>
          <div className="brand-wallet-balance">
            <span>
              <ProductIcon name="wallet" />
            </span>
            <p>
              <small>Total funding order</small>
              <strong>
                <Money value={draft.pot + fee} />
              </strong>
            </p>
            <Status tone="lime">Server checked</Status>
          </div>
          <div className="funding-methods">
            <button
              type="button"
              className={method === "bank" ? "is-selected" : ""}
              onClick={() => setMethod("bank")}
            >
              <ProductIcon name="wallet" />
              <span>
                <strong>Bank payment</strong>
                <small>Use the account details from the payment provider</small>
              </span>
              <i>{method === "bank" && <ProductIcon name="check" />}</i>
            </button>
            <button
              type="button"
              className={method === "card" ? "is-selected" : ""}
              onClick={() => setMethod("card")}
            >
              <ProductIcon name="bank" />
              <span>
                <strong>Card payment</strong>
                <small>Continue to the payment provider's secure checkout</small>
              </span>
              <i>{method === "card" && <ProductIcon name="check" />}</i>
            </button>
          </div>
          {method === "bank" ? (
            <div className="funding-bank">
              <span>
                <ProductIcon name="shield" />
              </span>
              <p>
                <small>Bank funding order</small>
                <strong>Creator pot + campaign fee</strong>
                <b>
                  <Money value={draft.pot + fee} />
                </b>
                <em>Payment details are generated after you continue.</em>
              </p>
            </div>
          ) : (
            <div className="funding-bank">
              <span>
                <ProductIcon name="bank" />
              </span>
              <p>
                <small>Card checkout</small>
                <strong>Secure provider payment</strong>
                <b>
                  <Money value={draft.pot + fee} />
                </b>
                <em>You will return here after payment is confirmed.</em>
              </p>
            </div>
          )}
          <label className="funding-agreement">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <i>
              <ProductIcon name="check" />
            </i>
            <span>
              I approve the creator pot and the non-refundable 15% Clippit
              campaign fee shown in this order.
            </span>
          </label>
          {publishError ? (
            <p className="campaign-publish-error" role="alert">
              {publishError}
            </p>
          ) : null}
          <button
            type="submit"
            className="brand-button"
            disabled={!agreed || publishing}
          >
            {publishing
              ? "Creating campaign…"
              : "Create funding order"}
            <ProductIcon name="arrow" />
          </button>
        </form>
        <aside className="funding-receipt">
          <ReceiptHeader
            title="Campaign funding order"
            reference="Created after you continue"
          />
          <div className="funding-receipt__campaign">
            <span>
              {draft.coverImage ? (
                <Image
                  src={draft.coverImage}
                  alt=""
                  fill
                  unoptimized
                  sizes="76px"
                />
              ) : (
                <Image src={art.funding} alt="" fill sizes="76px" />
              )}
            </span>
            <p>
              <small>Campaign</small>
              <strong>{draft.title}</strong>
              <em>Your organisation</em>
            </p>
          </div>
          <div className="funding-receipt__parties">
            <section>
              <h2>Reserved for</h2>
              <p>
                <strong>Clippit campaign pot</strong>
                <span>Creator earnings only</span>
              </p>
            </section>
            <section>
              <h2>From</h2>
              <p>
                <strong>Your organisation</strong>
                <span>{method === "bank" ? "Bank payment" : "Card payment"}</span>
              </p>
            </section>
          </div>
          <dl>
            <div>
              <dt>Funding ID</dt>
              <dd>Assigned by the server</dd>
            </div>
            <div>
              <dt>Wallet ledger reference</dt>
              <dd>Created after payment</dd>
            </div>
            <div>
              <dt>Creator pot</dt>
              <dd>
                <Money value={draft.pot} />
              </dd>
            </div>
            <div>
              <dt>Clippit campaign fee (15%)</dt>
              <dd>
                <Money value={fee} />
              </dd>
            </div>
            <div>
              <dt>Campaign end</dt>
              <dd>
                {draft.endCondition === "budget"
                  ? "When the pot is empty"
                  : `${draft.days} days or an empty pot`}
              </dd>
            </div>
          </dl>
          <p className="funding-receipt__total">
            <span>Total payment</span>
            <strong>
              <Money value={draft.pot + fee} />
            </strong>
          </p>
          <ul>
            <li>
              <ProductIcon name="shield" />
              Creator pot becomes reserved
            </li>
            <li>
              <ProductIcon name="eye" />
              Only the selected verified results draw from the pot
            </li>
            <li>
              <ProductIcon name="bank" />
              Eligible unused money returns to the Brand wallet
            </li>
          </ul>
        </aside>
      </div>
    </div>
  );
}

export function CampaignFundedScreen() {
  const { draft } = useBrandCampaign();
  const fee = calculateFee(draft.pot, BRAND_CAMPAIGN_FEE_RATE);
  return (
    <div className="brand-page funded-page">
      <section className="funded-hero">
        <div className="funded-art">
          {draft.coverImage ? (
            <div className="funded-cover">
              <Image
                src={draft.coverImage}
                alt={`${draft.title} campaign cover`}
                fill
                unoptimized
                sizes="420px"
              />
            </div>
          ) : (
            <BrandArt src={art.funding} label="Pot received" tone="lime" />
          )}
          <span>
            <ProductIcon name="check" />
          </span>
        </div>
        <Status>Funds confirmed</Status>
        <h1>Campaign funded.</h1>
        <p>{draft.title} is live. Creators can now join and submit clips.</p>
        <div>
          <ActionLink href="/brand/campaigns/no-long-thing">
            View campaign
          </ActionLink>
          <ActionLink href="/brand/campaigns" dark>
            Back to campaigns
          </ActionLink>
        </div>
      </section>
      <aside className="funded-ticket">
        <ReceiptHeader
          title="Campaign funding certificate"
          reference="CLP-LIVE-041"
        />
        <div className="funded-ticket__campaign">
          <span>
            {draft.coverImage ? (
              <Image
                src={draft.coverImage}
                alt=""
                fill
                unoptimized
                sizes="84px"
              />
            ) : (
              <Image src={art.funding} alt="" fill sizes="84px" />
            )}
          </span>
          <p>
            <small>Funded campaign</small>
            <strong>{draft.title}</strong>
            <em>Gbedu Records</em>
          </p>
          <i>
            <ProductIcon name="check" />
            Live
          </i>
        </div>
        <div className="funded-ticket__amount">
          <small>Total paid</small>
          <h2>
            <Money value={draft.pot + fee} />
          </h2>
          <time>20 Sep 2026 · 15:07:13 WAT</time>
        </div>
        <div className="funded-ticket__parties">
          <section>
            <h2>Reserved for</h2>
            <p>
              <strong>Clippit campaign pot</strong>
              <span>Creator earnings</span>
            </p>
          </section>
          <section>
            <h2>From</h2>
            <p>
              <strong>Gbedu Records Ltd.</strong>
              <span>Brand wallet</span>
            </p>
          </section>
        </div>
        <section className="funded-ticket__information">
          <h2>Transaction information</h2>
          <dl>
            <div>
              <dt>Funding transaction ID</dt>
              <dd>CLP-LIVE-041</dd>
            </div>
            <div>
              <dt>Wallet ledger reference</dt>
              <dd>LDG-260920-041</dd>
            </div>
            <div>
              <dt>Creator pot</dt>
              <dd>
                <Money value={draft.pot} />
              </dd>
            </div>
            <div>
              <dt>Clippit campaign fee (15%)</dt>
              <dd>
                <Money value={fee} />
              </dd>
            </div>
            <div>
              <dt>Performance rates</dt>
              <dd>{draft.metrics.length} selected</dd>
            </div>
            <div>
              <dt>Campaign end</dt>
              <dd>
                {draft.endCondition === "budget"
                  ? "When the pot is empty"
                  : `${draft.days} days or an empty pot`}
              </dd>
            </div>
          </dl>
        </section>
        <footer>
          <ProductIcon name="shield" />
          <span>
            <strong>Verify this certificate</strong>
            <small>clippit.ng/verify/CLP-LIVE-041 · Code C04A-7719</small>
          </span>
        </footer>
      </aside>
    </div>
  );
}

const EMPTY_LIVE_CAMPAIGN: BrandCampaign = {
  slug: "",
  title: "",
  line: "",
  state: "Draft",
  image: "/assets/illustrations/clippit-icons/campaign-brief.webp",
  pot: 0,
  remaining: 0,
  rate: 0,
  verifiedViews: 0,
  submissions: 0,
  approved: 0,
  review: 0,
  daysLeft: 0,
  endCondition: "budget",
};

export function LiveCampaignScreen({ slug }: { slug?: string }) {
  const [campaign, setCampaign] = useState(EMPTY_LIVE_CAMPAIGN);
  const [brandName, setBrandName] = useState("");
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [campaignMetrics, setCampaignMetrics] = useState<
    CampaignOut["performance_metrics"]
  >([]);
  const [submissions, setSubmissions] = useState<CampaignSubmissionRow[]>([]);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [controlBusy, setControlBusy] = useState(false);
  const [pauseMode, setPauseMode] = useState<"entries" | "full">("entries");
  const [control, setControl] = useState<"pause" | null>(null);
  const [integrationSecret, setIntegrationSecret] = useState("");
  const [integrationBusy, setIntegrationBusy] = useState(false);
  const [integrationError, setIntegrationError] = useState("");
  const [integrationCopied, setIntegrationCopied] = useState(false);

  useEffect(() => {
    if (!slug) { setLoading(false); setLoadError("Campaign reference is missing."); return; }
    Promise.all([campaignsApi.get(slug), campaignsApi.getStats(slug), campaignsApi.getSubmissions(slug)])
      .then(([data, statsData, submissionData]) => {
        setBrandName(data.brand?.name ?? "Brand");
        setPaused(!data.accepting_entries);
        setCampaignMetrics(
          data.performance_metrics?.length
            ? data.performance_metrics
            : [
                {
                  metric_type: "view",
                  rate_amount: data.payout_rule?.rate_per_1000_views ?? 0,
                  unit_size: 1000,
                  min_threshold: data.payout_rule?.min_views_threshold ?? 1000,
                },
              ],
        );
        setCampaign({
          ...campaignOutToBrand(data),
          title: data.title,
          line: data.tagline ?? data.description.slice(0, 120),
          image: data.cover_image_url ?? EMPTY_LIVE_CAMPAIGN.image,
          rate: data.payout_rule?.rate_per_1000_views ?? 0,
          pot: data.pot,
          remaining: data.remaining,
          daysLeft: data.time_left?.days ?? 0,
          endCondition: data.time_left ? "duration" : "budget",
        });
        setStats(statsData);
        setSubmissions(submissionData);
      })
      .catch((err) => setLoadError(errorMessage(err, "We couldn't load this campaign.")))
      .finally(() => setLoading(false));
  }, [slug]);

  const verifiedViews = stats?.verified_views ?? campaign.verifiedViews;
  const viewsLast24h = stats?.views_last_24h ?? 0;
  const submissionCount = stats?.submissions ?? campaign.submissions;
  const approvedCount = stats?.approved ?? campaign.approved;
  const reviewCount = stats?.review ?? campaign.review;
  const checkingCount = stats?.checking ?? 0;
  const lastReading = stats?.last_reading_at
    ? new Date(stats.last_reading_at).toLocaleTimeString("en-NG", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "No platform reading yet";
  const primaryMetric = campaignMetrics[0]?.metric_type ?? "view";
  const tracksConversions = campaignMetrics.some((metric) =>
    ["visit", "signup", "lead", "purchase"].includes(metric.metric_type),
  );

  const createIntegrationKey = async () => {
    if (!slug || integrationBusy) return;
    setIntegrationBusy(true);
    setIntegrationError("");
    try {
      const result = await campaignsApi.rotateIntegrationSecret(slug);
      setIntegrationSecret(result.secret);
      setIntegrationCopied(false);
    } catch (error) {
      setIntegrationError(
        errorMessage(error, "The setup key could not be created. Try again."),
      );
    } finally {
      setIntegrationBusy(false);
    }
  };

  const copyIntegrationKey = async () => {
    if (!integrationSecret) return;
    await navigator.clipboard?.writeText(integrationSecret);
    setIntegrationCopied(true);
  };

  const resumeCampaign = async () => {
    if (!slug || controlBusy) return;
    setControlBusy(true);
    setLoadError("");
    try {
      const updated = await campaignsApi.resume(slug);
      setPaused(!updated.accepting_entries);
    } catch (error) {
      setLoadError(errorMessage(error, "The campaign could not be resumed."));
    } finally {
      setControlBusy(false);
    }
  };

  const pauseCampaign = async () => {
    if (!slug || controlBusy) return;
    setControlBusy(true);
    setLoadError("");
    try {
      const updated = await campaignsApi.pause(slug, pauseMode === "full" ? "full" : "acquisition");
      setPaused(!updated.accepting_entries);
      setControl(null);
    } catch (error) {
      setLoadError(errorMessage(error, "The campaign could not be paused."));
    } finally {
      setControlBusy(false);
    }
  };

  const submissionStateTone = (state: string) =>
    state === "Earning" ? "lime" : state === "Review" ? "gold" : "paper";

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading campaign activity" /></div>;
  if (loadError && !campaign.slug) return <div className="brand-page"><ClippitEmptyState tone="danger" icon="campaigns" title="Campaign unavailable" copy={loadError} role="alert" /></div>;

  return (
    <div className="brand-page live-campaign-page">
      <header className="live-campaign-head">
        <div>
          <Status tone={paused ? "gold" : "lime"}>
            {paused
              ? pauseMode === "full"
                ? "Fully paused"
                : "Entries paused"
              : "Live now"}
          </Status>
          <p>{brandName}</p>
          <h1>{campaign.title}</h1>
          <span>{campaign.line}</span>
        </div>
        <div>
          <button
            type="button"
            onClick={() => (paused ? void resumeCampaign() : setControl("pause"))}
            disabled={controlBusy}
          >
            {paused ? "Resume campaign" : "Pause campaign"}
          </button>
          <Link href={`/brand/campaigns/${slug ?? "live"}/refund`}>
            End campaign
          </Link>
        </div>
      </header>
      {loadError && <p className="auth-error" role="alert">{loadError}</p>}
      {paused && (
        <section className="campaign-pause-banner">
          <ProductIcon name="pause" />
          <p>
            <strong>
              {pauseMode === "full"
                ? "Everything is paused"
                : "New entries are paused"}
            </strong>
            <small>
              {pauseMode === "full"
                ? "No new entries or future view earnings are being added."
                : "Existing approved clips can keep earning while new creators cannot join."}
            </small>
          </p>
          <button type="button" onClick={() => void resumeCampaign()} disabled={controlBusy}>
            Resume
          </button>
        </section>
      )}
      <section className="live-money-room">
        <div className="live-money-room__visual">
          <Image
            src={campaign.image}
            alt=""
            fill
            sizes="(max-width: 900px) 100vw, 48vw"
            priority
          />
          <div>
            <span>
              {campaignMetrics.length === 1 ? "Live rate" : "Performance rates"}
            </span>
            <strong>
              {campaignMetrics.length === 1 ? (
                <Money value={campaignMetrics[0].rate_amount} />
              ) : (
                <AnimatedNumber value={campaignMetrics.length} padStart={2} />
              )}
            </strong>
            <small>
              {campaignMetrics.length === 1
                ? `per ${campaignMetrics[0].unit_size.toLocaleString()} ${campaignMetrics[0].metric_type}${campaignMetrics[0].unit_size === 1 ? "" : "s"}`
                : "selected results"}
            </small>
          </div>
        </div>
        <div className="live-money-room__pot">
          <BrandArt
            src={art.funding}
            label="Campaign pot"
            tone="gold"
            compact
          />
          <p>Money still in the pot</p>
          <strong>
            <Money value={campaign.remaining} />
          </strong>
          <PotBar campaign={campaign} />
          <dl>
            <div>
              <dt>Started with</dt>
              <dd>
                <Money value={campaign.pot} />
              </dd>
            </div>
            <div>
              <dt>Earned by creators</dt>
              <dd>
                <Money value={campaign.pot - campaign.remaining} />
              </dd>
            </div>
            <div>
              <dt>Campaign closes</dt>
              <dd>
                {campaign.endCondition === "budget" ? (
                  "When pot is empty"
                ) : (
                  <AnimatedNumber value={campaign.daysLeft} suffix="d" />
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>
      <section className="live-performance-strip">
        <header>
          <div>
            <small>Campaign scorecard</small>
            <h2>Results being measured</h2>
          </div>
          <span>
            <ProductIcon name="shield" />
            Verified only
          </span>
        </header>
        <div>
          {campaignMetrics.map((metric, index) => (
            <article key={metric.metric_type}>
              <i>{String(index + 1).padStart(2, "0")}</i>
              <p>
                <small>{metric.metric_type}</small>
                <strong>
                  <AnimatedNumber
                    value={stats?.performance?.[metric.metric_type] ?? 0}
                    format="compact"
                  />
                </strong>
                <span>verified so far</span>
              </p>
              <b>
                <Money value={metric.rate_amount} />
                <small>
                  {metric.unit_size === 1
                    ? "each"
                    : `per ${metric.unit_size.toLocaleString()}`}
                </small>
              </b>
            </article>
          ))}
        </div>
      </section>
      {tracksConversions ? (
        <section className="campaign-integration-card">
          <div className="campaign-integration-card__mark">
            <ProductIcon name="link" />
          </div>
          <div className="campaign-integration-card__copy">
            <small>Store connection</small>
            <h2>Connect confirmed customer actions</h2>
            <p>
              Create a one-time setup key and give it to whoever manages your
              website or store. It lets your store confirm signups, leads and
              purchases against the right creator link.
            </p>
            {integrationError ? (
              <span className="campaign-integration-card__error">
                {integrationError}
              </span>
            ) : null}
          </div>
          <div className="campaign-integration-card__action">
            {integrationSecret ? (
              <div className="campaign-integration-card__secret">
                <span>Copy now. It will not be shown again.</span>
                <code>{integrationSecret}</code>
                <button type="button" onClick={copyIntegrationKey}>
                  <ProductIcon name={integrationCopied ? "check" : "link"} />
                  {integrationCopied ? "Copied" : "Copy setup key"}
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="brand-button"
                onClick={createIntegrationKey}
                disabled={!slug || integrationBusy}
              >
                {integrationBusy ? "Creating key..." : "Create setup key"}
                <ProductIcon name="arrow" />
              </button>
            )}
          </div>
        </section>
      ) : null}
      <section className="live-signal-grid">
        <article>
          <small>Verified views</small>
          <strong>
            <AnimatedNumber value={verifiedViews} format="compact" />
          </strong>
          <div className="brand-sparkline">
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <p>
            <b>
              +
              {viewsLast24h >= 1000
                ? `${(viewsLast24h / 1000).toFixed(1)}K`
                : viewsLast24h}
            </b>{" "}
            since yesterday
          </p>
        </article>
        <article>
          <small>Submission flow</small>
          <strong>
            <AnimatedNumber value={submissionCount} />
          </strong>
          <div className="submission-pipeline">
            <span>
              <b>{approvedCount}</b> earning
            </span>
            <i />
            <span>
              <b>{reviewCount}</b> need review
            </span>
            <i />
            <span>
              <b>{checkingCount}</b> checking
            </span>
          </div>
          <Link href="/brand/reviews">
            Open review queue
            <ProductIcon name="arrow" />
          </Link>
        </article>
        <article className="live-proof-card">
          <BrandArt src={art.proof} label="Views proven" tone="lime" compact />
          <p>
            <small>Last view update</small>
            <strong>{lastReading}</strong>
            <span>
              Official views are up to date across the selected platforms.
            </span>
          </p>
        </article>
      </section>
      <section className="brand-activity-sheet">
        <header>
          <div>
            <h2>Recent submissions</h2>
            <p>Latest view and earning status for each submission.</p>
          </div>
          <Link
            href={`/brand/campaigns/${slug ?? "live"}/report`}
            className="brand-button brand-button--small"
          >
            Export report
            <ProductIcon name="arrow" />
          </Link>
        </header>
        <div className="brand-activity-sheet__labels">
          <span>Creator</span>
          <span>Clip</span>
          <span>
            Verified {primaryMetric}
            {primaryMetric.endsWith("s") ? "" : "s"}
          </span>
          <span>Earned</span>
          <span>State</span>
        </div>
        {!submissions.length && <ClippitEmptyState className="brand-activity-empty" size="inline" tone="gold" icon="play" title="No submissions yet" copy="Creator submissions will appear here after they join and post." />}
        {submissions.map((row) => (
          <article key={row.id}>
            <span className="brand-activity-creator">
              <i>
                {(row.creator_handle ?? row.creator_name)
                  .slice(0, 2)
                  .toUpperCase()}
              </i>
              <p>
                <strong>{row.creator_name}</strong>
                <small>@{row.creator_handle ?? row.creator_name}</small>
              </p>
            </span>
            <strong>{row.title ?? "Untitled clip"}</strong>
            <b>
              <AnimatedNumber
                value={row.performance?.[primaryMetric] ?? row.verified_views}
                format="compact"
              />
            </b>
            <b>
              <Money value={row.earned} />
            </b>
            <Status tone={submissionStateTone(row.state)}>{row.state}</Status>
          </article>
        ))}
      </section>
      {control === "pause" && (
        <div
          className="campaign-lock-backdrop"
          onMouseDown={() => setControl(null)}
        >
          <section
            className="campaign-lock-modal campaign-control-modal"
            role="dialog"
            aria-modal="true"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <span>
              <ProductIcon name="pause" />
            </span>
            <h2>How should this campaign pause?</h2>
            <p>Choose what happens to new entries and approved clips.</p>
            <div className="pause-mode-grid">
              <button
                type="button"
                className={pauseMode === "entries" ? "is-selected" : ""}
                onClick={() => setPauseMode("entries")}
              >
                <strong>Pause new entries</strong>
                <small>
                  Creators cannot join or submit. Approved clips keep earning.
                </small>
              </button>
              <button
                type="button"
                className={pauseMode === "full" ? "is-selected" : ""}
                onClick={() => setPauseMode("full")}
              >
                <strong>Pause everything</strong>
                <small>
                  Stops entries and future view earnings until you resume.
                </small>
              </button>
            </div>
            <div>
              <button type="button" onClick={() => setControl(null)}>
                Keep running
              </button>
              <button
                type="button"
                className="brand-button"
                onClick={() => void pauseCampaign()}
                disabled={controlBusy}
              >
                Confirm pause
                <ProductIcon name="pause" />
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function ReviewCard({ review }: { review: BrandReview }) {
  return (
    <Link href={`/brand/reviews/${review.id}`} className="review-card">
      <div className="review-card__image">
        <Image
          src={review.image}
          alt=""
          fill
          sizes="(max-width: 700px) 100vw, 280px"
        />
        <span>
          <ProductIcon name="play" />
        </span>
        <b>{review.platform}</b>
      </div>
      <div className="review-card__body">
        <div>
          <Status tone="gold">Needs review</Status>
          <small>{review.submitted}</small>
        </div>
        <h2>{review.title}</h2>
        <p>
          {review.creator} <span>{review.handle}</span>
        </p>
        <blockquote>{review.issue}</blockquote>
        <div className="review-card__decision">
          <span>Decision needed</span>
          <strong>Open clip</strong>
          <i>
            <b style={{ width: "100%" }} />
          </i>
        </div>
      </div>
      <ProductIcon name="arrow" />
    </Link>
  );
}

const tabMap: Record<string, "needs_review" | "appeals" | "resolved"> = {
  "Needs review": "needs_review",
  Appeals: "appeals",
  Resolved: "resolved",
};

function apiReviewToBrand(r: ApiReviewCard): BrandReview {
  const validPlatforms = [
    "TikTok",
    "Instagram",
    "Facebook",
    "X",
    "YouTube",
  ] as const;
  const platform =
    validPlatforms.find((p) => p.toLowerCase() === r.platform.toLowerCase()) ??
    "TikTok";
  return {
    id: r.id,
    title: r.title ?? r.campaign_title,
    creator: r.creator_name,
    handle: r.creator_handle ? `@${r.creator_handle.replace(/^@/, "")}` : "",
    platform,
    image: r.video_url ?? "/assets/video/creator-reaction-poster.jpg",
    submitted: new Date(r.submitted_at).toLocaleDateString("en-NG", {
      day: "numeric",
      month: "short",
    }),
    issue: r.issue ?? "Please review this submission.",
    confidence: Math.round((r.confidence ?? 0.75) * 100),
  };
}

export function BrandReviewQueueScreen() {
  const [filter, setFilter] = useState("Needs review");
  const [reviews, setReviews] = useState<BrandReview[]>([]);
  const [counts, setCounts] = useState({
    needs_review: 0,
    appeals: 0,
    resolved: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    const tab = tabMap[filter] ?? "needs_review";
    brandApi
      .reviews(tab)
      .then((data) => {
        setCounts(data.counts);
        setReviews(data.items.map(apiReviewToBrand));
      })
      .catch((err) => setError(errorMessage(err, "We couldn't load the review queue.")))
      .finally(() => setLoading(false));
  }, [filter]);

  const needsCount = counts.needs_review;
  return (
    <div className="brand-page review-queue-page">
      <PageHeading
        title={`${needsCount} submission${needsCount !== 1 ? "s" : ""} need review.`}
        copy="Approve a submission or request a correction. These clips are not earning yet."
        action={
          <div className="review-count">
            <AnimatedNumber value={needsCount} padStart={2} />
            <span>
              waiting
              <br />
              for review
            </span>
          </div>
        }
      />
      <div className="brand-filter-row">
        {["Needs review", "Appeals", "Resolved"].map((item) => (
          <button
            type="button"
            key={item}
            onClick={() => setFilter(item)}
            className={filter === item ? "is-active" : ""}
          >
            {item}
            {item === "Needs review" && <b>{needsCount}</b>}
          </button>
        ))}
      </div>
      {loading ? (
        <ClippitLoader
          contained
          compact
          tone="gold"
          label="Opening the review queue"
          note="Bringing in the latest submissions and decisions."
        />
      ) : error ? (
        <ClippitEmptyState className="review-empty" tone="danger" icon="eye" title="We couldn't load reviews" copy={error} role="alert" />
      ) : reviews.length ? (
        <section className="review-list">
          {reviews.map((review) => (
            <ReviewCard review={review} key={review.id} />
          ))}
        </section>
      ) : (
        <ClippitEmptyState
          className="review-empty"
          tone="gold"
          icon={
            filter === "Appeals"
              ? "shield"
              : filter === "Needs review"
                ? "eye"
                : "check"
          }
          artSrc={filter === "Appeals" ? art.review : art.proof}
          title={
            filter === "Appeals"
              ? "No appeals waiting"
              : filter === "Needs review"
                ? "Review queue cleared"
                : "No resolved submissions yet"
          }
          copy={
            filter === "Appeals"
              ? "Appeals will arrive here with the original verdict and evidence."
              : filter === "Needs review"
                ? "New creator submissions will appear here when they are ready for your decision."
                : "Completed review decisions will appear here."
          }
        />
      )}
    </div>
  );
}

export function BrandReviewDetailScreen({
  id = "submission-1042",
}: {
  id?: string;
}) {
  const mockReview =
    brandReviews.find((item) => item.id === id) ?? brandReviews[0];
  const [review, setReview] = useState<BrandReview>(mockReview);
  const [decision, setDecision] = useState<"approve" | "changes" | null>(null);
  const [acting, setActing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeAction, setActiveAction] = useState<
    "approve" | "changes" | null
  >(null);

  useEffect(() => {
    brandApi
      .getReview(id)
      .then((data) => {
        setReview((current) => ({
          ...current,
          creator: data.creator_name,
          handle: data.creator_handle ?? current.handle,
          title: data.title ?? current.title,
          platform:
            (data.platform as BrandReview["platform"]) ?? current.platform,
          confidence: data.confidence ?? current.confidence,
          issue: data.issue ?? current.issue,
        }));
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [id]);

  const approve = async () => {
    setActing(true);
    setActiveAction("approve");
    brandApi
      .approveReview(id)
      .catch(() => undefined)
      .finally(() => setActing(false));
    setDecision("approve");
  };

  const requestCorrection = async () => {
    setActing(true);
    setActiveAction("changes");
    brandApi
      .requestCorrection(id, review.issue ?? "Please review this submission.")
      .catch(() => undefined)
      .finally(() => setActing(false));
    setDecision("changes");
  };

  if (loading || acting)
    return (
      <div className="brand-page">
        <ClippitLoader
          contained
          tone="gold"
          label={
            loading
              ? "Preparing the submission"
              : activeAction === "approve"
                ? "Approving this clip"
                : "Saving your correction request"
          }
          note={
            loading
              ? "Loading the clip, evidence and campaign requirements."
              : "Recording your decision and updating the creator."
          }
        />
      </div>
    );

  if (decision)
    return (
      <div className="brand-page review-resolved">
        <BrandArt
          src={decision === "approve" ? art.proof : art.review}
          label={decision === "approve" ? "Approved" : "Correction requested"}
          tone={decision === "approve" ? "lime" : "gold"}
        />
        <Status tone={decision === "approve" ? "lime" : "gold"}>
          {decision === "approve" ? "Approved" : "Changes requested"}
        </Status>
        <h1>
          {decision === "approve" ? "Clip approved." : "Correction requested."}
        </h1>
        <p>
          {decision === "approve"
            ? "New verified views can now earn from the No long thing campaign."
            : "The creator received the failed requirement and can submit a corrected post."}
        </p>
        <ActionLink href="/brand/reviews">Review the next clip</ActionLink>
      </div>
    );
  return (
    <div className="brand-page review-detail-page">
      <Link className="brand-back" href="/brand/reviews">
        <ProductIcon name="chevron" />
        Back to review queue
      </Link>
      <header>
        <div>
          <Status tone="gold">Needs review</Status>
          <h1>{review.title}</h1>
          <p>
            {review.creator} <span>{review.handle}</span> · {review.platform}
          </p>
        </div>
        <div className="confidence-ticket">
          <span>Your decision</span>
          <strong>Review</strong>
          <small>One campaign requirement needs a closer look.</small>
        </div>
      </header>
      <div className="review-detail-grid">
        <section className="submission-player">
          <div>
            <Image
              src={review.image}
              alt="Submission preview"
              fill
              sizes="(max-width: 900px) 100vw, 50vw"
            />
            <button type="button" aria-label="Play submission">
              <ProductIcon name="play" />
            </button>
            <span>00:24</span>
          </div>
          <p>
            <span>
              <i>KM</i>
              <strong>{review.creator}</strong>
              <small>Connected {review.platform} account</small>
            </span>
            <a href="#public-post">
              Open public post
              <ProductIcon name="link" />
            </a>
          </p>
        </section>
        <aside className="review-evidence">
          <BrandArt src={art.review} label="Review point" tone="gold" compact />
          <div>
            <small>Flagged requirement</small>
            <h2>{review.issue}</h2>
            <p>
              The product appears between 00:11 and 00:13. The pack is visible,
              but another object covers part of the brand mark.
            </p>
          </div>
        </aside>
      </div>
      <section className="decision-sheet">
        <header>
          <div>
            <h2>Requirements</h2>
            <p>Check each requirement before deciding.</p>
          </div>
          <Status tone="paper">4 requirements</Status>
        </header>
        <ol>
          <li className="is-pass">
            <span>
              <ProductIcon name="check" />
            </span>
            <p>
              <strong>Show the prepared noodles clearly on screen.</strong>
              <small>Found at 00:08 and 00:19</small>
            </p>
            <b>Pass</b>
          </li>
          <li className="is-review">
            <span>
              <ProductIcon name="eye" />
            </span>
            <p>
              <strong>Show the product pack clearly on screen.</strong>
              <small>
                Partly visible at 00:11. Brand mark may be obscured.
              </small>
            </p>
            <b>Review</b>
          </li>
          <li className="is-pass">
            <span>
              <ProductIcon name="check" />
            </span>
            <p>
              <strong>Say or display: No long thing.</strong>
              <small>Transcript match at 00:17</small>
            </p>
            <b>Pass</b>
          </li>
          <li className="is-pass">
            <span>
              <ProductIcon name="check" />
            </span>
            <p>
              <strong>Tag @indomie_nigeria and use #NoLongThing.</strong>
              <small>Both found in the public caption</small>
            </p>
            <b>Pass</b>
          </li>
        </ol>
        <div className="decision-actions">
          <button
            type="button"
            className="brand-button brand-button--dark"
            disabled={acting}
            onClick={requestCorrection}
          >
            Request a correction
            <ProductIcon name="arrow" />
          </button>
          <button
            type="button"
            className="brand-button"
            disabled={acting}
            onClick={approve}
          >
            Approve this clip
            <ProductIcon name="check" />
          </button>
        </div>
      </section>
    </div>
  );
}

export function BrandSettingsScreen() {
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [notices, setNotices] = useState({
    funding: true,
    reviews: true,
    reports: false,
  });
  const [profile, setProfile] = useState(BRAND_PROFILE_FALLBACK);
  const [website, setWebsite] = useState("");
  const [financeEmail, setFinanceEmail] = useState("");
  const [verified, setVerified] = useState(false);
  const [orgName, setOrgName] = useState("");

  useEffect(() => {
    Promise.all([organisationsApi.getProfile(), profileApi.getPreferences()])
      .then(([data, preferences]) => {
        setProfile((current) => ({
          ...current,
          name: data.name,
          bio: data.bio ?? "",
          photo: data.photo_url ?? "",
        }));
        setWebsite(data.website ?? "");
        setFinanceEmail(data.finance_email ?? "");
        setOrgName(data.business_legal_name ?? data.name);
        setVerified(data.business_verified);
        setNotices({
          funding: preferences.notifications.funding_alerts,
          reviews: preferences.notifications.review_alerts,
          reports: preferences.notifications.weekly_report,
        });
      })
      .catch((error) => setSettingsError(errorMessage(error, "We couldn't load your organisation settings.")))
      .finally(() => setLoading(false));
  }, []);

  const toggleNotice = (key: "funding" | "reviews" | "reports") => {
    const apiKey =
      key === "funding"
        ? "funding_alerts"
        : key === "reviews"
          ? "review_alerts"
          : "weekly_report";
    const previous = notices;
    const updated = { ...notices, [key]: !notices[key] };
    setNotices(updated);
    setSettingsError("");
    profileApi
      .updatePreferences({ notifications: { [apiKey]: updated[key] } })
      .catch((error) => {
        setNotices(previous);
        setSettingsError(errorMessage(error, "That notification setting could not be saved."));
      });
  };

  const saveIdentity = async () => {
    const clean = {
      ...profile,
      name: profile.name.trim(),
      bio: profile.bio.trim(),
    };
    setSaving(true);
    setSettingsError("");
    try {
      const photoUpload = clean.photo.startsWith("data:")
        ? await uploadsApi.imageFromDataUrl(clean.photo)
        : null;
      const updated = await organisationsApi.updateProfile({
        name: clean.name,
        bio: clean.bio,
        website: website || undefined,
        finance_email: financeEmail || undefined,
        ...(photoUpload ? { photo_upload_id: photoUpload.id } : {}),
      });
      const persisted = {
        name: updated.name,
        bio: updated.bio ?? "",
        photo: updated.photo_url ?? "",
      };
      setProfile(persisted);
      setOrgName(updated.business_legal_name ?? updated.name);
      saveStoredProfile("brand", persisted);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1800);
    } catch (error) {
      setSettingsError(errorMessage(error, "Your organisation details could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading settings" note="" /></div>;

  return (
    <div className="brand-page brand-settings-page">
      <PageHeading
        title="Settings"
        copy="Manage organisation details, funding contact and campaign alerts."
      />
      {settingsError ? <p className="campaign-publish-error" role="alert">{settingsError}</p> : null}
      <div className="brand-settings-layout">
        <nav>
          <a href="#identity">Organisation identity</a>
          <a href="#funding">Funding contact</a>
          <a href="#alerts">Campaign alerts</a>
        </nav>
        <div>
          <section id="identity" className="brand-settings-sheet">
            <header>
              <div>
                <h2>Organisation identity</h2>
                <p>Shown to creators on your campaigns.</p>
              </div>
              <ProfileAvatar
                profile={profile}
                fallback="GR"
                className="brand-settings-avatar"
              />
            </header>
            <div className="brand-profile-editor">
              <ProfilePhotoPicker
                value={profile.photo}
                name={profile.name}
                onChange={(photo) =>
                  setProfile((current) => ({ ...current, photo }))
                }
                tone="gold"
                compact
              />
              <div className="brand-profile-fields">
                <label>
                  <span>Public organisation name</span>
                  <input
                    value={profile.name}
                    onChange={(event) =>
                      setProfile((current) => ({
                        ...current,
                        name: event.target.value.slice(0, 60),
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Short description</span>
                  <textarea
                    value={profile.bio}
                    onChange={(event) =>
                      setProfile((current) => ({
                        ...current,
                        bio: event.target.value.slice(0, 240),
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Website</span>
                  <input
                    value={website}
                    onChange={(event) => setWebsite(event.target.value)}
                  />
                </label>
              </div>
            </div>
            <button
              type="button"
              className="brand-button"
              disabled={
                profile.name.trim().length < 2 || profile.bio.trim().length < 2
              }
              onClick={saveIdentity}
            >
              {saving ? "Saving..." : saved ? "Changes saved" : "Save identity"}
              <ProductIcon name={saved ? "check" : "arrow"} />
            </button>
          </section>
          <section id="funding" className="brand-settings-sheet">
            <header>
              <div>
                <h2>Funding contact</h2>
                <p>
                  Used for receipts, settlement questions and campaign closeout.
                </p>
              </div>
              <ProductIcon name="bank" />
            </header>
            <label>
              <span>Finance email</span>
              <input
                type="email"
                value={financeEmail}
                onChange={(event) => setFinanceEmail(event.target.value)}
              />
            </label>
            <div className="verified-funder">
              <ProductIcon name="shield" />
              <span>
                <strong>{orgName}</strong>
                <small>
                  Business identity {verified ? "verified" : "pending"}
                </small>
              </span>
              <Status tone={verified ? "lime" : "gold"}>
                {verified ? "Verified" : "Pending"}
              </Status>
            </div>
          </section>
          <section id="alerts" className="brand-settings-sheet">
            <header>
              <div>
                <h2>Campaign alerts</h2>
                <p>Choose which campaign events send an alert.</p>
              </div>
              <ProductIcon name="bell" />
            </header>
            {Object.entries(notices).map(([key, value]) => (
              <label className="brand-toggle" key={key}>
                <span>
                  <strong>
                    {key === "funding"
                      ? "Funding and pot alerts"
                      : key === "reviews"
                        ? "Submission review alerts"
                        : "Weekly performance report"}
                  </strong>
                  <small>
                    {key === "funding"
                      ? "Cleared funds, low pot and campaign closeout"
                      : key === "reviews"
                        ? "Uncertain checks and creator appeals"
                        : "Verified views and spend summary every Monday"}
                  </small>
                </span>
                <input
                  type="checkbox"
                  checked={value}
                  onChange={() =>
                    toggleNotice(key as "funding" | "reviews" | "reports")
                  }
                />
                <i />
              </label>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
