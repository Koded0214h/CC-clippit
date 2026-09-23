import type { ReactNode } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
