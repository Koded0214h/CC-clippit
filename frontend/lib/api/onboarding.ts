import { api } from "./client";

export type PlatformValue = "tiktok" | "instagram" | "facebook" | "threads" | "x" | "youtube";

export interface OnboardingDraftOut {
  status: "not_started" | "in_progress" | "completed";
  step: string | null;
  revision: number;
  answers: Record<string, unknown>;
  completed_at: string | null;
}

export interface CreatorOnboardingIn {
  display_name: string;
  interests: string[];
  platforms: PlatformValue[];
  photo_upload_id?: string | null;
  discovery_source?: string | null;
  experience?: string | null;
  goals: string[];
  location?: string | null;
  viewing_interests: string[];
}

export interface CreatorProfileOut {
  display_name: string;
  bio: string | null;
  photo_url: string | null;
  onboarding_completed: boolean;
}

export interface OrganisationOnboardingIn {
  name: string;
  bio?: string | null;
  website?: string | null;
  photo_upload_id?: string | null;
  production_workflow?: string | null;
  team_size?: string | null;
  campaign_goal?: string | null;
  budget_range?: string | null;
  contact_name?: string | null;
  location?: string | null;
  funder_type?: "brand" | "individual" | null;
  registered?: boolean | null;
  content_interests: string[];
  viewing_interests: string[];
  discovery_source?: string | null;
}

export interface OrganisationProfileOut {
  name: string;
  bio: string | null;
  photo_url: string | null;
  onboarding_completed: boolean;
}

export interface UploadOut {
  id: string;
  url: string;
}

export const onboardingApi = {
  creatorDraft: () => api.get<OnboardingDraftOut>("/creators/me/onboarding"),
  saveCreatorDraft: (payload: Record<string, unknown> & { revision: number }) =>
    api.patch<OnboardingDraftOut>("/creators/me/onboarding", payload),
  completeCreator: (payload: CreatorOnboardingIn) =>
    api.put<CreatorProfileOut>("/creators/me/onboarding", payload),
  creatorProfile: () => api.get<CreatorProfileOut>("/creators/me/profile"),

  organisationDraft: () => api.get<OnboardingDraftOut>("/organisations/me/onboarding"),
  saveOrganisationDraft: (payload: Record<string, unknown> & { revision: number }) =>
    api.patch<OnboardingDraftOut>("/organisations/me/onboarding", payload),
  completeOrganisation: (payload: OrganisationOnboardingIn) =>
    api.put<OrganisationProfileOut>("/organisations/me/onboarding", payload),
  organisationProfile: () => api.get<OrganisationProfileOut>("/organisations/me/profile"),

  uploadPhoto: async (dataUrl: string) => {
    const blob = await (await fetch(dataUrl)).blob();
    const form = new FormData();
    form.append("file", blob, "profile.jpg");
    return api.upload<UploadOut>("/uploads/images", form);
  },
};

export const PLATFORM_VALUES: Record<string, PlatformValue> = {
  TikTok: "tiktok",
  Instagram: "instagram",
  Facebook: "facebook",
  Threads: "threads",
  X: "x",
  YouTube: "youtube",
};

export function homeFor(role: string) {
  return role === "organisation" ? "/brand" : "/dashboard";
}

export function onboardingFor(role: string) {
  return role === "organisation" ? "/onboarding/brand" : "/onboarding/creator";
}
