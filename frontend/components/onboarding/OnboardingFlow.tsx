"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";

const interests: Array<{ label: string; icon: ProductIconName }> = [
  { label: "Comedy", icon: "spark" },
  { label: "Food", icon: "food" },
  { label: "Music", icon: "music" },
  { label: "Beauty", icon: "beauty" },
  { label: "Lifestyle", icon: "camera" },
  { label: "Gaming", icon: "game" },
  { label: "Fitness", icon: "fitness" },
  { label: "Tech", icon: "tech" },
  { label: "Travel", icon: "travel" },
];

const platforms: Array<{ label: string; icon: ProductIconName; copy: string }> = [
  { label: "TikTok", icon: "tiktok", copy: "Short-form, trends and skits" },
  { label: "Instagram", icon: "instagram", copy: "Reels, stories and feed" },
  { label: "YouTube", icon: "youtube", copy: "Shorts and long-form video" },
];

function SetupTopbar() {
  const router = useRouter();
  return (
    <header className="onboarding-topbar">
      <div className="onboarding-brand">
        <Image src="/assets/clippit-mark-light.png" width={38} height={38} alt="" priority />
        <strong>Clippit</strong>
      </div>
      <button type="button" onClick={() => router.push("/dashboard")}>Finish later</button>
    </header>
  );
}

function SetupProgress({ step, label }: { step: number; label: string }) {
  return (
    <div className="setup-progress" aria-label={`${label} step ${step + 1} of 3`}>
      <span>{label}</span>
      <div>{[0, 1, 2].map((item) => <i key={item} className={item <= step ? "is-filled" : ""} />)}</div>
      <b>{String(step + 1).padStart(2, "0")} / 03</b>
    </div>
  );
}

function InterestPicker({ selected, onToggle }: { selected: string[]; onToggle: (label: string) => void }) {
  return (
    <div className="interest-grid">
      {interests.map((item) => {
        const active = selected.includes(item.label);
        return (
          <button type="button" key={item.label} className={active ? "is-selected" : ""} onClick={() => onToggle(item.label)} aria-pressed={active}>
            <ProductIcon name={item.icon} />
            <span>{item.label}</span>
            <i><ProductIcon name="check" /></i>
          </button>
        );
      })}
    </div>
  );
}

export function CreatorOnboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>(["Comedy", "Lifestyle"]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["TikTok"]);
  const [error, setError] = useState("");
  const firstName = useMemo(() => name.trim().split(/\s+/)[0] || "You", [name]);

  const toggleInterest = (label: string) => {
    setSelected((current) => current.includes(label) ? current.filter((item) => item !== label) : current.length < 5 ? [...current, label] : current);
  };

  const togglePlatform = (label: string) => {
    setSelectedPlatforms((current) => current.includes(label) ? current.filter((item) => item !== label) : [...current, label]);
  };

  const next = () => {
    if (step === 0 && name.trim().length < 2) return setError("Tell us what you would like to be called.");
    if (step === 1 && selected.length < 2) return setError("Pick at least two content lanes.");
    if (step === 2 && !selectedPlatforms.length) return setError("Choose at least one place you post.");
    setError("");
    if (step < 2) setStep((value) => value + 1);
    else router.push("/dashboard");
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    next();
  };

  return (
    <main className="onboarding-shell creator-onboarding">
      <SetupTopbar />
      <div className="onboarding-layout">
        <section className="onboarding-workbench">
          <SetupProgress step={step} label="Creator setup" />
          <form className="setup-form" onSubmit={submit}>
            {step === 0 && (
              <div className="setup-step" key="creator-name">
                <p className="setup-note">Put your name on the work.</p>
                <h1>What should we call you?</h1>
                <p className="setup-copy">This name appears on submissions, campaign leaderboards and payout records.</p>
                <label className="name-field">
                  <span>Creator name</span>
                  <input autoFocus value={name} onChange={(event) => { setName(event.target.value.slice(0, 32)); setError(""); }} placeholder="Tobi On Cam" autoComplete="nickname" />
                  <small>{name.length}/32</small>
                </label>
              </div>
            )}

            {step === 1 && (
              <div className="setup-step" key="creator-lanes">
                <p className="setup-note">Build your campaign signal.</p>
                <h1>What do you make for brands?</h1>
                <p className="setup-copy">Choose two to five lanes you make now or want to get paid to explore.</p>
                <InterestPicker selected={selected} onToggle={toggleInterest} />
              </div>
            )}

            {step === 2 && (
              <div className="setup-step" key="creator-platforms">
                <p className="setup-note">Connect attention to proof.</p>
                <h1>Where do you post?</h1>
                <p className="setup-copy">Choose every platform you use. Connections happen securely after setup.</p>
                <div className="platform-picker">
                  {platforms.map((platform) => {
                    const active = selectedPlatforms.includes(platform.label);
                    return (
                      <button type="button" key={platform.label} className={active ? "is-selected" : ""} onClick={() => togglePlatform(platform.label)} aria-pressed={active}>
                        <span><ProductIcon name={platform.icon} /></span>
                        <p><strong>{platform.label}</strong><small>{platform.copy}</small></p>
                        <i><ProductIcon name="check" /></i>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <SetupActions step={step} error={error} onBack={() => setStep((value) => value - 1)} finalLabel="Open creator dashboard" />
          </form>
        </section>

        <aside className="signal-board" aria-label="Live creator profile preview">
          <div className="signal-board__grid" />
          <p className="marker-note">Your work. Your signal.</p>
          <div className="creator-passport">
            <div className="creator-passport__head"><span>Creator pass</span><ProductIcon name="shield" /></div>
            <div className="creator-passport__identity">
              <span className="creator-passport__avatar">{firstName.slice(0, 2).toUpperCase()}</span>
              <div><small>Known as</small><strong>{name.trim() || "Your name lands here"}</strong></div>
            </div>
            <div className="creator-passport__lane"><small>Makes for brands</small><div>{selected.map((item) => <span key={item}>{item}</span>)}</div></div>
            <div className="creator-passport__footer"><span>Attention</span><i /><span>Proof</span><i /><span>Money</span></div>
          </div>
          <div className="signal-stat signal-stat--views"><ProductIcon name="play" /><span>Verified views</span><strong>124.8K</strong></div>
          <div className="signal-stat signal-stat--money"><ProductIcon name="wallet" /><span>Future payday</span><strong>₦28,400</strong></div>
          <div className="signal-stamp"><ProductIcon name="check" /><span>Built to earn</span></div>
        </aside>
      </div>
    </main>
  );
}

const brandGoals: Array<{ label: string; copy: string; icon: ProductIconName }> = [
  { label: "Launch something", copy: "A product, service or new feature", icon: "campaigns" },
  { label: "Move a sound", copy: "Music, podcast or culture moment", icon: "music" },
  { label: "Stay remembered", copy: "Reach, conversation and brand recall", icon: "spark" },
  { label: "Drive an action", copy: "Visits, sign-ups or event interest", icon: "arrow" },
];

export function BrandOnboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [organisation, setOrganisation] = useState("");
  const [contact, setContact] = useState("");
  const [selected, setSelected] = useState<string[]>(["Comedy", "Lifestyle"]);
  const [goal, setGoal] = useState("Launch something");
  const [error, setError] = useState("");

  const toggleInterest = (label: string) => {
    setSelected((current) => current.includes(label) ? current.filter((item) => item !== label) : current.length < 5 ? [...current, label] : current);
  };

  const next = () => {
    if (step === 0 && organisation.trim().length < 2) return setError("Enter the name behind your campaigns.");
    if (step === 0 && contact.trim().length < 2) return setError("Tell us what to call you inside the workspace.");
    if (step === 1 && selected.length < 2) return setError("Pick at least two content directions.");
    setError("");
    if (step < 2) setStep((value) => value + 1);
    else router.push("/dashboard/campaigns");
  };

  return (
    <main className="onboarding-shell brand-onboarding">
      <SetupTopbar />
      <div className="onboarding-layout brand-setup-layout">
        <section className="onboarding-workbench brand-workbench">
          <SetupProgress step={step} label="Brand setup" />
          <form className="setup-form" onSubmit={(event) => { event.preventDefault(); next(); }}>
            {step === 0 && (
              <div className="setup-step" key="brand-name">
                <p className="setup-note">Start with the people behind the pot.</p>
                <h1>Who is funding the work?</h1>
                <p className="setup-copy">Set the organisation name creators will see, then tell us what to call you.</p>
                <div className="brand-name-fields">
                  <label className="name-field"><span>Organisation name</span><input autoFocus value={organisation} onChange={(event) => { setOrganisation(event.target.value.slice(0, 40)); setError(""); }} placeholder="Gbedu Records" autoComplete="organization" /></label>
                  <label className="name-field"><span>Your preferred name</span><input value={contact} onChange={(event) => { setContact(event.target.value.slice(0, 32)); setError(""); }} placeholder="Amara" autoComplete="nickname" /></label>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="setup-step" key="brand-lanes">
                <p className="setup-note">Point creators in the right direction.</p>
                <h1>What do you want made?</h1>
                <p className="setup-copy">Choose the content worlds your campaigns should live inside.</p>
                <InterestPicker selected={selected} onToggle={toggleInterest} />
              </div>
            )}

            {step === 2 && (
              <div className="setup-step" key="brand-goal">
                <p className="setup-note">Give the attention a job.</p>
                <h1>What should the first campaign move?</h1>
                <p className="setup-copy">This shapes the first brief template in your workspace.</p>
                <div className="brand-goal-grid">
                  {brandGoals.map((item) => (
                    <button type="button" key={item.label} className={goal === item.label ? "is-selected" : ""} onClick={() => setGoal(item.label)}>
                      <ProductIcon name={item.icon} />
                      <span><strong>{item.label}</strong><small>{item.copy}</small></span>
                      <i><ProductIcon name="check" /></i>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <SetupActions step={step} error={error} onBack={() => setStep((value) => value - 1)} finalLabel="Open campaign workspace" />
          </form>
        </section>

        <aside className="brand-brief-room" aria-label="Live brand brief preview">
          <div className="brand-brief-room__grid" />
          <p className="marker-note">Fund the idea. Prove the views.</p>
          <div className="live-brief">
            <div className="live-brief__head"><span>Campaign direction</span><b>Draft</b></div>
            <div className="live-brief__brand"><small>From</small><strong>{organisation.trim() || "Your brand"}</strong></div>
            <div className="live-brief__asks"><small>Creators should make</small><p>{selected.join(" / ")}</p></div>
            <div className="live-brief__goal"><ProductIcon name="campaigns" /><span><small>The campaign should</small><strong>{goal}</strong></span></div>
          </div>
          <div className="brand-pot-preview"><span>Sample funded pot</span><strong>₦500,000</strong><div><i /></div><small>Enough for 1M views at ₦500 / 1K</small></div>
          <div className="brand-proof-stamp"><ProductIcon name="shield" /><span>Pay for proof</span></div>
        </aside>
      </div>
    </main>
  );
}

function SetupActions({ step, error, onBack, finalLabel }: { step: number; error: string; onBack: () => void; finalLabel: string }) {
  return (
    <div className="setup-actions">
      <div>{step > 0 && <button className="setup-back" type="button" onClick={onBack}>Back</button>}<span className="setup-error" role="alert">{error}</span></div>
      <button className="setup-next" type="submit">{step === 2 ? finalLabel : "Keep going"}<ProductIcon name="arrow" /></button>
    </div>
  );
}
