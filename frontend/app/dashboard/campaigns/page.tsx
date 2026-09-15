import type { Metadata } from "next";
import { CampaignDirectory } from "@/components/dashboard/DashboardScreens";

export const metadata: Metadata = { title: "Campaigns" };

export default function Page() {
  return <CampaignDirectory />;
}
