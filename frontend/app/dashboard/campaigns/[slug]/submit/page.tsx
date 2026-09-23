import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { SubmitClipScreen } from "@/components/creator/CreatorScreens";
import { campaigns } from "@/lib/product";

export const metadata: Metadata = { title: "Submit a clip" };
export function generateStaticParams() { return campaigns.map((campaign) => ({ slug: campaign.slug })); }
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!campaigns.some((campaign) => campaign.slug === slug)) notFound();
  return (
    <Suspense fallback={<div className="dashboard-page creator-flow-page" aria-busy="true" />}>
      <SubmitClipScreen campaignSlug={slug} />
    </Suspense>
  );
}
