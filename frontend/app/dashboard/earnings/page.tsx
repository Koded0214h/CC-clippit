import type { Metadata } from "next";
import { EarningsScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Earnings" };
export default function Page() { return <EarningsScreen />; }
