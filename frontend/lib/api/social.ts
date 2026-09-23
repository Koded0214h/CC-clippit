import { api } from "./client";

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
}

export interface CreatorProfileUpdate {
  display_name?: string;
  handle?: string;
  bio?: string;
  interests?: string[];
  photo_upload_id?: string;
}

export const socialApi = {
  accounts: () => api.get<ConnectedAccountOut[]>("/social/accounts"),
  disconnect: (platform: string) => api.delete<void>(`/social/${platform}`),
};

export const creatorProfileApi = {
  get: () => api.get<CreatorProfileOut>("/creators/me/profile"),
  update: (payload: CreatorProfileUpdate) => api.put<CreatorProfileOut>("/creators/me/profile", payload),
};
