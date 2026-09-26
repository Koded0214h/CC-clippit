"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { useUser } from "@/lib/user-context";
import { homeFor, onboardingFor } from "@/lib/api/onboarding";
import type { AccountRole } from "@/lib/auth";

export function RoleGate({ role, children }: { role: AccountRole; children: ReactNode }) {
  const router = useRouter();
  const { user, isLoading } = useUser();
  const wrongRole = !!user && user.role !== role;
  const needsOnboarding = !!user && user.role === role && !user.onboarding_completed;

  useEffect(() => {
    if (wrongRole && user) router.replace(user.role === "creator" || user.role === "organisation" ? homeFor(user.role) : "/");
    else if (needsOnboarding) router.replace(onboardingFor(role));
  }, [wrongRole, needsOnboarding, user, role, router]);

  if (isLoading || wrongRole || needsOnboarding) {
    return <ClippitLoader tone={role === "organisation" ? "gold" : "paper"} label="Opening your workspace" note="Making sure you land in the right place." />;
  }
  return <>{children}</>;
}
