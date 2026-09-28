import { BrandInvoiceScreen } from "@/components/brand/BrandBillingConnected";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  return <BrandInvoiceScreen id={(await params).id} />;
}
