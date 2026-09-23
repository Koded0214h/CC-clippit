import { api } from "./client";

export interface RequirementResultOut {
  id: string;
  rule_id: string | null;
  kind: string;
  text: string;
  position: number;
  verdict: "pass" | "fail" | "review" | "skipped";
  note: string | null;
}

export interface VerificationStep {
  key: string;
  title: string;
  detail: string;
  state: "done" | "active" | "pending" | "failed";
}

export interface AppealOut {
  id: string;
  status: string;
  reason: string;
  evidence_url: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface VerificationOut {
  status: string;
  confidence: number | null;
  summary: string | null;
  verdict_at: string | null;
  decided_by_human: boolean;
  requirements: RequirementResultOut[];
  passed: number;
  total: number;
  failed_requirement: RequirementResultOut | null;
  steps: VerificationStep[];
  appeal: AppealOut | null;
}

export interface SubmissionCampaignOut {
  id: string;
  slug: string;
  title: string;
  brand_name: string | null;
}

export interface SubmissionOut {
  id: string;
  campaign_id: string;
  creator_id: string;
  platform: string;
  url: string;
  title: string | null;
  video_url: string | null;
  status: string;
  rejection_code: string | null;
  rejection_message: string | null;
  created_at: string;
  updated_at: string;
  campaign: SubmissionCampaignOut | null;
  verification: VerificationOut | null;
  resubmitted_from_id: string | null;
}

export interface SubmissionEarningsOut {
  submission_id: string;
  verified_views: number;
  accrued: number;
  next_payable_at: string | null;
  payable_now: number;
}

export interface SubmissionCreateIn {
  campaign_id: string;
  platform: string;
  url: string;
  title?: string | null;
  video_upload_id?: string | null;
}

export interface ResubmitIn {
  platform: string;
  url: string;
  title?: string | null;
  video_upload_id?: string | null;
}

export interface SubmissionListParams {
  campaign_id?: string;
  verification?: string;
}

// --- performance (thin proxy onto Intelligence's own contract) ---

export interface ContentIdentityOut {
  platform: string;
  platform_content_id: string;
  url: string;
  author_username: string | null;
  kind: string;
  post_type: string;
  published_at: string | null;
}

export interface MetricsBlockOut {
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  reach: number | null;
  impressions: number | null;
}

export interface PerformanceFeaturesOut {
  incremental_views: number | null;
  billable_views: number | null;
  view_velocity_per_hour: number | null;
  growth_rate: number | null;
  like_view_ratio: number | null;
  comment_view_ratio: number | null;
  share_view_ratio: number | null;
  observation_count: number;
  first_observed_at: string | null;
}

export interface ProvenanceOut {
  platform: string;
  source: string;
  snapshot_id: string | null;
  observed_at: string;
}

export interface TrackingStateOut {
  status: "active" | "stopped" | "failed";
  reason_code: string | null;
  message: string | null;
  next_poll_at: string | null;
  last_success_at: string | null;
}

export interface PerformanceResultOut {
  submission_id: string;
  content: ContentIdentityOut;
  metrics: MetricsBlockOut;
  features: PerformanceFeaturesOut;
  provenance: ProvenanceOut;
  tracking: TrackingStateOut | null;
}

export const submissionsApi = {
  create: (payload: SubmissionCreateIn) => api.post<SubmissionOut>("/submissions", payload),

  list: (params?: SubmissionListParams) => {
    const query = new URLSearchParams();
    if (params?.campaign_id) query.set("campaign_id", params.campaign_id);
    if (params?.verification) query.set("verification", params.verification);
    const qs = query.toString();
    return api.get<SubmissionOut[]>(`/submissions${qs ? `?${qs}` : ""}`);
  },

  resubmit: (submissionId: string, payload: ResubmitIn) =>
    api.post<SubmissionOut>(`/submissions/${submissionId}/resubmit`, payload),

  get: (submissionId: string) => api.get<SubmissionOut>(`/submissions/${submissionId}`),
  getEarnings: (submissionId: string) => api.get<SubmissionEarningsOut>(`/submissions/${submissionId}/earnings`),
  appeal: (submissionId: string, reason: string, evidenceUploadId?: string) =>
    api.post<void>(`/submissions/${submissionId}/appeal`, { reason, evidence_upload_id: evidenceUploadId ?? null }),
  withdraw: (submissionId: string) => api.post<void>(`/submissions/${submissionId}/withdraw`, {}),
  getPerformance: (submissionId: string, sinceSnapshotId?: string) => {
    const qs = sinceSnapshotId ? `?since_snapshot_id=${encodeURIComponent(sinceSnapshotId)}` : "";
    return api.get<PerformanceResultOut>(`/submissions/${submissionId}/performance${qs}`);
  },
};
