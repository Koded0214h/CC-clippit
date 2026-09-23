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

export const submissionsApi = {
  get: (submissionId: string) => api.get<SubmissionOut>(`/submissions/${submissionId}`),
  getEarnings: (submissionId: string) => api.get<SubmissionEarningsOut>(`/submissions/${submissionId}/earnings`),
  appeal: (submissionId: string, reason: string, evidenceUploadId?: string) =>
    api.post<void>(`/submissions/${submissionId}/appeal`, { reason, evidence_upload_id: evidenceUploadId ?? null }),
  withdraw: (submissionId: string) => api.post<void>(`/submissions/${submissionId}/withdraw`, {}),
};
