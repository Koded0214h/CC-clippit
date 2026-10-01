export type BrandCampaignState = "Live" | "Paused" | "Draft" | "Completed" | "Cancelled" | "Funding";

export type BrandCampaign = {
  brandName?: string;
  slug: string;
  title: string;
  line: string;
  state: BrandCampaignState;
  image: string;
  pot: number;
  remaining: number;
  rate: number;
  verifiedViews: number;
  submissions: number;
  approved: number;
  review: number;
  daysLeft: number;
  endCondition: "duration" | "budget";
};

export type BrandReview = {
  id: string;
  creator: string;
  handle: string;
  title: string;
  platform: string;
  image: string;
  issue: string;
  submitted: string;
};
