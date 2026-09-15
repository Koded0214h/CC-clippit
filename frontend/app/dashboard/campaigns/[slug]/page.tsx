import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CampaignDetail } from "@/components/dashboard/DashboardScreens";
import { campaigns } from "@/lib/product";

export function generateStaticParams() {
  return campaigns.map((campaign) => ({ slug: campaign.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const campaign = campaigns.find((item) => item.slug === slug);
  return { title: campaign ? `${campaign.title} campaign` : "Campaign" };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const campaign = campaigns.find((item) => item.slug === slug);
  if (!campaign) notFound();
  return <CampaignDetail campaign={campaign} />;
}
