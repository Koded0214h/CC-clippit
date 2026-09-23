import { api } from "./client";

export interface BrandOut {
  id: string;
  name: string;
  photo_url: string | null;
  verified: boolean;
}

export interface PayoutRuleOut {
  rate_per_1000_views: number;
  cap_amount: number | null;
  min_views_threshold: number;
}

export interface RuleOut {
  id: string;
  kind: "must" | "avoid";
  text: string;
  position: number;
}

export interface TimeLeft {
  days: number;
  hours: number;
  ended: boolean;
}

export interface CampaignMetrics {
  verified_views: number;
  submissions: number;
  approved: number;
  review: number;
  checking: number;
  rejected: number;
  earned: number;
}

export interface CampaignOut {
  id: string;
  slug: string;
  brand: BrandOut | null;
  title: string;
  tagline: string | null;
  description: string;
  category: string | null;
  cover_image_url: string | null;
  platforms: string[];
  status: string;
  phase: string;
  accepting_entries: boolean;
  time_left: TimeLeft | null;
  pot: number;
  spent: number;
  remaining: number;
  payout_rule: PayoutRuleOut | null;
  rules: RuleOut[];
  feed_status: string | null;
  joined: boolean | null;
  metrics: CampaignMetrics | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignListOut {
  items: CampaignOut[];
  total: number;
  next_cursor: string | null;
}

export interface MyCampaignRow {
  campaign: CampaignOut;
  membership_status: string;
  joined_at: string | null;
  submission_id: string | null;
  submission_status: string | null;
}

export const campaignsApi = {
  list: (params?: { feed?: string; category?: string; platform?: string; search?: string; cursor?: string }) => {
    const query = new URLSearchParams();
    if (params?.feed) query.set("feed", params.feed);
    if (params?.category) query.set("category", params.category);
    if (params?.platform) query.set("platform", params.platform);
    if (params?.search) query.set("search", params.search);
    if (params?.cursor) query.set("cursor", params.cursor);
    const qs = query.toString();
    return api.get<CampaignListOut>(`/campaigns${qs ? `?${qs}` : ""}`);
  },

  get: (ref: string) => api.get<CampaignOut>(`/campaigns/${ref}`),

  join: (ref: string) => api.post<void>(`/campaigns/${ref}/join`, {}),

  leave: (ref: string) => api.delete<void>(`/campaigns/${ref}/join`),
};
