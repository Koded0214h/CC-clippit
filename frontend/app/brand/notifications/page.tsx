import type { Metadata } from "next";
import { BrandNotificationsScreen } from "@/components/customer/CustomerScreens";

export const metadata: Metadata = { title: "Notifications" };

export default function Page() {
  return <BrandNotificationsScreen />;
}
