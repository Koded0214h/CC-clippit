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

  // Keep protected content hidden while the local session is checked.
  if (!allowed) return null;
  return <>{children}</>;
}
