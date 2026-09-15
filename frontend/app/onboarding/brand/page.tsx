import type { Metadata } from "next";
import { BrandOnboarding } from "@/components/onboarding/OnboardingFlow";

export const metadata: Metadata = {
  title: "Brand setup",
  description: "Set your organisation's content direction and campaign goals.",
};

export default function Page() {
  return <BrandOnboarding />;
}
