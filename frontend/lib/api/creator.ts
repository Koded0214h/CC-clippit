import { api } from "./client";
import type { CampaignOut } from "./campaigns";
import type { EarningsSummary } from "./earnings";

export interface CreatorOverview {
  closing_soon: CampaignOut | null;
  new_matches: number;
  earnings: EarningsSummary;
}

export interface ClipRow {
  id: string;
  title: string | null;
  platform: string;
  campaign_slug: string;
  campaign_title: string;
  brand: string | null;
  status: string;
  label: string;
  verified_views: number;
  earned: number;
  link: string;
  submitted_at: string;
}

export interface ClipsOut {
  active_clips: number;
  verified_views: number;
  total_earned: number;
  items: ClipRow[];
}

export const creatorApi = {
  overview: () => api.get<CreatorOverview>("/creators/me/overview"),
  clips: () => api.get<ClipsOut>("/creators/me/clips"),
};
