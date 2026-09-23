"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type BriefRule = { id: string; text: string; kind: "must" | "avoid" };

export type BrandCampaignDraft = {
  title: string;
  description: string;
  sourceLink: string;
  coverImage: string;
  platforms: string[];
  assets: string[];
  niche: string;
  accessMode: "public" | "invite";
  inviteCode: string;
  rules: BriefRule[];
  minimumViews: number;
  videoCap: number;
  creatorCap: number;
  maxSubmissions: number;
  endCondition: "duration" | "budget";
  days: number;
  pot: number;
  rate: number;
};

const initialDraft: BrandCampaignDraft = {
  title: "The late-night bowl",
  description: "Show how Indomie fits into late-night work, study or travel.",
  sourceLink: "https://indomie.ng/brand-kit",
  coverImage: "",
  platforms: ["TikTok", "Instagram"],
  assets: ["Official campaign sound", "Product pack reference"],
  niche: "Comedy",
  accessMode: "public",
  inviteCode: "",
  rules: [
    { id: "rule-1", text: "Show the prepared noodles clearly on screen.", kind: "must" },
    { id: "rule-2", text: "Say or display: No long thing.", kind: "must" },
    { id: "rule-3", text: "Tag @indomie_nigeria and use #NoLongThing.", kind: "must" },
    { id: "rule-4", text: "Do not make health or nutrition claims.", kind: "avoid" },
  ],
  minimumViews: 1000,
  videoCap: 50000,
  creatorCap: 75000,
  maxSubmissions: 3,
  endCondition: "duration",
  days: 14,
  pot: 500000,
  rate: 500,
};

type BrandCampaignContextValue = {
  draft: BrandCampaignDraft;
  update: (next: Partial<BrandCampaignDraft>) => void;
  addRule: (kind: BriefRule["kind"], text: string) => void;
  removeRule: (id: string) => void;
  togglePlatform: (platform: string) => void;
  reset: () => void;
};

const BrandCampaignContext = createContext<BrandCampaignContextValue | null>(null);

export function BrandCampaignProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState(initialDraft);
  const hydrated = useRef(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = window.localStorage.getItem("clippit:brand-campaign-draft");
      hydrated.current = true;
      if (!stored) {
        window.localStorage.setItem("clippit:brand-campaign-draft", JSON.stringify(initialDraft));
        return;
      }
      try {
        setDraft({ ...initialDraft, ...JSON.parse(stored) });
      } catch {
        window.localStorage.removeItem("clippit:brand-campaign-draft");
        window.localStorage.setItem("clippit:brand-campaign-draft", JSON.stringify(initialDraft));
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    window.localStorage.setItem("clippit:brand-campaign-draft", JSON.stringify(draft));
  }, [draft]);

  const value = useMemo<BrandCampaignContextValue>(() => ({
    draft,
    update: (next) => setDraft((current) => ({ ...current, ...next })),
    addRule: (kind, text) => setDraft((current) => ({
      ...current,
      rules: [...current.rules, { id: `rule-${Date.now()}`, kind, text }],
    })),
    removeRule: (id) => setDraft((current) => ({ ...current, rules: current.rules.filter((rule) => rule.id !== id) })),
    togglePlatform: (platform) => setDraft((current) => ({
      ...current,
      platforms: current.platforms.includes(platform)
        ? current.platforms.filter((item) => item !== platform)
        : [...current.platforms, platform],
    })),
    reset: () => setDraft(initialDraft),
  }), [draft]);

  return <BrandCampaignContext.Provider value={value}>{children}</BrandCampaignContext.Provider>;
}

export function useBrandCampaign() {
  const value = useContext(BrandCampaignContext);
  if (!value) throw new Error("useBrandCampaign must be used inside BrandCampaignProvider");
  return value;
}
