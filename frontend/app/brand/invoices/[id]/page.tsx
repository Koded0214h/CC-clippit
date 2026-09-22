import { BrandInvoiceScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <BrandInvoiceScreen id={(await params).id} />;
}
