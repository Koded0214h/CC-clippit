"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/api/auth";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { AUTH_PROTECTION_ENABLED } from "@/lib/auth-protection";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (!AUTH_PROTECTION_ENABLED) {
      setAllowed(true);
      return;
    }
    if (pathname === "/admin/login" || getAccessToken()) {
      setAllowed(true);
    } else {
      setAllowed(false);
      router.replace("/auth/sign-in");
    }
  }, [pathname, router]);

  if (!AUTH_PROTECTION_ENABLED) return <>{children}</>;

  if (!allowed) {
    const admin = pathname.startsWith("/admin");
    const brand = pathname.startsWith("/brand");
    return <ClippitLoader tone={admin ? "ink" : brand ? "gold" : "paper"} label="Checking your session" note="Opening the right Clippit workspace for you." />;
  }
  return <>{children}</>;
}
