"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { ButtonLoader } from "@/components/ui/ClippitLoader";
import { authApi, clearTokens, storeTokens } from "@/lib/api/auth";
import { errorMessage } from "@/lib/api/client";
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = Date.now() - then;
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function untilTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = then - Date.now();
  if (diffMs <= 0) return "Overdue";
  const days = Math.floor(diffMs / 86400000);
  if (days >= 1) return `${days}d left`;
  const hours = Math.round(diffMs / 3600000);
  return `${hours}h left`;
}

export function titleCase(value: string): string {
  return value.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export type Tone = "lime" | "gold" | "red" | "blue" | "ink" | "paper";

export function AdminStatus({ children, tone = "paper" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`admin-status admin-status--${tone}`}><i />{children}</span>;
}

export function AdminHeading({ title, copy, eyebrow, action, back }: { title: string; copy?: string; eyebrow?: string; action?: ReactNode; back?: string }) {
  return <header className="admin-heading"><div>{back && <Link className="admin-back" href={back}><ProductIcon name="chevron" />Back</Link>}{eyebrow && <span>{eyebrow}</span>}<h1>{title}</h1>{copy && <p>{copy}</p>}</div>{action}</header>;
}

export function AdminButton({ children, tone = "lime", onClick, type = "button", disabled }: { children: ReactNode; tone?: "lime" | "ink" | "gold"; onClick?: () => void; type?: "button" | "submit"; disabled?: boolean }) {
  return <button className={`admin-button admin-button--${tone}`} type={type} onClick={onClick} disabled={disabled} aria-busy={disabled}>{disabled ? <ButtonLoader label="Opening operations" /> : <>{children}<ProductIcon name="arrow" /></>}</button>;
}

export function AdminLoginScreen() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = event.currentTarget;
    const email = (form.querySelector('input[type="email"]') as HTMLInputElement | null)?.value ?? "";
    const password = (form.querySelector('input[type="password"]') as HTMLInputElement | null)?.value ?? "";
    setBusy(true);
    setError("");
    try {
      const session = await authApi.adminLogin({ email: email.trim(), password });
      if ((session.user.role as string) !== "admin") {
        clearTokens();
        setError("This account does not have operator access.");
        return;
      }
      storeTokens(session, "session");
      const next = new URLSearchParams(window.location.search).get("next");
      const destination = next && /^\/admin(?:\/|$)/.test(next) && !next.includes("\\") && !next.startsWith("/admin/login") ? next : "/admin";
      router.replace(destination);
    } catch {
      setError("Unable to sign in. Check your administrator email and password, then try again.");
    } finally {
      setBusy(false);
    }
  };
  return <main className="admin-login"><section><Link href="/"><Image src="/assets/clippit-mark-light.png" width={44} height={44} alt="" /><strong>Clippit</strong><span>operations</span></Link><div className="admin-login__signal"><i /><i /><i /><span><ProductIcon name="shield" /></span></div><blockquote>Customer money and decisions require an accountable operator.</blockquote><small>Restricted workspace · actions are written to the audit log</small></section><form onSubmit={submit}><AdminStatus tone="gold">Operator access</AdminStatus><h1>Sign in to operations.</h1><p>Sign in with your administrator email and password.</p><label><span>Work email</span><input type="email" name="email" autoComplete="username" placeholder="you@example.com" disabled={busy} required /></label><label><span>Password</span><input type="password" name="password" autoComplete="current-password" placeholder="Enter your password" disabled={busy} required /></label><div className="admin-login__key"><ProductIcon name="shield" /><span><strong>Administrator access only</strong><small>Your session ends when this browser session closes.</small></span></div><div aria-live="polite">{error && <p className="admin-login-error" role="alert">{error}</p>}</div><AdminButton type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in to operations"}</AdminButton><Link href="/support/tickets/new">Cannot access your operator account?</Link></form></main>;
}

export function AdminInvitationScreen() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [invitation, setInvitation] = useState<{ status: string; email: string | null; permissions: string[] | null } | null>(
    token ? null : { status: "invalid", email: null, permissions: null },
  );
  const [loading, setLoading] = useState(Boolean(token));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    authApi.adminInvitation(token)
      .then((value) => { if (active) setInvitation(value); })
      .catch(() => { if (active) setInvitation({ status: "invalid", email: null, permissions: null }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || busy) return;
    const form = new FormData(event.currentTarget);
    const fullName = String(form.get("full_name") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");
    if (password !== confirmation) { setError("Passwords do not match."); return; }
    setBusy(true); setError("");
    try {
      const session = await authApi.acceptAdminInvitation(token, { full_name: fullName, password });
      storeTokens(session, "session");
      router.replace("/admin");
    } catch (err) {
      setError(errorMessage(err, "This invitation could not be accepted. It may have expired or already been used."));
    } finally { setBusy(false); }
  };

  const unavailable = invitation?.status !== "valid";
  return <main className="admin-login"><section><Link href="/"><Image src="/assets/clippit-mark-light.png" width={44} height={44} alt="" /><strong>Clippit</strong><span>operations</span></Link><div className="admin-login__signal"><i /><i /><i /><span><ProductIcon name="shield" /></span></div><blockquote>Join the operations team with your own accountable operator identity.</blockquote><small>Restricted workspace · every action is recorded</small></section><form onSubmit={submit}><AdminStatus tone="gold">Operator invitation</AdminStatus><h1>{loading ? "Checking invitation…" : unavailable ? "Invitation unavailable" : "Create your operator account."}</h1>{loading ? <p>Please wait while we verify this invitation.</p> : unavailable ? <><p>{invitation?.status === "expired" ? "This invitation has expired. Ask an administrator to send a new one." : invitation?.status === "used" ? "This invitation has already been accepted." : "This invitation link is invalid."}</p><Link href="/admin/login">Go to operator sign in</Link></> : <><p>This invitation is for <strong>{invitation?.email}</strong>.</p>{invitation?.permissions?.length ? <p>Access: {invitation.permissions.map(titleCase).join(", ")}</p> : <p>This account will receive full operator access.</p>}<label><span>Full name</span><input name="full_name" autoComplete="name" minLength={2} maxLength={200} disabled={busy} required /></label><label><span>Password</span><input type="password" name="password" autoComplete="new-password" minLength={8} pattern="(?=.*[0-9]).{8,}" title="Use at least 8 characters and include a number." disabled={busy} required /></label><label><span>Confirm password</span><input type="password" name="confirmation" autoComplete="new-password" minLength={8} disabled={busy} required /></label>{error && <p className="admin-login-error" role="alert">{error}</p>}<AdminButton type="submit" disabled={busy}>{busy ? "Creating account…" : "Accept invitation"}</AdminButton></>}</form></main>;
}


export { AdminCommandCentreScreen, AdminQueueScreen, AdminDetailScreen, AdminLedgerScreen, AdminReconciliationScreen, AdminOperatorsScreen, AdminInviteOperatorScreen, AdminRolesScreen, AdminAuditScreen, AdminReviewIndexScreen } from "./AdminLive";
