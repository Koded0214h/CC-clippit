import { api } from "./client";

export interface BankDestinationOut {
  bank_code: string;
  bank_name: string;
  account_number_masked: string;
  account_name: string;
}

export interface SourceRowOut {
  campaign_title: string;
  clip: string;
  amount: number;
}

export interface ProvenanceOut {
  approved_clips: number;
  campaigns: string[];
  billable_views: number;
  sources: SourceRowOut[];
}

export interface PayoutOut {
  id: string;
  reference: string;
  status: "pending" | "processing" | "succeeded" | "failed" | string;
  amount: number;
  fee: number;
  net: number;
  creator_name: string;
  destination: BankDestinationOut;
  provider: string;
  sandbox: boolean;
  failure_reason: string | null;
  initiated_at: string;
  completed_at: string | null;
  provenance: ProvenanceOut | null;
}

export interface PayoutListOut {
  items: PayoutOut[];
  total: number;
}

export interface PayoutCreateIn {
  amount: number;
  idempotency_key: string;
}

export interface PayoutQuoteOut {
  amount: number;
  fee: number;
  net_amount: number;
  currency: string;
  valid_for_minutes: number;
}

export const payoutsApi = {
  quote: (payload: PayoutCreateIn) => api.post<PayoutQuoteOut>("/payouts/quote", payload),

  withdraw: (payload: PayoutCreateIn) => api.post<PayoutOut>("/payouts", payload),

  list: (params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    const qs = query.toString();
    return api.get<PayoutListOut>(`/payouts${qs ? `?${qs}` : ""}`);
  },

  get: (payoutId: string) => api.get<PayoutOut>(`/payouts/${payoutId}`),
};
