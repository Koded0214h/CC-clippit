"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ProfileAvatar, ProfilePhotoPicker, saveStoredProfile, useStoredProfile, type StoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { campaigns, leaderboard, type Campaign } from "@/lib/product";
import { campaignsApi, type CampaignOut } from "@/lib/api/campaigns";
import { earningsApi, type LeaderRow } from "@/lib/api/earnings";
import { creatorApi } from "@/lib/api/creator";
import { creatorProfileApi } from "@/lib/api/social";
import { bankDetailsApi, type BankAccountOut } from "@/lib/api/bankDetails";

function campaignOutToLocal(c: CampaignOut): Campaign {
  return {
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
    status: (c.feed_status as Campaign["status"]) ?? "Open",
    minimumViews: c.payout_rule?.min_views_threshold ?? 1000,
    creatorCap: c.payout_rule?.cap_amount ?? 0,
    brief: c.description,
    mustDo: c.rules.filter((r) => r.kind === "must").map((r) => r.text),
    mustAvoid: c.rules.filter((r) => r.kind === "avoid").map((r) => r.text),
  };
}

const CREATOR_PROFILE_FALLBACK: StoredProfile = {
  name: "Tobi On Cam",
  bio: "Comedy, food and everyday Lagos stories. I make the ad feel like the timeline.",
  photo: "",
};

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

function platformIcon(platform: string): ProductIconName {
  if (platform === "YouTube") return "youtube";
  if (platform === "Instagram") return "instagram";
  return "tiktok";
}

function PlatformMarks({ platforms }: { platforms: string[] }) {
  return (
    <span className="platform-marks" aria-label={platforms.join(", ")}>
      {platforms.map((platform) => (
        <i key={platform} title={platform}><ProductIcon name={platformIcon(platform)} /></i>
      ))}
    </span>
  );
}

function Countdown({ campaign }: { campaign: Campaign }) {
  return (
    <span className="countdown">
      <ProductIcon name="clock" />
      <strong><AnimatedNumber value={campaign.daysLeft} suffix="d " duration={800} /><AnimatedNumber value={campaign.hoursLeft} suffix="h" duration={900} delay={90} /></strong>
      <small>left</small>
    </span>
  );
}

function AnimatedMoney({ value }: { value: number }) {
  return <AnimatedNumber value={value} format="money" />;
}

function LiveDuration({ campaign, compact = false }: { campaign: Campaign; compact?: boolean }) {
  const [seconds, setSeconds] = useState(59 * 60 + 59);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSeconds((current) => (current > 0 ? current - 1 : 59 * 60 + 59));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return (
    <span className="live-duration" role="timer" aria-label={`${campaign.daysLeft} days, ${campaign.hoursLeft} hours left`}>
      <b>{String(campaign.daysLeft).padStart(2, "0")}</b><small>d</small>
      <b>{String(campaign.hoursLeft).padStart(2, "0")}</b><small>h</small>
      {!compact && <><b>{String(minutes).padStart(2, "0")}</b><small>m</small><b>{String(remainder).padStart(2, "0")}</b><small>s</small></>}
    </span>
  );
}

function CampaignVitals({ campaign, includeMinimum = false }: { campaign: Campaign; includeMinimum?: boolean }) {
  const potLevel = Math.round((campaign.remaining / campaign.pot) * 100);
  const style = { "--pot-level": `${potLevel}%` } as CSSProperties;
  return (
    <div className={`campaign-vitals${includeMinimum ? " campaign-vitals--detail" : ""}`} style={style}>
      <div className="campaign-vital campaign-vital--rate">
        <span className="vital-icon"><ProductIcon name="spark" /></span>
        <div><small>Live rate</small><strong><AnimatedMoney value={campaign.rate} /></strong><p>per 1K verified views</p></div>
      </div>
      <div className="campaign-vital campaign-vital--pot">
        <Image className="campaign-vital__generated-art" src="/assets/illustrations/clippit-icons/funding-pot.webp" alt="" width={112} height={112} aria-hidden="true" />
        <div className="pot-label"><small>Money still in the pot</small><strong><AnimatedMoney value={campaign.remaining} /></strong></div>
        <div className="pot-meter" aria-label={`${potLevel}% of campaign pot remains`}><span className="pot-meter__fill" /><i className="pot-meter__proof"><ProductIcon name="shield" /></i></div>
        <p><b><AnimatedNumber value={potLevel} suffix="%" duration={900} /></b> of <AnimatedMoney value={campaign.pot} /> remains</p>
      </div>
      <div className="campaign-vital campaign-vital--time">
        <span className="time-orbit"><ProductIcon name="clock" /></span>
        <div><small>Campaign closes in</small><LiveDuration campaign={campaign} compact={!includeMinimum} /><p>20 Sep · 18:00 WAT</p></div>
      </div>
      {includeMinimum && (
        <div className="campaign-vital campaign-vital--minimum">
          <ProductIcon name="play" />
          <div><small>Starts earning at</small><strong><AnimatedNumber value={campaign.minimumViews} format="compact" /></strong><p>verified views</p></div>
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
          {linkLabel ?? "See all"}<ProductIcon name="arrow" />
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
    if (!video || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver(([entry]) => {
      setActive(entry.isIntersecting);
    }, { threshold: 0.3 });
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
    <video ref={videoRef} muted loop playsInline preload="none" poster={poster} aria-label="Creator setting up a phone to record">
      {active && <source src={src} type="video/mp4" />}
    </video>
  );
}

function CreatorFieldNotes() {
  return (
    <section className="creator-field-notes" aria-labelledby="creator-field-notes-title">
      <div className="creator-field-notes__heading">
        <div>
          <h2 id="creator-field-notes-title">Content references</h2>
        </div>
        <p>Use these references for framing, lighting and pacing.</p>
      </div>
      <div className="creator-reel">
        {creatorFieldNotes.map((item, index) => (
          <article key={item.src + item.kicker} className={`creator-reel__card${index === 0 ? " creator-reel__card--lead" : ""}`}>
            <div className="creator-reel__media">
              {item.type === "video" ? (
                <AutoPreviewVideo src={item.src} poster={item.poster} />
              ) : (
                <Image src={item.src} alt="Creator filming content in a home studio" fill sizes="(max-width: 700px) 78vw, 24vw" />
              )}
              <span className="creator-reel__number">0{index + 1}</span>
              {item.type === "video" && <span className="creator-reel__live"><i /> Playing now</span>}
            </div>
            <div className="creator-reel__copy">
              <p>{item.kicker}</p>
              <h3>{item.title}</h3>
              <span><ProductIcon name={item.type === "video" ? "play" : "camera"} />{item.lane}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

type BoardRow = { rank: number; name: string; handle: string; views: number; earned: number; is_me?: boolean };

function MiniLeaderboard() {
  const [board, setBoard] = useState<BoardRow[]>(leaderboard.slice(0, 4).map((r) => ({ ...r, is_me: r.name === "Tobi On Cam" })));
  useEffect(() => {
    earningsApi.leaderboard({ period: "week" }).then((data) => {
      if (data.items.length > 0) {
        setBoard(data.items.slice(0, 4).map((r) => ({
          rank: r.rank,
          name: r.name,
          handle: r.handle ?? "",
          views: r.views,
          earned: r.earned,
          is_me: r.is_me,
        })));
      }
    }).catch(() => undefined);
  }, []);
  return (
    <aside className="mini-leaderboard">
      <SectionTitle title="Weekly leaderboard" href="/dashboard/leaderboard" linkLabel="Full board" />
      {board.map((person) => (
        <div key={person.rank} className={person.is_me ? "is-you" : ""}>
          <span><AnimatedNumber value={person.rank} padStart={2} duration={600} /></span>
          <i>{person.name.slice(0, 2).toUpperCase()}</i>
          <p><strong>{person.name}</strong><small>{person.handle}</small></p>
          <b><AnimatedNumber value={person.views} format="compact" /></b>
        </div>
      ))}
    </aside>
  );
}

export function DashboardHome() {
  const [feature, setFeature] = useState<Campaign>(campaigns[0]);
  const [earnings, setEarnings] = useState({ total: 42850, payable: 18400, inHold: 24450, paidAllTime: 126700, addedThisWeek: 6200, activeClips: 3 });
  const [tapeCampaigns, setTapeCampaigns] = useState<Campaign[]>(campaigns.slice(1));

  useEffect(() => {
    creatorApi.overview().then((data) => {
      if (data.closing_soon) setFeature(campaignOutToLocal(data.closing_soon));
      setEarnings({
        total: data.earnings.total_accrued,
        payable: data.earnings.payable,
        inHold: data.earnings.in_hold,
        paidAllTime: data.earnings.paid_all_time,
        addedThisWeek: data.earnings.added_this_week,
        activeClips: data.earnings.active_clips,
      });
    }).catch(() => undefined);
    campaignsApi.list({ feed: "all", page_size: 6 }).then((data) => {
      if (data.items.length > 0) setTapeCampaigns(data.items.map(campaignOutToLocal));
    }).catch(() => undefined);
  }, []);

  return (
    <div className="dashboard-page dashboard-home">
      <PageHeading
        title="One campaign closes soon"
        copy="No long thing closes in 4 days. Two new campaigns match your content preferences."
      />

      <section className="dashboard-lead" aria-label="Featured campaign and earnings">
        <article className="feature-campaign">
          <Image src={feature.image} alt="Creator filming a campaign clip" fill sizes="(max-width: 900px) 100vw, 58vw" priority />
          <div className="feature-campaign__wash" />
          <div className="feature-campaign__top">
            <span className="status-chip"><i /> {feature.status}</span>
            <div className="campaign-top-signals">
              <span className="mobile-time-chip"><ProductIcon name="clock" /> {feature.daysLeft}d {feature.hoursLeft}h left</span>
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
            <Link href={`/dashboard/campaigns/${feature.slug}`} className="lime-button">
              Read the brief<ProductIcon name="arrow" />
            </Link>
          </div>
        </article>

        <aside className="money-receipt">
          <div className="money-receipt__head">
            <div><Image className="money-receipt__generated-art" src="/assets/illustrations/clippit-icons/payout-wallet.webp" alt="" width={36} height={36} aria-hidden="true" /><span>Your money</span></div>
            <small>15 Sep 2026</small>
          </div>
          <div className="money-total">
            <span>Total accrued</span>
            <strong><AnimatedMoney value={earnings.total} /></strong>
            <small><b>Across {earnings.activeClips} clips</b><i /><span><AnimatedMoney value={earnings.addedThisWeek} /> added this week</span></small>
          </div>
          <dl>
            <div><dt>Payable now</dt><dd><AnimatedMoney value={earnings.payable} /></dd></div>
            <div><dt>In 5-day hold</dt><dd><AnimatedMoney value={earnings.inHold} /></dd></div>
            <div><dt>Paid all time</dt><dd><AnimatedMoney value={earnings.paidAllTime} /></dd></div>
          </dl>
          <Link href="/dashboard/withdraw" className="ink-button">
            Withdraw payable money<ProductIcon name="arrow" />
          </Link>
          <p><ProductIcon name="shield" /> Earnings use platform-reported views.</p>
        </aside>
      </section>

      <section className="dashboard-section">
        <SectionTitle title="New campaigns" href="/dashboard/campaigns" />
        <div className="campaign-tape">
          {tapeCampaigns.map((campaign) => (
            <Link key={campaign.slug} href={`/dashboard/campaigns/${campaign.slug}`} className="campaign-tape__item">
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
                <strong><AnimatedMoney value={campaign.rate} /></strong>
                <span>/ 1K views</span>
              </div>
              <div className="campaign-tape__pot">
                <small>Pot left</small>
                <strong><AnimatedMoney value={campaign.remaining} /></strong>
                <i><span style={{ width: `${(campaign.remaining / campaign.pot) * 100}%` }} /></i>
              </div>
              <Countdown campaign={campaign} />
              <span className="round-arrow"><ProductIcon name="arrow" /></span>
            </Link>
          ))}
        </div>
      </section>

      <CreatorFieldNotes />

      <section className="dashboard-bottom-grid">
        <div className="proof-stream">
          <SectionTitle title="Recent clip activity" />
          <div className="proof-stream__line" aria-hidden="true" />
          <article>
            <span className="proof-node is-live"><ProductIcon name="play" /></span>
            <div><small>Posted</small><strong>Roommate ate my last pack</strong><p>Indomie · TikTok</p></div>
            <b><AnimatedNumber value={43200} format="compact" /> <small>views</small></b>
          </article>
          <article>
            <span className="proof-node"><ProductIcon name="shield" /></span>
            <div><small>Checking</small><strong>The transfer plot twist</strong><p>PalmPay · YouTube</p></div>
            <b><AnimatedNumber value={2} suffix=" min" duration={650} /> <small>ago</small></b>
          </article>
          <article>
            <span className="proof-node is-money"><ProductIcon name="wallet" /></span>
            <div><small>Payable</small><strong>Main character entrance</strong><p>Gbedu Records · Instagram</p></div>
            <b><AnimatedMoney value={9600} /></b>
          </article>
        </div>

        <MiniLeaderboard />

      </section>
    </div>
  );
}

const campaignFilters = ["All", "For you", "Closing soon", "Joined"];
const feedMap: Record<string, string> = { "All": "all", "For you": "for_you", "Closing soon": "closing_soon", "Joined": "joined" };

export function CampaignDirectory() {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [allCampaigns, setAllCampaigns] = useState<Campaign[]>(campaigns);

  useEffect(() => {
    const feed = feedMap[filter] ?? "all";
    campaignsApi.list({ feed }).then((data) => {
      if (data.items.length > 0) setAllCampaigns(data.items.map(campaignOutToLocal));
    }).catch(() => undefined);
  }, [filter]);

  const visible = useMemo(() => {
    const normalized = query.toLowerCase().trim();
    return allCampaigns.filter((campaign) => {
      const matchesQuery = !normalized || [campaign.brand, campaign.title, campaign.category].join(" ").toLowerCase().includes(normalized);
      return matchesQuery;
    });
  }, [allCampaigns, query]);

  return (
    <div className="dashboard-page campaigns-page">
      <PageHeading
        title="Campaigns"
        copy="Compare rates, remaining budgets and deadlines before joining."
      />
      <div className="campaign-tools">
        <div className="campaign-filters" aria-label="Campaign filters">
          {campaignFilters.map((item) => (
            <button key={item} type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)}>
              {item}
            </button>
          ))}
        </div>
        <label className="campaign-search">
          <ProductIcon name="search" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search campaigns" />
        </label>
      </div>

      <div className="campaign-ledger">
        <div className="campaign-ledger__header">
          <span>Campaign</span><span>Rate</span><span>Available money</span><span>Closes</span><span />
        </div>
        {visible.map((campaign) => (
          <Link key={campaign.slug} href={`/dashboard/campaigns/${campaign.slug}`} className="campaign-ledger__row">
            <div className="ledger-campaign">
              <span className="ledger-image"><Image src={campaign.image} alt="" fill sizes="110px" /></span>
              <span><small>{campaign.brand} · {campaign.category}</small><strong>{campaign.title}</strong><i>{campaign.status}</i></span>
            </div>
            <div className="ledger-rate"><strong><AnimatedMoney value={campaign.rate} /></strong><small>per 1K verified views</small></div>
            <div className="ledger-pot"><strong><AnimatedMoney value={campaign.remaining} /></strong><span><i style={{ width: `${(campaign.remaining / campaign.pot) * 100}%` }} /></span><small>of <AnimatedMoney value={campaign.pot} /></small></div>
            <Countdown campaign={campaign} />
            <span className="round-arrow"><ProductIcon name="arrow" /></span>
          </Link>
        ))}
        {!visible.length && (
          <div className="campaign-empty">
            <ProductIcon name="search" />
            <h2>No campaigns match those filters.</h2>
            <p>Try another title, brand or category.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function CampaignDetail({ campaign: initialCampaign }: { campaign: Campaign }) {
  const [campaign, setCampaign] = useState(initialCampaign);
  const [joined, setJoined] = useState(initialCampaign.status === "Joined");
  const [sideLeaders, setSideLeaders] = useState(leaderboard.slice(0, 3).map((r) => ({ ...r, is_me: r.name === "Tobi On Cam" })));

  useEffect(() => {
    campaignsApi.get(initialCampaign.slug).then((data) => {
      setCampaign(campaignOutToLocal(data));
      if (data.joined !== null) setJoined(!!data.joined);
    }).catch(() => undefined);
    earningsApi.leaderboard({ campaign: initialCampaign.slug }).then((data) => {
      if (data.items.length > 0) setSideLeaders(data.items.slice(0, 3).map((r) => ({ ...r, handle: r.handle ?? "", is_me: r.is_me })));
    }).catch(() => undefined);
  }, [initialCampaign.slug]);

  return (
    <div className="dashboard-page campaign-detail-page">
      <Link className="product-back" href="/dashboard/campaigns"><ProductIcon name="chevron" /> All campaigns</Link>
      <section className="campaign-detail-hero">
        <Image src={campaign.image} alt="Campaign visual" fill priority sizes="(max-width: 900px) 100vw, 70vw" />
        <div className="campaign-detail-hero__wash" />
        <div className="campaign-detail-hero__top">
          <span className="status-chip"><i /> {joined ? "Joined" : campaign.status}</span>
          <div className="campaign-top-signals">
            <span className="mobile-time-chip"><ProductIcon name="clock" /> {campaign.daysLeft}d {campaign.hoursLeft}h left</span>
            <PlatformMarks platforms={campaign.platforms} />
          </div>
        </div>
        <div className="campaign-detail-hero__copy">
          <p>{campaign.brand}</p>
          <h1>{campaign.title}</h1>
          <span>{campaign.line}</span>
        </div>
        <div className="campaign-detail-hero__action">
          {joined
            ? <Link className="lime-button" href={`/dashboard/campaigns/${campaign.slug}/submit`}>Submit your clip<ProductIcon name="arrow" /></Link>
            : <button className="lime-button" type="button" onClick={() => setJoined(true)}>Join campaign<ProductIcon name="arrow" /></button>}
        </div>
      </section>

      <CampaignVitals campaign={campaign} includeMinimum />

      <div className="campaign-detail-grid">
        <div className="campaign-detail-main">
          <section className="brief-sheet">
            <div className="brief-sheet__heading"><span>Brief</span><small>Read this before you film</small></div>
            <h2>Campaign brief</h2>
            <p className="brief-lead">{campaign.brief}</p>
            <div className="brief-rule-columns">
              <div>
                <h3><ProductIcon name="check" /> Your clip must</h3>
                <ol>{campaign.mustDo.map((rule) => <li key={rule}><span>{campaign.mustDo.indexOf(rule) + 1}</span><p>{rule}</p></li>)}</ol>
              </div>
              <div className="avoid-list">
                <h3><ProductIcon name="shield" /> Keep out</h3>
                <ul>{campaign.mustAvoid.map((rule) => <li key={rule}>{rule}</li>)}</ul>
              </div>
            </div>
          </section>

          <section className="campaign-materials">
            <SectionTitle title="Campaign materials" />
            <div>
              <button type="button"><span><ProductIcon name="play" /></span><p><strong>Campaign sound</strong><small>Official audio · 00:24</small></p><ProductIcon name="arrow" /></button>
              <button type="button"><span><ProductIcon name="link" /></span><p><strong>Visual reference</strong><small>Mood and pacing guide</small></p><ProductIcon name="arrow" /></button>
            </div>
          </section>
        </div>

        <aside className="campaign-detail-aside">
          <section className="plain-rules">
            <h2>Earning rules</h2>
            <dl>
              <div><dt>Creator cap</dt><dd><AnimatedMoney value={campaign.creatorCap} /></dd></div>
              <div><dt>Holding period</dt><dd><AnimatedNumber value={5} suffix=" days" duration={700} /></dd></div>
              <div><dt>View counting</dt><dd>Full thousands only</dd></div>
              <div><dt>Platforms</dt><dd>{campaign.platforms.join(" + ")}</dd></div>
              <div><dt>Content review</dt><dd>Usually under <AnimatedNumber value={5} suffix=" min" duration={700} /></dd></div>
            </dl>
            <p><ProductIcon name="shield" /> Views come from the platforms. Partial thousands wait until the next full 1,000.</p>
          </section>

          <section className="campaign-leaders">
            <SectionTitle title="Campaign leaderboard" href="/dashboard/leaderboard" linkLabel="View board" />
            {sideLeaders.map((person) => (
              <div key={person.rank}><span><AnimatedNumber value={person.rank} duration={600} /></span><i>{person.name.slice(0, 2).toUpperCase()}</i><p><strong>{person.name}</strong><small><AnimatedNumber value={person.views} format="compact" /> views</small></p><b><AnimatedMoney value={person.earned} /></b></div>
            ))}
          </section>
        </aside>
      </div>

      <div className="mobile-campaign-action">
        <div><small><AnimatedMoney value={campaign.rate} /> / 1K views</small><strong><AnimatedNumber value={campaign.daysLeft} suffix="d " duration={800} /><AnimatedNumber value={campaign.hoursLeft} suffix="h left" duration={900} delay={90} /></strong></div>
        {joined
          ? <Link href={`/dashboard/campaigns/${campaign.slug}/submit`}>Submit clip<ProductIcon name="arrow" /></Link>
          : <button type="button" onClick={() => setJoined(true)}>Join campaign<ProductIcon name="arrow" /></button>}
      </div>
    </div>
  );
}

export function LeaderboardScreen() {
  const [board, setBoard] = useState<BoardRow[]>(leaderboard.map((r) => ({ ...r, is_me: r.name === "Tobi On Cam" })));
  const [updatedAt, setUpdatedAt] = useState("2 minutes ago");

  useEffect(() => {
    earningsApi.leaderboard({ period: "week" }).then((data) => {
      if (data.items.length > 0) {
        setBoard(data.items.map((r) => ({ rank: r.rank, name: r.name, handle: r.handle ?? "", views: r.views, earned: r.earned, is_me: r.is_me })));
        try { setUpdatedAt(new Date(data.updated_at).toLocaleTimeString()); } catch { /* keep default */ }
      }
    }).catch(() => undefined);
  }, []);

  const podium = [board[1], board[0], board[2]].filter(Boolean);

  return (
    <div className="dashboard-page leaderboard-page">
      <PageHeading title="Leaderboard" copy="Weekly ranking by verified views across active campaigns." />
      <section className="podium-board">
        <div className="podium-copy"><h2>Top creators this week</h2><p>Updated after each verified view check.</p></div>
        {podium.map((person) => (
          <article key={person.rank} className={`podium-person podium-person--${person.rank}`}>
            <span><AnimatedNumber value={person.rank} duration={600} /></span>
            <i>{person.name.slice(0, 2).toUpperCase()}</i>
            <strong>{person.name}</strong>
            <small><AnimatedNumber value={person.views} format="compact" /> verified views</small>
            <b><AnimatedMoney value={person.earned} /></b>
          </article>
        ))}
      </section>

      <section className="ranking-sheet">
        <div className="ranking-sheet__head"><h2>All creators</h2><span>Updated {updatedAt}</span></div>
        <div className="ranking-row ranking-row--labels"><span>Rank</span><span>Creator</span><span>Verified views</span><span>Earned</span></div>
        {board.map((person) => (
          <div key={person.rank} className={`ranking-row${person.is_me ? " is-you" : ""}`}>
            <span className="rank-number"><AnimatedNumber value={person.rank} padStart={2} duration={600} /></span>
            <span className="rank-creator"><i>{person.name.slice(0, 2).toUpperCase()}</i><span><strong>{person.name}</strong><small>{person.handle}</small></span>{person.is_me && <b>You</b>}</span>
            <strong><AnimatedNumber value={person.views} format="compact" /></strong>
            <strong className="rank-money"><AnimatedMoney value={person.earned} /></strong>
          </div>
        ))}
      </section>
    </div>
  );
}

export function SettingsScreen() {
  const [saved, setSaved] = useState(false);
  const [activeSection, setActiveSection] = useState("profile");
  const storedProfile = useStoredProfile("creator", CREATOR_PROFILE_FALLBACK);
  const [profile, setProfile] = useState(CREATOR_PROFILE_FALLBACK);
  const [bankDetail, setBankDetail] = useState<BankAccountOut | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setProfile(storedProfile));
    return () => window.cancelAnimationFrame(frame);
  }, [storedProfile]);

  useEffect(() => {
    creatorProfileApi.get().then((data) => {
      setProfile((current) => ({
        ...current,
        name: data.display_name || current.name,
        bio: data.bio || current.bio,
        photo: data.photo_url || current.photo,
      }));
    }).catch(() => undefined);
    bankDetailsApi.get().then(setBankDetail).catch(() => undefined);
  }, []);

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
    const link = index?.querySelector<HTMLElement>(`a[href="#${activeSection}"]`);
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
    "aria-current": activeSection === id ? "location" as const : undefined,
  });
  return (
    <div className="dashboard-page settings-page">
      <PageHeading  title="Settings" copy="Manage your profile, connected accounts, payout account and alerts." />
      <div className="settings-layout">
        <nav className="settings-index" aria-label="Settings sections">
          <a {...sectionLink("profile")}><ProductIcon name="settings" /> Profile</a>
          <a {...sectionLink("accounts")}><ProductIcon name="link" /> Social accounts</a>
          <a {...sectionLink("payouts")}><ProductIcon name="bank" /> Payout account</a>
          <a {...sectionLink("notifications")}><ProductIcon name="bell" /> Notifications</a>
          <Link href="/dashboard/verification"><ProductIcon name="shield" /> Verification</Link>
          <Link href="/dashboard/security"><ProductIcon name="shield" /> Security</Link>
          <Link href="/help"><ProductIcon name="brief" /> Help and support</Link>
        </nav>
        <div className="settings-sheets">
          <section id="profile" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Creator profile</h2><p>What brands and leaderboards see.</p></div><ProfileAvatar profile={profile} fallback="TO" className="settings-avatar" /></div>
            <div className="settings-profile-editor">
              <ProfilePhotoPicker value={profile.photo} name={profile.name} onChange={(photo) => setProfile((current) => ({ ...current, photo }))} compact />
              <div className="settings-fields">
              <label><span>Display name</span><input value={profile.name} onChange={(event) => setProfile((current) => ({ ...current, name: event.target.value.slice(0, 40) }))} /></label>
              <label><span>Handle</span><div className="prefix-input"><i>@</i><input defaultValue="tobioncam" /></div></label>
              <label className="is-wide"><span>Creator bio</span><textarea value={profile.bio} onChange={(event) => setProfile((current) => ({ ...current, bio: event.target.value.slice(0, 180) }))} /></label>
              <label><span>Primary lane</span><select defaultValue="Comedy"><option>Comedy</option><option>Lifestyle</option><option>Food</option><option>Music</option></select></label>
              <label><span>Location</span><input defaultValue="Lagos, Nigeria" /></label>
              </div>
            </div>
            <div className="settings-profile-actions"><button className="lime-button" type="button" disabled={profile.name.trim().length < 2 || profile.bio.trim().length < 2} onClick={() => { const clean = { ...profile, name: profile.name.trim(), bio: profile.bio.trim() }; saveStoredProfile("creator", clean); creatorProfileApi.update({ display_name: clean.name, bio: clean.bio }).catch(() => undefined); setSaved(true); window.setTimeout(() => setSaved(false), 2200); }}>{saved ? <><ProductIcon name="check" /> Changes saved</> : <>Save profile<ProductIcon name="arrow" /></>}</button><Link className="ink-button" href="/dashboard/profile">View public profile<ProductIcon name="eye" /></Link></div>
          </section>

          <section id="accounts" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Connected socials</h2><p>We read views directly from these platforms.</p></div><ProductIcon name="shield" /></div>
            <div className="social-account is-connected"><span><ProductIcon name="tiktok" /></span><p><strong>TikTok</strong><small>@tobioncam · Last checked 2 min ago</small></p><b><i /> Connected</b><button type="button"><ProductIcon name="more" /></button></div>
            <div className="social-account is-connected"><span><ProductIcon name="instagram" /></span><p><strong>Instagram</strong><small>@tobioncam · Last checked 4 min ago</small></p><b><i /> Connected</b><button type="button"><ProductIcon name="more" /></button></div>
            <div className="social-account"><span><ProductIcon name="youtube" /></span><p><strong>YouTube</strong><small>Add a channel to join YouTube briefs.</small></p><Link className="connect-button" href="/dashboard/accounts">Connect<ProductIcon name="arrow" /></Link></div>
          </section>

          <section id="payouts" className="settings-sheet payout-sheet">
            <div className="settings-sheet__title"><div><h2>Payout account</h2><p>Payable money lands here.</p></div><ProductIcon name="bank" /></div>
            {bankDetail ? (
              <div className="bank-account"><span><ProductIcon name="bank" /></span><p><small>{bankDetail.bank_name}</small><strong>{bankDetail.account_number_masked}</strong>{bankDetail.account_name && <b>{bankDetail.account_name}</b>}</p><i>{bankDetail.verified ? "Verified" : "Unverified"}</i><Link className="bank-edit-link" href="/dashboard/payout-account">Change<ProductIcon name="arrow" /></Link></div>
            ) : (
              <div className="bank-account bank-account--empty"><span><ProductIcon name="bank" /></span><p><small>No payout account</small><strong>Add a bank account to withdraw earnings</strong></p><Link className="lime-button" href="/dashboard/payout-account">Add account<ProductIcon name="arrow" /></Link></div>
            )}
            <p className="security-note"><ProductIcon name="shield" /> Account changes trigger a security review before the next withdrawal.</p>
          </section>

          <section id="notifications" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Notifications</h2><p>Choose which events send a notification.</p></div><ProductIcon name="bell" /></div>
            {["New campaigns in my lanes", "Submission verdicts", "Earnings become payable", "Campaign closing reminders"].map((label, index) => (
              <label className="toggle-row" key={label}><span><strong>{label}</strong><small>{index === 0 ? "Matched campaigns only." : "Delivered by email and in your Clippit inbox."}</small></span><input type="checkbox" defaultChecked={index !== 3} /><i /></label>
            ))}
          </section>
          <section className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Account records</h2><p>Verification, support and your Clippit data.</p></div><ProductIcon name="brief" /></div>
            <div className="settings-profile-actions"><Link className="lime-button" href="/dashboard/verification">Identity verification<ProductIcon name="arrow" /></Link><Link className="ink-button" href="/account/data">Account and data<ProductIcon name="arrow" /></Link><Link className="ink-button" href="/support/tickets">Support tickets<ProductIcon name="arrow" /></Link><Link className="ink-button" href="/disputes">Disputes<ProductIcon name="arrow" /></Link><Link className="ink-button" href="/legal">Legal centre<ProductIcon name="arrow" /></Link><Link className="ink-button" href="/account/delete">Delete account<ProductIcon name="arrow" /></Link></div>
          </section>
        </div>
      </div>
    </div>
  );
}
