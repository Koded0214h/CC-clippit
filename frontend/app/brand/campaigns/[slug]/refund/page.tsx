import { CampaignRefundScreen } from "@/components/brand/BrandCampaignRecordScreens";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  return <CampaignRefundScreen slug={(await params).slug} />;
}
