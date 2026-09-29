"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authApi, getAccessToken } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { ClippitLoader } from "@/components/ui/ClippitLoader";

export function AdminGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return <AdminAccessGuard key={pathname}>{children}</AdminAccessGuard>;
}

function AdminAccessGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [verifiedPath, setVerifiedPath] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const login = pathname === "/admin/login";

  useEffect(() => {
    if (login) return;
    let active = true;
    const signIn = () => router.replace(`/admin/login?next=${encodeURIComponent(pathname)}`);
    if (!getAccessToken()) { signIn(); return; }
    authApi.me().then((user) => {
      if (!active) return;
      if ((user.role as string) !== "admin") { signIn(); return; }
      setVerifiedPath(pathname);
    }).catch((error) => {
      if (!active) return;
      if (error instanceof ApiError && [401, 403].includes(error.status)) signIn();
      else setFailed(true);
    });
    return () => { active = false; };
  }, [pathname, router, login, attempt]);

  if (login) return <>{children}</>;
  if (failed) return <main className="admin-access-error"><h1>We couldn’t verify your access</h1><p>Check your connection and try again.</p><button type="button" onClick={() => { setFailed(false); setAttempt((n) => n + 1); }}>Try again</button></main>;
  if (verifiedPath !== pathname) return <ClippitLoader tone="ink" label="Checking operator access" note="Verifying your admin session." />;
  return <>{children}</>;
}
