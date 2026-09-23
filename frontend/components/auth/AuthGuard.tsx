"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/api/auth";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (getAccessToken()) {
      setAllowed(true);
    } else {
      router.replace("/auth/sign-in");
    }
  }, [router]);

  // Render nothing while checking — avoids a flash of protected content.
  if (!allowed) return null;
  return <>{children}</>;
}
