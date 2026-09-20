import type { Metadata } from "next";
import { VerificationProgressScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "Checking your clip" };
export default function Page() { return <VerificationProgressScreen />; }
