import type { Metadata } from "next";
import { WithdrawScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Withdraw" };
export default function Page() { return <WithdrawScreen />; }
