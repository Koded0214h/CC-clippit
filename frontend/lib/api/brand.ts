import { api } from "./client";
import type { CampaignOut } from "./campaigns";

export interface BrandOverviewOut {
  organisation_name: string;
  pending_reviews: number;
  live_campaigns: number;
  draft_campaigns: number;
  completed_campaigns: number;
  total_pot: number;
  total_spent: number;
  views_last_24h: number;
  earnings_last_24h: number;
  unmatched_spend: number;
  featured: CampaignOut | null;
}

export interface ReviewCounts {
  needs_review: number;
  appeals: number;
  resolved: number;
}

export interface ReviewCard {
  id: string;
  creator_name: string;
  creator_handle: string | null;
  title: string | null;
  platform: string;
  campaign_slug: string;
  campaign_title: string;
  video_url: string | null;
  url: string;
  confidence: number | null;
  issue: string | null;
  status: string;
  is_appeal: boolean;
  submitted_at: string;
}

export interface ReviewQueue {
  tab: string;
  counts: ReviewCounts;
  items: ReviewCard[];
}

export const brandApi = {
  overview: () => api.get<BrandOverviewOut>("/brand/overview"),

  reviews: (tab?: "needs_review" | "appeals" | "resolved") => {
    const qs = tab ? `?tab=${tab}` : "";
    return api.get<ReviewQueue>(`/brand/reviews${qs}`);
  },

  getReview: (submissionId: string) => api.get<ReviewCard>(`/brand/reviews/${submissionId}`),

  approveReview: (submissionId: string, note?: string) =>
    api.post<void>(`/brand/reviews/${submissionId}/approve`, { note: note ?? null }),

  requestCorrection: (submissionId: string, reason: string, requirementId?: string) =>
    api.post<void>(`/brand/reviews/${submissionId}/correction`, {
      reason,
      requirement_id: requirementId ?? null,
    }),
};
