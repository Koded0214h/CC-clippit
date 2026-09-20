import type { Metadata } from "next";
import { ConnectedAccountsScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Connected accounts" };
export default function Page() { return <ConnectedAccountsScreen />; }
