import Image from "next/image";
import Script from "next/script";

export function LandingPage() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <svg
        className="svg-library"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <symbol id="i-arrow" viewBox="0 0 24 24">
          <path d="M5 12h14m-6-6 6 6-6 6" />
        </symbol>
        <symbol id="i-up" viewBox="0 0 24 24">
          <path d="M5 19 19 5M5 5h14v14" />
        </symbol>
        <symbol id="i-check" viewBox="0 0 24 24">
          <path d="m5 12 4 4L19 6" />
        </symbol>
        <symbol id="i-play" viewBox="0 0 24 24">
          <path d="m9 5 11 7-11 7Z" />
        </symbol>
        <symbol id="i-star" viewBox="0 0 100 100">
          <path d="m50 3 9 29 26-17-17 26 29 9-29 9 17 26-26-17-9 29-9-29-26 17 17-26-29-9 29-9-17-26 26 17Z" />
        </symbol>
        <symbol id="i-tiktok" viewBox="0 0 24 24">
          <path d="M14 3v12.5a4.5 4.5 0 1 1-4-4.47M14 3c.7 4 3 6 7 6" />
        </symbol>
        <symbol id="i-instagram" viewBox="0 0 24 24">
          <rect x={3} y={3} width={18} height={18} rx={5} />
          <circle cx={12} cy={12} r={4} />
          <path d="M17.5 6.5h.01" />
        </symbol>
        <symbol id="i-youtube" viewBox="0 0 24 24">
          <rect x={2} y={5} width={20} height={14} rx={4} />
          <path d="m10 9 5 3-5 3Z" />
        </symbol>
        <symbol id="i-eye" viewBox="0 0 24 24">
          <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
          <circle cx={12} cy={12} r={3} />
        </symbol>
      </svg>
      <header className="nav" id="nav">
        <div className="shell nav__inner">
          <a className="brand" href="#top" aria-label="Clippit home">
            <Image
              src="/assets/clippit-mark.png"
              alt=""
              width={40}
              height={40}
              priority
            />
            <span>
              Clippit<sup>™</sup>
            </span>
          </a>
          <nav className="nav__links" aria-label="Main navigation">
            <a href="#how">How it works</a>
            <a href="#campaigns">Explore campaigns</a>
            <a href="#brands">
              For brands{" "}
              <svg className="icon">
                <use href="#i-up" />
              </svg>
            </a>
          </nav>
          <div className="nav__actions">
            <a className="button button--small" href="/auth/sign-up">
              Find your first campaign
              <svg className="icon">
                <use href="#i-up" />
              </svg>
            </a>
            <button
              className="menu-toggle"
              id="burger"
              aria-label="Open menu"
              aria-expanded="false"
              aria-controls="mobileNav"
            >
              <span />
              <span />
            </button>
          </div>
        </div>
        <nav
          className="mobile-nav"
          id="mobileNav"
          aria-label="Mobile navigation"
          hidden
        >
          <a href="#how">How it works</a>
          <a href="#campaigns">Explore campaigns</a>
          <a href="#brands">For brands</a>
          <a href="#faq">Questions? Sorted.</a>
        </nav>
      </header>
      <main id="main">
        <section className="hero" id="top">
          <div className="shell hero__layout">
            <div className="hero__copy">
              <div className="hero__tag">
                <span className="little-star">✳</span> Made for the ones who
                make things.
              </div>
              <h1>
                <span className="title-mask">
                  <span>Your next</span>
                </span>
                <span className="title-mask">
                  <span>post. Your</span>
                </span>
                <span className="title-mask">
                  <span className="payday">
                    next payday.
                    <svg
                      viewBox="0 0 600 30"
                      preserveAspectRatio="none"
                      aria-hidden="true"
                    >
                      <path d="M8 19C138-1 349 5 590 10M95 27C238 16 430 19 535 24" />
                    </svg>
                  </span>
                </span>
              </h1>
              <p className="hero__description">
                You’ve got the ideas. Brands have the budget.
                <br />
                Make the content, bring the views, get paid in naira.
                <br className="desktop-break" />
                Your own page. Your own kind of creative.
              </p>
              <div className="hero__buttons">
                <a className="button button--large" href="/auth/sign-up">
                  Let’s get you paid
                  <svg className="icon">
                    <use href="#i-up" />
                  </svg>
                </a>
                <a className="text-link" href="#how">
                  <span className="play-circle">
                    <svg className="icon">
                      <use href="#i-play" />
                    </svg>
                  </span>
                  How it works
                </a>
              </div>
              <div className="hero__perks">
                <span>
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                  No follower minimum
                </span>
                <span>
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                  Your creativity, rewarded
                </span>
              </div>
            </div>
            <div
              className="hero__collage"
              aria-label="Illustrative social posts and Clippit earnings"
            >
              <div className="collage-orbit" aria-hidden="true" />
              <svg
                className="collage-star"
                viewBox="0 0 100 100"
                aria-hidden="true"
              >
                <use href="#i-star" />
              </svg>
              <div className="hand-note collage-note">
                that thing you do?
                <br />
                it’s worth something.
                <svg viewBox="0 0 100 60" aria-hidden="true">
                  <path d="M5 7C58-12 96 14 78 49m-17-9 16 12 15-18" />
                </svg>
              </div>
              <article className="social-card social-card--back">
                <Image
                  src="/assets/photos/street-style.jpg"
                  alt="A smiling creator in headphones on a city street"
                  width={650}
                  height={812}
                  sizes="(max-width: 700px) 54vw, 330px"
                />
                <div className="social-card__top">
                  <svg className="icon">
                    <use href="#i-instagram" />
                  </svg>
                  <span>Reels</span>
                  <span>•••</span>
                </div>
                <div className="social-card__caption">
                  <span>POV: the sound is too good</span>
                  <b>Good music. Better moves.</b>
                  <small>♫ original sound · weekend energy</small>
                </div>
                <span className="view-bubble">
                  <svg className="icon">
                    <use href="#i-play" />
                  </svg>{" "}
                  84.2K
                </span>
              </article>
              <article className="social-card social-card--front">
                <Image
                  src="/assets/photos/fashion.jpg"
                  alt="A stylish Black woman with an afro and cat-eye sunglasses"
                  width={800}
                  height={1100}
                  priority
                  sizes="(max-width: 700px) 58vw, 360px"
                />
                <div className="social-card__top">
                  <svg className="icon">
                    <use href="#i-tiktok" />
                  </svg>
                  <span>For you</span>
                  <span>⌕</span>
                </div>
                <div className="social-card__center">
                  a little main
                  <br />
                  character energy.
                </div>
                <div className="social-card__rail" aria-hidden="true">
                  <span>
                    ♥<small>12.8K</small>
                  </span>
                  <span>
                    ●<small>246</small>
                  </span>
                  <span>
                    ➤<small>Share</small>
                  </span>
                </div>
                <div className="social-card__caption">
                  <b>Your style. Your story.</b>
                  <small>Today’s look understood the assignment.</small>
                  <small>#CreateWithClippit #Style</small>
                </div>
                <span className="view-bubble">
                  <svg className="icon">
                    <use href="#i-play" />
                  </svg>{" "}
                  128.4K views
                </span>
              </article>
              <div className="earning-sticker">
                <span className="earning-sticker__check">
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                </span>
                <div>
                  <small>Creativity looks good on you.</small>
                  <strong>+₦64,000</strong>
                  <span>128,000 eligible views × ₦500 / 1K</span>
                </div>
                <svg className="icon">
                  <use href="#i-up" />
                </svg>
              </div>
              <div className="round-sticker" aria-hidden="true">
                <span>GOOD CLIPS</span>
                <b>☺</b>
                <span>BETTER PAYDAYS</span>
              </div>
              <p className="collage-disclaimer">
                Social-post mockups · illustrative views &amp; earnings
              </p>
            </div>
          </div>
          <div className="shell hero__bottom">
            <span>Your content. These platforms.</span>
            <div className="platforms">
              <span>
                <svg className="icon">
                  <use href="#i-tiktok" />
                </svg>
                TikTok
              </span>
              <span>
                <svg className="icon">
                  <use href="#i-instagram" />
                </svg>
                Instagram
              </span>
              <span>
                <svg className="icon">
                  <use href="#i-youtube" />
                </svg>
                YouTube
              </span>
            </div>
            <a href="#how" className="scroll-note">
              There’s money in your next idea <span>↓</span>
            </a>
          </div>
        </section>
        <div className="ticker" aria-label="Create. Post. Earn. Repeat.">
          <div className="ticker__track">
            <span>
              Create something good <b>✳</b> Post it your way <b>✳</b> Let the
              views pay <b>✳</b> Do your thing <b>✳</b>{" "}
            </span>
            <span aria-hidden="true">
              Create something good <b>✳</b> Post it your way <b>✳</b> Let the
              views pay <b>✳</b> Do your thing <b>✳</b>
            </span>
          </div>
        </div>
        <section className="how section" id="how">
          <div className="shell">
            <div className="section-heading">
              <div>
                <p className="section-label">
                  <span className="little-star">✳</span> The creative-to-cash
                  pipeline
                </p>
                <h2 data-reveal>
                  Less pitching.
                  <br />
                  More posting.
                </h2>
              </div>
              <p>
                You don’t need a manager, a media kit, or a million followers.
                Just a good idea and a social account.
              </p>
            </div>
            <ol className="steps">
              <li className="step" data-reveal>
                <div className="step__visual step__visual--brief">
                  <div className="mini-brief">
                    <span>
                      <span className="brand-dot">g.</span> Gbedu Records
                      <svg className="icon">
                        <use href="#i-check" />
                      </svg>
                    </span>
                    <b>
                      Make the next hit
                      <br />
                      impossible to skip.
                    </b>
                    <div>
                      <strong>₦850</strong>
                      <small>per 1,000 views</small>
                    </div>
                    <span className="mini-brief__button">
                      This one’s my vibe
                      <svg className="icon">
                        <use href="#i-up" />
                      </svg>
                    </span>
                  </div>
                  <span className="hand-note">find your thing ↗</span>
                </div>
                <div className="step__title">
                  <span>01</span>
                  <h3>Find your kind of campaign.</h3>
                </div>
                <p>
                  Music, fashion, lifestyle, tech. Pick a funded brief that fits
                  your style. Check the rate, remaining budget, and rules before
                  you start.
                </p>
              </li>
              <li className="step" data-reveal>
                <div className="step__visual step__visual--post">
                  <div className="mini-post">
                    <Image
                      src="/assets/photos/lagos-portrait.jpg"
                      alt="Smiling woman photographed in Lagos"
                      width={650}
                      height={975}
                      sizes="(max-width: 700px) 70vw, 320px"
                    />
                    <span>
                      Made it. Posted it. <b>✳</b>
                    </span>
                  </div>
                  <div className="link-pill">
                    <svg className="icon">
                      <use href="#i-tiktok" />
                    </svg>
                    tiktok.com/@you/video/… <span>✓</span>
                  </div>
                </div>
                <div className="step__title">
                  <span>02</span>
                  <h3>Make it. Post it. Drop the link.</h3>
                </div>
                <p>
                  Connect your account, follow the brief, and post on your own
                  page. Submit the link and video. Keep your voice; that’s why
                  you’re here.
                </p>
              </li>
              <li className="step" data-reveal>
                <div className="step__visual step__visual--proof">
                  <div className="proof-slip">
                    <span>
                      Your clip checks out <span>✳</span>
                    </span>
                    <p>
                      <i>✓</i> Product in the frame
                    </p>
                    <p>
                      <i>✓</i> Campaign tag included
                    </p>
                    <p>
                      <i>✓</i> The brief? Understood.
                    </p>
                    <div>
                      <svg className="icon">
                        <use href="#i-eye" />
                      </svg>
                      <b>24,800</b>
                      <small>views read from the platform</small>
                    </div>
                  </div>
                </div>
                <div className="step__title">
                  <span>03</span>
                  <h3>You create. We count.</h3>
                </div>
                <p>
                  We check your clip against the brief and read views directly
                  from the platform. Approved, eligible views turn into
                  earnings.
                </p>
              </li>
              <li className="step" data-reveal>
                <div className="step__visual step__visual--paid">
                  <div className="mini-receipt">
                    <span>Clippit payday</span>
                    <svg className="icon">
                      <use href="#i-check" />
                    </svg>
                    <strong>₦12,000</strong>
                    <small>Example earnings at ₦500 / 1K</small>
                    <div>
                      24,000 eligible views <span>✓</span>
                    </div>
                  </div>
                  <span className="hand-note">now that’s a good post.</span>
                </div>
                <div className="step__title">
                  <span>04</span>
                  <h3>Turn “nice post” into naira.</h3>
                </div>
                <p>
                  After the five-day holding period and checks, cleared earnings
                  become available to withdraw to your Nigerian bank account.
                </p>
              </li>
            </ol>
          </div>
        </section>
        <section className="campaigns section" id="campaigns">
          <div className="shell">
            <div className="section-heading">
              <div>
                <p className="section-label">
                  <span className="little-star">✳</span> Find your next creative
                  obsession
                </p>
                <h2 data-reveal>Big brief energy.</h2>
              </div>
              <div>
                <p>
                  A beat you can’t sit still to. A fit worth showing off.
                  <br />
                  Pick the brief you’d make content for anyway.
                </p>
                <span className="preview-label">
                  Campaign previews · not live offers
                </span>
              </div>
            </div>
            <div
              className="filter-bar"
              role="group"
              aria-label="Filter campaign previews"
            >
              <button
                className="filter is-active"
                data-filter="all"
                aria-pressed="true"
              >
                A little bit of everything <span>3</span>
              </button>
              <button
                className="filter"
                data-filter="music"
                aria-pressed="false"
              >
                ♫ Music
              </button>
              <button
                className="filter"
                data-filter="lifestyle"
                aria-pressed="false"
              >
                ✳ Lifestyle
              </button>
              <button
                className="filter"
                data-filter="fashion"
                aria-pressed="false"
              >
                ✂ Fashion
              </button>
            </div>
            <div className="campaign-grid" id="campaignGrid">
              <article
                className="campaign-card"
                data-category="music"
                data-reveal
              >
                <div className="campaign-art campaign-art--music">
                  <Image
                    src="/assets/photos/street-style.jpg"
                    alt="Music fan wearing headphones outdoors"
                    width={650}
                    height={812}
                    sizes="(max-width: 700px) 100vw, 33vw"
                  />
                  <span className="campaign-category">Music &amp; culture</span>
                  <div className="campaign-art__type">
                    ON
                    <br />
                    REPEAT.<span>↗</span>
                  </div>
                  <span className="campaign-art__brand">gbedu records®</span>
                </div>
                <div className="campaign-card__body">
                  <div className="campaign-card__byline">
                    <span>Gbedu Records</span>
                    <div>
                      <svg className="icon">
                        <use href="#i-tiktok" />
                      </svg>
                      <svg className="icon">
                        <use href="#i-youtube" />
                      </svg>
                    </div>
                  </div>
                  <h3>Put the next anthem on the map.</h3>
                  <p>
                    Make a dance, a transition, or a moment with the campaign
                    sound. Let your take do the talking.
                  </p>
                  <div className="campaign-rate">
                    <strong>₦850</strong>
                    <span>
                      per 1,000
                      <br />
                      verified views
                    </span>
                  </div>
                  <div className="campaign-pot">
                    <span>Campaign budget remaining</span>
                    <b>₦408,000</b>
                  </div>
                  <div className="pot-track">
                    <span style={{ width: "34%" }} />
                  </div>
                  <button className="campaign-open" data-campaign="music">
                    Explore the brief{" "}
                    <svg className="icon">
                      <use href="#i-up" />
                    </svg>
                  </button>
                </div>
              </article>
              <article
                className="campaign-card"
                data-category="lifestyle"
                data-reveal
              >
                <div className="campaign-art campaign-art--life">
                  <Image
                    src="/assets/photos/lagos-portrait.jpg"
                    alt="Lagos portrait with a vibrant patterned headwrap"
                    width={650}
                    height={975}
                    sizes="(max-width: 700px) 100vw, 33vw"
                  />
                  <span className="campaign-category">Everyday stories</span>
                  <div className="campaign-art__type">
                    THE GOOD
                    <br />
                    IN YOUR
                    <br />
                    EVERYDAY.
                  </div>
                  <span className="campaign-art__brand">Everyday Lagos ✳</span>
                </div>
                <div className="campaign-card__body">
                  <div className="campaign-card__byline">
                    <span>Everyday Lagos</span>
                    <div>
                      <svg className="icon">
                        <use href="#i-tiktok" />
                      </svg>
                      <svg className="icon">
                        <use href="#i-instagram" />
                      </svg>
                    </div>
                  </div>
                  <h3>Your city. Through your lens.</h3>
                  <p>
                    Find a little joy in your daily routine. Tell a story that
                    makes someone stop scrolling and smile.
                  </p>
                  <div className="campaign-rate">
                    <strong>₦500</strong>
                    <span>
                      per 1,000
                      <br />
                      verified views
                    </span>
                  </div>
                  <div className="campaign-pot">
                    <span>Campaign budget remaining</span>
                    <b>₦340,000</b>
                  </div>
                  <div className="pot-track">
                    <span style={{ width: "68%" }} />
                  </div>
                  <button className="campaign-open" data-campaign="lifestyle">
                    Explore the brief{" "}
                    <svg className="icon">
                      <use href="#i-up" />
                    </svg>
                  </button>
                </div>
              </article>
              <article
                className="campaign-card"
                data-category="fashion"
                data-reveal
              >
                <div className="campaign-art campaign-art--fashion">
                  <Image
                    src="/assets/photos/afro-style.jpg"
                    alt="Black fashion model with an afro and sunglasses in warm sunlight"
                    width={650}
                    height={900}
                    sizes="(max-width: 700px) 100vw, 33vw"
                  />
                  <span className="campaign-category">Fashion &amp; style</span>
                  <div className="campaign-art__type">
                    WEAR
                    <br />
                    YOUR
                    <br />
                    ENERGY.
                  </div>
                  <span className="campaign-art__brand">shuku / studios</span>
                </div>
                <div className="campaign-card__body">
                  <div className="campaign-card__byline">
                    <span>Shuku Studios</span>
                    <div>
                      <svg className="icon">
                        <use href="#i-instagram" />
                      </svg>
                    </div>
                  </div>
                  <h3>The fit deserves its own film.</h3>
                  <p>
                    Style the collection your way. A GRWM, a street-style
                    moment, or the cleanest transition on the feed.
                  </p>
                  <div className="campaign-rate">
                    <strong>₦620</strong>
                    <span>
                      per 1,000
                      <br />
                      verified views
                    </span>
                  </div>
                  <div className="campaign-pot">
                    <span>Campaign budget remaining</span>
                    <b>₦880,000</b>
                  </div>
                  <div className="pot-track">
                    <span style={{ width: "88%" }} />
                  </div>
                  <button className="campaign-open" data-campaign="fashion">
                    Explore the brief{" "}
                    <svg className="icon">
                      <use href="#i-up" />
                    </svg>
                  </button>
                </div>
              </article>
            </div>
            <p className="campaigns__note">
              A little preview of what’s possible. Rates, budgets, and briefs
              are illustrative.
            </p>
          </div>
        </section>
        <section className="calculator-section section" id="earnings">
          <div className="shell calculator-layout">
            <div className="calculator-copy">
              <p className="section-label">
                <span className="little-star">✳</span> Okay, but what’s the
                money like?
              </p>
              <h2 data-reveal>
                Do the maths.
                <br />
                Then do
                <br />
                <span className="hand-heading">your thing.</span>
              </h2>
              <p>
                No mysterious creator fund. Each brand sets a rate for every
                1,000 verified views. You see the deal before you make the clip.
              </p>
              <div className="calculator-copy__note">
                <svg viewBox="0 0 100 60" aria-hidden="true">
                  <path d="M5 48C18 3 71 9 92 32m-21 1 24 2-5-23" />
                </svg>
                <span className="hand-note">go on, move the slider.</span>
              </div>
            </div>
            <div className="calculator" data-reveal>
              <div className="calculator__top">
                <span>Your potential payday</span>
                <span className="mini-tag">Try it out ↗</span>
              </div>
              <label htmlFor="viewSlider">If your clip gets…</label>
              <div className="calculator__views">
                <output htmlFor="viewSlider" id="calcViews">
                  50,000
                </output>
                <span>verified views</span>
              </div>
              <input
                id="viewSlider"
                type="range"
                min={0}
                max={500000}
                step={1000}
                defaultValue={50000}
                aria-describedby="calcRules"
              />
              <div className="range-labels">
                <span>0</span>
                <span>500K views</span>
              </div>
              <label htmlFor="rateSelect">At a campaign rate of</label>
              <select id="rateSelect">
                <option value={500}>₦500 per 1,000 views</option>
                <option value={620}>₦620 per 1,000 views</option>
                <option value={850}>₦850 per 1,000 views</option>
              </select>
              <div className="calculator__result">
                <span>That’s a potential</span>
                <output id="calcMoney" aria-live="polite">
                  ₦25,000
                </output>
                <span className="hand-note">from one good idea. ✳</span>
              </div>
              <p id="calcRules">
                Illustrative gross earnings, not a guarantee. Full thousands
                count after the 1,000-view minimum. Approval, campaign caps,
                available budget, and a five-day hold apply.
              </p>
            </div>
          </div>
        </section>
        <section className="proof-section section" id="proof">
          <div className="shell proof-layout">
            <div className="proof-board" data-reveal>
              <div className="proof-board__tape" aria-hidden="true" />
              <span className="hand-note">Receipts. We love receipts.</span>
              <div className="proof-board__row">
                <span className="proof-board__icon">
                  <svg className="icon">
                    <use href="#i-tiktok" />
                  </svg>
                </span>
                <div>
                  <b>Straight from the source.</b>
                  <small>Platform view count</small>
                </div>
                <strong>128,400</strong>
              </div>
              <div className="proof-board__connector">↓</div>
              <div className="proof-board__row">
                <span className="proof-board__icon">
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                </span>
                <div>
                  <b>Every requirement, checked.</b>
                  <small>Brief compliance</small>
                </div>
                <span className="status-pill">Approved ✓</span>
              </div>
              <div className="proof-board__connector">↓</div>
              <div className="proof-board__row proof-board__row--money">
                <span className="proof-board__icon">₦</span>
                <div>
                  <b>Every naira, accounted for.</b>
                  <small>128 × ₦500, before any caps</small>
                </div>
                <strong>₦64,000</strong>
              </div>
              <span className="proof-board__fine">
                Illustrative submission · 400 partial views carry no payout
              </span>
              <span className="verified-stamp">
                VIEW
                <br />
                VERIFIED
                <br />✳
              </span>
            </div>
            <div className="proof-copy">
              <p className="section-label">
                <span className="little-star">✳</span> Serious about your money
              </p>
              <h2 data-reveal>
                All the vibes.
                <br />
                All the receipts.
              </h2>
              <p>
                Creating should be the fun part. Wondering whether you’ll get
                paid shouldn’t be part of it.
              </p>
              <ul className="feature-list">
                <li>
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                  <div>
                    <h3>Funded before you film.</h3>
                    <p>
                      A campaign only opens once the brand’s funds have cleared
                      into escrow.
                    </p>
                  </div>
                </li>
                <li>
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                  <div>
                    <h3>Your views tell the story.</h3>
                    <p>
                      We read counts from connected platforms. No typed-in
                      numbers or screenshot submissions as proof.
                    </p>
                  </div>
                </li>
                <li>
                  <svg className="icon">
                    <use href="#i-check" />
                  </svg>
                  <div>
                    <h3>A clear answer. A fair next step.</h3>
                    <p>
                      If a clip misses the brief, you see exactly why. You can
                      appeal the decision.
                    </p>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </section>
        <section className="brands-section section" id="brands">
          <div className="shell brands-layout">
            <div className="brands-copy">
              <p className="section-label">
                <span className="little-star">✳</span> For brands, artists, and
                big ideas
              </p>
              <h2 data-reveal>
                Don’t interrupt
                <br />
                the culture.
                <br />
                Be part of it.
              </h2>
              <p>
                Your next campaign deserves more than a skipped ad. Put it in
                the hands of creators who know how to make people watch.
              </p>
              <div className="brand-benefits">
                <span>✓ You set the rate</span>
                <span>✓ You set the budget</span>
                <span>✓ Verified views, visible spend</span>
              </div>
              <button className="button button--white" data-open="brand">
                Build a sample campaign
                <svg className="icon">
                  <use href="#i-up" />
                </svg>
              </button>
            </div>
            <div className="brand-board" data-reveal>
              <div className="brand-board__head">
                <span className="brand-dot">c.</span>
                <span>Your next big thing</span>
                <span className="mini-tag">Campaign preview</span>
              </div>
              <div className="brand-board__budget">
                <div>
                  <small>You put in</small>
                  <strong>₦500,000</strong>
                </div>
                <span>↗</span>
                <div>
                  <small>At ₦500 / 1K, that funds</small>
                  <strong>
                    1M <em>views</em>
                  </strong>
                </div>
              </div>
              <div
                className="brand-board__chart"
                aria-label="Illustrative campaign growth chart"
              >
                <div style={{ "--bar": "22%" } as React.CSSProperties} />
                <div style={{ "--bar": "31%" } as React.CSSProperties} />
                <div style={{ "--bar": "27%" } as React.CSSProperties} />
                <div style={{ "--bar": "43%" } as React.CSSProperties} />
                <div style={{ "--bar": "39%" } as React.CSSProperties} />
                <div style={{ "--bar": "58%" } as React.CSSProperties} />
                <div style={{ "--bar": "66%" } as React.CSSProperties} />
                <div style={{ "--bar": "60%" } as React.CSSProperties} />
                <div style={{ "--bar": "81%" } as React.CSSProperties} />
                <div style={{ "--bar": "89%" } as React.CSSProperties} />
                <div style={{ "--bar": "100%" } as React.CSSProperties} />
                <span className="chart-label">Good content travels. ↗</span>
              </div>
              <div className="brand-board__bottom">
                <div className="avatar-stack">
                  <Image
                    src="/assets/photos/lagos-portrait.jpg"
                    alt=""
                    width={44}
                    height={44}
                  />
                  <Image
                    src="/assets/photos/street-style.jpg"
                    alt=""
                    width={44}
                    height={44}
                  />
                  <Image
                    src="/assets/photos/fashion.jpg"
                    alt=""
                    width={44}
                    height={44}
                  />
                </div>
                <p>
                  One brief. A whole lot
                  <br />
                  of creative possibilities.
                </p>
                <svg className="icon">
                  <use href="#i-star" />
                </svg>
              </div>
              <span className="hand-note brand-board__note">
                you bring the brief.
                <br />
                they bring the magic.
              </span>
            </div>
          </div>
        </section>
        <section className="faq-section section" id="faq">
          <div className="shell faq-layout">
            <div>
              <p className="section-label">
                <span className="little-star">✳</span> Before you hit record
              </p>
              <h2 data-reveal>
                Good questions.
                <br />
                Straight answers.
              </h2>
              <span className="hand-note faq-note">
                no fine-print gymnastics.
                <svg viewBox="0 0 100 60" aria-hidden="true">
                  <path d="M5 8c40-2 60 12 75 37m-20-2 22 6 6-23" />
                </svg>
              </span>
            </div>
            <div className="faq-list">
              <details open>
                <summary>
                  Do I need a big following?<span>+</span>
                </summary>
                <p>
                  No follower minimum. You need a connected social account and
                  content that meets the campaign brief. A clip starts earning
                  once it reaches 1,000 verified views, subject to the
                  campaign’s rules.
                </p>
              </details>
              <details>
                <summary>
                  What kind of content can I make?<span>+</span>
                </summary>
                <p>
                  Whatever fits the brief: a music edit, a GRWM, a product demo,
                  a funny skit, or a slice of everyday life. Each campaign tells
                  you what to say, show, tag, and avoid. You create and edit
                  with your own tools.
                </p>
              </details>
              <details>
                <summary>
                  How are my earnings calculated?<span>+</span>
                </summary>
                <p>
                  The brand sets a rate per 1,000 verified views. Only full
                  thousands pay: at ₦500 per 1,000 views, 4,900 views earns
                  ₦2,000. Your clip must be approved, and earnings are limited
                  by the remaining campaign budget and clip or creator caps.
                </p>
              </details>
              <details>
                <summary>
                  When can I withdraw my money?<span>+</span>
                </summary>
                <p>
                  Earnings have a five-day holding period so suspicious views
                  can be checked. Once cleared and payable, you can request a
                  withdrawal to a Nigerian bank account. The product targets
                  delivery within 24 hours of becoming payable; bank processing
                  may vary.
                </p>
              </details>
              <details>
                <summary>
                  What if my clip gets rejected?<span>+</span>
                </summary>
                <p>
                  You get the specific checklist items your content did not
                  meet, with reasons. If you think the decision is wrong, you
                  can appeal. You should always know what happened and what you
                  can do next.
                </p>
              </details>
              <details>
                <summary>
                  What happens when the campaign budget runs out?<span>+</span>
                </summary>
                <p>
                  The campaign closes when the pot is exhausted or its deadline
                  passes. It cannot pay more than it holds. Check the remaining
                  budget and the campaign caps before creating; example
                  calculator results are not reserved earnings.
                </p>
              </details>
              <details>
                <summary>
                  Is Clippit available outside Nigeria?<span>+</span>
                </summary>
                <p>
                  The first version is built for creators in Nigeria, with naira
                  payouts to Nigerian bank accounts. Platform availability
                  depends on supported account connections. International
                  payouts are not part of the first release.
                </p>
              </details>
            </div>
          </div>
        </section>
        <section className="throw-stage" id="join" data-throw>
          <div className="throw-pin">
            <div className="throw-intro" id="throwIntro">
              <p className="section-label">
                <span className="little-star">✳</span> One last thing…
              </p>
              <h2>
                Put that phone
                <br />
                to good use.
              </h2>
              <span className="hand-note">
                keep scrolling. catch your next payday. ↓
              </span>
            </div>
            <canvas
              id="throwCanvas"
              className="throw-canvas"
              aria-hidden="true"
            />
            <div className="phone" id="phone">
              <div className="phone__screen">
                <div className="phone__content" id="phoneContent">
                  <span className="little-star finale-star">✳</span>
                  <p className="section-label">
                    Good creators. Better paydays.
                  </p>
                  <h2>
                    Go on.
                    <br />
                    Make your move.
                  </h2>
                  <p>
                    Your next great idea could be your next payday.
                    <br />
                    Let’s find a brief with your name on it.
                  </p>
                  <a className="button button--large" href="/auth/sign-up">
                    Find my first campaign
                    <svg className="icon">
                      <use href="#i-up" />
                    </svg>
                  </a>
                  <button className="celebrate-button" id="celebrate">
                    Or just make it rain confetti <span>✳</span>
                  </button>
                  <span className="finale-fine">
                    Your own account. Your own voice. A whole new possibility.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="footer">
        <div className="shell">
          <div className="footer__top">
            <div>
              <a className="brand" href="#top">
                <Image
                  src="/assets/clippit-mark.png"
                  alt=""
                  width={40}
                  height={40}
                />
                <span>
                  Clippit<sup>™</sup>
                </span>
              </a>
              <p>
                More creators.
                <br />A richer internet.
              </p>
            </div>
            <div>
              <h3>Make your move</h3>
              <a href="#campaigns">Explore campaigns</a>
              <a href="/auth/sign-in">Sign in</a>
              <a href="#how">How it works</a>
              <a href="#earnings">Earnings calculator</a>
            </div>
            <div>
              <h3>Bring your brand</h3>
              <a href="#brands">For brands &amp; artists</a>
              <button data-open="brand">Preview a campaign</button>
              <a href="#proof">How verification works</a>
            </div>
            <div>
              <h3>The good-to-knows</h3>
              <a href="#faq">Your questions, answered</a>
              <button data-open="credits">Photo credits</button>
              <span className="footer-location">
                <span /> Made in Nigeria. For the culture.
              </span>
            </div>
          </div>
          <div className="footer__wordmark">
            <Image
              src="/assets/clippit-footer-title.png"
              alt="Clippit"
              width={2172}
              height={724}
              sizes="100vw"
            />
          </div>
          <div className="footer__bottom">
            <span>© 2026 Clippit</span>
            <span>Attention → Proof → Money</span>
            <a href="#top">Back to the good stuff ↑</a>
          </div>
        </div>
      </footer>
      <dialog
        id="detailDialog"
        className="dialog"
        aria-labelledby="dialogTitle"
      >
        <button className="dialog-close" aria-label="Close dialog">
          ×
        </button>
        <div id="dialogContent" />
      </dialog>
      <canvas className="confetti" id="confetti" aria-hidden="true" />

      <Script src="/landing-runtime.js" strategy="afterInteractive" />
    </>
  );
}
