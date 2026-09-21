import type { Metadata } from "next";
import { BrandTransactionReceiptScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Transaction receipt" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BrandTransactionReceiptScreen transactionId={decodeURIComponent(id)} />;
}
