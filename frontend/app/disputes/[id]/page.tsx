import { ProductionDisputeDetailScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <ProductionDisputeDetailScreen id={(await params).id} />;
}
