import type { Metadata } from "next";
import { PayoutAccountScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Payout account" };
export default function Page() { return <PayoutAccountScreen />; }
