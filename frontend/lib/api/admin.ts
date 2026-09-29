import { api } from "./client";

// --- overview ------------------------------------------------------------------

export interface AdminOverview {
  users: Record<string, number>;
  campaigns: Record<string, number>;
  submissions_needing_review: number;
  open_appeals: number;
  payouts: Record<string, number>;
  creator_liability: number;
  funding_awaiting_confirmation: number;
  blocked_earning_accounts: number;
}

// --- payouts ---------------------------------------------------------------------

export interface AdminPayoutRow {
  id: string;
  reference: string;
  status: string;
  amount: number;
  creator_id: string;
  creator_email: string;
  creator_name: string;
  provider: string;
  provider_reference: string | null;
  failure_reason: string | null;
  initiated_at: string;
  completed_at: string | null;
}

// --- funding -----------------------------------------------------------------------

export interface AdminFundingRow {
  id: string;
  reference: string;
  status: string;
  campaign_id: string;
  campaign_title: string;
  total: number;
  provider: string;
  created_at: string;
  confirmed_at: string | null;
}

// --- blocked accounts / audit --------------------------------------------------------

export interface BlockedAccountRow {
  submission_id: string;
  campaign_id: string;
  creator_id: string;
  reason: string;
  cumulative_views: number;
  accrued: number;
  last_settled_at: string | null;
}

export interface AuditRow {
  id: string;
  created_at: string;
  kind: string;
  actor_id: string | null;
  campaign_id: string | null;
  submission_id: string | null;
  subject_id: string | null;
  amount: number | null;
  data: Record<string, unknown>;
}

export interface RunResult {
  processed: number;
}

// --- users -------------------------------------------------------------------------

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  onboarding_completed: boolean;
  suspended: boolean;
  created_at: string;
}

export interface AdminUserDetail extends AdminUserRow {
  active_sessions: number;
  connected_platforms: number;
  money_summary: Record<string, number>;
  suspension_scopes: string[];
  suspension_reason: string | null;
  suspension_expires_at: string | null;
  recent_audit: AuditRow[];
}

// --- submissions / trust -------------------------------------------------------------

export interface AdminSubmissionRow {
  id: string;
  campaign_id: string;
  campaign_title: string;
  creator_id: string;
  creator_name: string;
  platform: string;
  status: string;
  verification_status: string;
  flagged: boolean;
  cumulative_views: number;
  accrued: number;
  created_at: string;
}

export interface AdminSubmissionDetail extends AdminSubmissionRow {
  url: string;
  verification_summary: string | null;
  trust: Record<string, unknown> | null;
  admin_trust_override: boolean | null;
  hold_active: boolean;
  hold_reason: string | null;
}

export interface RandomAuditRow {
  submission_id: string;
  campaign_id: string;
  creator_id: string;
  platform: string;
  created_at: string;
}

// --- campaigns -------------------------------------------------------------------------

export interface AdminCampaignRow {
  id: string;
  slug: string;
  title: string;
  organisation_id: string;
  organisation_name: string;
  status: string;
  pot: number;
  spent: number;
  needs_review: number;
  created_at: string;
}

export interface AdminCampaignDetail extends AdminCampaignRow {
  platforms: string[];
  duration_days: number | null;
  ends_at: string | null;
  submissions: number;
}

// --- earnings --------------------------------------------------------------------------

export interface AdminEarningEntryRow {
  id: string;
  submission_id: string;
  campaign_id: string;
  creator_id: string;
  amount: number;
  billable_views: number;
  thousands: number;
  payable_at: string;
  accrued_at: string;
  on_hold: boolean;
  trust_blocked: boolean;
}

export interface EarningEntryDetail {
  id: string;
  submission_id: string;
  campaign_id: string;
  creator_id: string;
  amount: number;
  billable_views: number;
  thousands: number;
  payable_at: string;
  accrued_at: string;
  [key: string]: unknown;
}

// --- ledger ----------------------------------------------------------------------------

export interface AdminLedgerRow {
  id: string;
  kind: "funding" | "refund" | "payout";
  organisation_id: string | null;
  creator_id: string | null;
  campaign_id: string | null;
  amount: number;
  status: string;
  provider: string;
  provider_reference: string | null;
  reference: string;
  created_at: string;
  settled_at: string | null;
}

// --- operators -------------------------------------------------------------------------

export interface OperatorRow {
  id: string;
  email: string;
  full_name: string;
  permissions: string[];
  suspended: boolean;
  invited_by: string | null;
  last_active_at: string | null;
  created_at: string;
}

export interface AdminInvitationCreated {
  id: string;
  email: string;
  permissions: string[];
  expires_at: string;
  invite_token: string;
}

// --- provider health ---------------------------------------------------------------------

export interface ProviderHealth {
  name: string;
  kind: string;
  configured: boolean;
  sandbox: boolean | null;
  detail: string | null;
}

// --- system health / delivery (live telemetry; also streamed over /admin/ws) --------------
// Contract documented in architecture/ops-api.md.

export type OpsStatus = "operational" | "degraded" | "down" | "sandbox" | "disabled";
export interface SystemService {
  key: "api" | "database" | "jobs" | "media_checks" | "storage" | "host";
  name: string; status: OpsStatus;
  /** e.g. { label: "Latency (p95)", display: "48 ms" } */
  headline: { label: string; display: string };
  detail: string;
  /** Persisted, survives restarts. null until ~5 minutes of samples exist (and for services we can't sample). */
  availability_30d: number | null;
  /** Small numeric series for a sparkline bar chart. */
  trend: number[];
  [extra: string]: unknown;
}
export interface SeriesPoint { t: number; ok: number; client_err: number; server_err: number; p50: number | null; p95: number | null }
export interface SystemHealth {
  generated_at: number; environment: string; status: "operational" | "degraded" | "down";
  uptime_seconds: number; started_at: number; services: SystemService[];
  requests: number; error_rate: number; throughput_rpm: number;
  latency: { p50: number | null; p95: number | null; p99: number | null };
  series: SeriesPoint[]; db_history: Array<{ ts: number; ok: boolean; ms: number | null }>;
  log_counts: { info: number; warn: number; error: number };
}

export type DeliveryStatus = "healthy" | "attention" | "failing" | "quiet" | "unconfigured";
export interface DeliveryEvent { id: string; ts: number | null; title: string; ref: string; result: string }
export interface DeliveryCard {
  key: string; name: string; note: string; status: DeliveryStatus;
  /** 0-100, or null when there is nothing to measure yet. */
  success_rate: number | null;
  headline: { label: string; display: string };
  /** Per-minute buckets for the "last 60 minutes" chart; null when there is no time series. */
  window: { minutes: number; buckets: Array<{ t: number; ok: number; retried: number; failed: number }> } | null;
  events: DeliveryEvent[];
  facts: Record<string, string | number | boolean | null>;
}
export interface DeliveryFeed { kind: "webhooks" | "social" | "notifications"; generated_at: number; status: "healthy" | "attention" | "failing"; scope: string; cards: DeliveryCard[] }

// --- support tickets ---------------------------------------------------------------------

export interface SupportMessageOut {
  id: string;
  author_id: string;
  from_admin: boolean;
  body: string;
  attachment_upload_ids: string[];
  created_at: string;
}

export interface SupportNoteOut {
  id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export interface TicketOut {
  id: string;
  category: string;
  subject: string;
  status: "open" | "closed";
  priority: "low" | "normal" | "high" | "urgent";
  resource_type: string | null;
  resource_id: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface TicketAdminOut extends TicketOut {
  messages: SupportMessageOut[];
  notes: SupportNoteOut[];
  customer_email: string;
  customer_role: string;
  assignee_id: string | null;
}

// --- disputes ----------------------------------------------------------------------------

export interface DisputeMessageOut {
  id: string;
  author_id: string;
  from_admin: boolean;
  body: string;
  evidence_upload_ids: string[];
  created_at: string;
}

export interface DisputeOut {
  id: string;
  type: "submission_verdict" | "earning_entry" | "payout" | "funding_order" | "refund";
  resource_id: string;
  reason: string;
  status: "open" | "awaiting_customer" | "resolved" | "withdrawn";
  amount_at_risk: number | null;
  deadline_at: string;
  resolution: "upheld" | "denied" | "partial" | null;
  resolution_note: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface DisputeAdminOut extends DisputeOut {
  messages: DisputeMessageOut[];
  assignee_id: string | null;
  customer_role: string;
}

// --- reports -----------------------------------------------------------------------------

export interface ReportOut {
  id: string;
  target_type: "campaign" | "creator_profile" | "organisation_profile" | "submission";
  target_id: string;
  reason: string;
  status: "open" | "resolved";
  created_at: string;
}

export interface ReportAdminOut extends ReportOut {
  reporter_id: string;
  details: string | null;
  evidence_upload_ids: string[];
  resolution: "no_action" | "content_restricted" | "campaign_paused" | "account_sanctioned" | "escalated" | null;
  resolution_note: string | null;
  resolved_at: string | null;
}

// --- helper --------------------------------------------------------------------------------

function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const s = query.toString();
  return s ? `?${s}` : "";
}

export const adminApi = {
  // overview
  overview: () => api.get<AdminOverview>("/admin/overview"),

  // payouts
  listPayouts: (params?: { status_filter?: string; limit?: number; offset?: number }) =>
    api.get<AdminPayoutRow[]>(`/admin/payouts${qs(params ?? {})}`),
  retryPayout: (payoutId: string) => api.post<AdminPayoutRow>(`/admin/payouts/${payoutId}/retry`, {}),
  failPayout: (payoutId: string, reason: string) =>
    api.post<AdminPayoutRow>(`/admin/payouts/${payoutId}/fail`, { reason }),

  // funding
  listFunding: (params?: { status_filter?: string; limit?: number }) =>
    api.get<AdminFundingRow[]>(`/admin/funding${qs(params ?? {})}`),
  confirmFunding: (orderId: string, payload: { amount_received: number; note: string }) =>
    api.post<AdminFundingRow>(`/admin/funding/${orderId}/confirm`, payload),

  // earnings / blocked / settlement / sweep
  blockedAccounts: () => api.get<BlockedAccountRow[]>("/admin/earnings/blocked"),
  runSettlement: () => api.post<RunResult>("/admin/earnings/settle", {}),
  runSweep: () => api.post<RunResult>("/admin/campaigns/sweep", {}),

  // organisations
  verifyBusiness: (userId: string, payload: { verified: boolean; legal_name?: string | null }) =>
    api.post<{ user_id: string; business_verified: boolean; legal_name: string | null }>(
      `/admin/organisations/${userId}/verify-business`,
      payload,
    ),

  // audit
  readAudit: (params?: { kind?: string; campaign_id?: string; submission_id?: string; subject_id?: string; limit?: number }) =>
    api.get<AuditRow[]>(`/admin/audit${qs(params ?? {})}`),

  // users
  listUsers: (params?: { role?: string; q?: string; verified?: boolean; suspended?: boolean; limit?: number; offset?: number }) =>
    api.get<AdminUserRow[]>(`/admin/users${qs(params ?? {})}`),
  userDetail: (userId: string) => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  suspendUser: (userId: string, payload: { scopes: string[]; reason: string; duration_days?: number | null }) =>
    api.post<AdminUserDetail>(`/admin/users/${userId}/suspend`, payload),
  restoreUser: (userId: string) => api.post<AdminUserDetail>(`/admin/users/${userId}/restore`, {}),

  // submissions / trust
  flaggedSubmissions: (params?: { limit?: number; offset?: number }) =>
    api.get<AdminSubmissionRow[]>(`/admin/submissions/flagged${qs(params ?? {})}`),
  allSubmissions: (params?: {
    verification_status?: string;
    status?: string;
    platform?: string;
    campaign_id?: string;
    creator_id?: string;
    flagged?: boolean;
    limit?: number;
    offset?: number;
  }) => api.get<AdminSubmissionRow[]>(`/admin/submissions${qs(params ?? {})}`),
  randomAudits: (params?: { limit?: number }) => api.get<RandomAuditRow[]>(`/admin/submissions/random-audits${qs(params ?? {})}`),
  submissionDetail: (submissionId: string) => api.get<AdminSubmissionDetail>(`/admin/submissions/${submissionId}`),
  clearTrustFlag: (submissionId: string, note: string) =>
    api.post<AdminSubmissionDetail>(`/admin/submissions/${submissionId}/trust/clear`, { note }),
  confirmTrustFraud: (submissionId: string, note: string) =>
    api.post<AdminSubmissionDetail>(`/admin/submissions/${submissionId}/trust/confirm`, { note }),
  submitTrustReview: (submissionId: string, payload: { outcome: string; source?: string; notes?: string | null }) =>
    api.post<Record<string, unknown>>(`/admin/submissions/${submissionId}/trust/review`, payload),

  // campaigns
  listCampaigns: (params?: { status?: string; organisation_id?: string; limit?: number; offset?: number }) =>
    api.get<AdminCampaignRow[]>(`/admin/campaigns${qs(params ?? {})}`),
  campaignDetail: (campaignRef: string) => api.get<AdminCampaignDetail>(`/admin/campaigns/${campaignRef}`),
  emergencyPause: (campaignRef: string, reason: string) =>
    api.post<AdminCampaignDetail>(`/admin/campaigns/${campaignRef}/pause`, { reason }),
  emergencyClose: (campaignRef: string, reason: string) =>
    api.post<AdminCampaignDetail>(`/admin/campaigns/${campaignRef}/close`, { reason }),

  // earnings entries
  listEarningEntries: (params?: { creator_id?: string; campaign_id?: string; submission_id?: string; limit?: number; offset?: number }) =>
    api.get<AdminEarningEntryRow[]>(`/admin/earnings${qs(params ?? {})}`),
  earningEntryDetail: (entryId: string) => api.get<EarningEntryDetail>(`/admin/earnings/${entryId}`),
  holdEarnings: (submissionId: string, reason: string) =>
    api.post<AdminSubmissionDetail>(`/admin/earnings/${submissionId}/hold`, { reason }),
  releaseEarningsHold: (submissionId: string) => api.post<AdminSubmissionDetail>(`/admin/earnings/${submissionId}/release`, {}),

  // ledger
  unifiedLedger: (params?: { kind?: string; limit?: number; offset?: number }) =>
    api.get<AdminLedgerRow[]>(`/admin/ledger${qs(params ?? {})}`),
  ledgerEntryDetail: (entryId: string) => api.get<AdminLedgerRow>(`/admin/ledger/${entryId}`),

  // operators
  inviteOperator: (payload: { email: string; permissions: string[] }) =>
    api.post<AdminInvitationCreated>("/admin/operators/invitations", payload),
  listOperators: () => api.get<OperatorRow[]>("/admin/operators"),
  updateOperator: (operatorId: string, payload: { permissions?: string[] | null }) =>
    api.patch<OperatorRow>(`/admin/operators/${operatorId}`, payload),
  suspendOperator: (operatorId: string) => api.post<OperatorRow>(`/admin/operators/${operatorId}/suspend`, {}),
  restoreOperator: (operatorId: string) => api.post<OperatorRow>(`/admin/operators/${operatorId}/restore`, {}),

  // trust rules / provider health
  trustRules: () => api.get<unknown>("/admin/trust/rules"),
  providerHealth: () => api.get<ProviderHealth[]>("/admin/providers"),

  // system health / trust & delivery
  systemHealth: () => api.get<SystemHealth>("/admin/system/health"),
  webhookDelivery: () => api.get<DeliveryFeed>("/admin/delivery/webhooks"),
  socialDelivery: () => api.get<DeliveryFeed>("/admin/delivery/social"),
  notificationDelivery: () => api.get<DeliveryFeed>("/admin/delivery/notifications"),

  // support tickets
  supportQueue: (params?: { status?: string; category?: string; assignee_id?: string; priority?: string; limit?: number; offset?: number }) =>
    api.get<TicketOut[]>(`/admin/support/tickets${qs(params ?? {})}`),
  ticketDetail: (ticketId: string) => api.get<TicketAdminOut>(`/admin/support/tickets/${ticketId}`),
  updateTicket: (ticketId: string, payload: { status?: string; priority?: string; category?: string; assignee_id?: string | null }) =>
    api.patch<TicketAdminOut>(`/admin/support/tickets/${ticketId}`, payload),
  operatorReply: (ticketId: string, payload: { body: string; attachment_upload_ids?: string[] }) =>
    api.post<TicketAdminOut>(`/admin/support/tickets/${ticketId}/messages`, payload),
  addTicketNote: (ticketId: string, body: string) =>
    api.post<SupportNoteOut>(`/admin/support/tickets/${ticketId}/notes`, { body }),

  // disputes
  disputeQueue: (params?: { type?: string; status?: string; assignee_id?: string; limit?: number; offset?: number }) =>
    api.get<DisputeOut[]>(`/admin/disputes${qs(params ?? {})}`),
  disputeDetail: (disputeId: string) => api.get<DisputeAdminOut>(`/admin/disputes/${disputeId}`),
  updateDispute: (disputeId: string, payload: { assignee_id?: string | null; status?: string }) =>
    api.patch<DisputeAdminOut>(`/admin/disputes/${disputeId}`, payload),
  resolveDispute: (disputeId: string, payload: { resolution: string; note: string }) =>
    api.post<DisputeAdminOut>(`/admin/disputes/${disputeId}/resolve`, payload),
  reopenDispute: (disputeId: string) => api.post<DisputeAdminOut>(`/admin/disputes/${disputeId}/reopen`, {}),

  // reports
  reportQueue: (params?: { target_type?: string; status?: string; limit?: number; offset?: number }) =>
    api.get<ReportAdminOut[]>(`/admin/reports${qs(params ?? {})}`),
  reportDetail: (reportId: string) => api.get<ReportAdminOut>(`/admin/reports/${reportId}`),
  resolveReport: (reportId: string, payload: { resolution: string; note: string }) =>
    api.post<ReportAdminOut>(`/admin/reports/${reportId}/resolve`, payload),
};
