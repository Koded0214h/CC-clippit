import { BrandReviewDetailScreen } from "@/components/brand/BrandReviewDetailConnected";

export default async function BrandReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BrandReviewDetailScreen id={id} />;
}
