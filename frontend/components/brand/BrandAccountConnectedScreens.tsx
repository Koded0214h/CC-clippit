"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { ClippitEmptyState } from "@/components/ui/ClippitEmptyState";
import { ClippitLoader } from "@/components/ui/ClippitLoader";
import { ProductIcon } from "@/components/ui/ProductIcon";
import { authApi, type UserOut } from "@/lib/api/auth";
import { errorMessage } from "@/lib/api/client";
import { organisationsApi, type OrganisationProfileOut } from "@/lib/api/organisations";

function Status({ verified }: { verified: boolean }) {
  return <span className={`brand-status brand-status--${verified ? "lime" : "gold"}`}><i className="brand-status__dot" />{verified ? "Verified" : "Not verified"}</span>;
}

function Header({ title, copy, back, action }: { title: string; copy: string; back?: string; action?: ReactNode }) {
  return <header className="customer-head"><div>{back && <Link className="customer-back" href={back}><ProductIcon name="chevron" />Back</Link>}<h1>{title}</h1><p>{copy}</p></div>{action}</header>;
}

function useBrandAccount() {
  const [data, setData] = useState<{ profile: OrganisationProfileOut; user: UserOut } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([organisationsApi.getProfile(), authApi.me()])
      .then(([profile, user]) => setData({ profile, user }))
      .catch((reason) => setError(errorMessage(reason, "We couldn't load this organisation account.")));
  }, []);
  return { data, error };
}

export function BrandTeamConnectedScreen() {
  const { data, error } = useBrandAccount();
  if (!data && !error) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Loading team access" note="" /></div>;
  if (!data) return <div className="brand-page completion-workspace"><Header title="Team" copy={error} /></div>;
  const initials = (data.user.full_name || data.profile.name).split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  return <div className="brand-page completion-workspace">
    <Header title="Team" copy={`People who can access ${data.profile.name}.`} />
    <section className="team-board">
      <aside><strong><AnimatedNumber value={1} padStart={2} /></strong><span>account owner</span><p>This is the only account currently authorised to manage the organisation.</p></aside>
      <div><header><span>Member</span><span>Role</span><span>Status</span><span>Access</span></header><article><i>{initials || "YO"}</i><p><strong>{data.user.full_name}</strong><small>{data.user.email}</small></p><b>Owner</b><Status verified /><span aria-label="Full organisation access"><ProductIcon name="shield" /></span></article></div>
    </section>
    <ClippitEmptyState className="completion-empty" size="compact" tone="gold" icon="users" title="Team invitations are not available yet" copy="No invitations have been sent, and nobody else has access to this organisation." />
  </div>;
}

export function BrandInviteConnectedScreen() {
  return <div className="brand-page completion-workspace">
    <Header back="/brand/team" title="Invite a team member" copy="Team invitations are not available yet." />
    <ClippitEmptyState className="completion-empty" tone="gold" icon="users" title="Invitations are currently unavailable" copy="Your organisation still has one owner account. No invitation will be recorded or shown as sent." action={<Link className="brand-button" href="/support/tickets/new">Contact support<ProductIcon name="arrow" /></Link>} />
  </div>;
}

export function BrandVerificationConnectedScreen() {
  const { data, error } = useBrandAccount();
  if (!data && !error) return <div className="brand-page"><ClippitLoader contained tone="gold" label="Checking organisation status" note="" /></div>;
  if (!data) return <div className="brand-page completion-workspace"><Header title="Business verification" copy={error} /></div>;
  const { profile } = data;
  return <div className="brand-page completion-workspace">
    <Header title="Business verification" copy={profile.business_legal_name ?? profile.name} action={<Status verified={profile.business_verified} />} />
    {profile.business_verified ? <section className="verification-status"><div className="status-orbit"><i /><i /><i /><span><ProductIcon name="check" /></span><strong>Verified</strong><small>Your organisation status is current.</small></div><section><article className="is-complete"><span><ProductIcon name="check" /></span><p><strong>Business identity</strong><small>{profile.business_legal_name ?? profile.name}</small></p><Status verified /></article></section></section> : <ClippitEmptyState className="completion-empty" tone="gold" icon="shield" title="This organisation is not verified" copy="There is no verification submission attached to this account. Contact support if verification is required for an account action." action={<Link className="brand-button" href="/support/tickets/new">Contact support<ProductIcon name="arrow" /></Link>} />}
  </div>;
}
