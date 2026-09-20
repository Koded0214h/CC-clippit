import type { Metadata } from "next";
import { RejectedVerdictScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Clip needs attention" };
export default function Page() { return <RejectedVerdictScreen />; }
