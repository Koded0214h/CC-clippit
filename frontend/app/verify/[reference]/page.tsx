import { ReceiptVerificationScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ reference: string }> }) {
  return <ReceiptVerificationScreen reference={(await params).reference} />;
}
