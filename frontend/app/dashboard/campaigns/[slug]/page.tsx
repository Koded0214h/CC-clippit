import type { Metadata } from "next";
import { CampaignDetail } from "@/components/dashboard/DashboardScreens";

export const metadata: Metadata = { title: "Campaign" };

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <CampaignDetail slug={slug} />;
}
