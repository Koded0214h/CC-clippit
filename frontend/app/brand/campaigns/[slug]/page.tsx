import { LiveCampaignScreen } from "@/components/brand/BrandScreens";

export default async function BrandLiveCampaignPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <LiveCampaignScreen slug={slug} />;
}
