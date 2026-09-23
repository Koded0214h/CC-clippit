import { api } from "./client";
import type { CampaignOut } from "./campaigns";
import type { EarningsSummary } from "./earnings";

export interface CreatorOverview {
  closing_soon: CampaignOut | null;
  new_matches: number;
  earnings: EarningsSummary;
}

export const creatorApi = {
  overview: () => api.get<CreatorOverview>("/creators/me/overview"),
};
