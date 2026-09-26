import type { ReactNode } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import "../../styles/product.css";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
