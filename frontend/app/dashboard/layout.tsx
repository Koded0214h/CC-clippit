import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ProductShell } from "@/components/dashboard/ProductShell";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { UserProvider } from "@/lib/user-context";
import "../../styles/product.css";

export const metadata: Metadata = {
  title: "Creator dashboard",
  description: "Campaigns, verified views and creator earnings in one place.",
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <AuthGuard>
        <ProductShell>{children}</ProductShell>
      </AuthGuard>
    </UserProvider>
  );
}
