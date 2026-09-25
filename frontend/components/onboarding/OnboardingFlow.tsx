"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ProductIcon, type ProductIconName } from "@/components/ui/ProductIcon";
import { ProfilePhotoPicker, saveStoredProfile } from "@/components/ui/ProfilePhotoPicker";
import { ApiError } from "@/lib/api/client";
import { onboardingApi, PLATFORM_VALUES, type OnboardingDraftOut } from "@/lib/api/onboarding";

const PLATFORM_LABELS = Object.fromEntries(Object.entries(PLATFORM_VALUES).map(([label, value]) => [value, label]));

function useDraftSync(load: () => Promise<OnboardingDraftOut>, save: (payload: Record<string, unknown> & { revision: number }) => Promise<OnboardingDraftOut>, restore: (draft: OnboardingDraftOut) => void) {
  const revision = useRef<number | null>(null);
  const [draft, setDraft] = useState<OnboardingDraftOut | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((result) => { if (!cancelled) { revision.current = result.revision; setDraft(result); restore(result); } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setReady(true); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const persist = async (answers: Record<string, unknown>, step: string) => {
    if (revision.current === null) return;
    const body = Object.fromEntries(Object.entries(answers).filter(([, value]) => value !== "" && value !== null && value !== undefined));
    try {
      revision.current = (await save({ ...body, step, revision: revision.current })).revision;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        try { revision.current = (await load()).revision; } catch { /* next save retries */ }
      }
    }
  };

  return { draft, ready, persist };
}

async function uploadIfLocal(photo: string) {
  if (!photo.startsWith("data:")) return { id: null, url: photo || "" };
  try {
    const upload = await onboardingApi.uploadPhoto(photo);
    return { id: upload.id, url: upload.url };
  } catch {
    return { id: null, url: photo };
  }
}

function SetupLoading() {
  return <main className="onboarding-shell"><SetupTopbar /></main>;
}

type Option = { label: string; copy?: string; icon: ProductIconName };

const interests: Option[] = [
  { label: "Comedy", icon: "spark" }, { label: "Food", icon: "food" },
  { label: "Music", icon: "music" }, { label: "Beauty", icon: "beauty" },
  { label: "Lifestyle", icon: "camera" }, { label: "Gaming", icon: "game" },
  { label: "Fitness", icon: "fitness" }, { label: "Tech", icon: "tech" },
  { label: "Travel", icon: "travel" },
];

const platforms: Option[] = [
  { label: "TikTok", icon: "tiktok", copy: "Short-form, trends and skits" },
  { label: "Instagram", icon: "instagram", copy: "Reels, stories and feed" },
  { label: "Facebook", icon: "facebook", copy: "Video and community posts" },
  { label: "X", icon: "x", copy: "Video posts and conversations" },
  { label: "YouTube", icon: "youtube", copy: "Shorts and long-form video" },
];

const discoverySources: Option[] = [
  { label: "A creator or friend", icon: "users" }, { label: "TikTok or Instagram", icon: "play" },
  { label: "A brand or team", icon: "building" }, { label: "Event or community", icon: "source" },
  { label: "Search or article", icon: "search" }, { label: "Somewhere else", icon: "more" },
];

const creatorExperience: Option[] = [
  { label: "Setting up my first page", icon: "spark" }, { label: "I post when inspiration hits", icon: "camera" },
  { label: "I publish consistently", icon: "play" }, { label: "Content is my full-time work", icon: "brief" },
];

const creatorGoals: Option[] = [
  { label: "Earn from what I already make", icon: "wallet" }, { label: "Find briefs that fit my style", icon: "brief" },
  { label: "Build a stronger portfolio", icon: "camera" }, { label: "Understand my audience", icon: "eye" },
];

const productionWorkflows: Option[] = [
  { label: "In-house team", copy: "Our own people plan and produce", icon: "users" },
  { label: "Freelancers", copy: "A flexible external roster", icon: "person" },
  { label: "Agency partners", copy: "Strategy and production are outsourced", icon: "building" },
  { label: "Creators directly", copy: "We brief creators one by one", icon: "camera" },
  { label: "Starting fresh", copy: "No repeatable process yet", icon: "spark" },
];

const teamSizes: Option[] = [
  { label: "Just me", icon: "person" }, { label: "2–10 people", icon: "users" },
  { label: "11–50 people", icon: "building" }, { label: "51–200 people", icon: "brief" },
  { label: "More than 200", icon: "source" },
];

const campaignGoals: Option[] = [
  { label: "Launch a product or feature", icon: "spark" }, { label: "Make a sound or moment travel", icon: "music" },
  { label: "Build awareness and recall", icon: "eye" }, { label: "Drive visits, sign-ups or sales", icon: "arrow" },
  { label: "Collect creator-made assets", icon: "camera" },
];

const budgets: Option[] = [
  { label: "Under ₦250,000", icon: "wallet" }, { label: "₦250,000–₦750,000", icon: "wallet" },
  { label: "₦750,000–₦2,000,000", icon: "wallet" }, { label: "Above ₦2,000,000", icon: "wallet" },
  { label: "Still deciding", icon: "more" },
];

const generatedArt = {
  camera: { src: "/assets/illustrations/clippit-icons/creator-camera.webp", alt: "Creator phone and tripod illustration" },
  taste: { src: "/assets/illustrations/clippit-icons/taste-eye.webp", alt: "Content taste and viewing illustration" },
  pot: { src: "/assets/illustrations/clippit-icons/funding-pot.webp", alt: "Campaign funding pot illustration" },
  brief: { src: "/assets/illustrations/clippit-icons/campaign-brief.webp", alt: "Campaign brief illustration" },
  proof: { src: "/assets/illustrations/clippit-icons/verified-proof.webp", alt: "Verified content proof illustration" },
  payout: { src: "/assets/illustrations/clippit-icons/payout-wallet.webp", alt: "Creator payout illustration" },
};

function SetupTopbar() {
  return <header className="onboarding-topbar"><div className="onboarding-brand"><Image src="/assets/clippit-mark-light.png" width={38} height={38} alt="" priority /><strong>Clippit</strong></div><span className="onboarding-required-note"><ProductIcon name="shield" />Setup required</span></header>;
}

function SetupProgress({ step, total, label }: { step: number; total: number; label: string }) {
  return <div className="setup-progress" aria-label={`${label} question ${step + 1} of ${total}`}><span>{label}</span><div style={{ gridTemplateColumns: `repeat(${total}, 1fr)` }}>{Array.from({ length: total }, (_, item) => <i key={item} className={item <= step ? "is-filled" : ""} />)}</div><b>{String(step + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</b></div>;
}

function SetupArtwork({ artwork, tone = "lime" }: { artwork: keyof typeof generatedArt; tone?: "lime" | "gold" }) {
  const item = generatedArt[artwork];
  return <div className={`setup-generated-art setup-generated-art--${tone}`} key={item.src} aria-hidden="true"><Image src={item.src} alt={item.alt} fill sizes="110px" /></div>;
}

function Question({ note, title, copy, children }: { note: string; title: string; copy: string; children: ReactNode }) {
  return <div className="setup-step typeform-question"><p className="setup-note">{note}</p><h1>{title}</h1><p className="setup-copy">{copy}</p><div className="typeform-answer">{children}</div></div>;
}

function TextAnswer({ label, value, onChange, placeholder, autoComplete, maxLength = 60, multiline = false }: { label: string; value: string; onChange: (value: string) => void; placeholder: string; autoComplete?: string; maxLength?: number; multiline?: boolean }) {
  return <label className={`typeform-field${multiline ? " typeform-field--textarea" : ""}`}><span>{label}</span>{multiline ? <textarea autoFocus value={value} onChange={(event) => onChange(event.target.value.slice(0, maxLength))} placeholder={placeholder} /> : <input autoFocus value={value} onChange={(event) => onChange(event.target.value.slice(0, maxLength))} placeholder={placeholder} autoComplete={autoComplete} />}<small>{value.length}/{maxLength}</small></label>;
}

function InterestPicker({ selected, onToggle, label }: { selected: string[]; onToggle: (label: string) => void; label: string }) {
  return <div className="interest-grid typeform-interest-grid" aria-label={label}>{interests.map((item, index) => { const active = selected.includes(item.label); return <button type="button" key={item.label} className={active ? "is-selected" : ""} onClick={() => onToggle(item.label)} aria-pressed={active}><em>{index + 1}</em><ProductIcon name={item.icon} /><span>{item.label}</span><i><ProductIcon name="check" /></i></button>; })}</div>;
}

function ChoiceGrid({ options, value, onChange, compact = false }: { options: Option[]; value: string; onChange: (value: string) => void; compact?: boolean }) {
  return <div className={`intake-choice-grid typeform-choice-grid${compact ? " intake-choice-grid--small" : ""}`}>{options.map((item, index) => { const active = item.label === value; return <button type="button" key={item.label} className={active ? "is-selected" : ""} onClick={() => onChange(item.label)} aria-pressed={active}><em>{index + 1}</em><span className="intake-choice-icon"><ProductIcon name={item.icon} /></span><span><strong>{item.label}</strong>{item.copy && <small>{item.copy}</small>}</span><i><ProductIcon name="check" /></i></button>; })}</div>;
}

function PlatformPicker({ selected, onToggle }: { selected: string[]; onToggle: (label: string) => void }) {
  return <div className="platform-picker platform-picker--compact typeform-platforms">{platforms.map((platform, index) => { const active = selected.includes(platform.label); return <button type="button" key={platform.label} className={active ? "is-selected" : ""} onClick={() => onToggle(platform.label)} aria-pressed={active}><em>{index + 1}</em><span><ProductIcon name={platform.icon} /></span><p><strong>{platform.label}</strong><small>{platform.copy}</small></p><i><ProductIcon name="check" /></i></button>; })}</div>;
}

function SetupActions({ step, isLast, error, onBack, finalLabel, hint = "Press Enter to continue", continueLabel, busy = false }: { step: number; isLast: boolean; error: string; onBack: () => void; finalLabel: string; hint?: string; continueLabel?: string; busy?: boolean }) {
  return <div className="setup-actions typeform-actions"><div>{step > 0 && <button className="setup-back" type="button" onClick={onBack} disabled={busy}>Back</button>}<span className="setup-error" role="alert">{error}</span></div><div className="typeform-continue"><small>{busy ? "Saving your answers…" : hint}</small><button className="setup-next" type="submit" disabled={busy} aria-busy={busy}>{busy ? "Saving…" : isLast ? finalLabel : continueLabel || "Continue"}<ProductIcon name="arrow" /></button></div></div>;
}

function toggleLimited(current: string[], label: string, limit = 5) {
  if (current.includes(label)) return current.filter((item) => item !== label);
  return current.length < limit ? [...current, label] : current;
}

type CreatorStep = "name" | "photo" | "location" | "makes" | "watches" | "platforms" | "experience" | "discovery" | "goal";
const creatorSteps: CreatorStep[] = ["name", "photo", "location", "makes", "watches", "platforms", "experience", "discovery", "goal"];

export function CreatorOnboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0); const [name, setName] = useState(""); const [location, setLocation] = useState("");
  const [photo, setPhoto] = useState("");
  const [makes, setMakes] = useState<string[]>(["Comedy", "Lifestyle"]); const [watches, setWatches] = useState<string[]>(["Comedy", "Music"]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["TikTok"]); const [experience, setExperience] = useState("");
  const [discovery, setDiscovery] = useState(""); const [goal, setGoal] = useState(""); const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const current = creatorSteps[step]; const firstName = useMemo(() => name.trim().split(/\s+/)[0] || "You", [name]);
  const artwork: Record<CreatorStep, keyof typeof generatedArt> = { name: "camera", photo: "camera", location: "camera", makes: "brief", watches: "taste", platforms: "proof", experience: "proof", discovery: "payout", goal: "payout" };
  const sync = useDraftSync(onboardingApi.creatorDraft, onboardingApi.saveCreatorDraft, (draft) => {
    if (draft.status === "completed") { router.replace("/dashboard"); return; }
    if (draft.status !== "in_progress") return;
    const a = draft.answers as Record<string, unknown>;
    const list = (key: string) => (Array.isArray(a[key]) ? (a[key] as string[]) : null);
    if (typeof a.display_name === "string") setName(a.display_name);
    if (typeof a.location === "string") setLocation(a.location);
    if (list("interests")) setMakes(list("interests")!);
    if (list("viewing_interests")) setWatches(list("viewing_interests")!);
    if (list("platforms")) setSelectedPlatforms(list("platforms")!.map((value) => PLATFORM_LABELS[value] ?? value));
    if (typeof a.experience === "string") setExperience(a.experience);
    if (typeof a.discovery_source === "string") setDiscovery(a.discovery_source);
    if (list("goals")?.length) setGoal(list("goals")![0]);
    const resumeAt = creatorSteps.indexOf(draft.step as CreatorStep);
    if (resumeAt > 0) setStep(resumeAt);
  });

  const answers = () => ({
    display_name: name.trim().length >= 2 ? name.trim() : undefined,
    location: location.trim() || undefined,
    interests: makes,
    viewing_interests: watches,
    platforms: selectedPlatforms.map((label) => PLATFORM_VALUES[label]).filter(Boolean),
    experience: experience || undefined,
    discovery_source: discovery || undefined,
    goals: goal ? [goal] : [],
  });
  const latestAnswers = useRef(answers);
  useEffect(() => { latestAnswers.current = answers; });
  const advanceTo = (index: number) => { setStep(index); window.setTimeout(() => void sync.persist(latestAnswers.current(), creatorSteps[index]), 0); };

  const finish = async () => {
    setSaving(true); setError("");
    try {
      const uploaded = await uploadIfLocal(photo);
      const profile = await onboardingApi.completeCreator({ ...answers(), display_name: name.trim(), photo_upload_id: uploaded.id });
      window.localStorage.removeItem("clippit:creator-onboarding");
      saveStoredProfile("creator", { name: profile.display_name, bio: profile.bio ?? "", photo: profile.photo_url || uploaded.url });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't save your answers. Check your connection and try again.");
      setSaving(false);
    }
  };
  const next = () => {
    if (current === "name" && name.trim().length < 2) return setError("Tell us what you would like to be called.");
    if (current === "location" && location.trim().length < 2) return setError("Add the city or region you create from.");
    if (current === "makes" && makes.length < 2) return setError("Pick at least two kinds of content you like making.");
    if (current === "watches" && watches.length < 2) return setError("Pick at least two kinds of content you enjoy watching.");
    if (current === "platforms" && !selectedPlatforms.length) return setError("Choose at least one place you publish.");
    if (current === "experience" && !experience) return setError("Choose the closest match for your creator journey.");
    if (current === "discovery" && !discovery) return setError("Tell us how you heard about Clippit.");
    if (current === "goal" && !goal) return setError("Choose what Clippit should help with first.");
    setError(""); if (step === creatorSteps.length - 1) void finish(); else advanceTo(step + 1);
  };
  const choose = (setter: (value: string) => void, value: string) => { setter(value); setError(""); if (step < creatorSteps.length - 1) window.setTimeout(() => advanceTo(step + 1), 230); };

  if (!sync.ready || sync.draft?.status === "completed") return <SetupLoading />;

  return <main className="onboarding-shell creator-onboarding"><SetupTopbar /><div className="onboarding-layout"><section className="onboarding-workbench typeform-workbench"><SetupProgress step={step} total={creatorSteps.length} label="Creator setup" /><SetupArtwork artwork={artwork[current]} /><form className="setup-form setup-form--extended typeform-form" onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); next(); }}><div key={current}>
    {current === "name" && <Question note="First, make it yours." title="What would you like to be called?" copy="Use the name people know from your content."><TextAnswer label="Creator name" value={name} onChange={(value) => { setName(value); setError(""); }} placeholder="Tobi On Cam" autoComplete="nickname" maxLength={32} /></Question>}
    {current === "photo" && <Question note="Optional." title="Put a face to the name." copy="Add a profile photo for campaign rooms and leaderboards, or skip this step for now."><ProfilePhotoPicker value={photo} name={name} onChange={setPhoto} /></Question>}
    {current === "location" && <Question note={`Good to meet you, ${firstName}.`} title="Where are you creating from?" copy="Your city helps us surface nearby moments and locally relevant briefs."><TextAnswer label="City or region" value={location} onChange={(value) => { setLocation(value); setError(""); }} placeholder="Lagos, Nigeria" autoComplete="address-level2" maxLength={40} /></Question>}
    {current === "makes" && <Question note="Your creative fingerprint." title="What do you like making?" copy="Pick two to five lanes. This tunes the funded briefs you see first."><InterestPicker selected={makes} onToggle={(label) => { setMakes((value) => toggleLimited(value, label)); setError(""); }} label="Content you like making" /></Question>}
    {current === "watches" && <Question note="Now tune the feed." title="What stops your scroll?" copy="Pick the content you genuinely enjoy viewing, even if you do not make it yet."><InterestPicker selected={watches} onToggle={(label) => { setWatches((value) => toggleLimited(value, label)); setError(""); }} label="Content you like viewing" /></Question>}
    {current === "platforms" && <Question note="Map your publishing rhythm." title="Where does your work live?" copy="Choose every platform where you currently publish."><PlatformPicker selected={selectedPlatforms} onToggle={(label) => { setSelectedPlatforms((value) => toggleLimited(value, label, 3)); setError(""); }} /></Question>}
    {current === "experience" && <Question note="No follower minimum." title="How established is your practice?" copy="Choose the answer that feels most like your current rhythm."><ChoiceGrid options={creatorExperience} value={experience} onChange={(value) => choose(setExperience, value)} /></Question>}
    {current === "discovery" && <Question note="Almost there." title="How did you hear about us?" copy="This helps us understand where the creator community is finding Clippit."><ChoiceGrid options={discoverySources} value={discovery} onChange={(value) => choose(setDiscovery, value)} compact /></Question>}
    {current === "goal" && <Question note="Set your first signal." title="What should Clippit help you do first?" copy="Your answer shapes the first version of your creator dashboard."><ChoiceGrid options={creatorGoals} value={goal} onChange={(value) => { setGoal(value); setError(""); }} /></Question>}
  </div><SetupActions step={step} isLast={step === creatorSteps.length - 1} error={error} onBack={() => { setError(""); setStep((value) => Math.max(0, value - 1)); }} finalLabel="Build my creator feed" busy={saving} continueLabel={current === "photo" && !photo ? "Skip for now" : undefined} hint={current === "photo" ? photo ? "Photo added" : "This step is optional" : current === "makes" || current === "watches" || current === "platforms" ? "Choose, then continue" : current === "experience" || current === "discovery" ? "Choose one to continue" : current === "goal" ? "Choose one, then continue" : "Press Enter to continue"} /></form></section><CreatorPreview name={name} photo={photo} location={location} firstName={firstName} makes={makes} watches={watches} step={step} total={creatorSteps.length} /></div></main>;
}

function CreatorPreview({ name, photo, location, firstName, makes, watches, step, total }: { name: string; photo: string; location: string; firstName: string; makes: string[]; watches: string[]; step: number; total: number }) {
  return <aside className="signal-board" aria-label="Live creator profile preview"><div className="signal-board__grid" /><p className="marker-note">Your work. Your taste. Your signal.</p><div className="creator-passport creator-passport--intake"><div className="creator-passport__head"><span>Creator pass</span><ProductIcon name="shield" /></div><div className="creator-passport__identity"><span className="creator-passport__avatar">{photo ? <Image src={photo} alt="" fill unoptimized sizes="54px" /> : firstName.slice(0, 2).toUpperCase()}</span><div><small>Known as</small><strong>{name.trim() || "Your name lands here"}</strong><small>{location || "Your city"}</small></div></div><div className="creator-passport__lane"><small>Makes</small><div>{makes.map((item) => <span key={item}>{item}</span>)}</div></div><div className="creator-passport__lane creator-passport__lane--watch"><small>Watches</small><div>{watches.map((item) => <span key={item}>{item}</span>)}</div></div><div className="creator-passport__footer"><span>Attention</span><i /><span>Proof</span><i /><span>Money</span></div></div><div className="signal-stat signal-stat--views"><ProductIcon name="brief" /><span>Profile signal</span><strong>{Math.round(((step + 1) / total) * 100)}%</strong></div><div className="signal-stat signal-stat--money"><ProductIcon name="eye" /><span>Feed direction</span><strong>{watches.length} lanes</strong></div><div className="signal-stamp"><ProductIcon name="check" /><span>Built to earn</span></div></aside>;
}

type BrandStep = "name" | "photo" | "location" | "identity" | "registration" | "organisation" | "website" | "description" | "team" | "fund" | "workflow" | "view" | "discovery" | "campaignGoal" | "budget";

function brandStepsFor(identity: "" | "brand" | "individual", registered: "" | "yes" | "no"): BrandStep[] {
  if (identity === "individual") return ["name", "photo", "location", "identity", "fund", "view", "discovery", "campaignGoal", "budget"];
  const company: BrandStep[] = ["name", "photo", "location", "identity", "registration"];
  if (registered === "yes") company.push("organisation", "website", "description", "team");
  return [...company, "fund", "workflow", "view", "discovery", "campaignGoal", "budget"];
}

export function BrandOnboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0); const [name, setName] = useState(""); const [location, setLocation] = useState("");
  const [photo, setPhoto] = useState("");
  const [identity, setIdentity] = useState<"" | "brand" | "individual">(""); const [registered, setRegistered] = useState<"" | "yes" | "no">("");
  const [organisation, setOrganisation] = useState(""); const [description, setDescription] = useState(""); const [website, setWebsite] = useState(""); const [teamSize, setTeamSize] = useState("");
  const [funds, setFunds] = useState<string[]>(["Comedy", "Lifestyle"]); const [watches, setWatches] = useState<string[]>(["Comedy", "Music"]); const [workflow, setWorkflow] = useState("");
  const [discovery, setDiscovery] = useState(""); const [campaignGoal, setCampaignGoal] = useState(""); const [budget, setBudget] = useState(""); const [error, setError] = useState("");
  const steps = useMemo(() => brandStepsFor(identity, registered), [identity, registered]);
  const current = steps[step] ?? steps[steps.length - 1]; const displayName = identity === "individual" ? name : organisation || name;
  const artwork: Record<BrandStep, keyof typeof generatedArt> = { name: "camera", photo: "camera", location: "camera", identity: "brief", registration: "proof", organisation: "brief", website: "brief", description: "brief", team: "proof", fund: "pot", workflow: "camera", view: "taste", discovery: "payout", campaignGoal: "brief", budget: "pot" };
  const [saving, setSaving] = useState(false);
  const sync = useDraftSync(onboardingApi.organisationDraft, onboardingApi.saveOrganisationDraft, (draft) => {
    if (draft.status === "completed") { router.replace("/brand"); return; }
    if (draft.status !== "in_progress") return;
    const a = draft.answers as Record<string, unknown>;
    const text = (key: string) => (typeof a[key] === "string" ? (a[key] as string) : null);
    const list = (key: string) => (Array.isArray(a[key]) ? (a[key] as string[]) : null);
    const funder = text("funder_type");
    const restoredIdentity = funder === "brand" || funder === "individual" ? funder : "";
    const restoredRegistered = a.registered === true ? "yes" : a.registered === false ? "no" : "";
    setIdentity(restoredIdentity);
    setRegistered(restoredRegistered);
    if (text("contact_name")) setName(text("contact_name")!);
    if (funder === "brand" && a.registered === true && text("name")) setOrganisation(text("name")!);
    if (text("location")) setLocation(text("location")!);
    if (text("website")) setWebsite(text("website")!);
    if (text("bio")) setDescription(text("bio")!);
    if (text("team_size")) setTeamSize(text("team_size")!);
    if (list("content_interests")) setFunds(list("content_interests")!);
    if (list("viewing_interests")) setWatches(list("viewing_interests")!);
    if (text("production_workflow")) setWorkflow(text("production_workflow")!);
    if (text("discovery_source")) setDiscovery(text("discovery_source")!);
    if (text("campaign_goal")) setCampaignGoal(text("campaign_goal")!);
    if (text("budget_range")) setBudget(text("budget_range")!);
    const resumeAt = brandStepsFor(restoredIdentity, restoredRegistered).indexOf(draft.step as BrandStep);
    if (resumeAt > 0) setStep(resumeAt);
  });

  const answers = () => {
    const brand = identity !== "individual";
    const orgName = brand && registered === "yes" ? organisation.trim() : name.trim();
    return {
      name: orgName.length >= 2 ? orgName : undefined,
      contact_name: name.trim() || undefined,
      location: location.trim() || undefined,
      funder_type: identity || undefined,
      registered: brand && registered ? registered === "yes" : undefined,
      website: brand && registered === "yes" ? website.trim() || undefined : undefined,
      bio: brand && registered === "yes" ? description.trim() || undefined : undefined,
      team_size: brand && registered === "yes" ? teamSize || undefined : undefined,
      content_interests: funds,
      production_workflow: brand ? workflow || undefined : undefined,
      viewing_interests: watches,
      discovery_source: discovery || undefined,
      campaign_goal: campaignGoal || undefined,
      budget_range: budget || undefined,
    };
  };
  const latestAnswers = useRef(answers);
  useEffect(() => { latestAnswers.current = answers; });
  const advanceTo = (index: number) => { setStep(index); window.setTimeout(() => void sync.persist(latestAnswers.current(), steps[index] ?? ""), 0); };

  const finish = async () => {
    setSaving(true); setError("");
    try {
      const uploaded = await uploadIfLocal(photo);
      const payload = answers();
      const profile = await onboardingApi.completeOrganisation({ ...payload, name: payload.name ?? displayName.trim(), photo_upload_id: uploaded.id });
      window.localStorage.removeItem("clippit:brand-onboarding");
      saveStoredProfile("brand", { name: profile.name, bio: profile.bio ?? "", photo: profile.photo_url || uploaded.url });
      router.push("/brand");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We couldn't save your answers. Check your connection and try again.");
      setSaving(false);
    }
  };
  const next = () => {
    if (current === "name" && name.trim().length < 2) return setError("Tell us what you would like to be called.");
    if (current === "location" && location.trim().length < 2) return setError("Add your city or region.");
    if (current === "identity" && !identity) return setError("Choose whether you are funding as a brand or an individual.");
    if (current === "registration" && !registered) return setError("Tell us whether the company is registered.");
    if (current === "organisation" && organisation.trim().length < 2) return setError("Enter the organisation name creators should see.");
    if (current === "website" && website.trim().length < 3) return setError("Add the organisation website or public social page.");
    if (current === "description" && description.trim().length < 30) return setError("Give creators a description of at least 30 characters.");
    if (current === "team" && !teamSize) return setError("Choose the size of the team.");
    if (current === "fund" && funds.length < 2) return setError("Pick at least two kinds of content you want to fund.");
    if (current === "workflow" && !workflow) return setError("Choose how content gets made today.");
    if (current === "view" && watches.length < 2) return setError("Pick at least two kinds of content you want in your feed.");
    if (current === "discovery" && !discovery) return setError("Tell us how you heard about Clippit.");
    if (current === "campaignGoal" && !campaignGoal) return setError("Choose the first result you want from creators.");
    if (current === "budget" && !budget) return setError("Choose a comfortable starting budget.");
    setError(""); if (step === steps.length - 1) void finish(); else advanceTo(step + 1);
  };
  const choose = (setter: (value: string) => void, value: string) => { setter(value); setError(""); if (step < steps.length - 1) window.setTimeout(() => advanceTo(step + 1), 230); };

  if (!sync.ready || sync.draft?.status === "completed") return <SetupLoading />;

  return <main className="onboarding-shell brand-onboarding"><SetupTopbar /><div className="onboarding-layout brand-setup-layout"><section className="onboarding-workbench brand-workbench typeform-workbench"><SetupProgress step={step} total={steps.length} label={identity === "individual" ? "Funder setup" : "Brand setup"} /><SetupArtwork artwork={artwork[current]} tone="gold" /><form className="setup-form setup-form--extended typeform-form" onSubmit={(event) => { event.preventDefault(); next(); }}><div key={current}>
    {current === "name" && <Question note="Start with the person behind the pot." title="What would you like to be called?" copy="Use the name you want to see across your workspace."><TextAnswer label="Preferred name" value={name} onChange={(value) => { setName(value); setError(""); }} placeholder="Amara" autoComplete="nickname" maxLength={32} /></Question>}
    {current === "photo" && <Question note="Optional." title="Add your profile photo." copy="Use a personal photo or brand mark. You can skip this step and add one from settings later."><ProfilePhotoPicker value={photo} name={displayName} onChange={setPhoto} tone="gold" /></Question>}
    {current === "location" && <Question note={`Good to meet you, ${name.trim().split(/\s+/)[0] || "there"}.`} title="Where are you based?" copy="Your location helps us tune creator recommendations and campaign timing."><TextAnswer label="City or region" value={location} onChange={(value) => { setLocation(value); setError(""); }} placeholder="Lagos, Nigeria" autoComplete="address-level2" maxLength={40} /></Question>}
    {current === "identity" && <Question note="Tell us who is commissioning the work." title="Are you funding as a brand or an individual?" copy="We will only ask for the information that applies to you."><ChoiceGrid options={[{ label: "A brand or business", copy: "For an organisation, product or team", icon: "building" }, { label: "An individual", copy: "For a personal project, event or idea", icon: "person" }]} value={identity === "brand" ? "A brand or business" : identity === "individual" ? "An individual" : ""} onChange={(value) => { const nextIdentity = value === "An individual" ? "individual" : "brand"; choose((item) => setIdentity(item as "brand" | "individual"), nextIdentity); }} /></Question>}
    {current === "registration" && <Question note="A quick business check." title="Is the company registered?" copy="This prepares verification and campaign billing. You can still explore if registration is in progress."><ChoiceGrid options={[{ label: "Yes, it is registered", copy: "Add the organisation profile now", icon: "shield" }, { label: "Not yet", copy: "Testing the idea or registration is in progress", icon: "brief" }]} value={registered === "yes" ? "Yes, it is registered" : registered === "no" ? "Not yet" : ""} onChange={(value) => { const nextRegistration = value === "Yes, it is registered" ? "yes" : "no"; choose((item) => setRegistered(item as "yes" | "no"), nextRegistration); }} /></Question>}
    {current === "organisation" && <Question note="Build the creator-facing profile." title="What is the organisation called?" copy="Use the public name creators should recognise on a campaign brief."><TextAnswer label="Organisation name" value={organisation} onChange={(value) => { setOrganisation(value); setError(""); }} placeholder="Gbedu Records" autoComplete="organization" maxLength={60} /></Question>}
    {current === "website" && <Question note="Give creators somewhere to look." title="What is your website or social page?" copy="Add the public page creators can use to understand the organisation."><TextAnswer label="Website or social link" value={website} onChange={(value) => { setWebsite(value); setError(""); }} placeholder="gbedurecords.com" autoComplete="url" maxLength={90} /></Question>}
    {current === "description" && <Question note="Say what the organisation stands for." title="How would you describe it?" copy="Write one short paragraph creators can understand before they open a brief."><TextAnswer label="Brief description" value={description} onChange={(value) => { setDescription(value); setError(""); }} placeholder="We are building a new home for African pop and the creators moving it forward." maxLength={240} multiline /></Question>}
    {current === "team" && <Question note="Size the collaboration." title="How many people are on the team?" copy="This helps us shape approvals and workspace tools around you."><ChoiceGrid options={teamSizes} value={teamSize} onChange={(value) => choose(setTeamSize, value)} compact /></Question>}
    {current === "fund" && <Question note="Choose where the money should move." title="What kind of content do you want to fund?" copy="Pick two to five directions for your creator discovery feed."><InterestPicker selected={funds} onToggle={(label) => { setFunds((value) => toggleLimited(value, label)); setError(""); }} label="Content to fund" /></Question>}
    {current === "workflow" && <Question note="Map the way content happens today." title="How do you make content now?" copy="Choose the closest fit. We will adapt brief templates around it."><ChoiceGrid options={productionWorkflows} value={workflow} onChange={(value) => choose(setWorkflow, value)} /></Question>}
    {current === "view" && <Question note="Train the inspiration feed." title="What content do you want to see?" copy="Choose the work your team enjoys studying, sharing and referencing."><InterestPicker selected={watches} onToggle={(label) => { setWatches((value) => toggleLimited(value, label)); setError(""); }} label="Content to view" /></Question>}
    {current === "discovery" && <Question note="One quick signal." title="How did you hear about us?" copy="This helps us understand where funders are discovering Clippit."><ChoiceGrid options={discoverySources} value={discovery} onChange={(value) => choose(setDiscovery, value)} compact /></Question>}
    {current === "campaignGoal" && <Question note="Point the first campaign." title="What should creators help you achieve?" copy="Choose the result that matters most for your first recommendation."><ChoiceGrid options={campaignGoals} value={campaignGoal} onChange={(value) => choose(setCampaignGoal, value)} /></Question>}
    {current === "budget" && <Question note="Set a comfortable starting point." title="What budget range feels right?" copy="This is not a commitment. It helps us recommend realistic campaign shapes."><ChoiceGrid options={budgets} value={budget} onChange={(value) => { setBudget(value); setError(""); }} compact /></Question>}
  </div><SetupActions step={step} isLast={step === steps.length - 1} error={error} onBack={() => { setError(""); setStep((value) => Math.max(0, value - 1)); }} finalLabel={identity === "individual" ? "Build my funding feed" : "Open campaign workspace"} busy={saving} continueLabel={current === "photo" && !photo ? "Skip for now" : undefined} hint={current === "photo" ? photo ? "Photo added" : "This step is optional" : current === "fund" || current === "view" ? "Choose, then continue" : current === "description" ? "Write, then continue" : current === "name" || current === "location" || current === "organisation" || current === "website" ? "Press Enter to continue" : current === "budget" ? "Choose one, then continue" : "Choose one to continue"} /></form></section><BrandPreview displayName={displayName} photo={photo} location={location} identity={identity} registered={registered} funds={funds} watches={watches} budget={budget} campaignGoal={campaignGoal} /></div></main>;
}

function BrandPreview({ displayName, photo, location, identity, registered, funds, watches, budget, campaignGoal }: { displayName: string; photo: string; location: string; identity: "" | "brand" | "individual"; registered: "" | "yes" | "no"; funds: string[]; watches: string[]; budget: string; campaignGoal: string }) {
  const initials = displayName.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "BR";
  return <aside className="brand-brief-room" aria-label="Live funding profile preview"><div className="brand-brief-room__grid" /><p className="marker-note">Fund the idea. Prove the views.</p><div className="live-brief live-brief--intake"><div className="live-brief__head"><span>Funding profile</span><b>{identity === "individual" ? "Individual" : registered === "yes" ? "Registered" : "Draft"}</b></div><div className="live-brief__brand"><span className="live-brief__avatar">{photo ? <Image src={photo} alt="" fill unoptimized sizes="48px" /> : initials}</span><div><small>Commissioned by</small><strong>{displayName.trim() || "Your name"}</strong><small>{location || "Your city"}</small></div></div><div className="live-brief__asks"><small>Wants to fund</small><p>{funds.join(" / ")}</p></div><div className="live-brief__goal"><ProductIcon name="eye" /><span><small>Wants to view</small><strong>{watches.join(" / ")}</strong></span></div></div><div className="brand-pot-preview"><span>First pot direction</span><strong>{budget || "Not set"}</strong><div><i /></div><small>{campaignGoal || "Choose a campaign goal"}</small></div><div className="brand-proof-stamp"><ProductIcon name="shield" /><span>{identity === "individual" ? "Personal brief" : "Funding ready"}</span></div></aside>;
}
