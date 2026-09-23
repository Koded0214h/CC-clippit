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

export const organisationsApi = {
  getProfile: () => api.get<OrganisationProfileOut>("/organisations/me/profile"),
  updateProfile: (payload: OrganisationProfileUpdate) => api.put<OrganisationProfileOut>("/organisations/me/profile", payload),
};
