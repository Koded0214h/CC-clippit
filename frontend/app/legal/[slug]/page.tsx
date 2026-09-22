import { ProductionLegalDocumentScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  return <ProductionLegalDocumentScreen slug={(await params).slug} />;
}
