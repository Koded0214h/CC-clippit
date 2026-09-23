import type { Metadata } from "next";
import { BrandWalletWithdrawScreen } from "@/components/wallet/WalletScreens";

export const metadata: Metadata = { title: "Withdraw from Brand wallet" };
export default function Page() { return <BrandWalletWithdrawScreen />; }
