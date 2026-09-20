export type BrandCampaignState = "Live" | "Draft" | "Completed" | "Funding";

export type BrandCampaign = {
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
};

export const brandCampaigns: BrandCampaign[] = [
  {
    slug: "no-long-thing",
    title: "No long thing",
    line: "Creator skits about hunger interrupting everyday moments.",
    state: "Live",
    image: "/assets/video/creator-reaction-poster.jpg",
    pot: 500000,
    remaining: 312500,
    rate: 500,
    verifiedViews: 375000,
    submissions: 84,
    approved: 61,
    review: 7,
    daysLeft: 4,
  },
  {
    slug: "late-night-bowl",
    title: "The late-night bowl",
    line: "Late-night meal routines from students and people working after hours.",
    state: "Draft",
    image: "/assets/photos/creator-vlogger-pexels-6954220.jpg",
    pot: 650000,
    remaining: 650000,
    rate: 650,
    verifiedViews: 0,
    submissions: 0,
    approved: 0,
    review: 0,
    daysLeft: 14,
  },
  {
    slug: "campus-chop",
    title: "Campus chop stories",
    line: "Student meal routines filmed on campus.",
    state: "Completed",
    image: "/assets/photos/street-style.jpg",
    pot: 350000,
    remaining: 0,
    rate: 400,
    verifiedViews: 875000,
    submissions: 126,
    approved: 93,
    review: 0,
    daysLeft: 0,
  },
];

export type BrandReview = {
  id: string;
  creator: string;
  handle: string;
  title: string;
  platform: "TikTok" | "Instagram" | "YouTube";
  image: string;
  confidence: number;
  issue: string;
  submitted: string;
};

export const brandReviews: BrandReview[] = [
  {
    id: "submission-1042",
    creator: "Kemi Frames",
    handle: "@kemiframes",
    title: "When hunger joins the group call",
    platform: "TikTok",
    image: "/assets/photos/creator-studio-pexels-8359963.jpg",
    confidence: 68,
    issue: "Product pack is partly hidden during the required reveal.",
    submitted: "8 min ago",
  },
  {
    id: "submission-1038",
    creator: "Nana Edits",
    handle: "@nanaedits",
    title: "No light, still no long thing",
    platform: "Instagram",
    image: "/assets/photos/fashion.jpg",
    confidence: 74,
    issue: "The spoken campaign phrase may be covered by background audio.",
    submitted: "21 min ago",
  },
  {
    id: "submission-1029",
    creator: "Deji Does It",
    handle: "@dejidoesit",
    title: "The fastest flatmate alive",
    platform: "YouTube",
    image: "/assets/photos/headphones.jpg",
    confidence: 71,
    issue: "The video length is one second over the brief limit.",
    submitted: "46 min ago",
  },
];
