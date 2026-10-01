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

export type PerformanceMetricType =
  | "view"
  | "comment"
  | "share"
  | "visit"
  | "signup"
  | "lead"
  | "purchase";

export interface CampaignMetric {
  id?: string;
  metric_type: PerformanceMetricType;
  rate_amount: number;
  unit_size: number;
  min_threshold: number;
  verification_method?: string;
  position?: number;
}

export interface ConversionSetup {
  destination_type: "website" | "whatsapp";
  destination_url?: string | null;
  whatsapp_number?: string | null;
  attribution_window_days: number;
  attribution_model: "first_touch";
}

export interface CampaignIntegrationOut {
  campaign_id: string;
  configured: boolean;
  secret_last_four: string | null;
  created_at: string | null;
  rotated_at: string | null;
  event_endpoint: string;
  tracker_script_url: string;
  attribution_parameter: "clippit_ref";
  destination_url: string | null;
  attribution_window_days: number;
  attribution_model: "first_touch";
  selected_event_types: Array<"visit" | "signup" | "lead" | "purchase">;
  events_received: number;
  last_event_at: string | null;
}

export interface CampaignCreatePayload {
  title: string;
  description: string;
  category?: string | null;
  source_link?: string | null;
  platforms: string[];
  pot: number;
  payout_rule: {
    rate_per_1000_views: number;
    cap_amount?: number | null;
    video_cap_amount?: number | null;
    max_submissions?: number | null;
    min_views_threshold: number;
  };
  duration_days?: number | null;
  rules: Array<{ kind: "must" | "avoid"; text: string }>;
  access_mode: "public" | "invite";
  end_condition: "duration" | "budget";
  performance_metrics: CampaignMetric[];
  conversion_setup?: ConversionSetup | null;
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
  performance?: Record<string, number>;
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
  performance_metrics: CampaignMetric[];
  conversion_setup: ConversionSetup | null;
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
  performance: Record<string, number>;
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
  performance?: Record<string, number>;
  state: string;
  submitted_at: string;
}

export interface MyCampaignRow {
  campaign: CampaignOut;
  membership_status:
    | "joined"
    | "submitted"
    | "active"
    | "completed"
    | "left"
    | string;
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

export interface FundingQuoteOut {
  campaign_id: string;
  pot: number;
  fee: number;
  fee_rate: number;
  total: number;
  currency: string;
  methods: Array<"bank" | "card">;
  valid_for_minutes: number;
  terms_version: string;
}

export interface FundingOrderOut {
  id: string;
  campaign_id: string;
  reference: string;
  status: string;
  method: "bank" | "card";
  pot: number;
  fee: number;
  total: number;
  provider: string;
  sandbox: boolean;
  provider_reference: string | null;
  checkout_url: string | null;
  collection: { bank_name: string; account_number: string; account_name: string } | null;
  campaign_status: string;
  created_at: string;
  confirmed_at: string | null;
}

export interface RefundOut {
  id: string;
  campaign_id: string;
  amount: number;
  status: string;
  reason: string;
  provider: string;
  sandbox: boolean;
  provider_reference: string | null;
  failure_reason: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface CampaignDraftOut {
  id: string;
  schema_version: number;
  status: "not_started" | "in_progress" | "finalized";
  step: string | null;
  revision: number;
  answers: Record<string, unknown>;
  blockers: Record<string, string>;
  finalized_campaign_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignDraftFinalizeOut {
  campaign_id: string;
  campaign_slug: string;
  next_route: string;
}

export type CampaignFeed =
  | "all"
  | "for_you"
  | "joined"
  | "closing_soon"
  | "open";

function qs(params: Record<string, string | number | undefined | null>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "")
      query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const campaignsApi = {
  create: (payload: CampaignCreatePayload) =>
    api.post<CampaignOut>("/campaigns", payload),
  list: (params?: {
    feed?: CampaignFeed;
    category?: string;
    platform?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => api.get<CampaignOut[]>(`/campaigns${qs({ ...params })}`),

  mine: (params?: {
    membership_status?: string;
    limit?: number;
    offset?: number;
  }) => api.get<MyCampaignRow[]>(`/creators/me/campaigns${qs({ ...params })}`),

  get: (ref: string) => api.get<CampaignOut>(`/campaigns/${ref}`),

  getStats: (ref: string) => api.get<CampaignStats>(`/campaigns/${ref}/stats`),

  getSubmissions: (ref: string, limit?: number) =>
    api.get<CampaignSubmissionRow[]>(
      `/campaigns/${ref}/submissions${qs({ limit })}`,
    ),

  downloadReport: (ref: string) =>
    api.download(`/campaigns/${encodeURIComponent(ref)}/report`),

  join: (ref: string, inviteCode?: string) =>
    api.post<MembershipOut>(
      `/campaigns/${ref}/join${qs({ invite_code: inviteCode })}`,
      {},
    ),

  leave: (ref: string) => api.delete<MembershipOut>(`/campaigns/${ref}/join`),

  createAttributionLink: (ref: string, submissionId?: string) =>
    api.post<{
      id: string;
      campaign_id: string;
      short_code: string;
      tracking_url: string;
      destination_url: string;
      expires_at: string | null;
    }>(`/campaigns/${ref}/attribution-links`, {
      submission_id: submissionId ?? null,
    }),

  rotateIntegrationSecret: (ref: string) =>
    api.post<{
      campaign_id: string;
      secret: string;
      last_four: string;
      warning: string;
    }>(`/campaigns/${ref}/integration-secret`, {}),

  integration: (ref: string) =>
    api.get<CampaignIntegrationOut>(`/campaigns/${ref}/integration`),

  performance: (ref: string) =>
    api.get<{
      campaign_id: string;
      metrics: Array<{
        metric_type: string;
        total: number;
        approved: number;
        pending: number;
        earned: number;
      }>;
    }>(`/campaigns/${ref}/performance`),

  pause: (ref: string, mode: "acquisition" | "full" = "acquisition") =>
    api.post<CampaignOut>(`/campaigns/${ref}/pause?mode=${mode}`, {}),
  resume: (ref: string) => api.post<CampaignOut>(`/campaigns/${ref}/resume`, {}),
  close: (ref: string) => api.post<CampaignOut>(`/campaigns/${ref}/close`, {}),
  activate: (ref: string) => api.post<CampaignOut>(`/campaigns/${ref}/activate`, {}),
  fundingQuote: (ref: string) => api.post<FundingQuoteOut>(`/campaigns/${ref}/funding/quote`, {}),
  fund: (ref: string, method: "bank" | "card") => api.post<FundingOrderOut>(`/campaigns/${ref}/funding`, { method }),
  funding: (ref: string) => api.get<FundingOrderOut>(`/campaigns/${ref}/funding`),
  confirmFunding: (ref: string) => api.post<FundingOrderOut>(`/campaigns/${ref}/funding/confirm`, {}),
  cancelFunding: (ref: string) => api.delete<FundingOrderOut>(`/campaigns/${ref}/funding`),
  refunds: (ref: string) => api.get<RefundOut[]>(`/campaigns/${ref}/refunds`),
  requestRefund: (ref: string, reason: string) => api.post<RefundOut>(`/campaigns/${ref}/refunds`, { reason }),
};

export const campaignDraftsApi = {
  create: () => api.post<CampaignDraftOut>("/campaign-drafts", {}),
  list: () => api.get<CampaignDraftOut[]>("/campaign-drafts"),
  get: (id: string) => api.get<CampaignDraftOut>(`/campaign-drafts/${id}`),
  update: (id: string, payload: Record<string, unknown> & { revision: number }) =>
    api.patch<CampaignDraftOut>(`/campaign-drafts/${id}`, payload),
  remove: (id: string) => api.delete<void>(`/campaign-drafts/${id}`),
  finalize: (id: string) => api.post<CampaignDraftFinalizeOut>(`/campaign-drafts/${id}/finalize`, {}),
};
