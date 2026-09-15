import type { Metadata } from "next";
import { CreatorOnboarding } from "@/components/onboarding/OnboardingFlow";

export const metadata: Metadata = {
  title: "Creator setup",
  description: "Shape your creator profile and campaign feed.",
};

export default function Page() {
  return <CreatorOnboarding />;
}
