import type { Metadata } from "next";
import { CampaignCloseoutScreen } from "@/components/brand/BrandCampaignRecordScreens";

export const metadata: Metadata = { title: "Campaign closeout" };
export default async function Page({ params }: { params: Promise<{ slug: string }> }) { return <CampaignCloseoutScreen slug={(await params).slug} />; }
