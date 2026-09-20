import type { Metadata } from "next";
import { PayoutReceiptScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Payout receipt" };
export default function Page() { return <PayoutReceiptScreen />; }
