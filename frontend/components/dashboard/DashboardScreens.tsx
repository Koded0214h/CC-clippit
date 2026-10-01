"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import {
  ProfileAvatar,
  ProfilePhotoPicker,
  saveStoredProfile,
  type StoredProfile,
} from "@/components/ui/ProfilePhotoPicker";
import type { Campaign } from "@/lib/product";
import {
  campaignsApi,
  type CampaignFeed,
  type CampaignOut,
} from "@/lib/api/campaigns";
import { earningsApi, type LeaderRow } from "@/lib/api/earnings";
import { creatorApi, type ClipRow } from "@/lib/api/creator";
import {
  creatorProfileApi,
  handlesApi,
  socialApi,
  type ConnectedAccountOut,
} from "@/lib/api/social";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";
import { profileApi, type NotificationSettings } from "@/lib/api/profile";
import { productConfigApi, uploadsApi } from "@/lib/api/account";
import { ApiError, errorMessage } from "@/lib/api/client";
import {
  formatDate,
  formatDateTime,
  initials,
  platformIconName,
  platformLabel,
  timeAgo,
} from "@/lib/format";

export function campaignOutToLocal(c: CampaignOut): Campaign {
  return {
    id: c.id,
    slug: c.slug,
    brand: c.brand?.name ?? "Brand",
    title: c.title,
    line: c.tagline ?? c.description.slice(0, 120),
    image: c.cover_image_url ?? "/assets/video/creator-reaction-poster.jpg",
    rate: c.payout_rule?.rate_per_1000_views ?? 0,
    pot: c.pot,
    remaining: c.remaining,
    daysLeft: c.time_left?.days ?? 0,
    hoursLeft: c.time_left?.hours ?? 0,
    platforms: c.platforms,
    category: c.category ?? "General",
    status: c.joined
      ? "Joined"
      : ((c.feed_status as Campaign["status"]) ?? "Open"),
    minimumViews: c.payout_rule?.min_views_threshold ?? 1000,
    creatorCap: c.payout_rule?.cap_amount ?? 0,
    brief: c.description,
    mustDo: c.rules.filter((r) => r.kind === "must").map((r) => r.text),
    mustAvoid: c.rules.filter((r) => r.kind === "avoid").map((r) => r.text),
    videoCap: c.video_cap ?? c.payout_rule?.video_cap_amount ?? 0,
    maxSubmissions: c.max_submissions ?? c.payout_rule?.max_submissions ?? 0,
    accessMode: c.access_mode ?? "public",
    assets:
      c.assets?.map((asset) => ({
        name: asset.name,
        url: asset.url,
        kind: asset.kind ?? "reference",
      })) ?? [],
    endCondition: c.end_condition ?? (c.time_left ? "duration" : "budget"),
    endsAt: c.ends_at ?? null,
    acceptingEntries: c.accepting_entries,
    performanceMetrics: c.performance_metrics?.map((metric) => ({
      metricType: metric.metric_type,
      rate: metric.rate_amount,
      unitSize: metric.unit_size,
      minimum: metric.min_threshold,
    })),
    conversionDestinationType: c.conversion_setup?.destination_type ?? null,
  };
}

const EMPTY_PROFILE: StoredProfile = { name: "", bio: "", photo: "" };

function EmptyState({
  icon = "search",
  title,
  copy,
  action,
}: {
  icon?: ProductIconName;
  title: string;
  copy: string;
  action?: React.ReactNode;
}) {
  return (
    <ClippitEmptyState icon={icon} title={title} copy={copy} action={action} />
  );
}

function LoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <ClippitEmptyState
      role="alert"
      tone="danger"
      icon="shield"
      title="We couldn't load this right now."
      copy={message}
      action={
        <button type="button" className="ink-button" onClick={onRetry}>
          Try again
          <ProductIcon name="arrow" />
        </button>
      }
    />
  );
}

function PageHeading({
  title,
  copy,
  note,
}: {
  title: string;
  copy?: string;
  note?: string;
}) {
  return (
    <header className="page-heading">
      <div>
        {note && <p className="marker-label">{note}</p>}
        <h1>{title}</h1>
        {copy && <p>{copy}</p>}
      </div>
    </header>
  );
}

function PlatformMarks({ platforms }: { platforms: string[] }) {
  return (
    <span
      className="platform-marks"
      aria-label={platforms.map(platformLabel).join(", ")}
    >
      {platforms.map((platform) => (
        <i key={platform} title={platformLabel(platform)}>
          <ProductIcon name={platformIconName(platform)} />
        </i>
      ))}
    </span>
  );
}

function Countdown({ campaign }: { campaign: Campaign }) {
  return (
    <span className="countdown">
      <ProductIcon name="clock" />
      <strong>
        <AnimatedNumber value={campaign.daysLeft} suffix="d " duration={800} />
        <AnimatedNumber
          value={campaign.hoursLeft}
          suffix="h"
          duration={900}
          delay={90}
        />
      </strong>
      <small>left</small>
    </span>
  );
}

function AnimatedMoney({ value }: { value: number }) {
  return <AnimatedNumber value={value} format="money" />;
}

function useSecondsLeft(
  endsAt: string | null | undefined,
  fallbackSeconds: number,
) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  if (!endsAt) return fallbackSeconds;
  return Math.max(0, Math.floor((new Date(endsAt).getTime() - now) / 1000));
}

function LiveDuration({
  campaign,
  compact = false,
}: {
  campaign: Campaign;
  compact?: boolean;
}) {
  const seconds = useSecondsLeft(
    campaign.endsAt,
    campaign.daysLeft * 86400 + campaign.hoursLeft * 3600,
  );
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return (
    <span
      className="live-duration"
      role="timer"
      aria-label={`${days} days, ${hours} hours left`}
    >
      <b>{String(days).padStart(2, "0")}</b>
      <small>d</small>
      <b>{String(hours).padStart(2, "0")}</b>
      <small>h</small>
      {!compact && (
        <>
          <b>{String(minutes).padStart(2, "0")}</b>
          <small>m</small>
          <b>{String(remainder).padStart(2, "0")}</b>
          <small>s</small>
        </>
      )}
    </span>
  );
}

function potPercent(campaign: Campaign) {
  return campaign.pot > 0
    ? Math.round((campaign.remaining / campaign.pot) * 100)
    : 0;
}

function CampaignVitals({
  campaign,
  includeMinimum = false,
}: {
  campaign: Campaign;
  includeMinimum?: boolean;
}) {
  const potLevel = potPercent(campaign);
  const style = { "--pot-level": `${potLevel}%` } as CSSProperties;
  const outcomes = campaign.performanceMetrics?.length
    ? campaign.performanceMetrics
    : [
        {
          metricType: "view",
          rate: campaign.rate,
          unitSize: 1000,
          minimum: campaign.minimumViews,
        },
      ];
  return (
    <div
      className={`campaign-vitals${includeMinimum ? " campaign-vitals--detail" : ""}`}
      style={style}
    >
      <div className="campaign-vital campaign-vital--rate">
        <span className="vital-icon">
          <ProductIcon name="spark" />
        </span>
        <div>
          <small>
            {outcomes.length === 1 ? "Live rate" : "Performance rates"}
          </small>
          <strong>
            {outcomes.length === 1 ? (
              <AnimatedMoney value={outcomes[0].rate} />
            ) : (
              <AnimatedNumber value={outcomes.length} padStart={2} />
            )}
          </strong>
          <p>
            {outcomes.length === 1
              ? `per ${outcomes[0].unitSize.toLocaleString()} ${outcomes[0].metricType}${outcomes[0].unitSize === 1 ? "" : "s"}`
              : "verified outcomes selected"}
          </p>
        </div>
      </div>
      <div className="campaign-vital campaign-vital--pot">
        <Image
          className="campaign-vital__generated-art"
          src="/assets/illustrations/clippit-icons/funding-pot.webp"
          alt=""
          width={112}
          height={112}
          aria-hidden="true"
        />
        <div className="pot-label">
          <small>Money still in the pot</small>
          <strong>
            <AnimatedMoney value={campaign.remaining} />
          </strong>
        </div>
        <div
          className="pot-meter"
          aria-label={`${potLevel}% of campaign pot remains`}
        >
          <span className="pot-meter__fill" />
          <i className="pot-meter__proof">
            <ProductIcon name="shield" />
          </i>
        </div>
        <p>
          <b>
            <AnimatedNumber value={potLevel} suffix="%" duration={900} />
          </b>{" "}
          of <AnimatedMoney value={campaign.pot} /> remains
        </p>
      </div>
      <div className="campaign-vital campaign-vital--time">
        <span className="time-orbit">
          <ProductIcon name="clock" />
        </span>
        {campaign.endCondition === "budget" ? (
          <div>
            <small>Campaign end</small>
            <strong className="budget-only-end">Pot exhaustion</strong>
            <p>No fixed closing date</p>
          </div>
        ) : (
          <div>
            <small>Campaign closes in</small>
            <LiveDuration campaign={campaign} compact={!includeMinimum} />
            <p>
              {campaign.endsAt
                ? formatDateTime(campaign.endsAt)
                : `${campaign.daysLeft}d ${campaign.hoursLeft}h left`}
            </p>
          </div>
        )}
      </div>
      {includeMinimum && (
        <div className="campaign-vital campaign-vital--minimum">
          <ProductIcon name="play" />
          <div>
            <small>Starts earning at</small>
            <strong>
              <AnimatedNumber value={campaign.minimumViews} format="compact" />
            </strong>
            <p>verified views</p>
          </div>
        </div>
      )}
    </div>
  );
}

function SectionTitle({
  title,
  href,
  linkLabel,
}: {
  title: string;
  href?: string;
  linkLabel?: string;
}) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {href && (
        <Link href={href}>
          {linkLabel ?? "See all"}
          <ProductIcon name="arrow" />
        </Link>
      )}
    </div>
  );
}

const creatorFieldNotes = [
  {
    type: "video" as const,
    src: "/assets/video/creator-studio-pexels-7480862.mp4",
    poster: "/assets/photos/creator-vlogger-pexels-6954220.jpg",
    kicker: "Video reference",
    title: "Phone tripod setup",
    lane: "Lifestyle setup",
  },
  {
    type: "image" as const,
    src: "/assets/photos/creator-fashion-pexels-7585630.jpg",
    kicker: "Image reference",
    title: "Plan movement before the transition",
    lane: "Fashion",
  },
  {
    type: "image" as const,
    src: "/assets/photos/creator-studio-pexels-8359963.jpg",
    kicker: "Image reference",
    title: "Lighting a home setup",
    lane: "Home studio",
  },
  {
    type: "image" as const,
    src: "/assets/photos/creator-vlogger-pexels-6954220.jpg",
    kicker: "Image reference",
    title: "Capture natural reactions",
    lane: "Personality",
  },
];

function AutoPreviewVideo({ src, poster }: { src: string; poster: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || window.matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        setActive(entry.isIntersecting);
      },
      { threshold: 0.3 },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (active) void video.play().catch(() => undefined);
    else video.pause();
  }, [active]);

  return (
    <video
      ref={videoRef}
      muted
      loop
      playsInline
      preload="none"
      poster={poster}
      aria-label="Creator setting up a phone to record"
    >
      {active && <source src={src} type="video/mp4" />}
    </video>
  );
}

function CreatorFieldNotes() {
  return (
    <section
      className="creator-field-notes"
      aria-labelledby="creator-field-notes-title"
    >
      <div className="creator-field-notes__heading">
        <div>
          <h2 id="creator-field-notes-title">Content references</h2>
        </div>
        <p>Use these references for framing, lighting and pacing.</p>
      </div>
      <div className="creator-reel">
        {creatorFieldNotes.map((item, index) => (
          <article
            key={item.src + item.kicker}
            className={`creator-reel__card${index === 0 ? " creator-reel__card--lead" : ""}`}
          >
            <div className="creator-reel__media">
              {item.type === "video" ? (
                <AutoPreviewVideo src={item.src} poster={item.poster} />
              ) : (
                <Image
                  src={item.src}
                  alt="Creator filming content in a home studio"
                  fill
                  sizes="(max-width: 700px) 78vw, 24vw"
                />
              )}
              <span className="creator-reel__number">0{index + 1}</span>
              {item.type === "video" && (
                <span className="creator-reel__live">
                  <i /> Playing now
                </span>
              )}
            </div>
            <div className="creator-reel__copy">
              <p>{item.kicker}</p>
              <h3>{item.title}</h3>
              <span>
                <ProductIcon name={item.type === "video" ? "play" : "camera"} />
                {item.lane}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

type BoardRow = {
  rank: number;
  name: string;
  handle: string;
  views: number;
  earned: number;
  is_me?: boolean;
};

function toBoardRow(r: LeaderRow): BoardRow {
  return {
    rank: r.rank,
    name: r.name,
    handle: r.handle ? `@${r.handle}` : "",
    views: r.views,
    earned: r.earned,
    is_me: r.is_me,
  };
}

function MiniLeaderboard() {
  const [board, setBoard] = useState<BoardRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    earningsApi
      .leaderboard({ period: "week", limit: 4 })
      .then((data) => {
        setBoard(data.items.slice(0, 4).map(toBoardRow));
        setError("");
      })
      .catch((err) => setError(errorMessage(err, "We couldn't load the weekly leaderboard.")));
  }, []);
  return (
    <aside className="mini-leaderboard">
      <SectionTitle
        title="Weekly leaderboard"
        href="/dashboard/leaderboard"
        linkLabel="Full board"
      />
      {error && <p className="auth-error" role="alert">{error}</p>}
      {board && !board.length && (
        <ClippitEmptyState
          className="mini-leaderboard__empty"
          size="inline"
          icon="trophy"
          title="The board is open"
          copy="Your first approved clip with verified views puts you here."
        />
      )}
      {(board ?? []).map((person) => (
        <div key={person.rank} className={person.is_me ? "is-you" : ""}>
          <span>
            <AnimatedNumber value={person.rank} padStart={2} duration={600} />
          </span>
          <i>{person.name.slice(0, 2).toUpperCase()}</i>
          <p>
            <strong>{person.name}</strong>
            <small>{person.handle}</small>
          </p>
          <b>
            <AnimatedNumber value={person.views} format="compact" />
          </b>
        </div>
      ))}
    </aside>
  );
}

function homeHeading(feature: Campaign | null, newMatches: number) {
  const matches =
    newMatches === 0
      ? "No new campaigns match your lanes this week yet."
      : `${newMatches} new campaign${newMatches === 1 ? "" : "s"} match${newMatches === 1 ? "es" : ""} your content lanes.`;
  if (!feature)
    return {
      title: "Your creator desk",
      copy: `No live campaign is closing soon. ${matches}`,
    };
  const when =
    feature.endCondition === "budget"
      ? "runs until its pot is empty"
      : `closes in ${feature.daysLeft}d ${feature.hoursLeft}h`;
  return {
    title: "One campaign closes soon",
    copy: `${feature.title} ${when}. ${matches}`,
  };
}

function clipNode(status: string) {
  if (status === "approved")
    return { className: "proof-node is-money", icon: "wallet" as const };
  if (status === "needs_attention")
    return { className: "proof-node", icon: "shield" as const };
  return { className: "proof-node is-live", icon: "play" as const };
}

export function DashboardHome() {
  const [feature, setFeature] = useState<Campaign | null>(null);
  const [newMatches, setNewMatches] = useState(0);
  const [earnings, setEarnings] = useState({
    total: 0,
    payable: 0,
    inHold: 0,
    paidAllTime: 0,
    addedThisWeek: 0,
    activeClips: 0,
    holdDays: 5,
  });
  const [tapeCampaigns, setTapeCampaigns] = useState<Campaign[]>([]);
  const [recentClips, setRecentClips] = useState<ClipRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      creatorApi.overview(),
      campaignsApi.list({ feed: "all", limit: 6 }),
      creatorApi.clips(),
    ])
      .then(([overview, list, clips]) => {
        if (cancelled) return;
        const closing = overview.closing_soon
          ? campaignOutToLocal(overview.closing_soon)
          : null;
        setFeature(closing);
        setNewMatches(overview.new_matches);
        setEarnings({
          total: overview.earnings.total_accrued,
          payable: overview.earnings.payable,
          inHold: overview.earnings.in_hold,
          paidAllTime: overview.earnings.paid_all_time,
          addedThisWeek: overview.earnings.added_this_week,
          activeClips: overview.earnings.active_clips,
          holdDays: overview.earnings.hold_days,
        });
        setTapeCampaigns(
          list
            .map(campaignOutToLocal)
            .filter((item) => item.slug !== closing?.slug),
        );
        setRecentClips(clips.items.slice(0, 3));
        setError("");
      })
      .catch((err) => {
        if (!cancelled)
          setError(errorMessage(err, "Check your connection and try again."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  if (loading)
    return (
      <div className="dashboard-page">
        <ClippitLoader
          contained
          label="Bringing your dashboard up to date"
          note="Checking your campaigns, verified views and available money."
        />
      </div>
    );
  if (error)
    return (
      <div className="dashboard-page">
        <LoadError
          message={error}
          onRetry={() => {
            setLoading(true);
            setReload((value) => value + 1);
          }}
        />
      </div>
    );

  const heading = homeHeading(feature, newMatches);

  return (
    <div className="dashboard-page dashboard-home">
      <PageHeading title={heading.title} copy={heading.copy} />

      <section
        className="dashboard-lead"
        aria-label="Featured campaign and earnings"
      >
        {feature ? (
          <FeatureCampaign feature={feature} />
        ) : (
          <article className="feature-campaign feature-campaign--empty">
            <EmptyState
              icon="brief"
              title="No campaign is closing soon"
              copy="Browse live briefs, join one that fits your lane, and your next deadline shows up here."
              action={
                <Link className="lime-button" href="/dashboard/campaigns">
                  Browse campaigns
                  <ProductIcon name="arrow" />
                </Link>
              }
            />
          </article>
        )}

        <aside className="money-receipt">
          <div className="money-receipt__head">
            <div>
              <Image
                className="money-receipt__generated-art"
                src="/assets/illustrations/clippit-icons/payout-wallet.webp"
                alt=""
                width={36}
                height={36}
                aria-hidden="true"
              />
              <span>Your money</span>
            </div>
            <small>{formatDate(new Date().toISOString())}</small>
          </div>
          <div className="money-total">
            <span>Total accrued</span>
            <strong>
              <AnimatedMoney value={earnings.total} />
            </strong>
            <small>
              <b>
                Across {earnings.activeClips} clip
                {earnings.activeClips === 1 ? "" : "s"}
              </b>
              <i />
              <span>
                <AnimatedMoney value={earnings.addedThisWeek} /> added this week
              </span>
            </small>
          </div>
          <dl>
            <div>
              <dt>Payable now</dt>
              <dd>
                <AnimatedMoney value={earnings.payable} />
              </dd>
            </div>
            <div>
              <dt>In {earnings.holdDays}-day hold</dt>
              <dd>
                <AnimatedMoney value={earnings.inHold} />
              </dd>
            </div>
            <div>
              <dt>Paid all time</dt>
              <dd>
                <AnimatedMoney value={earnings.paidAllTime} />
              </dd>
            </div>
          </dl>
          <Link href="/dashboard/wallet" className="ink-button">
            {earnings.payable > 0 ? "Withdraw payable money" : "Open wallet"}
            <ProductIcon name="arrow" />
          </Link>
          <p>
            <ProductIcon name="shield" /> Earnings use platform-reported views.
          </p>
        </aside>
      </section>

      <section className="dashboard-section">
        <SectionTitle title="New campaigns" href="/dashboard/campaigns" />
        {!tapeCampaigns.length && (
          <EmptyState
            title="No other live campaigns right now"
            copy="New briefs appear here the moment a brand funds them."
          />
        )}
        <div className="campaign-tape">
          {tapeCampaigns.map((campaign) => (
            <Link
              key={campaign.slug}
              href={`/dashboard/campaigns/${campaign.slug}`}
              className="campaign-tape__item"
            >
              <div className="campaign-tape__image">
                <Image src={campaign.image} alt="" fill sizes="160px" />
                <span>{campaign.category}</span>
              </div>
              <div className="campaign-tape__name">
                <small>{campaign.brand}</small>
                <strong>{campaign.title}</strong>
                <PlatformMarks platforms={campaign.platforms} />
              </div>
              <div className="campaign-tape__rate">
                <small>Rate</small>
                <strong>
                  <AnimatedMoney value={campaign.rate} />
                </strong>
                <span>/ 1K views</span>
              </div>
              <div className="campaign-tape__pot">
                <small>Pot left</small>
                <strong>
                  <AnimatedMoney value={campaign.remaining} />
                </strong>
                <i>
                  <span style={{ width: `${potPercent(campaign)}%` }} />
                </i>
              </div>
              <Countdown campaign={campaign} />
              <span className="round-arrow">
                <ProductIcon name="arrow" />
              </span>
            </Link>
          ))}
        </div>
      </section>

      <CreatorFieldNotes />

      <section className="dashboard-bottom-grid">
        <div className="proof-stream">
          <SectionTitle
            title="Recent clip activity"
            href={recentClips.length ? "/dashboard/clips" : undefined}
            linkLabel="All clips"
          />
          <div className="proof-stream__line" aria-hidden="true" />
          {!recentClips.length && (
            <ClippitEmptyState
              className="proof-stream__empty"
              size="inline"
              icon="play"
              title="No clips submitted yet"
              copy="Your verification status and verified views will appear here."
            />
          )}
          {recentClips.map((clip) => {
            const node = clipNode(clip.status);
            return (
              <Link
                key={clip.id}
                href={clip.link}
                className="proof-stream__item"
              >
                <article>
                  <span className={node.className}>
                    <ProductIcon name={node.icon} />
                  </span>
                  <div>
                    <small>{clip.label}</small>
                    <strong>{clip.title || clip.campaign_title}</strong>
                    <p>
                      {clip.brand ?? clip.campaign_title} ·{" "}
                      {platformLabel(clip.platform)}
                    </p>
                  </div>
                  {clip.status === "approved" ? (
                    <b>
                      <AnimatedMoney value={clip.earned} />
                    </b>
                  ) : (
                    <b>
                      <AnimatedNumber
                        value={clip.verified_views}
                        format="compact"
                      />{" "}
                      <small>views</small>
                    </b>
                  )}
                </article>
              </Link>
            );
          })}
        </div>

        <MiniLeaderboard />
      </section>
    </div>
  );
}

function FeatureCampaign({ feature }: { feature: Campaign }) {
  return (
    <article className="feature-campaign">
      <Image
        src={feature.image}
        alt="Creator filming a campaign clip"
        fill
        sizes="(max-width: 900px) 100vw, 58vw"
        priority
      />
      <div className="feature-campaign__wash" />
      <div className="feature-campaign__top">
        <span className="status-chip">
          <i /> {feature.status}
        </span>
        <div className="campaign-top-signals">
          <span className="mobile-time-chip">
            <ProductIcon name="clock" /> {feature.daysLeft}d {feature.hoursLeft}
            h left
          </span>
          <PlatformMarks platforms={feature.platforms} />
        </div>
      </div>
      <div className="feature-campaign__copy">
        <span>{feature.brand}</span>
        <h2>{feature.title}</h2>
        <p>{feature.line}</p>
      </div>
      <div className="feature-campaign__bottom">
        <CampaignVitals campaign={feature} />
        <Link
          href={`/dashboard/campaigns/${feature.slug}`}
          className="lime-button"
        >
          Read the brief
          <ProductIcon name="arrow" />
        </Link>
      </div>
    </article>
  );
}

const campaignFilters = ["All", "For you", "Closing soon", "Joined"];
const feedMap: Record<string, CampaignFeed> = {
  All: "all",
  "For you": "for_you",
  "Closing soon": "closing_soon",
  Joined: "joined",
};
const PAGE_SIZE = 24;

const emptyCopy: Record<string, { title: string; copy: string }> = {
  All: {
    title: "No live campaigns right now.",
    copy: "Brands fund new briefs every week. Check back soon.",
  },
  "For you": {
    title: "Nothing matches your lanes yet.",
    copy: "Add more content lanes in Settings to widen what we match you with.",
  },
  "Closing soon": {
    title: "Nothing is closing soon.",
    copy: "Every live campaign has more than a few days left.",
  },
  Joined: {
    title: "You haven't joined a campaign yet.",
    copy: "Open a brief and tap Join campaign to start earning from it.",
  },
};

export function CampaignDirectory() {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [visible, setVisible] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setSearch(query.trim().slice(0, 80)),
      350,
    );
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    campaignsApi
      .list({
        feed: feedMap[filter] ?? "all",
        q: search || undefined,
        limit: PAGE_SIZE,
      })
      .then((data) => {
        if (cancelled) return;
        setVisible(data.map(campaignOutToLocal));
        setHasMore(data.length === PAGE_SIZE);
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter, search, reload]);

  const changeFilter = (item: string) => {
    setLoading(true);
    setFilter(item);
  };

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await campaignsApi.list({
        feed: feedMap[filter] ?? "all",
        q: search || undefined,
        limit: PAGE_SIZE,
        offset: visible.length,
      });
      setVisible((current) => [...current, ...data.map(campaignOutToLocal)]);
      setHasMore(data.length === PAGE_SIZE);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="dashboard-page campaigns-page">
      <PageHeading
        title="Campaigns"
        copy="Compare rates, remaining budgets and deadlines before joining."
      />
      <div className="campaign-tools">
        <div className="campaign-filters" aria-label="Campaign filters">
          {campaignFilters.map((item) => (
            <button
              key={item}
              type="button"
              className={filter === item ? "is-active" : ""}
              onClick={() => changeFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <label className="campaign-search">
          <ProductIcon name="search" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search campaigns, brands or lanes"
            aria-label="Search campaigns"
          />
        </label>
      </div>

      {loading ? (
        <ClippitLoader
          contained
          compact
          label="Finding campaigns for you"
          note="Comparing live rates, available money and campaign status."
        />
      ) : error ? (
        <LoadError
          message={error}
          onRetry={() => {
            setLoading(true);
            setReload((value) => value + 1);
          }}
        />
      ) : (
        <div className="campaign-ledger">
          <div className="campaign-ledger__header">
            <span>Campaign</span>
            <span>Rate</span>
            <span>Available money</span>
            <span>Closes</span>
            <span />
          </div>
          {visible.map((campaign) => (
            <Link
              key={campaign.slug}
              href={`/dashboard/campaigns/${campaign.slug}`}
              className="campaign-ledger__row"
            >
              <div className="ledger-campaign">
                <span className="ledger-image">
                  <Image src={campaign.image} alt="" fill sizes="110px" />
                </span>
                <span>
                  <small>
                    {campaign.brand} · {campaign.category}
                  </small>
                  <strong>{campaign.title}</strong>
                  <i>{campaign.status}</i>
                </span>
              </div>
              <div className="ledger-rate">
                <strong>
                  <AnimatedMoney value={campaign.rate} />
                </strong>
                <small>per 1K verified views</small>
              </div>
              <div className="ledger-pot">
                <strong>
                  <AnimatedMoney value={campaign.remaining} />
                </strong>
                <span>
                  <i style={{ width: `${potPercent(campaign)}%` }} />
                </span>
                <small>
                  of <AnimatedMoney value={campaign.pot} />
                </small>
              </div>
              {campaign.endCondition === "budget" ? (
                <span className="countdown">
                  <ProductIcon name="clock" />
                  <strong>Pot</strong>
                  <small>until empty</small>
                </span>
              ) : (
                <Countdown campaign={campaign} />
              )}
              <span className="round-arrow">
                <ProductIcon name="arrow" />
              </span>
            </Link>
          ))}
          {!visible.length &&
            (search ? (
              <EmptyState
                title="No campaigns match that search."
                copy="Try another title, brand or category."
              />
            ) : (
              <EmptyState
                title={emptyCopy[filter].title}
                copy={emptyCopy[filter].copy}
              />
            ))}
          {hasMore && (
            <button
              type="button"
              className="ink-button campaign-load-more"
              disabled={loadingMore}
              onClick={loadMore}
            >
              {loadingMore ? "Loading…" : "Load more campaigns"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

type JoinProblem = { message: string; href?: string; cta?: string };

function joinProblem(err: unknown): JoinProblem {
  if (err instanceof ApiError) {
    if (err.code === "email_not_verified")
      return {
        message: "Confirm your email address before joining campaigns.",
        href: "/auth/verify-email",
        cta: "Confirm email",
      };
    if (err.status === 409 && /connect/i.test(err.detail))
      return {
        message: err.detail,
        href: "/dashboard/accounts",
        cta: "Connect an account",
      };
    return { message: err.detail };
  }
  return {
    message:
      "We couldn't join this campaign. Check your connection and try again.",
  };
}

export function CampaignDetail({ slug }: { slug: string }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [joined, setJoined] = useState(false);
  const [sideLeaders, setSideLeaders] = useState<BoardRow[] | null>(null);
  const [leadersError, setLeadersError] = useState("");
  const [holdDays, setHoldDays] = useState<number | null>(null);
  const [joining, setJoining] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [problem, setProblem] = useState<JoinProblem | null>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [trackedLink, setTrackedLink] = useState("");
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkError, setLinkError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    campaignsApi
      .get(slug)
      .then((data) => {
        if (cancelled) return;
        setCampaign(campaignOutToLocal(data));
        setJoined(!!data.joined);
        setLoadError("");
        earningsApi
          .leaderboard({ campaign_id: data.id, limit: 3 })
          .then((board) => {
            if (!cancelled) {
              setSideLeaders(board.items.slice(0, 3).map(toBoardRow));
              setLeadersError("");
            }
          })
          .catch((err) => {
            if (!cancelled) setLeadersError(errorMessage(err, "We couldn't load this campaign's leaderboard."));
          });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setLoadError(errorMessage(err));
      });
    productConfigApi
      .get()
      .then((data) => {
        if (!cancelled) setHoldDays(data.hold_days);
      })
      .catch(() => {
        if (!cancelled) setHoldDays(null);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, reload]);

  if (notFound)
    return (
      <div className="dashboard-page">
        <EmptyState
          icon="brief"
          title="This campaign isn't available"
          copy="It may have closed, or the link is wrong."
          action={
            <Link className="lime-button" href="/dashboard/campaigns">
              Browse live campaigns
              <ProductIcon name="arrow" />
            </Link>
          }
        />
      </div>
    );
  if (loadError)
    return (
      <div className="dashboard-page">
        <LoadError
          message={loadError}
          onRetry={() => {
            setLoadError("");
            setReload((value) => value + 1);
          }}
        />
      </div>
    );
  if (!campaign)
    return (
      <div className="dashboard-page">
        <ClippitLoader
          contained
          label="Opening the brief"
          note="Loading the rules, rate and money left in the pot."
        />
      </div>
    );

  const inviteOnly = campaign.accessMode === "invite";
  const closed = campaign.acceptingEntries === false;

  const joinCampaign = async () => {
    if (inviteOnly && !inviteCode.trim()) {
      setProblem({
        message:
          "This campaign is invite-only. Enter the code the brand gave you.",
      });
      return;
    }
    setJoining(true);
    setProblem(null);
    try {
      await campaignsApi.join(
        campaign.slug,
        inviteOnly ? inviteCode.trim() : undefined,
      );
      setJoined(true);
      setCampaign((current) => current && { ...current, status: "Joined" });
    } catch (err) {
      setProblem(joinProblem(err));
    } finally {
      setJoining(false);
    }
  };

  const leaveCampaign = async () => {
    if (
      !window.confirm(
        `Leave "${campaign.title}"? You can join again while it's open.`,
      )
    )
      return;
    setLeaving(true);
    setProblem(null);
    try {
      await campaignsApi.leave(campaign.slug);
      setJoined(false);
    } catch (err) {
      setProblem({ message: errorMessage(err) });
    } finally {
      setLeaving(false);
    }
  };

  const createTrackedLink = async () => {
    setLinkBusy(true);
    setLinkError("");
    try {
      const link = await campaignsApi.createAttributionLink(campaign.slug);
      setTrackedLink(link.tracking_url);
      await navigator.clipboard?.writeText(link.tracking_url);
    } catch (error) {
      setLinkError(
        errorMessage(error, "We couldn't create the campaign link."),
      );
    } finally {
      setLinkBusy(false);
    }
  };

  const joinButton = closed ? (
    <button className="lime-button" type="button" disabled>
      No longer accepting clips
    </button>
  ) : (
    <button
      className="lime-button"
      type="button"
      disabled={joining}
      onClick={joinCampaign}
    >
      {joining ? "Joining…" : "Join campaign"}
      <ProductIcon name="arrow" />
    </button>
  );

  return (
    <div className="dashboard-page campaign-detail-page">
      <Link className="product-back" href="/dashboard/campaigns">
        <ProductIcon name="chevron" /> All campaigns
      </Link>
      <section className="campaign-detail-hero">
        <Image
          src={campaign.image}
          alt="Campaign visual"
          fill
          priority
          sizes="(max-width: 900px) 100vw, 70vw"
        />
        <div className="campaign-detail-hero__wash" />
        <div className="campaign-detail-hero__top">
          <span className="status-chip">
            <i /> {joined ? "Joined" : campaign.status}
          </span>
          <div className="campaign-top-signals">
            <span className="mobile-time-chip">
              <ProductIcon name="clock" /> {campaign.daysLeft}d{" "}
              {campaign.hoursLeft}h left
            </span>
            <PlatformMarks platforms={campaign.platforms} />
          </div>
        </div>
        <div className="campaign-detail-hero__copy">
          <p>{campaign.brand}</p>
          <h1>{campaign.title}</h1>
          <span>{campaign.line}</span>
        </div>
        <div className="campaign-detail-hero__action">
          {!joined && inviteOnly && !closed && (
            <input
              className="invite-code-input"
              value={inviteCode}
              onChange={(event) =>
                setInviteCode(event.target.value.toUpperCase().slice(0, 20))
              }
              placeholder="Invite code"
              aria-label="Invite code"
            />
          )}
          {joined ? (
            <Link
              className="lime-button"
              href={`/dashboard/campaigns/${campaign.slug}/submit`}
            >
              Submit your clip
              <ProductIcon name="arrow" />
            </Link>
          ) : (
            joinButton
          )}
          {joined && (
            <button
              className="text-button"
              type="button"
              disabled={leaving}
              onClick={leaveCampaign}
            >
              {leaving ? "Leaving…" : "Leave campaign"}
            </button>
          )}
        </div>
      </section>

      {problem && (
        <p className="campaign-join-problem" role="alert">
          <ProductIcon name="shield" /> {problem.message}
          {problem.href && (
            <Link href={problem.href}>
              {problem.cta}
              <ProductIcon name="arrow" />
            </Link>
          )}
        </p>
      )}

      <CampaignVitals campaign={campaign} includeMinimum />

      <section className="campaign-outcome-sheet">
        <header>
          <div>
            <small>How this campaign pays</small>
            <h2>Performance scorecard</h2>
          </div>
          <span>{campaign.performanceMetrics?.length ?? 1} selected</span>
        </header>
        <div className="campaign-outcome-grid">
          {(campaign.performanceMetrics?.length
            ? campaign.performanceMetrics
            : [
                {
                  metricType: "view",
                  rate: campaign.rate,
                  unitSize: 1000,
                  minimum: campaign.minimumViews,
                },
              ]
          ).map((metric, index) => (
            <article key={metric.metricType}>
              <i>{String(index + 1).padStart(2, "0")}</i>
              <div>
                <small>{metric.metricType}</small>
                <strong>
                  <AnimatedMoney value={metric.rate} />
                </strong>
                <p>
                  per {metric.unitSize.toLocaleString()} verified{" "}
                  {metric.metricType}
                  {metric.unitSize === 1 ? "" : "s"}
                </p>
              </div>
              <ProductIcon
                name={
                  metric.metricType === "view"
                    ? "eye"
                    : metric.metricType === "comment"
                      ? "brief"
                      : metric.metricType === "share"
                        ? "arrow"
                        : metric.metricType === "visit"
                          ? "link"
                          : metric.metricType === "purchase"
                            ? "wallet"
                            : "person"
                }
              />
            </article>
          ))}
        </div>
        {campaign.conversionDestinationType && joined ? (
          <div className="creator-tracked-link">
            <span>
              <ProductIcon
                name={
                  campaign.conversionDestinationType === "whatsapp"
                    ? "phone"
                    : "link"
                }
              />
            </span>
            <div>
              <small>Your campaign link</small>
              <strong>
                {trackedLink || "Create your creator-specific link"}
              </strong>
              <p>
                Visits and confirmed customer actions from this link are
                credited to you.
              </p>
              {linkError && <em role="alert">{linkError}</em>}
            </div>
            <button
              type="button"
              disabled={linkBusy}
              onClick={createTrackedLink}
            >
              {linkBusy
                ? "Creating…"
                : trackedLink
                  ? "Copy again"
                  : "Create and copy"}
              <ProductIcon name="arrow" />
            </button>
          </div>
        ) : null}
      </section>

      <div className="campaign-detail-grid">
        <div className="campaign-detail-main">
          <section className="brief-sheet">
            <div className="brief-sheet__heading">
              <span>Brief</span>
              <small>Read this before you film</small>
            </div>
            <h2>Campaign brief</h2>
            <p className="brief-lead">{campaign.brief}</p>
            <div className="brief-rule-columns">
              <div>
                <h3>
                  <ProductIcon name="check" /> Your clip must
                </h3>
                <ol>
                  {campaign.mustDo.map((rule) => (
                    <li key={rule}>
                      <span>{campaign.mustDo.indexOf(rule) + 1}</span>
                      <p>{rule}</p>
                    </li>
                  ))}
                </ol>
              </div>
              <div className="avoid-list">
                <h3>
                  <ProductIcon name="shield" /> Keep out
                </h3>
                <ul>
                  {campaign.mustAvoid.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <section className="campaign-materials">
            <SectionTitle title="Campaign materials" />
            <div>
              {campaign.assets.length ? (
                campaign.assets.map((asset) => (
                  <a
                    href={asset.url}
                    target="_blank"
                    rel="noreferrer"
                    key={`${asset.name}-${asset.url}`}
                  >
                    <span>
                      <ProductIcon
                        name={asset.kind === "sound" ? "play" : "link"}
                      />
                    </span>
                    <p>
                      <strong>{asset.name}</strong>
                      <small>
                        {asset.kind === "sound"
                          ? "Campaign sound"
                          : "Campaign reference"}
                      </small>
                    </p>
                    <ProductIcon name="arrow" />
                  </a>
                ))
              ) : (
                <ClippitEmptyState
                  className="campaign-materials__empty"
                  size="inline"
                  tone="paper"
                  icon="brief"
                  title="No extra files"
                  copy="Everything you need is already in the brief."
                />
              )}
            </div>
          </section>
        </div>

        <aside className="campaign-detail-aside">
          <section className="plain-rules">
            <h2>Earning rules</h2>
            <dl>
              <div>
                <dt>Creator cap</dt>
                <dd>
                  {campaign.creatorCap > 0 ? (
                    <AnimatedMoney value={campaign.creatorCap} />
                  ) : (
                    "No cap"
                  )}
                </dd>
              </div>
              <div>
                <dt>Per-video cap</dt>
                <dd>
                  {campaign.videoCap > 0 ? (
                    <AnimatedMoney value={campaign.videoCap} />
                  ) : (
                    "No cap"
                  )}
                </dd>
              </div>
              <div>
                <dt>Submissions allowed</dt>
                <dd>
                  {campaign.maxSubmissions > 0 ? (
                    <AnimatedNumber value={campaign.maxSubmissions} />
                  ) : (
                    "Unlimited"
                  )}
                </dd>
              </div>
              <div>
                <dt>Access</dt>
                <dd>
                  {campaign.accessMode === "invite" ? "Invite only" : "Public"}
                </dd>
              </div>
              <div>
                <dt>Campaign end</dt>
                <dd>
                  {campaign.endCondition === "budget"
                    ? "When the pot is empty"
                    : campaign.endsAt
                      ? formatDateTime(campaign.endsAt)
                      : "Date or empty pot"}
                </dd>
              </div>
              <div>
                <dt>Holding period</dt>
                <dd>
                  {holdDays === null ? "Unavailable" : (
                    <AnimatedNumber
                      value={holdDays}
                      suffix=" days"
                      duration={700}
                    />
                  )}
                </dd>
              </div>
              <div>
                <dt>Results measured</dt>
                <dd>
                  {campaign.performanceMetrics
                    ?.map((metric) => metric.metricType)
                    .join(", ") || "Views"}
                </dd>
              </div>
              <div>
                <dt>Platforms</dt>
                <dd>{campaign.platforms.map(platformLabel).join(" + ")}</dd>
              </div>
              <div>
                <dt>Content review</dt>
                <dd>
                  Usually under{" "}
                  <AnimatedNumber value={5} suffix=" min" duration={700} />
                </dd>
              </div>
            </dl>
            <p>
              <ProductIcon name="shield" />
              Social results come from connected platforms. Off-platform results
              use your Clippit campaign link.
            </p>
          </section>

          <section className="campaign-leaders">
            <SectionTitle
              title="Campaign leaderboard"
              href={
                campaign.id
                  ? `/dashboard/leaderboard?campaign=${campaign.id}`
                  : "/dashboard/leaderboard"
              }
              linkLabel="View board"
            />
            {leadersError && (
              <p className="auth-error" role="alert">{leadersError}</p>
            )}
            {!sideLeaders && !leadersError && (
              <ClippitLoader contained compact label="Loading campaign leaderboard" />
            )}
            {sideLeaders && !sideLeaders.length && !leadersError && (
              <ClippitEmptyState
                className="campaign-leaders__empty"
                size="inline"
                icon="trophy"
                title="No one is on the board yet"
                copy="The first approved clip with verified views takes the opening spot."
              />
            )}
            {(sideLeaders ?? []).map((person) => (
              <div key={person.rank}>
                <span>
                  <AnimatedNumber value={person.rank} duration={600} />
                </span>
                <i>{person.name.slice(0, 2).toUpperCase()}</i>
                <p>
                  <strong>{person.name}</strong>
                  <small>
                    <AnimatedNumber value={person.views} format="compact" />{" "}
                    views
                  </small>
                </p>
                <b>
                  <AnimatedMoney value={person.earned} />
                </b>
              </div>
            ))}
          </section>
        </aside>
      </div>

      <div className="mobile-campaign-action">
        <div>
          <small>
            {campaign.performanceMetrics?.length ? (
              `${campaign.performanceMetrics.length} paid results`
            ) : (
              <>
                <AnimatedMoney value={campaign.rate} /> / 1K views
              </>
            )}
          </small>
          <strong>
            {campaign.endCondition === "budget" ? (
              "Until pot is empty"
            ) : (
              <>
                <AnimatedNumber
                  value={campaign.daysLeft}
                  suffix="d "
                  duration={800}
                />
                <AnimatedNumber
                  value={campaign.hoursLeft}
                  suffix="h left"
                  duration={900}
                  delay={90}
                />
              </>
            )}
          </strong>
        </div>
        {joined ? (
          <Link href={`/dashboard/campaigns/${campaign.slug}/submit`}>
            Submit clip
            <ProductIcon name="arrow" />
          </Link>
        ) : (
          <button
            type="button"
            disabled={joining || closed}
            onClick={joinCampaign}
          >
            {closed ? "Closed" : joining ? "Joining…" : "Join campaign"}
            <ProductIcon name="arrow" />
          </button>
        )}
      </div>
    </div>
  );
}

export function LeaderboardScreen() {
  const [board, setBoard] = useState<BoardRow[] | null>(null);
  const [me, setMe] = useState<BoardRow | null>(null);
  const [updatedAt, setUpdatedAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [campaignOptionsLoaded, setCampaignOptionsLoaded] = useState(false);
  const [scope, setScope] = useState<"Global" | "Nigeria" | "Campaign">(
    "Global",
  );
  const [period, setPeriod] = useState<"week" | "all">("week");
  const [metric, setMetric] = useState<"Views" | "Earnings">("Views");
  const [campaignOptions, setCampaignOptions] = useState<
    { id: string; title: string }[]
  >([]);
  const [campaignId, setCampaignId] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("campaign");
    campaignsApi
      .mine()
      .then((rows) => {
        const options = rows.map((row) => ({
          id: row.campaign.id,
          title: row.campaign.title,
        }));
        setCampaignOptions(options);
        if (fromUrl) {
          setCampaignId(fromUrl);
          setScope("Campaign");
        } else if (options[0]) setCampaignId(options[0].id);
      })
      .catch(() => {
        if (fromUrl) {
          setCampaignId(fromUrl);
          setScope("Campaign");
        }
      })
      .finally(() => setCampaignOptionsLoaded(true));
  }, []);

  useEffect(() => {
    if (scope === "Campaign" && !campaignId) return;
    let cancelled = false;
    earningsApi
      .leaderboard({
        period,
        scope: scope === "Nigeria" ? "country" : "global",
        campaign_id: scope === "Campaign" ? campaignId : undefined,
        limit: 50,
      })
      .then((data) => {
        if (cancelled) return;
        setBoard(data.items.map(toBoardRow));
        setMe(data.me ? toBoardRow(data.me) : null);
        setUpdatedAt(timeAgo(data.updated_at));
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, period, campaignId, reload]);

  const rows = board ?? [];
  const ranked =
    metric === "Views"
      ? rows
      : [...rows]
          .sort((a, b) => b.earned - a.earned)
          .map((row, index) => ({ ...row, rank: index + 1 }));
  const podium = [ranked[1], ranked[0], ranked[2]].filter(Boolean);
  const noCampaigns =
    scope === "Campaign" &&
    campaignOptionsLoaded &&
    !campaignOptions.length &&
    !campaignId;
  const periodLabel = period === "week" ? "this week" : "all time";
  const changeScope = (next: "Global" | "Nigeria" | "Campaign") => {
    if (next === scope) return;
    setScope(next);
    setError("");
    setLoading(true);
  };
  const changePeriod = (next: "week" | "all") => {
    if (next === period) return;
    setPeriod(next);
    setError("");
    setLoading(true);
  };
  const changeCampaign = (next: string) => {
    if (next === campaignId) return;
    setCampaignId(next);
    setError("");
    setLoading(true);
  };
  const emptyAction =
    scope === "Nigeria" ? (
      <Link className="lime-button" href="/dashboard/settings#profile">
        Check profile country
        <ProductIcon name="arrow" />
      </Link>
    ) : scope === "Campaign" && campaignId ? (
      <Link className="lime-button" href="/dashboard/campaigns">
        Open campaigns
        <ProductIcon name="arrow" />
      </Link>
    ) : (
      <Link className="lime-button" href="/dashboard/campaigns">
        Find a campaign
        <ProductIcon name="arrow" />
      </Link>
    );

  return (
    <div className="dashboard-page leaderboard-page">
      <PageHeading
        title="Leaderboard"
        copy={`Ranking ${periodLabel} by ${metric === "Views" ? "verified views" : "creator earnings"}.`}
      />
      <section
        className="leaderboard-controls"
        aria-label="Leaderboard filters"
      >
        <div>
          {(["Global", "Nigeria", "Campaign"] as const).map((item) => (
            <button
              type="button"
              className={scope === item ? "is-active" : ""}
              onClick={() => changeScope(item)}
              key={item}
            >
              {item}
            </button>
          ))}
        </div>
        <div>
          {(["week", "all"] as const).map((item) => (
            <button
              type="button"
              className={period === item ? "is-active" : ""}
              onClick={() => changePeriod(item)}
              key={item}
            >
              {item === "week" ? "This week" : "All time"}
            </button>
          ))}
        </div>
        <div>
          {(["Views", "Earnings"] as const).map((item) => (
            <button
              type="button"
              className={metric === item ? "is-active" : ""}
              onClick={() => setMetric(item)}
              key={item}
            >
              {item}
            </button>
          ))}
        </div>
        {scope === "Campaign" && campaignOptions.length > 0 && (
          <select
            value={campaignId}
            onChange={(event) => changeCampaign(event.target.value)}
            aria-label="Choose a campaign"
          >
            {campaignOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.title}
              </option>
            ))}
          </select>
        )}
      </section>
      {error && (
        <LoadError
          message={error}
          onRetry={() => {
            setError("");
            setLoading(true);
            setReload((value) => value + 1);
          }}
        />
      )}
      {!error && noCampaigns && (
        <ClippitEmptyState
          className="leaderboard-empty"
          icon="brief"
          title="Join a campaign to open its board"
          copy="Campaign leaderboards start when creators join a brief and collect verified views."
          action={
            <Link className="lime-button" href="/dashboard/campaigns">
              Browse campaigns
              <ProductIcon name="arrow" />
            </Link>
          }
        />
      )}
      {!error && !noCampaigns && (loading || board === null) && (
        <ClippitLoader
          contained
          tone="ink"
          label="Opening the leaderboard"
          note="Checking the latest verified views and creator positions."
        />
      )}
      {!error && !loading && board && !board.length && !noCampaigns && (
        <ClippitEmptyState
          className="leaderboard-empty"
          icon="trophy"
          title={
            metric === "Earnings"
              ? "No earnings on this board yet"
              : "The starting line is open"
          }
          copy={
            scope === "Nigeria"
              ? "Creators in your country appear here after an approved clip records verified views."
              : scope === "Campaign"
                ? "The first approved clip with verified views takes the opening position."
                : "Creators appear here when approved clips begin collecting verified views."
          }
          action={emptyAction}
        />
      )}
      {!error && !loading && !!board?.length && (
        <section className="podium-board">
          <div className="podium-copy">
            <h2>Top creators {periodLabel}</h2>
            <p>Updated after each verified view check.</p>
          </div>
          {podium.map((person) => (
            <article
              key={person.rank}
              className={`podium-person podium-person--${person.rank}`}
            >
              <span>
                <AnimatedNumber value={person.rank} duration={600} />
              </span>
              <i>{person.name.slice(0, 2).toUpperCase()}</i>
              <strong>{person.name}</strong>
              <small>
                <AnimatedNumber value={person.views} format="compact" />{" "}
                verified views
              </small>
              <b>
                <AnimatedMoney value={person.earned} />
              </b>
            </article>
          ))}
        </section>
      )}

      {!error && !loading && !!board?.length && (
        <section className="ranking-sheet">
          <div className="ranking-sheet__head">
            <h2>All creators</h2>
            <span>Updated {updatedAt}</span>
          </div>
          <div className="ranking-row ranking-row--labels">
            <span>Rank</span>
            <span>Creator</span>
            <span>Verified views</span>
            <span>Earned</span>
          </div>
          {ranked.map((person) => (
            <div
              key={`${person.rank}-${person.name}`}
              className={`ranking-row${person.is_me ? " is-you" : ""}`}
            >
              <span className="rank-number">
                <AnimatedNumber
                  value={person.rank}
                  padStart={2}
                  duration={600}
                />
              </span>
              <span className="rank-creator">
                <i>{initials(person.name)}</i>
                <span>
                  <strong>{person.name}</strong>
                  <small>{person.handle}</small>
                </span>
                {person.is_me && <b>You</b>}
              </span>
              <strong>
                <AnimatedNumber value={person.views} format="compact" />
              </strong>
              <strong className="rank-money">
                <AnimatedMoney value={person.earned} />
              </strong>
            </div>
          ))}
          {me && !ranked.some((row) => row.is_me) && (
            <div className="ranking-row is-you">
              <span className="rank-number">
                <AnimatedNumber value={me.rank} padStart={2} duration={600} />
              </span>
              <span className="rank-creator">
                <i>{initials(me.name)}</i>
                <span>
                  <strong>{me.name}</strong>
                  <small>{me.handle}</small>
                </span>
                <b>You</b>
              </span>
              <strong>
                <AnimatedNumber value={me.views} format="compact" />
              </strong>
              <strong className="rank-money">
                <AnimatedMoney value={me.earned} />
              </strong>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

const NOTIFICATION_KEYS: Array<{
  key: keyof NotificationSettings;
  label: string;
  note: string;
}> = [
  {
    key: "new_campaigns",
    label: "New campaigns in my lanes",
    note: "Matched campaigns only.",
  },
  {
    key: "submission_verdicts",
    label: "Submission verdicts",
    note: "Delivered by email and in your Clippit inbox.",
  },
  {
    key: "earnings_payable",
    label: "Earnings become payable",
    note: "Delivered by email and in your Clippit inbox.",
  },
  {
    key: "campaign_closing",
    label: "Campaign closing reminders",
    note: "Delivered by email and in your Clippit inbox.",
  },
];

const LANES = [
  "Comedy",
  "Food",
  "Music",
  "Beauty",
  "Lifestyle",
  "Gaming",
  "Fitness",
  "Tech",
  "Travel",
];
const COUNTRIES: Array<[string, string]> = [
  ["NG", "Nigeria"],
  ["GH", "Ghana"],
  ["KE", "Kenya"],
  ["ZA", "South Africa"],
  ["GB", "United Kingdom"],
  ["US", "United States"],
];

type ProfileForm = StoredProfile & {
  handle: string;
  lanes: string[];
  location: string;
  country: string;
};

export function SettingsScreen() {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [activeSection, setActiveSection] = useState("profile");
  const [profile, setProfile] = useState<ProfileForm>({
    ...EMPTY_PROFILE,
    handle: "",
    lanes: [],
    location: "",
    country: "",
  });
  const [originalHandle, setOriginalHandle] = useState("");
  const [handleCheck, setHandleCheck] = useState<{
    handle: string;
    state: "ok" | "taken";
    note: string;
  } | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [bankDetail, setBankDetail] = useState<BankAccountOut | null | undefined>(undefined);
  const [bankError, setBankError] = useState("");
  const [socials, setSocials] = useState<ConnectedAccountOut[] | null>(null);
  const [socialError, setSocialError] = useState("");
  const [socialNotice, setSocialNotice] = useState("");
  const [notifPrefs, setNotifPrefs] = useState<NotificationSettings | null>(
    null,
  );
  const [notifError, setNotifError] = useState("");

  useEffect(() => {
    creatorProfileApi
      .get()
      .then((data) => {
        setProfile({
          name: data.display_name,
          bio: data.bio ?? "",
          photo: data.photo_url ?? "",
          handle: data.handle ?? "",
          lanes: data.interests,
          location: data.location ?? "",
          country: data.country ?? "",
        });
        setOriginalHandle(data.handle ?? "");
      })
      .catch((err) =>
        setSaveError(errorMessage(err, "We couldn't load your profile.")),
      )
      .finally(() => setProfileLoaded(true));
    bankDetailsApi
      .get()
      .then((data) => {
        setBankDetail(data);
        setBankError("");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setBankDetail(null);
          setBankError("");
        } else {
          setBankError(errorMessage(err, "We couldn't load your payout account."));
        }
      });
    socialApi
      .accounts()
      .then((data) => {
        setSocials(data);
        setSocialError("");
      })
      .catch((err) => setSocialError(errorMessage(err, "We couldn't load your connected accounts.")));
    profileApi
      .getPreferences()
      .then((data) => setNotifPrefs(data.notifications))
      .catch(() =>
        setNotifError("We couldn't load your notification settings."),
      );

    const frame = window.requestAnimationFrame(() => {
      const params = new URLSearchParams(window.location.search);
      const social = params.get("social");
      if (!social) return;
      const ok = params.get("status") === "ok";
      setSocialNotice(
        ok
          ? `${platformLabel(social)} is connected. We'll read verified views from it.`
          : `We couldn't connect ${platformLabel(social)}${params.get("reason") ? ` (${params.get("reason")})` : ""}. Try again.`,
      );
      window.history.replaceState(
        {},
        "",
        `${window.location.pathname}#accounts`,
      );
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const wantedHandle = profile.handle.trim().toLowerCase();
  const handleNeedsCheck =
    profileLoaded && !!wantedHandle && wantedHandle !== originalHandle;
  const handleStatus: {
    state: "idle" | "checking" | "ok" | "taken";
    note: string;
  } = !handleNeedsCheck
    ? { state: "idle", note: "" }
    : handleCheck?.handle === wantedHandle
      ? handleCheck
      : { state: "checking", note: "Checking…" };

  useEffect(() => {
    if (!handleNeedsCheck) return;
    const timer = window.setTimeout(() => {
      handlesApi
        .availability(wantedHandle)
        .then((data) =>
          setHandleCheck(
            data.available
              ? {
                  handle: wantedHandle,
                  state: "ok",
                  note: `@${data.handle} is available`,
                }
              : {
                  handle: wantedHandle,
                  state: "taken",
                  note: data.reason ?? "That handle is taken.",
                },
          ),
        )
        .catch((err) =>
          setHandleCheck({
            handle: wantedHandle,
            state: "taken",
            note: errorMessage(
              err,
              "Use 3-30 lowercase letters, numbers or underscores.",
            ),
          }),
        );
    }, 400);
    return () => window.clearTimeout(timer);
  }, [wantedHandle, handleNeedsCheck]);

  const toggleNotif = (key: keyof NotificationSettings) => {
    if (!notifPrefs) return;
    const previous = notifPrefs;
    const updated = { ...notifPrefs, [key]: !notifPrefs[key] };
    setNotifPrefs(updated);
    setNotifError("");
    profileApi
      .updatePreferences({ notifications: { [key]: updated[key] } })
      .catch(() => {
        setNotifPrefs(previous);
        setNotifError("That change didn't save. Try again.");
      });
  };

  const saveProfile = async () => {
    setSaving(true);
    setSaveError("");
    try {
      let photoUploadId: string | undefined;
      let photo = profile.photo;
      if (photo.startsWith("data:")) {
        const upload = await uploadsApi.imageFromDataUrl(photo);
        photoUploadId = upload.id;
        photo = upload.url;
      }
      const handle = profile.handle.trim().toLowerCase();
      const updated = await creatorProfileApi.update({
        display_name: profile.name.trim(),
        bio: profile.bio.trim(),
        interests: profile.lanes,
        location: profile.location.trim(),
        ...(profile.country ? { country: profile.country } : {}),
        ...(handle && handle !== originalHandle ? { handle } : {}),
        ...(photoUploadId ? { photo_upload_id: photoUploadId } : {}),
      });
      setOriginalHandle(updated.handle ?? "");
      setProfile((current) => ({
        ...current,
        photo: updated.photo_url ?? photo,
        handle: updated.handle ?? current.handle,
      }));
      saveStoredProfile("creator", {
        name: updated.display_name,
        bio: updated.bio ?? "",
        photo: updated.photo_url ?? photo,
      });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2200);
    } catch (err) {
      setSaveError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const disconnect = async (platform: string) => {
    if (
      !window.confirm(
        `Disconnect ${platformLabel(platform)}? Clips on it stop collecting verified views until you reconnect.`,
      )
    )
      return;
    try {
      await socialApi.disconnect(platform);
      setSocials(await socialApi.accounts());
    } catch (err) {
      setSocialNotice(errorMessage(err));
    }
  };

  const toggleLane = (lane: string) =>
    setProfile((current) => ({
      ...current,
      lanes: current.lanes.includes(lane)
        ? current.lanes.filter((item) => item !== lane)
        : [...current.lanes, lane].slice(0, 12),
    }));

  const canSave =
    profile.name.trim().length >= 2 &&
    profile.lanes.length > 0 &&
    handleStatus.state !== "taken" &&
    handleStatus.state !== "checking";

  useEffect(() => {
    const ids = ["profile", "accounts", "payouts", "notifications"];
    const syncFromHash = () => {
      const id = window.location.hash.slice(1);
      setActiveSection(ids.includes(id) ? id : "profile");
    };
    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => {
      window.removeEventListener("hashchange", syncFromHash);
    };
  }, []);

  useEffect(() => {
    const index = document.querySelector<HTMLElement>(".settings-index");
    const link = index?.querySelector<HTMLElement>(
      `a[href="#${activeSection}"]`,
    );
    if (!index || !link) return;
    index.scrollTo({
      left: link.offsetLeft - (index.clientWidth - link.clientWidth) / 2,
      behavior: "smooth",
    });
  }, [activeSection]);

  const sectionLink = (id: string) => ({
    href: `#${id}`,
    className: activeSection === id ? "is-active" : "",
    onClick: () => setActiveSection(id),
    "aria-current": activeSection === id ? ("location" as const) : undefined,
  });
  return (
    <div className="dashboard-page settings-page">
      <PageHeading
        title="Settings"
        copy="Manage your profile, connected accounts, payout account and alerts."
      />
      <div className="settings-layout">
        <nav className="settings-index" aria-label="Settings sections">
          <a {...sectionLink("profile")}>
            <ProductIcon name="settings" /> Profile
          </a>
          <a {...sectionLink("accounts")}>
            <ProductIcon name="link" /> Social accounts
          </a>
          <a {...sectionLink("payouts")}>
            <ProductIcon name="bank" /> Payout account
          </a>
          <a {...sectionLink("notifications")}>
            <ProductIcon name="bell" /> Notifications
          </a>
          <Link href="/dashboard/verification">
            <ProductIcon name="shield" /> Verification
          </Link>
          <Link href="/dashboard/security">
            <ProductIcon name="shield" /> Security
          </Link>
          <Link href="/help">
            <ProductIcon name="brief" /> Help and support
          </Link>
        </nav>
        <div className="settings-sheets">
          <section id="profile" className="settings-sheet">
            <div className="settings-sheet__title">
              <div>
                <h2>Creator profile</h2>
                <p>What brands and leaderboards see.</p>
              </div>
              <ProfileAvatar
                profile={profile}
                fallback={initials(profile.name)}
                className="settings-avatar"
              />
            </div>
            {!profileLoaded ? (
              <ClippitLoader contained compact label="Loading your profile" />
            ) : (
              <>
                <div className="settings-profile-editor">
                  <ProfilePhotoPicker
                    value={profile.photo}
                    name={profile.name}
                    onChange={(photo) =>
                      setProfile((current) => ({ ...current, photo }))
                    }
                    compact
                  />
                  <div className="settings-fields">
                    <label>
                      <span>Display name</span>
                      <input
                        value={profile.name}
                        onChange={(event) =>
                          setProfile((current) => ({
                            ...current,
                            name: event.target.value.slice(0, 80),
                          }))
                        }
                      />
                    </label>
                    <label>
                      <span>Handle</span>
                      <div className="prefix-input">
                        <i>@</i>
                        <input
                          value={profile.handle}
                          placeholder="pick_a_handle"
                          onChange={(event) =>
                            setProfile((current) => ({
                              ...current,
                              handle: event.target.value
                                .toLowerCase()
                                .replace(/[^a-z0-9_]/g, "")
                                .slice(0, 30),
                            }))
                          }
                        />
                      </div>
                      {handleStatus.note && (
                        <small
                          className={`field-hint${handleStatus.state === "taken" ? " is-error" : ""}`}
                        >
                          {handleStatus.note}
                        </small>
                      )}
                      {!profile.handle && (
                        <small className="field-hint">
                          Pick a handle to get a public profile page.
                        </small>
                      )}
                    </label>
                    <label className="is-wide">
                      <span>Creator bio</span>
                      <textarea
                        value={profile.bio}
                        placeholder="What you make and who it's for"
                        onChange={(event) =>
                          setProfile((current) => ({
                            ...current,
                            bio: event.target.value.slice(0, 240),
                          }))
                        }
                      />
                    </label>
                    <fieldset className="is-wide settings-lanes">
                      <legend>
                        Content lanes{" "}
                        <small>(used to match you with campaigns)</small>
                      </legend>
                      <div>
                        {LANES.map((lane) => (
                          <button
                            type="button"
                            key={lane}
                            className={
                              profile.lanes.includes(lane) ? "is-selected" : ""
                            }
                            aria-pressed={profile.lanes.includes(lane)}
                            onClick={() => toggleLane(lane)}
                          >
                            {lane}
                          </button>
                        ))}
                      </div>
                    </fieldset>
                    <label>
                      <span>City or region</span>
                      <input
                        value={profile.location}
                        placeholder="Lagos"
                        onChange={(event) =>
                          setProfile((current) => ({
                            ...current,
                            location: event.target.value.slice(0, 80),
                          }))
                        }
                      />
                    </label>
                    <label>
                      <span>Country</span>
                      <select
                        value={profile.country}
                        onChange={(event) =>
                          setProfile((current) => ({
                            ...current,
                            country: event.target.value,
                          }))
                        }
                      >
                        <option value="">Choose a country</option>
                        {COUNTRIES.map(([code, name]) => (
                          <option key={code} value={code}>
                            {name}
                          </option>
                        ))}
                      </select>
                      <small className="field-hint">
                        Puts you on your country&apos;s leaderboard.
                      </small>
                    </label>
                  </div>
                </div>
                {saveError && (
                  <p className="form-error" role="alert">
                    {saveError}
                  </p>
                )}
                <div className="settings-profile-actions">
                  <button
                    className="lime-button"
                    type="button"
                    disabled={!canSave || saving}
                    onClick={saveProfile}
                  >
                    {saving ? (
                      "Saving…"
                    ) : saved ? (
                      <>
                        <ProductIcon name="check" /> Changes saved
                      </>
                    ) : (
                      <>
                        Save profile
                        <ProductIcon name="arrow" />
                      </>
                    )}
                  </button>
                  <Link className="ink-button" href="/dashboard/profile">
                    View public profile
                    <ProductIcon name="eye" />
                  </Link>
                </div>
              </>
            )}
          </section>

          <section id="accounts" className="settings-sheet">
            <div className="settings-sheet__title">
              <div>
                <h2>Connected socials</h2>
                <p>We read views directly from these platforms.</p>
              </div>
              <ProductIcon name="shield" />
            </div>
            {socialNotice && (
              <p className="form-notice" role="status">
                {socialNotice}
              </p>
            )}
            {socialError && (
              <p className="form-error" role="alert">
                {socialError}
              </p>
            )}
            {!socials && !socialError && (
              <ClippitLoader contained compact label="Checking your accounts" />
            )}
            {socials?.map((account) =>
              account.connected ? (
                <div
                  key={account.platform}
                  className="social-account is-connected"
                >
                  <span>
                    <ProductIcon name={platformIconName(account.platform)} />
                  </span>
                  <p>
                    <strong>{platformLabel(account.platform)}</strong>
                    <small>
                      {account.handle
                        ? `@${account.handle.replace(/^@/, "")}`
                        : (account.display_name ?? "Connected")}{" "}
                      · Last checked {timeAgo(account.last_checked_at)}
                    </small>
                  </p>
                  <b>
                    <i /> Connected
                  </b>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => disconnect(account.platform)}
                  >
                    Disconnect
                  </button>
                </div>
              ) : (
                <div key={account.platform} className="social-account">
                  <span>
                    <ProductIcon name={platformIconName(account.platform)} />
                  </span>
                  <p>
                    <strong>{platformLabel(account.platform)}</strong>
                    <small>
                      {account.connectable
                        ? `Connect to join ${platformLabel(account.platform)} briefs.`
                        : "Coming soon"}
                    </small>
                  </p>
                  {account.connectable ? (
                    <a
                      className="connect-button"
                      href={socialApi.connectUrl(account.platform)}
                    >
                      Connect
                      <ProductIcon name="arrow" />
                    </a>
                  ) : (
                    <b>Soon</b>
                  )}
                </div>
              ),
            )}
          </section>

          <section id="payouts" className="settings-sheet payout-sheet">
            <div className="settings-sheet__title">
              <div>
                <h2>Payout account</h2>
                <p>Payable money lands here.</p>
              </div>
              <ProductIcon name="bank" />
            </div>
            {bankError ? (
              <ClippitEmptyState
                tone="danger"
                icon="bank"
                title="We couldn't load your payout account"
                copy={bankError}
                action={<Link className="ink-button" href="/dashboard/payout-account">Open payout account<ProductIcon name="arrow" /></Link>}
              />
            ) : bankDetail === undefined ? (
              <ClippitLoader contained compact label="Checking your payout account" />
            ) : bankDetail ? (
              <div className="bank-account">
                <span>
                  <ProductIcon name="bank" />
                </span>
                <p>
                  <small>{bankDetail.bank_name}</small>
                  <strong>{bankDetail.account_number_masked}</strong>
                  {bankDetail.account_name && <b>{bankDetail.account_name}</b>}
                </p>
                <i>{bankDetail.verified ? "Verified" : "Needs verification"}</i>
                <Link
                  className="bank-edit-link"
                  href="/dashboard/payout-account"
                >
                  Change
                  <ProductIcon name="arrow" />
                </Link>
              </div>
            ) : (
              <div className="bank-account bank-account--empty">
                <span>
                  <ProductIcon name="bank" />
                </span>
                <p>
                  <small>No payout account</small>
                  <strong>Add a bank account to withdraw earnings</strong>
                </p>
                <Link className="lime-button" href="/dashboard/payout-account">
                  Add account
                  <ProductIcon name="arrow" />
                </Link>
              </div>
            )}
            <p className="security-note">
              <ProductIcon name="shield" /> Changing your account means
              verifying it again before your next withdrawal.
            </p>
          </section>

          <section id="notifications" className="settings-sheet">
            <div className="settings-sheet__title">
              <div>
                <h2>Notifications</h2>
                <p>Choose which events send a notification.</p>
              </div>
              <ProductIcon name="bell" />
            </div>
            {notifError && (
              <p className="form-error" role="alert">
                {notifError}
              </p>
            )}
            {notifPrefs &&
              NOTIFICATION_KEYS.map(({ key, label, note }) => (
                <label className="toggle-row" key={key}>
                  <span>
                    <strong>{label}</strong>
                    <small>{note}</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={notifPrefs[key]}
                    onChange={() => toggleNotif(key)}
                  />
                  <i />
                </label>
              ))}
          </section>
          <section className="settings-sheet">
            <div className="settings-sheet__title">
              <div>
                <h2>Account records</h2>
                <p>Verification, support and your Clippit data.</p>
              </div>
              <ProductIcon name="brief" />
            </div>
            <div className="settings-profile-actions">
              <Link className="lime-button" href="/dashboard/verification">
                Identity verification
                <ProductIcon name="arrow" />
              </Link>
              <Link className="ink-button" href="/account/data">
                Account and data
                <ProductIcon name="arrow" />
              </Link>
              <Link className="ink-button" href="/support/tickets">
                Support tickets
                <ProductIcon name="arrow" />
              </Link>
              <Link className="ink-button" href="/disputes">
                Disputes
                <ProductIcon name="arrow" />
              </Link>
              <Link className="ink-button" href="/legal">
                Legal centre
                <ProductIcon name="arrow" />
              </Link>
              <Link className="ink-button" href="/account/delete">
                Delete account
                <ProductIcon name="arrow" />
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
