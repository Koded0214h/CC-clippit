import { CampaignRefundScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  return <CampaignRefundScreen slug={(await params).slug} />;
}
