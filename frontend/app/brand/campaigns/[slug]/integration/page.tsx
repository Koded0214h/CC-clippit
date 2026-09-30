import { CampaignIntegrationScreen } from "@/components/brand/BrandTracking";

export default async function CampaignIntegrationPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <CampaignIntegrationScreen slug={slug} />;
}
