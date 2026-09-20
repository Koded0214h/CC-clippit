"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type BriefRule = { id: string; text: string; kind: "must" | "avoid" };

export type BrandCampaignDraft = {
  title: string;
  description: string;
  sourceLink: string;
  platforms: string[];
  rules: BriefRule[];
  minimumViews: number;
  creatorCap: number;
  days: number;
  pot: number;
  rate: number;
};

const initialDraft: BrandCampaignDraft = {
  title: "The late-night bowl",
  description: "Show how Indomie fits into late-night work, study or travel.",
  sourceLink: "https://indomie.ng/brand-kit",
  platforms: ["TikTok", "Instagram"],
  rules: [
    { id: "rule-1", text: "Show the prepared noodles clearly on screen.", kind: "must" },
    { id: "rule-2", text: "Say or display: No long thing.", kind: "must" },
    { id: "rule-3", text: "Tag @indomie_nigeria and use #NoLongThing.", kind: "must" },
    { id: "rule-4", text: "Do not make health or nutrition claims.", kind: "avoid" },
  ],
  minimumViews: 1000,
  creatorCap: 75000,
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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = window.localStorage.getItem("clippit:brand-campaign-draft");
      if (!stored) return;
      try {
        setDraft({ ...initialDraft, ...JSON.parse(stored) });
      } catch {
        window.localStorage.removeItem("clippit:brand-campaign-draft");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
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
