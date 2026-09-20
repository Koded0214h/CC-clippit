import type { Metadata } from "next";
import { MyClipsScreen } from "@/components/creator/CreatorScreens";

export const metadata: Metadata = { title: "My clips" };
export default function Page() { return <MyClipsScreen />; }
