import type { Metadata } from "next";
import { BrandNotificationsConnected } from "@/components/brand/BrandNotificationsConnected";

export const metadata: Metadata = { title: "Notifications" };

export default function Page() {
  return <BrandNotificationsConnected />;
}
