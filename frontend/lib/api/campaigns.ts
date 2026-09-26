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
  video_cap_amount?: number | null;
  max_submissions?: number | null;
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
  access_mode?: "public" | "invite";
  assets?: Array<{ id?: string; name: string; url: string; kind?: string }>;
  end_condition?: "duration" | "budget";
  video_cap?: number | null;
  max_submissions?: number | null;
  status: "draft" | "pending_funding" | "active" | "closed" | string;
  phase: string;
  accepting_entries: boolean;
  ends_at?: string | null;
  duration_days?: number | null;
  source_link?: string | null;
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

export interface CampaignStats {
  campaign_id: string;
  phase: string;
  accepting_entries: boolean;
  pot: number;
  spent: number;
  remaining: number;
  percent_remaining: number;
  verified_views: number;
  views_last_24h: number;
  submissions: number;
  approved: number;
  review: number;
  checking: number;
  rejected: number;
  time_left: TimeLeft | null;
  last_reading_at: string | null;
}

export interface CampaignSubmissionRow {
  id: string;
  creator_id: string;
  creator_name: string;
  creator_handle: string | null;
  title: string | null;
  platform: string;
  url: string;
  verified_views: number;
  earned: number;
  state: string;
  submitted_at: string;
}

export interface MyCampaignRow {
  campaign: CampaignOut;
  membership_status: "joined" | "submitted" | "active" | "completed" | "left" | string;
  joined_at: string | null;
  left_at: string | null;
  submission_id: string | null;
  submission_status: string | null;
}

export interface MembershipOut {
  id: string;
  campaign_id: string;
  joined_at: string;
  left_at: string | null;
}

export type CampaignFeed = "all" | "for_you" | "joined" | "closing_soon" | "open";

function qs(params: Record<string, string | number | undefined | null>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const campaignsApi = {
  list: (params?: { feed?: CampaignFeed; category?: string; platform?: string; q?: string; limit?: number; offset?: number }) =>
    api.get<CampaignOut[]>(`/campaigns${qs({ ...params })}`),

  mine: (params?: { membership_status?: string; limit?: number; offset?: number }) =>
    api.get<MyCampaignRow[]>(`/creators/me/campaigns${qs({ ...params })}`),

  get: (ref: string) => api.get<CampaignOut>(`/campaigns/${ref}`),

  getStats: (ref: string) => api.get<CampaignStats>(`/campaigns/${ref}/stats`),

  getSubmissions: (ref: string, limit?: number) =>
    api.get<CampaignSubmissionRow[]>(`/campaigns/${ref}/submissions${qs({ limit })}`),

  join: (ref: string, inviteCode?: string) =>
    api.post<MembershipOut>(`/campaigns/${ref}/join${qs({ invite_code: inviteCode })}`, {}),

  leave: (ref: string) => api.delete<MembershipOut>(`/campaigns/${ref}/join`),
};
