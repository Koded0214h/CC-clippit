import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ProductShell } from "@/components/dashboard/ProductShell";
import { AuthGuard } from "@/components/auth/AuthGuard";

export const metadata: Metadata = {
  title: "Creator dashboard",
  description: "Campaigns, verified views and creator earnings in one place.",
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <ProductShell>{children}</ProductShell>
    </AuthGuard>
  );
}
