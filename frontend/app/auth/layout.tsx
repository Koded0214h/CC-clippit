import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthFlowProvider } from "@/components/auth/AuthFlowProvider";
import { AuthShell } from "@/components/auth/AuthShell";
import "@/styles/auth.css";

export const metadata: Metadata = {
  title: "Account access",
  description: "Create or access your Clippit account.",
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <AuthFlowProvider>
      <AuthShell>{children}</AuthShell>
    </AuthFlowProvider>
  );
}
