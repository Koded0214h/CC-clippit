import type { Metadata } from "next";
import { NotificationsScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Notifications" };
export default function Page() { return <NotificationsScreen />; }
