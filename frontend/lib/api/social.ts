import { api, API_URL } from "./client";

export interface ConnectedAccountOut {
  platform: string;
  connectable: boolean;
  connected: boolean;
  handle: string | null;
  display_name: string | null;
  connected_at: string | null;
  last_checked_at: string | null;
}

export interface CreatorProfileOut {
  user_id: string;
  display_name: string;
  handle: string | null;
  public_profile: boolean;
  bio: string | null;
  photo_url: string | null;
  interests: string[];
  platforms: string[];
  discovery_source: string | null;
  experience: string | null;
  goals: string[];
  country?: string | null;
  location?: string | null;
  viewing_interests?: string[];
  onboarding_completed?: boolean;
  updated_at?: string;
}

export interface CreatorProfileUpdate {
  display_name?: string;
  handle?: string;
  public_profile?: boolean;
  bio?: string;
  interests?: string[];
  photo_upload_id?: string;
  country?: string;
  location?: string;
}

export interface HandleAvailability {
  handle: string;
  available: boolean;
  reason: string | null;
}

export const socialApi = {
  accounts: () => api.get<ConnectedAccountOut[]>("/creators/me/accounts"),
  disconnect: (platform: string) => api.delete<void>(`/social/${platform.toLowerCase()}`),
  syncProfile: (platform: string) =>
    api.post<ConnectedAccountOut>(`/social/${platform.toLowerCase()}/sync-profile`, {}),
  connectUrl: (platform: string) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("clippit:access-token") ?? "" : "";
    return `${API_URL}/social/${platform.toLowerCase()}/login?token=${encodeURIComponent(token)}`;
  },
};

export const handlesApi = {
  availability: (handle: string) => api.get<HandleAvailability>(`/handles/${encodeURIComponent(handle)}/availability`),
};

export const creatorProfileApi = {
  get: () => api.get<CreatorProfileOut>("/creators/me/profile"),
  update: (payload: CreatorProfileUpdate) => api.put<CreatorProfileOut>("/creators/me/profile", payload),
};
