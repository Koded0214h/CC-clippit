import type { Metadata } from "next";
import { SecurityScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Security" };
export default function Page() { return <SecurityScreen />; }
