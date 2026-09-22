import { ProductionSupportTicketDetailScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <ProductionSupportTicketDetailScreen id={(await params).id} />;
}
