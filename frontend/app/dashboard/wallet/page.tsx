import type { Metadata } from "next";
import { CreatorWalletScreen } from "@/components/wallet/WalletScreens";

export const metadata: Metadata = { title: "Creator wallet" };
export default function Page() { return <CreatorWalletScreen />; }
