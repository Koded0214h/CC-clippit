export type CampaignStatus = "Open" | "Closing soon" | "Joined";

export interface Campaign {
  slug: string;
  brand: string;
  title: string;
  line: string;
  image: string;
  rate: number;
  pot: number;
  remaining: number;
  daysLeft: number;
  hoursLeft: number;
  platforms: string[];
  category: string;
  status: CampaignStatus;
  minimumViews: number;
  creatorCap: number;
  videoCap: number;
  maxSubmissions: number;
  accessMode: "public" | "invite";
  assets: Array<{ name: string; url: string; kind: string }>;
  endCondition: string;
  brief: string;
  mustDo: string[];
  mustAvoid: string[];
  id?: string;
  endsAt?: string | null;
  acceptingEntries?: boolean;
  performanceMetrics?: Array<{
    metricType: string;
    rate: number;
    unitSize: number;
    minimum: number;
  }>;
  conversionDestinationType?: "website" | "whatsapp" | null;
}

export const money = (value: number) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(value);

export const compactNumber = (value: number) =>
  new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
