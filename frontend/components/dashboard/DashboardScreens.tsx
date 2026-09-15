"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { campaigns, compactNumber, leaderboard, money, type Campaign } from "@/lib/product";

function PageHeading({
  title,
  copy,
  note,
}: {
  title: string;
  copy: string;
  note?: string;
}) {
  return (
    <header className="page-heading">
      <div>
        {note && <p className="marker-label">{note}</p>}
        <h1>{title}</h1>
        <p>{copy}</p>
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
      <strong>{campaign.daysLeft}d {campaign.hoursLeft}h</strong>
      <small>left</small>
    </span>
  );
}

function useCountUp(target: number, duration = 1250) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const reducedMotionFrame = window.requestAnimationFrame(() => setValue(target));
      return () => window.cancelAnimationFrame(reducedMotionFrame);
    }
    let frame = 0;
    const started = performance.now();
    const update = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 4);
      setValue(Math.round(target * eased));
      if (progress < 1) frame = window.requestAnimationFrame(update);
    };
    frame = window.requestAnimationFrame(update);
    return () => window.cancelAnimationFrame(frame);
  }, [duration, target]);

  return value;
}

function AnimatedMoney({ value }: { value: number }) {
  return <>{money(useCountUp(value))}</>;
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
        <div className="pot-label"><small>Money still in the pot</small><strong><AnimatedMoney value={campaign.remaining} /></strong></div>
        <div className="pot-meter" aria-label={`${potLevel}% of campaign pot remains`}><span className="pot-meter__fill" /><i className="pot-meter__proof"><ProductIcon name="shield" /></i></div>
        <p><b>{potLevel}%</b> of {money(campaign.pot)} remains</p>
      </div>
      <div className="campaign-vital campaign-vital--time">
        <span className="time-orbit"><ProductIcon name="clock" /></span>
        <div><small>Campaign closes in</small><LiveDuration campaign={campaign} compact={!includeMinimum} /><p>20 Sep · 18:00 WAT</p></div>
      </div>
      {includeMinimum && (
        <div className="campaign-vital campaign-vital--minimum">
          <ProductIcon name="play" />
          <div><small>Starts earning at</small><strong>{compactNumber(campaign.minimumViews)}</strong><p>verified views</p></div>
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

export function DashboardHome() {
  const feature = campaigns[0];
  return (
    <div className="dashboard-page dashboard-home">
      <PageHeading
        note="Your feed is moving"
        title="Morning, Tobi."
        copy="Two briefs match your lanes. One joined campaign closes soon."
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
            <span>{feature.brand} presents</span>
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
            <div><ProductIcon name="wallet" /><span>Your money</span></div>
            <small>15 Sep 2026</small>
          </div>
          <div className="money-total">
            <span>Accrued across 3 clips</span>
            <strong>₦42,850</strong>
            <small>₦6,200 added this week</small>
          </div>
          <dl>
            <div><dt>Payable now</dt><dd>₦18,400</dd></div>
            <div><dt>In 5-day hold</dt><dd>₦24,450</dd></div>
            <div><dt>Paid all time</dt><dd>₦126,700</dd></div>
          </dl>
          <Link href="/dashboard/settings#payouts" className="ink-button">
            Withdraw payable money<ProductIcon name="arrow" />
          </Link>
          <p><ProductIcon name="shield" /> Every naira traces back to platform-reported views.</p>
        </aside>
      </section>

      <section className="dashboard-section">
        <SectionTitle title="Campaigns worth opening" href="/dashboard/campaigns" />
        <div className="campaign-tape">
          {campaigns.slice(1).map((campaign) => (
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

      <section className="dashboard-bottom-grid">
        <div className="proof-stream">
          <SectionTitle title="Your clips, right now" />
          <div className="proof-stream__line" aria-hidden="true" />
          <article>
            <span className="proof-node is-live"><ProductIcon name="play" /></span>
            <div><small>Posted</small><strong>Roommate ate my last pack</strong><p>Indomie · TikTok</p></div>
            <b>43.2K <small>views</small></b>
          </article>
          <article>
            <span className="proof-node"><ProductIcon name="shield" /></span>
            <div><small>Checking</small><strong>The transfer plot twist</strong><p>PalmPay · YouTube</p></div>
            <b>2 min <small>ago</small></b>
          </article>
          <article>
            <span className="proof-node is-money"><ProductIcon name="wallet" /></span>
            <div><small>Payable</small><strong>Main character entrance</strong><p>Gbedu Records · Instagram</p></div>
            <b>₦9,600</b>
          </article>
        </div>

        <aside className="mini-leaderboard">
          <SectionTitle title="Fastest moving" href="/dashboard/leaderboard" linkLabel="Full board" />
          {leaderboard.slice(0, 4).map((person) => (
            <div key={person.rank} className={person.name === "Tobi On Cam" ? "is-you" : ""}>
              <span>{String(person.rank).padStart(2, "0")}</span>
              <i>{person.name.slice(0, 2).toUpperCase()}</i>
              <p><strong>{person.name}</strong><small>{person.handle}</small></p>
              <b>{compactNumber(person.views)}</b>
            </div>
          ))}
        </aside>
      </section>
    </div>
  );
}

const campaignFilters = ["All", "For you", "Closing soon", "Joined"];

export function CampaignDirectory() {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const normalized = query.toLowerCase().trim();
    return campaigns.filter((campaign) => {
      const matchesFilter =
        filter === "All" ||
        filter === "For you" ||
        campaign.status === filter;
      const matchesQuery = !normalized || [campaign.brand, campaign.title, campaign.category].join(" ").toLowerCase().includes(normalized);
      return matchesFilter && matchesQuery;
    });
  }, [filter, query]);

  return (
    <div className="dashboard-page campaigns-page">
      <PageHeading
        note="Funded and ready"
        title="Find your next brief."
        copy="Rates, remaining money and rules are visible before you join."
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
            <div className="ledger-pot"><strong><AnimatedMoney value={campaign.remaining} /></strong><span><i style={{ width: `${(campaign.remaining / campaign.pot) * 100}%` }} /></span><small>of {money(campaign.pot)}</small></div>
            <Countdown campaign={campaign} />
            <span className="round-arrow"><ProductIcon name="arrow" /></span>
          </Link>
        ))}
        {!visible.length && (
          <div className="campaign-empty">
            <ProductIcon name="search" />
            <h2>No funded brief matches that.</h2>
            <p>Try another title, brand or category.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function CampaignDetail({ campaign }: { campaign: Campaign }) {
  const [joined, setJoined] = useState(campaign.status === "Joined");

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
          <p>{campaign.brand} presents</p>
          <h1>{campaign.title}</h1>
          <span>{campaign.line}</span>
        </div>
        <div className="campaign-detail-hero__action">
          <button className={joined ? "joined-button" : "lime-button"} type="button" onClick={() => setJoined(true)}>
            {joined ? <><ProductIcon name="check" /> Campaign joined</> : <>Join campaign<ProductIcon name="arrow" /></>}
          </button>
        </div>
      </section>

      <CampaignVitals campaign={campaign} includeMinimum />

      <div className="campaign-detail-grid">
        <div className="campaign-detail-main">
          <section className="brief-sheet">
            <div className="brief-sheet__heading"><span>Brief</span><small>Read this before you film</small></div>
            <h2>The idea</h2>
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
            <SectionTitle title="Things to make with" />
            <div>
              <button type="button"><span><ProductIcon name="play" /></span><p><strong>Campaign sound</strong><small>Official audio · 00:24</small></p><ProductIcon name="arrow" /></button>
              <button type="button"><span><ProductIcon name="link" /></span><p><strong>Visual reference</strong><small>Mood and pacing guide</small></p><ProductIcon name="arrow" /></button>
            </div>
          </section>
        </div>

        <aside className="campaign-detail-aside">
          <section className="plain-rules">
            <h2>Money rules, plainly</h2>
            <dl>
              <div><dt>Creator cap</dt><dd>{money(campaign.creatorCap)}</dd></div>
              <div><dt>Holding period</dt><dd>5 days</dd></div>
              <div><dt>View counting</dt><dd>Full thousands only</dd></div>
              <div><dt>Platforms</dt><dd>{campaign.platforms.join(" + ")}</dd></div>
              <div><dt>Content review</dt><dd>Usually under 5 min</dd></div>
            </dl>
            <p><ProductIcon name="shield" /> Views come from the platforms. Partial thousands wait until the next full 1,000.</p>
          </section>

          <section className="campaign-leaders">
            <SectionTitle title="Leading this brief" href="/dashboard/leaderboard" linkLabel="View board" />
            {leaderboard.slice(0, 3).map((person) => (
              <div key={person.rank}><span>{person.rank}</span><i>{person.name.slice(0, 2).toUpperCase()}</i><p><strong>{person.name}</strong><small>{compactNumber(person.views)} views</small></p><b>{money(person.earned)}</b></div>
            ))}
          </section>
        </aside>
      </div>

      <div className="mobile-campaign-action">
        <div><small>{money(campaign.rate)} / 1K views</small><strong>{campaign.daysLeft}d {campaign.hoursLeft}h left</strong></div>
        <button type="button" onClick={() => setJoined(true)}>{joined ? "Joined" : "Join campaign"}<ProductIcon name={joined ? "check" : "arrow"} /></button>
      </div>
    </div>
  );
}

export function LeaderboardScreen() {
  return (
    <div className="dashboard-page leaderboard-page">
      <PageHeading note="Real views, real movement" title="The board." copy="Creators ranked by verified views across live campaigns this week." />
      <section className="podium-board">
        <div className="podium-copy"><p className="marker-label">This week</p><h2>Attention, proved.</h2><p>Ranks refresh whenever a new platform reading lands.</p></div>
        {[leaderboard[1], leaderboard[0], leaderboard[2]].map((person) => (
          <article key={person.rank} className={`podium-person podium-person--${person.rank}`}>
            <span>{person.rank}</span>
            <i>{person.name.slice(0, 2).toUpperCase()}</i>
            <strong>{person.name}</strong>
            <small>{compactNumber(person.views)} verified views</small>
            <b>{money(person.earned)}</b>
          </article>
        ))}
      </section>

      <section className="ranking-sheet">
        <div className="ranking-sheet__head"><h2>All creators</h2><span>Updated 2 minutes ago</span></div>
        <div className="ranking-row ranking-row--labels"><span>Rank</span><span>Creator</span><span>Verified views</span><span>Earned</span></div>
        {leaderboard.map((person) => (
          <div key={person.rank} className={`ranking-row${person.name === "Tobi On Cam" ? " is-you" : ""}`}>
            <span className="rank-number">{String(person.rank).padStart(2, "0")}</span>
            <span className="rank-creator"><i>{person.name.slice(0, 2).toUpperCase()}</i><span><strong>{person.name}</strong><small>{person.handle}</small></span>{person.name === "Tobi On Cam" && <b>You</b>}</span>
            <strong>{compactNumber(person.views)}</strong>
            <strong className="rank-money">{money(person.earned)}</strong>
          </div>
        ))}
      </section>
    </div>
  );
}

export function SettingsScreen() {
  const [saved, setSaved] = useState(false);
  return (
    <div className="dashboard-page settings-page">
      <PageHeading note="Your side of Clippit" title="Settings." copy="Keep the details behind your clips and payouts accurate." />
      <div className="settings-layout">
        <nav className="settings-index" aria-label="Settings sections">
          <a href="#profile" className="is-active"><ProductIcon name="settings" /> Profile</a>
          <a href="#accounts"><ProductIcon name="link" /> Social accounts</a>
          <a href="#payouts"><ProductIcon name="bank" /> Payout account</a>
          <a href="#notifications"><ProductIcon name="bell" /> Notifications</a>
        </nav>
        <div className="settings-sheets">
          <section id="profile" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Creator profile</h2><p>What brands and leaderboards see.</p></div><span className="settings-avatar">TO</span></div>
            <div className="settings-fields">
              <label><span>Display name</span><input defaultValue="Tobi On Cam" /></label>
              <label><span>Handle</span><div className="prefix-input"><i>@</i><input defaultValue="tobioncam" /></div></label>
              <label className="is-wide"><span>Creator bio</span><textarea defaultValue="Comedy, food and everyday Lagos stories. I make the ad feel like the timeline." /></label>
              <label><span>Primary lane</span><select defaultValue="Comedy"><option>Comedy</option><option>Lifestyle</option><option>Food</option><option>Music</option></select></label>
              <label><span>Location</span><input defaultValue="Lagos, Nigeria" /></label>
            </div>
            <button className="lime-button" type="button" onClick={() => { setSaved(true); window.setTimeout(() => setSaved(false), 2200); }}>{saved ? <><ProductIcon name="check" /> Changes saved</> : <>Save profile<ProductIcon name="arrow" /></>}</button>
          </section>

          <section id="accounts" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Connected socials</h2><p>We read views directly from these platforms.</p></div><ProductIcon name="shield" /></div>
            <div className="social-account is-connected"><span><ProductIcon name="tiktok" /></span><p><strong>TikTok</strong><small>@tobioncam · Last checked 2 min ago</small></p><b><i /> Connected</b><button type="button"><ProductIcon name="more" /></button></div>
            <div className="social-account is-connected"><span><ProductIcon name="instagram" /></span><p><strong>Instagram</strong><small>@tobioncam · Last checked 4 min ago</small></p><b><i /> Connected</b><button type="button"><ProductIcon name="more" /></button></div>
            <div className="social-account"><span><ProductIcon name="youtube" /></span><p><strong>YouTube</strong><small>Add a channel to join YouTube briefs.</small></p><button className="connect-button" type="button">Connect<ProductIcon name="arrow" /></button></div>
          </section>

          <section id="payouts" className="settings-sheet payout-sheet">
            <div className="settings-sheet__title"><div><h2>Payout account</h2><p>Payable money lands here.</p></div><ProductIcon name="bank" /></div>
            <div className="bank-account"><span><ProductIcon name="bank" /></span><p><small>GTBank</small><strong>0123 456 789</strong><b>Tobi Adeyemi</b></p><i>Verified</i></div>
            <p className="security-note"><ProductIcon name="shield" /> Account changes trigger a security review before the next withdrawal.</p>
          </section>

          <section id="notifications" className="settings-sheet">
            <div className="settings-sheet__title"><div><h2>Notifications</h2><p>Choose what deserves your attention.</p></div><ProductIcon name="bell" /></div>
            {["New campaigns in my lanes", "Submission verdicts", "Earnings become payable", "Campaign closing reminders"].map((label, index) => (
              <label className="toggle-row" key={label}><span><strong>{label}</strong><small>{index === 0 ? "A short list, never a noisy blast." : "Delivered by email and in your Clippit inbox."}</small></span><input type="checkbox" defaultChecked={index !== 3} /><i /></label>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
