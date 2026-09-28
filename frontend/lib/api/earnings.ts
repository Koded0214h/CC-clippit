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
  metric_type: string;
  billable_units: number;
  unit_size: number;
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
  scope?: string;
  updated_at: string;
  items: LeaderRow[];
  me: LeaderRow | null;
}

export interface EarningEntryDetail {
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
  views_total?: number;
  thousands?: number;
  rate_per_1000_views?: number;
  metric_type?: string;
  billable_units?: number;
  unit_size?: number;
  rate_amount?: number;
  cap_amount?: number | null;
  reference?: string | null;
  payout_id?: string | null;
}

function qs(params: Record<string, string | number | undefined | null>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "")
      query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const earningsApi = {
  summary: () => api.get<EarningsSummary>("/earnings/summary"),

  history: (params?: { limit?: number; offset?: number }) =>
    api.get<EarningsHistory>(`/earnings/history${qs({ ...params })}`),

  entry: (entryId: string) =>
    api.get<EarningEntryDetail>(`/earnings/entries/${entryId}`),

  leaderboard: (params?: {
    period?: "week" | "all";
    scope?: "global" | "country";
    campaign_id?: string;
    limit?: number;
  }) => api.get<Leaderboard>(`/leaderboard${qs({ ...params })}`),
};
