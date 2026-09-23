import type { Metadata } from "next";
import { BrandWalletFundScreen } from "@/components/wallet/WalletScreens";

export const metadata: Metadata = { title: "Add money to Brand wallet" };
export default function Page() { return <BrandWalletFundScreen />; }
