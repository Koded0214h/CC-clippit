import { api } from "./client";

export interface OrganisationProfileOut {
  user_id: string;
  name: string;
  slug: string | null;
  public_profile: boolean;
  bio: string | null;
  website: string | null;
  photo_url: string | null;
  finance_email: string | null;
  business_legal_name: string | null;
  business_verified: boolean;
  production_workflow: string | null;
  team_size: string | null;
  campaign_goal: string | null;
  budget_range: string | null;
  updated_at: string;
}

export interface OrganisationProfileUpdate {
  name?: string;
  bio?: string;
  website?: string;
  finance_email?: string;
  photo_upload_id?: string;
}

export interface OrganisationTransactionOut {
  id: string;
  kind: string;
  campaign_id: string;
  campaign_title: string;
  amount: number;
  fee: number | null;
  status: string;
  provider: string;
  provider_reference: string | null;
  reference: string;
  created_at: string;
  settled_at: string | null;
}

export interface OrganisationTransactionsOut {
  items: OrganisationTransactionOut[];
  total: number;
}

export const organisationsApi = {
  getProfile: () => api.get<OrganisationProfileOut>("/organisations/me/profile"),
  updateProfile: (payload: OrganisationProfileUpdate) => api.put<OrganisationProfileOut>("/organisations/me/profile", payload),
  transactions: (params?: { campaign_id?: string; kind?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.campaign_id) query.set("campaign_id", params.campaign_id);
    if (params?.kind) query.set("kind", params.kind);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    const suffix = query.toString();
    return api.get<OrganisationTransactionsOut>(`/organisations/me/transactions${suffix ? `?${suffix}` : ""}`);
  },
  transaction: (id: string) => api.get<OrganisationTransactionOut>(`/organisations/me/transactions/${id}`),
};
