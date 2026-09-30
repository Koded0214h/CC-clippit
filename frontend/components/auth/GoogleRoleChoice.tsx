"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState } from "react";
import { authApi, storeTokens } from "@/lib/api/auth";
import { errorMessage } from "@/lib/api/client";
import type { AccountRole } from "@/lib/auth";
import { AuthButton } from "./AuthScreen";

export function GoogleRoleChoice() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [role, setRole] = useState<AccountRole>("creator");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(token ? "" : "This Google sign-up link is incomplete. Start again from sign in.");

  const submit = async () => {
    if (!token || busy) return;
    setBusy(true);
    setError("");
    try {
      const session = await authApi.completeGoogleSignup({ token, role });
      storeTokens(session, "persistent");
      router.replace(role === "creator" ? "/onboarding/creator" : "/onboarding/brand");
    } catch (err) {
      setError(errorMessage(err, "We couldn't finish your Google sign-up. Start again from sign in."));
      setBusy(false);
    }
  };

  return <form className="auth-screen auth-role-choice" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <header><span className="auth-eyebrow">One last choice</span><h1>How will you use Clippit?</h1><p>Choose the workspace you need. This sets the account role and cannot be changed from settings.</p></header>
    <div className="auth-role-options" role="radiogroup" aria-label="Account type">
      <button type="button" role="radio" aria-checked={role === "creator"} className={role === "creator" ? "is-selected" : ""} onClick={() => setRole("creator")}><strong>Creator</strong><span>Join campaigns, submit clips and earn from verified views.</span></button>
      <button type="button" role="radio" aria-checked={role === "organisation"} className={role === "organisation" ? "is-selected" : ""} onClick={() => setRole("organisation")}><strong>Brand or organisation</strong><span>Create, fund and manage creator campaigns.</span></button>
    </div>
    {error && <p className="auth-error" role="alert">{error}</p>}
    <AuthButton loading={busy} loadingLabel="Creating your workspace" disabled={!token}>Continue</AuthButton>
    <a className="auth-secondary-link" href="/auth/sign-in">Back to sign in</a>
  </form>;
}
