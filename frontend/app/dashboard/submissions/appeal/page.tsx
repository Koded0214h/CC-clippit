import type { Metadata } from "next";
import { AppealScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Appeal verdict" };
export default function Page() { return <AppealScreen />; }
