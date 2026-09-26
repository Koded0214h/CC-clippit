import type { Metadata } from "next";
import { Suspense } from "react";
import { SubmitClipScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Submit a clip" };

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <Suspense fallback={<div className="dashboard-page creator-flow-page" aria-busy="true" />}>
      <SubmitClipScreen campaignSlug={slug} />
    </Suspense>
  );
}
