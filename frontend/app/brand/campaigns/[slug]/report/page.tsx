import type { Metadata } from "next";
import { CampaignCloseoutScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Campaign closeout" };
export default function Page() { return <CampaignCloseoutScreen />; }
