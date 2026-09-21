import type { Metadata } from "next";
import { PublicProfileScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Public profile" };
export default function Page() { return <PublicProfileScreen />; }
