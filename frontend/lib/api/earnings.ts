import { api } from "./client";

export interface EarningsSummary {
  payable: number;
  in_hold: number;
  processing: number;
  paid_all_time: number;
  total_accrued: number;
  lifetime_views: number;
  completed_payouts: number;
  added_this_week: number;
  hold_days: number;
  next_clears_at: string | null;
  last_earned_at: string | null;
  min_withdrawal: number;
  active_clips: number;
}

export interface EarningRow {
  id: string;
  date: string;
  submission_id: string;
  clip: string;
  campaign_slug: string;
  campaign_title: string;
  brand: string | null;
  billable_views: number;
  amount: number;
  state: string;
  payable_at: string;
}

export interface EarningsHistory {
  items: EarningRow[];
  total: number;
}

export interface LeaderRow {
  rank: number;
  creator_id: string;
  name: string;
  handle: string | null;
  views: number;
  earned: number;
  is_me: boolean;
}

export interface Leaderboard {
  period: string;
  updated_at: string;
  items: LeaderRow[];
  me: LeaderRow | null;
}

export const earningsApi = {
  summary: () => api.get<EarningsSummary>("/earnings/summary"),

  history: (params?: { cursor?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.cursor) query.set("cursor", params.cursor);
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return api.get<EarningsHistory>(`/earnings/history${qs ? `?${qs}` : ""}`);
  },

  leaderboard: (params?: { period?: "week" | "all"; campaign?: string }) => {
    const query = new URLSearchParams();
    if (params?.period) query.set("period", params.period);
    if (params?.campaign) query.set("campaign", params.campaign);
    const qs = query.toString();
    return api.get<Leaderboard>(`/leaderboard${qs ? `?${qs}` : ""}`);
  },
};
