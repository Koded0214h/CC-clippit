import type { Metadata } from "next";
import { LeaderboardScreen } from "@/components/dashboard/DashboardScreens";

export const metadata: Metadata = { title: "Leaderboard" };

export default function Page() {
  return <LeaderboardScreen />;
}
