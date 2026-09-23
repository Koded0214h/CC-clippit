import type { Metadata } from "next";
import { BrandWalletScreen } from "@/components/wallet/WalletScreens";

export const metadata: Metadata = { title: "Brand wallet" };
export default function Page() { return <BrandWalletScreen />; }
