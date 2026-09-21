import type { Metadata } from "next";
import { BrandTransactionsScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Transactions" };
export default function Page() { return <BrandTransactionsScreen />; }
