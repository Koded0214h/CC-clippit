import type { Metadata } from "next";
import { ApprovedVerdictScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Clip approved" };
export default function Page() { return <ApprovedVerdictScreen />; }
