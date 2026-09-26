import type { ReactNode } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import "../../styles/completion.css";

export default function DisputesLayout({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
