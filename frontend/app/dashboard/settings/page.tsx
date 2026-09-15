import type { Metadata } from "next";
import { SettingsScreen } from "@/components/dashboard/DashboardScreens";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return <SettingsScreen />;
}
